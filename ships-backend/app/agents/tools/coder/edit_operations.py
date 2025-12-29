"""
Edit File Content Tool

Token-efficient file editing using search/replace operations.
Allows targeted modifications without rewriting entire files.

This is critical for vibe coding platforms where token usage matters.
"""

import json
import re
from typing import Optional
from langchain_core.tools import tool
from .context import get_project_root, is_path_safe


@tool
def edit_file_content(
    path: str,
    operations: str
) -> str:
    """
    Edit a file using search/replace operations. Token-efficient for targeted changes.
    
    Use this instead of write_file_to_disk when modifying existing files.
    Only outputs the changed portions, saving tokens.
    
    Args:
        path: Relative path to the file (e.g., "src/App.jsx")
        operations: JSON string array of operations, each with:
            - search: Exact text to find (must match exactly, including whitespace)
            - replace: Text to replace it with
            
    Example operations:
    '[{"search": "const old = 1;", "replace": "const new = 2;"}]'
    
    Multiple operations are applied in order.
    
    Returns:
        JSON with success status, changes made, and any errors.
    """
    try:
        # Get project root (set by agent_graph before coder runs)
        project_root = get_project_root()
        if not project_root:
            return json.dumps({
                "success": False,
                "error": "Project root not set. This is a security restriction."
            })
        
        # Security: Validate path
        if not is_path_safe(path, project_root):
            return json.dumps({
                "success": False,
                "error": f"Path '{path}' is outside project root or contains dangerous patterns."
            })
        
        from pathlib import Path
        full_path = Path(project_root) / path
        
        # Check file exists
        if not full_path.exists():
            return json.dumps({
                "success": False,
                "error": f"File not found: {path}. Use write_file_to_disk for new files."
            })
        
        if not full_path.is_file():
            return json.dumps({
                "success": False,
                "error": f"Path is not a file: {path}"
            })
        
        # Parse operations
        try:
            ops = json.loads(operations)
            if not isinstance(ops, list):
                return json.dumps({
                    "success": False,
                    "error": "Operations must be a JSON array"
                })
        except json.JSONDecodeError as e:
            return json.dumps({
                "success": False,
                "error": f"Invalid JSON in operations: {str(e)}"
            })
        
        # Read current content
        try:
            content = full_path.read_text(encoding='utf-8')
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"Failed to read file: {str(e)}"
            })
        
        original_content = content
        changes_made = []
        errors = []
        
        # Apply each operation
        for i, op in enumerate(ops):
            if not isinstance(op, dict):
                errors.append(f"Operation {i}: Not a valid object")
                continue
                
            search = op.get("search")
            replace = op.get("replace")
            
            if search is None:
                errors.append(f"Operation {i}: Missing 'search' field")
                continue
            if replace is None:
                errors.append(f"Operation {i}: Missing 'replace' field")
                continue
            
            # Count occurrences
            count = content.count(search)
            
            if count == 0:
                errors.append(f"Operation {i}: Search text not found: '{search[:50]}...'")
                continue
            
            if count > 1:
                # Multiple matches - warn but proceed (replaces all)
                changes_made.append({
                    "operation": i,
                    "search_preview": search[:40] + "..." if len(search) > 40 else search,
                    "matches": count,
                    "warning": "Multiple matches found, all replaced"
                })
            else:
                changes_made.append({
                    "operation": i,
                    "search_preview": search[:40] + "..." if len(search) > 40 else search,
                    "matches": 1
                })
            
            # Apply replacement
            content = content.replace(search, replace)
        
        # Only write if changes were made
        if content != original_content:
            try:
                full_path.write_text(content, encoding='utf-8')
            except Exception as e:
                return json.dumps({
                    "success": False,
                    "error": f"Failed to write file: {str(e)}"
                })
            
            return json.dumps({
                "success": True,
                "path": path,
                "changes_applied": len(changes_made),
                "changes": changes_made,
                "errors": errors if errors else None,
                "bytes_written": len(content.encode('utf-8'))
            })
        else:
            return json.dumps({
                "success": False,
                "error": "No changes made to file",
                "errors": errors
            })
            
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"Unexpected error: {str(e)}"
        })


@tool
def insert_at_line(
    path: str,
    line_number: int,
    content: str,
    mode: str = "after"
) -> str:
    """
    Insert content at a specific line number. Useful for adding imports, functions, etc.
    
    Args:
        path: Relative path to file
        line_number: Line number to insert at (1-indexed)
        content: Content to insert
        mode: "after" (insert after line) or "before" (insert before line)
        
    Returns:
        JSON with success status and info.
    """
    try:
        project_root = get_project_root()
        if not project_root:
            return json.dumps({
                "success": False,
                "error": "Project root not set."
            })
        
        if not is_path_safe(path, project_root):
            return json.dumps({
                "success": False,
                "error": f"Path '{path}' is outside project root."
            })
        
        from pathlib import Path
        full_path = Path(project_root) / path
        
        if not full_path.exists():
            return json.dumps({
                "success": False,
                "error": f"File not found: {path}"
            })
        
        # Read lines
        lines = full_path.read_text(encoding='utf-8').splitlines(keepends=True)
        
        if line_number < 1 or line_number > len(lines) + 1:
            return json.dumps({
                "success": False,
                "error": f"Line number {line_number} out of range (file has {len(lines)} lines)"
            })
        
        # Ensure content ends with newline
        if not content.endswith('\n'):
            content += '\n'
        
        # Insert at position
        if mode == "before":
            insert_idx = line_number - 1
        else:  # after
            insert_idx = line_number
        
        lines.insert(insert_idx, content)
        
        # Write back
        full_path.write_text(''.join(lines), encoding='utf-8')
        
        return json.dumps({
            "success": True,
            "path": path,
            "line_number": line_number,
            "mode": mode,
            "lines_inserted": content.count('\n')
        })
        
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e)
        })


# Export tools
EDIT_TOOLS = [
    edit_file_content,
    insert_at_line,
]
