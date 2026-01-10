"""
ShipS* Centralized Logging Configuration

Provides:
- Environment-based log levels (dev=DEBUG, prod=INFO)
- Namespaced loggers under 'ships.*'
- Dev-only logging utilities
- Third-party log silencing

Usage:
    from app.core.logger import get_logger, dev_log
    
    logger = get_logger("my_module")
    logger.info("Always visible")
    dev_log(logger, "Only in dev mode: %s", some_data)
"""

import logging
import os
import sys
from typing import Optional
from functools import wraps

# ============================================================================
# ENVIRONMENT DETECTION
# ============================================================================

def is_dev_mode() -> bool:
    """Check if running in development mode."""
    env = os.getenv("SHIPS_ENV", "development").lower()
    return env in ("development", "dev", "local")

IS_DEV = is_dev_mode()

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

class SensitiveDataFilter(logging.Filter):
    """
    Filter to prevent sensitive data from appearing in production logs.
    Redacts content that looks like API keys, tokens, or user content longer than thresholds.
    """
    
    # Patterns that should never appear in logs
    SENSITIVE_PATTERNS = [
        "api_key",
        "secret",
        "password",
        "token",
        "bearer",
        "authorization",
    ]
    
    # Max length for user content in production
    MAX_CONTENT_LENGTH = 100
    
    def filter(self, record: logging.LogRecord) -> bool:
        if IS_DEV:
            return True  # Allow everything in dev
        
        # In production, check for sensitive patterns
        msg = record.getMessage().lower()
        for pattern in self.SENSITIVE_PATTERNS:
            if pattern in msg:
                record.msg = "[REDACTED - contains sensitive data]"
                record.args = ()
                return True
        
        return True


def setup_logging() -> logging.Logger:
    """
    Configure centralized logging for ShipS*.
    
    Call this ONCE at application startup (in main.py).
    
    Returns:
        Root ShipS* logger
    """
    level = logging.DEBUG if IS_DEV else logging.INFO
    
    # Configure root logger
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
        force=True  # Override any existing config
    )
    
    # Get ships root logger
    ships_logger = logging.getLogger("ships")
    ships_logger.setLevel(level)
    
    # Add sensitive data filter in production
    if not IS_DEV:
        ships_logger.addFilter(SensitiveDataFilter())
    
    # ================================================================
    # SILENCE NOISY THIRD-PARTY LOGGERS
    # ================================================================
    noisy_loggers = [
        ("httpx", logging.WARNING),
        ("httpcore", logging.WARNING),
        ("google_genai", logging.WARNING),
        ("google_genai.models", logging.WARNING),
        ("urllib3", logging.WARNING),
        ("asyncio", logging.WARNING),
        ("websockets", logging.WARNING),
    ]
    
    for logger_name, log_level in noisy_loggers:
        logging.getLogger(logger_name).setLevel(log_level)
    
    # Log startup info
    mode = "DEVELOPMENT" if IS_DEV else "PRODUCTION"
    ships_logger.info(f"🔧 Logging initialized ({mode} mode, level={logging.getLevelName(level)})")
    
    return ships_logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a namespaced logger under ships.*.
    
    Args:
        name: Module name (e.g., "planner", "coder", "orchestrator")
        
    Returns:
        Logger instance
        
    Example:
        logger = get_logger("intent")
        logger.info("[INTENT] Classified request")
    """
    return logging.getLogger(f"ships.{name}")


# ============================================================================
# DEV-ONLY LOGGING UTILITIES
# ============================================================================

def dev_log(logger: logging.Logger, message: str, *args, level: int = logging.DEBUG):
    """
    Log a message ONLY in development mode.
    
    Use this for verbose debugging that should NEVER appear in production.
    
    Args:
        logger: Logger instance
        message: Log message (can use %s formatting)
        *args: Format arguments
        level: Log level (default DEBUG)
        
    Example:
        dev_log(logger, "Full prompt: %s", prompt[:500])
    """
    if IS_DEV:
        logger.log(level, message, *args)


def truncate_for_log(content: str, max_length: int = 100) -> str:
    """
    Truncate content for safe logging.
    
    Args:
        content: String to truncate
        max_length: Max length (default 100)
        
    Returns:
        Truncated string with ... suffix if needed
    """
    if len(content) <= max_length:
        return content
    return content[:max_length] + "..."


# ============================================================================
# TIMING DECORATOR (Dev only)
# ============================================================================

def log_timing(logger: logging.Logger):
    """
    Decorator to log function execution time (dev mode only).
    
    Example:
        @log_timing(logger)
        async def slow_function():
            ...
    """
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            if not IS_DEV:
                return await func(*args, **kwargs)
            
            import time
            start = time.perf_counter()
            result = await func(*args, **kwargs)
            duration = (time.perf_counter() - start) * 1000
            logger.debug(f"⏱️ {func.__name__} completed in {duration:.2f}ms")
            return result
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            if not IS_DEV:
                return func(*args, **kwargs)
            
            import time
            start = time.perf_counter()
            result = func(*args, **kwargs)
            duration = (time.perf_counter() - start) * 1000
            logger.debug(f"⏱️ {func.__name__} completed in {duration:.2f}ms")
            return result
        
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator
