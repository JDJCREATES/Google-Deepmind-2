"""
Knowledge Capture Hooks for Agent Graph.

Provides async-safe capture functions to be called from agent graph nodes
after successful code generation or fix application.

These functions handle:
- Database session management
- Context extraction from graph state
- Async capture calls
- Graceful failure (non-blocking)
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from app.database import get_session
from app.services.knowledge import (
    capture_successful_pattern,
    capture_successful_fix,
    FixerKnowledge,
    CoderKnowledge,
)
from app.services.knowledge.normalization import extract_tech_stack

logger = logging.getLogger("ships.knowledge.hooks")


async def capture_coder_pattern(
    state: Dict[str, Any],
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> bool:
    """
    Capture successful code generation pattern from graph state.
    
    Called from complete_node after validation passes for Coder output.
    
    Pattern capture conditions:
    - Validation passed (we're in complete_node)
    - Files were actually created
    - Build is running successfully
    
    Args:
        state: AgentGraphState after successful completion
        session_id: Agent session ID
        user_id: User ID for attribution
        
    Returns:
        True if captured, False if skipped/failed
    """
    try:
        artifacts = state.get("artifacts", {})
        user_request = state.get("messages", [{}])[0]
        
        # Extract feature request from original user message
        if hasattr(user_request, "content"):
            feature_request = user_request.content
        else:
            feature_request = str(user_request)
        
        # Skip if no meaningful request
        if not feature_request or len(feature_request) < 10:
            logger.info("[KNOWLEDGE] ⏭️ Pattern capture skipped: no meaningful request")
            return False
        
        # Get files created
        completed_files = state.get("completed_files", [])
        if not completed_files:
            logger.info("[KNOWLEDGE] ⏭️ Pattern capture skipped: no files created")
            return False
        
        logger.info(f"[KNOWLEDGE] 🔍 Processing pattern capture: {len(completed_files)} files")
        
        # Extract code context
        project_path = artifacts.get("project_path", "")
        plan_content = artifacts.get("plan_content", "")
        
        # Detect tech stack from plan or project path
        tech_stack = _detect_tech_stack_from_state(
            project_path,
            plan_content,
            completed_files
        )
        logger.info(f"[KNOWLEDGE] 🔧 Tech stack detected: {tech_stack}")
        
        # Build code description from plan
        code_description = _extract_description(plan_content, feature_request)
        
        # Get session ID
        if not session_id:
            session_id = f"graph_{datetime.utcnow().isoformat()}"
        
        # Read sample of generated code for embedding
        generated_code = await _sample_generated_code(project_path, completed_files)
        
        if not generated_code:
            logger.info("[KNOWLEDGE] ⏭️ Pattern capture skipped: no readable code")
            return False
        
        logger.info(f"[KNOWLEDGE] 📝 Sampled {len(generated_code)} chars of code for embedding")
        
        # Capture the pattern
        async for db in get_session():
            entry = await capture_successful_pattern(
                db=db,
                session_id=session_id,
                feature_request=feature_request[:500],  # Limit length
                generated_code=generated_code,
                code_description=code_description[:300],
                tech_stack=tech_stack,
                files_created=completed_files,
                user_id=user_id,
                visibility="private",
                build_passed=True,  # We only capture on success
                user_continued=True,  # Implicit - they didn't revert
            )
            
            if entry:
                logger.info(
                    f"📚 Captured pattern for '{feature_request[:40]}...' "
                    f"({len(completed_files)} files, tech: {tech_stack})"
                )
                return True
            break
        
        return False
        
    except Exception as e:
        logger.warning(f"Pattern capture failed (non-blocking): {e}")
        return False


async def capture_fixer_success(
    state: Dict[str, Any],
    error_message: str,
    solution_code: str,
    solution_description: str,
    diff: str,
    before_errors: List[str],
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> bool:
    """
    Capture successful fix from fixer node.
    
    Called after fixer applies a fix AND subsequent validation passes.
    
    Args:
        state: AgentGraphState
        error_message: The error that was fixed
        solution_code: Code that fixed it
        solution_description: Description of the fix
        diff: Git-style diff
        before_errors: Errors before the fix
        session_id: Agent session ID
        user_id: User ID
        
    Returns:
        True if captured, False if skipped/failed
    """
    try:
        artifacts = state.get("artifacts", {})
        project_path = artifacts.get("project_path", "")
        plan_content = artifacts.get("plan_content", "")
        
        # Build project context
        project_context = {
            "project_path": project_path,
            "dependencies": _extract_dependencies(project_path),
            "files": state.get("completed_files", []),
        }
        
        # Detect tech stack
        tech_stack = _detect_tech_stack_from_state(
            project_path,
            plan_content,
            state.get("completed_files", [])
        )
        project_context["tech_stack"] = tech_stack
        
        # Get session ID
        if not session_id:
            session_id = f"fix_{datetime.utcnow().isoformat()}"
        
        # Capture the fix
        async for db in get_session():
            entry = await capture_successful_fix(
                db=db,
                session_id=session_id,
                error_message=error_message,
                solution_code=solution_code,
                solution_description=solution_description,
                diff=diff,
                before_errors=before_errors,
                after_errors=[],  # Validation passed, so no errors
                project_context=project_context,
                user_id=user_id,
                visibility="private",
                user_approved=False,  # Will be set later if user approves
                user_continued=True,  # Implicit approval
            )
            
            if entry:
                logger.info(
                    f"🔧 Captured fix for '{error_message[:40]}...' "
                    f"(tech: {tech_stack})"
                )
                return True
            break
        
        return False
        
    except Exception as e:
        logger.warning(f"Fix capture failed (non-blocking): {e}")
        return False


def _detect_tech_stack_from_state(
    project_path: str,
    plan_content: str,
    files: List[str]
) -> str:
    """Detect tech stack from project state."""
    # Use the normalization module's extractor
    context = {
        "project_path": project_path,
        "files": files,
    }
    
    # Quick inference from file extensions
    ext_counts = {}
    for f in files:
        ext = f.split(".")[-1].lower() if "." in f else ""
        ext_counts[ext] = ext_counts.get(ext, 0) + 1
    
    stack_parts = []
    
    # Frontend
    if ext_counts.get("tsx", 0) or ext_counts.get("jsx", 0):
        stack_parts.append("react")
    elif ext_counts.get("vue", 0):
        stack_parts.append("vue")
    elif ext_counts.get("svelte", 0):
        stack_parts.append("svelte")
    elif ext_counts.get("html", 0):
        stack_parts.append("html")
    
    # Backend
    if ext_counts.get("py", 0):
        if "fastapi" in plan_content.lower():
            stack_parts.append("fastapi")
        elif "flask" in plan_content.lower():
            stack_parts.append("flask")
        else:
            stack_parts.append("python")
    
    if ext_counts.get("ts", 0) and not stack_parts:
        stack_parts.append("typescript")
    
    return "+".join(stack_parts) if stack_parts else "unknown"


def _extract_description(plan_content: str, feature_request: str) -> str:
    """Extract meaningful description from plan or request."""
    if plan_content:
        # Try to find first meaningful line from plan
        lines = plan_content.split("\n")
        for line in lines[:10]:
            line = line.strip()
            if line and not line.startswith("#") and len(line) > 20:
                return line
    
    return feature_request[:200]


async def _sample_generated_code(
    project_path: str,
    files: List[str],
    max_chars: int = 5000
) -> str:
    """Read a sample of generated code for embedding."""
    import os
    
    if not project_path or not files:
        return ""
    
    sample_parts = []
    chars = 0
    
    # Prioritize main files
    priority_files = [f for f in files if any(p in f.lower() for p in ["app.", "main.", "index."])]
    other_files = [f for f in files if f not in priority_files]
    
    for filename in priority_files + other_files:
        if chars >= max_chars:
            break
            
        filepath = os.path.join(project_path, filename) if not os.path.isabs(filename) else filename
        
        try:
            if os.path.exists(filepath) and os.path.isfile(filepath):
                with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    remaining = max_chars - chars
                    sample_parts.append(f"// {filename}\n{content[:remaining]}")
                    chars += len(content[:remaining])
        except Exception:
            continue
    
    return "\n\n".join(sample_parts)


def _extract_dependencies(project_path: str) -> Dict[str, str]:
    """Extract dependencies from package.json or requirements.txt."""
    import os
    import json
    
    deps = {}
    
    if not project_path:
        return deps
    
    # Try package.json
    pkg_path = os.path.join(project_path, "package.json")
    if os.path.exists(pkg_path):
        try:
            with open(pkg_path) as f:
                pkg = json.load(f)
                deps.update(pkg.get("dependencies", {}))
                deps.update(pkg.get("devDependencies", {}))
        except Exception:
            pass
    
    # Try requirements.txt
    req_path = os.path.join(project_path, "requirements.txt")
    if os.path.exists(req_path):
        try:
            with open(req_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        # Handle package==version format
                        if "==" in line:
                            name, version = line.split("==", 1)
                            deps[name] = version
                        else:
                            deps[line] = "*"
        except Exception:
            pass
    
    return deps
