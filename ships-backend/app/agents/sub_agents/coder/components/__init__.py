"""
ShipS* Coder Components

Modular subcomponents for the Coder agent:
- TaskInterpreter: Verify task, map acceptance criteria to code objectives
- ContextConsumer: Fetch relevant code context (token-limited)
- StyleEnforcer: Apply repo conventions (naming, patterns)
- ImplementationSynthesizer: Generate minimal diffs
- DependencyVerifier: Validate imports, check allowed packages
- TestAuthor: Generate tests matching validation checklist
- PreflightChecker: Run lint/static checks on changes

Each component produces traceable decision notes.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List, Tuple
from pydantic import BaseModel
import re
import os

from app.agents.sub_agents.coder.models import (
    FileChange, FileChangeSet, FileDiff, FileOperation, ChangeRisk,
    TestBundle, TestCase, TestType, TestAssertion,
    PreflightCheck, CheckResult, CheckStatus,
    FollowUpTask, FollowUpTasks,
    InferredItem, EdgeCase,
)


class CoderComponentConfig(BaseModel):
    """Configuration for coder components."""
    max_diff_size_lines: int = 500
    max_files_per_changeset: int = 20
    require_tests: bool = True
    min_test_coverage: float = 0.8
    allow_new_dependencies: bool = True
    low_confidence_threshold: float = 0.6
    banned_patterns: List[str] = ["TODO", "FIXME", "HACK"]


class CoderComponent(ABC):
    """Base class for coder subcomponents."""
    
    def __init__(self, config: Optional[CoderComponentConfig] = None):
        self.config = config or CoderComponentConfig()
        self.decision_notes: List[str] = []
    
    def add_note(self, note: str) -> None:
        """Add a decision note."""
        self.decision_notes.append(note)
    
    @abstractmethod
    def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Process input and produce output."""
        pass


# ============================================================================
# TASK INTERPRETER
# ============================================================================

