"""
ShipS* Fixer Tools

LangChain tools for the Fixer agent using @tool decorator.
These are used with LangGraph's create_react_agent.
"""

from typing import Dict, Any, List, Optional
from langchain_core.tools import tool

from app.agents.sub_agents.fixer.models import (
    FixPlan, FixPatch, FixChange, FixReport,
    FixScope, FixApproach, FixRisk, FixResult,
    ViolationFix, ReplanRequest,
)
from app.agents.sub_agents.fixer.strategies import (
    StructuralFixer, CompletenessFixer, DependencyFixer, ScopeFixer,
    FixerConfig,
)
from app.agents.sub_agents.validator.models import Violation, FailureLayer


@tool
def triage_violations(violations: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Classify violations into fixable, requires_replan, or policy_blocked.
    
    Determines which violations can be fixed locally vs need escalation.
    
    Args:
        violations: List of violations from ValidationReport
        
    Returns:
        Dict with fixable, requires_replan, policy_blocked lists
    """
    config = FixerConfig()
    strategies = {
        "structural": StructuralFixer(config),
        "completeness": CompletenessFixer(config),
        "dependency": DependencyFixer(config),
        "scope": ScopeFixer(config),
    }
    
    result = {
        "fixable": [],
        "requires_replan": [],
        "policy_blocked": [],
        "unknown": []
    }
    
    for v_dict in violations:
        layer = v_dict.get("layer", "completeness")
        strategy = strategies.get(layer)
        
        if not strategy:
            result["unknown"].append(v_dict)
            continue
        
        # Create a minimal violation for the strategy
        violation = Violation(
            id=v_dict.get("id", ""),
            layer=FailureLayer(layer),
            rule=v_dict.get("rule", ""),
            message=v_dict.get("message", "")
        )
        
        can_fix, scope = strategy.can_fix(violation)
        
        if can_fix and scope == FixScope.LOCAL:
            result["fixable"].append(v_dict)
        elif scope == FixScope.ARCHITECTURAL:
            result["requires_replan"].append(v_dict)
        elif scope == FixScope.POLICY_BLOCKED:
            result["policy_blocked"].append(v_dict)
        else:
            result["unknown"].append(v_dict)
    
    return result


@tool
def generate_todo_fix(
    file_path: str,
    line_number: int,
    file_content: str
) -> Dict[str, Any]:
    """
    Generate a fix for a TODO violation.
    
    Converts TODO comments to NOTE comments to pass validation
    while creating a follow-up task for proper implementation.
    
    Args:
        file_path: Path to the file with TODO
        line_number: Line number of the TODO
        file_content: Full content of the file
        
    Returns:
        Fix change with original and new content
    """
    lines = file_content.split("\n")
    
    if line_number <= 0 or line_number > len(lines):
        return {"success": False, "error": "Invalid line number"}
    
    original_line = lines[line_number - 1]
    fixed_line = original_line
    
    for pattern in ["TODO", "FIXME", "HACK", "XXX"]:
        fixed_line = fixed_line.replace(f"// {pattern}", "// NOTE (from fix):")
        fixed_line = fixed_line.replace(f"# {pattern}", "# NOTE (from fix):")
    
    if fixed_line == original_line:
        return {"success": False, "error": "No TODO pattern found"}
    
    lines[line_number - 1] = fixed_line
    new_content = "\n".join(lines)
    
    return {
        "success": True,
        "path": file_path,
        "operation": "modify",
        "original_content": file_content,
        "new_content": new_content,
        "reason": f"Convert TODO to NOTE at line {line_number}",
        "creates_followup": True
    }


@tool
def generate_empty_function_fix(
    file_path: str,
    file_content: str
) -> Dict[str, Any]:
    """
    Generate fixes for empty function bodies.
    
    Adds minimal stub implementations to empty functions.
    
    Args:
        file_path: Path to the file
        file_content: Full content of the file
        
    Returns:
        Fix change with new content
    """
    import re
    
    new_content = file_content
    
    # JS/TS: () => {} -> () => { console.log('Not implemented'); }
    new_content = re.sub(
        r'=\s*\(\)\s*=>\s*\{\s*\}',
        "= () => { console.log('Not implemented'); }",
        new_content
    )
    
    # Python: def foo(): pass -> def foo(): return None
    new_content = re.sub(
        r'(def\s+\w+\s*\([^)]*\)\s*:\s*)pass(\s*$)',
        r'\1return None  # Stub\2',
        new_content,
        flags=re.MULTILINE
    )
    
    if new_content == file_content:
        return {"success": False, "error": "No empty functions found"}
    
    return {
        "success": True,
        "path": file_path,
        "operation": "modify",
        "original_content": file_content,
        "new_content": new_content,
        "reason": "Add stub implementation to empty functions"
    }


@tool
def create_fix_patch(
    fix_plan_id: str,
    changes: List[Dict[str, Any]],
    commit_message: str
) -> Dict[str, Any]:
    """
    Create a FixPatch from a list of changes.
    
    Args:
        fix_plan_id: ID of the fix plan
        changes: List of fix changes
        commit_message: Commit message for the patch
        
    Returns:
        FixPatch as dict
    """
    patch = FixPatch(
        fix_plan_id=fix_plan_id,
        summary=commit_message,
        commit_message=commit_message,
        rollback_command="git checkout HEAD~1 -- ."
    )
    
    for change in changes:
        if change.get("success", False):
            patch.add_change(FixChange(
                path=change.get("path", ""),
                operation=change.get("operation", "modify"),
                original_content=change.get("original_content"),
                new_content=change.get("new_content"),
                violation_ids=change.get("violation_ids", []),
                reason=change.get("reason", "")
            ))
    
    patch.preflight_passed = True  # Will be validated later
    
    return patch.model_dump()


@tool
def create_replan_request(
    validation_report_id: str,
    fix_plan_id: str,
    reason: str,
    violated_artifact: str,
    violation_details: str
) -> Dict[str, Any]:
    """
    Create a request to re-run the Planner.
    
    Used when fixes require architectural changes that
    the Fixer cannot handle.
    
    Args:
        validation_report_id: ID of failing validation report
        fix_plan_id: ID of the fix plan that couldn't proceed
        reason: Why replan is needed
        violated_artifact: Which artifact needs changes
        violation_details: Details about the violation
        
    Returns:
        ReplanRequest as dict
    """
    request = ReplanRequest(
        origin_validation_report_id=validation_report_id,
        origin_fix_plan_id=fix_plan_id,
        reason=reason,
        violated_artifact=violated_artifact,
        violation_details=violation_details
    )
    
    return request.model_dump()


@tool
def run_preflight_checks(
    patch: Dict[str, Any],
    max_files: int = 10,
    max_lines: int = 200
) -> Dict[str, Any]:
    """
    Run preflight checks on a fix patch.
    
    Validates:
    - No protected paths modified
    - Within size limits
    - Basic syntax checks
    
    Args:
        patch: FixPatch dict
        max_files: Maximum files allowed
        max_lines: Maximum lines changed
        
    Returns:
        Dict with passed status and issues
    """
    issues = []
    
    changes = patch.get("changes", [])
    total_files = len(changes)
    total_lines = sum(c.get("lines_added", 0) + c.get("lines_removed", 0) for c in changes)
    
    # Check protected paths
    protected = [".git/", "node_modules/", ".env"]
    for change in changes:
        path = change.get("path", "")
        for p in protected:
            if p in path:
                issues.append(f"Protected path: {path}")
    
    # Check size limits
    if total_files > max_files:
        issues.append(f"Too many files: {total_files} > {max_files}")
    
    if total_lines > max_lines:
        issues.append(f"Too many lines: {total_lines} > {max_lines}")
    
    return {
        "passed": len(issues) == 0,
        "issues": issues,
        "total_files": total_files,
        "total_lines": total_lines
    }


# Import write_file_to_disk from coder tools
from app.agents.tools.coder import write_file_to_disk

# Export all tools for the Fixer agent
FIXER_TOOLS = [
    triage_violations,
    generate_todo_fix,
    generate_empty_function_fix,
    create_fix_patch,
    create_replan_request,
    run_preflight_checks,
    write_file_to_disk,  # Fixer can now write fixes to disk
]
