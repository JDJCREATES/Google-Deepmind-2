"""
File Tree Scanner Tool

Uses tree-sitter to scan the project directory and return a comprehensive
file tree with symbol definitions (classes, functions).

This replaces manual hallucination of file structures by agents.
"""

import os
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from langchain_core.tools import tool
from .context import get_project_root, is_path_safe

# Try to import tree-sitter, handle missing gracefully
try:
    import tree_sitter_languages
    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False

logger = logging.getLogger("ships.coder")

# Parsing query constants
QUERIES = {
    "python": """
    (class_definition name: (identifier) @name)
    (function_definition name: (identifier) @name)
    """,
    "typescript": """
    (class_declaration name: (type_identifier) @name)
    (function_declaration name: (identifier) @name)
    (variable_declarator name: (identifier) @name value: (arrow_function))
    (interface_declaration name: (type_identifier) @name)
    (type_alias_declaration name: (type_identifier) @name)
    """,
    "javascript": """
    (class_declaration name: (identifier) @name)
    (function_declaration name: (identifier) @name)
    (variable_declarator name: (identifier) @name value: (arrow_function))
    """,
}

# Mapping extensions to tree-sitter languages
EXT_TO_LANG = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
}

def _get_symbols_from_file(file_path: Path) -> List[str]:
    """Extract top-level symbols using tree-sitter."""
    if not TREE_SITTER_AVAILABLE:
        return []
        
    ext = file_path.suffix.lower()
    lang_name = EXT_TO_LANG.get(ext)
    
    if not lang_name:
        return []
        
    try:
        # Use get_parser() which handles Language/Parser compatibility
        parser = tree_sitter_languages.get_parser(lang_name)
        language = tree_sitter_languages.get_language(lang_name)
        
        # Read file
        content = file_path.read_bytes()
        tree = parser.parse(content)
        
        # Run query
        query_str = QUERIES.get(lang_name)
        if not query_str:
            return []
            
        query = language.query(query_str)
        captures = query.captures(tree.root_node)
        
        symbols = []
        for node, capture_name in captures:
            if capture_name == "name":
                symbols.append(content[node.start_byte:node.end_byte].decode("utf-8"))
                
        return list(set(symbols)) # Dedupe
        
    except Exception as e:
        logger.warning(f"Tree-sitter parse failed for {file_path.name}: {e}")
        return []

@tool
def scan_project_tree(
    subpath: str = ".", 
    max_depth: int = 5,
    extract_symbols: bool = True,
    save_artifact: bool = False
) -> Dict[str, Any]:
    """
    Scan the project directory and return a JSON file tree.
    
    Can extract defined symbols (classes, functions) for better planning context.
    Optionally saves the tree to .ships/file_tree.json artifact.
    
    Args:
        subpath: Relative path to scan (default: root)
        max_depth: How deep to scan directory structure
        extract_symbols: Whether to parse files for class/function names
        save_artifact: Whether to save result to .ships/file_tree.json
        
    Returns:
        Dict containing list of entries and stats
    """
    try:
        # Validate path
        is_safe, error = is_path_safe(subpath)
        if not is_safe:
            return {"success": False, "error": error}
            
        project_root = get_project_root()
        root_path = (Path(project_root) / subpath).resolve()
        
        if not root_path.exists():
            return {"success": False, "error": f"Path not found: {subpath}"}
            
        ignore_dirs = {
            ".git", "node_modules", "__pycache__", ".venv", "venv", 
            "dist", "build", ".next", ".ships", "coverage"
        }
        
        entries = []
        file_count = 0
        dir_count = 0
        
        # Walk directory
        for path in root_path.rglob("*"):
            # Limit depth
            rel_path = path.relative_to(root_path)
            if len(rel_path.parts) > max_depth:
                continue
                
            # Check ignore patterns in path parts
            if any(part in ignore_dirs or part.startswith(".") for part in rel_path.parts):
                continue
                
            is_dir = path.is_dir()
            
            entry = {
                "path": str(rel_path).replace("\\", "/"),
                "is_directory": is_dir
            }
            
            if is_dir:
                entry["type"] = "directory"
                dir_count += 1
            else:
                entry["type"] = "file"
                file_count += 1
                if extract_symbols:
                    symbols = _get_symbols_from_file(path)
                    if symbols:
                        entry["definitions"] = symbols
            
            entries.append(entry)
            
        logger.info(f"[CODER] 🌳 Scanned tree: {file_count} files, {dir_count} dirs")
        
        result = {
            "success": True,
            "root": str(subpath),
            "entries": entries,
            "stats": {
                "files": file_count,
                "directories": dir_count
            }
        }
        
        # Save artifact if requested
        if save_artifact:
            try:
                import json
                ships_dir = Path(project_root) / ".ships"
                ships_dir.mkdir(exist_ok=True)
                artifact_path = ships_dir / "file_tree.json"
                
                with open(artifact_path, "w", encoding="utf-8") as f:
                    json.dump(result, f, indent=2)
                
                logger.info(f"[CODER] 💾 Saved file tree artifact to {artifact_path}")
                result["artifact_path"] = str(artifact_path)
            except Exception as e:
                logger.warning(f"[CODER] ⚠️ Failed to save file tree artifact: {e}")
        
        return result
        
    except Exception as e:
        logger.error(f"[CODER] ❌ Tree scan failed: {e}")
        return {"success": False, "error": str(e)}
