"""
Code Analysis Tools

Tools for analyzing code content - diffs, language detection, risk assessment.
These are utility tools that support the main file operations.
"""

from typing import Dict, Any, List, Optional
import difflib
import re
import uuid

from langchain_core.tools import tool


@tool
def detect_language(file_path: str) -> str:
    """
    Detect programming language from file extension.
    
    Args:
        file_path: Path to the file
        
    Returns:
        Language name (e.g., "python", "typescript")
    """
    ext_map = {
        ".py": "python",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".js": "javascript",
        ".jsx": "javascript",
        ".css": "css",
        ".scss": "scss",
        ".html": "html",
        ".json": "json",
        ".md": "markdown",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".toml": "toml",
        ".sql": "sql",
        ".sh": "bash",
        ".rs": "rust",
        ".go": "go",
    }
    
    for ext, lang in ext_map.items():
        if file_path.endswith(ext):
            return lang
    
    return "unknown"


@tool
def generate_file_diff(
    original_content: str,
    new_content: str,
    file_path: str
) -> Dict[str, Any]:
    """
    Generate a unified diff between original and new content.
    
    Args:
        original_content: Original file content
        new_content: New file content
        file_path: Path to the file
        
    Returns:
        Dict with unified diff, lines added/removed
    """
    original_lines = original_content.splitlines(keepends=True)
    new_lines = new_content.splitlines(keepends=True)
    
    diff = difflib.unified_diff(
        original_lines,
        new_lines,
        fromfile=f"a/{file_path}",
        tofile=f"b/{file_path}"
    )
    unified_diff = "".join(diff)
    
    # Count changes
    lines_added = sum(1 for line in unified_diff.split("\n") 
                     if line.startswith("+") and not line.startswith("+++"))
    lines_removed = sum(1 for line in unified_diff.split("\n") 
                       if line.startswith("-") and not line.startswith("---"))
    
    return {
        "unified_diff": unified_diff,
        "lines_added": lines_added,
        "lines_removed": lines_removed,
        "file_path": file_path
    }


@tool
def assess_change_risk(content: str, file_path: str) -> Dict[str, Any]:
    """
    Assess the risk level of a code change.
    
    Checks for security patterns, config file changes, etc.
    
    Args:
        content: New content
        file_path: Path to the file
        
    Returns:
        Dict with risk level and reasons
    """
    risk = "low"
    reasons = []
    
    # Security patterns
    secret_patterns = [
        r"api[_-]?key\s*=",
        r"secret\s*=",
        r"password\s*=",
        r"token\s*=",
        r"private[_-]?key",
        r"AWS_SECRET",
        r"OPENAI_API_KEY",
    ]
    
    for pattern in secret_patterns:
        if re.search(pattern, content, re.IGNORECASE):
            risk = "high"
            reasons.append("Contains potential secrets or credentials")
            break
    
    # Config files
    config_patterns = [".env", "config.", "settings.", ".secrets"]
    for pattern in config_patterns:
        if pattern in file_path.lower():
            if risk == "low":
                risk = "medium"
            reasons.append("Config file modification")
            break
    
    # Critical system files
    critical_patterns = ["package.json", "requirements.txt", "Dockerfile"]
    for pattern in critical_patterns:
        if pattern in file_path:
            if risk == "low":
                risk = "medium"
            reasons.append("Critical system file modification")
            break
    
    return {"risk": risk, "reasons": reasons}


