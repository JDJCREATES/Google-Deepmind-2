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

from typing import TypedDict, Annotated, Literal, Optional, List, Dict, Any, Union
from enum import Enum
from operator import add
import os
from pathlib import Path
import uuid
from sqlalchemy import update
from app.database.connection import get_session_factory
from app.models.agent_runs import AgentRun

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
from app.graphs.deterministic_router import DeterministicRouter  # Production-grade deterministic routing
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

class ValidationStatus(str, Enum):
    PENDING = "pending"       # Initial state / Needs validation (e.g. after code changes)
    PASSED = "passed"         # Validation run and passed
    FAILED_RECOVERABLE = "failed_recoverable" # Failed but can be fixed (lint errors)
    FAILED_CRITICAL = "failed_critical"       # Failed and cannot be auto-fixed (config errors)
    SKIPPED = "skipped"       # Explicitly skipped

class AgentGraphState(TypedDict):
    """
    Unified state object for the entire agent pipeline.
    Uses 'modern' fields for 2.0 architecture and legacy fields for backward compat.
    """
    # Messages for conversation (trimmed for token efficiency)
    messages: Annotated[List[BaseMessage], add]
    
    # Current phase (routing and state tracking)
    # Note: Routing phases (planner, coder, validator, fixer) are used by orchestrator
    # State phases (planning, coding, validating, fixing) are used by nodes
    phase: Literal[
        "planning", "planner",           # Planning state / route to planner
        "coding", "coder",               # Coding state / route to coder
        "validating", "validator",       # Validating state / route to validator
        "fixing", "fixer",               # Fixing state / route to fixer
        "chat", "chat_setup",            # Chat interaction
        "complete",                       # Success state
        "error",                         # Error state
        "waiting",                       # Waiting for locks
        "orchestrator"                   # Escalation to orchestrator
    ]
    
    # Artifacts produced by agents
    artifacts: Dict[str, Any]
    
    # Explicit Cache Name (Gemini)
    cache_name: Optional[str]
    
    # Tool results stored separately from messages (token optimization)
    # Only metadata/references go in messages, full results here
    tool_results: Dict[str, Any]
    
    # Current task being worked on
    current_task_index: int
    
    # Validation status - Robust Enum (2025)
    validation_status: ValidationStatus
    
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
    completed_files: Annotated[List[str], add]    # List of files successfully written
    
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
    
    # ============================================================================
    # AGENT STATUS (for orchestrator reasoning)
    # ============================================================================
    implementation_complete: bool   # Coder sets this when all files written
    agent_status: Dict[str, Any]    # {status, failure_layer, recommended_action, ...}
    current_step: int               # Step counter for git checkpointing
    
    # ============================================================================
    # FIX REQUEST (structured validator → fixer handoff)
    # ============================================================================
    fix_request: Optional[Dict[str, Any]]  # Structured error data from validator

    # ============================================================================
    # STREAM EVENTS (UI-safe emissions for frontend)
    # ============================================================================
    # Agents emit events here instead of relying on LangGraph internal parsing
    stream_events: Annotated[List[Dict[str, Any]], add]


# ============================================================================
# NODE FUNCTIONS
# ============================================================================

import logging
logger = logging.getLogger("ships.agent")




async def planner_node(state: AgentGraphState) -> Dict[str, Any]:
    """Run the Planner using the consolidated Planner agent."""
    logger.info("[PLANNER_NODE] � Delegating to consolidated Planner.invoke")
    
    # 1. Safety: Set project root if known
    artifacts = state.get("artifacts", {})
    project_path = artifacts.get("project_path")
    if project_path:
        set_project_root(project_path)
        
    # 2. Invoke Planner
    planner = Planner()
    result = await planner.invoke(state)
        
    # 3. Merge Artifacts (Safety: Don't lose project_path)
    merged_artifacts = {**state.get("artifacts", {})}
    if "artifacts" in result:
        merged_artifacts.update(result["artifacts"])
        result["artifacts"] = merged_artifacts
        
    return result


