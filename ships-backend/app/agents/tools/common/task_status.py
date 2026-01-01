"""
Task Status Management

Utility functions for updating task status in task_list.json.
Called by Orchestrator after Coder completes tasks.
"""

import json
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger("ships.task_status")


def update_task_status_on_disk(
    project_path: str,
    task_id: str,
    new_status: str
) -> bool:
    """
    Update a task's status in the .ships/task_list.json file.
    
    Args:
        project_path: Root project directory
        task_id: ID of the task to update
        new_status: New status (pending, in_progress, completed, blocked)
        
    Returns:
        True if task was found and updated
    """
    task_list_path = Path(project_path) / ".ships" / "task_list.json"
    
    if not task_list_path.exists():
        logger.warning(f"task_list.json not found at {task_list_path}")
        return False
    
    try:
        with open(task_list_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        tasks = data.get("tasks", [])
        updated = False
        
        for task in tasks:
            if task.get("id") == task_id:
                task["status"] = new_status
                updated = True
                logger.info(f"[TASK_STATUS] Updated {task_id} -> {new_status}")
                break
        
        if updated:
            with open(task_list_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            return True
        else:
            logger.warning(f"Task {task_id} not found in task_list.json")
            return False
            
    except Exception as e:
        logger.error(f"Failed to update task status: {e}")
        return False


def mark_task_complete_on_disk(project_path: str, task_id: str) -> bool:
    """Mark a task as completed."""
    return update_task_status_on_disk(project_path, task_id, "completed")


def mark_task_in_progress_on_disk(project_path: str, task_id: str) -> bool:
    """Mark a task as in progress."""
    return update_task_status_on_disk(project_path, task_id, "in_progress")


def get_task_progress(project_path: str) -> dict:
    """
    Get progress summary from task_list.json.
    
    Returns:
        Dict with total, completed, in_progress, pending, percent_complete
    """
    task_list_path = Path(project_path) / ".ships" / "task_list.json"
    
    if not task_list_path.exists():
        return {"total": 0, "completed": 0, "in_progress": 0, "pending": 0, "percent_complete": 0}
    
    try:
        with open(task_list_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        tasks = data.get("tasks", [])
        total = len(tasks)
        completed = sum(1 for t in tasks if t.get("status") == "completed")
        in_progress = sum(1 for t in tasks if t.get("status") == "in_progress")
        pending = sum(1 for t in tasks if t.get("status") == "pending")
        
        return {
            "total": total,
            "completed": completed,
            "in_progress": in_progress,
            "pending": pending,
            "percent_complete": round((completed / total * 100) if total > 0 else 0, 1)
        }
    except Exception as e:
        logger.error(f"Failed to get task progress: {e}")
        return {"total": 0, "completed": 0, "in_progress": 0, "pending": 0, "percent_complete": 0}
