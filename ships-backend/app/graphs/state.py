from typing import TypedDict, List, Dict, Any, Optional, Annotated
import operator

class AgentState(TypedDict):
    """
    Shared state for the LangGraph agent workflow.
    """
    messages: List[Dict[str, Any]]  # Chat history
    current_task: Optional[str]     # Description of the current task
    plan: Optional[Dict[str, Any]]  # The implementation plan from Planner
    files: Optional[Dict[str, str]] # Content of relevant files
    validation_results: Optional[Dict[str, Any]] # Results from validators
    error: Optional[str]            # Current error being fixed (if any)
    agent_scratchpad: Dict[str, Any] # Shared scratchpad for intermediate data
    
    # Metadata
    recursion_depth: int
    max_recursion_depth: int
