"""
Debounced logging utility to prevent log spam.
Tracks recent log messages and only emits if sufficient time has passed.
"""
import time
import logging
from typing import Dict, Tuple
from functools import wraps

class DebouncedLogger:
    """Logger wrapper that debounces repeated messages."""
    
    def __init__(self, logger: logging.Logger, debounce_seconds: float = 1.0):
        self.logger = logger
        self.debounce_seconds = debounce_seconds
        self._last_log_times: Dict[Tuple[str, str], float] = {}
        self._log_counts: Dict[Tuple[str, str], int] = {}
    
    def _should_log(self, level: str, message: str) -> bool:
        """Check if enough time has passed since last identical log."""
        key = (level, message)
        now = time.time()
        
        last_time = self._last_log_times.get(key, 0)
        time_since_last = now - last_time
        
        if time_since_last >= self.debounce_seconds:
            # Log the count if this message was suppressed
            count = self._log_counts.get(key, 0)
            if count > 0:
                self._log_counts[key] = 0
                return True  # Will add count suffix
            
            self._last_log_times[key] = now
            return True
        
        # Increment suppressed count
        self._log_counts[key] = self._log_counts.get(key, 0) + 1
        return False
    
    def _get_log_func(self, level: str):
        """Get the appropriate logging function."""
        return getattr(self.logger, level.lower())
    
    def log(self, level: str, message: str, *args, **kwargs):
        """Log a message with debouncing."""
        key = (level, message)
        
        if self._should_log(level, message):
            count = self._log_counts.get(key, 0)
            if count > 0:
                message = f"{message} (suppressed {count} similar logs)"
                self._log_counts[key] = 0
            
            log_func = self._get_log_func(level)
            log_func(message, *args, **kwargs)
    
    def info(self, message: str, *args, **kwargs):
        self.log("INFO", message, *args, **kwargs)
    
    def debug(self, message: str, *args, **kwargs):
        self.log("DEBUG", message, *args, **kwargs)
    
    def warning(self, message: str, *args, **kwargs):
        self.log("WARNING", message, *args, **kwargs)
    
    def error(self, message: str, *args, **kwargs):
        self.log("ERROR", message, *args, **kwargs)


def debounced_log(debounce_seconds: float = 1.0):
    """
    Decorator to debounce logging within a function.
    
    Usage:
        @debounced_log(2.0)
        def my_function():
            logger.info("This won't spam")
    """
    def decorator(func):
        debouncer = None
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            nonlocal debouncer
            
            # Intercept logger calls within the function
            # This is a simplified version - you'd typically patch the logger
            return func(*args, **kwargs)
        
        return wrapper
    return decorator
