"""
ShipS* Planner Tools

LangChain tools for the Planner agent using @tool decorator.
These are used with LangGraph's create_react_agent.
"""

from typing import Dict, Any, List, Optional
from langchain_core.tools import tool
import uuid
from datetime import datetime


@tool
def extract_scope(intent: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract scope boundaries from a structured intent.
    
    Identifies what's in scope, out of scope, and constraints.
    
    Args:
        intent: StructuredIntent with goals, non_goals, constraints
        
    Returns:
        Dict with in_scope, out_of_scope, constraints, and boundaries
    """
    goals = intent.get("goals", [])
    non_goals = intent.get("non_goals", [])
    constraints = intent.get("constraints", [])
    
    # Extract features from goals
    in_scope = []
    for goal in goals:
        if isinstance(goal, dict):
            in_scope.append(goal.get("description", str(goal)))
        else:
            in_scope.append(str(goal))
    
    return {
        "in_scope": in_scope,
        "out_of_scope": non_goals,
        "constraints": constraints,
        "has_clear_boundaries": len(non_goals) > 0,
        "estimated_complexity": "high" if len(in_scope) > 5 else "medium" if len(in_scope) > 2 else "low"
    }


@tool
def design_folder_structure(
    project_type: str,
    features: List[str],
    framework: str = "react"
) -> Dict[str, Any]:
    """
    Design a folder structure for the project.
    
    Creates a FolderMap artifact based on project type and features.
    
    Args:
        project_type: Type of project (web_app, api, library)
        features: List of features to include
        framework: Framework being used
        
    Returns:
        FolderMap artifact as dict
    """
    entries = []
    
    # Base structure
    if project_type == "web_app":
        base_dirs = ["src", "public", "tests"]
        if framework == "react":
            base_dirs.extend(["src/components", "src/hooks", "src/pages", "src/utils"])
        elif framework == "next":
            base_dirs.extend(["src/app", "src/components", "src/lib"])
    elif project_type == "api":
        base_dirs = ["src", "tests", "src/routes", "src/models", "src/services"]
    else:
        base_dirs = ["src", "tests", "lib"]
    
    for dir_path in base_dirs:
        entries.append({
            "path": dir_path,
            "is_directory": True,
            "purpose": f"Contains {dir_path.split('/')[-1]} files"
        })
    
    # Add feature-specific directories
    for feature in features:
        feature_dir = f"src/features/{feature.lower().replace(' ', '_')}"
        entries.append({
            "path": feature_dir,
            "is_directory": True,
            "purpose": f"Feature: {feature}"
        })
    
    return {
        "id": f"foldermap_{uuid.uuid4().hex[:8]}",
        "entries": entries,
        "root_path": "./",
        "total_directories": len([e for e in entries if e.get("is_directory")]),
        "framework": framework
    }


@tool
def create_task(
    title: str,
    description: str,
    acceptance_criteria: List[str],
    priority: int = 1,
    estimated_hours: float = 1.0,
    dependencies: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Create a Task artifact for the Coder to implement.
    
    Args:
        title: Task title
        description: Detailed description
        acceptance_criteria: List of criteria for completion
        priority: Priority level (1-5)
        estimated_hours: Estimated implementation time
        dependencies: IDs of tasks this depends on
        
    Returns:
        Task artifact as dict
    """
    return {
        "id": f"task_{uuid.uuid4().hex[:8]}",
        "title": title,
        "description": description,
        "acceptance_criteria": [
            {"description": c, "is_met": False} for c in acceptance_criteria
        ],
        "priority": priority,
        "estimated_hours": estimated_hours,
        "dependencies": dependencies or [],
        "status": "pending",
        "created_at": datetime.utcnow().isoformat()
    }


@tool
def create_task_list(
    tasks: List[Dict[str, Any]],
    plan_id: str
) -> Dict[str, Any]:
    """
    Create a TaskList artifact from individual tasks.
    
    Orders tasks by priority and dependencies.
    
    Args:
        tasks: List of Task dicts
        plan_id: ID of the parent plan
        
    Returns:
        TaskList artifact as dict
    """
    # Sort by priority then dependencies
    sorted_tasks = sorted(tasks, key=lambda t: (t.get("priority", 5), len(t.get("dependencies", []))))
    
    return {
        "id": f"tasklist_{uuid.uuid4().hex[:8]}",
        "plan_id": plan_id,
        "tasks": sorted_tasks,
        "total_tasks": len(tasks),
        "total_estimated_hours": sum(t.get("estimated_hours", 0) for t in tasks),
        "created_at": datetime.utcnow().isoformat()
    }


@tool
def define_api_contract(
    endpoint: str,
    method: str,
    description: str,
    request_schema: Optional[Dict[str, Any]] = None,
    response_schema: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Define an API endpoint contract.
    
    Args:
        endpoint: API endpoint path
        method: HTTP method
        description: What the endpoint does
        request_schema: Expected request body schema
        response_schema: Expected response schema
        
    Returns:
        API contract definition as dict
    """
    return {
        "id": f"api_{uuid.uuid4().hex[:8]}",
        "endpoint": endpoint,
        "method": method.upper(),
        "description": description,
        "request_schema": request_schema or {},
        "response_schema": response_schema or {},
        "auth_required": "/api/" in endpoint
    }


@tool
def create_dependency_plan(
    runtime_deps: List[Dict[str, Any]],
    dev_deps: List[Dict[str, Any]],
    package_manager: str = "npm"
) -> Dict[str, Any]:
    """
    Create a DependencyPlan artifact.
    
    Args:
        runtime_deps: List of runtime dependencies
        dev_deps: List of dev dependencies
        package_manager: Package manager to use
        
    Returns:
        DependencyPlan artifact as dict
    """
    return {
        "id": f"deps_{uuid.uuid4().hex[:8]}",
        "runtime_dependencies": runtime_deps,
        "dev_dependencies": dev_deps,
        "package_manager": package_manager,
        "install_command": f"{package_manager} install",
        "total_packages": len(runtime_deps) + len(dev_deps)
    }


@tool
def assess_risks(
    features: List[str],
    constraints: List[str],
    dependencies: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Assess risks for the plan.
    
    Args:
        features: Features being implemented
        constraints: Project constraints
        dependencies: External dependencies
        
    Returns:
        RiskReport artifact as dict
    """
    risks = []
    
    # Check for complex features
    if len(features) > 5:
        risks.append({
            "id": f"risk_{uuid.uuid4().hex[:4]}",
            "category": "scope",
            "description": "Large number of features may lead to scope creep",
            "severity": "medium",
            "mitigation": "Prioritize and potentially phase implementation"
        })
    
    # Check for external dependencies
    if len(dependencies) > 10:
        risks.append({
            "id": f"risk_{uuid.uuid4().hex[:4]}",
            "category": "dependency",
            "description": "High number of external dependencies",
            "severity": "low",
            "mitigation": "Review each dependency for necessity"
        })
    
    return {
        "id": f"riskreport_{uuid.uuid4().hex[:8]}",
        "risks": risks,
        "overall_risk_level": "high" if any(r["severity"] == "high" for r in risks) else "medium" if risks else "low",
        "total_risks": len(risks)
    }


# Import write_file_to_disk from coder tools (now modular)
from app.agents.tools.coder import write_file_to_disk

# Export all tools for the Planner agent
PLANNER_TOOLS = [
    extract_scope,
    design_folder_structure,
    create_task,
    create_task_list,
    define_api_contract,
    create_dependency_plan,
    assess_risks,
    write_file_to_disk,  # Planner can now write artifacts to disk
]
