"""
Project model - User-owned projects with metadata.

Represents individual coding projects managed by ShipS.
Each project belongs to one user and tracks local path,
framework, language, and custom settings.
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import String, Text, ForeignKey, UniqueConstraint, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
import uuid

from app.database.base import Base


class Project(Base):
    """
    Project model representing user's coding projects.
    
    Attributes:
        id: Unique project identifier (UUID)
        user_id: Foreign key to owning user
        name: Project display name
        description: Optional project description
        local_path: Absolute path to project on user's machine
        framework: Detected framework (react, vue, next, etc.)
        language: Primary language (typescript, python, etc.)
        settings: Custom project settings (JSONB)
        created_at: Project creation timestamp
        updated_at: Last modification timestamp
        last_opened_at: Last time project was opened
    """
    
    __tablename__ = "projects"
    
    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    
    # Foreign key to user
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Project details
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    local_path: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Project metadata
    framework: Mapped[Optional[str]] = mapped_column(String(50))
    language: Mapped[Optional[str]] = mapped_column(String(50))
    settings: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
    last_opened_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Relationships
    user = relationship("User", back_populates="projects")
    usage_logs = relationship("UsageLog", back_populates="project")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('user_id', 'local_path', name='uq_user_project_path'),
    )
    
    def update_last_opened(self):
        """Update last_opened_at to current time."""
        self.last_opened_at = datetime.utcnow()
    
    def __repr__(self) -> str:
        return f"<Project(id={self.id}, name={self.name}, user_id={self.user_id})>"
