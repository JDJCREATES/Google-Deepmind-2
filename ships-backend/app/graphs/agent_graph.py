"""
ShipS* Agent Graph Architecture

ROLE DEFINITION:
This file defines the ARCHITECTURE and ROUTING of the multi-agent system.
It is the "Skeleton" that holds the agents together.

The "BRAINS" (Decision Logic, Models, Components) reside in the sub_agents:
- Planner:      app/agents/sub_agents/planner/planner.py
- Coder:        app/agents/sub_agents/coder/coder.py
- Validator:    app/agents/sub_agents/validator/validator.py
- Fixer:        app/agents/sub_agents/fixer/fixer.py
- Orchestrator: app/agents/orchestrator/orchestrator.py (Master decision maker)

This file should ONLY contain:
1. Graph Node Definitions (calling the agents)
2. State Schema (AgentGraphState)
3. Edge/Routing Logic (wiring)
"""

from typing import TypedDict, Annotated, Literal, Optional, List, Dict, Any
from operator import add
import os
from pathlib import Path

from langgraph.graph import StateGraph, END, START
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

# Import the REAL agents from sub_agents (the original mature system)
from app.agents.sub_agents import (
    Planner, Coder, Validator, Fixer,
    ValidationStatus, RecommendedAction,
)
from app.agents.agent_factory import AgentFactory  # For creating orchestrator and other agents
# from app.agents.orchestrator import MasterOrchestrator  # The Brain (Unused, using agent factory)
from app.agents.tools.coder import set_project_root  # Secure project path context
from app.agents.sub_agents.planner.formatter import (
    format_implementation_plan, 
    format_task_list,
    format_folder_map,
    format_api_contracts,
    format_dependency_plan,
)
from app.core.cache import cache_manager # Explicit Caching



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
    
    # Explicit Cache Name (Gemini)
    cache_name: Optional[str]
    
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
    # MODERN STATE FIELDS (2025 Architecture)
    # ============================================================================
    # These replace "chat history" as the primary source of truth
    
    plan: Dict[str, Any]          # The parsed plan (goal, steps, files)
    completed_files: List[str]    # List of files successfully written
    active_file: Optional[str]    # File currently being edited
    project_structure: List[str]  # Cached file tree summary
    error_log: List[str]          # Recent errors to avoid repeating


# ============================================================================
# NODE FUNCTIONS
# ============================================================================

import logging
logger = logging.getLogger("ships.agent")




