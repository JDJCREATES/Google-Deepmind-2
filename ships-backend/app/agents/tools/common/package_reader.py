"""
Package/Dependency Reader Utility

Library-based reading of actual project dependencies from:
- package.json (npm/node projects)
- requirements.txt (Python projects)
- pyproject.toml (Python projects)

This provides GROUND TRUTH for what's installed, not LLM hallucinations.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
import re

logger = logging.getLogger("ships.package_reader")


def read_package_json(project_path: str) -> Dict[str, Any]:
    """
    Read package.json and return structured dependency data.
    
    Returns:
        Dict with:
        - name: Project name
        - version: Project version
        - runtime_dependencies: List of {name, version} dicts
        - dev_dependencies: List of {name, version} dicts
        - scripts: Dict of npm scripts
        - success: bool
    """
    pkg_path = Path(project_path) / "package.json"
    
    if not pkg_path.exists():
        return {"success": False, "error": "package.json not found"}
    
    try:
        with open(pkg_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # Parse dependencies
        runtime = []
        for name, version in data.get("dependencies", {}).items():
            runtime.append({"name": name, "version": version})
        
        dev = []
        for name, version in data.get("devDependencies", {}).items():
            dev.append({"name": name, "version": version})
        
        logger.info(f"[PACKAGE_READER] Read package.json: {len(runtime)} runtime, {len(dev)} dev dependencies")
        
        return {
            "success": True,
            "package_manager": "npm",
            "name": data.get("name", ""),
            "version": data.get("version", "0.0.0"),
            "runtime_dependencies": runtime,
            "dev_dependencies": dev,
            "scripts": data.get("scripts", {}),
        }
        
    except json.JSONDecodeError as e:
        logger.error(f"[PACKAGE_READER] Invalid JSON in package.json: {e}")
        return {"success": False, "error": f"Invalid JSON: {e}"}
    except Exception as e:
        logger.error(f"[PACKAGE_READER] Failed to read package.json: {e}")
        return {"success": False, "error": str(e)}


def read_requirements_txt(project_path: str) -> Dict[str, Any]:
    """
    Read requirements.txt and return structured dependency data.
    
    Returns:
        Dict with:
        - runtime_dependencies: List of {name, version} dicts
        - success: bool
    """
    req_path = Path(project_path) / "requirements.txt"
    
    if not req_path.exists():
        return {"success": False, "error": "requirements.txt not found"}
    
    try:
        with open(req_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        dependencies = []
        for line in lines:
            line = line.strip()
            # Skip comments and empty lines
            if not line or line.startswith("#"):
                continue
            
            # Parse: package==version, package>=version, package
            match = re.match(r"([a-zA-Z0-9_-]+)([<>=!~]+)?(.+)?", line)
            if match:
                name = match.group(1)
                version = (match.group(2) or "") + (match.group(3) or "latest")
                dependencies.append({"name": name, "version": version.strip()})
        
        logger.info(f"[PACKAGE_READER] Read requirements.txt: {len(dependencies)} dependencies")
        
        return {
            "success": True,
            "package_manager": "pip",
            "runtime_dependencies": dependencies,
            "dev_dependencies": [],  # requirements.txt doesn't distinguish
        }
        
    except Exception as e:
        logger.error(f"[PACKAGE_READER] Failed to read requirements.txt: {e}")
        return {"success": False, "error": str(e)}


def read_pyproject_toml(project_path: str) -> Dict[str, Any]:
    """
    Read pyproject.toml for Python dependencies.
    
    Returns structured dependency data.
    """
    pyproject_path = Path(project_path) / "pyproject.toml"
    
    if not pyproject_path.exists():
        return {"success": False, "error": "pyproject.toml not found"}
    
    try:
        import tomllib  # Python 3.11+
    except ImportError:
        try:
            import toml as tomllib  # Fallback
        except ImportError:
            return {"success": False, "error": "toml parser not available"}
    
    try:
        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)
        
        # Handle Poetry format
        poetry = data.get("tool", {}).get("poetry", {})
        if poetry:
            runtime = []
            for name, spec in poetry.get("dependencies", {}).items():
                if name == "python":
                    continue
                version = spec if isinstance(spec, str) else spec.get("version", "*")
                runtime.append({"name": name, "version": version})
            
            dev = []
            for name, spec in poetry.get("group", {}).get("dev", {}).get("dependencies", {}).items():
                version = spec if isinstance(spec, str) else spec.get("version", "*")
                dev.append({"name": name, "version": version})
            
            return {
                "success": True,
                "package_manager": "poetry",
                "name": poetry.get("name", ""),
                "version": poetry.get("version", "0.0.0"),
                "runtime_dependencies": runtime,
                "dev_dependencies": dev,
            }
        
        # Handle PEP 621 format
        project = data.get("project", {})
        if project:
            runtime = []
            for dep in project.get("dependencies", []):
                # Parse "package>=version" format
                match = re.match(r"([a-zA-Z0-9_-]+)([<>=!~\[\]]+)?(.+)?", dep)
                if match:
                    runtime.append({
                        "name": match.group(1),
                        "version": (match.group(2) or "") + (match.group(3) or "")
                    })
            
            return {
                "success": True,
                "package_manager": "pip",
                "name": project.get("name", ""),
                "version": project.get("version", "0.0.0"),
                "runtime_dependencies": runtime,
                "dev_dependencies": [],
            }
        
        return {"success": False, "error": "No recognized dependency format in pyproject.toml"}
        
    except Exception as e:
        logger.error(f"[PACKAGE_READER] Failed to read pyproject.toml: {e}")
        return {"success": False, "error": str(e)}


def read_project_dependencies(project_path: str) -> Dict[str, Any]:
    """
    Auto-detect and read project dependencies from any supported format.
    
    Tries in order:
    1. package.json (npm/node)
    2. pyproject.toml (Python modern)
    3. requirements.txt (Python legacy)
    
    Returns:
        Dict with unified dependency structure
    """
    project = Path(project_path)
    
    # Try npm first
    if (project / "package.json").exists():
        result = read_package_json(project_path)
        if result.get("success"):
            return result
    
    # Try Python pyproject.toml
    if (project / "pyproject.toml").exists():
        result = read_pyproject_toml(project_path)
        if result.get("success"):
            return result
    
    # Try requirements.txt
    if (project / "requirements.txt").exists():
        result = read_requirements_txt(project_path)
        if result.get("success"):
            return result
    
    # No dependency files found
    return {
        "success": True,
        "package_manager": None,
        "runtime_dependencies": [],
        "dev_dependencies": [],
        "note": "No dependency manifest found - new project"
    }
