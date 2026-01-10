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


@tool
def get_file_tree(force_rescan: bool = False) -> Dict[str, Any]:
    """
    Get the project file tree from cached artifact or scan.
    
    Prefers reading from .ships/file_tree.json artifact (generated by Electron).
    Falls back to scanning if artifact doesn't exist.
    
    Args:
        force_rescan: If True, always rescan instead of using artifact
        
    Returns:
        File tree with entries and symbols
    """
    try:
        project_root = get_project_root()
        artifact_path = Path(project_root) / ".ships" / "file_tree.json"
        
        # Try reading artifact first
        if not force_rescan and artifact_path.exists():
            try:
                import json
                with open(artifact_path, "r", encoding="utf-8") as f:
                    artifact = json.load(f)
                
                logger.info(f"[CODER] 📂 Loaded file tree from artifact")
                return {
                    "success": True,
                    "source": "artifact",
                    **artifact
                }
            except Exception as e:
                logger.warning(f"[CODER] ⚠️ Failed to read artifact: {e}")
        
        # Fall back to scanning
        logger.info(f"[CODER] 🔍 No artifact found, scanning...")
        return scan_project_tree(subpath=".", extract_symbols=True, save_artifact=True)
        
    except Exception as e:
        logger.error(f"[CODER] ❌ get_file_tree failed: {e}")
        return {"success": False, "error": str(e)}


@tool
def get_artifact(name: str) -> Dict[str, Any]:
    """
    Read any artifact from .ships/ directory.
    
    Available artifacts:
    - file_tree.json: File structure with symbols
    - dependency_graph.json: Module dependencies, circular deps
    - security_report.json: Vulnerabilities and secrets
    
    Args:
        name: Artifact filename (e.g. "dependency_graph.json")
        
    Returns:
        Artifact content or error
    """
    try:
        project_root = get_project_root()
        artifact_path = Path(project_root) / ".ships" / name
        
        if not artifact_path.exists():
            return {
                "success": False, 
                "error": f"Artifact not found: {name}",
                "hint": "Run 'generateArtifacts()' in Electron to create artifacts"
            }
        
        import json
        with open(artifact_path, "r", encoding="utf-8") as f:
            content = json.load(f)
        
        logger.info(f"[CODER] 📄 Loaded artifact: {name}")
        return {"success": True, "name": name, "content": content}
        
    except Exception as e:
        logger.error(f"[CODER] ❌ Failed to read artifact {name}: {e}")
        return {"success": False, "error": str(e)}