async def planner_node(state: AgentGraphState) -> Dict[str, Any]:
    """
    Run the Planner agent.
    
    Uses the mature sub_agents Planner class which:
    - Produces 7 discrete artifacts (PlanManifest, TaskList, FolderMap, etc.)
    - Uses modular components (Scoper, FolderArchitect, ContractAuthor, etc.)
    - Supports streaming
    - Has deterministic heuristics
    """
    logger.info("[PLANNER] 🎯 Starting planner node...")
    
    # Extract project path and set context for tools
    artifacts = state.get("artifacts", {})
    project_path = artifacts.get("project_path")
    set_project_root(project_path)
    logger.info(f"[PLANNER] 📁 Project root set to: {project_path}")

    # Get the user message as intent
    messages = state.get("messages", [])
    user_request = ""
    for m in messages:
        if isinstance(m, HumanMessage):
            user_request = m.content if hasattr(m, 'content') else str(m)
            break
    
    logger.info(f"[PLANNER] 📝 User request: {user_request[:100]}...")
    
    # Create the mature Planner instance
    # Use existing cache if available (from previous turn)
    cache_name = state.get("cache_name")
    planner = Planner(cached_content=cache_name)
    
    # Build intent dict from user request
    intent = {
        "raw_request": user_request,
        "project_path": project_path,
    }
    
    # Check for re-planning context (errors from previous attempts)
    error_log = state.get("error_log", [])
    if error_log:
        intent["previous_errors"] = error_log[-3:]  # Last 3 errors
        logger.info(f"[PLANNER] ⚠️ Re-planning with {len(error_log)} previous errors")
    
    # Invoke the Planner
    try:
        result = await planner.invoke(state)
        
        # Merge planner artifacts with existing artifacts
        merged_artifacts = {**artifacts}
        if "artifacts" in result:
            merged_artifacts.update(result["artifacts"])

        # SAVE ARTIFACTS TO DISK (For Frontend Persistence)
        if project_path:
            try:
                dot_ships = os.path.join(project_path, ".ships")
                os.makedirs(dot_ships, exist_ok=True)
                
                # Save implementation_plan.md
                plan_md = format_implementation_plan(merged_artifacts)
                with open(os.path.join(dot_ships, "implementation_plan.md"), "w", encoding="utf-8") as f:
                    f.write(plan_md)
                    
                # Save task.md
                task_list = merged_artifacts.get("task_list")
                if task_list:
                    task_md = format_task_list(task_list)
                    with open(os.path.join(dot_ships, "task.md"), "w", encoding="utf-8") as f:
                        f.write(task_md)
                        
                # Save folder_map.md
                folder_map = merged_artifacts.get("folder_map")
                if folder_map:
                    fm_md = format_folder_map(folder_map)
                    with open(os.path.join(dot_ships, "folder_map.md"), "w", encoding="utf-8") as f:
                        f.write(fm_md)
                        
                # Save api_contracts.md
                api_contracts = merged_artifacts.get("api_contracts")
                if api_contracts:
                    ac_md = format_api_contracts(api_contracts)
                    with open(os.path.join(dot_ships, "api_contracts.md"), "w", encoding="utf-8") as f:
                        f.write(ac_md)
                        
                # Save dependencies.md
                deps = merged_artifacts.get("dependency_plan")
                if deps:
                    dp_md = format_dependency_plan(deps)
                    with open(os.path.join(dot_ships, "dependencies.md"), "w", encoding="utf-8") as f:
                        f.write(dp_md)
                
                logger.info(f"[PLANNER] 💾 Saved artifacts to {dot_ships}")
                
            except Exception as io_e:
                logger.error(f"[PLANNER] ❌ Failed to save artifacts: {io_e}")

            # CREATE/UPDATE GEMINI EXPLICIT CACHE
            # We use the formatted markdown content for best context
            if cache_manager.enabled:
                cache_artifacts = {}
                if "folder_map" in merged_artifacts and folder_map:
                    cache_artifacts["folder_map"] = format_folder_map(folder_map)
                if "api_contracts" in merged_artifacts and api_contracts:
                    cache_artifacts["api_contracts"] = format_api_contracts(api_contracts)
                if "dependency_plan" in merged_artifacts and deps:
                    cache_artifacts["dependencies"] = format_dependency_plan(deps)
                
                # Create cache if we have meaningful context
                if cache_artifacts:
                    new_cache_name = cache_manager.create_project_context_cache(
                        project_id=os.path.basename(project_path) if project_path else "default",
                        artifacts=cache_artifacts
                    )
                    if new_cache_name:
                         # Update state with new cache name
                         cache_name = new_cache_name
                         logger.info(f"[PLANNER] 🧠 Created Explicit Cache: {new_cache_name}")
        
        return {
            "phase": "plan_ready",
            "artifacts": merged_artifacts,
            "cache_name": cache_name, # Propagate cache name
            "messages": [AIMessage(content="Planning complete. Ready for coding.")]
        }
    except Exception as e:
        logger.error(f"[PLANNER] ❌ Planner failed: {e}")
        return {
            "phase": "error",
            "error_log": state.get("error_log", []) + [f"Planner error: {str(e)}"],
            "messages": [AIMessage(content=f"Planning failed: {e}")]
        }


