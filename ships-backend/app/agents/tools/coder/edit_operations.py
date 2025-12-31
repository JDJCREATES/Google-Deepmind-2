"""
Edit Operations Tool

Robust, context-aware file editing tools for AI agents.
Prioritizes search/replace blocks over line numbers to prevent drift and errors.
"""

import json
import logging
import re
from typing import Optional, List, Dict, Any, Tuple
from langchain_core.tools import tool
from .context import get_project_root, is_path_safe

logger = logging.getLogger("ships.coder.tools")

def normalize_line(line: str) -> str:
    """Normalize a line for fuzzy matching (strip whitespace)."""
    return line.strip()

def find_fuzzy_match(content_lines: List[str], search_lines: List[str]) -> Tuple[int, int]:
    """
    Find lines in content that fuzzy-match the search lines.
    Returns (start_index, end_index) or (-1, -1).
    Index is 0-based.
    Verifies uniqueness (returns -1 if ambiguous).
    """
    if not search_lines:
        return -1, -1
        
    normalized_search = [normalize_line(l) for l in search_lines]
    # Filter out empty search lines? No, whitespace matters for block structure sometimes, 
    # but for fuzzy match we usually ignore empty lines? 
    # Let's keep empty lines but they match any empty-looking line.
    
    n_search = len(normalized_search)
    n_content = len(content_lines)
    
    matches = []
    
    for i in range(n_content - n_search + 1):
        window = content_lines[i : i + n_search]
        # Check match
        is_match = True
        for j, s_line in enumerate(normalized_search):
            c_line = normalize_line(window[j])
            if s_line != c_line:
                is_match = False
                break
        
        if is_match:
            matches.append(i)
            
    if len(matches) == 1:
        return matches[0], matches[0] + n_search
    elif len(matches) > 1:
        logger.warning(f"Ambiguous fuzzy match found {len(matches)} times.")
        return -2, -2 # Ambiguous
    else:
        return -1, -1

