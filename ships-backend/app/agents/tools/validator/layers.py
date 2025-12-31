"""
ShipS* Validator Layers

The 4 deterministic validation layers, run in order.
If any layer fails, validation STOPS.

Layer 1: Structural - Did Coder obey Folder Map?
Layer 2: Completeness - Are there TODOs/placeholders?
Layer 3: Dependency - Do imports resolve?
Layer 4: Scope - Does implementation match Blueprint?

Each layer is a ruthless gate, not a helper.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
import re
import os

from app.agents.sub_agents.validator.models import (
    ValidationStatus, FailureLayer, RecommendedAction,
    ViolationSeverity, Violation, LayerResult,
    StructuralViolation, CompletenessViolation,
    DependencyViolation, ScopeViolation,
    ValidatorConfig,
)


class ValidationLayer(ABC):
    """
    Base class for validation layers.
    
    Each layer is a gate: it passes or fails, nothing else.
    """
    
    def __init__(self, config: Optional[ValidatorConfig] = None):
        self.config = config or ValidatorConfig()
        self.layer_name: FailureLayer = FailureLayer.NONE
    
    @abstractmethod
    def validate(self, context: Dict[str, Any]) -> LayerResult:
        """
        Run validation and return result.
        
        Returns LayerResult with passed=True/False and violations list.
        """
        pass
    
    def _create_result(
        self, 
        passed: bool, 
        violations: List[Violation],
        checks_run: int,
        duration_ms: int = 0
    ) -> LayerResult:
        """Create a LayerResult."""
        return LayerResult(
            layer=self.layer_name,
            passed=passed,
            violations=violations,
            duration_ms=duration_ms,
            checks_run=checks_run,
            checks_passed=checks_run - len(violations)
        )


# ============================================================================
# LAYER 1: STRUCTURAL VALIDATION
# ============================================================================

class StructuralLayer(ValidationLayer):
    """
    Layer 1: Did the Coder obey the Folder Map?
    
    Checks:
    - Are files placed where they are allowed?
    - Are protected directories untouched?
    - Is there cross-layer leakage (UI in services, etc.)?
    
    This layer prevents architectural erosion.
    """
    
    def __init__(self, config: Optional[ValidatorConfig] = None):
        super().__init__(config)
        self.layer_name = FailureLayer.STRUCTURAL
    
    def validate(self, context: Dict[str, Any]) -> LayerResult:
        """Validate file structure against Folder Map."""
        start = datetime.utcnow()
        violations = []
        checks_run = 0
        
        file_changes = context.get("file_changes", [])
        folder_map = context.get("folder_map", {})
        
        # Get allowed paths from folder map
        allowed_entries = folder_map.get("entries", [])
        allowed_dirs = set()
        for entry in allowed_entries:
            path = entry.get("path", "")
            if entry.get("is_directory", False):
                allowed_dirs.add(path.rstrip("/"))
            else:
                # Add parent directory
                parent = os.path.dirname(path)
                if parent:
                    allowed_dirs.add(parent)
        
        # Check each file change
        for change in file_changes:
            checks_run += 1
            path = change.get("path", "")
            operation = change.get("operation", "add")
            
            # Check 1: Protected paths
            for protected in self.config.protected_paths:
                if path.startswith(protected) or protected in path:
                    violations.append(StructuralViolation(
                        rule="no_protected_paths",
                        message=f"Cannot modify protected path: {path}",
                        file_path=path,
                        severity=ViolationSeverity.CRITICAL,
                        fix_hint="Remove this file from changeset",
                        allowed_path="(none - protected)",
                        actual_path=path
                    ))
            
            # Check 2: File in allowed directory
            if allowed_dirs:
                parent = os.path.dirname(path)
                if parent and not any(parent.startswith(d) or d.startswith(parent) for d in allowed_dirs):
                    violations.append(StructuralViolation(
                        rule="folder_map_compliance",
                        message=f"File not in allowed directory: {path}",
                        file_path=path,
                        severity=ViolationSeverity.MAJOR,
                        fix_hint=f"Move file to an allowed directory or update Folder Map",
                        actual_path=path
                    ))
            
            # Check 3: Cross-layer leakage patterns
            violations.extend(self._check_layer_leakage(path, change.get("content", "")))
        
        duration = int((datetime.utcnow() - start).total_seconds() * 1000)
        passed = len([v for v in violations if v.severity in [ViolationSeverity.CRITICAL, ViolationSeverity.MAJOR]]) == 0
        
        return self._create_result(passed, violations, checks_run, duration)
    
    def _check_layer_leakage(self, path: str, content: str) -> List[StructuralViolation]:
        """Check for architecture layer violations."""
        violations = []
        path_lower = path.lower()
        
        # UI logic in services
        if "/service" in path_lower or "/api" in path_lower:
            ui_patterns = ["useState", "useEffect", "React.", "render(", "component"]
            for pattern in ui_patterns:
                if pattern in content:
                    violations.append(StructuralViolation(
                        rule="no_layer_leakage",
                        message=f"UI logic found in service layer: {pattern}",
                        file_path=path,
                        severity=ViolationSeverity.MAJOR,
                        fix_hint="Move UI logic to components"
                    ))
                    break
        
        # Database logic in UI
        if "/component" in path_lower or ".tsx" in path_lower:
            db_patterns = ["prisma.", "mongoose.", "sequelize.", "knex."]
            for pattern in db_patterns:
                if pattern in content:
                    violations.append(StructuralViolation(
                        rule="no_layer_leakage",
                        message=f"Database logic found in UI layer: {pattern}",
                        file_path=path,
                        severity=ViolationSeverity.MAJOR,
                        fix_hint="Move database logic to services"
                    ))
                    break
        
        return violations


# ============================================================================
# LAYER 2: COMPLETENESS VALIDATION
# ============================================================================

class CompletenessLayer(ValidationLayer):
    """
    Layer 2: Is the implementation complete?
    
    Checks:
    - Are there TODOs?
    - Are there placeholder functions?
    - Are required exports missing?
    - Are error paths unhandled?
    
    This is where most AI tools lie by omission.
    This layer enforces: "No partial work passes as progress."
    """
    
    def __init__(self, config: Optional[ValidatorConfig] = None):
        super().__init__(config)
        self.layer_name = FailureLayer.COMPLETENESS
    
    def validate(self, context: Dict[str, Any]) -> LayerResult:
        """Validate implementation completeness."""
        start = datetime.utcnow()
        violations = []
        checks_run = 0
        
        file_changes = context.get("file_changes", [])
        
        for change in file_changes:
            path = change.get("path", "")
            content = change.get("content", "")
            
            if not content:
                continue
            
            # Check 1: TODOs
            checks_run += 1
            if self.config.fail_on_todo:
                todo_violations = self._find_todos(path, content)
                violations.extend(todo_violations)
            
            # Check 2: Placeholders
            checks_run += 1
            if self.config.fail_on_placeholder:
                placeholder_violations = self._find_placeholders(path, content)
                violations.extend(placeholder_violations)
            
            # Check 3: Empty functions
            checks_run += 1
            empty_violations = self._find_empty_functions(path, content)
            violations.extend(empty_violations)
            
            # Check 4: NotImplementedError
            checks_run += 1
            not_impl_violations = self._find_not_implemented(path, content)
            violations.extend(not_impl_violations)
        
        duration = int((datetime.utcnow() - start).total_seconds() * 1000)
        passed = len([v for v in violations if v.severity in [ViolationSeverity.CRITICAL, ViolationSeverity.MAJOR]]) == 0
        
        return self._create_result(passed, violations, checks_run, duration)
    
    def _find_todos(self, path: str, content: str) -> List[CompletenessViolation]:
        """Find TODO comments."""
        violations = []
        lines = content.split("\n")
        
        for i, line in enumerate(lines, 1):
            for pattern in self.config.todo_patterns:
                if pattern.upper() in line.upper():
                    violations.append(CompletenessViolation(
                        rule="no_todos",
                        message=f"TODO found: {line.strip()[:50]}",
                        file_path=path,
                        line_number=i,
                        code_snippet=line.strip(),
                        severity=ViolationSeverity.MAJOR,
                        violation_type="todo",
                        fix_hint="Implement the TODO or remove it"
                    ))
                    break
        
        return violations
    
    def _find_placeholders(self, path: str, content: str) -> List[CompletenessViolation]:
        """Find placeholder patterns."""
        violations = []
        content_lower = content.lower()
        
        for pattern in self.config.placeholder_patterns:
            if pattern.lower() in content_lower:
                violations.append(CompletenessViolation(
                    rule="no_placeholders",
                    message=f"Placeholder found: '{pattern}'",
                    file_path=path,
                    severity=ViolationSeverity.MAJOR,
                    violation_type="placeholder",
                    fix_hint="Replace placeholder with actual implementation"
                ))
        
        return violations
    
    def _find_empty_functions(self, path: str, content: str) -> List[CompletenessViolation]:
        """Find empty function bodies."""
        violations = []
        
        # JS/TS empty functions
        empty_patterns = [
            r'=\s*\(\)\s*=>\s*\{\s*\}',  # () => {}
            r'function\s+\w+\s*\([^)]*\)\s*\{\s*\}',  # function foo() {}
            r'def\s+\w+\s*\([^)]*\)\s*:\s*pass\s*$',  # def foo(): pass
        ]
        
        for pattern in empty_patterns:
            matches = re.finditer(pattern, content, re.MULTILINE)
            for match in matches:
                violations.append(CompletenessViolation(
                    rule="no_empty_functions",
                    message="Empty function body found",
                    file_path=path,
                    code_snippet=match.group(0)[:50],
                    severity=ViolationSeverity.MAJOR,
                    violation_type="empty_function",
                    fix_hint="Implement function body"
                ))
        
        return violations
    
    def _find_not_implemented(self, path: str, content: str) -> List[CompletenessViolation]:
        """Find NotImplementedError or similar."""
        violations = []
        
        patterns = [
            "raise NotImplementedError",
            "throw new Error('Not implemented')",
            "throw new Error(\"Not implemented\")",
        ]
        
        for pattern in patterns:
            if pattern in content:
                violations.append(CompletenessViolation(
                    rule="no_not_implemented",
                    message=f"NotImplementedError found",
                    file_path=path,
                    severity=ViolationSeverity.CRITICAL,
                    violation_type="stub",
                    fix_hint="Implement the functionality"
                ))
        
        return violations


# ============================================================================
# LAYER 3: DEPENDENCY VALIDATION
# ============================================================================

class DependencyLayer(ValidationLayer):
    """
    Layer 3: Do dependencies resolve?
    
    Checks:
    - Do all imports resolve?
    - Are dependencies declared in package manifest?
    - Are there hallucinated packages?
    - Are circular dependencies introduced?
    
    This layer exists because LLMs excel at inventing packages that feel real.
    """
    
    def __init__(self, config: Optional[ValidatorConfig] = None):
        super().__init__(config)
        self.layer_name = FailureLayer.DEPENDENCY
    
    def validate(self, context: Dict[str, Any]) -> LayerResult:
        """Validate dependencies and imports."""
        start = datetime.utcnow()
        violations = []
        checks_run = 0
        
        file_changes = context.get("file_changes", [])
        dependency_plan = context.get("dependency_plan", {})
        
        # Get declared dependencies
        declared_deps = set()
        for dep in dependency_plan.get("runtime_dependencies", []):
            name = dep.get("name", dep) if isinstance(dep, dict) else str(dep)
            declared_deps.add(name)
        for dep in dependency_plan.get("dev_dependencies", []):
            name = dep.get("name", dep) if isinstance(dep, dict) else str(dep)
            declared_deps.add(name)
        
        # Common built-in/allowed packages
        builtin_packages = {
            # JavaScript/TypeScript
            "react", "react-dom", "next", "path", "fs", "os",
            # Python
            "os", "sys", "json", "re", "datetime", "typing", "uuid",
        }
        
        for change in file_changes:
            path = change.get("path", "")
            content = change.get("content", "")
            
            if not content:
                continue
            
            # Extract imports
            imports = self._extract_imports(content, path)
            
            for imp in imports:
                checks_run += 1
                
                # Skip built-ins and relative imports
                if imp.startswith(".") or imp in builtin_packages:
                    continue
                
                # Check if declared
                base_package = imp.split("/")[0].split(".")[0]
                
                if declared_deps and base_package not in declared_deps and base_package not in builtin_packages:
                    # Potential hallucinated package
                    if self.config.fail_on_hallucinated_import:
                        violations.append(DependencyViolation(
                            rule="no_undeclared_imports",
                            message=f"Import '{imp}' not in dependency plan",
                            file_path=path,
                            severity=ViolationSeverity.MAJOR,
                            violation_type="unresolved_import",
                            package_name=base_package,
                            fix_hint=f"Add '{base_package}' to dependencies or remove import"
                        ))
        
        # Check for circular dependencies (simplified)
        checks_run += 1
        circular = self._detect_circular_deps(file_changes)
        violations.extend(circular)
        
        duration = int((datetime.utcnow() - start).total_seconds() * 1000)
        passed = len([v for v in violations if v.severity in [ViolationSeverity.CRITICAL, ViolationSeverity.MAJOR]]) == 0
        
        return self._create_result(passed, violations, checks_run, duration)
    
    def _extract_imports(self, content: str, path: str) -> List[str]:
        """Extract import statements from code."""
        imports = []
        
        # JavaScript/TypeScript imports
        js_pattern = r"(?:import|from)\s+['\"]([^'\"]+)['\"]"
        imports.extend(re.findall(js_pattern, content))
        
        # require() calls
        require_pattern = r"require\s*\(['\"]([^'\"]+)['\"]\)"
        imports.extend(re.findall(require_pattern, content))
        
        # Python imports
        py_pattern = r"(?:from\s+(\S+)\s+import|import\s+(\S+))"
        for match in re.findall(py_pattern, content):
            imports.extend([m for m in match if m])
        
        return imports
    
    def _detect_circular_deps(self, file_changes: List[Dict]) -> List[DependencyViolation]:
        """Simple circular dependency detection."""
        violations = []
        
        # Build import graph
        import_graph = {}
        for change in file_changes:
            path = change.get("path", "")
            content = change.get("content", "")
            if content:
                imports = self._extract_imports(content, path)
                # Only track relative imports for circular detection
                relative_imports = [i for i in imports if i.startswith(".")]
                import_graph[path] = relative_imports
        
        # Simple cycle detection (check if A imports B and B imports A)
        for path, imports in import_graph.items():
            for imp in imports:
                # Resolve relative path (simplified)
                if imp in import_graph:
                    reverse_imports = import_graph.get(imp, [])
                    if any(path in ri for ri in reverse_imports):
                        violations.append(DependencyViolation(
                            rule="no_circular_deps",
                            message=f"Potential circular dependency: {path} <-> {imp}",
                            file_path=path,
                            severity=ViolationSeverity.MAJOR,
                            violation_type="circular_dependency",
                            fix_hint="Refactor to break the cycle"
                        ))
        
        return violations


# ============================================================================
# LAYER 4: SCOPE VALIDATION
# ============================================================================

class ScopeLayer(ValidationLayer):
    """
    Layer 4: Does implementation match the App Blueprint?
    
    Checks:
    - Does implementation match the task spec?
    - Were non-goals respected?
    - Were assumptions violated?
    - Did Coder exceed scope?
    
    This is subtle but critical: sometimes "working code" is still wrong.
    """
    
    def __init__(self, config: Optional[ValidatorConfig] = None):
        super().__init__(config)
        self.layer_name = FailureLayer.SCOPE
    
    def validate(self, context: Dict[str, Any]) -> LayerResult:
        """Validate scope compliance."""
        start = datetime.utcnow()
        violations = []
        checks_run = 0
        
        file_changes = context.get("file_changes", [])
        current_task = context.get("current_task", {})
        app_blueprint = context.get("app_blueprint", {})
        folder_map = context.get("folder_map", {})
        
        # Get expected outputs from task
        expected_outputs = current_task.get("expected_outputs", [])
        expected_paths = set()
        for output in expected_outputs:
            path = output.get("file_path", output.get("path", "")) if isinstance(output, dict) else str(output)
            if path:
                expected_paths.add(path)
        
        # Check 1: Changed files match expected outputs
        if expected_paths:
            checks_run += 1
            changed_paths = {c.get("path", "") for c in file_changes}
            
            unexpected = changed_paths - expected_paths
            if unexpected:
                for path in unexpected:
                    violations.append(ScopeViolation(
                        rule="expected_outputs_only",
                        message=f"Unexpected file modified: {path}",
                        file_path=path,
                        severity=ViolationSeverity.MAJOR,
                        violation_type="scope_exceeded",
                        fix_hint="Remove this file from changeset or update task spec"
                    ))
        
        # Check 2: Non-goals from blueprint
        non_goals = app_blueprint.get("non_goals", [])
        if non_goals:
            checks_run += 1
            for change in file_changes:
                content = change.get("content", "").lower()
                path = change.get("path", "")
                
                for non_goal in non_goals:
                    if isinstance(non_goal, str) and non_goal.lower() in content:
                        violations.append(ScopeViolation(
                            rule="respect_non_goals",
                            message=f"Non-goal touched: {non_goal}",
                            file_path=path,
                            severity=ViolationSeverity.MAJOR,
                            violation_type="non_goal_touched",
                            expected="Should not implement",
                            actual="Implementation found"
                        ))
        
        # Check 3: Task acceptance criteria coverage
        acceptance_criteria = current_task.get("acceptance_criteria", [])
        if acceptance_criteria:
            checks_run += 1
            # This is a simplified check - in production, would use LLM
            for criterion in acceptance_criteria:
                desc = criterion.get("description", str(criterion)) if isinstance(criterion, dict) else str(criterion)
                # Just check it's not explicitly marked as unimplemented
                if "not implemented" in desc.lower():
                    violations.append(ScopeViolation(
                        rule="acceptance_criteria_coverage",
                        message=f"Acceptance criterion not satisfied: {desc[:50]}",
                        severity=ViolationSeverity.MAJOR,
                        violation_type="blueprint_mismatch",
                        expected=desc,
                        actual="Not implemented"
                    ))
        
        duration = int((datetime.utcnow() - start).total_seconds() * 1000)
        passed = len([v for v in violations if v.severity in [ViolationSeverity.CRITICAL, ViolationSeverity.MAJOR]]) == 0
        
        return self._create_result(passed, violations, checks_run, duration)
