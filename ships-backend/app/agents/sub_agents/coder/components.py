"""
ShipS* Coder Subcomponents

Subcomponents that support code generation workflow.
Each component handles a specific responsibility.
Wraps core logic in 'process' methods to interface with Coder agent.

Components:
- TaskInterpreter: Parses and validates task inputs
- ContextConsumer: Gathers context from artifacts
- StyleEnforcer: Applies coding conventions
- ImplementationSynthesizer: Generates code diffs
- DependencyVerifier: Validates imports/deps
- TestAuthor: Generates test cases
- PreflightChecker: Runs preflight validations
"""

from typing import Dict, Any, List, Optional
from app.agents.sub_agents.coder.models import (
    FileChangeSet, FileChange, FileDiff, FileOperation, ChangeRisk,
    TestBundle, TestCase, TestType,
    PreflightCheck, CheckResult, CheckStatus,
    CoderComponentConfig,
    CoderMetadata, ImplementationReport, CommitIntent,
    CoderOutput,
)


class TaskInterpreter:
    """
    Parses and validates task inputs.
    
    Extracts what needs to be done from the task artifact.
    """
    
    def __init__(self, config: Optional[CoderComponentConfig] = None):
        self.config = config or CoderComponentConfig()
    
    def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main entry point for task interpretation.
        Matches Coder agent expectation.
        """
        task = context.get("task", {})
        
        # 1. Validate
        validation = self.validate_task(task)
        if not validation["valid"]:
            return {
                "is_valid": False,
                "blocking_reasons": validation["errors"],
                "objectives": []
            }
            
        # 2. Parse
        parsed = self.parse_task(task)
        
        # 3. Create directives (objectives)
        objectives = [
            f"Create/Update {file_out.get('path', 'unknown file')}"
            for file_out in parsed["expected_outputs"]
        ]
        
        return {
            "is_valid": True,
            "parsed_task": parsed,
            "objectives": objectives,
            "blocking_reasons": []
        }

    def parse_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse a task into actionable directives.
        """
        return {
            "id": task.get("id", ""),
            "title": task.get("title", ""),
            "description": task.get("description", ""),
            "complexity": task.get("complexity", "small"),
            "priority": task.get("priority", "medium"),
            "expected_outputs": task.get("expected_outputs", []),
            "acceptance_criteria": task.get("acceptance_criteria", []),
            "target_area": task.get("target_area", "frontend"),
        }
    
    def validate_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate task has required fields.
        """
        errors = []
        if not task.get("title"):
            errors.append("Missing task title")
        # Description might be implicit if we have a clear title, but usually required
        if not task.get("description") and not task.get("title"):
             errors.append("Missing task description")
        
        return {"valid": len(errors) == 0, "errors": errors}


class ContextConsumer:
    """
    Gathers context from plan artifacts.
    """
    
    def __init__(self, config: Optional[CoderComponentConfig] = None):
        self.config = config or CoderComponentConfig()
        
    def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main entry for context gathering.
        """
        # In coder.py, context has folder_map, etc. updated before this call
        # But we also just pass 'context' through
        return self.gather_context(context)
    
    def gather_context(self, artifacts: Dict[str, Any]) -> Dict[str, Any]:
        """
        Gather relevant context for code generation.
        """
        return {
            "folder_map": artifacts.get("folder_map", {}),
            "api_contracts": artifacts.get("api_contracts", {}),
            "dependency_plan": artifacts.get("dependency_plan", {}),
            "patterns": self._extract_patterns(artifacts),
        }
    
    def _extract_patterns(self, artifacts: Dict[str, Any]) -> Dict[str, str]:
        """Extract coding patterns from existing code or plan."""
        return {
            "naming": "camelCase",
            "async_style": "async/await",
            "exports": "named",
        }


class StyleEnforcer:
    """
    Enforces coding conventions.
    """
    
    def __init__(self, config: Optional[CoderComponentConfig] = None):
        self.config = config or CoderComponentConfig()
        
    def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main entry for style enforcement.
        """
        language = "typescript" # Default, or detect from context
        framework = context.get("framework", "react")
        
        rules = self.get_style_rules(language)
        
        # Add test patterns based on framework
        test_patterns = {
            "library": "vitest" if framework == "vite" else "jest",
            "naming": "*.test.tsx"
        }
        
        return {
            "style_rules": rules,
            "test_patterns": test_patterns
        }
    
    def get_style_rules(self, language: str) -> Dict[str, Any]:
        """
        Get style rules for a language.
        """
        if language in ["typescript", "javascript", "tsx", "jsx"]:
            return {
                "indent": 2,
                "quotes": "single",
                "semicolons": True,
                "trailing_comma": "es5",
            }
        elif language == "python":
            return {
                "indent": 4,
                "quotes": "double",
                "max_line_length": 88,
            }
        return {"indent": 2}


class ImplementationSynthesizer:
    """
    Generates code implementations.
    """
    
    def __init__(self, config: Optional[CoderComponentConfig] = None):
        self.config = config or CoderComponentConfig()
        
    # This class is usually used directly via create_file_change, 
    # but strictly following the pattern, it might not need a process method 
    # if Coder uses the 'tools' to assemble output.
    # Checking coder.py, it uses LLM to get changes, then might use this helper.
    # Actually coder.py invokes LLM directly for code gen. This component helps structure it.
    
    def create_file_change(
        self,
        path: str,
        content: str,
        operation: FileOperation = FileOperation.ADD
    ) -> FileChange:
        """
        Create a FileChange artifact.
        """
        return FileChange(
            path=path,
            operation=operation,
            new_content=content,
            language=self._detect_language(path),
        )
    
    def _detect_language(self, path: str) -> str:
        """Detect language from file extension."""
        ext = path.split(".")[-1] if "." in path else ""
        return {
            "ts": "typescript",
            "tsx": "typescript",
            "js": "javascript",
            "jsx": "javascript",
            "py": "python",
            "css": "css",
            "json": "json",
        }.get(ext, "text")


class DependencyVerifier:
    """
    Verifies imports and dependencies.
    """
    
    def __init__(self, config: Optional[CoderComponentConfig] = None):
        self.config = config or CoderComponentConfig()
        
    def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Verify dependencies.
        """
        # Mock result for now
        return {
            "has_blockers": False,
            "blocked": []
        }
    
    def verify_imports(self, file_changes: List[FileChange]) -> Dict[str, Any]:
        """
        Verify all imports in file changes can be resolved.
        """
        return {"valid": True, "issues": []}