@tool
def analyze_task(task: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze a task and extract code objectives.
    
    Args:
        task: Task dict with title, description, acceptance_criteria
        
    Returns:
        Dict with objectives and validation info
    """
    required_fields = ["title", "description"]
    missing = [f for f in required_fields if not task.get(f)]
    
    if missing:
        return {
            "is_valid": False,
            "blocking_reasons": [f"Missing fields: {missing}"],
            "objectives": []
        }
    
    acceptance_criteria = task.get("acceptance_criteria", [])
    if not acceptance_criteria:
        acceptance_criteria = [{"description": "Implementation matches task description"}]
    
    objectives = []
    for i, criterion in enumerate(acceptance_criteria):
        desc = criterion.get("description", "") if isinstance(criterion, dict) else str(criterion)
        objectives.append({
            "id": f"obj_{i}",
            "description": desc,
            "is_testable": "should" in desc.lower() or "must" in desc.lower(),
        })
    
    return {
        "is_valid": True,
        "objectives": objectives,
        "task_summary": task.get("description", ""),
        "expected_outputs": task.get("expected_outputs", [])
    }


@tool
def check_imports(content: str, allowed_packages: List[str]) -> Dict[str, Any]:
    """
    Check if all imports in the code are allowed.
    
    Args:
        content: Code content
        allowed_packages: List of allowed package names
        
    Returns:
        Dict with allowed, blocked, and unknown imports
    """
    imports = []
    
    # JS/TS imports
    js_pattern = r"(?:import|from)\s+['\"]([^'\"]+)['\"]"
    imports.extend(re.findall(js_pattern, content))
    
    # Python imports
    py_pattern = r"(?:from\s+(\S+)\s+import|import\s+(\S+))"
    for match in re.findall(py_pattern, content):
        imports.extend([m for m in match if m])
    
    # Classify
    allowed = []
    blocked = []
    unknown = []
    
    builtin = {"react", "os", "sys", "json", "re", "typing", "path", "fs", "uuid", "datetime"}
    
    for imp in imports:
        base = imp.split("/")[0].split(".")[0]
        
        if imp.startswith("."):  # Relative import
            allowed.append(imp)
        elif base in builtin:
            allowed.append(imp)
        elif base in allowed_packages:
            allowed.append(imp)
        else:
            unknown.append(imp)
    
    return {
        "allowed": allowed,
        "blocked": blocked,
        "unknown": unknown,
        "has_issues": len(blocked) > 0
    }


@tool
def create_file_change(
    path: str,
    operation: str,
    new_content: str,
    original_content: Optional[str] = None,
    reason: str = ""
) -> Dict[str, Any]:
    """
    Create a FileChange artifact for tracking.
    
    Args:
        path: File path
        operation: add, modify, or delete
        new_content: New file content
        original_content: Original content (for modify)
        reason: Reason for the change
        
    Returns:
        FileChange as dict
    """
    # Generate diff if modifying
    diff_result = {}
    if operation == "modify" and original_content:
        diff_result = generate_file_diff.invoke({
            "original_content": original_content,
            "new_content": new_content,
            "file_path": path
        })
    elif operation == "add":
        diff_result = {
            "lines_added": new_content.count("\n") + 1,
            "lines_removed": 0
        }
    
    # Detect language
    language = detect_language.invoke({"file_path": path})
    
    # Assess risk
    risk_result = assess_change_risk.invoke({
        "content": new_content,
        "file_path": path
    })
    
    return {
        "id": f"change_{uuid.uuid4().hex[:8]}",
        "path": path,
        "operation": operation,
        "diff": {
            "original_content": original_content,
            "new_content": new_content,
            "unified_diff": diff_result.get("unified_diff", "")
        },
        "lines_added": diff_result.get("lines_added", 0),
        "lines_removed": diff_result.get("lines_removed", 0),
        "language": language,
        "risk": risk_result.get("risk", "low"),
        "reason": reason
    }


@tool
def build_commit_message(task_type: str, summary: str, task_id: str) -> Dict[str, Any]:
    """
    Build a conventional commit message.
    
    Args:
        task_type: Type of task (feature, fix, refactor, etc.)
        summary: Short summary of changes
        task_id: Task ID for traceability
        
    Returns:
        Dict with message and body
    """
    type_map = {
        "feature": "feat",
        "fix": "fix",
        "refactor": "refactor",
        "test": "test",
        "docs": "docs",
        "chore": "chore",
    }
    
    prefix = type_map.get(task_type, "feat")
    message = f"{prefix}: {summary}"
    body = f"Task: {task_id}\n\nGenerated by ShipS* Coder Agent"
    
    return {"message": message, "body": body}


# Export all code analysis tools
CODE_ANALYSIS_TOOLS = [
    detect_language,
    generate_file_diff,
    assess_change_risk,
    analyze_task,
    check_imports,
    create_file_change,
    build_commit_message,
]
