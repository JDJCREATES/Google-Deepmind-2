"""
LangGraph Agent State

Enhanced state for the ShipS* agent workflow with:
- Artifact passthrough (folder_map, api_contracts, task_list)
- Thought signature propagation for Gemini 3
- Project metadata for dynamic prompt selection
"""

from typing import TypedDict, List, Dict, Any, Optional, Annotated
import operator


class AgentState(TypedDict):
    """
    Shared state for the LangGraph agent workflow.
    
    Optimized for Gemini 3 with thought signature propagation
    and artifact passthrough between agents.
    """
    # Core conversation
    messages: List[Dict[str, Any]]          # Chat history
    current_task: Optional[str]             # Current task description
    error: Optional[str]                    # Current error being fixed
    
    # Artifact Passthrough (avoids disk I/O between agents)
    folder_map: Optional[Dict[str, Any]]    # Folder structure from Planner
    api_contracts: Optional[Dict[str, Any]] # API definitions from Planner
    task_list: Optional[List[Dict]]         # Tasks from Planner
    plan: Optional[Dict[str, Any]]          # Full implementation plan
    files: Optional[Dict[str, str]]         # File contents (path -> content)
    
    # Validation
    validation_results: Optional[Dict[str, Any]]  # Results from Validator
    diagnostics: Optional[List[Dict[str, Any]]]   # Errors/warnings
    
    # Project Metadata (for dynamic prompts)
    project_type: Optional[str]             # web_app, api, cli, etc.
    project_path: Optional[str]             # Absolute path to project
    detected_stack: Optional[Dict[str, Any]] # Detected frameworks/languages
    
    # Gemini 3 Thought Signatures
    # Encrypted reasoning context - MUST be passed back for multi-turn
    thought_signatures: Dict[str, str]      # agent_name -> signature
    
    # Agent Coordination
    agent_scratchpad: Dict[str, Any]        # Shared scratchpad
    pending_files: Optional[List[Dict]]     # Files queued for writing
    completed_files: Optional[List[str]]    # Files successfully written
    
    # Metadata
    session_id: Optional[str]               # For checkpointing
    recursion_depth: int
    max_recursion_depth: int


def create_initial_state(
    user_message: str,
    project_path: Optional[str] = None,
    project_type: str = "generic",
    session_id: Optional[str] = None
) -> AgentState:
    """
    Create initial state for a new workflow.
    
    Args:
        user_message: The user's request
        project_path: Optional project directory
        project_type: Detected or specified project type
        session_id: Unique session ID for checkpointing
        
    Returns:
        Initialized AgentState
    """
    import uuid
    
    return AgentState(
        messages=[{"role": "user", "content": user_message}],
        current_task=None,
        error=None,
        
        # Artifacts (populated by Planner)
        folder_map=None,
        api_contracts=None,
        task_list=None,
        plan=None,
        files={},
        
        # Validation
        validation_results=None,
        diagnostics=None,
        
        # Project metadata
        project_type=project_type,
        project_path=project_path,
        detected_stack=None,
        
        # Gemini 3 thought signatures
        thought_signatures={},
        
        # Coordination
        agent_scratchpad={},
        pending_files=None,
        completed_files=[],
        
        # Metadata
        session_id=session_id or str(uuid.uuid4()),
        recursion_depth=0,
        max_recursion_depth=10,
    )


def merge_state_update(state: AgentState, update: Dict[str, Any]) -> AgentState:
    """
    Merge a partial update into existing state.
    
    Handles special merging for:
    - messages: append
    - files: merge dict
    - thought_signatures: merge dict
    - completed_files: extend list
    """
    new_state = dict(state)
    
    for key, value in update.items():
        if key == "messages" and value:
            # Append new messages
            new_state["messages"] = list(state.get("messages", [])) + value
        elif key == "files" and value:
            # Merge file contents
            existing = dict(state.get("files", {}) or {})
            existing.update(value)
            new_state["files"] = existing
        elif key == "thought_signatures" and value:
            # Merge thought signatures
            existing = dict(state.get("thought_signatures", {}) or {})
            existing.update(value)
            new_state["thought_signatures"] = existing
        elif key == "completed_files" and value:
            # Extend completed files
            existing = list(state.get("completed_files", []) or [])
            existing.extend(value)
            new_state["completed_files"] = existing
        elif key == "diagnostics" and value:
            # Extend diagnostics
            existing = list(state.get("diagnostics", []) or [])
            existing.extend(value)
            new_state["diagnostics"] = existing
        else:
            new_state[key] = value
    
    return AgentState(**new_state)
