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

# PostgreSQL checkpointer for persistent state
# Falls back to MemorySaver if DB unavailable
def get_checkpointer(user_id: str = None, run_id: str = None):
    """
    Get appropriate checkpointer for the pipeline.
    
    Uses PostgresSaver for production (persistent state across restarts),
    or MemorySaver as fallback for development/testing.
    
    Args:
        user_id: Optional user ID for scoped thread_id
        run_id: Optional run ID for scoped thread_id
        
    Returns:
        Configured checkpointer instance
    """
    try:
        from langgraph.checkpoint.postgres import PostgresSaver
        import os
        
        # Get database URL (convert asyncpg to psycopg format)
        db_url = os.getenv(
            "DATABASE_URL",
            "postgresql+asyncpg://ships:ships@localhost/ships"
        )
        # PostgresSaver needs psycopg format, not asyncpg
        sync_db_url = db_url.replace("+asyncpg", "")
        
        # Create PostgresSaver
        checkpointer = PostgresSaver.from_conn_string(sync_db_url)
        
        # Setup tables if needed (idempotent)
        checkpointer.setup()
        
        return checkpointer
        
    except Exception as e:
        import logging
        logger = logging.getLogger("ships.agent")
        logger.warning(f"[CHECKPOINTER] PostgresSaver unavailable, using MemorySaver: {e}")
        return MemorySaver()

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
# Collective Intelligence - capture successful patterns and fixes
from app.services.knowledge.hooks import capture_coder_pattern, capture_fixer_success
from app.services.lock_manager import lock_manager # File locking service



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
    # LOOP DETECTION & CHECKPOINTING (2026 Architecture)
    # ============================================================================
    # Track consecutive calls to detect loops and inform orchestrator
    loop_detection: Dict[str, Any]  # {last_node, consecutive_calls, loop_detected, loop_message}
    current_step: int               # Step counter for git checkpointing


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

    def get_project_tree(root_str: str, max_depth: int = 4) -> str:
        """Scan project structure recursively for context (Limited size)."""
        tree = []
        root = Path(root_str)
        
        # Hard cap to prevent token explosion
        MAX_LINES = 500
        line_count = 0
        truncated = False
        
        ignore_names = {
            'node_modules', 'dist', 'build', 'coverage', '__pycache__', 
            'venv', '.venv', 'env', '.env', 'target', 'bin', 'obj', 
            'vendor', 'bower_components', 'jspm_packages', '.git',
            '.idea', '.vscode', '.next', '.nuxt', 'out', '.output'
        }
        
        def _scan(dir_path: Path, prefix: str = "", level: int = 0):
            nonlocal line_count, truncated
            if level > max_depth or truncated: return
            
            try:
                # Sort dirs first, then files
                items = sorted(dir_path.iterdir(), key=lambda x: (not x.is_dir(), x.name))
            except Exception:
                return

            for item in items:
                if line_count >= MAX_LINES:
                    truncated = True
                    return
                
                # Skip heavy/hidden folders
                if item.name.startswith('.') or item.name in ignore_names:
                    continue
                
                if item.is_dir():
                    tree.append(f"{prefix}📂 {item.name}/")
                    line_count += 1
                    _scan(item, prefix + "  ", level + 1)
                else:
                    tree.append(f"{prefix}📄 {item.name}")
                    line_count += 1

        try:
            if root.exists():
                _scan(root)
                if truncated:
                    tree.append("... (truncated: max 500 lines)")
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

    # 3.5 SYSTEM-LEVEL DISPATCH: Pick & Lock File
    # Instead of letting LLM pick (and race), WE pick an unlocked file here.
    active_file = None
    expected_files = []
    
    if plan_content and project_path:
        import re
        # Extract files from plan
        file_patterns = re.findall(r'(?:src|public|app)/[\w/.-]+\.\w+', plan_content)
        expected_files = sorted(list(set(file_patterns)))
        
        # Determine what's left
        normalized_completed = {str(f).replace("\\", "/").lower() for f in unique_completed}
        pending_files = []
        for f in expected_files:
            if str(f).replace("\\", "/").lower() not in normalized_completed:
                pending_files.append(f)
        
        # Try to acquire lock on first available file (with retry)
        import time
        import asyncio
        
        start_wait = time.time()
        wait_timeout = 60 # wait up to 60s before yielding
        
        while (time.time() - start_wait) < wait_timeout:
            for f in pending_files:
                # Check if locked
                if not lock_manager.is_locked(project_path, f):
                    # Acquire!
                    if lock_manager.acquire(project_path, f, "coder_node"):
                        active_file = f
                        logger.info(f"[CODER] 🔒 Acquired lock for: {active_file}")
                        break
            
            if active_file:
                break
                
            # Wait and retry
            if pending_files:
                logger.debug(f"[CODER] ⏳ All files locked. Waiting... ({int(time.time() - start_wait)}s)")
                await asyncio.sleep(2)
            else:
                break
        
        if not active_file and pending_files:
             logger.warning(f"[CODER] ⚠️ All {len(pending_files)} pending files are LOCKED after {wait_timeout}s. Yielding.")
             return {
                 "phase": "waiting", # Wait for locks to free
                 "messages": [AIMessage(content="Waiting for file locks to release.")]
             }

    # 4. Build Dynamic System Prompt
    task_focus = "3. Pick the NEXT file..."
    if active_file:
        task_focus = f"3. ➤ IMPLEMENT: {active_file}\n   (You have exclusive lock on this file. Do NOT touch others.)"

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
2. CRITICAL: Check "ACTUAL FILE STRUCTURE".
   - If looking for `src/components/Board.tsx` and `src/components/Board/Board.tsx` exists -> SKIP (Exists).
   - Do NOT create duplicate files.
{task_focus}
4. Write it using write_file_to_disk.
5. IF DONE with this file, output "File created: [filename]".
6. If the plan lists more files, you can try to continue, BUT:
   - If you were assigned a specific file (Step 3), only implement THAT one then stop.
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

    # 5. Build state for Coder.invoke() - Use centralized context scoping
    # Import context scoping service for maintainable token optimization
    from app.services.context_scoping import scope_context_for_agent
    
    # Get scoped context (excludes full message history to prevent token bloat)
    coder_state = scope_context_for_agent(state, "coder")
    
    # Merge with coder-specific overrides that need fresh computation
    coder_state["artifacts"] = {
        **coder_state.get("artifacts", {}),
        "plan_content": plan_content,
        "project_structure": real_file_tree,
        "project_path": project_path,
    }
    coder_state["parameters"] = {
        "user_request": user_request.content if hasattr(user_request, 'content') else str(user_request),
        "project_path": project_path,
    }
    coder_state["completed_files"] = unique_completed
    
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
            folder_map_path = ships_dir / "folder_map_plan.json"
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
            
            # Check each expected file against state AND disk
            missing = []
            for expected in expected_files:
                norm_expected = str(expected).replace("\\", "/").lower()
                
                # 1. Check if marked completed
                if norm_expected in normalized_completed:
                    continue
                
                # 2. Check strict disk existence (handles cases where tool output parsing failed)
                # This prevents "loop of doom" where file exists but Coder keeps being told to make it
                try:
                    full_path = Path(project_path) / expected
                    if full_path.exists() and full_path.is_file():
                        current_completed.append(str(expected)) # Sync state
                        normalized_completed.add(norm_expected)
                        logger.info(f"[CODER] 🔍 Verified existing file on disk: {expected}")
                        continue
                except Exception:
                    pass
                
                missing.append(expected)

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
        
        # Release lock
        if active_file:
            lock_manager.release(project_path, active_file, "coder_node")
            logger.info(f"[CODER] 🔓 Released lock for {active_file}")

        return {
            "messages": [AIMessage(content=f"Coder completed: {result.get('status', 'unknown')}")],
            "phase": next_phase,
            "completed_files": current_completed,
            "agent_status": {"status": result.get("status", "in_progress")}
        }
        
    except Exception as e:
        logger.error(f"[CODER] ❌ Coder invoke failed: {e}")
        
        # Release lock
        if active_file:
            lock_manager.release(project_path, active_file, "coder_node")
            
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
        logger.warning(f"[FIXER] ⚠️ Max attempts ({max_attempts}) exceeded, asking user for help")
        return {
            "phase": "chat",  # Ask user for help, NOT planner (that causes rebuilds)
            "fix_attempts": fix_attempts,
            "error_log": state.get("error_log", []) + ["Fixer max attempts exceeded - needs user guidance"],
            "messages": [AIMessage(content="I've tried to fix this issue multiple times but am still stuck. Let me explain what's happening and get your input.")]
        }
    
    # Invoke the Fixer
    fixer = Fixer()
    
    # 3.5 SYSTEM-LEVEL DISPATCH: Pick & Lock File from Errors
    # Filter the validation report to focus ONLY on one unlocked file.
    active_fix_file = None
    original_report = artifacts.get("validation_report", {})
    filtered_report = original_report # Default to full report if no fit
    
    violations = original_report.get("violations", [])
    if violations:
        # Extract unique files needing fix
        error_files = []
        seen = set()
        for v in violations:
            f_path = v.get("file_path") or v.get("file")
            if f_path and f_path not in seen:
                error_files.append(f_path)
                seen.add(f_path)
        
        # If no specific files identified (e.g., general build error), skip lock waiting
        if not error_files:
            logger.info("[FIXER] ℹ️ No specific error files identified - proceeding without lock")
            filtered_report = original_report
            filtered_report["fixer_instructions"] = (
                "GENERAL FIX: No specific file identified in error. "
                "Check build output and ensure all required files exist (e.g., index.html)."
            )
        else:
            # Try to acquire lock with retry
            import time
            import asyncio
            
            start_wait = time.time()
            wait_timeout = 60
            
            while (time.time() - start_wait) < wait_timeout:
                for f in error_files:
                    if not lock_manager.is_locked(project_path, f):
                        if lock_manager.acquire(project_path, f, "fixer_node"):
                            active_fix_file = f
                            logger.info(f"[FIXER] 🔒 Acquired lock for: {active_fix_file}")
                            break
                
                if active_fix_file:
                    break
                    
                logger.debug(f"[FIXER] ⏳ All error files locked. Waiting... ({int(time.time() - start_wait)}s)")
                await asyncio.sleep(2)
            
            # If we locked a file, filter the report
            if active_fix_file:
                filtered_violations = [
                    v for v in violations 
                    if (v.get("file_path") == active_fix_file or v.get("file") == active_fix_file)
                ]
                filtered_report = {**original_report, "violations": filtered_violations}
                # Add directive
                filtered_report["fixer_instructions"] = (
                    f"FOCUS: Only fix errors in {active_fix_file}. "
                    "You have an exclusive lock on this file."
                )
            elif error_files:
                 # All files locked
                 logger.warning(f"[FIXER] ⚠️ All error files locked after {wait_timeout}s. Yielding.")
                 return {
                     "phase": "waiting",
                     "messages": [AIMessage(content="Waiting for files to unlock.")]
                 }

    # Use centralized context scoping (prevents token bloat from full state spread)
    from app.services.context_scoping import scope_context_for_agent
    
    fixer_state = scope_context_for_agent(state, "fixer")
    
    # Merge with fixer-specific overrides
    fixer_state["artifacts"] = {
        **fixer_state.get("artifacts", {}),
        "project_path": project_path,
        "validation_report": filtered_report  # Pass constrained report
    }
    fixer_state["parameters"] = {
        "attempt_number": fix_attempts,
        "active_file": active_fix_file
    }
    
    try:
        try:
            result = await fixer.invoke(fixer_state)
            
            logger.info(f"[FIXER] ✅ Fixer completed")
            
            # Check for escalation (but route to user, not planner)
            if result.get("requires_user_help") or result.get("requires_replan") or result.get("needs_replan"):
                reason = result.get("artifacts", {}).get("escalation_reason") or \
                         result.get("artifacts", {}).get("reason") or "Fixer needs user guidance"
                logger.info(f"[FIXER] ⚠️ User help needed: {reason}")
                return {
                    "phase": "chat",  # Ask user, NOT planner
                    "fix_attempts": fix_attempts,
                    "error_log": state.get("error_log", []) + [f"Needs help: {reason}"],
                    "messages": [AIMessage(content=f"I need your help: {reason}")]
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
    finally:
        if active_fix_file:
             lock_manager.release(project_path, active_fix_file, "fixer_node")
             logger.info(f"[FIXER] 🔓 Released lock for {active_fix_file}")


async def orchestrator_node(state: AgentGraphState) -> Dict[str, Any]:
    """
    MASTER ORCHESTRATOR NODE
    Decides which agent to call next based on global state.
    """
    logger.info("[ORCHESTRATOR] 🧠 Starting orchestrator node...")
    
    # ================================================================
    # LOOP DETECTION: Track consecutive calls and inform orchestrator
    # ================================================================
    loop_detection = state.get("loop_detection", {
        "last_node": None,
        "consecutive_calls": 0,
        "loop_detected": False,
        "loop_message": ""
    })
    
    # Check if we're looping (same phase called 3+ times consecutively)
    current_phase = state.get("phase", "planning")
    loop_warning = ""
    
    if loop_detection.get("last_node") == current_phase:
        loop_detection["consecutive_calls"] = loop_detection.get("consecutive_calls", 0) + 1
        
        if loop_detection["consecutive_calls"] >= 3:
            loop_detection["loop_detected"] = True
            loop_detection["loop_message"] = (
                f"⚠️ LOOP DETECTED: {current_phase} called {loop_detection['consecutive_calls']} times consecutively. "
                f"Previous attempts are not making progress. Consider: "
                f"1) Ask user for clarification, 2) Try a completely different approach, "
                f"3) Skip this task and move on, 4) Mark as blocked and explain why."
            )
            loop_warning = loop_detection["loop_message"]
            logger.warning(f"[ORCHESTRATOR] {loop_warning}")
    else:
        # Different node - reset counter
        loop_detection = {
            "last_node": current_phase,
            "consecutive_calls": 1,
            "loop_detected": False,
            "loop_message": ""
        }
    
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
    # Classify current intent (Optimized: Check cache first)
    current_intent = None
    cached_intent_data = artifacts.get("structured_intent")
    
    if cached_intent_data:
        # Re-hydrate from cache to save tokens
        try:
            current_intent = IntentClassifier()._create_default_intent(user_request) # Dummy shell
            # Manually hydrate fields
            for key, val in cached_intent_data.items():
                if hasattr(current_intent, key):
                    setattr(current_intent, key, val)
            logger.info(f"[ORCHESTRATOR] ⏩ Using CACHED intent: {current_intent.task_type}/{current_intent.action}")
        except Exception as e:
            logger.warning(f"[ORCHESTRATOR] Failed to hydrate cached intent: {e}")
            cached_intent_data = None # Force re-classify

    if user_request and not cached_intent_data:
        try:
            classifier = IntentClassifier()
            # Load folder_map for context if available
            folder_map_data = None
            if project_path:
                folder_map_path = Path(project_path) / ".ships" / "folder_map_plan.json"
                if folder_map_path.exists():
                    import json
                    folder_map_data = json.loads(folder_map_path.read_text(encoding='utf-8'))
            
            current_intent = await classifier.classify(user_request, folder_map=folder_map_data)
            logger.info(f"[ORCHESTRATOR] 🎯 Intent classified: {current_intent.task_type}/{current_intent.action} (conf: {current_intent.confidence:.2f})")
            
            # Cache it!
            artifacts["structured_intent"] = current_intent.model_dump()
            
        except Exception as e:
            logger.warning(f"[ORCHESTRATOR] Intent classification failed: {e}")
    
    # ====================================================================
    # NEW INTENT DETECTION: Use LLM action type, not keyword matching
    # ====================================================================
    # If action is 'modify', 'add', 'update', 'fix', 'remove', etc. on an
    # existing project with a plan, we need to create a FRESH plan for this
    # specific modification - not continue the old project build plan.
    # ====================================================================
    
    modification_actions = {'modify', 'add', 'update', 'fix', 'remove', 'change', 'improve', 'refactor', 'enhance'}
    
    if project_path and plan_exists and current_intent:
        # Check if this is a modification action (not a new build)
        if current_intent.action in modification_actions:
            # Check if the project seems "complete" (has source files, node_modules, etc.)
            project_root = Path(project_path)
            has_src = (project_root / "src").exists()
            has_package = (project_root / "package.json").exists()
            project_looks_complete = has_src or has_package
            
            if project_looks_complete:
                is_new_intent = True
                logger.info(f"[ORCHESTRATOR] 🔄 MODIFICATION on existing project detected")
                logger.info(f"[ORCHESTRATOR]    Action: {current_intent.action}")
                logger.info(f"[ORCHESTRATOR]    Request: {current_intent.description[:60]}...")
                logger.info(f"[ORCHESTRATOR]    Will create fresh plan for this modification")
        
        # Also check for keyword-based new intent (fallback for edge cases)
        elif current_intent.task_type in ['feature', 'modify', 'refactor'] and not is_new_intent:
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
                    
                    # Less than 30% keyword coverage = definitely new intent (lowered from 50%)
                    if coverage < 0.3:
                        is_new_intent = True
                        logger.info(f"[ORCHESTRATOR] 🆕 NEW INTENT detected (keyword coverage: {coverage:.1%})")
                        
                except Exception as e:
                    logger.warning(f"[ORCHESTRATOR] Could not compare intents: {e}")
    
    # If new intent, version old artifacts and force re-plan
    # CRITICAL: Only version ONCE per session to prevent duplicate artifacts
    already_versioned = artifacts.get("artifacts_versioned_this_session", False)
    
    if is_new_intent and project_path and not already_versioned:
        logger.info("[ORCHESTRATOR] 🔄 Versioning old plan artifacts...")
        ships_dir = Path(project_path) / ".ships"
        import shutil
        from datetime import datetime
        version_suffix = datetime.now().strftime("_%Y%m%d_%H%M%S")
        
        versioned_count = 0
        for artifact_name in ["plan_manifest", "task_list", "folder_map_plan", "implementation_plan"]:
            for ext in [".json", ".md"]:
                artifact_file = ships_dir / f"{artifact_name}{ext}"
                if artifact_file.exists():
                    versioned = ships_dir / f"{artifact_name}{version_suffix}{ext}"
                    # Use MOVE instead of COPY to prevent duplicates
                    shutil.move(str(artifact_file), str(versioned))
                    versioned_count += 1
        
        # Mark as versioned in artifacts to prevent re-versioning
        artifacts["artifacts_versioned_this_session"] = True
        
        # Mark plan as needing refresh
        plan_exists = False
        logger.info(f"[ORCHESTRATOR] ✓ {versioned_count} artifacts versioned, forcing re-plan")

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
    # ALSO: Track if we already asked, to prevent infinite loop
    already_asked = artifacts.get("asked_for_clarification", False)
    
    if current_intent and current_intent.is_ambiguous and not already_asked:
        clarification_msg = "\n".join(current_intent.clarification_questions) if current_intent.clarification_questions else "I need more information to proceed. Could you clarify what you'd like me to do?"
        logger.info(f"[ORCHESTRATOR] ❓ AMBIGUOUS request detected - asking for clarification")
        logger.info(f"[ORCHESTRATOR] Questions: {current_intent.clarification_questions}")
        
        return {
            "phase": "chat",  # Route to chat to show message
            "messages": [AIMessage(content=f"🤔 **I need clarification:**\n\n{clarification_msg}")],
            "artifacts": {
                **artifacts, 
                "pending_intent": current_intent.model_dump() if hasattr(current_intent, 'model_dump') else {},
                "asked_for_clarification": True  # Prevent re-asking loop
            }
        }
    elif current_intent and current_intent.is_ambiguous and already_asked:
        # Already asked - just proceed with best guess
        logger.info("[ORCHESTRATOR] ⏭️ Already asked for clarification, proceeding with best guess")

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
    
    <agent_domains>
    === CRITICAL: Understand what each agent CAN and CANNOT do ===
    
    PLANNER:
    - CAN: Create implementation plans, scaffold new projects, design architecture
    - CANNOT: Fix code errors, resolve build failures, debug existing code
    - WHEN TO CALL: New feature requests, no plan exists, need to restructure
    
    CODER:
    - CAN: Write new files, implement features according to plan
    - CANNOT: Fix its own syntax/build errors (that's Fixer's job)
    - WHEN TO CALL: Plan exists, need to write/modify code files
    
    VALIDATOR:
    - CAN: Run builds, check for errors, verify code compiles
    - CANNOT: Fix errors (it only reports them)
    - WHEN TO CALL: Code was just written, need to verify it works
    
    FIXER:
    - CAN: Fix syntax errors, build errors, type errors, missing imports
    - CANNOT: Re-architect or re-plan the project
    - WHEN TO CALL: Validation found errors that need fixing
    
    CHAT:
    - CAN: Answer questions, ask user for clarification, escalate problems
    - WHEN TO CALL: User asked a question, OR agent is stuck and needs help
    </agent_domains>
    
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
    LOOP WARNING: {loop_warning if loop_warning else 'None'}
    RECENT ERRORS: {error_log[-3:] if error_log else 'None'}
    </state>
    
    <rules>
    PRIORITY 1: Questions
    - If USER QUESTION is True -> call_chat
    
    PRIORITY 2: Planning & Execution
    - If PHASE is "planning":
       - If NEW FEATURE REQUEST is True -> call_planner (re-plan for new feature)
       - If plan missing OR scaffolding NOT done -> call_planner
       - If plan ready AND scaffolding done -> call_coder (proceed to code!)
       
    PRIORITY 3: Execution
    - If PHASE is "plan_ready" or "coding" -> call_coder
    
    PRIORITY 4: Validation & Fixes
    - If PHASE is "validating" -> call_validator
    - If PHASE is "fixing" -> call_fixer
    - If Validation Passed -> finish
    
    PRIORITY 5: Error Recovery (CRITICAL)
    - If FIX ATTEMPTS >= 3 -> call_chat (ASK USER FOR HELP - fixer is stuck)
    - If LOOP WARNING is present -> call_chat (something is broken, need user)
    - NEVER call Planner when there are code/build errors - Planner cannot fix code!
    - NEVER rebuild the project just because validation is failing!
    
    PRIORITY 6: Completion
    - If all files coded and validation passed -> finish
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
    
    # ====================================================================
    # STEP TRACKING: Record orchestrator decision
    # ====================================================================
    try:
        from app.services.step_tracking import record_step
        import asyncio
        asyncio.create_task(record_step(
            agent="orchestrator",
            phase=state.get("phase", "unknown"),
            action=f"route_to_{decision}",
            content={"decision": decision, "loop_detected": loop_detection.get("loop_detected", False)},
        ))
    except Exception:
        pass  # Non-fatal
    # ====================================================================
    
    return {
        "phase": decision,  # This drives the routing
        "loop_detection": loop_detection,
        "current_step": state.get("current_step", 0) + 1
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
    
    # ===== RUN COMPLETION EVENT: For Electron git checkpointing =====
    # This gets streamed to the frontend via the WebSocket and can be
    # forwarded to Electron for git commit on run completion
    run_complete_event = {
        "type": "run:complete",
        "project_path": project_path,
        "step_count": state.get("current_step", 0),
        "files_completed": len(state.get("completed_files", [])),
        "status": "complete"
    }
    logger.info(f"[COMPLETE] 📤 Run complete event: {run_complete_event}")
    # ================================================================
    
    return {
        "phase": "complete",
        "result": {
            "success": True,
            "preview_url": preview_url,
            "project_path": project_path,
            "run_complete_event": run_complete_event  # For Electron git checkpoint
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
    checkpointer = get_checkpointer()
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
    artifact_context: Optional[dict] = None,  # File tree & dependency data from Electron
    user_id: Optional[str] = None  # User ID for step tracking
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
        user_id: Optional user ID for step tracking (enables DB persistence)
        
    Yields:
        Message chunks as the LLM generates tokens
    """
    import logging
    from uuid import UUID
    logger = logging.getLogger("ships.agent")
    
    logger.info("=" * 60)
    logger.info(f"[PIPELINE] 📨 Received user_request: '{user_request}'")
    logger.info(f"[PIPELINE] Request length: {len(user_request)} chars")
    logger.info(f"[PIPELINE] Project path: {project_path or 'Not set (using backend dir)'}")
    if artifact_context:
        logger.info(f"[PIPELINE] Artifact context: {len(artifact_context.get('fileTree', {}).get('files', {}))} files provided")
    logger.info("=" * 60)
    
    # ====================================================================
    # STEP TRACKING: Start a new run if user_id provided
    # ====================================================================
    run_id = None
    if user_id and project_path:
        try:
            from app.services.step_tracking import start_run
            run_id = await start_run(
                user_id=UUID(user_id) if isinstance(user_id, str) else user_id,
                project_path=project_path,
                user_request=user_request[:500]  # Truncate for DB
            )
            if run_id:
                logger.info(f"[PIPELINE] 📊 Step tracking started: run_id={run_id}")
        except Exception as e:
            logger.debug(f"[PIPELINE] Step tracking unavailable: {e}")
    # ====================================================================
    
    # Use PostgresSaver for production persistence, MemorySaver as fallback
    checkpointer = get_checkpointer()
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
            "run_id": str(run_id) if run_id else None,  # For step tracking in nodes
            "user_id": user_id,  # Pass user_id to nodes
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
            "run_id": str(run_id) if run_id else None,
        },
        "recursion_limit": 100,  # Agent needs iterations for multi-step tasks
    }
    
    # Use stream_mode="messages" for token-by-token streaming
    # This yields (message_chunk, metadata) tuples as the LLM generates
    accumulated_usage = {"input": 0, "output": 0}
    try:
        async for event in graph.astream(initial_state, config=config, stream_mode="messages", subgraphs=True):
            # Track token usage from message chunks
            if isinstance(event, tuple) and len(event) == 2:
                chunk, metadata = event
                if hasattr(chunk, "usage_metadata") and chunk.usage_metadata:
                    # Accumulate usage
                    usage = chunk.usage_metadata
                    accumulated_usage["input"] += usage.get("input_tokens", 0)
                    accumulated_usage["output"] += usage.get("output_tokens", 0)
            yield event
    finally:
        # ====================================================================
        # STEP TRACKING: Complete the run when pipeline finishes
        # ====================================================================
        try:
            # 1. Update Token Usage in DB
            from app.database import get_session_factory
            from sqlalchemy import select
            from app.models import User
            
            # Helper to access DB inside generator finally block
            async with get_session_factory()() as session:
                if user_id:
                     user = await session.execute(select(User).where(User.id == user_id))
                     user = user.scalar_one_or_none()
                     if user:
                         # Weighted Tracking: Flash=1x, Pro=20x
                         # Currently defaulting to Flash (1x) as it's the main driver
                         # TODO: Detect model from metadata for 20x multiplier
                         multiplier = 1.0 
                         
                         total_cost = int((accumulated_usage["input"] + accumulated_usage["output"]) * multiplier)
                         if total_cost > 0:
                             user.tokens_used_month += total_cost
                             await session.commit()
                             logger.info(f"[PIPELINE] 💰 Tracked {total_cost} tokens for user {user.email}")

            # 2. Complete Step Tracking
            if run_id:
                from app.services.step_tracking import complete_run
                await complete_run(status="complete")
                logger.info(f"[PIPELINE] 📊 Step tracking completed: run_id={run_id}")
        except Exception as e:
            logger.error(f"[PIPELINE] Finalization failed: {e}")
        # ====================================================================

