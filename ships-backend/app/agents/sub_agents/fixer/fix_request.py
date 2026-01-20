"""
ShipS* Fix Request Model

Structured data model for validator → fixer handoff.
This replaces the messy error_log parsing with clean typed data.
"""

from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
import uuid


class ViolationDetail(BaseModel):
    """Single violation with full context for fixer."""
    
    # Made optional with defaults to handle general errors without specific file
    file_path: str = Field(default="unknown", description="Relative file path")
    line_number: Optional[int] = Field(None, description="Line number if available")
    column: Optional[int] = Field(None, description="Column number if available")
    error_code: str = Field(default="BUILD_ERROR", description="Error code (e.g., TS2307, E0001)")
    message: str = Field(..., description="Full error message")
    severity: str = Field(default="error", description="error | warning | info")
    source: str = Field(default="unknown", description="typescript | eslint | build | python | etc")
    
    # Context for smarter fixes
    surrounding_code: Optional[str] = Field(None, description="Code snippet around error")
    suggested_fix: Optional[str] = Field(None, description="If tool provides a suggestion")


class SuggestedFix(BaseModel):
    """Suggested fix from collective intelligence or heuristics."""
    
    file_path: str
    description: str
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    code_snippet: Optional[str] = None
    source: str = Field(default="heuristic", description="heuristic | collective_intelligence | llm")


class FixRequest(BaseModel):
    """
    Structured request from Validator to Fixer.
    
    This is the canonical handoff format between validator and fixer agents.
    It provides all context needed for intelligent fix generation.
    """
    
    # Identity
    id: str = Field(default_factory=lambda: f"fix_{uuid.uuid4().hex[:8]}")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # Context
    project_path: str = Field(..., description="Absolute project path")
    validation_run_id: Optional[str] = Field(None, description="ID of validation run")
    
    # What failed
    failure_layer: str = Field(..., description="build | typescript | eslint | python | test")
    total_violations: int = Field(default=0)
    violations: List[ViolationDetail] = Field(default_factory=list)
    
    # Raw output for fallback
    raw_error_output: str = Field(default="", description="Raw build/lint output")
    
    # Context from previous agents
    completed_files: List[str] = Field(default_factory=list, description="Files coder created")
    implementation_plan_summary: Optional[str] = Field(None, description="Brief summary of intent")
    
    # Previous fix attempts
    fix_attempt_number: int = Field(default=1)
    previous_fixes: List[dict] = Field(default_factory=list)
    
    # Recommendations
    suggested_fixes: List[SuggestedFix] = Field(default_factory=list)
    recommended_action: str = Field(default="fix", description="fix | escalate | replan")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
    
    @classmethod
    def from_validation_result(
        cls,
        validation_result: dict,
        project_path: str,
        completed_files: List[str] = None,
        fix_attempt: int = 1
    ) -> "FixRequest":
        """
        Create FixRequest from validator output.
        
        Args:
            validation_result: Output from validator agent
            project_path: Project path
            completed_files: List of files coder created
            fix_attempt: Current fix attempt number
            
        Returns:
            FixRequest instance
        """
        violations = []
        
        # Parse violations from validation report
        validation_report = validation_result.get("artifacts", {}).get("validation_report", {})
        raw_violations = validation_report.get("violations", [])
        
        for v in raw_violations:
            # Ensure file_path is never None (Pydantic requires string)
            file_path = v.get("file_path") or "project_root"
            if not file_path or file_path == "unknown":
                file_path = "globals.css"  # Educated guess for CSS build errors
            
            violations.append(ViolationDetail(
                file_path=file_path,
                line_number=v.get("line_number"),
                column=v.get("column"),
                error_code=v.get("error_code", "UNKNOWN"),
                message=v.get("message", str(v)),
                severity=v.get("severity", "error"),
                source=v.get("source", validation_result.get("failure_layer", "unknown"))
            ))
        
        return cls(
            project_path=project_path,
            failure_layer=validation_result.get("failure_layer", "unknown"),
            total_violations=len(violations),
            violations=violations,
            raw_error_output=validation_report.get("raw_output", ""),
            completed_files=completed_files or [],
            fix_attempt_number=fix_attempt,
            recommended_action=validation_result.get("recommended_action", "fix")
        )
    
    def get_files_with_errors(self) -> List[str]:
        """Get unique list of files that have errors."""
        return list(set(v.file_path for v in self.violations))
    
    def get_violations_for_file(self, file_path: str) -> List[ViolationDetail]:
        """Get all violations for a specific file."""
        return [v for v in self.violations if v.file_path == file_path]
    
    def to_fixer_prompt(self) -> str:
        """Generate a prompt section for the fixer agent."""
        lines = [
            f"## Fix Request ({self.id})",
            f"**Layer**: {self.failure_layer}",
            f"**Violations**: {self.total_violations}",
            f"**Attempt**: #{self.fix_attempt_number}",
            "",
            "### Errors by File:",
        ]
        
        for file_path in self.get_files_with_errors():
            file_violations = self.get_violations_for_file(file_path)
            lines.append(f"\n#### {file_path}")
            for v in file_violations:
                loc = f"L{v.line_number}" if v.line_number else ""
                lines.append(f"- [{v.error_code}] {loc}: {v.message}")
        
        if self.suggested_fixes:
            lines.append("\n### Suggested Fixes:")
            for sf in self.suggested_fixes:
                lines.append(f"- {sf.file_path}: {sf.description} (confidence: {sf.confidence:.0%})")
        
        return "\n".join(lines)
