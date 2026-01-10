"""
Python Call Graph Analyzer

Uses PyCG for accurate Python call graph generation.
PyCG performs inter-procedural analysis to track function calls across files.

Fallback to jedi for symbol resolution if PyCG unavailable.
"""

import logging
import subprocess
import json
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger("ships.intelligence")

# Check for PyCG availability
try:
    import pycg
    from pycg.pycg import CallGraphGenerator
    from pycg import formats
    PYCG_AVAILABLE = True
except ImportError:
    PYCG_AVAILABLE = False
    logger.warning("[PYTHON_ANALYZER] pycg not installed, call graph generation limited")

# Check for jedi availability
try:
    import jedi
    JEDI_AVAILABLE = True
except ImportError:
    JEDI_AVAILABLE = False


class PythonCallGraphAnalyzer:
    """
    Python-specific call graph analyzer using PyCG.
    
    PyCG provides accurate inter-procedural call graphs by analyzing
    assignment relations between functions, variables, classes, and modules.
    """
    
    def __init__(self):
        self.cache: Dict[str, Any] = {}
    
    def analyze_project(self, project_path: str, entry_point: Optional[str] = None) -> Dict[str, Any]:
        """
        Analyze Python project and generate call graph.
        
        Args:
            project_path: Root directory of Python project
            entry_point: Optional entry point file (e.g., 'main.py')
            
        Returns:
            Dict with functions and their call relationships
        """
        root = Path(project_path)
        
        # Find all Python files
        python_files = list(root.rglob("*.py"))
        
        # Filter out test files and common ignore patterns
        ignore_patterns = ["test_", "_test.py", "tests/", ".venv/", "venv/", "__pycache__/"]
        python_files = [
            f for f in python_files 
            if not any(pattern in str(f) for pattern in ignore_patterns)
        ]
        
        if not python_files:
            return {"success": False, "error": "No Python files found"}
        
        # Convert to string paths
        file_paths = [str(f) for f in python_files]
        
        # Determine entry point
        if not entry_point:
            # Try common entry points
            candidates = ["main.py", "app.py", "__main__.py", "run.py"]
            for candidate in candidates:
                candidate_path = root / candidate
                if candidate_path.exists():
                    entry_point = str(candidate_path)
                    break
            
            # If no entry point, use first file
            if not entry_point and file_paths:
                entry_point = file_paths[0]
        
        if PYCG_AVAILABLE:
            return self._analyze_with_pycg(file_paths, entry_point)
        else:
            return self._analyze_basic(root, python_files)
    
    def _analyze_with_pycg(self, files: List[str], entry_point: str) -> Dict[str, Any]:
        """Use PyCG for accurate call graph generation."""
        try:
            logger.info(f"[PYTHON_ANALYZER] Running PyCG on {len(files)} files")
            
            # Initialize PyCG
            cg = CallGraphGenerator(
                files,
                entry_point,
                max_iter=-1,  # No limit on iterations
                operation="call-graph"
            )
            
            # Run analysis
            cg.analyze()
            
            # Get output
            output = cg.output()
            
            # Transform to our format
            functions = {}
            
            for caller, callees in output.items():
                # Parse module.function format
                parts = caller.rsplit(".", 1)
                if len(parts) == 2:
                    module, func_name = parts
                else:
                    module = ""
                    func_name = caller
                
                calls = []
                for callee in callees:
                    callee_parts = callee.rsplit(".", 1)
                    if len(callee_parts) == 2:
                        callee_module, callee_func = callee_parts
                    else:
                        callee_module = ""
                        callee_func = callee
                    
                    calls.append({
                        "function": callee_func,
                        "module": callee_module,
                        "qualified_name": callee
                    })
                
                functions[caller] = {
                    "name": func_name,
                    "module": module,
                    "calls": calls,
                    "called_by": []  # Will be populated in post-processing
                }
            
            # Post-process: populate called_by
            for caller, data in functions.items():
                for call in data["calls"]:
                    callee = call["qualified_name"]
                    if callee in functions:
                        functions[callee]["called_by"].append({
                            "function": data["name"],
                            "module": data["module"],
                            "qualified_name": caller
                        })
            
            logger.info(f"[PYTHON_ANALYZER] Extracted {len(functions)} functions from call graph")
            
            return {
                "success": True,
                "language": "python",
                "analyzer": "pycg",
                "functions": functions,
                "stats": {
                    "total_functions": len(functions),
                    "total_calls": sum(len(f["calls"]) for f in functions.values())
                }
            }
            
        except Exception as e:
            logger.error(f"[PYTHON_ANALYZER] PyCG analysis failed: {e}")
            return {"success": False, "error": str(e), "analyzer": "pycg"}
    
    def _analyze_basic(self, root: Path, files: List[Path]) -> Dict[str, Any]:
        """Basic analysis using jedi or AST when PyCG unavailable."""
        import ast
        
        functions = {}
        
        for file_path in files:
            try:
                content = file_path.read_text(encoding="utf-8")
                tree = ast.parse(content)
                
                module_name = str(file_path.relative_to(root)).replace("/", ".").replace("\\", ".")[:-3]
                
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        qualified_name = f"{module_name}.{node.name}"
                        
                        # Find function calls within this function
                        calls = []
                        for child in ast.walk(node):
                            if isinstance(child, ast.Call):
                                if isinstance(child.func, ast.Name):
                                    calls.append({
                                        "function": child.func.id,
                                        "module": "",
                                        "qualified_name": child.func.id
                                    })
                                elif isinstance(child.func, ast.Attribute):
                                    calls.append({
                                        "function": child.func.attr,
                                        "module": "",
                                        "qualified_name": child.func.attr
                                    })
                        
                        functions[qualified_name] = {
                            "name": node.name,
                            "module": module_name,
                            "file": str(file_path.relative_to(root)),
                            "line": node.lineno,
                            "calls": calls,
                            "called_by": []
                        }
                        
            except Exception as e:
                logger.warning(f"[PYTHON_ANALYZER] Failed to parse {file_path}: {e}")
        
        logger.info(f"[PYTHON_ANALYZER] Basic analysis found {len(functions)} functions")
        
        return {
            "success": True,
            "language": "python",
            "analyzer": "ast",
            "functions": functions,
            "stats": {
                "total_functions": len(functions),
                "total_calls": sum(len(f["calls"]) for f in functions.values())
            }
        }
    
    def get_function_info(self, project_path: str, function_name: str) -> Optional[Dict]:
        """Get detailed info about a specific function using jedi."""
        if not JEDI_AVAILABLE:
            return None
        
        # Use jedi for symbol resolution
        # This would require knowing the file location
        return None
