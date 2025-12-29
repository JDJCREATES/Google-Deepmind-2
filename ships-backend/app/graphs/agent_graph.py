"""
ShipS* Agent Graph

Creates a multi-agent StateGraph using LangGraph for 
orchestrating Planner → Coder → Validator → Fixer flow.

This is the modern approach using:
- StateGraph for workflow definition
- create_react_agent for individual agents
- Conditional edges for routing
- State persistence with checkpointing
"""

from typing import TypedDict, Annotated, Literal, Optional, List, Dict, Any
from operator import add

from langgraph.graph import StateGraph, END, START
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

from app.agents.agent_factory import AgentFactory
from app.agents.tools.coder import set_project_root  # Secure project path context


# ============================================================================
# STATE DEFINITION  
# ============================================================================

class AgentGraphState(TypedDict):
    """State shared across all agents in the graph."""
    
    # Messages for conversation (trimmed for token efficiency)
    messages: Annotated[List[BaseMessage], add]
    
    # Current phase
    phase: Literal["planning", "coding", "validating", "fixing", "complete", "error"]
    
    # Artifacts produced by agents
    artifacts: Dict[str, Any]
    
    # Tool results stored separately from messages (token optimization)
    # Only metadata/references go in messages, full results here
    tool_results: Dict[str, Any]
    
    # Current task being worked on
    current_task_index: int
    
    # Validation status
    validation_passed: bool
    
    # Fix attempts
    fix_attempts: int
    max_fix_attempts: int
    
    # Final result
    result: Optional[Dict[str, Any]]


# ============================================================================
# NODE FUNCTIONS
# ============================================================================

import logging
logger = logging.getLogger("ships.agent")

async def planner_node(state: AgentGraphState) -> Dict[str, Any]:
    """Run the Planner agent."""
    logger.info("[PLANNER] 🎯 Starting planner node...")
    
    # Extract project path and set context for tools
    artifacts = state.get("artifacts", {})
    project_path = artifacts.get("project_path")  # None if not set - safety check will catch
    set_project_root(project_path)
    logger.info(f"[PLANNER] 📁 Project root set to: {project_path}")

    # PRE-CHECK: Determine project state BEFORE calling LLM (saves tokens!)
    project_state = "empty"
    if project_path:
        from pathlib import Path
        package_json = Path(project_path) / "package.json"
        if package_json.exists():
            project_state = "scaffolded"
            logger.info("[PLANNER] ✅ Project already scaffolded (package.json exists)")
        else:
            logger.info("[PLANNER] 📦 Project needs scaffolding (no package.json)")
    
    planner = AgentFactory.create_planner()
    
    # Get the user message
    messages = state.get("messages", [])
    logger.info(f"[PLANNER] Input messages count: {len(messages)}")
    
    # INJECT PROJECT STATE into first message to avoid LLM checking
    if messages:
        original_content = messages[0].content if hasattr(messages[0], 'content') else str(messages[0])
        if project_state == "scaffolded":
            context_msg = HumanMessage(content=f"""
PROJECT STATE: Already scaffolded (package.json exists). Skip scaffolding.

USER REQUEST: {original_content}
""")
        else:
            context_msg = HumanMessage(content=f"""
PROJECT STATE: Empty project. Scaffold with Vite/React first.

USER REQUEST: {original_content}
""")
        messages = [context_msg]
    
    result = await planner.ainvoke({"messages": messages})
    
    # Extract artifacts from tool calls
    new_messages = result.get("messages", [])
    logger.info(f"[PLANNER] Output messages count: {len(new_messages)}")
    
    # Log tool calls if any
    for msg in new_messages:
        if hasattr(msg, 'tool_calls') and msg.tool_calls:
            logger.info(f"[PLANNER] 🔧 Tool calls: {[tc.get('name', 'unknown') for tc in msg.tool_calls]}")
        if hasattr(msg, 'content') and msg.content:
            content_preview = str(msg.content)[:200]
            logger.info(f"[PLANNER] 📝 Content preview: {content_preview}...")
    
    return {
        "messages": new_messages,
        "phase": "coding",
        "artifacts": state.get("artifacts", {})
    }


