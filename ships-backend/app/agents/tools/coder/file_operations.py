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
        
        # ================================================================
        # AUTO-VERSIONING: Backup implementation_plan.md before overwrite
        # ================================================================
        if "implementation_plan.md" in file_path and resolved_path.exists():
            try:
                from datetime import datetime
                history_dir = Path(project_root) / ".ships" / "history"
                history_dir.mkdir(parents=True, exist_ok=True)
                
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_name = f"implementation_plan_{timestamp}.md"
                backup_path = history_dir / backup_name
                
                # Copy existing content to backup
                existing_content = resolved_path.read_text(encoding="utf-8")
                backup_path.write_text(existing_content, encoding="utf-8")
                
                logger.info(f"[PLANNER] 📦 Backed up plan to: .ships/history/{backup_name}")
            except Exception as backup_err:
                logger.warning(f"[PLANNER] ⚠️ Failed to backup plan: {backup_err}")
        
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
def write_files_batch(files: list[dict]) -> Dict[str, Any]:
    """
    Write multiple files to disk in a single tool call.
    
    This is the PREFERRED method for creating multiple files at once.
    Reduces ReAct loop iterations and token usage significantly.
    
    Args:
        files: List of file specs, each with:
               - path: Relative path (e.g., "src/App.tsx")
               - content: Full content to write
               
    Returns:
        Summary with success count and any errors (not full file contents)
        
    Example:
        write_files_batch([
            {"path": "src/App.tsx", "content": "import React..."},
            {"path": "src/index.css", "content": "body {...}"},
        ])
    """
    project_root = get_project_root()
    if not project_root:
        return {"success": False, "error": "Project root not set", "written": 0}
    
    written = []
    errors = []
    total_bytes = 0
    
    for file_spec in files:
        file_path = file_spec.get("path", "")
        content = file_spec.get("content", "")
        
        if not file_path:
            errors.append({"path": "(empty)", "error": "Missing path"})
            continue
            
        try:
            # Validate path safety
            is_safe, error = is_path_safe(file_path)
            if not is_safe:
                errors.append({"path": file_path, "error": error})
                continue
            
            resolved_path = (Path(project_root) / file_path).resolve()
            
            # Create parent directories
            resolved_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write the file
            resolved_path.write_text(content, encoding="utf-8")
            
            written.append(file_path)
            total_bytes += len(content)
            
            # Log explicitly if overwriting
            status_msg = "Overwrote" if resolved_path.exists() else "Created"
            logger.info(f"[CODER] ✅ {status_msg} file: {file_path} ({len(content)} bytes)")
            
        except Exception as e:
            errors.append({"path": file_path, "error": str(e)})
            logger.error(f"[CODER] ❌ Failed to write {file_path}: {e}")
    
    # Return minimal summary (not full content) to reduce token usage
    return {
        "success": len(errors) == 0,
        "written": written,
        "written_count": len(written),
        "total_bytes": total_bytes,
        "errors": errors if errors else None,
        "message": f"Wrote {len(written)} files ({total_bytes} bytes)" + (f", {len(errors)} errors" if errors else "")
    }


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
        
        # TOKEN OPTIMIZATION: Truncate to 25 items max
        total_count = len(items)
        truncated = total_count > 25
        display_items = items[:25] if truncated else items
        
        return {
            "success": True,
            "path": path,
            "items": display_items,
            "count": total_count,
            "truncated": truncated,
            "message": f"{total_count} items" + (f" (showing first 25)" if truncated else "")
        }
        
    except Exception as e:
        logger.error(f"[CODER] ❌ Failed to list {path}: {e}")
        return {"success": False, "error": str(e), "path": path}


@tool
def create_directory(dir_path: str) -> Dict[str, Any]:
    """
    Create a directory (and any parent directories) in the project.
    
    Use this to set up folder structure before writing files.
    
    Args:
        dir_path: Relative path for the directory (e.g., "src/components")
        
    Returns:
        Dict with success status and path created
    """
    try:
        is_safe, error = is_path_safe(dir_path)
        if not is_safe:
            return {"success": False, "error": error, "path": dir_path}
        
        project_root = get_project_root()
        resolved_path = (Path(project_root) / dir_path).resolve()
        
        resolved_path.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"[PLANNER] 📁 Created directory: {dir_path}")
        
        return {
            "success": True,
            "path": dir_path,
            "created": True
        }
        
    except Exception as e:
        logger.error(f"[PLANNER] ❌ Failed to create {dir_path}: {e}")
        return {"success": False, "error": str(e), "path": dir_path}


@tool
def create_directories(dir_paths: list[str]) -> Dict[str, Any]:
    """
    Create multiple directories in a single call.
    
    Use this to set up folder structure efficiently. All directories are created
    with their parent directories (similar to `mkdir -p`).
    
    Args:
        dir_paths: List of relative paths for directories (e.g., ["src/components", "src/hooks", "src/lib"])
        
    Returns:
        Dict with overall success, list of created paths, and any errors
    """
    project_root = get_project_root()
    created = []
    errors = []
    
    for dir_path in dir_paths:
        try:
            is_safe, error = is_path_safe(dir_path)
            if not is_safe:
                errors.append({"path": dir_path, "error": error})
                continue
            
            resolved_path = (Path(project_root) / dir_path).resolve()
            resolved_path.mkdir(parents=True, exist_ok=True)
            created.append(dir_path)
            
        except Exception as e:
            errors.append({"path": dir_path, "error": str(e)})
    
    logger.info(f"[PLANNER] 📁 Created directories: {' '.join(created)}")
    
    return {
        "success": len(errors) == 0,
        "created": created,
        "errors": errors,
        "total": len(dir_paths)
    }


@tool
def view_source_code(
    path: str,
    start_line: int = 1,
    end_line: int = -1,
    show_lines: bool = True
) -> str:
    """
    Read file content with line numbers. Essential for using line-based edits.
    
    Args:
        path: Relative path to file.
        start_line: Start line (1-indexed).
        end_line: End line (inclusive). -1 for end of file.
        show_lines: Whether to prepend line numbers (e.g., "1: import os").
    
    Returns:
        String content of the file (or slice).
    """
    try:
        project_root = get_project_root()
        if not project_root:
            return "Error: Project root not set."
            
        is_safe, error = is_path_safe(path)
        if not is_safe:
            return f"Error: {error}"
            
        from pathlib import Path
        full_path = Path(project_root) / path
        
        if not full_path.exists():
            return f"Error: File not found: {path}"
            
        content = full_path.read_text(encoding='utf-8')
        lines = content.splitlines()
        
        total_lines = len(lines)
        start = max(1, start_line)
        end = total_lines if end_line == -1 else min(total_lines, end_line)
        
        # Adjust to 0-indexed for slicing
        # lines[0] is line 1
        relevant_lines = lines[start-1 : end]
        
        output = []
        if show_lines:
            # Calculate padding based on max line number
            padding = len(str(end))
            for idx, line in enumerate(relevant_lines):
                line_num = start + idx
                output.append(f"{str(line_num).rjust(padding)}: {line}")
        else:
            output = relevant_lines
            
        return "\n".join(output)

    except Exception as e:
        return f"Error reading file: {str(e)}"

# Export tools
FILE_OPERATION_TOOLS = [
    write_file_to_disk,
    write_files_batch,  # Batch writes - reduces ReAct iterations
    read_file_from_disk,
    list_directory,
    create_directory,
    view_source_code,
]