async def coder_node(state: AgentGraphState) -> Dict[str, Any]:
    """Run the Coder agent."""
    logger.info("[CODER] 💻 Starting coder node...")
    
    # ========================================================================
    # SETUP & CONTEXT SANITIZATION
    # ========================================================================
    artifacts = state.get("artifacts", {})
    project_path = artifacts.get("project_path")
    set_project_root(project_path)  # Security context for tools

    messages = state.get("messages", [])
    # Filter out Planner's JSON output, keep only the original user request
    user_request = messages[0] if messages else HumanMessage(content="Start coding.")
    
    if not isinstance(user_request, HumanMessage) and len(messages) > 0:
        for m in messages:
            if isinstance(m, HumanMessage):
                user_request = m
                break
    
    # ========================================================================
    # DYNAMIC PROMPT CONSTRUCTION (State-Driven)
    # ========================================================================
    # Helper: Normalize paths to relative path string (no leading ./, forward slashes)
    from pathlib import Path
    
    def normalize_path(p: str, root: Optional[str]) -> str:
        if not p: return ""
        try:
            # Handle Windows backslashes
            p = str(p).replace("\\", "/")
            if root:
                root = str(root).replace("\\", "/")
                # Try to make relative
                if p.startswith(root):
                    p = p[len(root):]
            # Strip leading slashes/dots
            p = p.lstrip("./\\")
            return p
        except:
            return p

    def get_project_tree(root_str: str, max_depth: int = 5) -> str:
        """Scan project structure recursively for context."""
        tree = []
        root = Path(root_str)
        
        def _scan(dir_path: Path, prefix: str = "", level: int = 0):
            if level > max_depth: return
            try:
                # Sort dirs first, then files
                items = sorted(dir_path.iterdir(), key=lambda x: (not x.is_dir(), x.name))
            except Exception:
                return

            for item in items:
                # Skip heavy/hidden folders
                if item.name.startswith('.') or item.name in ['node_modules', 'dist', 'build', 'coverage', '__pycache__']:
                    continue
                
                if item.is_dir():
                    tree.append(f"{prefix}📂 {item.name}/")
                    _scan(item, prefix + "  ", level + 1)
                else:
                    tree.append(f"{prefix}📄 {item.name}")

        try:
            if root.exists():
                _scan(root)
        except Exception as e:
            return f"Error scanning tree: {e}"
            
        return "\n".join(tree) if tree else "Project Empty"

    # 1. Get progress (Normalize everything)
    completed_files = state.get("completed_files", [])
    safe_completed = [normalize_path(f, project_path) for f in completed_files]
    unique_completed = sorted(list(set(safe_completed))) # Deduplicate
    files_list = "\n".join([f"- {f}" for f in unique_completed]) if unique_completed else "- None"
    
    # 2. Get REAL Project Structure (The Source of Truth)
    real_file_tree = "Project path not set."
    if project_path:
        real_file_tree = get_project_tree(project_path)
    
    # 3. Read Plan Content (Optimization: Prevent repetitive tool calls)
    plan_content = "Plan not found."
    if project_path:
        plan_path = Path(project_path) / ".ships" / "implementation_plan.md"
        if plan_path.exists():
            try:
                plan_content = plan_path.read_text(encoding="utf-8")
            except Exception as e:
                plan_content = f"Error reading plan: {e}"

    # 4. Build Dynamic System Prompt
    system_prompt = f"""<role>You are the Coder. You write complete, working code files.</role>

<context>
CURRENT PROJECT PATH: {project_path}

FILES ALREADY CREATED (Session State):
{files_list}

ACTUAL FILE STRUCTURE (Disk State):
{real_file_tree}
</context>

<implementation_plan>
{plan_content}
</implementation_plan>

<task>
1. Analyze the <implementation_plan> and <context>.
2. CRITICAL: Check "ACTUAL FILE STRUCTURE" to see if file already exists (maybe in a different folder?).
   - If `src/components/Board.tsx` is needed, looking at `src/components/Board/Board.tsx` -> IT EXISTS. Skip it.
   - Do NOT create duplicate files in different locations.
3. Pick the NEXT file to implement that is NOT in "FILES ALREADY CREATED" or on disk.
4. Write it using write_file_to_disk.
5. Continue until ALL files in plan are implemented.
6. When ALL files are done, output "Implementation complete."
</task>

<constraints>
- Do NOT read the plan file with tools (it is provided above).
- Write COMPLETE code, no TODOs.
- Listen to "FILES ALREADY CREATED" - do NOT overwrite them unless asked.
- Tries to batch multiple file writes in one turn if they are small.
</constraints>

<output_format>
"Created: [file]" or "Implementation complete."
</output_format>"""

    # 5. Build state for Coder
    coder_state = {
        **state,
        "artifacts": {
            **artifacts,
            "plan_content": plan_content,
            "project_structure": real_file_tree,
            "completed_files": unique_completed,
        },
        "parameters": {
            "user_request": user_request.content if hasattr(user_request, 'content') else str(user_request),
            "project_path": project_path,
        }
    }
    
    # 6. Invoke Coder with cached context
    cache_name = state.get("cache_name")
    coder = Coder(cached_content=cache_name)
    
    logger.info(f"[CODER] 🚀 Invoking Coder (Cache: {cache_name})...")
    
    try:
        result = await coder.invoke(coder_state)
        new_messages = [AIMessage(content=f"Coder completed: {result.get('status', 'unknown')}")]
        
        # Check if coder produced file changes
        coder_artifacts = result.get("artifacts", {})
        file_change_set = coder_artifacts.get("file_change_set", {})
        changes = file_change_set.get("changes", [])
        
        for change in changes:
            path = change.get("path", "")
            if path:
                norm_path = normalize_path(path, project_path)
                if norm_path:
                    unique_completed.add(norm_path)
        
        implementation_complete = result.get("status") == "complete" or len(changes) == 0
    except Exception as e:
        logger.error(f"[CODER] ❌ Coder invoke failed: {e}, falling back to AgentFactory")
        # FALLBACK: If sub_agents Coder fails, we need to handle gracefully
        # For now, just log and mark as error
        return {
            "phase": "error",
            "error_log": state.get("error_log", []) + [f"Coder error: {str(e)}"],
            "messages": [AIMessage(content=f"Coding failed: {e}")]
        }
    
    new_messages = result.get("messages", []) if isinstance(result.get("messages"), list) else new_messages
    
    # EXTRACT STATUS from agent output
    # Priority: Structured JSON > String matching (backwards compat)
    new_completed = []
    implementation_complete = False
    agent_status = {"status": "in_progress"}  # Default
    
    import json as json_module
    import re as re_module
    
    for msg in new_messages:
        if hasattr(msg, 'content') and msg.content:
            content = str(msg.content)
            
            # Try to parse structured JSON status
            try:
                json_match = re_module.search(r'\{[\s\S]*"status"[\s\S]*\}', content)
                if json_match:
                    parsed = json_module.loads(json_match.group())
                    if parsed.get("status") == "complete":
                        implementation_complete = True
                        agent_status = parsed
                        logger.info(f"[CODER] ✅ Structured completion signal: {parsed}")
                    elif parsed.get("just_created"):
                        new_completed.append(parsed.get("just_created"))
            except (json_module.JSONDecodeError, AttributeError):
                pass
            
            # Fallback: String matching for backwards compatibility
            if not implementation_complete and "implementation complete" in content.lower():
                implementation_complete = True
                logger.info("[CODER] ✅ String completion signal detected (fallback)")
        
        # Track file creation from tool calls
        if hasattr(msg, 'tool_calls') and msg.tool_calls:
            for tc in msg.tool_calls:
                if tc.get('name') == 'write_file_to_disk':
                    path = tc['args'].get('file_path')
                    if path:
                        norm_path = normalize_path(path, project_path)
                        if norm_path:
                            new_completed.append(norm_path)
    
    # Update completed files list
    current_set = set(state.get("completed_files", []))
    current_set.update(new_completed)
    current_completed = list(current_set)
    
    # Determine next phase
    next_phase = "validating" if implementation_complete else "coding"
    if implementation_complete:
        logger.info(f"[CODER] ✅ Implementation complete. {len(current_completed)} files created.")
    
    return {
        "messages": new_messages,
        "phase": next_phase,
        "completed_files": current_completed,
        "agent_status": agent_status  # Pass structured status for frontend
    }