async def coder_node(state: AgentGraphState) -> Dict[str, Any]:
    """Run the Coder using the consolidated Coder agent."""
    logger.info("[CODER_NODE] 💻 Delegating to consolidated Coder.invoke")
    
    # 1. Safety
    artifacts = state.get("artifacts", {})
    project_path = artifacts.get("project_path")
    if project_path:
        set_project_root(project_path)
    
    # 2. Invoke Coder
    coder = Coder()
    result = await coder.invoke(state)
    
    # 3. Extract Status
    implementation_complete = result.get("implementation_complete", False)
    completed_files = result.get("completed_files", [])
    
    # 4. Refresh File Tree (For Frontend)
    if project_path:
        try:
             from app.agents.tools.coder.file_tree import scan_project_tree
             # Scan depth from settings or default
             settings = state.get("artifacts", {}).get("settings", {})
             scan_depth = settings.get("artifacts", {}).get("fileTreeDepth", 3) if settings else 3
             
             scan_project_tree.invoke({
                "subpath": ".",
                "max_depth": int(scan_depth),
                "save_artifact": True
             })
             logger.info("[CODER_NODE] 🌳 Refreshed file tree")
        except Exception as e:
             logger.warning(f"[CODER_NODE] ⚠️ File tree refresh failed: {e}")

    # 5. Git Checkpoint (If complete)
    if implementation_complete and project_path:
        try:
            from app.services.git_checkpointer import get_checkpointer
            checkpointer = get_checkpointer(project_path)
            commit_hash = checkpointer.checkpoint(
                "implementation_complete",
                f"{len(completed_files)} files implemented"
            )
            if commit_hash:
                logger.info(f"[CODER] 📸 Git checkpoint: {commit_hash[:8]}")
        except Exception as cp_err:
            logger.debug(f"[CODER] Git checkpoint skipped: {cp_err}")

    # 6. Prepare Result
    merged_artifacts = {**artifacts}
    if "artifacts" in result:
        merged_artifacts.update(result["artifacts"])
    
    merged_artifacts["implementation_complete"] = implementation_complete
    
    return {
        "phase": "orchestrator",
        "artifacts": merged_artifacts,
        "completed_files": completed_files,
        "validation_status": ValidationStatus.PENDING, # Code changed, validation needed
        "stream_events": result.get("stream_events", []),
        "loop_detection": {**state.get("loop_detection", {}), "wait_attempts": 0} if implementation_complete else state.get("loop_detection")
    }


async def validator_node(state: AgentGraphState) -> Dict[str, Any]:
    """
    Run the Validator agent (WRAPPER).
    Delegates to sub_agents.validator.Validator for core logic.
    """
    logger.info("[VALIDATOR] 🔍 Starting validator node...")
    
    # Local context
    artifacts = state.get("artifacts", {})
    project_path = artifacts.get("project_path")
    set_project_root(project_path)
    
    try:
        # Delegate to Validator Agent
        validator = Validator()
        result = await validator.invoke(state)
        
        # Extract core results
        validation_passed = result.get("passed", False)
        violation_count = result.get("violation_count", 0)
        failure_layer = result.get("failure_layer", "none")
        
        # =================================================================
        # POST-PROCESSING: Checkpoints, Fix Requests, Collective Intel
        # =================================================================
        if validation_passed:
            logger.info(f"[VALIDATOR] ✅ Passed ({violation_count} violations)")
            
            # 1. Collective Intelligence Capture
            if state.get("pending_fix_context"):
                await _try_capture_fix_success(state)
                
            # 2. Git Checkpoint
            _try_git_checkpoint(project_path, "validation_passed", f"Tests passed")
            
        else:
            # Log failure details
            logger.warning(f"[VALIDATOR] ❌ Failed at {failure_layer} layer ({violation_count} violations)")
            
            # CRITICAL: Log actual validation errors
            validation_report = result.get("artifacts", {}).get("validation_report", {})
            layer_results = validation_report.get("layer_results", {})
            
            if layer_results:
                failed_layer_data = layer_results.get(failure_layer, {})
                violations = failed_layer_data.get("violations", [])
                
                if violations:
                    logger.error(f"[VALIDATOR] 🔍 Top validation errors:")
                    for i, violation in enumerate(violations[:5], 1):  # Show top 5
                        logger.error(f"  {i}. [{violation.get('severity', 'UNKNOWN')}] {violation.get('message', 'No message')}")
                        if violation.get('details'):
                            logger.error(f"     Details: {violation.get('details')}")
                else:
                    logger.error(f"[VALIDATOR] No violation details found in {failure_layer} layer")
            else:
                logger.error(f"[VALIDATOR] No layer results found in validation report")
            
            # 1. Create Fix Request (Required for Fixer)
            _try_create_fix_request(state, result, project_path)
            
            # 2. Update Error Log
            # Logic handled by result return, but we ensure it persists
            pass

        # Return State Update
        # Return State Update
        return {
            "validation_status": ValidationStatus.PASSED if validation_passed else ValidationStatus.FAILED_RECOVERABLE,
            "phase": "orchestrator",
            "error_log": state.get("error_log", []) + ([f"Validation Failed [{failure_layer}]"] if not validation_passed else []),
            "artifacts": {**artifacts, **result.get("artifacts", {})},
            "agent_status": {
                "status": "pass" if validation_passed else "fail",
                "failure_layer": failure_layer,
                "violation_count": violation_count
            },
            "stream_events": result.get("stream_events", []),
            # Clear pending fix context if we just validated it (pass or fail)
            "pending_fix_context": None if validation_passed else state.get("pending_fix_context")
        }
        
    except Exception as e:
        logger.error(f"[VALIDATOR] ❌ Validator failed: {e}")
    except Exception as e:
        logger.error(f"[VALIDATOR] ❌ Validator failed: {e}")
        return {
            "validation_status": ValidationStatus.FAILED_CRITICAL,
            "phase": "orchestrator",
            "error_log": state.get("error_log", []) + [f"Validator error: {str(e)}"],
            "messages": [AIMessage(content=f"Validation error: {e}")]
        }


