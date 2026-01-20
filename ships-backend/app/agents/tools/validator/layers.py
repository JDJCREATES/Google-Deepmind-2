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


import subprocess
import json
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
import re
import os

from app.agents.sub_agents.validator.models import (
    ValidationStatus, FailureLayer, RecommendedAction,
    ViolationSeverity, Violation, LayerResult,
    StructuralViolation, CompletenessViolation,
    DependencyViolation, ScopeViolation, BuildViolation,
    ValidatorConfig,
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
            
        # Check 4: Verify Deletions (Production Hardening)
        # If FolderMap says "delete", file MUST NOT exist
        for entry in allowed_entries:
            if entry.get("action") == "delete":
                target_path = entry.get("path", "")
                full_target_path = os.path.join(context.get("project_path", ""), target_path)
                
                # Check if it still exists on disk OR in the change set (as an add/modify)
                exists_on_disk = os.path.exists(full_target_path)
                reintroduced_in_changes = any(
                    c.get("path") == target_path and c.get("operation") != "delete" 
                    for c in file_changes
                )
                
                if exists_on_disk and not reintroduced_in_changes:
                     # Check if it was deleted in this very changeset involved?
                     # Ideally the changeset should have operation='delete' for this path
                     was_deleted = any(
                        c.get("path") == target_path and c.get("operation") == "delete"
                        for c in file_changes
                     )
                     
                     if not was_deleted:
                        violations.append(StructuralViolation(
                            rule="enforce_deletion",
                            message=f"File marked for deletion still exists: {target_path}",
                            file_path=target_path,
                            severity=ViolationSeverity.MAJOR,
                            fix_hint="Delete this file as required by Folder Map",
                            actual_path=target_path
                        ))
        
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
        project_path = context.get("project_path")
        
        # Get declared dependencies from plan
        declared_deps = set()
        for dep in dependency_plan.get("runtime_dependencies", []):
            name = dep.get("name", dep) if isinstance(dep, dict) else str(dep)
            declared_deps.add(name)
        for dep in dependency_plan.get("dev_dependencies", []):
            name = dep.get("name", dep) if isinstance(dep, dict) else str(dep)
            declared_deps.add(name)
        
        # ALSO check actual package.json if it exists
        package_json_deps = set()
        if project_path:
            import json
            from pathlib import Path
            pkg_path = Path(project_path) / "package.json"
            if pkg_path.exists():
                try:
                    with open(pkg_path) as f:
                        pkg_data = json.load(f)
                        package_json_deps.update(pkg_data.get("dependencies", {}).keys())
                        package_json_deps.update(pkg_data.get("devDependencies", {}).keys())
                except:
                    pass
        
        # Combine both sources
        all_declared = declared_deps | package_json_deps
        
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
                
                if all_declared and base_package not in all_declared and base_package not in builtin_packages:
                    # Potential hallucinated package or missing from package.json
                    if self.config.fail_on_hallucinated_import:
                        violations.append(DependencyViolation(
                            rule="no_undeclared_imports",
                            message=f"Import '{imp}' not in dependency plan or package.json - add to package.json dependencies",
                            file_path=path,
                            severity=ViolationSeverity.MAJOR,
                            violation_type="unresolved_import",
                            package_name=base_package,
                            fix_hint=f"Add '{base_package}' to package.json dependencies or devDependencies"
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


# ============================================================================
# LAYER 5: BUILD VALIDATION
# ============================================================================

class BuildLayer(ValidationLayer):
    """
    Layer 5: Does it build?
    
    Checks:
    - Runs 'npm install' to ensure dependencies are present
    - Runs 'npm run build' (if package.json exists)
    - Verifies exit code 0
    - Captures stderr/stdout and extracts specific error messages
    
    This is the ultimate truth. Code that doesn't build is useless.
    """
    
    def __init__(self, config: Optional[ValidatorConfig] = None):
        super().__init__(config)
        self.layer_name = FailureLayer.BUILD
    
    def validate(self, context: Dict[str, Any]) -> LayerResult:
        """Run build verification with npm install + npm run build."""
        import logging
        logger = logging.getLogger("ships.validator")
        
        start = datetime.utcnow()
        violations = []
        checks_run = 0
        
        project_path = context.get("project_path", "")
        if not project_path or not os.path.exists(project_path):
            # No project path, cannot build
            logger.debug("[BUILD] No project_path provided, skipping build validation")
            return self._create_result(True, [], 0, 0)
        
        # SMART DETECTION: Find package.json based on actual file paths from this run
        # Look at file_changes to determine the actual working directory
        file_changes = context.get("file_changes", [])
        folder_map = context.get("folder_map", {})
        working_dir = None
        
        if file_changes:
            # Extract directory from first file change
            for change in file_changes:
                file_path = change.get("path", "")
                if file_path:
                    # File path might be relative or absolute
                    # Example: "ships-test-scaffold/src/app/page.tsx" or "/full/path/to/file.tsx"
                    parts = file_path.replace("\\", "/").split("/")
                    
                    # Find the root-most directory that might contain package.json
                    # Typically: if path is "subfolder/src/...", the root is "subfolder"
                    if len(parts) > 1:
                        # Check if it's an absolute path starting with project_path
                        if os.path.isabs(file_path):
                            # Absolute path - extract relative to project_path
                            try:
                                rel_path = os.path.relpath(file_path, project_path)
                                first_dir = rel_path.split(os.sep)[0]
                                if first_dir != "..":
                                    potential_root = os.path.join(project_path, first_dir)
                                    if os.path.exists(os.path.join(potential_root, "package.json")):
                                        working_dir = potential_root
                                        break
                            except ValueError:
                                pass
                        else:
                            # Relative path - first component is likely the project root
                            first_dir = parts[0]
                            potential_root = os.path.join(project_path, first_dir)
                            if os.path.exists(os.path.join(potential_root, "package.json")):
                                working_dir = potential_root
                                logger.info(f"[BUILD] 📁 Detected project root from file_changes: {first_dir}")
                                break
        
        # FALLBACK 1: If no file_changes, try folder_map entries
        if not working_dir and folder_map:
            entries = folder_map.get("entries", [])
            for entry in entries:
                file_path = entry.get("path", "")
                if file_path:
                    parts = file_path.replace("\\", "/").split("/")
                    if len(parts) > 1:
                        first_dir = parts[0]
                        potential_root = os.path.join(project_path, first_dir)
                        if os.path.exists(os.path.join(potential_root, "package.json")):
                            working_dir = potential_root
                            logger.info(f"[BUILD] 📁 Detected project root from folder_map: {first_dir}")
                            break
        
        # FALLBACK 2: Scan immediate subdirectories for package.json
        if not working_dir:
            try:
                for item in os.listdir(project_path):
                    item_path = os.path.join(project_path, item)
                    if os.path.isdir(item_path):
                        pkg_check = os.path.join(item_path, "package.json")
                        if os.path.exists(pkg_check):
                            working_dir = item_path
                            logger.info(f"[BUILD] 📁 Detected project root from directory scan: {item}")
                            break
            except Exception as scan_err:
                logger.debug(f"[BUILD] Directory scan failed: {scan_err}")
        
        # Fallback: Check project_path root first, then fail
        pkg_path = os.path.join(project_path, "package.json") if not working_dir else os.path.join(working_dir, "package.json")
        actual_project_root = working_dir if working_dir else project_path
        
        if not os.path.exists(pkg_path):
            # Try root as last resort
            root_pkg = os.path.join(project_path, "package.json")
            if os.path.exists(root_pkg):
                pkg_path = root_pkg
                actual_project_root = project_path
            else:
                # No package.json found based on actual file paths - not a node project
                logger.debug(f"[BUILD] No package.json found at {pkg_path} or {root_pkg}, skipping build validation")
                return self._create_result(True, [], 0, 0)
        
        logger.info(f"[BUILD] 🔨 Running build validation for: {actual_project_root}")
        
        # Check for build script
        checks_run += 1
        try:
            with open(pkg_path, "r", encoding="utf-8") as f:
                pkg_data = json.load(f)
            
            scripts = pkg_data.get("scripts", {})
            
            # Step 1: Run npm install to ensure dependencies are present
            checks_run += 1
            logger.info("[BUILD] 📦 Running npm install...")
            try:
                install_result = subprocess.run(
                    "npm install",
                    cwd=actual_project_root,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=180  # 3 minute timeout for install
                )
                
                if install_result.returncode != 0:
                    # npm install failed - likely invalid package.json or network issue
                    error_msg = self._extract_error_message(install_result.stderr, install_result.stdout)
                    violations.append(BuildViolation(
                        rule="npm_install_success",
                        message=f"npm install failed: {error_msg}",
                        layer=FailureLayer.BUILD,
                        severity=ViolationSeverity.CRITICAL,
                        command="npm install",
                        stdout=install_result.stdout[-1500:] if install_result.stdout else "",
                        stderr=install_result.stderr[-1500:] if install_result.stderr else "",
                        fix_hint="Check package.json for invalid dependencies or syntax errors"
                    ))
                    # Don't continue to build if install failed
                    duration = int((datetime.utcnow() - start).total_seconds() * 1000)
                    return self._create_result(False, violations, checks_run, duration)
                else:
                    logger.info("[BUILD] ✅ npm install succeeded")
                    
            except subprocess.TimeoutExpired:
                violations.append(BuildViolation(
                    rule="npm_install_timeout",
                    message="npm install timed out after 180s",
                    layer=FailureLayer.BUILD,
                    severity=ViolationSeverity.MAJOR,
                    fix_hint="Check network connection or remove problematic dependencies"
                ))
                duration = int((datetime.utcnow() - start).total_seconds() * 1000)
                return self._create_result(False, violations, checks_run, duration)
            
            # Step 2: Run npm run build (if script exists)
            if "build" not in scripts:
                # No build script - try dev script with a quick timeout to catch import errors
                if "dev" in scripts:
                    logger.info("[BUILD] No build script, running quick dev check...")
                    checks_run += 1
                    try:
                        # Run dev server briefly to catch import errors
                        dev_result = subprocess.run(
                            "npm run dev",
                            cwd=actual_project_root,
                            shell=True,
                            capture_output=True,
                            text=True,
                            timeout=15  # 15 second timeout - just to catch initial errors
                        )
                        # Dev server will timeout (which is expected), check stderr for errors
                        if dev_result.stderr:
                            error_msg = self._extract_error_message(dev_result.stderr, dev_result.stdout)
                            if error_msg and ("failed to resolve" in error_msg.lower() or 
                                            "module not found" in error_msg.lower() or
                                            "cannot find module" in error_msg.lower()):
                                violations.append(BuildViolation(
                                    rule="dev_server_error",
                                    message=f"Dev server error: {error_msg}",
                                    layer=FailureLayer.BUILD,
                                    severity=ViolationSeverity.CRITICAL,
                                    command="npm run dev",
                                    stderr=dev_result.stderr[-1500:],
                                    fix_hint=f"Install missing dependency: {error_msg}"
                                ))
                    except subprocess.TimeoutExpired:
                        # Timeout is expected for dev server - this is fine
                        logger.info("[BUILD] Dev server check passed (no immediate errors)")
                else:
                    logger.debug("[BUILD] No build or dev script found")
            else:
                checks_run += 1
                logger.info("[BUILD] 🏗️ Running npm run build...")
                try:
                    # Capture output
                    result = subprocess.run(
                        "npm run build",
                        cwd=actual_project_root,
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=120  # 2 minute timeout for build
                    )
                    
                    if result.returncode != 0:
                        # Build failed - extract meaningful error
                        error_msg = self._extract_error_message(result.stderr, result.stdout)
                        logger.error(f"[BUILD] ❌ Build failed: {error_msg}")
                        
                        violations.append(BuildViolation(
                            rule="build_success",
                            message=f"Build failed: {error_msg}",
                            layer=FailureLayer.BUILD,
                            severity=ViolationSeverity.CRITICAL,
                            command="npm run build",
                            stdout=result.stdout[-1500:] if result.stdout else "",
                            stderr=result.stderr[-1500:] if result.stderr else "",
                            fix_hint=f"Fix: {error_msg}"
                        ))
                    else:
                        logger.info("[BUILD] ✅ npm run build succeeded")
                        
                except subprocess.TimeoutExpired:
                    violations.append(BuildViolation(
                        rule="build_timeout",
                        message="Build timed out after 120s",
                        layer=FailureLayer.BUILD,
                        severity=ViolationSeverity.MAJOR,
                        fix_hint="Optimize build or increase timeout"
                    ))
                except Exception as e:
                    violations.append(BuildViolation(
                        rule="build_execution_error",
                        message=f"Failed to execute build: {str(e)}",
                        layer=FailureLayer.BUILD,
                        severity=ViolationSeverity.CRITICAL,
                        fix_hint="Check system environment"
                    ))
                    
        except json.JSONDecodeError:
             violations.append(BuildViolation(
                rule="valid_package_json",
                message="package.json is invalid JSON",
                layer=FailureLayer.BUILD,
                severity=ViolationSeverity.CRITICAL,
                file_path=pkg_path,
                fix_hint="Fix JSON syntax in package.json"
            ))
        except Exception as e:
             violations.append(BuildViolation(
                rule="package_json_read_error",
                message=f"Could not read package.json: {str(e)}",
                layer=FailureLayer.BUILD,
                severity=ViolationSeverity.MAJOR
            ))
            
        duration = int((datetime.utcnow() - start).total_seconds() * 1000)
        passed = len([v for v in violations if v.severity in [ViolationSeverity.CRITICAL, ViolationSeverity.MAJOR]]) == 0
        
        if passed:
            logger.info(f"[BUILD] ✅ Build validation passed in {duration}ms")
        else:
            logger.warning(f"[BUILD] ❌ Build validation failed with {len(violations)} violations")
        
        return self._create_result(passed, violations, checks_run, duration)
    
    def _extract_error_message(self, stderr: str, stdout: str) -> str:
        """Extract the most relevant error message from build output."""
        combined = (stderr or "") + (stdout or "")
        
        # Common error patterns to look for
        patterns = [
            r"Failed to resolve import ['\"]([^'\"]+)['\"]",  # Vite/ESBuild import error
            r"Module not found: Error: Can't resolve ['\"]([^'\"]+)['\"]",  # Webpack
            r"Cannot find module ['\"]([^'\"]+)['\"]",  # Node.js
            r"error TS\d+: (.+)",  # TypeScript errors
            r"SyntaxError: (.+)",  # JS Syntax errors
            r"Error: (.+)",  # Generic errors
        ]
        
        for pattern in patterns:
            match = re.search(pattern, combined, re.IGNORECASE)
            if match:
                return match.group(0)[:200]  # Return the full match, truncated
        
        # Fallback: find any line with "error" in it
        for line in combined.split("\n"):
            if "error" in line.lower() and len(line.strip()) > 10:
                return line.strip()[:200]
        
        return "Unknown build error (check full output)"


# ============================================================================
# LAYER 6: UNIFIED LANGUAGE CHECKER (TypeScript, Python, Rust, Go, CSS, ESLint)
# ============================================================================

class LanguageCheckerLayer(ValidationLayer):
    """
    Unified language checker layer.
    
    Uses the CheckerRegistry to auto-detect project types and run
    all applicable language checkers (TypeScript, Python, Rust, Go, CSS, ESLint).
    
    Results are aggregated and reported to the diagnostics store.
    Performance: Registry is cached, checkers run in parallel.
    """
    
    # Class-level registry cache (shared across instances)
    _registry = None
    
    def __init__(self, config: Optional[ValidatorConfig] = None):
        super().__init__(config)
        self.layer_name = FailureLayer.DEPENDENCY
        
        # Lazy-init registry once
        if LanguageCheckerLayer._registry is None:
            from app.agents.tools.validator.checkers import CheckerRegistry
            LanguageCheckerLayer._registry = CheckerRegistry()
    
    def validate(self, context: Dict[str, Any]) -> LayerResult:
        """Run all applicable language checkers (parallel execution)."""
        start = datetime.utcnow()
        violations = []
        checks_run = 0
        
        project_path = context.get("project_path", "")
        if not project_path:
            return self._create_result(True, [], 0, 0)
        
        # Run all applicable checkers via cached registry
        result = self._registry.run_all(project_path, report_diagnostics=True)
        
        # Convert checker errors to validation violations (limit to 50 total)
        total_violations = 0
        MAX_VIOLATIONS = 50
        
        for checker_name, checker_result in result.results.items():
            if checker_result.skipped:
                continue
            
            checks_run += 1
            
            for error in checker_result.errors:
                if total_violations >= MAX_VIOLATIONS:
                    break
                    
                violations.append(Violation(
                    id=f"{error.source}_{error.code or 'err'}_{error.line}",
                    rule=f"{checker_name}_error",
                    message=f"[{error.source.upper()}] {error.code or ''}: {error.message}",
                    file_path=error.file,
                    line_number=error.line,
                    severity=ViolationSeverity.MAJOR,
                    layer=FailureLayer.DEPENDENCY,
                    fix_hint=f"Fix {checker_name} error: {error.message[:80]}"
                ))
                total_violations += 1
        
        duration = int((datetime.utcnow() - start).total_seconds() * 1000)
        passed = len(violations) == 0
        
        return self._create_result(passed, violations, checks_run, duration)


# Keep TypeScriptLayer as an alias for backwards compatibility
TypeScriptLayer = LanguageCheckerLayer


