"""
Call Graph Merger

Combines language-specific call graphs into unified function_call_graph.json.
"""

import logging
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from .python_analyzer import PythonCallGraphAnalyzer
from .typescript_analyzer import TypeScriptCallGraphAnalyzer

logger = logging.getLogger("ships.intelligence")


class CallGraphMerger:
    """
    Merges call graphs from multiple language-specific analyzers
    into a unified function_call_graph.json artifact.
    """
    
    def __init__(self):
        self.python_analyzer = PythonCallGraphAnalyzer()
        self.ts_analyzer = TypeScriptCallGraphAnalyzer()
    
    def analyze_project(self, project_path: str) -> Dict[str, Any]:
        """
        Analyze project with all applicable analyzers and merge results.
        
        Args:
            project_path: Root directory of the project
            
        Returns:
            Unified call graph with functions from all languages
        """
        root = Path(project_path)
        
        # Detect project type
        has_python = any(root.rglob("*.py"))
        has_typescript = any(root.rglob("*.ts")) or any(root.rglob("*.tsx"))
        has_javascript = any(root.rglob("*.js")) or any(root.rglob("*.jsx"))
        
        all_functions = {}
        all_modules = {}
        all_edges = []
        languages_analyzed = []
        errors = []
        
        # Run Python analyzer
        if has_python:
            logger.info("[MERGER] Analyzing Python files...")
            py_result = self.python_analyzer.analyze_project(project_path)
            
            if py_result.get("success"):
                languages_analyzed.append("python")
                
                # Merge functions
                for name, data in py_result.get("functions", {}).items():
                    all_functions[f"py:{name}"] = {
                        **data,
                        "language": "python",
                        "qualified_name": name
                    }
            else:
                errors.append(f"Python: {py_result.get('error', 'Unknown error')}")
        
        # Run TypeScript/JavaScript analyzer
        if has_typescript or has_javascript:
            lang = "typescript" if has_typescript else "javascript"
            logger.info(f"[MERGER] Analyzing {lang} files...")
            
            ts_result = self.ts_analyzer.analyze_project(project_path)
            
            if ts_result.get("success"):
                languages_analyzed.append(lang)
                
                # Merge modules (TS analyzer gives module-level deps)
                for name, data in ts_result.get("modules", {}).items():
                    all_modules[f"ts:{name}"] = {
                        **data,
                        "language": lang
                    }
                
                # Add edges
                for edge in ts_result.get("edges", []):
                    all_edges.append({
                        **edge,
                        "language": lang
                    })
            else:
                errors.append(f"{lang}: {ts_result.get('error', 'Unknown error')}")
        
        if not languages_analyzed:
            return {
                "success": False,
                "error": "No supported languages found",
                "errors": errors
            }
        
        logger.info(f"[MERGER] Merged call graphs for: {languages_analyzed}")
        
        return {
            "version": "1.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "success": True,
            "languages": languages_analyzed,
            "functions": all_functions,
            "modules": all_modules,
            "edges": all_edges,
            "stats": {
                "total_functions": len(all_functions),
                "total_modules": len(all_modules),
                "total_edges": len(all_edges)
            },
            "errors": errors if errors else None
        }
    
    def save_artifact(self, project_path: str, output_path: Optional[str] = None) -> str:
        """Analyze project and save to function_call_graph.json."""
        result = self.analyze_project(project_path)
        
        # Default to .ships/function_call_graph.json
        if not output_path:
            output_path = Path(project_path) / ".ships" / "function_call_graph.json"
        else:
            output_path = Path(output_path)
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
        
        logger.info(f"[MERGER] Saved function_call_graph.json to {output_path}")
        
        return str(output_path)