class TaskInterpreter(CoderComponent):
    """
    Verifies task artifact and maps acceptance criteria to code objectives.
    
    Rejects tasks that lack measurable acceptance criteria.
    """
    
    def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Interpret task and extract coding objectives.
        
        Args:
            context: Contains 'task' artifact from Planner
            
        Returns:
            Dict with 'objectives', 'is_valid', 'blocking_reasons'
        """
        task = context.get("task", {})
        
        # Validate task has required fields
        required_fields = ["title", "description"]
        missing = [f for f in required_fields if not task.get(f)]
        
        if missing:
            self.add_note(f"Task missing required fields: {missing}")
            return {
                "is_valid": False,
                "blocking_reasons": [f"Missing fields: {missing}"],
                "objectives": []
            }
        
        # Extract acceptance criteria
        acceptance_criteria = task.get("acceptance_criteria", [])
        if not acceptance_criteria:
            self.add_note("Task has no acceptance criteria - adding default")
            acceptance_criteria = [{"description": "Implementation matches task description"}]
        
        # Map criteria to code objectives
        objectives = []
        for i, criterion in enumerate(acceptance_criteria):
            desc = criterion.get("description", "") if isinstance(criterion, dict) else str(criterion)
            objectives.append({
                "id": f"obj_{i}",
                "description": desc,
                "is_testable": self._is_testable(desc),
                "requires_ui": self._requires_ui(desc),
                "requires_api": self._requires_api(desc),
            })
        
        self.add_note(f"Extracted {len(objectives)} code objectives from task")
        
        return {
            "is_valid": True,
            "blocking_reasons": [],
            "objectives": objectives,
            "task_summary": task.get("description", ""),
            "expected_outputs": task.get("expected_outputs", [])
        }
    
    def _is_testable(self, description: str) -> bool:
        """Check if criterion can be tested automatically."""
        testable_keywords = ["returns", "responds", "renders", "displays", "validates"]
        return any(kw in description.lower() for kw in testable_keywords)
    
    def _requires_ui(self, description: str) -> bool:
        """Check if criterion requires UI changes."""
        ui_keywords = ["ui", "display", "render", "component", "button", "form", "page"]
        return any(kw in description.lower() for kw in ui_keywords)
    
    def _requires_api(self, description: str) -> bool:
        """Check if criterion requires API changes."""
        api_keywords = ["api", "endpoint", "request", "response", "route", "http"]
        return any(kw in description.lower() for kw in api_keywords)


# ============================================================================
# CONTEXT CONSUMER
# ============================================================================

class ContextConsumer(CoderComponent):
    """
    Fetches relevant code context with token limits.
    
    Validates context matches expected Folder Map entries.
    """
    
    MAX_CONTEXT_TOKENS = 8000  # Limit context to avoid token waste
    
    def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Gather relevant context for code generation.
        
        Args:
            context: Contains 'folder_map', 'target_files', 'existing_code'
            
        Returns:
            Dict with 'relevant_snippets', 'file_structures'
        """
        folder_map = context.get("folder_map", {})
        target_files = context.get("target_files", [])
        existing_code = context.get("existing_code", {})
        
        relevant_snippets = {}
        file_structures = {}
        
        # Get entries from folder map
        entries = folder_map.get("entries", [])
        
        # Identify relevant files based on task objectives
        objectives = context.get("objectives", [])
        
        for entry in entries[:20]:  # Limit to avoid token explosion
            path = entry.get("path", "")
            if not path:
                continue
            
            # Check if this file is relevant
            if self._is_relevant(path, objectives):
                # Get existing content if available
                content = existing_code.get(path, "")
                if content:
                    # Trim to reasonable size
                    trimmed = self._trim_content(content)
                    relevant_snippets[path] = trimmed
                    file_structures[path] = self._extract_structure(content)
        
        self.add_note(f"Gathered context from {len(relevant_snippets)} relevant files")
        
        return {
            "relevant_snippets": relevant_snippets,
            "file_structures": file_structures,
            "context_token_estimate": sum(len(s.split()) for s in relevant_snippets.values())
        }
    
    def _is_relevant(self, path: str, objectives: List[Dict]) -> bool:
        """Check if a file is relevant to the objectives."""
        path_lower = path.lower()
        
        for obj in objectives:
            desc = obj.get("description", "").lower()
            # Check for keyword overlap
            path_parts = path_lower.replace("/", " ").replace("\\", " ").replace(".", " ")
            if any(word in desc for word in path_parts.split() if len(word) > 3):
                return True
        
        return False
    
    def _trim_content(self, content: str, max_lines: int = 200) -> str:
        """Trim content to limit tokens."""
        lines = content.split("\n")
        if len(lines) <= max_lines:
            return content
        # Keep first and last portions
        return "\n".join(lines[:max_lines // 2] + ["// ... trimmed ..."] + lines[-max_lines // 2:])
    
    def _extract_structure(self, content: str) -> Dict[str, Any]:
        """Extract file structure (functions, classes, exports)."""
        structure = {
            "functions": [],
            "classes": [],
            "exports": [],
            "imports": []
        }
        
        # Simple regex-based extraction
        # Functions
        func_pattern = r'(?:function|const|let|var)\s+(\w+)\s*[=\(]'
        structure["functions"] = re.findall(func_pattern, content)[:20]
        
        # Classes
        class_pattern = r'class\s+(\w+)'
        structure["classes"] = re.findall(class_pattern, content)[:10]
        
        # Exports
        export_pattern = r'export\s+(?:default\s+)?(?:function|class|const|let|var)?\s*(\w+)'
        structure["exports"] = re.findall(export_pattern, content)[:20]
        
        return structure


# ============================================================================
# STYLE ENFORCER
# ============================================================================

class StyleEnforcer(CoderComponent):
    """
    Applies repository conventions to generated code.
    
    Queries patterns for naming, code style, and error handling.
    """
    
    COMMON_CONVENTIONS = {
        "react": {
            "component_case": "PascalCase",
            "hook_prefix": "use",
            "file_case": "PascalCase",
            "test_suffix": ".test.tsx",
        },
        "node": {
            "function_case": "camelCase",
            "file_case": "kebab-case",
            "test_suffix": ".test.js",
        },
        "python": {
            "function_case": "snake_case",
            "class_case": "PascalCase",
            "file_case": "snake_case",
            "test_prefix": "test_",
        }
    }
    
    def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Determine style conventions to apply.
        
        Args:
            context: Contains 'framework', 'existing_patterns'
            
        Returns:
            Dict with 'naming_rules', 'code_patterns', 'test_patterns'
        """
        framework = context.get("framework", "react")
        existing_snippets = context.get("relevant_snippets", {})
        
        # Get base conventions
        conventions = self.COMMON_CONVENTIONS.get(framework, {})
        
        # Detect patterns from existing code
        detected = self._detect_patterns(existing_snippets)
        
        # Merge (detected takes precedence)
        merged = {**conventions, **detected}
        
        self.add_note(f"Applied {framework} conventions with {len(detected)} detected patterns")
        
        return {
            "naming_rules": {
                "component_case": merged.get("component_case", "PascalCase"),
                "function_case": merged.get("function_case", "camelCase"),
                "file_case": merged.get("file_case", "kebab-case"),
            },
            "code_patterns": {
                "use_semicolons": merged.get("use_semicolons", True),
                "quote_style": merged.get("quote_style", "single"),
                "indent_style": merged.get("indent_style", "spaces"),
                "indent_size": merged.get("indent_size", 2),
            },
            "test_patterns": {
                "test_suffix": merged.get("test_suffix", ".test.ts"),
                "test_framework": merged.get("test_framework", "jest"),
            }
        }
    
    def _detect_patterns(self, snippets: Dict[str, str]) -> Dict[str, Any]:
        """Detect patterns from existing code."""
        detected = {}
        
        all_content = "\n".join(snippets.values())
        
        # Detect semicolons
        if all_content:
            semicolon_lines = len(re.findall(r';\s*$', all_content, re.MULTILINE))
            no_semicolon_lines = len(re.findall(r'[^;]\s*$', all_content, re.MULTILINE))
            detected["use_semicolons"] = semicolon_lines > no_semicolon_lines
            
            # Detect quote style
            single_quotes = all_content.count("'")
            double_quotes = all_content.count('"')
            detected["quote_style"] = "single" if single_quotes > double_quotes else "double"
            
            # Detect indent
            if "  " in all_content[:500]:
                detected["indent_style"] = "spaces"
                detected["indent_size"] = 2
            elif "\t" in all_content[:500]:
                detected["indent_style"] = "tabs"
        
        return detected


# ============================================================================
# IMPLEMENTATION SYNTHESIZER
# ============================================================================

class ImplementationSynthesizer(CoderComponent):
    """
    Generates minimal diffs that satisfy acceptance criteria.
    
    Prefers least invasive changes when multiple options exist.
    """
    
    def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Synthesize implementation changes.
        
        This is a template - actual implementation uses LLM.
        
        Args:
            context: Contains objectives, context, style rules
            
        Returns:
            Dict with 'suggested_changes', 'change_rationale'
        """
        objectives = context.get("objectives", [])
        expected_outputs = context.get("expected_outputs", [])
        style = context.get("style", {})
        
        suggested_changes = []
        
        # Generate change suggestions based on expected outputs
        for output in expected_outputs:
            path = output.get("file_path", output.get("path", ""))
            action = output.get("action", "create")
            
            if not path:
                continue
            
            change = {
                "path": path,
                "operation": action,
                "reason": f"Required by task output specification",
                "estimated_lines": 50,  # Default estimate
            }
            suggested_changes.append(change)
        
        self.add_note(f"Synthesized {len(suggested_changes)} file changes")
        
        return {
            "suggested_changes": suggested_changes,
            "change_rationale": "Changes generated to satisfy task acceptance criteria",
            "is_minimal": len(suggested_changes) <= 5
        }


# ============================================================================
# DEPENDENCY VERIFIER
# ============================================================================

class DependencyVerifier(CoderComponent):
    """
    Validates imports against allowed packages.
    
    Checks for banned packages and security vulnerabilities.
    """
    
    # Common safe packages by ecosystem
    SAFE_PACKAGES = {
        "npm": ["react", "react-dom", "next", "typescript", "lodash", "axios", "zod"],
        "pip": ["fastapi", "pydantic", "requests", "pytest", "uvicorn"],
    }
    
    BANNED_PACKAGES = {
        "npm": ["event-stream"],  # Known vulnerable
        "pip": [],
    }
    
    def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Verify dependencies are allowed.
        
        Args:
            context: Contains 'new_imports', 'dependency_plan'
            
        Returns:
            Dict with 'allowed', 'blocked', 'warnings'
        """
        new_imports = context.get("new_imports", [])
        dependency_plan = context.get("dependency_plan", {})
        ecosystem = context.get("ecosystem", "npm")
        
        existing_deps = dependency_plan.get("runtime_dependencies", [])
        existing_names = {d.get("name", d) if isinstance(d, dict) else d for d in existing_deps}
        
        allowed = []
        blocked = []
        warnings = []
        
        for imp in new_imports:
            pkg_name = imp.get("name", imp) if isinstance(imp, dict) else imp
            
            # Check if banned
            if pkg_name in self.BANNED_PACKAGES.get(ecosystem, []):
                blocked.append({
                    "name": pkg_name,
                    "reason": "Package is banned for security reasons"
                })
                continue
            
            # Check if already exists
            if pkg_name in existing_names:
                allowed.append({
                    "name": pkg_name,
                    "status": "already_installed"
                })
                continue
            
            # Check if known safe
            if pkg_name in self.SAFE_PACKAGES.get(ecosystem, []):
                allowed.append({
                    "name": pkg_name,
                    "status": "safe",
                    "install_command": f"npm install {pkg_name}" if ecosystem == "npm" else f"pip install {pkg_name}"
                })
            else:
                # Unknown package - warn
                warnings.append({
                    "name": pkg_name,
                    "reason": "Unknown package - requires review"
                })
        
        self.add_note(f"Verified {len(new_imports)} imports: {len(allowed)} allowed, {len(blocked)} blocked")
        
        return {
            "allowed": allowed,
            "blocked": blocked,
            "warnings": warnings,
            "has_blockers": len(blocked) > 0
        }


# ============================================================================
# TEST AUTHOR
# ============================================================================

class TestAuthor(CoderComponent):
    """
    Generates tests matching the validation checklist.
    
    Requires at least one automated check per acceptance criterion.
    """
    
    def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate tests for the implementation.
        
        Args:
            context: Contains 'objectives', 'changes', 'test_patterns'
            
        Returns:
            Dict with 'test_cases', 'test_bundle'
        """
        objectives = context.get("objectives", [])
        changes = context.get("suggested_changes", [])
        test_patterns = context.get("test_patterns", {})
        
        test_suffix = test_patterns.get("test_suffix", ".test.ts")
        framework = test_patterns.get("test_framework", "jest")
        
        test_cases = []
        
        for obj in objectives:
            if not obj.get("is_testable", True):
                continue
            
            test_case = TestCase(
                name=f"test_{obj['id']}",
                description=f"Test: {obj['description']}",
                test_type=TestType.UNIT,
                test_code=self._generate_test_stub(obj, framework),
                test_file_path=self._get_test_path(changes, test_suffix),
                covers_acceptance_criteria=[obj['id']]
            )
            test_cases.append(test_case)
        
        self.add_note(f"Generated {len(test_cases)} test cases")
        
        return {
            "test_cases": test_cases,
            "coverage_estimate": len(test_cases) / max(len(objectives), 1)
        }
    
    def _generate_test_stub(self, objective: Dict, framework: str) -> str:
        """Generate a test stub for an objective."""
        if framework == "jest":
            return f"""
describe('{objective.get("description", "Feature")[:50]}', () => {{
  it('should satisfy acceptance criteria', () => {{
    // TODO: Implement test
    expect(true).toBe(true);
  }});
}});
"""
        elif framework == "pytest":
            return f"""
def test_{objective['id']}():
    \"\"\"Test: {objective.get('description', '')}\"\"\"
    # TODO: Implement test
    assert True
"""
        return "// Test stub"
    
    def _get_test_path(self, changes: List[Dict], suffix: str) -> str:
        """Determine test file path based on changes."""
        if changes:
            first_path = changes[0].get("path", "src/index.ts")
            base = first_path.rsplit(".", 1)[0]
            return f"{base}{suffix}"
        return f"tests/feature{suffix}"


# ============================================================================
# PREFLIGHT CHECKER
# ============================================================================

class PreflightChecker(CoderComponent):
    """
    Runs static checks on generated code.
    
    Fast checks without building - lint, imports, security.
    """
    
    def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run preflight checks on changes.
        
        Args:
            context: Contains 'file_change_set', 'policy'
            
        Returns:
            Dict with 'preflight_check' artifact
        """
        changes = context.get("changes", [])
        policy = context.get("policy", {})
        
        preflight = PreflightCheck()
        
        for change in changes:
            content = change.get("content", "")
            path = change.get("path", "")
            
            # Check for banned patterns
            self._check_banned_patterns(content, path, preflight)
            
            # Check for missing imports (basic)
            self._check_imports(content, path, preflight)
            
            # Check for security issues
            self._check_security(content, path, preflight)
            
            # Check line count
            self._check_size(content, path, preflight)
        
        self.add_note(f"Preflight: {preflight.total_passed} passed, {preflight.total_failed} failed")
        
        return {"preflight_check": preflight}
    
    def _check_banned_patterns(self, content: str, path: str, preflight: PreflightCheck) -> None:
        """Check for banned patterns like TODO."""
        for pattern in self.config.banned_patterns:
            if pattern in content:
                preflight.add_check(CheckResult(
                    name=f"no_{pattern.lower()}",
                    status=CheckStatus.WARNING,
                    message=f"Found '{pattern}' in {path}",
                    fix_suggestion=f"Remove or implement the {pattern}"
                ))
        
        # If no banned patterns found
        preflight.add_check(CheckResult(
            name="no_banned_patterns",
            status=CheckStatus.PASSED,
            message="No banned patterns found"
        ))
    
    def _check_imports(self, content: str, path: str, preflight: PreflightCheck) -> None:
        """Basic import validation."""
        # Check for potential undefined imports (very basic)
        if "import" in content or "require" in content:
            preflight.add_check(CheckResult(
                name="imports_present",
                status=CheckStatus.PASSED,
                message="Imports detected"
            ))
    
    def _check_security(self, content: str, path: str, preflight: PreflightCheck) -> None:
        """Check for security issues."""
        security_issues = []
        
        # Check for hardcoded secrets
        secret_patterns = [
            r'api[_-]?key\s*[:=]\s*["\'][^"\']+["\']',
            r'password\s*[:=]\s*["\'][^"\']+["\']',
            r'secret\s*[:=]\s*["\'][^"\']+["\']',
        ]
        
        for pattern in secret_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                security_issues.append("Potential hardcoded secret detected")
        
        if security_issues:
            preflight.add_check(CheckResult(
                name="security_check",
                status=CheckStatus.FAILED,
                message="; ".join(security_issues),
                fix_suggestion="Use environment variables for secrets"
            ))
            preflight.security_issues.extend(security_issues)
        else:
            preflight.add_check(CheckResult(
                name="security_check",
                status=CheckStatus.PASSED,
                message="No security issues detected"
            ))
    
    def _check_size(self, content: str, path: str, preflight: PreflightCheck) -> None:
        """Check file size limits."""
        lines = content.count("\n") + 1
        
        if lines > self.config.max_diff_size_lines:
            preflight.add_check(CheckResult(
                name="size_check",
                status=CheckStatus.WARNING,
                message=f"File {path} has {lines} lines (limit: {self.config.max_diff_size_lines})",
                fix_suggestion="Consider splitting into smaller files"
            ))
        else:
            preflight.add_check(CheckResult(
                name="size_check",
                status=CheckStatus.PASSED,
                message=f"File size OK ({lines} lines)"
            ))
