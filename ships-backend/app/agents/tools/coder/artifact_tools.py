"""
Artifact Update Tools

LLM-callable tools for updating artifacts during execution.
Enables agents to:
- Mark tasks as complete
- Add notes to implementation plan
- Update folder_map_plan statuses

These tools are designed to be robust with proper error handling
and atomic writes to prevent corruption.
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, Literal
from langchain_core.tools import tool
from .context import get_project_root

logger = logging.getLogger("ships.coder")


@tool
def update_task_status(
    task_id: str,
    status: Literal["pending", "in_progress", "complete", "blocked", "skipped"],
    notes: Optional[str] = None
) -> Dict[str, Any]:
    """
    Update the status of a task in task_list.json.
    
    Call this after completing implementation of a task to track progress.
    
    Args:
        task_id: The task ID (e.g., "TASK-001") to update
        status: New status - one of: pending, in_progress, complete, blocked, skipped
        notes: Optional note about the update (e.g., "Completed with minor adjustments")
        
    Returns:
        Success/failure status with updated task info
    """
    try:
        project_root = get_project_root()
        task_list_path = Path(project_root) / ".ships" / "task_list.json"
        
        if not task_list_path.exists():
            return {
                "success": False,
                "error": "task_list.json not found",
                "hint": "Run Planner first to create task list"
            }
        
        # Read current task list
        with open(task_list_path, "r", encoding="utf-8") as f:
            task_data = json.load(f)
        
        # Find and update the task
        tasks = task_data.get("tasks", [])
        task_found = False
        updated_task = None
        
        for task in tasks:
            if task.get("id") == task_id:
                task_found = True
                task["status"] = status
                task["updated_at"] = datetime.now().isoformat()
                if notes:
                    existing_notes = task.get("notes", [])
                    existing_notes.append({
                        "content": notes,
                        "timestamp": datetime.now().isoformat()
                    })
                    task["notes"] = existing_notes
                updated_task = task
                break
        
        if not task_found:
            return {
                "success": False,
                "error": f"Task '{task_id}' not found",
                "available_tasks": [t.get("id") for t in tasks[:10]]
            }
        
        # Atomic write: write to temp, then rename
        temp_path = task_list_path.with_suffix(".tmp")
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(task_data, f, indent=2)
        temp_path.replace(task_list_path)
        
        logger.info(f"[ARTIFACT] ✅ Task {task_id} updated to '{status}'")
        
        return {
            "success": True,
            "task_id": task_id,
            "new_status": status,
            "task_title": updated_task.get("title", ""),
            "message": f"Task {task_id} marked as {status}"
        }
        
    except Exception as e:
        logger.error(f"[ARTIFACT] ❌ Failed to update task: {e}")
        return {"success": False, "error": str(e)}


@tool
def update_folder_map_status(
    file_path: str,
    status: Literal["pending", "in_progress", "complete", "skipped"] = "complete"
) -> Dict[str, Any]:
    """
    Update the status of a file in folder_map_plan.json.
    
    Call this after successfully creating a file to track progress.
    Automatically called by write_file_to_disk, but can be called manually.
    
    Args:
        file_path: Relative path to the file (e.g., "src/components/Button.tsx")
        status: New status - typically "complete" after file is written
        
    Returns:
        Success/failure status
    """
    try:
        project_root = get_project_root()
        folder_map_path = Path(project_root) / ".ships" / "folder_map_plan.json"
        
        if not folder_map_path.exists():
            return {
                "success": False,
                "error": "folder_map_plan.json not found",
                "hint": "Run Planner first to create folder map"
            }
        
        # Normalize path
        normalized_path = file_path.replace("\\", "/").lstrip("./")
        
        # Read current folder map
        with open(folder_map_path, "r", encoding="utf-8") as f:
            folder_data = json.load(f)
        
        # Find and update the entry
        entries = folder_data.get("entries", [])
        entry_found = False
        
        for entry in entries:
            entry_path = entry.get("path", "").replace("\\", "/").lstrip("./")
            if entry_path == normalized_path:
                entry_found = True
                entry["status"] = status
                entry["updated_at"] = datetime.now().isoformat()
                break
        
        # If not found, add it (defensive - file was created but not in plan)
        if not entry_found:
            entries.append({
                "path": normalized_path,
                "is_directory": False,
                "status": status,
                "added_dynamically": True,
                "updated_at": datetime.now().isoformat()
            })
            logger.info(f"[ARTIFACT] ➕ Added dynamic file to folder_map_plan: {normalized_path}")
        
        folder_data["entries"] = entries
        
        # Atomic write
        temp_path = folder_map_path.with_suffix(".tmp")
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(folder_data, f, indent=2)
        temp_path.replace(folder_map_path)
        
        logger.info(f"[ARTIFACT] ✅ File {normalized_path} marked as '{status}'")
        
        return {
            "success": True,
            "file_path": normalized_path,
            "status": status
        }
        
    except Exception as e:
        logger.error(f"[ARTIFACT] ❌ Failed to update folder map: {e}")
        return {"success": False, "error": str(e)}


@tool
def add_implementation_note(
    section: str,
    note: str
) -> Dict[str, Any]:
    """
    Append a note to implementation_plan.md.
    
    Use this to document important decisions, changes, or issues during execution.
    
    Args:
        section: Section header to add note under (e.g., "Design Decisions", "Issues Found")
        note: The note content to add
        
    Returns:
        Success/failure status
    """
    try:
        project_root = get_project_root()
        plan_path = Path(project_root) / ".ships" / "implementation_plan.md"
        
        if not plan_path.exists():
            return {
                "success": False,
                "error": "implementation_plan.md not found",
                "hint": "Run Planner first to create implementation plan"
            }
        
        # Read current plan
        content = plan_path.read_text(encoding="utf-8")
        
        # Format the note with timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        formatted_note = f"\n- **[{timestamp}]** {note}"
        
        # Try to find the section
        section_header = f"## {section}"
        if section_header in content:
            # Insert after section header
            parts = content.split(section_header)
            # Find end of section (next ## or end of file)
            after_header = parts[1]
            next_section_idx = after_header.find("\n## ")
            
            if next_section_idx > -1:
                # Insert before next section
                insert_point = after_header[:next_section_idx].rfind("\n")
                if insert_point > -1:
                    new_after = after_header[:insert_point] + formatted_note + after_header[insert_point:]
                else:
                    new_after = after_header.rstrip() + formatted_note + "\n"
            else:
                # Append to end of section
                new_after = after_header.rstrip() + formatted_note + "\n"
            
            content = parts[0] + section_header + new_after
        else:
            # Section doesn't exist, add it at the end
            content = content.rstrip() + f"\n\n{section_header}\n{formatted_note}\n"
        
        # Write atomically
        temp_path = plan_path.with_suffix(".tmp")
        temp_path.write_text(content, encoding="utf-8")
        temp_path.replace(plan_path)
        
        logger.info(f"[ARTIFACT] 📝 Added note to '{section}' section")
        
        return {
            "success": True,
            "section": section,
            "note_added": note[:50] + "..." if len(note) > 50 else note
        }
        
    except Exception as e:
        logger.error(f"[ARTIFACT] ❌ Failed to add implementation note: {e}")
        return {"success": False, "error": str(e)}


# Export tools
ARTIFACT_TOOLS = [
    update_task_status,
    update_folder_map_status,
    add_implementation_note,
]

__all__ = [
    "update_task_status",
    "update_folder_map_status", 
    "add_implementation_note",
    "ARTIFACT_TOOLS",
]
