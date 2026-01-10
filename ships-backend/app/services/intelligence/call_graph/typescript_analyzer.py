"""
TypeScript/JavaScript Call Graph Analyzer

Uses dependency-cruiser for module-level dependencies.
For function-level call graphs, uses a Node.js sidecar with the TypeScript compiler API.
"""

import logging
import subprocess
import json
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger("ships.intelligence")


class TypeScriptCallGraphAnalyzer:
    """
    TypeScript/JavaScript call graph analyzer.
    
    Uses:
    - dependency-cruiser for module-level dependencies (npm package)
    - TypeScript compiler API for function-level analysis (Node.js sidecar)
    """
    
    def __init__(self):
        self.cache: Dict[str, Any] = {}
    
    def analyze_project(self, project_path: str) -> Dict[str, Any]:
        """
        Analyze TypeScript/JavaScript project.
        
        Args:
            project_path: Root directory of the project
            
        Returns:
            Dict with modules and their dependencies
        """
        root = Path(project_path)
        
        # Find source directory
        src_dirs = ["src", "app", "lib", "."]
        source_dir = None
        for src in src_dirs:
            if (root / src).exists():
                source_dir = root / src
                break
        
        if not source_dir:
            return {"success": False, "error": "No source directory found"}
        
        # Try dependency-cruiser first (module-level)
        result = self._run_dependency_cruiser(root, source_dir)
        
        if not result.get("success"):
            # Fallback to basic analysis
            result = self._analyze_basic(root)
        
        return result
    
    def _run_dependency_cruiser(self, root: Path, source_dir: Path) -> Dict[str, Any]:
        """Run dependency-cruiser for module dependencies."""
        try:
            # Check if dependency-cruiser is installed
            cmd = [
                "npx", "-y", "dependency-cruiser",
                "--output-type", "json",
                str(source_dir.relative_to(root))
            ]
            
            logger.info(f"[TS_ANALYZER] Running dependency-cruiser on {source_dir}")
            
            result = subprocess.run(
                cmd,
                cwd=str(root),
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode != 0:
                logger.warning(f"[TS_ANALYZER] dependency-cruiser failed: {result.stderr}")
                return {"success": False, "error": result.stderr}
            
            # Parse JSON output
            data = json.loads(result.stdout)
            
            # Transform to our format
            modules = {}
            edges = []
            
            for module in data.get("modules", []):
                source = module.get("source", "")
                
                dependencies = []
                for dep in module.get("dependencies", []):
                    resolved = dep.get("resolved", dep.get("module", ""))
                    dep_type = "external" if dep.get("coreModule") or dep.get("externalPackage") else "internal"
                    
                    dependencies.append({
                        "module": resolved,
                        "type": dep_type
                    })
                    
                    edges.append({
                        "from": source,
                        "to": resolved,
                        "type": "import"
                    })
                
                modules[source] = {
                    "path": source,
                    "dependencies": dependencies,
                    "dependents": []  # Populated in post-processing
                }
            
            # Post-process: populate dependents
            for source, mod_data in modules.items():
                for dep in mod_data["dependencies"]:
                    dep_module = dep["module"]
                    if dep_module in modules:
                        modules[dep_module]["dependents"].append(source)
            
            # Detect circular dependencies
            circular = self._detect_circular_deps(modules)
            
            logger.info(f"[TS_ANALYZER] Found {len(modules)} modules, {len(edges)} edges")
            
            return {
                "success": True,
                "language": "typescript",
                "analyzer": "dependency-cruiser",
                "modules": modules,
                "edges": edges,
                "circular_dependencies": circular,
                "stats": {
                    "total_modules": len(modules),
                    "total_edges": len(edges),
                    "circular_count": len(circular)
                }
            }
            
        except subprocess.TimeoutExpired:
            logger.error("[TS_ANALYZER] dependency-cruiser timed out")
            return {"success": False, "error": "Analysis timed out"}
        except json.JSONDecodeError as e:
            logger.error(f"[TS_ANALYZER] Failed to parse output: {e}")
            return {"success": False, "error": f"Invalid JSON: {e}"}
        except Exception as e:
            logger.error(f"[TS_ANALYZER] Analysis failed: {e}")
            return {"success": False, "error": str(e)}
    
    def _detect_circular_deps(self, modules: Dict[str, Any]) -> List[List[str]]:
        """Detect circular dependencies using DFS."""
        visited = set()
        rec_stack = set()
        cycles = []
        
        def dfs(node: str, path: List[str]) -> None:
            visited.add(node)
            rec_stack.add(node)
            
            if node not in modules:
                rec_stack.discard(node)
                return
            
            for dep in modules[node].get("dependencies", []):
                dep_module = dep["module"]
                
                if dep_module not in visited:
                    dfs(dep_module, path + [dep_module])
                elif dep_module in rec_stack:
                    # Found cycle
                    cycle_start = path.index(dep_module) if dep_module in path else len(path)
                    cycle = path[cycle_start:] + [dep_module]
                    if cycle not in cycles:
                        cycles.append(cycle)
            
            rec_stack.discard(node)
        
        for module in modules:
            if module not in visited:
                dfs(module, [module])
        
        return cycles
    
    def _analyze_basic(self, root: Path) -> Dict[str, Any]:
        """Basic analysis using regex when dependency-cruiser unavailable."""
        import re
        
        modules = {}
        
        # Find all TS/JS files
        extensions = ["*.ts", "*.tsx", "*.js", "*.jsx"]
        for ext in extensions:
            for file_path in root.rglob(ext):
                # Skip node_modules
                if "node_modules" in str(file_path):
                    continue
                
                try:
                    content = file_path.read_text(encoding="utf-8")
                    rel_path = str(file_path.relative_to(root))
                    
                    # Find imports using regex
                    import_pattern = r"import\s+.*?from\s+['\"](.+?)['\"]"
                    require_pattern = r"require\s*\(['\"](.+?)['\"]\)"
                    
                    imports = re.findall(import_pattern, content)
                    imports.extend(re.findall(require_pattern, content))
                    
                    dependencies = []
                    for imp in imports:
                        dep_type = "external" if not imp.startswith(".") else "internal"
                        dependencies.append({
                            "module": imp,
                            "type": dep_type
                        })
                    
                    modules[rel_path] = {
                        "path": rel_path,
                        "dependencies": dependencies,
                        "dependents": []
                    }
                    
                except Exception as e:
                    logger.warning(f"[TS_ANALYZER] Failed to parse {file_path}: {e}")
        
        logger.info(f"[TS_ANALYZER] Basic analysis found {len(modules)} modules")
        
        return {
            "success": True,
            "language": "typescript",
            "analyzer": "regex",
            "modules": modules,
            "edges": [],
            "circular_dependencies": [],
            "stats": {
                "total_modules": len(modules)
            }
        }