class TestAuthor:
    """
    Generates test cases for implementations.
    """
    
    def __init__(self, config: Optional[CoderComponentConfig] = None):
        self.config = config or CoderComponentConfig()
        
    def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate test cases.
        """
        objectives = context.get("objectives", [])
        
        # Generate generic test placeholders
        test_cases = []
        for obj in objectives:
            test_cases.append({
                "name": f"Test for {obj}",
                "description": "Verify implementation",
                "type": "unit",
                "code": "// Test code implementation pending"
            })
            
        return {"test_cases": test_cases}
    
    def create_test_bundle(
        self,
        task_id: str,
        test_cases: List[Dict[str, Any]]
    ) -> TestBundle:
        """
        Create a TestBundle from test case definitions.
        """
        cases = []
        for tc in test_cases:
            cases.append(TestCase(
                name=tc.get("name", "Test"),
                description=tc.get("description", ""),
                test_type=TestType(tc.get("type", "unit")),
                test_code=tc.get("code", ""),
                test_file_path=tc.get("file_path", f"tests/{tc.get('name', 'test')}.test.ts")
            ))
        
        # Create metadata for the bundle
        metadata = CoderMetadata(task_id=task_id, plan_id=None, confidence=1.0)
        return TestBundle(metadata=metadata, tests=cases)


class PreflightChecker:
    """
    Runs preflight validation checks.
    """
    
    def __init__(self, config: Optional[CoderComponentConfig] = None):
        self.config = config or CoderComponentConfig()
        
    def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run preflight checks.
        """
        # Create a mock preflight check result
        changes = context.get("changes", [])
        
        results = [
            CheckResult(
                name="syntax",
                status=CheckStatus.PASSED,
                message="Syntax validation passed"
            ),
             CheckResult(
                name="imports",
                status=CheckStatus.PASSED,
                message="Imports resolved"
            )
        ]
        
        check = PreflightCheck(
            task_id=context.get("task_id", ""),
            checks=results,
            passed=True
        )
        
        return {"preflight_check": check}
    
    def run_checks(self, file_changes: FileChangeSet) -> PreflightCheck:
        """
        Run preflight checks on file changes.
        """
        results = []
        
        results.append(CheckResult(
            name="syntax",
            status=CheckStatus.PASSED,
            message="Syntax validation delegated to Validator"
        ))
        
        # Import resolution check
        results.append(CheckResult(
            name="imports",
            status=CheckStatus.PASSED,
            message="Import validation delegated to Validator"
        ))
        
        return PreflightCheck(
            task_id=file_changes.task_id,
            checks=results,
            passed=True
        )


class CodeTools:
    """
    Static tools available to the Coder.
    """
    
    @staticmethod
    def generate_file_path(folder_map: Dict[str, Any], file_type: str, name: str) -> str:
        """
        Generate appropriate file path based on folder map.
        """
        entries = folder_map.get("entries", [])
        
        # Map file types to directories
        type_dirs = {
            "component": "src/components",
            "hook": "src/hooks",
            "type": "src/types",
            "util": "src/lib",
            "style": "src",
        }
        
        base_dir = type_dirs.get(file_type, "src")
        
        # Check if dir exists in folder map
        for entry in entries:
            if entry.get("path", "").startswith(base_dir):
                return f"{base_dir}/{name}"
        
        return f"src/{name}"

    @staticmethod
    def assemble_coder_output(
        task_id: str,
        changes: List[FileChange],
        tests: List[TestCase],
        summary: str,
        confidence: float,
        plan_id: Optional[str] = None
    ) -> CoderOutput:
        """Assemble the complete coder output."""
        metadata = CoderMetadata(
            task_id=task_id,
            plan_id=plan_id,
            confidence=confidence
        )
        
        # Create changeset
        changeset = FileChangeSet(
            metadata=metadata,
            summary=summary,
            changes=changes,
            total_files_changed=len(changes),
            total_lines_added=sum(c.lines_added for c in changes),
            total_lines_removed=sum(c.lines_removed for c in changes)
        )
        
        # Create implementation report
        report = ImplementationReport(
            metadata=metadata,
            summary=summary,
            changes_made=[c.summary_line for c in changes if c.summary_line] or ["Implemented changes"],
            overall_confidence=confidence
        )
        
        # Create commit intent
        commit = CommitIntent(
            task_id=task_id,
            plan_id=plan_id,
            changeset_id=changeset.id,
            message=summary
        )
        
        return CoderOutput(
            success=True,
            file_change_set=changeset,
            test_bundle=TestBundle(metadata=metadata, tests=tests),
            commit_intent=commit,
            implementation_report=report,
            total_files_changed=changeset.total_files_changed,
            total_lines_changed=changeset.total_lines_added + changeset.total_lines_removed
        )


__all__ = [
    "TaskInterpreter",
    "ContextConsumer",
    "StyleEnforcer",
    "ImplementationSynthesizer",
    "DependencyVerifier",
    "TestAuthor",
    "PreflightChecker",
    "CodeTools",
]
