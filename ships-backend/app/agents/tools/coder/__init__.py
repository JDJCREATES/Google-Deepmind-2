"""
ShipS* Coder Tools

LangChain tools for the Coder agent using @tool decorator.
These are used with LangGraph's create_react_agent.
"""

from typing import Dict, Any, List, Optional
from langchain_core.tools import tool
import difflib
import hashlib
import re
import os
from pathlib import Path
import logging

logger = logging.getLogger("ships.coder")

# ============================================================================
# SECURE PROJECT PATH CONTEXT
# This is set by the system before the coder runs, NEVER by the LLM
# The LLM never sees or receives the actual filesystem path
# ============================================================================
_project_context = {
    "project_root": "."  # Default to current directory
}

def set_project_root(path: str):
    """Set the project root path (called by system, not LLM)"""
    _project_context["project_root"] = path
    logger.info(f"[CODER] 📁 Project root set to: {path}")

def get_project_root() -> str:
    """Get the current project root path"""
    return _project_context["project_root"]



@tool
def write_file_to_disk(
    file_path: str,
    content: str
) -> Dict[str, Any]:
    """
    Write a file to disk in the current project.
    
    This is the primary tool for creating and modifying files.
    Creates parent directories if they don't exist.
    
    Args:
        file_path: Relative path within the project (e.g., "src/components/Button.tsx")
        content: The full content to write to the file
        
    Returns:
        Dict with success status, relative path, and bytes written
    """
    try:
        # Get project root from secure context (NOT from LLM input)
        project_root = get_project_root()
        
        # ====================================================================
        # CRITICAL SAFETY: Refuse to write if no valid project path is set
        # ====================================================================
        if not project_root or project_root == "." or project_root == "":
            logger.error("[CODER] ❌ BLOCKED: No project path set! Cannot write files without a user-selected project.")
            return {
                "success": False,
                "error": "No project folder selected. Please use the Electron app to select a project folder first.",
                "path": file_path
            }
        
        resolved_root = Path(project_root).resolve()
        resolved_path = (resolved_root / file_path).resolve()
        
        # ====================================================================
        # CRITICAL SAFETY: Block writes to THIS backend's directory
        # Uses the actual location of this script to detect the backend
        # ====================================================================
        backend_dir = Path(__file__).resolve().parent.parent.parent.parent  # ships-backend/
        
        if str(resolved_root).startswith(str(backend_dir)):
            logger.error(f"[CODER] ❌ BLOCKED: Attempted write to backend directory!")
            return {
                "success": False,
                "error": "Cannot write to the ShipS* backend. Please select a user project.",
                "path": file_path
            }
        
        # Security check - don't allow escaping project root
        if not str(resolved_path).startswith(str(resolved_root)):
            logger.error(f"[CODER] Security: Attempted path escape: {file_path}")
            return {
                "success": False,
                "error": "Invalid file path",
                "path": file_path
            }
        
        # Create parent directories
        resolved_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write the file
        resolved_path.write_text(content, encoding="utf-8")
        
        logger.info(f"[CODER] ✅ Wrote file: {file_path} ({len(content)} bytes)")
        
        # Return only relative path info (don't leak full paths)
        return {
            "success": True,
            "relative_path": file_path,
            "bytes_written": len(content),
            "lines": content.count("\n") + 1
        }
        
    except Exception as e:
        logger.error(f"[CODER] ❌ Failed to write {file_path}: {e}")
        return {
            "success": False,
            "error": str(e),
            "path": file_path
        }


@tool
def analyze_task(task: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze a task and extract code objectives.
    
    Parses acceptance criteria and determines what code
    changes are needed.
    
    Args:
        task: Task dict with title, description, acceptance_criteria
        
    Returns:
        Dict with objectives, is_valid, and task summary
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
        Dict with diff, lines_added, lines_removed
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
    lines_added = sum(1 for line in unified_diff.split("\n") if line.startswith("+") and not line.startswith("+++"))
    lines_removed = sum(1 for line in unified_diff.split("\n") if line.startswith("-") and not line.startswith("---"))
    
    return {
        "unified_diff": unified_diff,
        "lines_added": lines_added,
        "lines_removed": lines_removed,
        "file_path": file_path
    }


@tool
def detect_language(file_path: str) -> str:
    """
    Detect programming language from file extension.
    
    Args:
        file_path: Path to the file
        
    Returns:
        Language name
    """
    ext_map = {
        ".py": "python",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".js": "javascript",
        ".jsx": "javascript",
        ".css": "css",
        ".html": "html",
        ".json": "json",
        ".md": "markdown",
        ".yaml": "yaml",
        ".yml": "yaml",
    }
    
    for ext, lang in ext_map.items():
        if file_path.endswith(ext):
            return lang
    
    return "unknown"


@tool
def assess_change_risk(
    content: str,
    file_path: str
) -> Dict[str, Any]:
    """
    Assess the risk level of a code change.
    
    Checks for:
    - Security patterns (secrets, credentials)
    - Config file changes
    - Critical system files
    
    Args:
        content: New content
        file_path: Path to the file
        
    Returns:
        Dict with risk level and reason
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
    ]
    
    for pattern in secret_patterns:
        if re.search(pattern, content, re.IGNORECASE):
            risk = "high"
            reasons.append("Contains potential secrets")
            break
    
    # Config files
    config_patterns = [".env", "config.", "settings."]
    for pattern in config_patterns:
        if pattern in file_path.lower():
            if risk == "low":
                risk = "medium"
            reasons.append("Config file modification")
            break
    
    return {
        "risk": risk,
        "reasons": reasons
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
    Create a FileChange artifact.
    
    Args:
        path: File path
        operation: add, modify, or delete
        new_content: New file content
        original_content: Original content (for modify)
        reason: Reason for the change
        
    Returns:
        FileChange as dict
    """
    import uuid
    
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
def build_commit_message(
    task_type: str,
    summary: str,
    task_id: str
) -> Dict[str, Any]:
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
    
    return {
        "message": message,
        "body": body
    }


@tool
def check_imports(
    content: str,
    allowed_packages: List[str]
) -> Dict[str, Any]:
    """
    Check if all imports in the code are allowed.
    
    Args:
        content: Code content
        allowed_packages: List of allowed package names
        
    Returns:
        Dict with allowed, blocked, and unknown imports
    """
    # Extract imports
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
    
    builtin = {"react", "os", "sys", "json", "re", "typing", "path", "fs"}
    
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


# Export all tools for the Coder agent
# write_file_to_disk is FIRST because it's the primary tool for creating files
CODER_TOOLS = [
    write_file_to_disk,  # PRIMARY TOOL - actually writes files to disk
    analyze_task,
    generate_file_diff,
    detect_language,
    assess_change_risk,
    create_file_change,
    build_commit_message,
    check_imports,
]