@tool
def apply_source_edits(
    path: str,
    edits: str
) -> str:
    """
    Apply a list of search/replace edits to a file.
    
    Robustness Features:
    - Verifies uniqueness of search blocks.
    - Supports fuzzy matching (ignores indentation/whitespace differences).
    - Prevents "drift" by applying edits from bottom-to-top or strictly monitoring context.
    
    Args:
        path: Relative path to file.
        edits: JSON string of List[Dict], where each Dict has:
               - "search": The code block to replace (EXACT or FUZZY match).
               - "replace": The new code block.
               
    Usage Strategy:
        - Provide enough "search" context to be unique.
        - Whitespace in "search" is flexible, but text content must match.
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
            
        content = full_path.read_text(encoding='utf-8')
        lines = content.splitlines(keepends=True) # Keep original newlines for reconstruction
        
        try:
            edit_list = json.loads(edits)
            if not isinstance(edit_list, list):
                return json.dumps({"success": False, "error": "Edits must be a JSON array."})
        except json.JSONDecodeError as e:
            return json.dumps({"success": False, "error": f"Invalid JSON: {str(e)}"})
            
        # Log of what happened
        changes_log = []
        
        # We apply edits one by one. 
        # WARNING: Applying an edit changes the file content!
        # If multiple edits are provided, subsequent searches might fail if they overlap or context changes.
        # Ideally, we sort edits by position? But we don't know position until we search.
        # "Aider" applies them sequentially and re-reads (or updates in-memory).
        # We will apply sequentially to in-memory 'lines'.
        
        for i, edit in enumerate(edit_list):
            search_block = edit.get("search", "")
            replace_block = edit.get("replace", "")
            
            if not search_block:
                 return json.dumps({"success": False, "error": f"Op {i}: Missing search block."})
            
            # Prepare search lines (split by \n)
            # Handle Windows/Unix newlines
            search_lines = search_block.replace('\r\n', '\n').split('\n')
            
            # Search in current 'lines'
            # 1. Try Exact String Match first (fastest)
            current_text = "".join(lines)
            if current_text.count(search_block) == 1:
                # Exact unique match
                current_text = current_text.replace(search_block, replace_block)
                lines = current_text.splitlines(keepends=True)
                changes_log.append(f"Op {i}: Exact match replaced.")
                continue
            elif current_text.count(search_block) > 1:
                return json.dumps({"success": False, "error": f"Op {i}: Search block is ambiguous (found {current_text.count(search_block)} times). Provide more context."})
            
            # 2. Try Fuzzy Line Match
            # We must map 'lines' (which have keepends=True) to stripped versions
            # Note: search_lines usually don't have newlines at end if coming from JSON string split
            
            # Normalize content lines for matching (remove trailing \n and whitespace)
            content_lines_stripped = [l.strip() for l in lines]
            
            # Find match indices
            start_idx, end_idx = find_fuzzy_match(content_lines_stripped, [l.strip() for l in search_lines])
            
            if start_idx == -2:
                return json.dumps({"success": False, "error": f"Op {i}: Ambiguous fuzzy match found. Provide more unique context."})
            
            if start_idx == -1:
                # Debug info
                # Maybe show a snippet?
                return json.dumps({"success": False, "error": f"Op {i}: Search block not found (exact or fuzzy). Check indentation and content."})
            
            # Replace lines [start_idx : end_idx]
            # Verify we are replacing what we think
            
            # Prepare replacement lines
            replace_lines = replace_block.replace('\r\n', '\n').split('\n')
            # Add newline to end of each line except last? 
            # Actually, splitlines() consumes delimiters. 
            # We want to reconstruct the file. 
            # Easier: Just replace the list slice with new list of strings.
            # But we need newline chars.
            
            final_replace_lines = [l + '\n' for l in replace_lines[:-1]]
            if replace_lines:
                final_replace_lines.append(replace_lines[-1]) # Last line might not need \n if file doesn't end with one?
                # Usually safely add \n unless it's EOF special case.
                # Let's standardize: Code usually has newlines.
                if len(final_replace_lines) > 0 and not final_replace_lines[-1].endswith('\n'):
                     final_replace_lines[-1] += '\n'
            
            # Apply replacement
            lines[start_idx:end_idx] = final_replace_lines
            changes_log.append(f"Op {i}: Fuzzy match replaced (lines {start_idx+1}-{end_idx}).")
            
        # Write Result
        full_path.write_text("".join(lines), encoding='utf-8')
        
        return json.dumps({
            "success": True,
            "changes": changes_log,
            "new_line_count": len(lines)
        })
        
    except Exception as e:
        return json.dumps({"success": False, "error": f"Unexpected error: {str(e)}"})


@tool
def insert_content(
    path: str,
    content: str,
    after_context: str
) -> str:
    """
    Insert content into a file immediately after the specified context block.
    
    Args:
        path: Relative path.
        content: The new code to insert.
        after_context: Unique code block to find. Insertion happens after this block.
    """
    try:
        project_root = get_project_root()
        if not project_root:
            return json.dumps({"success": False, "error": "Project root not set."})
            
        full_path = get_project_root() / path # type: ignore
        if not full_path.exists():
             return json.dumps({"success": False, "error": f"File not found: {path}"})

        file_content = full_path.read_text(encoding='utf-8')
        lines = file_content.splitlines(keepends=True)
        
        # Search for context
        # Try exact match first
        if after_context in file_content:
            if file_content.count(after_context) > 1:
                return json.dumps({"success": False, "error": "Context block found multiple times. Provide more unique context."})
            
            # Exact insert
            parts = file_content.split(after_context)
            new_content = parts[0] + after_context + "\n" + content + parts[1]
            full_path.write_text(new_content, encoding='utf-8')
            return json.dumps({"success": True, "message": "Content inserted (exact match)."})
        
        # Fuzzy match
        ctx_lines = after_context.replace('\r\n', '\n').split('\n')
        content_lines_stripped = [l.strip() for l in lines]
        start_idx, end_idx = find_fuzzy_match(content_lines_stripped, [l.strip() for l in ctx_lines])
        
        if start_idx < 0:
             return json.dumps({"success": False, "error": "Context block not found (exact or fuzzy)."})
             
        # Insert after end_idx
        # Prepare content lines
        new_lines = content.replace('\r\n', '\n').split('\n') 
        final_new_lines = [l + '\n' for l in new_lines] # Add newlines aggressively
        
        lines[end_idx:end_idx] = final_new_lines
        
        full_path.write_text("".join(lines), encoding='utf-8')
        return json.dumps({"success": True, "message": f"Content inserted at line {end_idx+1} (fuzzy match)."})

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


# Export tools
EDIT_TOOLS = [
    apply_source_edits,
    insert_content,
    # Keeping old one just in case a prompt hallucinated it, but strongly discourage
    # edit_file_content - NO, REMOVE IT to force new behavior
]