# Helper functions to keep node clean
async def _try_capture_fix_success(state):
    try:
        pending_fix = state.get("pending_fix_context")
        if pending_fix:
             await capture_fixer_success(
                state=state,
                error_message=pending_fix.get("error_message", ""),
                solution_code=pending_fix.get("solution_code", ""),
                solution_description=pending_fix.get("description", ""),
                diff=pending_fix.get("diff", ""),
                before_errors=pending_fix.get("before_errors", []),
                session_id=state.get("thread_id") or state.get("config", {}).get("configurable", {}).get("thread_id"),
                user_id=state.get("user_id"),
            )
    except Exception: pass

def _try_git_checkpoint(project_path, action, msg):
    try:
        from app.services.git_checkpointer import get_checkpointer
        cp = get_checkpointer(project_path)
        cp.checkpoint(action, msg)
    except Exception: pass

def _try_create_fix_request(state, result, project_path):
    try:
        from app.agents.sub_agents.fixer.fix_request import FixRequest
        from app.artifacts.artifact_manager import get_artifact_manager
        
        fix_req = FixRequest.from_validation_result(
            validation_result=result,
            project_path=project_path,
            completed_files=state.get("completed_files", []),
            fix_attempt=state.get("fix_attempts", 0) + 1
        )
        
        # Update artifacts in result (mutation, but effective)
        if "artifacts" not in result: result["artifacts"] = {}
        result["artifacts"]["fix_request"] = fix_req.model_dump()
        
        # Save to disk
        if project_path:
            get_artifact_manager(project_path).save_json("fix_request", fix_req.model_dump())
            
    except Exception as e:
        logger.warning(f"[VALIDATOR] Could not create fix request: {e}")


async def chat_setup(state: AgentGraphState) -> Dict[str, Any]:
    """
    Setup before chat session.
    Sets the project_root so chat tools can read files.
    """
    artifacts = state.get("artifacts", {})
    project_path = artifacts.get("project_path")
    
    if project_path:
        set_project_root(project_path)
        logger.info(f"[CHAT_SETUP] 📁 Project root set to: {project_path}")
    
    return {}  # No state changes, just setup


async def chat_cleanup(state: AgentGraphState) -> Dict[str, Any]:
    """
    Cleanup after chat session.
    Ensure phase is marked complete and intent is cleared.
    """
    artifacts = state.get("artifacts", {})
    return {
        "phase": "complete",
        "artifacts": {**artifacts, "structured_intent": None},
        "stream_events": []
    }


