"""
Agent Run and Step Models - Track agent pipeline executions.

Stores:
- AgentRun: A single agent pipeline execution (user request → completion)
- AgentStep: Individual reasoning steps within a run

User isolation: All queries must filter by user_id.
"""

from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Integer, DateTime, Text, Index, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
import uuid

from app.database.base import Base


class AgentRun(Base):
    """
    Represents a single agent pipeline execution.
    
    Created when user sends a prompt, completed when pipeline finishes.
    Supports branching via parent_run_id for alternative exploration.
    
    Attributes:
        id: Unique run identifier (UUID)
        user_id: Owner of this run (for isolation)
        project_path: Filesystem path to the project
        branch_name: Git branch name (ships/run/{id})
        parent_run_id: If branched, the parent run
        user_request: The original user prompt
        status: Current status (pending, running, complete, error, cancelled)
        current_step: Latest step number
        error_message: Error details if status is 'error'
    """
    
    __tablename__ = "agent_runs"
    
    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    
    # User isolation - CRITICAL for security
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Project context
    project_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    branch_name: Mapped[Optional[str]] = mapped_column(String(255))
    
    # Branching support
    parent_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_runs.id", ondelete="SET NULL"),
        index=True
    )
    parent_step: Mapped[Optional[int]] = mapped_column(Integer)  # Step branched from
    
    # Request details
    user_request: Mapped[Optional[str]] = mapped_column(Text)
    
    # Status tracking
    status: Mapped[str] = mapped_column(
        String(50), 
        default="pending",
        nullable=False
    )  # pending, running, complete, error, cancelled
    
    current_step: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    # Error handling
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    
    # Metadata
    run_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Relationships
    user = relationship("User", back_populates="agent_runs")
    steps = relationship(
        "AgentStep", 
        back_populates="run", 
        cascade="all, delete-orphan",
        order_by="AgentStep.step_number"
    )
    child_runs = relationship(
        "AgentRun",
        back_populates="parent_run",
        foreign_keys="AgentRun.parent_run_id"
    )
    parent_run = relationship(
        "AgentRun",
        back_populates="child_runs",
        remote_side=[id]
    )
    
    # Indexes for common queries
    __table_args__ = (
        Index("ix_agent_runs_user_status", "user_id", "status"),
        Index("ix_agent_runs_user_created", "user_id", "created_at"),
    )
    
    def mark_running(self) -> None:
        """Mark run as actively executing."""
        self.status = "running"
    
    def mark_complete(self) -> None:
        """Mark run as successfully completed."""
        self.status = "complete"
        self.completed_at = datetime.utcnow()
    
    def mark_error(self, error_message: str) -> None:
        """Mark run as failed with error details."""
        self.status = "error"
        self.error_message = error_message
        self.completed_at = datetime.utcnow()
    
    def increment_step(self) -> int:
        """Increment and return the new step number."""
        self.current_step += 1
        return self.current_step
    
    def __repr__(self) -> str:
        return f"<AgentRun(id={self.id}, status={self.status}, steps={self.current_step})>"


class AgentStep(Base):
    """
    Represents a single reasoning step within an agent run.
    
    Each LangGraph node invocation creates a step. This provides
    the detailed audit trail that the LLM can reference (like
    Antigravity's 7000+ steps).
    
    Attributes:
        id: Unique step identifier
        run_id: Parent run
        step_number: Sequential number within the run
        agent: Which agent executed (orchestrator, planner, coder, etc.)
        phase: Current phase (planning, coding, validating, fixing)
        action: What action was taken (tool call, decision, etc.)
        content: Detailed content (reasoning, tool results, etc.)
        tokens_used: Token count for this step (for billing)
    """
    
    __tablename__ = "agent_steps"
    
    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    
    # Parent run
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Step identification
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Agent context
    agent: Mapped[str] = mapped_column(String(50), nullable=False)  # orchestrator, planner, coder, validator, fixer
    phase: Mapped[Optional[str]] = mapped_column(String(50))  # planning, coding, validating, fixing
    action: Mapped[Optional[str]] = mapped_column(String(100))  # tool_call, decision, completion
    
    # Content (LLM reasoning, tool results, etc.)
    content: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    
    # Billing
    tokens_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    
    # Relationship
    run = relationship("AgentRun", back_populates="steps")
    
    # Indexes
    __table_args__ = (
        Index("ix_agent_steps_run_number", "run_id", "step_number"),
    )
    
    def __repr__(self) -> str:
        return f"<AgentStep(run={self.run_id}, step={self.step_number}, agent={self.agent})>"
