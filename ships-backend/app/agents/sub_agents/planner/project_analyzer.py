"""
Project Analyzer

Analyzes project directory to determine:
- If scaffolding is needed
- What framework to use
- What dependencies are installed
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger("ships.planner")


class ProjectType(str, Enum):
    """Types of projects we can detect/scaffold."""
    EMPTY = "empty"
    REACT_VITE = "react-vite"
    REACT_CRA = "react-cra"
    NEXTJS = "nextjs"
    VUE = "vue"
    SVELTE = "svelte"
    PYTHON = "python"
    FASTAPI = "fastapi"
    STATIC_HTML = "static-html"
    UNKNOWN = "unknown"


@dataclass
class ProjectAnalysis:
    """Result of project analysis."""
    project_type: ProjectType
    needs_scaffolding: bool
    has_package_json: bool
    has_node_modules: bool
    has_requirements_txt: bool
    has_pyproject_toml: bool
    has_index_html: bool
    detected_framework: Optional[str] = None
    scaffold_command: Optional[str] = None
    install_command: Optional[str] = None
    recommendation: str = ""


def analyze_project(project_path: str, user_request: str = "") -> ProjectAnalysis:
    """
    Analyze a project directory to determine its state.
    
    Args:
        project_path: Path to the project directory
        user_request: The user's request (for framework hints)
        
    Returns:
        ProjectAnalysis with scaffolding recommendations
    """
    path = Path(project_path)
    
    if not path.exists() or not path.is_dir():
        return ProjectAnalysis(
            project_type=ProjectType.EMPTY,
            needs_scaffolding=True,
            has_package_json=False,
            has_node_modules=False,
            has_requirements_txt=False,
            has_pyproject_toml=False,
            has_index_html=False,
            recommendation="Project path does not exist"
        )
    
    # Check for common files
    files = set(f.name for f in path.iterdir() if f.is_file())
    dirs = set(d.name for d in path.iterdir() if d.is_dir())
    
    has_package_json = "package.json" in files
    has_node_modules = "node_modules" in dirs
    has_requirements_txt = "requirements.txt" in files
    has_pyproject_toml = "pyproject.toml" in files
    has_index_html = "index.html" in files
    has_src = "src" in dirs
    
    # Determine project type
    project_type = ProjectType.EMPTY
    detected_framework = None
    scaffold_command = None
    install_command = None
    needs_scaffolding = False
    
    # Check if directory is empty or near-empty
    is_empty = len(files) == 0 and len(dirs) == 0
    is_near_empty = len(files) <= 2 and len(dirs) == 0  # e.g., just README
    
    if is_empty or is_near_empty:
        # Empty project - needs scaffolding
        needs_scaffolding = True
        project_type = ProjectType.EMPTY
        
        # Infer framework from user request
        framework = _infer_framework_from_request(user_request)
        detected_framework = framework
        scaffold_command = _get_scaffold_command(framework)
        install_command = "npm install" if framework != "python" else "pip install -r requirements.txt"
        
    elif has_package_json:
        # Has package.json - check what kind
        project_type, detected_framework = _analyze_package_json(path / "package.json")
        
        if not has_node_modules:
            # Needs npm install
            needs_scaffolding = True
            install_command = "npm install"
            
    elif has_requirements_txt or has_pyproject_toml:
        # Python project
        project_type = ProjectType.PYTHON
        detected_framework = "python"
        
        if not (path / ".venv").exists() and not (path / "venv").exists():
            needs_scaffolding = True
            install_command = "pip install -r requirements.txt" if has_requirements_txt else "pip install -e ."
            
    elif has_index_html:
        # Static HTML project
        project_type = ProjectType.STATIC_HTML
        detected_framework = "html"
        needs_scaffolding = False
    else:
        project_type = ProjectType.UNKNOWN
    
    return ProjectAnalysis(
        project_type=project_type,
        needs_scaffolding=needs_scaffolding,
        has_package_json=has_package_json,
        has_node_modules=has_node_modules,
        has_requirements_txt=has_requirements_txt,
        has_pyproject_toml=has_pyproject_toml,
        has_index_html=has_index_html,
        detected_framework=detected_framework,
        scaffold_command=scaffold_command,
        install_command=install_command,
        recommendation=_get_recommendation(needs_scaffolding, scaffold_command, install_command)
    )


def _infer_framework_from_request(request: str) -> str:
    """Infer the desired framework from user's request."""
    request_lower = request.lower()
    
    # Explicit mentions
    if "next" in request_lower or "nextjs" in request_lower:
        return "nextjs"
    if "vue" in request_lower:
        return "vue"
    if "svelte" in request_lower:
        return "svelte"
    if "angular" in request_lower:
        return "angular"
    if "python" in request_lower or "fastapi" in request_lower or "flask" in request_lower:
        return "python"
    if "static" in request_lower or "html" in request_lower:
        return "html"
    
    # Default to React + Vite (most versatile)
    return "react-vite"


