"""
Knowledge entry model for Collective Intelligence system.

Stores successful fixes, patterns, and solutions for retrieval.
Uses pgvector for semantic similarity search.
"""

from datetime import datetime
from typing import Optional
import uuid
import zlib

from sqlalchemy import String, Integer, Float, LargeBinary, Text, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector

from app.database.base import Base
from app.services.embeddings import get_embedding_dimensions


class KnowledgeEntry(Base):
    """
    Knowledge entry for storing successful fixes and patterns.
    
    Attributes:
        id: Unique entry identifier
        entry_type: Type of knowledge (error_fix, pattern, integration)
        error_signature: Normalized error message for deduplication
        tech_stack: Compact tech stack identifier
        context_embedding: Vector for semantic search
        solution_pattern: Abstracted solution pattern
        solution_compressed: Full solution code, compressed
        success_count: Times this solution worked
        failure_count: Times this solution was tried but failed
        confidence: Calculated confidence score
        visibility: Sharing scope (private, team, community)
        user_id: Creator of this entry
    """
    
    __tablename__ = "knowledge_entries"
    
    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    
    # Entry type
    entry_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True
    )
    
    # Context (what problem)
    error_signature: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        index=True
    )
    tech_stack: Mapped[Optional[str]] = mapped_column(
        String(100),
        index=True
    )
    context_embedding: Mapped[Optional[list]] = mapped_column(
        Vector(768),  # Gemini dimensions
        nullable=True
    )
    
    # Solution (what fixed it)
    solution_pattern: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )
    solution_description: Mapped[Optional[str]] = mapped_column(
        Text
    )
    solution_compressed: Mapped[Optional[bytes]] = mapped_column(
        LargeBinary
    )
    
    # Metrics
    success_count: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False
    )
    failure_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )
    confidence: Mapped[float] = mapped_column(
        Float,
        default=0.7,
        nullable=False
    )
    
    # Privacy
    visibility: Mapped[str] = mapped_column(
        String(20),
        default="private",
        nullable=False
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL")
    )
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        default=func.now(),
        nullable=False
    )
    last_used_at: Mapped[datetime] = mapped_column(
        default=func.now(),
        nullable=False
    )
    
    # Relationships
    user = relationship("User", backref="knowledge_entries")
    
    # Indexes
    __table_args__ = (
        Index('idx_ke_confidence_desc', confidence.desc()),
        Index('idx_ke_visibility', visibility),
    )
    
    def __repr__(self) -> str:
        return f"<KnowledgeEntry(id={self.id}, type={self.entry_type}, confidence={self.confidence:.2f})>"
    
    # Helper methods
    
    def compress_solution(self, code: str) -> None:
        """Compress and store full solution code."""
        self.solution_compressed = zlib.compress(code.encode('utf-8'))
    
    def decompress_solution(self) -> Optional[str]:
        """Decompress stored solution code."""
        if self.solution_compressed:
            return zlib.decompress(self.solution_compressed).decode('utf-8')
        return None
    
    def recalculate_confidence(self) -> float:
        """Recalculate confidence based on success/failure ratio."""
        total = self.success_count + self.failure_count
        if total == 0:
            return 0.5
        
        base_confidence = self.success_count / total
        
        # Boost for high volume
        volume_boost = min(total / 100, 0.1)  # Cap at 0.1 boost
        
        self.confidence = min(base_confidence + volume_boost, 1.0)
        return self.confidence
    
    def increment_success(self) -> None:
        """Record successful use of this knowledge."""
        self.success_count += 1
        self.last_used_at = datetime.utcnow()
        self.recalculate_confidence()
    
    def increment_failure(self) -> None:
        """Record failed use of this knowledge."""
        self.failure_count += 1
        self.recalculate_confidence()
