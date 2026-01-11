"""
Step Tracking Integration for Agent Pipeline

Provides a synchronous interface to the AgentRunService for use
within LangGraph nodes. Creates runs at pipeline start and records
steps for each node invocation.

This is a bridge between the async service layer and the graph nodes.
"""

import logging
import asyncio
from typing import Optional, Dict, Any
from uuid import UUID, uuid4
from contextlib import contextmanager

logger = logging.getLogger("ships.step_tracking")

# Global tracking state (per-thread safe with asyncio)
_current_run_id: Optional[UUID] = None
_current_user_id: Optional[UUID] = None
_current_project_path: Optional[str] = None
_tracking_enabled: bool = True


def set_tracking_enabled(enabled: bool) -> None:
    """Enable or disable step tracking globally."""
    global _tracking_enabled
    _tracking_enabled = enabled


def is_tracking_enabled() -> bool:
    """Check if step tracking is enabled."""
    return _tracking_enabled


async def start_run(
    user_id: UUID,
    project_path: str,
    user_request: str,
    parent_run_id: Optional[UUID] = None,
    parent_step: Optional[int] = None
) -> Optional[UUID]:
    """
    Start a new agent run.
    
    Call this at the beginning of stream_pipeline.
    
    Args:
        user_id: Current user's ID
        project_path: Project being worked on
        user_request: The user's prompt
        parent_run_id: For branching from existing run
        parent_step: Step to branch from
        
    Returns:
        Run ID if created, None if tracking disabled or failed
    """
    global _current_run_id, _current_user_id, _current_project_path
    
    if not _tracking_enabled:
        return None
    
    try:
        from app.database.connection import get_session_factory
        from app.services.agent_run_service import AgentRunService
        
        session_factory = get_session_factory()
        async with session_factory() as session:
            service = AgentRunService(session, user_id)
            run = await service.create_run(
                project_path=project_path,
                user_request=user_request,
                parent_run_id=parent_run_id,
                parent_step=parent_step
            )
            await session.commit()
            
            _current_run_id = run.id
            _current_user_id = user_id
            _current_project_path = project_path
            
            logger.info(f"[STEP_TRACKING] Started run {run.id}")
            return run.id
            
    except Exception as e:
        logger.warning(f"[STEP_TRACKING] Failed to start run: {e}")
        return None


async def record_step(
    agent: str,
    phase: Optional[str] = None,
    action: Optional[str] = None,
    content: Optional[Dict[str, Any]] = None,
    tokens_used: int = 0
) -> Optional[int]:
    """
    Record a step in the current run.
    
    Call this at the end of each node function.
    
    Args:
        agent: Name of the agent (orchestrator, planner, coder, etc.)
        phase: Current phase
        action: Action type
        content: Step content (will be truncated if too large)
        tokens_used: Token count
        
    Returns:
        Step number if recorded, None otherwise
    """
    global _current_run_id, _current_user_id
    
    if not _tracking_enabled or not _current_run_id or not _current_user_id:
        return None
    
    try:
        from app.database.connection import get_session_factory
        from app.services.agent_run_service import AgentRunService
        
        # Truncate content to avoid DB bloat
        safe_content = _truncate_content(content) if content else {}
        
        session_factory = get_session_factory()
        async with session_factory() as session:
            service = AgentRunService(session, _current_user_id)
            step = await service.add_step(
                run_id=_current_run_id,
                agent=agent,
                phase=phase,
                action=action,
                content=safe_content,
                tokens_used=tokens_used
            )
            await session.commit()
            
            if step:
                logger.debug(f"[STEP_TRACKING] Recorded step {step.step_number}: {agent}/{action}")
                return step.step_number
            return None
            
    except Exception as e:
        logger.debug(f"[STEP_TRACKING] Failed to record step: {e}")
        return None


async def complete_run(status: str = "complete", error_message: Optional[str] = None) -> bool:
    """
    Mark the current run as complete or errored.
    
    Call this at the end of the pipeline (complete_node or error handling).
    
    Args:
        status: Final status (complete, error, cancelled)
        error_message: Error details if status is 'error'
        
    Returns:
        True if updated, False otherwise
    """
    global _current_run_id, _current_user_id
    
    if not _tracking_enabled or not _current_run_id or not _current_user_id:
        return False
    
    try:
        from app.database.connection import get_session_factory
        from app.services.agent_run_service import AgentRunService
        
        session_factory = get_session_factory()
        async with session_factory() as session:
            service = AgentRunService(session, _current_user_id)
            run = await service.update_run_status(
                run_id=_current_run_id,
                status=status,
                error_message=error_message
            )
            await session.commit()
            
            if run:
                logger.info(f"[STEP_TRACKING] Completed run {_current_run_id}: {status}")
                # Clear global state
                _current_run_id = None
                return True
            return False
            
    except Exception as e:
        logger.warning(f"[STEP_TRACKING] Failed to complete run: {e}")
        return False


def get_current_run_id() -> Optional[UUID]:
    """Get the current run ID if tracking is active."""
    return _current_run_id


def _truncate_content(content: Dict[str, Any], max_size: int = 10000) -> Dict[str, Any]:
    """
    Truncate content to prevent DB bloat.
    
    Keeps important keys, truncates large strings.
    """
    import json
    
    try:
        serialized = json.dumps(content)
        if len(serialized) <= max_size:
            return content
        
        # Truncate large string values
        result = {}
        for key, value in content.items():
            if isinstance(value, str) and len(value) > 1000:
                result[key] = value[:1000] + "...[truncated]"
            elif isinstance(value, (list, dict)):
                # Summarize large collections
                result[key] = f"[{type(value).__name__} with {len(value)} items]"
            else:
                result[key] = value
        
        return result
        
    except Exception:
        return {"error": "Content could not be serialized"}


# =============================================================================
# Sync wrappers for use in non-async contexts
# =============================================================================

def record_step_sync(
    agent: str,
    phase: Optional[str] = None,
    action: Optional[str] = None,
    content: Optional[Dict[str, Any]] = None,
    tokens_used: int = 0
) -> Optional[int]:
    """Synchronous wrapper for record_step."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Can't use run_until_complete in running loop
            # Schedule as task and return None
            asyncio.create_task(record_step(agent, phase, action, content, tokens_used))
            return None
        else:
            return loop.run_until_complete(
                record_step(agent, phase, action, content, tokens_used)
            )
    except Exception:
        return None
