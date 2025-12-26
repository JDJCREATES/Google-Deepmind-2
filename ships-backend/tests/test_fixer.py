"""
Tests for ShipS* Fixer Sub-Agent

Tests cover:
- Fixer models
- Fix strategies
- Main Fixer agent
"""

import pytest
from datetime import datetime
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.agents.sub_agents.fixer.models import (
    FixPlan, FixPatch, FixChange, FixReport, FixAttemptLog,
    ReplanRequest, FixerConfig, FixerOutput, ViolationFix,
    FixScope, FixApproach, FixRisk, FixResult, ApprovalType,
)
from app.agents.sub_agents.fixer.strategies import (
    StructuralFixer, CompletenessFixer, DependencyFixer, ScopeFixer,
)
from app.agents.sub_agents.validator.models import (
    Violation, FailureLayer, ViolationSeverity,
)


class TestFixerModels:
    """Tests for Fixer models."""
    
    def test_fix_plan_creation(self):
        """Test creating a FixPlan."""
        plan = FixPlan(
            origin_validation_report_id="val_123",
            summary="Fix TODO violations",
            failure_layer="completeness",
            approach=FixApproach.REMOVE_TODO,
            confidence=0.9
        )
        
        assert plan.id.startswith("fixplan_")
        assert plan.estimated_risk == FixRisk.LOW
        assert plan.auto_apply_allowed is True
    
    def test_fix_plan_needs_approval(self):
        """Test FixPlan approval logic."""
        # Low risk, high confidence = no approval
        plan1 = FixPlan(
            origin_validation_report_id="val_1",
            summary="Simple fix",
            failure_layer="completeness",
            approach=FixApproach.PATCH_FILE,
            estimated_risk=FixRisk.LOW,
            confidence=0.9
        )
        assert plan1.needs_approval() is False
        
        # High risk = needs approval
        plan2 = FixPlan(
            origin_validation_report_id="val_2",
            summary="Risky fix",
            failure_layer="dependency",
            approach=FixApproach.ADD_DEPENDENCY,
            estimated_risk=FixRisk.HIGH,
            confidence=0.9
        )
        assert plan2.needs_approval() is True
        
        # Low confidence = needs approval
        plan3 = FixPlan(
            origin_validation_report_id="val_3",
            summary="Uncertain fix",
            failure_layer="completeness",
            approach=FixApproach.PATCH_FILE,
            estimated_risk=FixRisk.LOW,
            confidence=0.6
        )
        assert plan3.needs_approval() is True
    
    def test_fix_patch_add_change(self):
        """Test FixPatch tracks changes."""
        patch = FixPatch(fix_plan_id="plan_1")
        
        patch.add_change(FixChange(
            path="src/app.ts",
            operation="modify",
            reason="Remove TODO",
            lines_added=5,
            lines_removed=3
        ))
        
        assert patch.total_files == 1
        assert patch.total_lines_added == 5
        assert patch.total_lines_removed == 3
    
    def test_fix_attempt_log(self):
        """Test FixAttemptLog tracks steps."""
        log = FixAttemptLog(fix_plan_id="plan_1")
        
        log.add_step("triage", True)
        log.add_step("generate_patch", True)
        log.add_step("preflight", False, "Lint failed")
        
        assert len(log.steps) == 3
        assert log.steps[2].success is False
        assert log.steps[2].error == "Lint failed"
    
    def test_replan_request(self):
        """Test ReplanRequest creation."""
        request = ReplanRequest(
            origin_validation_report_id="val_1",
            origin_fix_plan_id="plan_1",
            reason="Structural violation",
            violated_artifact="folder_map",
            violation_details="File in wrong directory"
        )
        
        assert request.id.startswith("replan_")
        assert request.is_blocking is True


