"""
User model - Core user entity with subscription and usage tracking.

Represents authenticated users with Google OAuth integration,
subscription tier management, and usage quota tracking.
"""

from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy import String, Integer, DateTime, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
import uuid

from app.database.base import Base


# Tier limits configuration
TIER_LIMITS = {
    'free': {
        'prompts_per_day': 5,
        'max_projects': 1,
        'tokens_per_month': 25_000,
        'priority_queue': False,
    },
    'starter': {
        'prompts_per_day': 100,
        'max_projects': 3,
        'tokens_per_month': 500_000,
        'priority_queue': False,
    },
    'pro': {
        'prompts_per_day': 500,
        'max_projects': 10,
        'tokens_per_month': 2_000_000,
        'priority_queue': True,
    },
    'enterprise': {
        'prompts_per_day': -1,  # Unlimited
        'max_projects': -1,
        'tokens_per_month': 10_000_000,
        'priority_queue': True,
    }
}


class User(Base):
    """
    User model with subscription and usage tracking.
    
    Attributes:
        id: Unique user identifier (UUID)
        email: User email address (unique, from Google OAuth)
        name: Display name
        google_id: Google OAuth user ID
        avatar_url: Profile picture URL
        tier: Subscription tier (free, starter, pro, enterprise)
        subscription_status: Current status (active, canceled, past_due, inactive)
        stripe_customer_id: Stripe customer ID
        stripe_subscription_id: Active Stripe subscription ID
        current_period_start: Current billing period start
        current_period_end: Current billing period end
        prompts_used_today: Number of prompts used today
        tokens_used_month: Number of tokens used this month
    """
    
    __tablename__ = "users"
    
    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    
    # Authentication
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    google_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(512))
    
    # Subscription
    tier: Mapped[str] = mapped_column(String(50), default='free', nullable=False)
    subscription_status: Mapped[str] = mapped_column(String(50), default='inactive', nullable=False)
    stripe_customer_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True)
    stripe_subscription_id: Mapped[Optional[str]] = mapped_column(String(255))
    
    # Billing period
    current_period_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    current_period_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Usage tracking
    prompts_used_today: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tokens_used_month: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
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
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Relationships
    projects = relationship("Project", back_populates="user", cascade="all, delete-orphan")
    usage_logs = relationship("UsageLog", back_populates="user", cascade="all, delete-orphan")
    
    def get_tier_limits(self) -> dict:
        """
        Get usage limits for user's current tier.
        
        Returns:
            dict: Tier limits configuration
        """
        return TIER_LIMITS.get(self.tier, TIER_LIMITS['free'])
    
    def can_use_prompts(self, count: int = 1) -> bool:
        """
        Check if user can use specified number of prompts.
        
        Args:
            count: Number of prompts to check
            
        Returns:
            bool: True if user has quota available
        """
        limits = self.get_tier_limits()
        daily_limit = limits['prompts_per_day']
        
        # Unlimited tier
        if daily_limit == -1:
            return True
        
        return self.prompts_used_today + count <= daily_limit
    
    def can_use_tokens(self, count: int) -> bool:
        """
        Check if user can use specified number of tokens.
        
        Args:
            count: Number of tokens to check
            
        Returns:
            bool: True if user has quota available
        """
        limits = self.get_tier_limits()
        monthly_limit = limits['tokens_per_month']
        
        return self.tokens_used_month + count <= monthly_limit
    
    def can_create_project(self) -> bool:
        """
        Check if user can create a new project.
        
        Returns:
            bool: True if user hasn't reached project limit
        """
        limits = self.get_tier_limits()
        max_projects = limits['max_projects']
        
        # Unlimited tier
        if max_projects == -1:
            return True
        
        # Count relationship uses len() which loads all - use COUNT query in production
        return len(self.projects) < max_projects
    
    def reset_daily_usage(self):
        """Reset daily usage counters."""
        self.prompts_used_today = 0
    
    def reset_monthly_usage(self):
        """Reset monthly usage counters."""
        self.tokens_used_month = 0
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email}, tier={self.tier})>"
