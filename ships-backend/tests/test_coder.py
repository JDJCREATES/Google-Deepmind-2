"""
Tests for ShipS* Coder Sub-Agent

Tests cover:
- Artifact models (FileChangeSet, TestBundle, CommitIntent, etc.)
- Coder components (TaskInterpreter, ContextConsumer, etc.)
- Tools (DiffGenerator, CommitBuilder, ReportBuilder)
"""

import pytest
from datetime import datetime
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.agents.sub_agents.coder.models import (
    FileChange, FileChangeSet, FileDiff, FileOperation, ChangeRisk,
    TestBundle, TestCase, TestType,
    CommitIntent, SemanticVersionBump,
    ImplementationReport, PreflightCheck, CheckResult, CheckStatus,
    FollowUpTask, FollowUpTasks, CoderOutput, CoderMetadata,
)
from app.agents.sub_agents.coder.components import (
    CoderComponentConfig, TaskInterpreter, ContextConsumer,
    StyleEnforcer, ImplementationSynthesizer, DependencyVerifier,
    TestAuthor, PreflightChecker,
)
from app.agents.sub_agents.coder.tools import (
    DiffGenerator, CommitBuilder, ReportBuilder, CodeTools,
)


class TestCoderModels:
    """Tests for Coder artifact models."""
    
    def test_create_file_change(self):
        """Test creating a FileChange."""
        change = FileChange(
            path="src/index.ts",
            operation=FileOperation.ADD,
            summary_line="Add main entry point",
            reason="Required by task"
        )
        
        assert change.path == "src/index.ts"
        assert change.operation == FileOperation.ADD
        assert change.id.startswith("change_")
    
    def test_file_diff_hash(self):
        """Test FileDiff hash computation."""
        diff = FileDiff(
            original_content="const a = 1;",
            new_content="const a = 2;"
        )
        
        hash1 = diff.compute_hash()
        assert len(hash1) == 12
        
        # Same content = same hash
        diff2 = FileDiff(
            original_content="const a = 1;",
            new_content="const a = 2;"
        )
        assert diff.compute_hash() == diff2.compute_hash()
    
    def test_file_change_set_add(self):
        """Test FileChangeSet add and stats."""
        metadata = CoderMetadata(task_id="task_1")
        changeset = FileChangeSet(metadata=metadata)
        
        change = FileChange(
            path="src/app.ts",
            operation=FileOperation.ADD,
            lines_added=50,
            lines_removed=0
        )
        changeset.add_change(change)
        
        assert changeset.total_files_changed == 1
        assert changeset.total_lines_added == 50
    
    def test_test_case(self):
        """Test TestCase creation."""
        test = TestCase(
            name="test_login",
            description="Test login functionality",
            test_code="it('should login', () => { expect(true).toBe(true); });",
            test_file_path="src/auth.test.ts"
        )
        
        assert test.name == "test_login"
        assert test.test_type == TestType.UNIT
    
    def test_commit_intent(self):
        """Test CommitIntent creation."""
        intent = CommitIntent(
            message="feat: Add user authentication",
            task_id="task_1",
            changeset_id="changeset_1"
        )
        
        assert intent.message.startswith("feat:")
        assert intent.author == "ShipS* Coder Agent"
        assert intent.version_bump == SemanticVersionBump.NONE
    
    def test_preflight_check_add(self):
        """Test PreflightCheck add and stats."""
        preflight = PreflightCheck()
        
        preflight.add_check(CheckResult(
            name="lint",
            status=CheckStatus.PASSED,
            message="No lint errors"
        ))
        preflight.add_check(CheckResult(
            name="security",
            status=CheckStatus.FAILED,
            message="Found hardcoded secret"
        ))
        
        assert preflight.total_passed == 1
        assert preflight.total_failed == 1
        assert preflight.passed is False
    
    def test_coder_output(self):
        """Test CoderOutput assembly."""
        output = CoderOutput(
            success=True,
            total_lines_changed=100,
            total_files_changed=5
        )
        
        assert output.recommended_next_agent == "validator"