async def validator_node(state: AgentGraphState) -> Dict[str, Any]:
    """
    Run the Validator agent.
    
    Uses the mature sub_agents Validator class which:
    - Runs 4 validation layers (Structural, Completeness, Dependency, Scope)
    - Produces ValidationReport with pass/fail status
    - Has recommended actions (PROCEED, FIX, REPLAN, ASK_USER)
    """
    logger.info("[VALIDATOR] 🔍 Starting validator node...")
    
    # Set project context for any file operations
    artifacts = state.get("artifacts", {})
    project_path = artifacts.get("project_path")
    set_project_root(project_path)
    
    # Create the mature Validator instance
    validator = Validator()
    
    try:
        # Invoke the Validator with current state
        result = await validator.invoke(state)
        
        # Extract validation status from result
        validation_passed = result.get("passed", False)
        validation_status = result.get("status", "unknown")
        failure_layer = result.get("failure_layer", "none")
        recommended_action = result.get("recommended_action", "fix")
        violation_count = result.get("violation_count", 0)
        
        if validation_passed:
            logger.info(f"[VALIDATOR] ✅ All {violation_count} checks passed")
        else:
            logger.info(f"[VALIDATOR] ❌ Failed at layer: {failure_layer} ({violation_count} violations)")
        
        # Update error log if failed
        error_log = state.get("error_log", [])
        if not validation_passed:
            validation_report = result.get("artifacts", {}).get("validation_report", {})
            fixer_instructions = validation_report.get("fixer_instructions", f"Fix {violation_count} violations")
            error_log.append(f"Validation Failed [{failure_layer}]: {fixer_instructions[:200]}")
        
        # Merge artifacts
        merged_artifacts = {**artifacts}
        if "artifacts" in result:
            merged_artifacts.update(result["artifacts"])
        
        return {
            "validation_passed": validation_passed,
            "phase": "validating",
            "error_log": error_log,
            "artifacts": merged_artifacts,
            "agent_status": {
                "status": "pass" if validation_passed else "fail",
                "failure_layer": failure_layer,
                "recommended_action": recommended_action,
                "violation_count": violation_count
            },
            "messages": [AIMessage(content=f"Validation {'passed' if validation_passed else 'failed'}: {violation_count} violations")]
        }
    except Exception as e:
        logger.error(f"[VALIDATOR] ❌ Validator failed: {e}")
        return {
            "validation_passed": False,
            "phase": "error",
            "error_log": state.get("error_log", []) + [f"Validator error: {str(e)}"],
            "messages": [AIMessage(content=f"Validation error: {e}")]
        }


