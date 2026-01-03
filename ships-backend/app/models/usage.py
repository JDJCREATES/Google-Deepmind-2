"""
Usage tracking model - Records all user activity for quota enforcement.

Logs every user action (prompts, generations, previews) with token
consumption for accurate rate limiting and analytics.
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
import uuid

from app.database.base import Base


class UsageLog(Base):
    """
    Usage log for tracking user activity and token consumption.
    
    Attributes:
        id: Unique log entry identifier (UUID)
        user_id: Foreign key to user
        project_id: Optional foreign key to project
        event_type: Type of event (prompt, file_edit, preview, build)
        tokens_consumed: Number of tokens used
        model_used: AI model used (gemini-pro, gpt-4, etc.)
        metadata: Additional event data (JSONB)
        created_at: Event timestamp
    """
    
    __tablename__ = "usage_logs"
    
    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    
    # Foreign keys
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="SET NULL")
    )
    
    # Event details
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    tokens_consumed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    model_used: Mapped[Optional[str]] = mapped_column(String(50))
    
    # Additional metadata
    metadata: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    
    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True
    )
    
    # Relationships
    user = relationship("User", back_populates="usage_logs")
    project = relationship("Project", back_populates="usage_logs")
    
    # Indexes for common queries
    __table_args__ = (
        Index('idx_user_usage_date', 'user_id', 'created_at'),
        Index('idx_user_event_type', 'user_id', 'event_type'),
    )
    
    def __repr__(self) -> str:
        return f"<UsageLog(id={self.id}, user_id={self.user_id}, event={self.event_type})>"
