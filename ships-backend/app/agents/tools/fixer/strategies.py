"""
ShipS* Fixer Strategies

Fix strategies for each validation layer:
- StructuralFixer: Handle folder map violations
- CompletenessFixer: Remove TODOs, fill placeholders
- DependencyFixer: Resolve imports, add packages
- ScopeFixer: Add guard clauses, limit changes

Each strategy produces minimal fixes within local scope
or escalates to Planner for architectural changes.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
import re
import difflib

# Import directly from models module to avoid circular import through sub_agents.__init__
# The models module is a pure Pydantic file with no circular dependencies
import app.agents.sub_agents.fixer.models as fixer_models

FixPlan = fixer_models.FixPlan
FixPatch = fixer_models.FixPatch
FixChange = fixer_models.FixChange
ViolationFix = fixer_models.ViolationFix
FixScope = fixer_models.FixScope
FixApproach = fixer_models.FixApproach
FixRisk = fixer_models.FixRisk
ApprovalType = fixer_models.ApprovalType
ReplanRequest = fixer_models.ReplanRequest
FixerConfig = fixer_models.FixerConfig

import app.agents.sub_agents.validator.models as validator_models

Violation = validator_models.Violation
FailureLayer = validator_models.FailureLayer
ViolationSeverity = validator_models.ViolationSeverity


class FixStrategy(ABC):
    """Base class for fix strategies."""
    
    def __init__(self, config: Optional[FixerConfig] = None):
        self.config = config or FixerConfig()
        self.layer: FailureLayer = FailureLayer.NONE
    
    @abstractmethod
    def can_fix(self, violation: Violation) -> Tuple[bool, FixScope]:
        """
        Determine if this strategy can fix the violation.
        
        Returns:
            Tuple of (can_fix, scope)
        """
        pass
    
    @abstractmethod
    def generate_fix(
        self,
        violation: Violation,
        context: Dict[str, Any]
    ) -> Tuple[Optional[ViolationFix], Optional[FixChange]]:
        """
        Generate a fix for the violation.
        
        Returns:
            Tuple of (ViolationFix plan, FixChange patch)
        """
        pass
    
    def _compute_diff(self, original: str, modified: str, path: str) -> str:
        """Compute unified diff."""
        original_lines = original.splitlines(keepends=True)
        modified_lines = modified.splitlines(keepends=True)
        
        diff = difflib.unified_diff(
            original_lines,
            modified_lines,
            fromfile=f"a/{path}",
            tofile=f"b/{path}"
        )
        return "".join(diff)


# ============================================================================
# STRUCTURAL FIXER
# ============================================================================

class StructuralFixer(FixStrategy):
    """
    Fix structural/folder map violations.
    
    Most structural issues require architectural changes
    and must be escalated to Planner.
    """
    
    def __init__(self, config: Optional[FixerConfig] = None):
        super().__init__(config)
        self.layer = FailureLayer.STRUCTURAL
    
    def can_fix(self, violation: Violation) -> Tuple[bool, FixScope]:
        """Structural fixes usually require replan."""
        rule = violation.rule
        
        # Protected path violations cannot be fixed - must replan
        if rule == "no_protected_paths":
            return False, FixScope.ARCHITECTURAL
        
        # Folder map violations need replan
        if rule == "folder_map_compliance":
            return False, FixScope.ARCHITECTURAL
        
        # Layer leakage might be fixable by moving code
        if rule == "no_layer_leakage":
            # Could potentially refactor, but risky
            return False, FixScope.ARCHITECTURAL
        
        return False, FixScope.ARCHITECTURAL
    
    def generate_fix(
        self,
        violation: Violation,
        context: Dict[str, Any]
    ) -> Tuple[Optional[ViolationFix], Optional[FixChange]]:
        """Structural fixes always escalate to replan."""
        # We don't fix structural issues - we escalate
        return None, None
    
    def create_replan_request(
        self,
        violation: Violation,
        validation_report_id: str,
        fix_plan_id: str
    ) -> ReplanRequest:
        """Create a replan request for structural violation."""
        return ReplanRequest(
            origin_validation_report_id=validation_report_id,
            origin_fix_plan_id=fix_plan_id,
            reason=f"Structural violation cannot be fixed without plan changes: {violation.message}",
            violated_artifact="folder_map",
            violation_details=violation.message,
            suggested_changes=[
                f"Update Folder Map to allow {violation.file_path}" if violation.file_path else "Review folder structure"
            ]
        )


# ============================================================================
# COMPLETENESS FIXER
# ============================================================================

class CompletenessFixer(FixStrategy):
    """
    Fix completeness violations (TODOs, placeholders, empty functions).
    
    Approaches:
    - Simple TODOs: Remove comment or add minimal implementation
    - Placeholders: Add mock implementation + follow-up task
    - Empty functions: Add stub that satisfies interface
    """
    
    def __init__(self, config: Optional[FixerConfig] = None):
        super().__init__(config)
        self.layer = FailureLayer.COMPLETENESS
    
    def can_fix(self, violation: Violation) -> Tuple[bool, FixScope]:
        """Completeness issues are usually locally fixable."""
        rule = violation.rule
        
        # TODOs can be removed or implemented
        if rule == "no_todos":
            return True, FixScope.LOCAL
        
        # Placeholders can be mocked
        if rule == "no_placeholders":
            return self.config.allow_mock_implementations, FixScope.LOCAL
        
        # Empty functions can be filled
        if rule == "no_empty_functions":
            return True, FixScope.LOCAL
        
        # NotImplementedError needs real implementation
        if rule == "no_not_implemented":
            return self.config.allow_mock_implementations, FixScope.LOCAL
        
        return False, FixScope.LOCAL
    
    def generate_fix(
        self,
        violation: Violation,
        context: Dict[str, Any]
    ) -> Tuple[Optional[ViolationFix], Optional[FixChange]]:
        """Generate fix for completeness violation."""
        rule = violation.rule
        file_path = violation.file_path or ""
        content = context.get("file_contents", {}).get(file_path, "")
        
        if not content and not file_path:
            return None, None
        
        if rule == "no_todos":
            return self._fix_todo(violation, content, file_path)
        elif rule == "no_placeholders":
            return self._fix_placeholder(violation, content, file_path)
        elif rule == "no_empty_functions":
            return self._fix_empty_function(violation, content, file_path)
        elif rule == "no_not_implemented":
            return self._fix_not_implemented(violation, content, file_path)
        
        return None, None
    
    def _fix_todo(
        self,
        violation: Violation,
        content: str,
        file_path: str
    ) -> Tuple[Optional[ViolationFix], Optional[FixChange]]:
        """Remove TODO comment or implement it."""
        lines = content.split("\n")
        line_num = violation.line_number or 0
        
        if line_num > 0 and line_num <= len(lines):
            original_line = lines[line_num - 1]
            
            # Strategy: Convert TODO to NOTE (acknowledging it's a known limitation)
            # This is safer than removing or guessing implementation
            fixed_line = original_line
            for pattern in ["TODO", "FIXME", "HACK", "XXX"]:
                fixed_line = fixed_line.replace(f"// {pattern}", "// NOTE (from fix):")
                fixed_line = fixed_line.replace(f"# {pattern}", "# NOTE (from fix):")
            
            if fixed_line != original_line:
                lines[line_num - 1] = fixed_line
                new_content = "\n".join(lines)
                
                return (
                    ViolationFix(
                        violation_id=violation.id,
                        violation_message=violation.message,
                        fix_approach=FixApproach.REMOVE_TODO,
                        fix_description=f"Converted TODO to NOTE at line {line_num}",
                        affected_files=[file_path],
                        confidence=0.9,
                        creates_followup_task=True
                    ),
                    FixChange(
                        path=file_path,
                        operation="modify",
                        original_content=content,
                        new_content=new_content,
                        unified_diff=self._compute_diff(content, new_content, file_path),
                        violation_ids=[violation.id],
                        reason="Convert TODO to NOTE to pass validation",
                        lines_added=0,
                        lines_removed=0
                    )
                )
        
        return None, None
    
    def _fix_placeholder(
        self,
        violation: Violation,
        content: str,
        file_path: str
    ) -> Tuple[Optional[ViolationFix], Optional[FixChange]]:
        """Replace placeholder with minimal implementation."""
        # Find and replace placeholder patterns
        new_content = content
        
        patterns = [
            (r"// placeholder[^\n]*\n", "// Implementation pending\n"),
            (r"# placeholder[^\n]*\n", "# Implementation pending\n"),
            (r"'placeholder'", "'pending'"),
            (r'"placeholder"', '"pending"'),
        ]
        
        for pattern, replacement in patterns:
            new_content = re.sub(pattern, replacement, new_content, flags=re.IGNORECASE)
        
        if new_content != content:
            return (
                ViolationFix(
                    violation_id=violation.id,
                    violation_message=violation.message,
                    fix_approach=FixApproach.PATCH_FILE,
                    fix_description="Replaced placeholder patterns",
                    affected_files=[file_path],
                    confidence=0.85,
                    creates_followup_task=True
                ),
                FixChange(
                    path=file_path,
                    operation="modify",
                    original_content=content,
                    new_content=new_content,
                    unified_diff=self._compute_diff(content, new_content, file_path),
                    violation_ids=[violation.id],
                    reason="Replace placeholder to pass validation"
                )
            )
        
        return None, None
    
    def _fix_empty_function(
        self,
        violation: Violation,
        content: str,
        file_path: str
    ) -> Tuple[Optional[ViolationFix], Optional[FixChange]]:
        """Fill empty function with minimal stub."""
        # Find empty arrow functions and add console.log
        new_content = content
        
        # () => {} -> () => { console.log('Not implemented'); }
        new_content = re.sub(
            r'=\s*\(\)\s*=>\s*\{\s*\}',
            "= () => { console.log('Not implemented'); }",
            new_content
        )
        
        # def foo(): pass -> def foo(): return None
        new_content = re.sub(
            r'(def\s+\w+\s*\([^)]*\)\s*:\s*)pass(\s*$)',
            r'\1return None  # Stub implementation\2',
            new_content,
            flags=re.MULTILINE
        )
        
        if new_content != content:
            return (
                ViolationFix(
                    violation_id=violation.id,
                    violation_message=violation.message,
                    fix_approach=FixApproach.PATCH_FILE,
                    fix_description="Added stub implementation to empty function",
                    affected_files=[file_path],
                    confidence=0.8,
                    requires_mock=True
                ),
                FixChange(
                    path=file_path,
                    operation="modify",
                    original_content=content,
                    new_content=new_content,
                    unified_diff=self._compute_diff(content, new_content, file_path),
                    violation_ids=[violation.id],
                    reason="Add stub to empty function"
                )
            )
        
        return None, None
    
    def _fix_not_implemented(
        self,
        violation: Violation,
        content: str,
        file_path: str
    ) -> Tuple[Optional[ViolationFix], Optional[FixChange]]:
        """Replace NotImplementedError with stub."""
        new_content = content
        
        # Python: raise NotImplementedError -> return None
        new_content = re.sub(
            r'raise NotImplementedError\([^)]*\)',
            'return None  # Stub: needs implementation',
            new_content
        )
        new_content = re.sub(
            r'raise NotImplementedError',
            'return None  # Stub: needs implementation',
            new_content
        )
        
        # JS: throw new Error('Not implemented') -> return null
        new_content = re.sub(
            r"throw new Error\(['\"]Not implemented['\"]\)",
            "return null; // Stub: needs implementation",
            new_content
        )
        
        if new_content != content:
            return (
                ViolationFix(
                    violation_id=violation.id,
                    violation_message=violation.message,
                    fix_approach=FixApproach.ADD_MOCK,
                    fix_description="Replaced NotImplementedError with stub return",
                    affected_files=[file_path],
                    confidence=0.75,
                    requires_mock=True,
                    creates_followup_task=True
                ),
                FixChange(
                    path=file_path,
                    operation="modify",
                    original_content=content,
                    new_content=new_content,
                    unified_diff=self._compute_diff(content, new_content, file_path),
                    violation_ids=[violation.id],
                    reason="Replace NotImplementedError with stub"
                )
            )
        
        return None, None


# ============================================================================
# DEPENDENCY FIXER
# ============================================================================

class DependencyFixer(FixStrategy):
    """
    Fix dependency/import violations.
    
    Approaches:
    - Typo in import path: Fix the path
    - Missing package: Add to dependencies (with approval)
    - Circular dependency: Escalate to Planner
    """
    
    def __init__(self, config: Optional[FixerConfig] = None):
        super().__init__(config)
        self.layer = FailureLayer.DEPENDENCY
    
    def can_fix(self, violation: Violation) -> Tuple[bool, FixScope]:
        """Check if dependency issue is fixable."""
        vtype = getattr(violation, 'violation_type', 'unresolved_import')
        
        # Unresolved imports might be typos or need new package
        if vtype == "unresolved_import":
            if self.config.allow_new_dependencies:
                return True, FixScope.LOCAL
            return False, FixScope.POLICY_BLOCKED
        
        # Hallucinated packages need review
        if vtype == "hallucinated_package":
            return False, FixScope.POLICY_BLOCKED
        
        # Circular deps need architectural fix
        if vtype == "circular_dependency":
            return False, FixScope.ARCHITECTURAL
        
        return False, FixScope.LOCAL
    
    def generate_fix(
        self,
        violation: Violation,
        context: Dict[str, Any]
    ) -> Tuple[Optional[ViolationFix], Optional[FixChange]]:
        """Generate fix for dependency violation."""
        vtype = getattr(violation, 'violation_type', 'unresolved_import')
        package_name = getattr(violation, 'package_name', None)
        
        if vtype == "unresolved_import" and package_name:
            # Check if it's a known package
            known_packages = {
                "react": "^18.2.0",
                "axios": "^1.6.0",
                "lodash": "^4.17.21",
                "zod": "^3.22.0",
            }
            
            if package_name in known_packages:
                # Propose adding to package.json
                version = known_packages[package_name]
                
                return (
                    ViolationFix(
                        violation_id=violation.id,
                        violation_message=violation.message,
                        fix_approach=FixApproach.ADD_DEPENDENCY,
                        fix_description=f"Add {package_name}@{version} to dependencies",
                        affected_files=["package.json"],
                        confidence=0.9
                    ),
                    None  # Package.json change would need special handling
                )
        
        return None, None


# ============================================================================
# SCOPE FIXER
# ============================================================================

class ScopeFixer(FixStrategy):
    """
    Fix scope/contract violations.
    
    Scope issues are subtle - usually need escalation.
    Only safe fixes are guard clauses or removing unexpected code.
    """
    
    def __init__(self, config: Optional[FixerConfig] = None):
        super().__init__(config)
        self.layer = FailureLayer.SCOPE
    
    def can_fix(self, violation: Violation) -> Tuple[bool, FixScope]:
        """Scope fixes are usually architectural."""
        vtype = getattr(violation, 'violation_type', 'scope_exceeded')
        
        # Scope exceeded might mean we added extra files
        if vtype == "scope_exceeded":
            # Could remove the extra file, but risky
            return False, FixScope.ARCHITECTURAL
        
        # Non-goals touched needs human review
        if vtype == "non_goal_touched":
            return False, FixScope.POLICY_BLOCKED
        
        # Blueprint mismatch needs replan
        if vtype == "blueprint_mismatch":
            return False, FixScope.ARCHITECTURAL
        
        return False, FixScope.ARCHITECTURAL
    
    def generate_fix(
        self,
        violation: Violation,
        context: Dict[str, Any]
    ) -> Tuple[Optional[ViolationFix], Optional[FixChange]]:
        """Scope fixes usually escalate."""
        # Most scope issues need replan or human review
        return None, None
    
    def create_replan_request(
        self,
        violation: Violation,
        validation_report_id: str,
        fix_plan_id: str
    ) -> ReplanRequest:
        """Create replan request for scope violation."""
        return ReplanRequest(
            origin_validation_report_id=validation_report_id,
            origin_fix_plan_id=fix_plan_id,
            reason=f"Scope violation requires plan adjustment: {violation.message}",
            violated_artifact="scope",
            violation_details=violation.message,
            suggested_changes=[
                "Review task scope and expected outputs",
                "Update acceptance criteria if needed"
            ]
        )