async def fixer_node(state: AgentGraphState) -> Dict[str, Any]:
    """
    Run the Fixer agent.
    
    Uses the mature sub_agents Fixer class which:
    - Has multiple fix strategies
    - Produces FixPlan with targeted patches
    - Knows when to escalate to Planner
    """
    logger.info("[FIXER] 🔧 Starting fixer node...")
    
    # Set project context for file operations
    artifacts = state.get("artifacts", {})
    project_path = artifacts.get("project_path")
    set_project_root(project_path)
    
    fix_attempts = state.get("fix_attempts", 0) + 1
    max_attempts = state.get("max_fix_attempts", 3)
    
    if fix_attempts > max_attempts:
        logger.warning(f"[FIXER] ⚠️ Max attempts ({max_attempts}) exceeded, escalating to planner")
        return {
            "phase": "planner",  # Escalate to replanning
            "fix_attempts": fix_attempts,
            "error_log": state.get("error_log", []) + ["Fixer max attempts exceeded - needs replanning"],
            "messages": [AIMessage(content="Fix attempts exceeded. Escalating to planner.")]
        }
    
    # Create the mature Fixer instance
    fixer = Fixer()
    
    try:
        # Invoke the Fixer with current state
        result = await fixer.invoke(state)
        
        # Check for escalation request
        needs_escalate = result.get("needs_replan", False)
        fix_status = result.get("status", "unknown")
        
        if needs_escalate:
            replan_request = result.get("artifacts", {}).get("replan_request", {})
            reason = replan_request.get("reason", "Fixer requested escalation")
            logger.info(f"[FIXER] ⚠️ Escalation requested: {reason}")
            return {
                "phase": "planner",
                "fix_attempts": fix_attempts,
                "error_log": state.get("error_log", []) + [f"Escalated: {reason}"],
                "artifacts": {**artifacts, **result.get("artifacts", {})},
                "messages": [AIMessage(content=f"Escalating to planner: {reason}")]
            }
        
        logger.info(f"[FIXER] ✅ Fix applied (attempt {fix_attempts}/{max_attempts})")
        
        # Merge artifacts
        merged_artifacts = {**artifacts}
        if "artifacts" in result:
            merged_artifacts.update(result["artifacts"])
        
        return {
            "fix_attempts": fix_attempts,
            "phase": "fixing",
            "artifacts": merged_artifacts,
            "agent_status": {"status": "fixed", "attempt": fix_attempts},
            "messages": [AIMessage(content=f"Fix applied (attempt {fix_attempts})")]
        }
    except Exception as e:
        logger.error(f"[FIXER] ❌ Fixer failed: {e}")
        return {
            "fix_attempts": fix_attempts,
            "phase": "error",
            "error_log": state.get("error_log", []) + [f"Fixer error: {str(e)}"],
            "messages": [AIMessage(content=f"Fix error: {e}")]
        }


async def orchestrator_node(state: AgentGraphState) -> Dict[str, Any]:
    """
    MASTER ORCHESTRATOR NODE
    Decides which agent to call next based on global state.
    """
    logger.info("[ORCHESTRATOR] 🧠 Starting orchestrator node...")
    
    # 1. Build Dynamic Context
    phase = state.get("phase", "planning")
    completed_files = state.get("completed_files", [])
    validation_passed = state.get("validation_passed", False)
    fix_attempts = state.get("fix_attempts", 0)
    error_log = state.get("error_log", [])
    
    # Check if plan exists (for context, not hard rule)
    from pathlib import Path
    artifacts = state.get("artifacts", {})
    project_path = artifacts.get("project_path")
    plan_exists = False
    if project_path:
        plan_path = Path(project_path) / ".ships" / "implementation_plan.md"
        plan_exists = plan_path.exists()
    
    # 2. Build Dynamic System Prompt
    # 2. Build Dynamic System Prompt
    system_prompt = f"""<role>You are the Master Orchestrator. You decide the next phase of development.</role>

<state>
CURRENT PHASE: {phase}
FILES COMPLETED: {len(completed_files)}
VALIDATION PASSED: {validation_passed}
FIX ATTEMPTS: {fix_attempts}
PLAN EXISTS: {plan_exists}
</state>

<rules>
1. If PHASE is "planning" (and plan missing/stale) -> call_planner
2. If PHASE is "plan_ready" -> call_coder
3. If PHASE is "coding" (and files remain) -> call_coder
4. If PHASE is "validating" -> call_validator
5. If PHASE is "fixing" -> call_fixer
6. If Validation Passed -> finish
7. If PHASE is "fixing_failed" -> call_planner (to re-scope)
8. If Fixer failed > 3 times -> call_planner (to re-scope) or finish (if stuck)
</rules>

<output_format>
Return JSON ONLY:
{{
  "observations": ["observation 1", "observation 2"],
  "reasoning": "Explain why you are choosing the next step based on state and rules.",
  "decision": "call_planner" | "call_coder" | "call_validator" | "call_fixer" | "finish",
  "confidence": 0.0 to 1.0
}}
</output_format>"""

    # 3. Call Orchestrator Agent
    orchestrator = AgentFactory.create_orchestrator(override_system_prompt=system_prompt)
    
    # Get last message content for context (why did we get here?)
    messages = state.get("messages", [])
    last_context = "No previous context."
    if messages:
        last_msg = messages[-1]
        content = last_msg.content if hasattr(last_msg, 'content') else str(last_msg)
        last_context = f"PREVIOUS AGENT OUTPUT: {str(content)[:1000]}" # Truncate for safety

    messages_with_context = [
        HumanMessage(content=f"""{last_context}
        
Analyze state and decide next step. Respond with JSON.""")
    ]
    
    # Run agent
    try:
        result = await orchestrator.ainvoke({"messages": messages_with_context})
        last_message = result["messages"][-1]
        
        # Robust content extraction
        content = last_message.content
        if isinstance(content, list):
             response = " ".join([str(c) for c in content if isinstance(c, (str, dict))])
             if isinstance(content[0], dict) and "text" in content[0]:
                 response = " ".join([c.get("text", "") for c in content])
        else:
            response = str(content)
            
        logger.info(f"[ORCHESTRATOR] 🧠 Raw Response: {response[:200]}...")
        
        # Parse JSON
        import json as json_module
        import re as re_module
        
        decision = "finish"
        json_match = re_module.search(r'\{[\s\S]*\}', response)
        
        if json_match:
            try:
                parsed = json_module.loads(json_match.group())
                raw_decision = parsed.get("decision", "finish").lower()
                logger.info(f"[ORCHESTRATOR] 🧠 Structured Decision: {parsed}")
                
                if "planner" in raw_decision: decision = "planner"
                elif "coder" in raw_decision: decision = "coder"
                elif "validator" in raw_decision: decision = "validator"
                elif "fixer" in raw_decision: decision = "fixer"
                elif "finish" in raw_decision: decision = "complete"
            except Exception as e:
                logger.error(f"[ORCHESTRATOR] ❌ JSON parse failed: {e}")
                decision = "finish" # Fail safe
        else:
            # Fallback string matching
            response = response.lower()
            if "call_planner" in response: decision = "planner"
            elif "call_coder" in response: decision = "coder"
            elif "call_validator" in response: decision = "validator"
            elif "call_fixer" in response: decision = "fixer"
            elif "finish" in response: decision = "complete"
            
    except Exception as e:
        logger.error(f"[ORCHESTRATOR] ❌ Orchestrator failed: {e}")
        decision = "finish" # Fail safe
        
    logger.info(f"[ORCHESTRATOR] 🧠 Final Routing: {decision}")
    
    return {
        "phase": decision  # This drives the routing
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
    graph.add_node("orchestrator", orchestrator_node)
    graph.add_node("planner", planner_node)
    graph.add_node("coder", coder_node)
    graph.add_node("validator", validator_node)
    graph.add_node("fixer", fixer_node)
    graph.add_node("complete", complete_node)
    
    # EDGE WIRING: Hub and Spoke
    # Everyone returns to Orchestrator
    graph.add_edge(START, "orchestrator")
    graph.add_edge("planner", "orchestrator")
    graph.add_edge("coder", "orchestrator")
    graph.add_edge("validator", "orchestrator")
    graph.add_edge("fixer", "orchestrator")
    
    # ORCHESTRATOR ROUTING
    def route_orchestrator(state: AgentGraphState):
        decision = state.get("phase")
        if decision in ["planner", "coder", "validator", "fixer", "complete"]:
            return decision
        return "complete" # Default fallback
        
    graph.add_conditional_edges(
        "orchestrator",
        route_orchestrator,
        {
            "planner": "planner",
            "coder": "coder",
            "validator": "validator",
            "fixer": "fixer",
            "complete": "complete"
        }
    )
    
    # Complete goes to END
    graph.add_edge("complete", END)
    
    # Compile
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
        "max_fix_attempts": 3,
        "result": None,
        # Modern State Init
        "plan": {},
        "completed_files": [],
        "active_file": None,
        "project_structure": [],
        "error_log": []
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
        "tool_results": {},
        # Modern State Init
        "plan": {},
        "completed_files": [],
        "active_file": None,
        "project_structure": [],
        "error_log": []
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

