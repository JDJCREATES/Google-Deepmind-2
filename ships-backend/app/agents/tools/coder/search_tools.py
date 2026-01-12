"""
ShipS* Search Tools

Codebase search and call graph navigation tools for the Coder agent.
Enables finding symbols, text patterns, and understanding code relationships.
"""

import json
import re
import os
from pathlib import Path
from typing import Optional, List, Dict, Any
from langchain_core.tools import tool

from .context import get_project_root, is_path_safe


@tool
def search_codebase(
    query: str,
    file_pattern: Optional[str] = None,
    case_sensitive: bool = False,
    max_results: int = 20
) -> str:
    """
    Search for text patterns across the codebase.
    
    Use this to find:
    - Function/variable usages
    - Import statements
    - String literals
    - TODO/FIXME comments
    
    Args:
        query: Text or regex pattern to search for
        file_pattern: Optional glob pattern (e.g., "*.tsx", "src/**/*.py")
        case_sensitive: Match case exactly (default: False)
        max_results: Maximum number of results to return (default: 20)
    
    Returns:
        JSON with matches: [{file, line, content, context}]
    """
    project_root = get_project_root()
    if not project_root:
        return json.dumps({"error": "Project root not set. Call set_project_root first."})
    
    project_path = Path(project_root)
    results: List[Dict[str, Any]] = []
    
    # Compile regex
    flags = 0 if case_sensitive else re.IGNORECASE
    try:
        pattern = re.compile(query, flags)
    except re.error as e:
        # Fall back to literal search if regex is invalid
        pattern = re.compile(re.escape(query), flags)
    
    # Directories to skip
    skip_dirs = {'.git', 'node_modules', '__pycache__', 'dist', 'build', '.ships', '.next', 'coverage'}
    
    # Extensions to search
    code_extensions = {'.ts', '.tsx', '.js', '.jsx', '.py', '.json', '.css', '.html', '.md', '.yaml', '.yml'}
    
    def matches_file_pattern(file_path: Path) -> bool:
        if not file_pattern:
            return True
        from fnmatch import fnmatch
        rel_path = str(file_path.relative_to(project_path))
        return fnmatch(rel_path, file_pattern) or fnmatch(file_path.name, file_pattern)
    
    for root, dirs, files in os.walk(project_path):
        # Skip ignored directories
        dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith('.')]
        
        for file_name in files:
            if len(results) >= max_results:
                break
                
            file_path = Path(root) / file_name
            
            # Check extension
            if file_path.suffix.lower() not in code_extensions:
                continue
            
            # Check file pattern
            if not matches_file_pattern(file_path):
                continue
            
            # Check path safety
            if not is_path_safe(str(file_path)):
                continue
            
            try:
                content = file_path.read_text(encoding='utf-8', errors='ignore')
                lines = content.split('\n')
                
                for i, line in enumerate(lines):
                    if pattern.search(line):
                        # Get context (2 lines before and after)
                        start = max(0, i - 2)
                        end = min(len(lines), i + 3)
                        context_lines = lines[start:end]
                        
                        results.append({
                            "file": str(file_path.relative_to(project_path)).replace('\\', '/'),
                            "line": i + 1,
                            "content": line.strip(),
                            "context": '\n'.join(context_lines)
                        })
                        
                        if len(results) >= max_results:
                            break
            except Exception:
                continue
    
    return json.dumps({
        "query": query,
        "total_matches": len(results),
        "matches": results,
        "truncated": len(results) >= max_results
    }, indent=2)


@tool
def query_call_graph(
    function_name: str,
    query_type: str = "callers"
) -> str:
    """
    Query the call graph to understand code relationships.
    
    Use this to find:
    - Who calls a function (callers)
    - What a function calls (callees)
    - Import dependencies
    
    Args:
        function_name: Name of the function to query
        query_type: "callers" (who calls this) or "callees" (what this calls)
    
    Returns:
        JSON with related functions and their locations
    """
    project_root = get_project_root()
    if not project_root:
        return json.dumps({"error": "Project root not set."})
    
    call_graph_path = Path(project_root) / '.ships' / 'call_graph.json'
    
    if not call_graph_path.exists():
        return json.dumps({
            "error": "call_graph.json not found. Run artifact generation first.",
            "suggestion": "The call graph is generated when the project is opened in the Electron app."
        })
    
    try:
        call_graph = json.loads(call_graph_path.read_text(encoding='utf-8'))
    except Exception as e:
        return json.dumps({"error": f"Failed to read call graph: {e}"})
    
    nodes = call_graph.get("nodes", [])
    results: List[Dict[str, Any]] = []
    
    if query_type == "callers":
        # Find all nodes that call this function
        for node in nodes:
            for call in node.get("calls", []):
                if call.get("callee") == function_name:
                    results.append({
                        "caller": node.get("fullName"),
                        "file": node.get("file"),
                        "line": call.get("line"),
                        "is_method_call": call.get("isMethodCall", False)
                    })
    
    elif query_type == "callees":
        # Find what this function calls
        for node in nodes:
            if node.get("name") == function_name or node.get("fullName") == function_name:
                results.append({
                    "function": node.get("fullName"),
                    "file": node.get("file"),
                    "calls": [
                        {"callee": c.get("callee"), "line": c.get("line")}
                        for c in node.get("calls", [])
                    ]
                })
    
    return json.dumps({
        "function": function_name,
        "query_type": query_type,
        "results": results
    }, indent=2)


@tool
def get_file_dependencies(file_path: str) -> str:
    """
    Get import dependencies for a specific file.
    
    Shows:
    - What this file imports (dependencies)
    - What imports this file (dependents)
    
    Args:
        file_path: Relative path to the file (e.g., "src/App.tsx")
    
    Returns:
        JSON with imports and dependents
    """
    project_root = get_project_root()
    if not project_root:
        return json.dumps({"error": "Project root not set."})
    
    dep_graph_path = Path(project_root) / '.ships' / 'dependency_graph.json'
    
    if not dep_graph_path.exists():
        return json.dumps({
            "error": "dependency_graph.json not found.",
            "suggestion": "Run artifact generation first."
        })
    
    try:
        dep_graph = json.loads(dep_graph_path.read_text(encoding='utf-8'))
    except Exception as e:
        return json.dumps({"error": f"Failed to read dependency graph: {e}"})
    
    # Normalize path
    file_path = file_path.replace('\\', '/')
    
    edges = dep_graph.get("edges", [])
    
    imports_from: List[Dict] = []
    imported_by: List[Dict] = []
    
    for edge in edges:
        if edge.get("from") == file_path:
            imports_from.append({
                "module": edge.get("to"),
                "items": edge.get("imports", []),
                "is_external": edge.get("isExternal", False)
            })
        
        if edge.get("to") == file_path or edge.get("to").endswith(f"/{file_path}"):
            imported_by.append({
                "file": edge.get("from"),
                "items": edge.get("imports", [])
            })
    
    # Check for circular dependencies
    circular = dep_graph.get("circular", [])
    in_cycle = [cycle for cycle in circular if file_path in cycle]
    
    return json.dumps({
        "file": file_path,
        "imports": imports_from,
        "imported_by": imported_by,
        "circular_dependencies": in_cycle
    }, indent=2)


# Export all search tools
SEARCH_TOOLS = [
    search_codebase,
    query_call_graph,
    get_file_dependencies,
]

__all__ = [
    "search_codebase",
    "query_call_graph", 
    "get_file_dependencies",
    "SEARCH_TOOLS",
]
