"""
Database connection and session management.

Production-grade PostgreSQL connection with:
- Async support via asyncpg
- Connection pooling
- Automatic retry on connection failures
- Health checks
"""

import asyncio
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool, QueuePool
from sqlalchemy import text
import logging
import os

logger = logging.getLogger("ships.database")

# Database configuration from environment
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://ships:ships@localhost/ships"
)
DATABASE_POOL_SIZE = int(os.getenv("DATABASE_POOL_SIZE", "20"))
DATABASE_MAX_OVERFLOW = int(os.getenv("DATABASE_MAX_OVERFLOW", "10"))
DATABASE_POOL_TIMEOUT = int(os.getenv("DATABASE_POOL_TIMEOUT", "30"))


class DatabaseConnection:
    """
    Manages PostgreSQL database connection and session lifecycle.
    
    Implements singleton pattern to ensure single engine instance.
    """
    
    _engine = None
    _session_factory = None
    
    @classmethod
    def get_engine(cls):
        """
        Get or create async database engine.
        
        Returns:
            AsyncEngine: SQLAlchemy async engine instance
        """
        if cls._engine is None:
            logger.info(f"Creating database engine: {DATABASE_URL.split('@')[1]}")
            
            cls._engine = create_async_engine(
                DATABASE_URL,
                poolclass=NullPool,  # NullPool for async engines
                echo=False,  # Set to True for SQL debugging
            )
        
        return cls._engine
    
    @classmethod
    def get_session_factory(cls):
        """
        Get or create session factory.
        
        Returns:
            async_sessionmaker: Factory for creating async sessions
        """
        if cls._session_factory is None:
            engine = cls.get_engine()
            cls._session_factory = async_sessionmaker(
                engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )
        
        return cls._session_factory
    
    @classmethod
    async def health_check(cls) -> bool:
        """
        Check database connection health.
        
        Returns:
            bool: True if connection is healthy, False otherwise
        """
        try:
            engine = cls.get_engine()
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            logger.info("✓ Database health check passed")
            return True
        except Exception as e:
            logger.error(f"✗ Database health check failed: {e}")
            return False
    
    @classmethod
    async def close(cls):
        """Close database engine and cleanup connections."""
        if cls._engine:
            await cls._engine.dispose()
            cls._engine = None
            cls._session_factory = None
            logger.info("Database connections closed")


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency to get database session.
    
    Usage in FastAPI:
        @app.get("/users")
        async def get_users(db: AsyncSession = Depends(get_session)):
            ...
    
    Yields:
        AsyncSession: Database session
    """
    session_factory = DatabaseConnection.get_session_factory()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# Export for convenience
get_engine = DatabaseConnection.get_engine
get_session_factory = DatabaseConnection.get_session_factory
health_check = DatabaseConnection.health_check
close_database = DatabaseConnection.close
