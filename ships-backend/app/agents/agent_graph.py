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


# ============================================================================
# STATE DEFINITION  
# ============================================================================

class AgentGraphState(TypedDict):
    """State shared across all agents in the graph."""
    
    # Messages for conversation
    messages: Annotated[List[BaseMessage], add]
    
    # Current phase
    phase: Literal["planning", "coding", "validating", "fixing", "complete", "error"]
    
    # Artifacts produced by agents
    artifacts: Dict[str, Any]
    
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

async def planner_node(state: AgentGraphState) -> Dict[str, Any]:
    """Run the Planner agent."""
    planner = AgentFactory.create_planner()
    
    # Get the user message
    messages = state.get("messages", [])
    
    result = await planner.ainvoke({"messages": messages})
    
    # Extract artifacts from tool calls
    new_messages = result.get("messages", [])
    
    return {
        "messages": new_messages,
        "phase": "coding",
        "artifacts": state.get("artifacts", {})
    }


async def coder_node(state: AgentGraphState) -> Dict[str, Any]:
    """Run the Coder agent."""
    coder = AgentFactory.create_coder()
    
    # Add context about current task
    artifacts = state.get("artifacts", {})
    task_index = state.get("current_task_index", 0)
    
    messages = state.get("messages", [])
    
    result = await coder.ainvoke({"messages": messages})
    
    return {
        "messages": result.get("messages", []),
        "phase": "validating"
    }


async def validator_node(state: AgentGraphState) -> Dict[str, Any]:
    """Run the Validator agent."""
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
            "complete": END
        }
    )
    
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
    thread_id: str = "default"
):
    """
    Stream the full agent pipeline.
    
    Yields events as each agent processes.
    
    Args:
        user_request: The user's request
        thread_id: Thread ID for state persistence
        
    Yields:
        State updates from each node
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
    
    async for event in graph.astream(initial_state, config=config, stream_mode="updates"):
        yield event
