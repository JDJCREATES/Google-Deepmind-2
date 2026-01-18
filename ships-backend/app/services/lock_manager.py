"""
LockManager Service

Manages exclusive write access to files within the agent system.
Prevents race conditions where Coder and Checker/Fixer might modify the same file simultaneously.

Design:
- Singleton pattern (managed via module-level instance or dependency injection).
- In-Memory storage (Dict) for current implementation (MVP).
- Thread-safe / Async-safe for asyncio event loop.
- Keys are effectively `{project_path}::{file_path}` to support multi-tenancy.
"""

import time
from typing import Dict, Optional, Tuple
import logging

logger = logging.getLogger("ships.services.locks")

class LockManager:
    _instance = None
    
    def __init__(self):
        # Map of lock_key -> (agent_id, timestamp)
        self._locks: Dict[str, Tuple[str, float]] = {}
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = LockManager()
        return cls._instance

    def _get_key(self, project_path: str, file_path: str) -> str:
        """normalize paths to create a unique key"""
        from pathlib import Path
        # Normalize slashes
        clean_proj = str(Path(project_path).resolve()).lower().replace("\\", "/")
        clean_file = str(Path(file_path)).lower().replace("\\", "/")
        
        # If file_path is absolute, ensure it starts with project_path
        if clean_file.startswith(clean_proj):
            # It's already absolute and correct
            pass
        else:
            # Assume relative, join them
            clean_file = str(Path(project_path) / file_path).lower().replace("\\", "/")
            
        return clean_file

    def is_locked(self, project_path: str, file_path: str, ttl_seconds: int = 300) -> Optional[str]:
        """
        Check if a file is locked (respecting TTL).
        Returns agent_id if locked and not expired, None if free or expired.
        Auto-cleans up expired locks.
        """
        key = self._get_key(project_path, file_path)
        if key in self._locks:
            agent_id, timestamp = self._locks[key]
            # Check TTL expiration
            if time.time() - timestamp > ttl_seconds:
                logger.warning(f"[LOCKS] ⚠️ Stale lock on {file_path} (held by {agent_id}) - auto-releasing")
                del self._locks[key]  # Auto-cleanup expired lock
                return None
            return agent_id
        return None

    def acquire(self, project_path: str, file_path: str, agent_id: str, ttl_seconds: int = 300) -> bool:
        """
        Attempt to acquire a lock.
        Returns True if successful, False if already locked by another agent.
        """
        key = self._get_key(project_path, file_path)
        now = time.time()
        
        # Check existing lock
        if key in self._locks:
            current_owner, timestamp = self._locks[key]
            
            # Allow re-entry (same agent)
            if current_owner == agent_id:
                self._locks[key] = (agent_id, now) # Refresh TTL
                return True
                
            # Check for generic TTL expiration (deadlock protection)
            if now - timestamp > ttl_seconds:
                logger.warning(f"[LOCKS] ⚠️ Force releasing expired lock on {file_path} (held by {current_owner})")
                # Fall through to acquire
            else:
                # Locked by someone else
                return False
                
        # Acquire
        self._locks[key] = (agent_id, now)
        logger.debug(f"[LOCKS] 🔒 {agent_id} acquired {file_path}")
        return True

    def release(self, project_path: str, file_path: str, agent_id: str) -> bool:
        """
        Release a lock.
        Returns True if released, False if lock was held by someone else or didn't exist.
        """
        key = self._get_key(project_path, file_path)
        
        if key in self._locks:
            current_owner, _ = self._locks[key]
            if current_owner == agent_id:
                del self._locks[key]
                logger.debug(f"[LOCKS] 🔓 {agent_id} released {file_path}")
                return True
            else:
                logger.warning(f"[LOCKS] ⚠️ {agent_id} tried to release lock held by {current_owner}")
                return False
        
        return True

    def clear_all_for_project(self, project_path: str):
        """Emergency cleanup for a project"""
        from pathlib import Path
        clean_proj = str(Path(project_path).resolve()).lower().replace("\\", "/")
        
        keys_to_remove = [k for k in self._locks.keys() if k.startswith(clean_proj)]
        for k in keys_to_remove:
            del self._locks[k]
        
        if keys_to_remove:
            logger.info(f"[LOCKS] 🧹 Cleared {len(keys_to_remove)} locks for project {clean_proj}")


# Global instance
lock_manager = LockManager.get_instance()

async def acquire_lock_with_retries(
    lock_manager: LockManager,
    project_path: str,
    files_to_lock: list[str],
    agent_id: str,
    timeout_seconds: int = 60
) -> Optional[str]:
    """
    Helper to acquire a lock on ANY of the provided files, with retries.
    Returns the file path that was locked, or None if timeout.
    """
    import asyncio
    
    start_wait = time.time()
    
    while (time.time() - start_wait) < timeout_seconds:
        for f in files_to_lock:
            if not lock_manager.is_locked(project_path, f):
                if lock_manager.acquire(project_path, f, agent_id):
                    logger.info(f"[LOCKS] 🔒 {agent_id} acquired lock for: {f}")
                    return f
        
        await asyncio.sleep(2)
        
    logger.warning(f"[LOCKS] ⚠️ Failed to acquire lock for {agent_id} on {files_to_lock} after {timeout_seconds}s")
    return None

