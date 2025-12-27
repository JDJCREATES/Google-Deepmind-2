"""
ShipS* Coder Tools

Tools for the Coder agent:
- Diff generation and manipulation
- Code analysis utilities
- File content management
"""

from typing import Dict, Any, List, Optional, Tuple
import difflib
import hashlib
import re
from datetime import datetime

from app.agents.sub_agents.coder.models import (
    FileChange, FileChangeSet, FileDiff, FileOperation, ChangeRisk,
    CommitIntent, SemanticVersionBump,
    ImplementationReport, InferredItem, EdgeCase,
    CoderMetadata, CoderOutput,
)


class DiffGenerator:
    """
    Generates unified diffs between code versions.
    """
    
    @staticmethod
    def generate_diff(
        original: str, 
        modified: str, 
        filename: str = "file"
    ) -> str:
        """Generate unified diff between original and modified content."""
        original_lines = original.splitlines(keepends=True)
        modified_lines = modified.splitlines(keepends=True)
        
        diff = difflib.unified_diff(
            original_lines,
            modified_lines,
            fromfile=f"a/{filename}",
            tofile=f"b/{filename}",
            lineterm=""
        )
        
        return "".join(diff)
    
    @staticmethod
    def count_changes(diff: str) -> Tuple[int, int]:
        """Count lines added and removed from a diff."""
        added = 0
        removed = 0
        
        for line in diff.split("\n"):
            if line.startswith("+") and not line.startswith("+++"):
                added += 1
            elif line.startswith("-") and not line.startswith("---"):
                removed += 1
        
        return added, removed
    
    @staticmethod
    def create_file_change(
        path: str,
        operation: FileOperation,
        original_content: Optional[str] = None,
        new_content: Optional[str] = None,
        reason: str = "",
        acceptance_criteria_ids: List[str] = None
    ) -> FileChange:
        """Create a FileChange with computed diff and stats."""
        diff = FileDiff(
            original_content=original_content,
            new_content=new_content
        )
        
        # Generate unified diff
        if operation == FileOperation.MODIFY and original_content and new_content:
            diff.unified_diff = DiffGenerator.generate_diff(
                original_content, new_content, path
            )
            added, removed = DiffGenerator.count_changes(diff.unified_diff)
        elif operation == FileOperation.ADD and new_content:
            added = new_content.count("\n") + 1
            removed = 0
        elif operation == FileOperation.DELETE and original_content:
            added = 0
            removed = original_content.count("\n") + 1
        else:
            added = removed = 0
        
        # Detect language
        language = DiffGenerator.detect_language(path)
        
        # Assess risk
        risk, risk_reason = DiffGenerator.assess_risk(new_content or "", path)
        
        return FileChange(
            path=path,
            operation=operation,
            diff=diff,
            summary_line=reason[:80] if reason else f"{operation.value} {path}",
            reason=reason,
            acceptance_criteria_ids=acceptance_criteria_ids or [],
            risk=risk,
            risk_reason=risk_reason,
            language=language,
            lines_added=added,
            lines_removed=removed
        )
    
    @staticmethod
    def detect_language(path: str) -> Optional[str]:
        """Detect programming language from file extension."""
        ext_map = {
            ".ts": "typescript",
            ".tsx": "typescript",
            ".js": "javascript",
            ".jsx": "javascript",
            ".py": "python",
            ".css": "css",
            ".scss": "scss",
            ".html": "html",
            ".json": "json",
            ".md": "markdown",
            ".yaml": "yaml",
            ".yml": "yaml",
        }
        
        for ext, lang in ext_map.items():
            if path.endswith(ext):
                return lang
        return None
    
    @staticmethod
    def assess_risk(content: str, path: str) -> Tuple[ChangeRisk, str]:
        """Assess risk level of a change."""
        reasons = []
        
        # High risk patterns
        high_risk_patterns = [
            (r'process\.env', "Accesses environment variables"),
            (r'exec\s*\(', "Uses exec()"),
            (r'eval\s*\(', "Uses eval()"),
            (r'dangerouslySetInnerHTML', "Uses dangerouslySetInnerHTML"),
            (r'__proto__', "Modifies prototype"),
        ]
        
        for pattern, reason in high_risk_patterns:
            if re.search(pattern, content):
                reasons.append(reason)
        
        # Check critical paths
        critical_paths = ["auth", "payment", "security", "config", "env"]
        if any(p in path.lower() for p in critical_paths):
            reasons.append(f"Modifies critical path")
        
        if len(reasons) >= 2:
            return ChangeRisk.HIGH, "; ".join(reasons)
        elif len(reasons) == 1:
            return ChangeRisk.MEDIUM, reasons[0]
        
        return ChangeRisk.LOW, ""