async def fixer_node(state: AgentGraphState) -> Dict[str, Any]:
    """
    Run the Fixer agent (WRAPPER).
    Delegates to sub_agents.fixer.Fixer for core logic.
    Features: Smart Locking, Context Scoping, Git Checkpoints.
    """
    logger.info("[FIXER] 🔧 Starting fixer node...")
    
    artifacts = state.get("artifacts", {})
    project_path = artifacts.get("project_path")
    set_project_root(project_path)
    
    # 1. Check Max Attempts
    fix_attempts = state.get("fix_attempts", 0) + 1
    max_attempts = state.get("max_fix_attempts", 3)
    
    if fix_attempts > max_attempts:
        logger.warning(f"[FIXER] ⚠️ Max attempts ({max_attempts}) exceeded")
        return {
            "phase": "chat", # Escalate to user
            "fix_attempts": fix_attempts,
            "messages": [AIMessage(content="I've tried multiple times but am stuck. I need your guidance.")],
            "stream_events": []
        }

    # 2. Acquire Smart Lock (refactored to LockManager helper)
    # Filter for files mentioned in validation violations
    from app.services.lock_manager import acquire_lock_with_retries
    
    error_files = _extract_error_files(artifacts.get("validation_report", {}))
    active_fix_file = None
    
    if error_files:
        active_fix_file = await acquire_lock_with_retries(lock_manager, project_path, error_files, "fixer_node")
        if not active_fix_file and error_files:
             # Escalation logic if locks fail
             logger.error("[FIXER] ❌ Could not acquire locks.")
             return {"phase": "waiting", "messages": [AIMessage(content="Waiting for files to unlock.")]}
    
    # 3. Invoke Fixer Context Scoped
    from app.services.context_scoping import scope_context_for_agent
    fixer_state = scope_context_for_agent(state, "fixer")
    
    # Pass metadata
    fixer_state["artifacts"] = {**fixer_state.get("artifacts", {}), "project_path": project_path}
    fixer_state["parameters"] = {"attempt_number": fix_attempts, "active_file": active_fix_file}
    
    try:
        fixer = Fixer()
        result = await fixer.invoke(fixer_state)
        
        # 4. Handle Result
        if result.get("requires_user_help"):
             return {
                 "phase": "chat",
                 "fix_attempts": fix_attempts,  # Track attempts even when asking for help
                 "messages": [AIMessage(content=f"Help needed: {result.get('artifacts', {}).get('reason')}")],
                 "stream_events": []
             }

        # 5. Git Checkpoint
        _try_git_checkpoint(project_path, "fix_applied", f"Fix attempt #{fix_attempts}")
        
        # 6. Prepare Context for Collective Intelligence
        pending_fix_context = _build_pending_fix_context(state, result, fix_attempts)
        
        return {
            "fix_attempts": fix_attempts,
            "phase": "orchestrator",
            "pending_fix_context": pending_fix_context,
            "fix_request": None, # Clear request
            "validation_status": ValidationStatus.PENDING, # Reset validation status to force re-validation
            "agent_status": {"status": "fixed", "attempt": fix_attempts},
            "stream_events": result.get("stream_events", [])
        }
        
    except Exception as e:
        logger.error(f"[FIXER] ❌ Fixer failed: {e}")
        # CRITICAL: Must return fix_attempts to track loop iterations
        return {
            "phase": "orchestrator",
            "fix_attempts": fix_attempts,  # Increment counter even on failure
            "messages": [AIMessage(content=f"Fixer Error: {e}")],
            "stream_events": []
        }
    finally:
        if active_fix_file:
             lock_manager.release(project_path, active_fix_file, "fixer_node")


def _extract_error_files(report):
    files = []
    seen = set()
    for v in report.get("violations", []):
        f = v.get("file_path") or v.get("file")
        if f and f not in seen:
            files.append(f)
            seen.add(f)
    return files

def _build_pending_fix_context(state, result, fix_attempts):
    try:
        fix_patch = result.get("artifacts", {}).get("fix_patch", {})
        report = state.get("artifacts", {}).get("validation_report", {})
        return {
            "error_message": report.get("fixer_instructions", "")[:500],
            "solution_code": fix_patch.get("summary", ""),
            "description": result.get("summary", f"Fix attempt {fix_attempts}"),
            "diff": fix_patch.get("unified_diff", ""),
            "before_errors": [str(v.get("message", "")) for v in report.get("violations", [])][:10],
        }
    except: return {}