class TestCoderComponents:
    """Tests for Coder components."""
    
    @pytest.fixture
    def config(self):
        return CoderComponentConfig()
    
    @pytest.fixture
    def basic_task(self):
        return {
            "title": "Add login button",
            "description": "Add a login button to the header",
            "acceptance_criteria": [
                {"description": "Button displays 'Login'"},
                {"description": "Button navigates to /auth"}
            ]
        }
    
    def test_task_interpreter_valid(self, config, basic_task):
        """Test TaskInterpreter with valid task."""
        interpreter = TaskInterpreter(config)
        result = interpreter.process({"task": basic_task})
        
        assert result["is_valid"] is True
        assert len(result["objectives"]) == 2
    
    def test_task_interpreter_missing_fields(self, config):
        """Test TaskInterpreter with missing fields."""
        interpreter = TaskInterpreter(config)
        result = interpreter.process({"task": {}})
        
        assert result["is_valid"] is False
        assert len(result["blocking_reasons"]) > 0
    
    def test_context_consumer(self, config):
        """Test ContextConsumer gathers relevant context."""
        consumer = ContextConsumer(config)
        result = consumer.process({
            "folder_map": {"entries": [{"path": "src/components/Header.tsx"}]},
            "existing_code": {"src/components/Header.tsx": "export const Header = () => <div>Header</div>;"},
            "objectives": [{"description": "Add button to header"}]
        })
        
        assert "relevant_snippets" in result
    
    def test_style_enforcer(self, config):
        """Test StyleEnforcer detects patterns."""
        enforcer = StyleEnforcer(config)
        result = enforcer.process({
            "framework": "react",
            "relevant_snippets": {"test.tsx": "const MyComponent = () => {};"}
        })
        
        assert "naming_rules" in result
        assert result["naming_rules"]["component_case"] == "PascalCase"
    
    def test_dependency_verifier_allowed(self, config):
        """Test DependencyVerifier allows safe packages."""
        verifier = DependencyVerifier(config)
        result = verifier.process({
            "new_imports": [{"name": "react"}],
            "dependency_plan": {},
            "ecosystem": "npm"
        })
        
        assert len(result["allowed"]) == 1
        assert result["has_blockers"] is False
    
    def test_dependency_verifier_blocked(self, config):
        """Test DependencyVerifier blocks banned packages."""
        verifier = DependencyVerifier(config)
        result = verifier.process({
            "new_imports": [{"name": "event-stream"}],
            "dependency_plan": {},
            "ecosystem": "npm"
        })
        
        assert len(result["blocked"]) == 1
        assert result["has_blockers"] is True
    
    def test_test_author(self, config):
        """Test TestAuthor generates tests."""
        author = TestAuthor(config)
        result = author.process({
            "objectives": [{"id": "obj_1", "description": "Button responds to click", "is_testable": True}],
            "suggested_changes": [{"path": "src/Button.tsx"}],
            "test_patterns": {"test_suffix": ".test.tsx", "test_framework": "jest"}
        })
        
        assert len(result["test_cases"]) == 1
        assert "jest" in result["test_cases"][0].test_code.lower() or "describe" in result["test_cases"][0].test_code
    
    def test_preflight_checker_security(self, config):
        """Test PreflightChecker detects security issues."""
        checker = PreflightChecker(config)
        result = checker.process({
            "changes": [{"path": "config.js", "content": "const apiKey = 'secret123';"}],
            "policy": {}
        })
        
        preflight = result["preflight_check"]
        assert len(preflight.security_issues) > 0 or any(c.status == CheckStatus.FAILED for c in preflight.checks)


class TestCoderTools:
    """Tests for Coder tools."""
    
    def test_diff_generator_create_change(self):
        """Test DiffGenerator creates FileChange."""
        change = DiffGenerator.create_file_change(
            path="src/utils.ts",
            operation=FileOperation.ADD,
            new_content="export const add = (a, b) => a + b;",
            reason="Add utility function"
        )
        
        assert change.path == "src/utils.ts"
        assert change.lines_added > 0
        assert change.language == "typescript"
    
    def test_diff_generator_unified_diff(self):
        """Test DiffGenerator generates unified diff."""
        diff = DiffGenerator.generate_diff(
            original="const a = 1;",
            modified="const a = 2;",
            filename="test.js"
        )
        
        assert "a/test.js" in diff
        assert "-const a = 1;" in diff
        assert "+const a = 2;" in diff
    
    def test_diff_generator_assess_risk(self):
        """Test DiffGenerator assesses risk."""
        risk, reason = DiffGenerator.assess_risk(
            "const secret = process.env.SECRET;",
            "config.js"
        )
        
        assert risk in [ChangeRisk.MEDIUM, ChangeRisk.HIGH]
    
    def test_commit_builder(self):
        """Test CommitBuilder creates commit intent."""
        intent = CommitBuilder.create_commit_intent(
            task_id="task_1",
            changeset_id="cs_1",
            summary="Add login feature",
            task_type="feature"
        )
        
        assert intent.message.startswith("feat:")
        assert "task_1" in intent.message_body
    
    def test_report_builder(self):
        """Test ReportBuilder creates implementation report."""
        report = ReportBuilder.create_report(
            task_id="task_1",
            summary="Implemented login button",
            changes_made=["Added Button.tsx", "Updated Header.tsx"],
            confidence=0.9
        )
        
        assert len(report.changes_made) == 2
        assert report.overall_confidence == 0.9
    
    def test_code_tools_assemble_output(self):
        """Test CodeTools assembles complete output."""
        change = DiffGenerator.create_file_change(
            path="src/app.ts",
            operation=FileOperation.ADD,
            new_content="export const app = () => {};"
        )
        
        output = CodeTools.assemble_coder_output(
            task_id="task_1",
            changes=[change],
            tests=[],
            summary="Add app module",
            confidence=0.85
        )
        
        assert output.success is True
        assert output.file_change_set is not None
        assert output.commit_intent is not None
        assert output.implementation_report is not None


# Run with: py -m pytest tests/test_coder.py -v
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
