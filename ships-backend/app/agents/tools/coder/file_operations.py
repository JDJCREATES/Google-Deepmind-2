"""
File Operations Tools

Core tools for reading, writing, and listing files in the project.
These are the primary tools for creating and modifying code.
"""

from typing import Dict, Any
from pathlib import Path
import logging

from langchain_core.tools import tool
from .context import get_project_root, is_path_safe

logger = logging.getLogger("ships.coder")


@tool
def write_file_to_disk(file_path: str, content: str) -> Dict[str, Any]:
    """
    Write a file to disk in the current project.
    
    This is the primary tool for creating and modifying files.
    Creates parent directories if they don't exist.
    
    Args:
        file_path: Relative path within the project (e.g., "src/App.tsx")
        content: The full content to write to the file
        
    Returns:
        Dict with success status, relative path, and bytes written
    """
    try:
        # Validate path safety
        is_safe, error = is_path_safe(file_path)
        if not is_safe:
            logger.error(f"[CODER] ❌ BLOCKED: {error}")
            return {"success": False, "error": error, "path": file_path}
        
        project_root = get_project_root()
        resolved_path = (Path(project_root) / file_path).resolve()
        
        # Create parent directories
        resolved_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write the file
        resolved_path.write_text(content, encoding="utf-8")
        
        logger.info(f"[CODER] ✅ Wrote file: {file_path} ({len(content)} bytes)")
        
        return {
            "success": True,
            "relative_path": file_path,
            "bytes_written": len(content),
            "lines": content.count("\n") + 1
        }
        
    except Exception as e:
        logger.error(f"[CODER] ❌ Failed to write {file_path}: {e}")
        return {"success": False, "error": str(e), "path": file_path}


@tool
def read_file_from_disk(file_path: str) -> Dict[str, Any]:
    """
    Read a file from the current project.
    
    Essential for modifying existing code - read first, then write changes.
    
    Args:
        file_path: Relative path within the project (e.g., "src/App.tsx")
        
    Returns:
        Dict with success status, content, and line count
    """
    try:
        # Validate path safety
        is_safe, error = is_path_safe(file_path)
        if not is_safe:
            logger.error(f"[CODER] ❌ BLOCKED read: {error}")
            return {"success": False, "error": error, "path": file_path}
        
        project_root = get_project_root()
        resolved_path = (Path(project_root) / file_path).resolve()
        
        if not resolved_path.exists():
            return {
                "success": False,
                "error": f"File not found: {file_path}",
                "path": file_path
            }
        
        if not resolved_path.is_file():
            return {
                "success": False,
                "error": f"Not a file: {file_path}",
                "path": file_path
            }
        
        content = resolved_path.read_text(encoding="utf-8")
        
        logger.info(f"[CODER] 📖 Read file: {file_path} ({len(content)} bytes)")
        
        # Return truncated preview to save tokens - full content is on disk
        # LLM can use edit_file_content for targeted changes without full read
        preview = content[:500] + "\n...[truncated]..." if len(content) > 500 else content
        
        return {
            "success": True,
            "content": preview,
            "full_lines": content.count("\n") + 1,
            "bytes": len(content),
            "truncated": len(content) > 500,
            "note": "Use edit_file_content for targeted changes instead of read+write"
        }
        
    except Exception as e:
        logger.error(f"[CODER] ❌ Failed to read {file_path}: {e}")
        return {"success": False, "error": str(e), "path": file_path}


@tool
def list_directory(path: str = ".") -> Dict[str, Any]:
    """
    List files and folders in a directory.
    
    Essential for understanding project structure before making changes.
    
    Args:
        path: Relative path within the project (default: root)
        
    Returns:
        Dict with success status and list of items with names, types, and sizes
    """
    try:
        # Validate path safety
        is_safe, error = is_path_safe(path)
        if not is_safe:
            logger.error(f"[CODER] ❌ BLOCKED list: {error}")
            return {"success": False, "error": error, "path": path}
        
        project_root = get_project_root()
        resolved_path = (Path(project_root) / path).resolve()
        
        if not resolved_path.exists():
            return {
                "success": False,
                "error": f"Directory not found: {path}",
                "path": path
            }
        
        if not resolved_path.is_dir():
            return {
                "success": False,
                "error": f"Not a directory: {path}",
                "path": path
            }
        
        items = []
        for item in sorted(resolved_path.iterdir(), key=lambda x: (not x.is_dir(), x.name)):
            item_info = {
                "name": item.name,
                "type": "directory" if item.is_dir() else "file",
            }
            if item.is_file():
                item_info["size"] = item.stat().st_size
            items.append(item_info)
        
        logger.info(f"[CODER] 📂 Listed directory: {path} ({len(items)} items)")
        
        return {
            "success": True,
            "path": path,
            "items": items,
            "count": len(items)
        }
        
    except Exception as e:
        logger.error(f"[CODER] ❌ Failed to list {path}: {e}")
        return {"success": False, "error": str(e), "path": path}


# Export all file operation tools
FILE_OPERATION_TOOLS = [
    write_file_to_disk,
    read_file_from_disk,
    list_directory,
]
