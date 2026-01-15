"""
ShipS* Validator Tool Functions

@tool decorated LangChain tools for the Validator agent.
Uses the validation layers from layers.py to perform checks.
"""

from typing import Dict, Any, List
from langchain_core.tools import tool

# Import directly from models.py to avoid circular import through __init__
from app.agents.sub_agents.validator.models import (
    ValidationStatus, FailureLayer, ViolationSeverity,
    Violation, ValidationReport, ValidatorConfig,
)
from app.agents.tools.validator.layers import (
    StructuralLayer, CompletenessLayer, DependencyLayer, ScopeLayer,
)
from app.api.runs.router import broadcast_event


@tool
def validate_structural(
    file_changes: List[Dict[str, Any]],
    folder_map: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Validate file changes against folder map structure.
    
    Checks:
    - Are files placed in allowed directories?
    - Are protected paths untouched?
    - Is there cross-layer leakage?
    
    Args:
        file_changes: List of file changes with path, operation, content
        folder_map: Expected folder structure from Planner
        
    Returns:
        Dict with passed status and violations list
    """
    config = ValidatorConfig()
    layer = StructuralLayer(config)
    
    result = layer.validate({
        "file_changes": file_changes,
        "folder_map": folder_map
    })
    
    return {
        "passed": result.passed,
        "layer": "structural",
        "violations": [v.model_dump() for v in result.violations],
        "checks_run": result.checks_run
    }


@tool
def validate_completeness(file_changes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Validate code completeness - no TODOs, placeholders, or stubs.
    
    Checks:
    - Are there TODO/FIXME comments?
    - Are there placeholder patterns?
    - Are there empty functions?
    - Are there NotImplementedError raises?
    
    Args:
        file_changes: List of file changes with path and content
        
    Returns:
        Dict with passed status and violations list
    """
    config = ValidatorConfig()
    layer = CompletenessLayer(config)
    
    result = layer.validate({"file_changes": file_changes})
    
    return {
        "passed": result.passed,
        "layer": "completeness",
        "violations": [v.model_dump() for v in result.violations],
        "checks_run": result.checks_run
    }


@tool
def validate_dependencies(
    file_changes: List[Dict[str, Any]],
    dependency_plan: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Validate imports and dependencies.
    
    Checks:
    - Do all imports resolve?
    - Are dependencies declared in the plan?
    - Are there hallucinated packages?
    - Are there circular dependencies?
    
    Args:
        file_changes: List of file changes with path and content
        dependency_plan: Declared dependencies from Planner
        
    Returns:
        Dict with passed status and violations list
    """
    config = ValidatorConfig()
    layer = DependencyLayer(config)
    
    result = layer.validate({
        "file_changes": file_changes,
        "dependency_plan": dependency_plan
    })
    
    return {
        "passed": result.passed,
        "layer": "dependency",
        "violations": [v.model_dump() for v in result.violations],
        "checks_run": result.checks_run
    }


@tool
def validate_scope(
    file_changes: List[Dict[str, Any]],
    current_task: Dict[str, Any],
    app_blueprint: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Validate implementation scope matches the task spec.
    
    Checks:
    - Does implementation match expected outputs?
    - Were non-goals respected?
    - Was scope exceeded?
    
    Args:
        file_changes: List of file changes
        current_task: Task being validated
        app_blueprint: App context with goals/non-goals
        
    Returns:
        Dict with passed status and violations list
    """
    config = ValidatorConfig()
    layer = ScopeLayer(config)
    
    result = layer.validate({
        "file_changes": file_changes,
        "current_task": current_task,
        "app_blueprint": app_blueprint
    })
    
    return {
        "passed": result.passed,
        "layer": "scope",
        "violations": [v.model_dump() for v in result.violations],
        "checks_run": result.checks_run
    }


@tool
def create_validation_report(
    structural_result: Dict[str, Any],
    completeness_result: Dict[str, Any],
    dependency_result: Dict[str, Any],
    scope_result: Dict[str, Any],
    task_id: str = ""
) -> Dict[str, Any]:
    """
    Create a final validation report from layer results.
    
    Determines overall pass/fail status and recommended action.
    
    Args:
        structural_result: Result from validate_structural
        completeness_result: Result from validate_completeness
        dependency_result: Result from validate_dependencies
        scope_result: Result from validate_scope
        task_id: ID of the task being validated
        
    Returns:
        Complete ValidationReport as dict
    """
    # Find first failing layer
    layers = [
        ("structural", structural_result),
        ("completeness", completeness_result),
        ("dependency", dependency_result),
        ("scope", scope_result)
    ]
    
    all_violations = []
    failure_layer = FailureLayer.NONE
    status = ValidationStatus.PASS
    
    for layer_name, result in layers:
        if result.get("violations"):
            all_violations.extend(result["violations"])
        
        if not result.get("passed", True) and failure_layer == FailureLayer.NONE:
            status = ValidationStatus.FAIL
            failure_layer = FailureLayer(layer_name)
    
    # Determine recommended action
    if status == ValidationStatus.PASS:
        action = "proceed"
    elif failure_layer in [FailureLayer.STRUCTURAL, FailureLayer.SCOPE]:
        action = "replan"
    else:
        action = "fix"
    
    return {
        "status": status.value,
        "failure_layer": failure_layer.value,
        "violations": all_violations,
        "total_violations": len(all_violations),
        "recommended_action": action,
        "task_id": task_id
    }


@tool
async def verify_visually(
    run_id: str,
    description: str
) -> str:
    """
    Request a visual verification screenshot of the current preview.
    
    This triggers the frontend to take a screenshot via Electron.
    The screenshot will appear in the run timeline.
    
    Args:
        run_id: The ID of the current run
        description: Description of what to verify (e.g., "Check the delete button style")
        
    Returns:
        Status message processing request
    """
    await broadcast_event({
        "type": "request_screenshot",
        "runId": run_id,
        "description": description
    })
    
    return f"Screenshot requested for run {run_id}. Check the timeline for the image."