async def coder_node(state: AgentGraphState) -> Dict[str, Any]:
    """Run the Coder agent."""
    logger.info("[CODER] 💻 Starting coder node...")
    
    coder = AgentFactory.create_coder()
    
    messages = state.get("messages", [])
    artifacts = state.get("artifacts", {})
    project_path = artifacts.get("project_path")  # None if not set - safety check will catch
    
    # SECURITY: Set project root in tool context BEFORE running coder
    # The LLM never sees this path - it's injected directly into the tool
    set_project_root(project_path)
    
    logger.info(f"[CODER] Input messages count: {len(messages)}")
    
    # CONTEXT SANITIZATION:
    # Filter out Planner's JSON output to prevent Coder from just continuing text generation.
    # We only keep the ORIGINAL user request (first message) and then append the execution directive.
    user_request = messages[0] if messages else HumanMessage(content="Start coding.")
    
    # If the first message is not HumanMessage (rare), find the proper one or use default
    if not isinstance(user_request, HumanMessage) and len(messages) > 0:
        for m in messages:
            if isinstance(m, HumanMessage):
                user_request = m
                break
    
    logger.info(f"[CODER] Using User Request: {str(user_request.content)[:50]}...")

    # IMPORTANT: Add a context message to guide the coder to execute
    # NOTE: We do NOT send the actual project path to the LLM for security reasons
    # The path is handled at the tool level, not by the LLM
    execution_prompt = HumanMessage(content=f"""<task>Implement: "{user_request.content}"</task>

<steps>
1. read_file_from_disk(".ships/implementation_plan.md")
2. For each file in plan: write_file_to_disk(path, complete_code)
3. Stop and summarize
</steps>

<output_format>
"Created:
- [files created]
Implementation complete."
</output_format>""")
    
    # Pass ONLY the user request and the execution prompt
    messages_with_context = [execution_prompt]  # The prompt includes the user request now
    logger.info(f"[CODER] Added execution prompt. Total messages: {len(messages_with_context)}")
    
    result = await coder.ainvoke({"messages": messages_with_context})
    
    new_messages = result.get("messages", [])
    logger.info(f"[CODER] Output messages count: {len(new_messages)}")
    
    # Log ONLY the NEW messages (not inherited ones)
    # The new messages are those beyond what we passed in
    new_count = len(new_messages) - len(messages_with_context)
    logger.info(f"[CODER] 🆕 New messages generated by coder: {new_count}")
    
    for msg in new_messages[-max(new_count, 3):]:  # Log last few messages
        if hasattr(msg, 'tool_calls') and msg.tool_calls:
            tool_names = [tc.get('name', 'unknown') for tc in msg.tool_calls]
            logger.info(f"[CODER] 🔧 NEW Tool calls: {tool_names}")
            if 'write_file_to_disk' in tool_names:
                logger.info("[CODER] ✅ Coder is writing files!")
                # Log the actual tool call args to see if project_root is being used
                for tc in msg.tool_calls:
                    if tc.get('name') == 'write_file_to_disk':
                        args = tc.get('args', {})
                        logger.info(f"[CODER] 📝 File: {args.get('file_path')} → {args.get('project_root', '.')}")
        if hasattr(msg, 'content') and msg.content:
            content_preview = str(msg.content)[:200]
            logger.info(f"[CODER] 📝 NEW Content: {content_preview}...")
    
    return {
        "messages": new_messages,
        "phase": "validating"
    }


async def validator_node(state: AgentGraphState) -> Dict[str, Any]:
    """Run the Validator agent."""
    logger.info("[VALIDATOR] 🔍 Starting validator node...")
    
    # Set project context for any file operations
    artifacts = state.get("artifacts", {})
    project_path = artifacts.get("project_path")
    set_project_root(project_path)
    
    validator = AgentFactory.create_validator()
    
    messages = state.get("messages", [])
    
    result = await validator.ainvoke({"messages": messages})
    
    # Check if validation passed (look for pass/fail in response)
    response = result.get("messages", [])
    validation_passed = any(
        "pass" in str(m.content).lower() and "fail" not in str(m.content).lower()
        for m in response if hasattr(m, 'content')
    )
    
    return {
        "messages": response,
        "validation_passed": validation_passed,
        "phase": "complete" if validation_passed else "fixing"
    }