async def orchestrator_node(state: AgentGraphState) -> Dict[str, Any]:
    """
    MASTER ORCHESTRATOR NODE - Production-Grade Routing with Intent Analysis
    
    Responsibilities:
    1. INTENT ANALYSIS: Run mini-agent to classify what user wants.
    2. ROUTING: Decide which agent should run next.
    3. QUALITY GATING: Check if previous step met criteria.
    4. LOOP DETECTION: Prevent infinite loops.
    """
    logger.info("[ORCHESTRATOR] 🧠 Starting orchestrator node...")
    
    phase = state.get("phase", "planning")
    messages = state.get("messages", [])
    artifacts = state.get("artifacts", {})
    
    logger.info(f"[ORCHESTRATOR] Current phase: {phase}")
    
    # Get latest user request
    user_request = ""
    for m in reversed(messages):
        if isinstance(m, HumanMessage):
            user_request = m.content
            break
            
    # ========================================================================
    # STEP 1: INTENT CLASSIFICATION (The "Mini Agent")
    # ========================================================================
    # We run this if we have a NEW request (e.g. at start of run) or if "structured_intent" is missing
    structured_intent = artifacts.get("structured_intent")
    
    # If we are in 'chat_setup' or don't have intent yet, run classification
    if (not structured_intent or phase == "chat_setup") and user_request:
        try:
            from app.agents.mini_agents.intent_classifier import IntentClassifier
            from langchain_core.callbacks import Callbacks
            
            logger.info(f"[ORCHESTRATOR] 🕵️ Running Intent Classifier on: {user_request[:50]}...")
            
            # Initialize with NO artifact manager to prevent extraneous logging if needed
            # But crucial part is how we invoke it. The classifier uses self.llm.
            # We need to ensure the LLM inside it doesn't stream to the main graph's handler.
            intent_agent = IntentClassifier()
            
            # Use current project context if known
            folder_map = artifacts.get("folder_map")
            
            # We can't easily pass run_manager/callbacks to .classify() unless we modify it.
            # However, IntentClassifier.classify() does:
            # response = await self.llm.ainvoke(messages)
            # If self.llm was created without callbacks, it should be fine.
            # BUT if the graph has global callbacks, they might attach.
            # Let's ensure we use a non-streaming invocation if possible, or modify IntentClassifier to accept callbacks=[]
            
            structured_intent_obj = await intent_agent.classify(
                user_request=user_request,
                folder_map=folder_map
            )
            
            structured_intent = structured_intent_obj.model_dump()
            
            # SAVE INTENT TO ARTIFACTS
            artifacts["structured_intent"] = structured_intent
            state["artifacts"] = artifacts # Update local ref
            
            logger.info(f"[ORCHESTRATOR] ✅ Intent Classified: {structured_intent.get('scope')} / {structured_intent.get('task_type')}")
            
            # CRITICAL: If scope is 'feature' or 'fix', ensure we mark scaffolding as complete/skipped
            # This prevents the Router/Planner from trying to scaffold a new app
            if structured_intent.get("scope") in ["feature", "component", "file", "layer"]:
                if not artifacts.get("scaffolding_complete"):
                     logger.info("[ORCHESTRATOR] 🩹 Auto-marking scaffolding as skipped for Feature/Fix request")
                     artifacts["scaffolding_complete"] = True
                     artifacts["scaffolding_skipped"] = True
                     artifacts["scaffolding_reason"] = f"Intent scope is {structured_intent.get('scope')}"
            
        except Exception as e:
            logger.error(f"[ORCHESTRATOR] ⚠️ Intent classification failed: {e}")
            # Fallback intent
            structured_intent = {"scope": "feature", "task_type": "feature", "description": user_request}

    # ================================================================
    # STEP 2: INITIALIZE DETERMINISTIC ROUTER
    # ================================================================
    router = DeterministicRouter()
    
    # ================================================================
    # STEP 3: INITIALIZE LOOP DETECTION
    # ================================================================
    loop_detection = state.get("loop_detection", {
        "last_node": None,
        "consecutive_calls": 0,
        "loop_detected": False,
        "loop_message": "",
        "wait_attempts": 0
    })
    
    # ================================================================
    # STEP 4: GET ROUTING DECISION (DETERMINISTIC OR LLM)
    # ================================================================
    routing_decision = router.route(state)
    
    logger.info(f"[ORCHESTRATOR] Routing decision: {routing_decision.next_phase} (LLM required: {routing_decision.requires_llm})")
    
    logger.info(f"[ORCHESTRATOR] Routing decision: {routing_decision.next_phase} (LLM required: {routing_decision.requires_llm})")
    
    # Check for immediate hard loops returned by router
    if "loop_warning" in routing_decision.metadata:
        logger.warning(f"[ORCHESTRATOR] ⚠️ Router Warned: {routing_decision.metadata['loop_warning']}")
    logger.info(f"[ORCHESTRATOR] Reason: {routing_decision.reason}")
    
    # ================================================================
    # STEP 5: LLM FALLBACK FOR AMBIGUOUS STATES
    # ================================================================
    # LLM Fallback - Use the Master Orchestrator for ambiguous states
    if routing_decision.requires_llm:
        logger.info("[ORCHESTRATOR] 🤖 Ambiguity detected - Calling Master Orchestrator LLM...")
        
        try:
             # Create LLM Orchestrator (The "LLM we already have")
             orchestrator = AgentFactory.create_orchestrator()
             
             # Enrich context for the LLM
             system_msg = f"""You are the Master Orchestrator Fallback. 
             The deterministic router stopped because: {routing_decision.reason}
             Analyze the state and decide the next step (planner, coder, validator, fixer, chat, complete).
             Return JSON: {{"decision": "next_agent_name", "reasoning": "..."}}"""
             
             messages_with_context = [
                 HumanMessage(content=system_msg + f"\n\nCurrent Phase: {phase}\nLast Message: {messages[-1].content if messages else 'None'}")
             ]
             
             # Invoke LLM
             result = await orchestrator.ainvoke({"messages": messages_with_context})
             response_content = result["messages"][-1].content
             
             # Simple Parsing
             import json, re
             json_match = re.search(r'\{[\s\S]*\}', str(response_content))
             if json_match:
                 parsed = json.loads(json_match.group())
                 llm_decision = parsed.get("decision", "chat").lower()
                 if "planner" in llm_decision: routing_decision.next_phase = "planner"
                 elif "coder" in llm_decision: routing_decision.next_phase = "coder"
                 elif "validator" in llm_decision: routing_decision.next_phase = "validator"
                 elif "fixer" in llm_decision: routing_decision.next_phase = "fixer"
                 elif "finish" in llm_decision: routing_decision.next_phase = "complete"
                 else: routing_decision.next_phase = "chat"
                 
                 routing_decision.reason = f"LLM Override: {parsed.get('reasoning', 'No reasoning')}"
                 logger.info(f"[ORCHESTRATOR] 🤖 LLM Decided: {routing_decision.next_phase}")
             else:
                 logger.warning("[ORCHESTRATOR] ⚠️ LLM returned invalid JSON, escalating to chat.")
                 routing_decision.next_phase = "chat"
                 
        except Exception as e:
            logger.error(f"[ORCHESTRATOR] ❌ LLM Fallback Failed: {e}")
            routing_decision.next_phase = "chat" # Ultimate safety net
    
    # ================================================================
    # STEP 6: UPDATE LOOP DETECTION
    # ================================================================
    # Use router-calculated loop info if available (Single Source of Truth)
    if "loop_detection" in routing_decision.metadata:
        loop_detection = routing_decision.metadata["loop_detection"]
    
    # Fallback: Manual calculation (only for LLM decisions that bypass router logic)
    elif routing_decision.next_phase == loop_detection.get("last_node"):
        loop_detection["consecutive_calls"] = loop_detection.get("consecutive_calls", 0) + 1
    else:
        loop_detection = {
            "last_node": routing_decision.next_phase,
            "consecutive_calls": 1,
            "loop_detected": False,
            "loop_message": "",
            "wait_attempts": loop_detection.get("wait_attempts", 0)  # Preserve wait counter
        }
    
    # ================================================================
    # STEP 7: STEP TRACKING
    # ================================================================
    try:
        from app.services.step_tracking import record_step
        import asyncio
        asyncio.create_task(record_step(
            agent="orchestrator",
            phase=state.get("phase", "unknown"),
            action=f"route_to_{routing_decision.next_phase}",
            content={
                "decision": routing_decision.next_phase,
                "reason": routing_decision.reason,
                "used_llm": routing_decision.requires_llm,
                "gate_passed": routing_decision.gate_result.passed if routing_decision.gate_result else None,
                "loop_detected": loop_detection.get("loop_detected", False),
                "intent": structured_intent.get("task_type") if structured_intent else "uknown"
            },
        ))
    except Exception:
        pass  # Non-fatal
    
    # ================================================================
    # STEP 8: RETURN ROUTING DECISION
    # ================================================================
    return {
        "phase": routing_decision.next_phase,
        "loop_detection": loop_detection,
        "current_step": state.get("current_step", 0) + 1,
        "stream_events": [],
        "artifacts": artifacts, # Return updated artifacts with intent
        "routing_metadata": {
            "reason": routing_decision.reason,
            "used_llm": routing_decision.requires_llm,
            "gate_result": routing_decision.gate_result.gate_name if routing_decision.gate_result else None
        }
    }


