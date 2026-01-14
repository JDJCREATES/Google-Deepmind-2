"""
Context Scoping Service for Multi-Agent Token Optimization

Provides agent-specific context extraction from the full AgentGraphState.
Each agent receives ONLY what it needs, preventing token bloat.

This is the centralized location for context management - adding a new agent
only requires adding a new handler here.
"""

from typing import Any, Dict, Optional
import logging

logger = logging.getLogger("ships.context")


def scope_context_for_agent(state: Dict[str, Any], agent_type: str) -> Dict[str, Any]:
    """
    Extract minimal context for a specific agent.
    
    This function is the single source of truth for what context each agent receives.
    It prevents token bloat by excluding unnecessary state (e.g., full message history).
    
    Args:
        state: Full AgentGraphState
        agent_type: One of "orchestrator", "planner", "coder", "fixer", "validator", "chat"
        
    Returns:
        Dict with only the fields that agent needs
    """
    artifacts = state.get("artifacts", {})
    
    # Always include these minimal fields
    base_context = {
        "project_path": artifacts.get("project_path"),
        "phase": state.get("phase"),
    }
    
    if agent_type == "coder":
        return _scope_for_coder(state, artifacts, base_context)
    elif agent_type == "fixer":
        return _scope_for_fixer(state, artifacts, base_context)
    elif agent_type == "planner":
        return _scope_for_planner(state, artifacts, base_context)
    elif agent_type == "validator":
        return _scope_for_validator(state, artifacts, base_context)
    elif agent_type == "orchestrator":
        return _scope_for_orchestrator(state, artifacts, base_context)
    else:
        # Default: return base context only (safe fallback)
        logger.warning(f"[CONTEXT] Unknown agent type '{agent_type}', using minimal context")
        return base_context


def _scope_for_coder(state: Dict, artifacts: Dict, base: Dict) -> Dict:
    """
    Coder needs:
    - Plan content (truncated)
    - Completed files list
    - Current task
    - Project structure summary
    
    Does NOT need:
    - Full message history
    - Validation reports
    - Error logs (unless fixing)
    """
    plan_content = artifacts.get("plan_content", "")
    
    return {
        **base,
        "artifacts": {
            "project_path": artifacts.get("project_path"),
            "plan_content": _truncate(plan_content, 4000),
            "project_structure": artifacts.get("project_structure", ""),
        },
        "completed_files": state.get("completed_files", []),
        "parameters": state.get("parameters", {}),
        # Exclude: messages, error_log, validation_report
    }


def _scope_for_fixer(state: Dict, artifacts: Dict, base: Dict) -> Dict:
    """
    Fixer needs:
    - Validation report (errors to fix)
    - Recent error log (last 5)
    - Active file being fixed
    
    Does NOT need:
    - Full message history
    - Plan content
    - Completed files from other runs
    """
    return {
        **base,
        "artifacts": {
            "project_path": artifacts.get("project_path"),
            "validation_report": artifacts.get("validation_report", {}),
        },
        "error_log": state.get("error_log", [])[-5:],  # Last 5 errors only
        "fix_attempts": state.get("fix_attempts", 0),
        "parameters": state.get("parameters", {}),
    }


def _scope_for_planner(state: Dict, artifacts: Dict, base: Dict) -> Dict:
    """
    Planner needs:
    - User request (first message)
    - Existing artifacts for context
    
    Does NOT need:
    - Tool call history
    - Validation details
    """
    # Extract user request from messages (first HumanMessage only)
    user_request = ""
    messages = state.get("messages", [])
    for msg in messages:
        if hasattr(msg, 'content') and msg.__class__.__name__ in ['HumanMessage', 'HumanMessageChunk']:
            user_request = str(msg.content).strip()
            break
    
    return {
        **base,
        "user_request": user_request,
        "artifacts": {
            "project_path": artifacts.get("project_path"),
            "existing_plan": artifacts.get("plan_content", ""),
            "folder_map": artifacts.get("folder_map", {}),
        },
    }


def _scope_for_validator(state: Dict, artifacts: Dict, base: Dict) -> Dict:
    """
    Validator needs:
    - Completed files list
    - Plan for completeness check
    """
    return {
        **base,
        "artifacts": {
            "project_path": artifacts.get("project_path"),
            "plan_content": _truncate(artifacts.get("plan_content", ""), 2000),
        },
        "completed_files": state.get("completed_files", []),
    }


def _scope_for_orchestrator(state: Dict, artifacts: Dict, base: Dict) -> Dict:
    """
    Orchestrator needs:
    - Current phase
    - Key status indicators
    - Intent classification
    
    Does NOT need:
    - Full artifacts content
    - Message history
    """
    return {
        **base,
        "validation_passed": state.get("validation_passed", False),
        "fix_attempts": state.get("fix_attempts", 0),
        "completed_files_count": len(state.get("completed_files", [])),
        "error_count": len(state.get("error_log", [])),
        "artifacts": {
            "structured_intent": artifacts.get("structured_intent"),
            "has_plan": bool(artifacts.get("plan_content")),
            "project_path": artifacts.get("project_path"),
        },
    }


def _truncate(text: str, max_chars: int) -> str:
    """Truncate text to max characters with indicator."""
    if not text or len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n... [truncated]"


def estimate_context_tokens(context: Dict[str, Any]) -> int:
    """
    Rough estimation of token count for a context dict.
    Uses ~4 chars per token approximation.
    """
    import json
    try:
        json_str = json.dumps(context, default=str)
        return len(json_str) // 4
    except Exception:
        return 0