class CommitBuilder:
    """
    Builds commit intents with proper metadata.
    """
    
    COMMIT_TEMPLATES = {
        "feature": "feat: {summary}",
        "fix": "fix: {summary}",
        "refactor": "refactor: {summary}",
        "test": "test: {summary}",
        "docs": "docs: {summary}",
        "chore": "chore: {summary}",
    }
    
    @staticmethod
    def build_commit_message(
        task_type: str,
        summary: str,
        body: str = "",
        task_id: str = ""
    ) -> Tuple[str, str]:
        """Build conventional commit message."""
        template = CommitBuilder.COMMIT_TEMPLATES.get(task_type, "chore: {summary}")
        message = template.format(summary=summary[:50])
        
        if task_id:
            body = f"Task: {task_id}\n\n{body}"
        
        return message, body
    
    @staticmethod
    def create_commit_intent(
        task_id: str,
        changeset_id: str,
        summary: str,
        task_type: str = "feature",
        plan_id: Optional[str] = None,
        is_safe: bool = False,
        version_bump: SemanticVersionBump = SemanticVersionBump.NONE,
        rollback_files: List[str] = None
    ) -> CommitIntent:
        """Create a complete commit intent."""
        message, body = CommitBuilder.build_commit_message(
            task_type=task_type,
            summary=summary,
            task_id=task_id
        )
        
        return CommitIntent(
            message=message,
            message_body=body,
            task_id=task_id,
            plan_id=plan_id,
            changeset_id=changeset_id,
            version_bump=version_bump,
            is_safe_to_auto_apply=is_safe,
            auto_apply_reason="Low-risk, isolated change" if is_safe else "",
            rollback_files=rollback_files or []
        )


class ReportBuilder:
    """
    Builds implementation reports with proper metadata.
    """
    
    @staticmethod
    def create_report(
        task_id: str,
        summary: str,
        changes_made: List[str],
        confidence: float = 1.0,
        new_dependencies: List[str] = None,
        inferred_items: List[Dict] = None,
        edge_cases: List[Dict] = None,
        plan_id: Optional[str] = None
    ) -> ImplementationReport:
        """Create a complete implementation report."""
        metadata = CoderMetadata(
            task_id=task_id,
            plan_id=plan_id,
            confidence=confidence
        )
        
        report = ImplementationReport(
            metadata=metadata,
            summary=summary,
            changes_made=changes_made,
            overall_confidence=confidence
        )
        
        if new_dependencies:
            report.new_dependencies = new_dependencies
            report.dependency_confidence = 0.8  # New deps reduce confidence
        
        if inferred_items:
            report.inferred_items = [
                InferredItem(**item) for item in inferred_items
            ]
        
        if edge_cases:
            report.edge_cases = [
                EdgeCase(**case) for case in edge_cases
            ]
        
        # Assess overall risk
        if report.new_dependencies or report.inferred_items:
            report.overall_risk = ChangeRisk.MEDIUM
            report.risk_factors.append("New dependencies or inferred items present")
        
        return report


class CodeTools:
    """
    Utility class aggregating all coder tools.
    """
    
    diff = DiffGenerator
    commit = CommitBuilder
    report = ReportBuilder
    
    @staticmethod
    def assemble_coder_output(
        task_id: str,
        changes: List[FileChange],
        tests: List[Any],
        summary: str,
        confidence: float = 1.0,
        plan_id: Optional[str] = None
    ) -> CoderOutput:
        """Assemble complete coder output from components."""
        # Create metadata
        metadata = CoderMetadata(
            task_id=task_id,
            plan_id=plan_id,
            confidence=confidence
        )
        
        # Create FileChangeSet
        changeset = FileChangeSet(metadata=metadata, summary=summary)
        for change in changes:
            changeset.add_change(change)
        
        # Create rollback command
        changeset.rollback_command = f"git checkout HEAD~1 -- {' '.join(c.path for c in changes)}"
        
        # Create commit intent
        commit_intent = CommitBuilder.create_commit_intent(
            task_id=task_id,
            changeset_id=changeset.id,
            summary=summary,
            plan_id=plan_id,
            is_safe=confidence > 0.8 and changeset.total_lines_added < 100,
            rollback_files=[c.path for c in changes]
        )
        
        # Create implementation report
        report = ReportBuilder.create_report(
            task_id=task_id,
            summary=f"Implemented: {summary}",
            changes_made=[c.summary_line for c in changes],
            confidence=confidence,
            plan_id=plan_id
        )
        
        return CoderOutput(
            success=True,
            file_change_set=changeset,
            commit_intent=commit_intent,
            implementation_report=report,
            total_lines_changed=changeset.total_lines_added + changeset.total_lines_removed,
            total_files_changed=changeset.total_files_changed,
            total_tests_added=len(tests)
        )
