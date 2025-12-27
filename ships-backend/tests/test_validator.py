"""
Tests for ShipS* Validator Sub-Agent

Tests cover:
- Validation models
- 4 Validation layers
- Main Validator agent
"""

import pytest
from datetime import datetime
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.agents.sub_agents.validator.models import (
    ValidationStatus, FailureLayer, RecommendedAction,
    ViolationSeverity, Violation, ValidationReport, LayerResult,
    StructuralViolation, CompletenessViolation,
    DependencyViolation, ScopeViolation,
    ValidatorConfig,
)
from app.agents.sub_agents.validator.layers import (
    StructuralLayer, CompletenessLayer, DependencyLayer, ScopeLayer,
)
from app.agents.sub_agents.validator import Validator


class TestValidatorModels:
    """Tests for Validator models."""
    
    def test_validation_status_enum(self):
        """Test ValidationStatus is strictly pass/fail."""
        assert ValidationStatus.PASS.value == "pass"
        assert ValidationStatus.FAIL.value == "fail"
        # No warning or other status
        assert len(ValidationStatus) == 2
    
    def test_violation_creation(self):
        """Test creating a Violation."""
        violation = Violation(
            layer=FailureLayer.COMPLETENESS,
            rule="no_todos",
            message="TODO found in code"
        )
        
        assert violation.layer == FailureLayer.COMPLETENESS
        assert violation.id.startswith("violation_")
    
    def test_validation_report_add_violation(self):
        """Test ValidationReport tracks stats."""
        report = ValidationReport(
            status=ValidationStatus.FAIL,
            recommended_action=RecommendedAction.FIX
        )
        
        report.add_violation(Violation(
            layer=FailureLayer.COMPLETENESS,
            rule="no_todos",
            message="TODO found",
            severity=ViolationSeverity.MAJOR
        ))
        report.add_violation(Violation(
            layer=FailureLayer.DEPENDENCY,
            rule="no_hallucinated",
            message="Package not found",
            severity=ViolationSeverity.CRITICAL
        ))
        
        assert report.total_violations == 2
        assert report.critical_count == 1
        assert report.major_count == 1
    
    def test_validation_report_get_fix_manifest(self):
        """Test ValidationReport generates fix manifest."""
        report = ValidationReport(
            status=ValidationStatus.FAIL,
            recommended_action=RecommendedAction.FIX,
            fixer_instructions="Fix the TODOs"
        )
        report.add_violation(Violation(
            layer=FailureLayer.COMPLETENESS,
            rule="no_todos",
            message="TODO found"
        ))
        
        manifest = report.get_fix_manifest()
        assert "violations" in manifest
        assert manifest["instructions"] == "Fix the TODOs"


class TestValidationLayers:
    """Tests for validation layers."""
    
    @pytest.fixture
    def config(self):
        return ValidatorConfig()
    
    def test_structural_layer_protected_path(self, config):
        """Test StructuralLayer catches protected paths."""
        layer = StructuralLayer(config)
        result = layer.validate({
            "file_changes": [{"path": ".git/config", "operation": "modify", "content": ""}],
            "folder_map": {}
        })
        
        assert result.passed is False
        assert any(v.rule == "no_protected_paths" for v in result.violations)
    
    def test_structural_layer_clean(self, config):
        """Test StructuralLayer passes clean files."""
        layer = StructuralLayer(config)
        result = layer.validate({
            "file_changes": [{"path": "src/app.ts", "operation": "add", "content": "const a = 1;"}],
            "folder_map": {"entries": [{"path": "src/", "is_directory": True}]}
        })
        
        assert result.passed is True
    
    def test_completeness_layer_todo(self, config):
        """Test CompletenessLayer catches TODOs."""
        layer = CompletenessLayer(config)
        result = layer.validate({
            "file_changes": [{"path": "src/app.ts", "content": "// TODO: implement this\nconst a = 1;"}]
        })
        
        assert result.passed is False
        assert any(v.rule == "no_todos" for v in result.violations)
    
    def test_completeness_layer_placeholder(self, config):
        """Test CompletenessLayer catches placeholders."""
        layer = CompletenessLayer(config)
        result = layer.validate({
            "file_changes": [{"path": "src/app.ts", "content": "// placeholder function\nconst a = 1;"}]
        })
        
        assert result.passed is False
        assert any(v.rule == "no_placeholders" for v in result.violations)
    
    def test_completeness_layer_not_implemented(self, config):
        """Test CompletenessLayer catches NotImplementedError."""
        layer = CompletenessLayer(config)
        result = layer.validate({
            "file_changes": [{"path": "src/app.py", "content": "def foo():\n    raise NotImplementedError"}]
        })
        
        assert result.passed is False
        assert any(v.violation_type == "stub" for v in result.violations)
    
    def test_completeness_layer_clean(self, config):
        """Test CompletenessLayer passes clean code."""
        layer = CompletenessLayer(config)
        result = layer.validate({
            "file_changes": [{"path": "src/app.ts", "content": "const add = (a, b) => a + b;\nexport { add };"}]
        })
        
        assert result.passed is True
    
    def test_dependency_layer_undeclared(self, config):
        """Test DependencyLayer catches undeclared imports."""
        layer = DependencyLayer(config)
        result = layer.validate({
            "file_changes": [{"path": "src/app.ts", "content": "import { foo } from 'unknown-package';"}],
            "dependency_plan": {"runtime_dependencies": []}
        })
        
        assert result.passed is False
        assert any(v.package_name == "unknown-package" for v in result.violations)
    
    def test_dependency_layer_declared(self, config):
        """Test DependencyLayer passes declared imports."""
        layer = DependencyLayer(config)
        result = layer.validate({
            "file_changes": [{"path": "src/app.ts", "content": "import React from 'react';"}],
            "dependency_plan": {"runtime_dependencies": [{"name": "react"}]}
        })
        
        assert result.passed is True
    
    def test_scope_layer_unexpected_file(self, config):
        """Test ScopeLayer catches unexpected files."""
        layer = ScopeLayer(config)
        result = layer.validate({
            "file_changes": [
                {"path": "src/app.ts", "content": "const a = 1;"},
                {"path": "src/extra.ts", "content": "const b = 2;"}
            ],
            "current_task": {
                "expected_outputs": [{"file_path": "src/app.ts"}]
            },
            "folder_map": {}
        })
        
        assert result.passed is False
        assert any("extra.ts" in v.message for v in result.violations)