async def fixer_node(state: AgentGraphState) -> Dict[str, Any]:
    """Run the Fixer agent."""
    logger.info("[FIXER] 🔧 Starting fixer node...")
    
    # Set project context for file operations
    artifacts = state.get("artifacts", {})
    project_path = artifacts.get("project_path")
    set_project_root(project_path)
    
    fixer = AgentFactory.create_fixer()
    
    fix_attempts = state.get("fix_attempts", 0) + 1
    max_attempts = state.get("max_fix_attempts", 3)
    
    if fix_attempts > max_attempts:
        return {
            "phase": "error",
            "result": {"error": "Max fix attempts exceeded"}
        }
    
    messages = state.get("messages", [])
    
    result = await fixer.ainvoke({"messages": messages})
    
    # Check if fixer wants to replan
    response = result.get("messages", [])
    needs_replan = any(
        "replan" in str(m.content).lower()
        for m in response if hasattr(m, 'content')
    )
    
    return {
        "messages": response,
        "fix_attempts": fix_attempts,
        "phase": "planning" if needs_replan else "validating"
    }


# ============================================================================
# ROUTING FUNCTIONS
# ============================================================================

def route_after_validation(state: AgentGraphState) -> Literal["fixer", "complete"]:
    """Route after validation based on pass/fail."""
    if state.get("validation_passed", False):
        return "complete"
    return "fixer"


def route_after_fix(state: AgentGraphState) -> Literal["planner", "validator", "error"]:
    """Route after fix based on result."""
    fix_attempts = state.get("fix_attempts", 0)
    max_attempts = state.get("max_fix_attempts", 3)
    
    if fix_attempts >= max_attempts:
        return "error"
    
    # Check if replan needed (would be set by fixer)
    phase = state.get("phase", "validating")
    if phase == "planning":
        return "planner"
    
    return "validator"


# ============================================================================
# COMPLETION NODE - Auto-launch preview
# ============================================================================

async def complete_node(state: AgentGraphState) -> Dict[str, Any]:
    """
    Run when pipeline completes successfully.
    Starts the dev server via preview_manager so ships-preview can display it.
    """
    logger.info("[COMPLETE] 🎉 Pipeline completed successfully!")
    
    artifacts = state.get("artifacts", {})
    project_path = artifacts.get("project_path")
    
    if not project_path:
        logger.warning("[COMPLETE] No project path set, cannot launch preview")
        return {
            "phase": "complete",
            "result": {"success": True, "preview_url": None}
        }
    
    from pathlib import Path
    from app.services.preview_manager import preview_manager
    
    # Detect project type
    package_json = Path(project_path) / "package.json"
    index_html = Path(project_path) / "index.html"
    
    preview_url = None
    
    if package_json.exists():
        # React/Vite project - start dev server via preview_manager
        # This sets current_url which ships-preview polls via /preview/status
        logger.info("[COMPLETE] 🚀 Starting dev server via preview_manager...")
        result = preview_manager.start_dev_server(project_path)
        
        if result.get("status") == "starting":
            # Wait briefly for URL to be detected
            import asyncio
            for _ in range(10):  # Wait up to 5 seconds
                await asyncio.sleep(0.5)
                if preview_manager.current_url:
                    preview_url = preview_manager.current_url
                    break
            
            if not preview_url:
                preview_url = "http://localhost:5173"  # Default Vite port
                
            logger.info(f"[COMPLETE] 🌐 Dev server started at: {preview_url}")
    
    elif index_html.exists():
        # Static HTML project
        preview_url = f"file://{index_html}"
        logger.info(f"[COMPLETE] 📄 Static HTML at: {preview_url}")
    
    return {
        "phase": "complete",
        "result": {
            "success": True,
            "preview_url": preview_url,
            "project_path": project_path
        }
    }


# ============================================================================
# GRAPH BUILDER
# ============================================================================

