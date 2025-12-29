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
        is_safe, error = is_path_safe(path)
        if not is_safe:
            return json.dumps({
                "success": False,
                "error": error or f"Path '{path}' is outside project root or contains dangerous patterns."
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
                # Debug help: Check for whitespace mismatch
                # Remove all whitespace to check if the tokens theoretically exist
                simplified_search = "".join(search.split())
                simplified_content = "".join(content.split())
                
                if simplified_search and simplified_search in simplified_content:
                     errors.append(f"Operation {i}: Search text mismatch (likely whitespace/indentation). Read the file to get exact bytes.")
                else:
                     errors.append(f"Operation {i}: Search text not found: '{search[:50]}...'. Please read the file first.")
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
        
        is_safe, error = is_path_safe(path)
        if not is_safe:
            return json.dumps({
                "success": False,
                "error": error or f"Path '{path}' is outside project root."
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


@tool
def apply_edits(
    path: str,
    edits: str
) -> str:
    """
    Advanced multi-modal file editing tool.
    Supports search/replace, line replacement, and insertion in a single transaction.
    
    Args:
        path: Relative path to the file.
        edits: JSON string of a LIST of edit objects.
        
    Edit Object Types:
    1. Search & Replace:
       {"type": "replace", "search": "exact string", "replace": "new string"}
       
    2. Line Replacement (Robust):
       {"type": "line_replace", "start_line": 10, "end_line": 15, "content": "new content\\n"}
       - Replaces lines 10 through 15 (inclusive) with content.
       - Use view_source_code first to get line numbers.
       
    3. Insert:
       {"type": "insert", "line": 10, "content": "new line\\n", "after": true}
       - Inserts content after (or before if after=false) line 10.
       
    Returns:
        JSON result with success/failure and diff summary.
    """
    try:
        project_root = get_project_root()
        if not project_root:
            return json.dumps({"success": False, "error": "Project root not set."})
            
        is_safe, error = is_path_safe(path)
        if not is_safe:
            return json.dumps({"success": False, "error": error or "Unsafe path."})
            
        from pathlib import Path
        full_path = Path(project_root) / path
        
        if not full_path.exists():
            return json.dumps({"success": False, "error": f"File not found: {path}"})
            
        # Read content
        original_content = full_path.read_text(encoding='utf-8')
        lines = original_content.splitlines(keepends=True)
        current_content = original_content
        
        # Parse edits
        try:
            edit_list = json.loads(edits)
            if not isinstance(edit_list, list):
                return json.dumps({"success": False, "error": "Edits must be a JSON array."})
        except json.JSONDecodeError as e:
            return json.dumps({"success": False, "error": f"Invalid JSON: {str(e)}"})
            
        changes_log = []
        
        # Apply edits sequentially in-memory
        # Note: Line numbers for LATER edits must account for shifts if using line_replace/insert!
        # Recommendation: Agents should group edits carefully or use search/replace which is content-based.
        
        for i, edit in enumerate(edit_list):
            edit_type = edit.get("type")
            
            if edit_type == "replace":
                search = edit.get("search")
                replace = edit.get("replace")
                if not search or replace is None:
                    return json.dumps({"success": False, "error": f"Op {i}: Missing search/replace fields"})
                
                count = current_content.count(search)
                if count == 0:
                    # Fuzzy Check
                    simplified_search = "".join(search.split())
                    simplified_content = "".join(current_content.split())
                    if simplified_search and simplified_search in simplified_content:
                        return json.dumps({"success": False, "error": f"Op {i}: Search mismatch (whitespace). Use view_source_code."})
                    return json.dumps({"success": False, "error": f"Op {i}: Search text not found."})
                
                current_content = current_content.replace(search, replace)
                changes_log.append(f"Op {i}: Replaced {count} occurrence(s)")
                # Sync lines for mixed mode usage
                lines = current_content.splitlines(keepends=True)
                
            elif edit_type == "line_replace":
                start_line = int(edit.get("start_line", -1))
                end_line = int(edit.get("end_line", -1))
                new_content = edit.get("content", "")
                
                if start_line < 1 or end_line < start_line:
                    return json.dumps({"success": False, "error": f"Op {i}: Invalid line range {start_line}-{end_line}"})
                
                if start_line > len(lines):
                     return json.dumps({"success": False, "error": f"Op {i}: Start line {start_line} out of bounds ({len(lines)} lines)"})
                
                # Convert to 0-indexed
                # Range is [start-1 : end]
                # Replace lines slices with new content (as list of lines)
                
                # Make sure new content has appropriate newlines
                if not new_content.endswith('\n') and end_line < len(lines):
                     new_content += '\n'
                     
                new_lines_list = new_content.splitlines(keepends=True)
                
                # perform slice replacement
                # Python list slice assignment: list[start:end] = new_list
                idx_start = start_line - 1
                idx_end = min(end_line, len(lines))
                
                lines[idx_start:idx_end] = new_lines_list
                
                # Update string content for mixed mode
                current_content = "".join(lines)
                changes_log.append(f"Op {i}: Replaced lines {start_line}-{end_line}")
                
            elif edit_type == "insert":
                line_num = int(edit.get("line", 1))
                content_to_insert = edit.get("content", "")
                after = edit.get("after", True)
                
                if not content_to_insert.endswith('\n'):
                    content_to_insert += '\n'
                
                idx = line_num if after else line_num - 1
                idx = max(0, min(idx, len(lines)))
                
                lines.insert(idx, content_to_insert)
                
                current_content = "".join(lines)
                changes_log.append(f"Op {i}: Inserted at line {line_num}")
                
            else:
                return json.dumps({"success": False, "error": f"Op {i}: Unknown edit type '{edit_type}'"})
        
        # Write final content
        full_path.write_text(current_content, encoding='utf-8')
        
        return json.dumps({
            "success": True,
            "changes": changes_log,
            "new_line_count": len(lines)
        })
        
    except Exception as e:
        return json.dumps({"success": False, "error": f"Unexpected error: {str(e)}"})

# Export tools
EDIT_TOOLS = [
    apply_edits,
    # Keeping old ones for backward compatibility if prompts assume them,
    # but prompts should be updated used new one.
    edit_file_content, 
    insert_at_line, 
]
