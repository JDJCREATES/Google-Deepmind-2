"""
ShipS* Core Module

Provides centralized utilities and configuration.
"""

from app.core.logger import (
    setup_logging,
    get_logger,
    dev_log,
    truncate_for_log,
    log_timing,
    IS_DEV,
)

from app.core.llm_factory import LLMFactory

__all__ = [
    # Logging
    "setup_logging",
    "get_logger", 
    "dev_log",
    "truncate_for_log",
    "log_timing",
    "IS_DEV",
    # LLM
    "LLMFactory",
]
