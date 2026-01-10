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

# Collective Intelligence - capture successful patterns and fixes
from app.services.knowledge.hooks import capture_coder_pattern, capture_fixer_success



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
    
    # Collective Intelligence: pending fix to capture after validation passes
    pending_fix_context: Optional[Dict[str, Any]]
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
    
    The Planner class now uses create_react_agent internally for:
    - PLANNER_TOOLS (run_terminal_command, create_directory, write_file_to_disk)
    - Scaffolding execution after plan generation
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
    # Find the LATEST human message (reversed iteration)
    for m in reversed(messages):
        if isinstance(m, HumanMessage):
            user_request = m.content if hasattr(m, 'content') else str(m)
            break
    
    logger.info(f"[PLANNER] 📝 User request: {user_request[:100]}...")
    
    
    # 3. Create agent instances
    planner = Planner()
    
    # 4. Prepare Planner state
    # user_request is already defined above
    structured_intent = state["artifacts"].get("structured_intent", {}) # This will be overwritten later if not present
    # project_path is already defined above
    
    # REFRESH FILE TREE ARTIFACT (System-level update)
    # This ensures the Planner always has the latest file structure without needing to call a tool
    file_tree_data = {}
    try:
        if project_path:
            from app.agents.tools.coder.file_tree import scan_project_tree
            
            # Get settings (injected in stream_pipeline)
            settings = state.get("artifacts", {}).get("settings", {})
            # safely extract depth, handle if settings is None or missing keys
            scan_depth = 3
            if settings and isinstance(settings, dict):
                scan_depth = settings.get("artifacts", {}).get("fileTreeDepth", 3)
            
            # Scan and save artifact
            file_tree_data = scan_project_tree.invoke({
                "subpath": ".",
                "max_depth": int(scan_depth),
                "extract_symbols": True,
                "save_artifact": True
            })
            
            if file_tree_data.get("success"):
                logger.info(f"[PLANNER_NODE] 🌳 Refreshed file tree artifact ({file_tree_data['stats']['files']} files)")
            else:
                logger.warning(f"[PLANNER_NODE] ⚠️ File tree scan returned error: {file_tree_data.get('error')}")
                file_tree_data = {}
                
    except Exception as ft_e:
        logger.warning(f"[PLANNER_NODE] ⚠️ Failed to refresh file tree: {ft_e}")
    
    planner_state = {
        **state,
        "environment": {
            "project_path": project_path,
            "file_tree": file_tree_data, # Inject directly into environment
        },
        "artifacts": {
            **artifacts,
            "structured_intent": structured_intent,
            "project_path": project_path,
        },
    }
    
    # Build structured intent for the planner (keeping original logic for structured_intent)
    structured_intent = {
        "description": user_request,
        "id": f"intent_{os.path.basename(project_path) if project_path else 'default'}",
    }
    
    try:
        # Invoke the Planner (now uses create_react_agent for scaffolding)
        result = await planner.invoke(planner_state)
        
        logger.info(f"[PLANNER] ✅ Planner completed")
        
        # ==================================================================
        # PLAN VALIDATION (Dynamic, no hardcoded rules)
        # ==================================================================
        from app.agents.sub_agents.planner.validator import PlanValidator
        
        # Check if plan needs validation (skip if retrying > 2 times)
        plan_iteration = artifacts.get("plan_iteration", 0)
        plan_data = result.get("artifacts", {}).get("plan", {})
        
        if plan_iteration < 2 and plan_data:
            logger.info(f"[PLANNER] 🔍 Validating plan (iteration {plan_iteration + 1}/2)")
            
            validator = PlanValidator()
            validation = validator.validate(
                plan_data=plan_data,
                user_request=user_request
            )
            
            if validation.status == "needs_revision":
                logger.warning(f"[PLANNER] ⚠️ Plan needs revision (score: {validation.score})")
                logger.warning(f"[PLANNER] Missing: {validation.missing_items}")
                
                # Return with retry flag + previous plan for editing
                return {
                    "phase": "planning",  # Stay in planning phase
                    "artifacts": {
                        **artifacts,
                        "plan_iteration": plan_iteration + 1,
                        "validation_feedback": validation.suggestions,
                        "previous_plan": plan_data,  # Pass for incremental editing
                        "retry_reason": "plan_incomplete"
                    },
                    "messages": [AIMessage(content=f"Plan needs revision. Issues: {', '.join(validation.missing_items[:3])}")]
                }
            else:
                logger.info(f"[PLANNER] ✅ Plan validated (score: {validation.score})")
        
        # ==================================================================
        # END VALIDATION
        # ==================================================================
        
        # Merge planner artifacts with existing artifacts
        merged_artifacts = {**artifacts}
        if "artifacts" in result:
            merged_artifacts.update(result["artifacts"])
        
        # Clear retry state on success
        merged_artifacts.pop("plan_iteration", None)
        merged_artifacts.pop("validation_feedback", None)
        merged_artifacts.pop("previous_plan", None)  # Don't carry over to next request
        merged_artifacts.pop("retry_reason", None)
        
        # SAVE ARTIFACTS TO DISK (For Frontend Persistence)
        if project_path:
            try:
                dot_ships = os.path.join(project_path, ".ships")
                os.makedirs(dot_ships, exist_ok=True)
                
                # Save planner status
                import json as json_mod
                with open(os.path.join(dot_ships, "planner_status.json"), "w", encoding="utf-8") as f:
                    json_mod.dump({
                        "status": "complete",
                        "scaffolding_complete": merged_artifacts.get("scaffolding_complete", False),
                        "project_path": project_path,
                    }, f, indent=2)
                
                logger.info(f"[PLANNER] 💾 Saved planner status to {dot_ships}")
                
            except Exception as io_e:
                logger.error(f"[PLANNER] ❌ Failed to save artifacts: {io_e}")
        
        return {
            "phase": "plan_ready",
            "artifacts": merged_artifacts,
            "messages": [AIMessage(content="Planning and scaffolding complete. Ready for coding.")]
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
    # Filter out Planner's JSON output, keep only the LATEST user request
    user_request = HumanMessage(content="Start coding.")
    
    # scan for latest human message
    if messages:
        for m in reversed(messages):
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

    # 5. Build state for Coder.invoke()
    coder_state = {
        **state,
        "artifacts": {
            **artifacts,
            "plan_content": plan_content,
            "project_structure": real_file_tree,
            "project_path": project_path,
        },
        "parameters": {
            "user_request": user_request.content if hasattr(user_request, 'content') else str(user_request),
            "project_path": project_path,
        },
        "completed_files": unique_completed,
    }
    
    # 6. Invoke the Coder (now uses create_react_agent internally)
    coder = Coder()
    
    try:
        result = await coder.invoke(coder_state)
        
        logger.info(f"[CODER] ✅ Coder completed")
        
        # Extract completion status
        implementation_complete = result.get("implementation_complete", False)
        files_written = result.get("completed_files", [])
        
        # Update completed files list
        current_set = set(state.get("completed_files", []))
        current_set.update(files_written)
        current_completed = list(current_set)
        
        # ================================================================
        # INTELLIGENT VALIDATION: Compare expected files from plan
        # ================================================================
        expected_files = []
        
        # Try to extract expected files from plan content
        plan_content = artifacts.get("plan_content", "")
        if plan_content:
            import re
            # Look for "Files to Create" sections or file paths in plan
            # Pattern: src/something.tsx or similar paths
            file_patterns = re.findall(r'(?:src|public|app)/[\w/.-]+\.\w+', plan_content)
            expected_files = list(set(file_patterns))
        
        # Also check folder_map if available
        ships_dir = Path(project_path) / ".ships" if project_path else None
        if ships_dir and ships_dir.exists():
            folder_map_path = ships_dir / "folder_map.json"
            if folder_map_path.exists():
                try:
                    import json
                    folder_data = json.loads(folder_map_path.read_text(encoding="utf-8"))
                    entries = folder_data.get("entries", [])
                    map_files = [e.get("path") for e in entries if not e.get("is_directory", False) and e.get("path")]
                    expected_files.extend(map_files)
                except Exception:
                    pass
        
        expected_files = list(set(expected_files))  # Dedupe
        
        # Log progress for debugging
        logger.info(f"[CODER] 📊 Progress: {len(current_completed)} files created")
        logger.info(f"[CODER] 📋 Expected from plan: {len(expected_files)} files")
        
        # Check what's missing (if we have expected files)
        if expected_files:
            # Normalize paths for comparison
            normalized_completed = {str(f).replace("\\", "/").lower() for f in current_completed}
            normalized_expected = {str(f).replace("\\", "/").lower() for f in expected_files}
            
            missing = normalized_expected - normalized_completed
            if missing:
                logger.info(f"[CODER] 📝 Missing files: {len(missing)}")
                for m in list(missing)[:5]:
                    logger.info(f"[CODER]    - {m}")
                
                # If LLM claims complete but files are missing, force continuation
                if implementation_complete and len(missing) > 0:
                    logger.warning(
                        f"[CODER] ⚠️ LLM claimed complete but {len(missing)} expected files missing. "
                        f"Continuing..."
                    )
                    implementation_complete = False
            else:
                logger.info(f"[CODER] ✅ All expected files present!")
        
        # Determine next phase
        next_phase = "validating" if implementation_complete else "coding"
        if implementation_complete:
            logger.info(f"[CODER] ✅ Implementation complete. {len(current_completed)} files created.")
        else:
            logger.info(f"[CODER] 🔄 More work needed, continuing in coding phase")
            
        # REFRESH FILE TREE ARTIFACT (System-level update after Coder)
        try:
             # Get settings (injected in stream_pipeline)
             settings = state.get("artifacts", {}).get("settings", {})
             scan_depth = 3
             if settings and isinstance(settings, dict):
                 scan_depth = settings.get("artifacts", {}).get("fileTreeDepth", 3)

             from app.agents.tools.coder.file_tree import scan_project_tree
             scan_project_tree.invoke({
                 "subpath": ".",
                 "max_depth": int(scan_depth),
                 "extract_symbols": True,
                 "save_artifact": True
             })
             logger.info(f"[CODER_NODE] 🌳 Refreshed file tree artifact after coding")
        except Exception as ft_e:
             logger.warning(f"[CODER_NODE] ⚠️ Failed to refresh file tree: {ft_e}")
        
        return {
            "messages": [AIMessage(content=f"Coder completed: {result.get('status', 'unknown')}")],
            "phase": next_phase,
            "completed_files": current_completed,
            "agent_status": {"status": result.get("status", "in_progress")}
        }
        
    except Exception as e:
        logger.error(f"[CODER] ❌ Coder invoke failed: {e}")
        return {
            "phase": "error",
            "error_log": state.get("error_log", []) + [f"Coder error: {str(e)}"],
            "messages": [AIMessage(content=f"Coding failed: {e}")]
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
            
            # ===== COLLECTIVE INTELLIGENCE: Capture fix if this validated a fix =====
            pending_fix = state.get("pending_fix_context")
            if pending_fix:
                try:
                    session_id = state.get("thread_id") or state.get("config", {}).get("configurable", {}).get("thread_id")
                    user_id = state.get("user_id")
                    
                    captured = await capture_fixer_success(
                        state=state,
                        error_message=pending_fix.get("error_message", ""),
                        solution_code=pending_fix.get("solution_code", ""),
                        solution_description=pending_fix.get("description", ""),
                        diff=pending_fix.get("diff", ""),
                        before_errors=pending_fix.get("before_errors", []),
                        session_id=session_id,
                        user_id=user_id,
                    )
                    if captured:
                        logger.info("[VALIDATOR] 🔧 Fix captured for Collective Intelligence")
                except Exception as e:
                    logger.debug(f"[VALIDATOR] Fix capture skipped: {e}")
            # =================================================================
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
            "pending_fix_context": None,  # Clear after capture attempt
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


async def chat_node(state: AgentGraphState) -> Dict[str, Any]:
    """
    Run the Chatter agent (Question Answerer).
    """
    logger.info("[CHAT] 💬 Starting chat node...")
    
    # Import locally to avoid circular deps if any, or just for cleanliness
    from app.agents.mini_agents.chatter import Chatter
    
    try:
        chatter = Chatter()
        return await chatter.invoke(state)
        
    except Exception as e:
        logger.error(f"[CHAT] ❌ Chat failed: {e}")
        return {
            "phase": "error",
            "messages": [AIMessage(content=f"I couldn't answer that: {e}")]
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
    
    # Invoke the Fixer (now uses create_react_agent internally)
    fixer = Fixer()
    
    fixer_state = {
        **state,
        "artifacts": {**artifacts, "project_path": project_path},
        "parameters": {"attempt_number": fix_attempts},
    }
    
    try:
        result = await fixer.invoke(fixer_state)
        
        logger.info(f"[FIXER] ✅ Fixer completed")
        
        # Check for escalation
        if result.get("requires_replan") or result.get("needs_replan"):
            reason = result.get("artifacts", {}).get("replan_request", {}).get("reason", "Fixer requested escalation")
            logger.info(f"[FIXER] ⚠️ Escalation requested: {reason}")
            return {
                "phase": "planner",
                "fix_attempts": fix_attempts,
                "error_log": state.get("error_log", []) + [f"Escalated: {reason}"],
                "messages": [AIMessage(content=f"Escalating to planner: {reason}")]
            }
        
        # ===== COLLECTIVE INTELLIGENCE: Store fix context for capture =====
        # Extract error and fix info for capture after validation passes
        fix_artifacts = result.get("artifacts", {})
        fix_patch = fix_artifacts.get("fix_patch", {})
        validation_report = artifacts.get("validation_report", {})
        
        pending_fix_context = {
            "error_message": validation_report.get("fixer_instructions", "")[:500] or 
                            str(state.get("error_log", [])[-1] if state.get("error_log") else ""),
            "solution_code": fix_patch.get("summary", ""),
            "description": result.get("summary", f"Fix attempt {fix_attempts}"),
            "diff": fix_patch.get("unified_diff", ""),
            "before_errors": [str(v.get("message", "")) for v in validation_report.get("violations", [])][:10],
        }
        # ==================================================================
        
        return {
            "fix_attempts": fix_attempts,
            "phase": "validating",  # Go back to validation after fix
            "pending_fix_context": pending_fix_context,
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
    project_scaffolded = False  # NEW: Check for actual project files
    
    if project_path:
        plan_path = Path(project_path) / ".ships" / "implementation_plan.md"
        plan_exists = plan_path.exists()
        
        # Check if scaffolding was explicitly marked complete in artifacts
        # OR if package.json exists (which implies scaffolding is done)
        scaffolding_done = artifacts.get("scaffolding_complete", False)
        if not scaffolding_done and (Path(project_path) / "package.json").exists():
            scaffolding_done = True
            
    fix_attempts = state.get("fix_attempts", 0)
    
    # ================================================================
    # INTENT CLASSIFICATION: Use IntentClassifier mini-agent
    # ================================================================
    from app.agents.mini_agents.intent_classifier import IntentClassifier
    
    is_new_intent = False
    messages = state.get("messages", [])
    user_request = ""
    
    # Get FIRST user message (the current request)
    for msg in messages:
        if hasattr(msg, 'content') and msg.__class__.__name__ in ['HumanMessage', 'HumanMessageChunk']:
            user_request = str(msg.content).strip()
            break
    
    # Classify current intent
    current_intent = None
    if user_request:
        try:
            classifier = IntentClassifier()
            # Load folder_map for context if available
            folder_map_data = None
            if project_path:
                folder_map_path = Path(project_path) / ".ships" / "folder_map.json"
                if folder_map_path.exists():
                    import json
                    folder_map_data = json.loads(folder_map_path.read_text(encoding='utf-8'))
            
            current_intent = await classifier.classify(user_request, folder_map=folder_map_data)
            logger.info(f"[ORCHESTRATOR] 🎯 Intent classified: {current_intent.task_type}/{current_intent.action} (conf: {current_intent.confidence:.2f})")
            
        except Exception as e:
            logger.warning(f"[ORCHESTRATOR] Intent classification failed: {e}")
    
    # Check if this is a NEW feature/modify request vs continuing previous work
    if project_path and plan_exists and current_intent:
        # New feature/modify requests should trigger re-planning
        if current_intent.task_type in ['feature', 'modify', 'refactor']:
            plan_manifest_path = Path(project_path) / ".ships" / "plan_manifest.json"
            if plan_manifest_path.exists():
                try:
                    import json
                    manifest = json.loads(plan_manifest_path.read_text(encoding='utf-8'))
                    planned_goal = manifest.get('user_goal', '') or manifest.get('intent_summary', '')
                    planned_description = manifest.get('description', '')
                    
                    # Compare intent descriptions
                    current_desc = current_intent.description.lower()
                    planned_combined = f"{planned_goal} {planned_description}".lower()
                    
                    # Check if key terms from current request are absent in old plan
                    current_keywords = set(w for w in current_desc.split() if len(w) > 3)
                    planned_keywords = set(w for w in planned_combined.split() if len(w) > 3)
                    
                    overlap = len(current_keywords & planned_keywords)
                    coverage = overlap / len(current_keywords) if current_keywords else 1.0
                    
                    # Less than 50% keyword coverage = likely new intent
                    if coverage < 0.5:
                        is_new_intent = True
                        logger.info(f"[ORCHESTRATOR] 🆕 NEW INTENT detected (keyword coverage: {coverage:.1%})")
                        logger.info(f"[ORCHESTRATOR]    Type: {current_intent.task_type}, Action: {current_intent.action}")
                        logger.info(f"[ORCHESTRATOR]    Description: {current_intent.description[:60]}...")
                        
                except Exception as e:
                    logger.warning(f"[ORCHESTRATOR] Could not compare intents: {e}")
    
    # If new intent, version old artifacts and force re-plan
    if is_new_intent and project_path:
        logger.info("[ORCHESTRATOR] 🔄 Versioning old plan artifacts...")
        ships_dir = Path(project_path) / ".ships"
        import shutil
        from datetime import datetime
        version_suffix = datetime.now().strftime("_%Y%m%d_%H%M%S")
        
        for artifact_name in ["plan_manifest", "task_list", "folder_map", "implementation_plan"]:
            for ext in [".json", ".md"]:
                artifact_file = ships_dir / f"{artifact_name}{ext}"
                if artifact_file.exists():
                    versioned = ships_dir / f"{artifact_name}{version_suffix}{ext}"
                    shutil.copy2(artifact_file, versioned)
        
        # Mark plan as needing refresh
        plan_exists = False
        logger.info("[ORCHESTRATOR] ✓ Old artifacts versioned, forcing re-plan")

    # 3. Check for CONFIRMATION intent (Approval to proceed)
    is_confirmation = False
    if current_intent and current_intent.task_type == "confirmation":
        is_confirmation = True
        logger.info("[ORCHESTRATOR] 👍 User CONFIRMATION detected")
    
    # 4. Check for QUESTION intent
    is_question = False
    if current_intent and current_intent.task_type == "question":
        is_question = True
        logger.info("[ORCHESTRATOR] ❓ User QUESTION detected")

    # 5. Check for AMBIGUOUS intent (needs clarification) - CRITICAL FIX
    # The Intent Classifier can detect ambiguity but we weren't checking it!
    if current_intent and current_intent.is_ambiguous:
        clarification_msg = "\n".join(current_intent.clarification_questions) if current_intent.clarification_questions else "I need more information to proceed. Could you clarify what you'd like me to do?"
        logger.info(f"[ORCHESTRATOR] ❓ AMBIGUOUS request detected - asking for clarification")
        logger.info(f"[ORCHESTRATOR] Questions: {current_intent.clarification_questions}")
        
        return {
            "phase": "chat",  # Route to chat to show message
            "messages": [AIMessage(content=f"🤔 **I need clarification:**\n\n{clarification_msg}")],
            "artifacts": {**artifacts, "pending_intent": current_intent.model_dump() if hasattr(current_intent, 'model_dump') else {}}
        }

    # 6. Check for NEW INTENT in EXISTING PROJECT (potential conflict)
    # If user asks for something new but we have existing code, ASK before proceeding
    if is_new_intent and project_path:
        src_path = Path(project_path) / "src"
        if src_path.exists():
            src_files = list(src_path.glob("**/*.tsx")) + list(src_path.glob("**/*.ts")) + list(src_path.glob("**/*.jsx")) + list(src_path.glob("**/*.js"))
            if len(src_files) > 5:  # Has meaningful code beyond scaffolding
                # Get previous goal from plan manifest
                plan_manifest_path = Path(project_path) / ".ships" / "plan_manifest.json"
                previous_goal = "an existing application"
                if plan_manifest_path.exists():
                    try:
                        import json
                        manifest = json.loads(plan_manifest_path.read_text(encoding='utf-8'))
                        previous_goal = manifest.get('user_goal', '') or manifest.get('description', 'an existing application')
                    except:
                        pass
                
                clarification_msg = f"""⚠️ **This project already contains code.**

I detected you want to build something new, but this project already has:
- **Previous goal:** {previous_goal}
- **{len(src_files)} source files** in the src/ directory

**What would you like to do?**
1. Reply **"add"** - Add this as a new feature to the existing app
2. Reply **"replace"** - Clear and rebuild with the new request (⚠️ destructive)
3. Reply **"new folder"** - Create in a separate project directory

Please clarify before I proceed."""

                logger.info(f"[ORCHESTRATOR] ⚠️ NEW INTENT + EXISTING CODE detected - asking for clarification")
                
                return {
                    "phase": "chat",
                    "messages": [AIMessage(content=clarification_msg)],
                    "artifacts": {**artifacts, "pending_new_intent": current_intent.model_dump() if hasattr(current_intent, 'model_dump') else {}}
                }

    # 7. Build Decision Prompt
    system_prompt = f"""<role>
    You are the Master Orchestrator. You decide which agent runs next.
    </role>
    
    <state>
    PHASE: {phase}
    FILES COMPLETED: {len(completed_files)}
    FIX ATTEMPTS: {fix_attempts}
    PLAN EXISTS: {plan_exists}
    SCAFFOLDING DONE: {scaffolding_done}
    NEW FEATURE REQUEST: {is_new_intent}
    USER CONFIRMATION: {is_confirmation}
    USER QUESTION: {is_question}
    INTENT TYPE: {current_intent.task_type if current_intent else 'None'}
    </state>
    
    <rules>
    PRIORITY 1: Questions
    - If USER QUESTION is True -> call_chat
    
    PRIORITY 2: Planning & Execution (AUTONOMOUS MODE)
    - If PHASE is "planning":
       - If NEW FEATURE REQUEST is True -> call_planner (ALWAYS re-plan)
       - If plan missing OR scaffolding NOT done -> call_planner
       - If plan ready AND scaffolding done -> call_coder (AUTO-PROCEED!)
       
    PRIORITY 3: Execution
    - If PHASE is "plan_ready" -> call_coder (NO PAUSING - just build!)
    - If PHASE is "coding" (and files remain) -> call_coder
    
    PRIORITY 4: Validation & Fixes
    - If PHASE is "validating" -> call_validator
    - If PHASE is "fixing" -> call_fixer
    - If Validation Passed -> finish
    - If PHASE is "fixing_failed" -> call_planner
    - If Fixer failed > 3 times -> finish
    
    NOTE: HITL (Human-in-the-Loop) is DISABLED for routine builds.
    Only pause for critical architectural decisions (not implemented yet).
    </rules>
    
    <output_format>
    Return JSON ONLY:
    {{
      "observations": ["observation 1", "observation 2"],
      "reasoning": "Explain why you are choosing the next step based on state and rules.",
      "decision": "call_planner" | "call_coder" | "call_validator" | "call_fixer" | "call_chat" | "finish",
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
                elif "chat" in raw_decision: decision = "chat"
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
            elif "call_chat" in response: decision = "chat"
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
    logger.info("=" * 60)
    logger.info("[COMPLETE] 🎉 Pipeline completed successfully!")
    logger.info("=" * 60)
    
    artifacts = state.get("artifacts", {})
    project_path = artifacts.get("project_path")
    
    logger.info(f"[COMPLETE] Project path from artifacts: {project_path}")
    
    if not project_path:
        logger.warning("[COMPLETE] ❌ No project path set, cannot launch preview")
        return {
            "phase": "complete",
            "result": {"success": True, "preview_url": None}
        }
    
    from pathlib import Path
    from app.services.preview_manager import preview_manager
    
    # Detect project type
    package_json = Path(project_path) / "package.json"
    index_html = Path(project_path) / "index.html"
    
    logger.info(f"[COMPLETE] Checking package.json: {package_json} - exists: {package_json.exists()}")
    logger.info(f"[COMPLETE] Checking index.html: {index_html} - exists: {index_html.exists()}")
    
    preview_url = None
    
    if package_json.exists():
        # React/Vite project - start dev server via preview_manager
        # This sets current_url which ships-preview polls via /preview/status
        logger.info("[COMPLETE] 🚀 Starting dev server via preview_manager...")
        result = preview_manager.start_dev_server(project_path)
        logger.info(f"[COMPLETE] start_dev_server result: {result}")
        
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
    
    # ===== COLLECTIVE INTELLIGENCE: Capture successful pattern =====
    try:
        session_id = state.get("thread_id") or state.get("config", {}).get("configurable", {}).get("thread_id")
        user_id = state.get("user_id")
        
        captured = await capture_coder_pattern(
            state=state,
            session_id=session_id,
            user_id=user_id,
        )
        if captured:
            logger.info("[COMPLETE] 📚 Pattern captured for Collective Intelligence")
    except Exception as e:
        logger.debug(f"[COMPLETE] Pattern capture skipped: {e}")
    # ================================================================
    
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
    graph.add_node("chat", chat_node)
    graph.add_node("complete", complete_node)
    
    # EDGE WIRING: Hub and Spoke
    # Everyone returns to Orchestrator
    graph.add_edge(START, "orchestrator")
    graph.add_edge("planner", "orchestrator")
    graph.add_edge("coder", "orchestrator")
    graph.add_edge("validator", "orchestrator")
    graph.add_edge("fixer", "orchestrator")
    graph.add_edge("chat", "orchestrator")
    
    # ORCHESTRATOR ROUTING
    def route_orchestrator(state: AgentGraphState):
        decision = state.get("phase")
        if decision in ["planner", "coder", "validator", "fixer", "chat", "complete"]:
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
            "chat": "chat",
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
    project_path: Optional[str] = None,
    settings: Optional[dict] = None,  # User settings
    artifact_context: Optional[dict] = None  # File tree & dependency data from Electron
):
    """
    Stream the full agent pipeline with token-by-token streaming.
    
    Uses stream_mode="messages" for real-time LLM token streaming.
    
    Args:
        user_request: The user's request
        thread_id: Thread ID for state persistence
        project_path: Optional path to user's project directory
        settings: Optional client-side settings dict
        artifact_context: Optional artifact data (file tree, deps) from Electron
        
    Yields:
        Message chunks as the LLM generates tokens
    """
    import logging
    logger = logging.getLogger("ships.agent")
    
    logger.info("=" * 60)
    logger.info(f"[PIPELINE] 📨 Received user_request: '{user_request}'")
    logger.info(f"[PIPELINE] Request length: {len(user_request)} chars")
    logger.info(f"[PIPELINE] Project path: {project_path or 'Not set (using backend dir)'}")
    if artifact_context:
        logger.info(f"[PIPELINE] Artifact context: {len(artifact_context.get('fileTree', {}).get('files', {}))} files provided")
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
            "project_path": project_path,  # None if not set - agents will check and refuse
            "settings": settings or {},    # Inject settings into artifacts
            "artifact_context": artifact_context,  # File tree & deps from Electron
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
        yield event