def create_agent_graph(checkpointer: Optional[MemorySaver] = None) -> StateGraph:
    """
    Create the multi-agent workflow graph.
    
    Flow:
    START → planner → coder → validator → [pass → END, fail → fixer → validator...]
    
    Args:
        checkpointer: Optional memory saver for state persistence
        
    Returns:
        Compiled StateGraph
    """
    # Create the graph
    graph = StateGraph(AgentGraphState)
    
    # Add nodes
    graph.add_node("planner", planner_node)
    graph.add_node("coder", coder_node)
    graph.add_node("validator", validator_node)
    graph.add_node("fixer", fixer_node)
    graph.add_node("complete", complete_node)  # Auto-launch preview
    
    # Add edges
    graph.add_edge(START, "planner")
    graph.add_edge("planner", "coder")
    graph.add_edge("coder", "validator")
    
    # Conditional routing after validation
    graph.add_conditional_edges(
        "validator",
        route_after_validation,
        {
            "fixer": "fixer",
            "complete": "complete"  # Route to complete_node, not END
        }
    )
    
    # Complete node goes to END after launching preview
    graph.add_edge("complete", END)
    
    # Conditional routing after fix
    graph.add_conditional_edges(
        "fixer",
        route_after_fix,
        {
            "planner": "planner",
            "validator": "validator",
            "error": END
        }
    )
    
    # Compile with optional checkpointing
    return graph.compile(checkpointer=checkpointer)


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

async def run_full_pipeline(
    user_request: str,
    thread_id: str = "default"
) -> Dict[str, Any]:
    """
    Run the full agent pipeline on a user request.
    
    Args:
        user_request: The user's request
        thread_id: Thread ID for state persistence
        
    Returns:
        Final state with artifacts and result
    """
    checkpointer = MemorySaver()
    graph = create_agent_graph(checkpointer)
    
    initial_state = {
        "messages": [HumanMessage(content=user_request)],
        "phase": "planning",
        "artifacts": {},
        "current_task_index": 0,
        "validation_passed": False,
        "fix_attempts": 0,
        "max_fix_attempts": 3,
        "result": None
    }
    
    config = {"configurable": {"thread_id": thread_id}}
    
    result = await graph.ainvoke(initial_state, config=config)
    
    return result



async def stream_pipeline(
    user_request: str,
    thread_id: str = "default",
    project_path: Optional[str] = None
):
    """
    Stream the full agent pipeline with token-by-token streaming.
    
    Uses stream_mode="messages" for real-time LLM token streaming.
    
    Args:
        user_request: The user's request
        thread_id: Thread ID for state persistence
        project_path: Optional path to user's project directory
        
    Yields:
        Message chunks as the LLM generates tokens
    """
    import logging
    logger = logging.getLogger("ships.agent")
    
    logger.info("=" * 60)
    logger.info(f"[PIPELINE] 📨 Received user_request: '{user_request}'")
    logger.info(f"[PIPELINE] Request length: {len(user_request)} chars")
    logger.info(f"[PIPELINE] Project path: {project_path or 'Not set (using backend dir)'}")
    logger.info("=" * 60)
    
    checkpointer = MemorySaver()
    graph = create_agent_graph(checkpointer)
    
    # Create the initial message
    human_msg = HumanMessage(content=user_request)
    logger.info(f"[PIPELINE] 📝 Created HumanMessage: {human_msg}")
    logger.info(f"[PIPELINE] HumanMessage.content: '{human_msg.content}'")
    
    initial_state = {
        "messages": [human_msg],
        "phase": "planning",
        "artifacts": {
            "project_path": project_path  # None if not set - agents will check and refuse
        },
        "current_task_index": 0,
        "validation_passed": False,
        "fix_attempts": 0,
        "max_fix_attempts": 3,
        "result": None,
        "tool_results": {}  # Store tool outputs here, not in messages
    }
    
    logger.info(f"[PIPELINE] 🎬 Starting graph with initial_state keys: {list(initial_state.keys())}")
    logger.info(f"[PIPELINE] Initial messages count: {len(initial_state['messages'])}")
    
    config = {
        "configurable": {"thread_id": thread_id},
        # LangSmith tracing config - provides readable run names in dashboard
        "run_name": f"ShipS* Pipeline: {user_request[:50]}...",
        "tags": ["ships", "multi-agent", "pipeline"],
        "metadata": {
            "project_path": project_path,
            "request_length": len(user_request),
        },
        "recursion_limit": 100,  # Agent needs iterations for multi-step tasks
    }
    
    # Use stream_mode="messages" for token-by-token streaming
    # This yields (message_chunk, metadata) tuples as the LLM generates
    async for event in graph.astream(initial_state, config=config, stream_mode="messages", subgraphs=True):
        logger.debug(f"[AGENT] Stream event type: {type(event)}")
        yield event