# LLM Orchestrator Fallback removed (Logic moved to DeterministicRouter escalation rules)





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
            "result": {"success": True, "preview_url": None},
            "stream_events": []
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
        },
        "stream_events": [run_complete_event]  # CRITICAL: Stream to frontend!
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
    
    # Chat is now a SUBGRAPH for streaming support
    from app.agents.mini_agents.chatter import Chatter
    chatter = Chatter()
    graph.add_node("chat_setup", chat_setup)  # Setup project root
    graph.add_node("chat", chatter.get_graph())
    graph.add_node("chat_cleanup", chat_cleanup)
    
    graph.add_node("complete", complete_node)
    
    # EDGE WIRING: Hub and Spoke
    # Everyone returns to Orchestrator
    graph.add_edge(START, "orchestrator")
    graph.add_edge("planner", "orchestrator")
    graph.add_edge("coder", "orchestrator")
    graph.add_edge("validator", "orchestrator")
    graph.add_edge("fixer", "orchestrator")
    
    # Chat Flow: Setup -> Chat -> Cleanup -> END
    graph.add_edge("chat_setup", "chat")
    graph.add_edge("chat", "chat_cleanup")
    graph.add_edge("chat_cleanup", END)
    
    # ORCHESTRATOR ROUTING (Production-Grade Deterministic)
    def route_orchestrator(state: AgentGraphState):
        """
        Hub-and-spoke routing from orchestrator to next agent.
        
        The orchestrator_node sets the "phase" value, this function
        reads it and routes to the appropriate node.
        
        Deterministic routing is handled in orchestrator_node via
        DeterministicRouter (95% of cases).
        
        LLM fallback is used only for ambiguous states (5% of cases).
        """
        decision = state.get("phase")
        
        logger.info(f"[GRAPH_ROUTER] Routing decision: {decision}")
        
        # Handle waiting state - retry same agent
        if decision == "waiting":
            # Get last agent from loop detection
            last_phase = state.get("loop_detection", {}).get("last_node", "coder")
            logger.info(f"[GRAPH_ROUTER] Waiting state detected, retrying {last_phase}")
            return last_phase if last_phase in ["coder", "fixer"] else "coder"
        
        # Route chat to chat_setup first
        if decision == "chat":
            return "chat_setup"
        
        # Valid phases
        if decision in ["planner", "coder", "validator", "fixer", "complete"]:
            return decision
        
        # Default: complete if unrecognized
        logger.warning(f"[ROUTER] Unrecognized phase '{decision}', routing to complete")
        return "complete"
        
    graph.add_conditional_edges(
        "orchestrator",
        route_orchestrator,
        {
            "planner": "planner",
            "coder": "coder",
            "validator": "validator",
            "fixer": "fixer",
            "chat_setup": "chat_setup",  # Route to chat_setup first
            "chat": "chat",              # Fallback direct to chat
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
        "validation_status": ValidationStatus.PENDING,
        "fix_attempts": 0,
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



