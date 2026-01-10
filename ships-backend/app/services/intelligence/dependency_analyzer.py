"""
Dependency Analyzer

Generates dependency_graph.json using dependency-cruiser for module-level dependencies.
Also provides circular dependency detection and orphaned file detection.
"""

import logging
import subprocess
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

logger = logging.getLogger("ships.intelligence")


class DependencyAnalyzer:
    """
    Generates module-level dependency graphs.
    
    Uses dependency-cruiser (Node.js) for comprehensive analysis,
    with fallback to import parsing for projects without npm.
    """
    
    def __init__(self):
        self.cache: Dict[str, Any] = {}
    
    def analyze_project(self, project_path: str) -> Dict[str, Any]:
        """
        Analyze project dependencies.
        
        Args:
            project_path: Root directory of the project
            
        Returns:
            Dependency graph with nodes, edges, circular deps
        """
        root = Path(project_path)
        
        # Check if this is a Node.js project
        has_package_json = (root / "package.json").exists()
        
        if has_package_json:
            result = self._run_dependency_cruiser(root)
            if result.get("success"):
                return result
        
        # Fallback to manual analysis
        return self._analyze_manual(root)
    
    def _run_dependency_cruiser(self, root: Path) -> Dict[str, Any]:
        """Run dependency-cruiser for comprehensive analysis."""
        try:
            # Find source directory
            src_dirs = ["src", "app", "lib"]
            source_dir = "."
            for src in src_dirs:
                if (root / src).exists():
                    source_dir = src
                    break
            
            logger.info(f"[DEP_ANALYZER] Running dependency-cruiser on {source_dir}")
            
            cmd = [
                "npx", "-y", "dependency-cruiser",
                "--output-type", "json",
                source_dir
            ]
            
            result = subprocess.run(
                cmd,
                cwd=str(root),
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode != 0:
                logger.warning(f"[DEP_ANALYZER] dependency-cruiser failed: {result.stderr[:200]}")
                return {"success": False, "error": result.stderr}
            
            data = json.loads(result.stdout)
            
            return self._transform_cruiser_output(data)
            
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Timeout"}
        except json.JSONDecodeError as e:
            return {"success": False, "error": f"Invalid JSON: {e}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _transform_cruiser_output(self, data: Dict) -> Dict[str, Any]:
        """Transform dependency-cruiser output to our format."""
        nodes = {}
        edges = []
        external_deps = set()
        
        for module in data.get("modules", []):
            source = module.get("source", "")
            
            imports = []
            imported_by = []  # Populated later
            
            for dep in module.get("dependencies", []):
                resolved = dep.get("resolved", dep.get("module", ""))
                is_external = dep.get("coreModule") or dep.get("externalPackage")
                
                if is_external:
                    external_deps.add(resolved)
                
                imports.append(resolved)
                
                edges.append({
                    "from": source,
                    "to": resolved,
                    "type": "import",
                    "is_external": is_external
                })
            
            nodes[source] = {
                "type": "file",
                "imports": imports,
                "imported_by": [],
                "external_deps": list(external_deps)
            }
        
        # Populate imported_by
        for edge in edges:
            if edge["to"] in nodes and not edge["is_external"]:
                nodes[edge["to"]]["imported_by"].append(edge["from"])
        
        # Find circular dependencies
        circular = self._detect_cycles(nodes)
        
        # Find orphaned files (not imported by anyone)
        orphaned = [
            path for path, node in nodes.items()
            if not node["imported_by"] and not path.endswith("index.ts") and not path.endswith("index.js")
        ]
        
        # Find entry points
        entry_points = self._detect_entry_points(nodes)
        
        return {
            "version": "1.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "success": True,
            "analyzer": "dependency-cruiser",
            "nodes": nodes,
            "edges": edges,
            "circular_dependencies": circular,
            "orphaned_files": orphaned[:10],  # Limit to 10
            "entry_points": entry_points,
            "external_dependencies": list(external_deps),
            "stats": {
                "total_modules": len(nodes),
                "total_edges": len(edges),
                "circular_count": len(circular),
                "orphaned_count": len(orphaned),
                "external_dep_count": len(external_deps)
            }
        }
    
    def _detect_cycles(self, nodes: Dict[str, Any]) -> List[List[str]]:
        """Detect circular dependencies using DFS."""
        visited = set()
        rec_stack = set()
        cycles = []
        
        def dfs(node: str, path: List[str]) -> None:
            visited.add(node)
            rec_stack.add(node)
            
            if node not in nodes:
                rec_stack.discard(node)
                return
            
            for dep in nodes[node].get("imports", []):
                if dep not in visited:
                    dfs(dep, path + [dep])
                elif dep in rec_stack:
                    try:
                        cycle_start = path.index(dep)
                        cycle = path[cycle_start:] + [dep]
                        if len(cycle) > 1 and cycle not in cycles:
                            cycles.append(cycle)
                    except ValueError:
                        pass
            
            rec_stack.discard(node)
        
        for module in nodes:
            if module not in visited:
                dfs(module, [module])
        
        return cycles[:10]  # Limit to 10 cycles
    
    def _detect_entry_points(self, nodes: Dict[str, Any]) -> List[str]:
        """Detect likely entry points."""
        entry_patterns = ["index", "main", "app", "server", "entry"]
        
        entry_points = []
        for path in nodes:
            name = Path(path).stem.lower()
            if any(pattern in name for pattern in entry_patterns):
                entry_points.append(path)
        
        return entry_points[:5]  # Limit to 5
    
    def _analyze_manual(self, root: Path) -> Dict[str, Any]:
        """Manual analysis using import parsing."""
        import re
        
        nodes = {}
        edges = []
        
        extensions = ["*.py", "*.ts", "*.tsx", "*.js", "*.jsx"]
        ignore_dirs = {"node_modules", ".venv", "venv", "__pycache__", "dist", "build"}
        
        for ext in extensions:
            for file_path in root.rglob(ext):
                if any(ignore in str(file_path) for ignore in ignore_dirs):
                    continue
                
                try:
                    content = file_path.read_text(encoding="utf-8")
                    rel_path = str(file_path.relative_to(root))
                    
                    # Find imports
                    imports = []
                    
                    # Python imports
                    if file_path.suffix == ".py":
                        import_pattern = r"^(?:from\s+(\S+)|import\s+(\S+))"
                        for match in re.finditer(import_pattern, content, re.MULTILINE):
                            module = match.group(1) or match.group(2)
                            if module:
                                imports.append(module.split(".")[0])
                    
                    # JS/TS imports
                    else:
                        import_pattern = r"import\s+.*?from\s+['\"](.+?)['\"]"
                        require_pattern = r"require\s*\(['\"](.+?)['\"]\)"
                        
                        imports.extend(re.findall(import_pattern, content))
                        imports.extend(re.findall(require_pattern, content))
                    
                    nodes[rel_path] = {
                        "type": "file",
                        "imports": imports,
                        "imported_by": []
                    }
                    
                except Exception as e:
                    logger.warning(f"[DEP_ANALYZER] Failed to parse {file_path}: {e}")
        
        return {
            "version": "1.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "success": True,
            "analyzer": "manual",
            "nodes": nodes,
            "edges": edges,
            "circular_dependencies": [],
            "orphaned_files": [],
            "entry_points": [],
            "stats": {
                "total_modules": len(nodes)
            }
        }
    
    def save_artifact(self, project_path: str, output_path: Optional[str] = None) -> str:
        """Analyze project and save to dependency_graph.json."""
        result = self.analyze_project(project_path)
        
        if not output_path:
            output_path = Path(project_path) / ".ships" / "dependency_graph.json"
        else:
            output_path = Path(output_path)
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
        
        logger.info(f"[DEP_ANALYZER] Saved dependency_graph.json to {output_path}")
        
        return str(output_path)