class TestFixStrategies:
    """Tests for fix strategies."""
    
    @pytest.fixture
    def config(self):
        return FixerConfig()
    
    def test_structural_fixer_escalates(self, config):
        """Test StructuralFixer always escalates."""
        fixer = StructuralFixer(config)
        
        violation = Violation(
            layer=FailureLayer.STRUCTURAL,
            rule="no_protected_paths",
            message="Protected path modified"
        )
        
        can_fix, scope = fixer.can_fix(violation)
        assert can_fix is False
        assert scope == FixScope.ARCHITECTURAL
    
    def test_structural_fixer_creates_replan(self, config):
        """Test StructuralFixer creates replan request."""
        fixer = StructuralFixer(config)
        
        violation = Violation(
            layer=FailureLayer.STRUCTURAL,
            rule="folder_map_compliance",
            message="File not in allowed directory",
            file_path="wrong/path/file.ts"
        )
        
        request = fixer.create_replan_request(violation, "val_1", "plan_1")
        
        assert request.violated_artifact == "folder_map"
        assert "wrong/path/file.ts" in request.suggested_changes[0]
    
    def test_completeness_fixer_handles_todo(self, config):
        """Test CompletenessFixer can fix TODOs."""
        fixer = CompletenessFixer(config)
        
        violation = Violation(
            layer=FailureLayer.COMPLETENESS,
            rule="no_todos",
            message="TODO found"
        )
        
        can_fix, scope = fixer.can_fix(violation)
        assert can_fix is True
        assert scope == FixScope.LOCAL
    
    def test_completeness_fixer_fixes_todo(self, config):
        """Test CompletenessFixer generates TODO fix."""
        fixer = CompletenessFixer(config)
        
        violation = Violation(
            layer=FailureLayer.COMPLETENESS,
            rule="no_todos",
            message="TODO found",
            file_path="src/app.ts",
            line_number=5
        )
        
        context = {
            "file_contents": {
                "src/app.ts": "line1\nline2\nline3\nline4\n// TODO: implement this\nline6"
            }
        }
        
        violation_fix, change = fixer.generate_fix(violation, context)
        
        assert violation_fix is not None
        assert violation_fix.fix_approach == FixApproach.REMOVE_TODO
        assert change is not None
        assert "NOTE" in change.new_content
    
    def test_dependency_fixer_handles_import(self, config):
        """Test DependencyFixer can add known packages."""
        fixer = DependencyFixer(config)
        
        # Create violation with package_name attribute
        violation = Violation(
            layer=FailureLayer.DEPENDENCY,
            rule="no_undeclared_imports",
            message="Import not declared"
        )
        # Add violation_type for strategy detection
        violation.violation_type = "unresolved_import"
        
        can_fix, scope = fixer.can_fix(violation)
        assert can_fix is True
        assert scope == FixScope.LOCAL
    
    def test_scope_fixer_escalates(self, config):
        """Test ScopeFixer escalates scope issues."""
        fixer = ScopeFixer(config)
        
        violation = Violation(
            layer=FailureLayer.SCOPE,
            rule="expected_outputs_only",
            message="Unexpected file"
        )
        violation.violation_type = "scope_exceeded"
        
        can_fix, scope = fixer.can_fix(violation)
        assert can_fix is False
        assert scope == FixScope.ARCHITECTURAL


class TestFixerOutput:
    """Tests for FixerOutput."""
    
    def test_fixer_output_success(self):
        """Test successful FixerOutput."""
        output = FixerOutput(
            success=True,
            requires_approval=False,
            fix_plan=FixPlan(
                origin_validation_report_id="val_1",
                summary="Fixed TODOs",
                failure_layer="completeness",
                approach=FixApproach.REMOVE_TODO
            ),
            recommended_action="apply_patch",
            confidence=0.9
        )
        
        assert output.next_agent == "validator"
    
    def test_fixer_output_replan(self):
        """Test FixerOutput that requires replan."""
        output = FixerOutput(
            success=False,
            requires_replan=True,
            replan_request=ReplanRequest(
                origin_validation_report_id="val_1",
                origin_fix_plan_id="plan_1",
                reason="Structural issue",
                violated_artifact="folder_map",
                violation_details="..."
            ),
            recommended_action="replan",
            next_agent="planner"
        )
        
        assert output.requires_replan is True
        assert output.next_agent == "planner"


# Run with: py -m pytest tests/test_fixer.py -v
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