class TestValidator:
    """Tests for main Validator agent."""
    
    @pytest.mark.skip(reason="Requires LLM API key")
    @pytest.mark.asyncio
    async def test_validate_clean_pass(self):
        """Test validator passes clean code."""
        validator = Validator()
        report = await validator.validate(
            file_change_set={
                "id": "cs_1",
                "changes": [{
                    "path": "src/app.ts",
                    "operation": "add",
                    "diff": {"new_content": "export const add = (a: number, b: number) => a + b;"}
                }]
            },
            folder_map={"entries": [{"path": "src/", "is_directory": True}]}
        )
        
        assert report.status == ValidationStatus.PASS
        assert report.recommended_action == RecommendedAction.PROCEED
    
    @pytest.mark.skip(reason="Requires LLM API key")
    @pytest.mark.asyncio
    async def test_validate_todo_fail(self):
        """Test validator fails on TODO."""
        validator = Validator()
        report = await validator.validate(
            file_change_set={
                "id": "cs_1",
                "changes": [{
                    "path": "src/app.ts",
                    "operation": "add",
                    "diff": {"new_content": "// TODO: implement\nconst a = 1;"}
                }]
            },
            folder_map={}
        )
        
        assert report.status == ValidationStatus.FAIL
        assert report.failure_layer == FailureLayer.COMPLETENESS
        assert report.recommended_action == RecommendedAction.FIX
    
    @pytest.mark.skip(reason="Requires LLM API key")
    @pytest.mark.asyncio
    async def test_validate_stops_on_first_failure(self):
        """Test validator stops at first failing layer."""
        validator = Validator()
        report = await validator.validate(
            file_change_set={
                "id": "cs_1",
                "changes": [{
                    "path": ".git/config",  # Structural fail
                    "operation": "modify",
                    "diff": {"new_content": "// TODO: more"}  # Would fail completeness too
                }]
            },
            folder_map={}
        )
        
        # Should fail at structural, not even run completeness
        assert report.status == ValidationStatus.FAIL
        assert report.failure_layer == FailureLayer.STRUCTURAL
    
    @pytest.mark.skip(reason="Requires LLM API key")
    @pytest.mark.asyncio
    async def test_validate_quick(self):
        """Test quick validation returns bool."""
        validator = Validator()
        passed = await validator.validate_quick(
            file_changes=[{"path": "src/a.ts", "content": "const a = 1;"}]
        )
        
        assert passed is True
        
        failed = await validator.validate_quick(
            file_changes=[{"path": "src/a.ts", "content": "// TODO: fix\nconst a = 1;"}]
        )
        
        assert failed is False
        
        assert failed is False


# Run with: py -m pytest tests/test_validator.py -v
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