def _get_scaffold_command(framework: str) -> str:
    """Get the scaffold command for a framework."""
    commands = {
        "react-vite": "npx create-vite@latest . --template react-ts",
        "react": "npx create-vite@latest . --template react-ts",
        "nextjs": "npx create-next-app@latest . --typescript --tailwind --eslint --app --src-dir --import-alias \"@/*\"",
        "vue": "npx create-vue@latest .",
        "svelte": "npx sv create .",
        "angular": "npx @angular/cli new . --skip-git",
        "python": "pip install fastapi uvicorn",
        "html": "",  # No scaffold needed
    }
    return commands.get(framework, "npx create-vite@latest . --template react-ts")


def _analyze_package_json(package_json_path: Path) -> Tuple[ProjectType, str]:
    """Analyze package.json to determine project type."""
    try:
        with open(package_json_path, "r") as f:
            pkg = json.load(f)
        
        deps = pkg.get("dependencies", {})
        dev_deps = pkg.get("devDependencies", {})
        all_deps = {**deps, **dev_deps}
        
        if "next" in all_deps:
            return ProjectType.NEXTJS, "nextjs"
        if "vue" in all_deps:
            return ProjectType.VUE, "vue"
        if "svelte" in all_deps:
            return ProjectType.SVELTE, "svelte"
        if "react" in all_deps:
            if "vite" in all_deps:
                return ProjectType.REACT_VITE, "react-vite"
            return ProjectType.REACT_CRA, "react"
        
        return ProjectType.UNKNOWN, "node"
        
    except Exception:
        return ProjectType.UNKNOWN, "unknown"


def _get_recommendation(needs_scaffolding: bool, scaffold_cmd: Optional[str], install_cmd: Optional[str]) -> str:
    """Generate a human-readable recommendation."""
    if not needs_scaffolding:
        return "Project is ready to use"
    
    parts = []
    if scaffold_cmd:
        parts.append(f"Run: {scaffold_cmd}")
    if install_cmd:
        parts.append(f"Then run: {install_cmd}")
    
    return " → ".join(parts) if parts else "No action needed"


def create_scaffolding_task(analysis: ProjectAnalysis) -> Optional[Dict[str, Any]]:
    """
    Create a scaffolding task based on project analysis.
    
    Returns:
        Task dict if scaffolding is needed, None otherwise
    """
    if not analysis.needs_scaffolding:
        return None
    
    commands = []
    acceptance_criteria = []
    
    if analysis.scaffold_command:
        commands.append(analysis.scaffold_command)
        acceptance_criteria.append("Project scaffolded with framework files")
    
    if analysis.install_command:
        commands.append(analysis.install_command)
        acceptance_criteria.append("Dependencies installed successfully")
    
    if not commands:
        return None
    
    return {
        "id": "task_scaffold_0",
        "title": f"Setup Project: {analysis.detected_framework or 'Initialize'}",
        "description": f"Scaffold the project with {analysis.detected_framework or 'starter files'} and install dependencies.",
        "complexity": "small",
        "priority": "critical",  # Must be done first
        "target_area": "config",
        "order": 0,  # First task
        "acceptance_criteria": [{"description": ac} for ac in acceptance_criteria],
        "expected_outputs": [
            {"path": "package.json", "action": "create"},
            {"path": "node_modules/", "action": "create"},
        ] if analysis.detected_framework != "python" else [
            {"path": "requirements.txt", "action": "create"},
        ],
        "estimated_minutes": 5,
        "terminal_commands": commands,
        "is_scaffolding_task": True,
    }
