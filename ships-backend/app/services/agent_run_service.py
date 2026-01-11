"""
Agent Run Service - Business logic for managing agent runs.

Provides CRUD operations and business logic for AgentRun and AgentStep,
with user isolation built into every query.
"""

import logging
from datetime import datetime
from typing import Optional, List
from uuid import UUID, uuid4

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.agent_runs import AgentRun, AgentStep

logger = logging.getLogger("ships.agent_runs")


class AgentRunService:
    """
    Service for managing agent pipeline runs.
    
    All operations are scoped to a specific user to ensure isolation.
    """
    
    def __init__(self, db: AsyncSession, user_id: UUID):
        """
        Initialize service with database session and user context.
        
        Args:
            db: Async database session
            user_id: Current user's ID for isolation
        """
        self.db = db
        self.user_id = user_id
    
    # =========================================================================
    # Run Operations
    # =========================================================================
    
    async def create_run(
        self,
        project_path: str,
        user_request: str,
        parent_run_id: Optional[UUID] = None,
        parent_step: Optional[int] = None,
        metadata: Optional[dict] = None
    ) -> AgentRun:
        """
        Create a new agent run.
        
        Args:
            project_path: Filesystem path to project
            user_request: The user's prompt
            parent_run_id: Optional parent for branching
            parent_step: Step number to branch from
            metadata: Additional metadata
            
        Returns:
            Created AgentRun instance
        """
        run_id = uuid4()
        branch_name = f"ships/run/{str(run_id)[:8]}"
        
        run = AgentRun(
            id=run_id,
            user_id=self.user_id,
            project_path=project_path,
            branch_name=branch_name,
            user_request=user_request,
            parent_run_id=parent_run_id,
            parent_step=parent_step,
            status="pending",
            run_metadata=metadata or {}
        )
        
        self.db.add(run)
        await self.db.flush()
        
        logger.info(f"[AGENT_RUN] Created run {run_id} for user {self.user_id}")
        return run
    
    async def get_run(self, run_id: UUID) -> Optional[AgentRun]:
        """
        Get a specific run (user-scoped).
        
        Args:
            run_id: Run to fetch
            
        Returns:
            AgentRun if found and owned by user, None otherwise
        """
        result = await self.db.execute(
            select(AgentRun)
            .where(and_(
                AgentRun.id == run_id,
                AgentRun.user_id == self.user_id
            ))
            .options(selectinload(AgentRun.steps))
        )
        return result.scalar_one_or_none()
    
    async def list_runs(
        self,
        project_path: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50
    ) -> List[AgentRun]:
        """
        List runs for current user.
        
        Args:
            project_path: Filter by project
            status: Filter by status
            limit: Maximum results
            
        Returns:
            List of AgentRun instances
        """
        query = (
            select(AgentRun)
            .where(AgentRun.user_id == self.user_id)
            .order_by(AgentRun.created_at.desc())
            .limit(limit)
        )
        
        if project_path:
            query = query.where(AgentRun.project_path == project_path)
        
        if status:
            query = query.where(AgentRun.status == status)
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def update_run_status(
        self,
        run_id: UUID,
        status: str,
        error_message: Optional[str] = None
    ) -> Optional[AgentRun]:
        """
        Update run status.
        
        Args:
            run_id: Run to update
            status: New status
            error_message: Error details if status is 'error'
            
        Returns:
            Updated run or None if not found
        """
        run = await self.get_run(run_id)
        if not run:
            logger.warning(f"[AGENT_RUN] Run {run_id} not found for user {self.user_id}")
            return None
        
        run.status = status
        
        if status == "complete":
            run.completed_at = datetime.utcnow()
        elif status == "error":
            run.error_message = error_message
            run.completed_at = datetime.utcnow()
        
        await self.db.flush()
        logger.info(f"[AGENT_RUN] Updated run {run_id} status to {status}")
        return run
    
    # =========================================================================
    # Step Operations
    # =========================================================================
    
    async def add_step(
        self,
        run_id: UUID,
        agent: str,
        phase: Optional[str] = None,
        action: Optional[str] = None,
        content: Optional[dict] = None,
        tokens_used: int = 0
    ) -> Optional[AgentStep]:
        """
        Add a step to a run.
        
        Automatically increments step number.
        
        Args:
            run_id: Parent run
            agent: Agent name (orchestrator, planner, etc.)
            phase: Current phase
            action: Action type
            content: Step content/reasoning
            tokens_used: Token count
            
        Returns:
            Created step or None if run not found
        """
        run = await self.get_run(run_id)
        if not run:
            return None
        
        step_number = run.increment_step()
        
        step = AgentStep(
            run_id=run_id,
            step_number=step_number,
            agent=agent,
            phase=phase,
            action=action,
            content=content or {},
            tokens_used=tokens_used
        )
        
        self.db.add(step)
        await self.db.flush()
        
        logger.debug(f"[AGENT_RUN] Added step {step_number} to run {run_id}")
        return step
    
    async def get_steps(
        self,
        run_id: UUID,
        limit: int = 100
    ) -> List[AgentStep]:
        """
        Get steps for a run.
        
        Args:
            run_id: Run to fetch steps for
            limit: Maximum steps to return
            
        Returns:
            List of AgentStep instances
        """
        # Verify user owns the run
        run = await self.get_run(run_id)
        if not run:
            return []
        
        result = await self.db.execute(
            select(AgentStep)
            .where(AgentStep.run_id == run_id)
            .order_by(AgentStep.step_number)
            .limit(limit)
        )
        return list(result.scalars().all())
    
    async def get_latest_step(self, run_id: UUID) -> Optional[AgentStep]:
        """
        Get the most recent step for a run.
        
        Args:
            run_id: Run to fetch from
            
        Returns:
            Latest AgentStep or None
        """
        run = await self.get_run(run_id)
        if not run:
            return None
        
        result = await self.db.execute(
            select(AgentStep)
            .where(AgentStep.run_id == run_id)
            .order_by(AgentStep.step_number.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()


# =============================================================================
# Factory function for dependency injection
# =============================================================================

def get_agent_run_service(db: AsyncSession, user_id: UUID) -> AgentRunService:
    """
    Factory for creating AgentRunService instances.
    
    Usage in FastAPI:
        @router.get("/runs")
        async def list_runs(
            db: AsyncSession = Depends(get_session),
            current_user: User = Depends(get_current_user)
        ):
            service = get_agent_run_service(db, current_user.id)
            return await service.list_runs()
    """
    return AgentRunService(db, user_id)
