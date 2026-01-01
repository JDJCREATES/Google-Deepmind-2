"""
Base Checker Module

Provides abstract base class for all language checkers.
Each checker must implement detection and validation logic.

Architecture:
- BaseChecker: Abstract class that all checkers inherit
- CheckerError: Standardized error format across all checkers
- CheckerResult: Result container with errors and metadata
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import List, Optional, Dict, Any
import subprocess
import logging

logger = logging.getLogger("ships.checkers")


class CheckerSeverity(str, Enum):
    """Severity levels for checker errors."""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class CheckerError:
    """
    Standardized error format for all language checkers.
    
    Attributes:
        file: Relative path to the file with the error
        line: 1-indexed line number
        column: 1-indexed column number
        message: Human-readable error message
        code: Language-specific error code (e.g., "TS2339", "E501")
        severity: Error severity level
        source: Name of the checker that produced this error
    """
    file: str
    line: int
    column: int = 1
    message: str = ""
    code: Optional[str] = None
    severity: CheckerSeverity = CheckerSeverity.ERROR
    source: str = "unknown"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "file": self.file,
            "line": self.line,
            "column": self.column,
            "message": self.message,
            "code": self.code,
            "severity": self.severity.value,
            "source": self.source,
        }


@dataclass
class CheckerResult:
    """
    Result container for checker execution.
    
    Attributes:
        checker_name: Name of the checker that ran
        errors: List of errors found
        passed: Whether validation passed (no errors)
        duration_ms: Execution time in milliseconds
        skipped: Whether checker was skipped (project not applicable)
        skip_reason: Reason for skipping (if skipped)
    """
    checker_name: str
    errors: List[CheckerError] = field(default_factory=list)
    passed: bool = True
    duration_ms: int = 0
    skipped: bool = False
    skip_reason: Optional[str] = None
    
    @property
    def error_count(self) -> int:
        """Number of errors found."""
        return len(self.errors)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "checker_name": self.checker_name,
            "errors": [e.to_dict() for e in self.errors],
            "passed": self.passed,
            "error_count": self.error_count,
            "duration_ms": self.duration_ms,
            "skipped": self.skipped,
            "skip_reason": self.skip_reason,
        }


class BaseChecker(ABC):
    """
    Abstract base class for language-specific checkers.
    
    All checkers must implement:
    - name: Unique identifier for the checker
    - detect(): Check if project uses this language
    - check(): Run validation and return errors
    
    Checkers should:
    - Auto-detect project type based on config files
    - Run the appropriate linting/type-checking tool
    - Parse output into standardized CheckerError format
    - Report errors to the diagnostics store
    """
    
    def __init__(self, timeout: int = 60):
        """
        Initialize checker.
        
        Args:
            timeout: Maximum seconds to wait for checker command
        """
        self.timeout = timeout
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique name for this checker (e.g., 'typescript', 'python')."""
        pass
    
    @property
    @abstractmethod
    def detection_files(self) -> List[str]:
        """
        List of files that indicate this project type.
        
        Examples:
        - TypeScript: ["tsconfig.json"]
        - Python: ["pyproject.toml", "setup.py", "requirements.txt"]
        - Rust: ["Cargo.toml"]
        """
        pass
    
    @property
    def command(self) -> List[str]:
        """
        Command to run for checking. Override in subclass.
        
        Returns:
            Command as list of strings (for subprocess)
        """
        return []
    
    def detect(self, project_path: str) -> bool:
        """
        Check if this project uses the language this checker handles.
        
        Args:
            project_path: Absolute path to project root
            
        Returns:
            True if any detection file exists
        """
        path = Path(project_path)
        for detection_file in self.detection_files:
            if (path / detection_file).exists():
                return True
        return False
    
    @abstractmethod
    def parse_output(self, output: str, project_path: str) -> List[CheckerError]:
        """
        Parse checker command output into standardized errors.
        
        Args:
            output: Raw stdout/stderr from checker command
            project_path: Project root for resolving relative paths
            
        Returns:
            List of CheckerError objects
        """
        pass
    
    def check(self, project_path: str) -> CheckerResult:
        """
        Run the checker and return results.
        
        Args:
            project_path: Absolute path to project root
            
        Returns:
            CheckerResult with errors and metadata
        """
        start = datetime.utcnow()
        
        # Skip if project doesn't use this language
        if not self.detect(project_path):
            return CheckerResult(
                checker_name=self.name,
                skipped=True,
                skip_reason=f"No {self.detection_files} found"
            )
        
        # Get command to run
        cmd = self.command
        if not cmd:
            return CheckerResult(
                checker_name=self.name,
                skipped=True,
                skip_reason="No command configured"
            )
        
        try:
            result = subprocess.run(
                cmd,
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            
            # Parse output (both stdout and stderr)
            output = result.stdout + result.stderr
            errors = self.parse_output(output, project_path)
            
            duration = int((datetime.utcnow() - start).total_seconds() * 1000)
            
            return CheckerResult(
                checker_name=self.name,
                errors=errors,
                passed=len(errors) == 0,
                duration_ms=duration
            )
            
        except subprocess.TimeoutExpired:
            logger.warning(f"[{self.name}] Checker timed out after {self.timeout}s")
            return CheckerResult(
                checker_name=self.name,
                errors=[CheckerError(
                    file="",
                    line=0,
                    message=f"Checker timed out after {self.timeout}s",
                    source=self.name
                )],
                passed=False,
                duration_ms=self.timeout * 1000
            )
            
        except FileNotFoundError:
            # Command not found (tool not installed)
            logger.info(f"[{self.name}] Tool not installed, skipping")
            return CheckerResult(
                checker_name=self.name,
                skipped=True,
                skip_reason="Tool not installed"
            )
            
        except Exception as e:
            logger.error(f"[{self.name}] Checker failed: {e}")
            return CheckerResult(
                checker_name=self.name,
                skipped=True,
                skip_reason=f"Error: {str(e)}"
            )
    
    def report_to_diagnostics(
        self, 
        project_path: str, 
        errors: List[CheckerError],
        api_url: str = "http://localhost:8001"
    ) -> bool:
        """
        Report errors to the diagnostics store.
        
        Args:
            project_path: Project root path
            errors: List of errors to report
            api_url: Backend API URL
            
        Returns:
            True if report was successful
        """
        if not errors:
            return True
            
        try:
            import httpx
            response = httpx.post(
                f"{api_url}/diagnostics/report",
                json={
                    "project_path": project_path,
                    "errors": [e.to_dict() for e in errors]
                },
                timeout=5.0
            )
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"[{self.name}] Failed to report diagnostics: {e}")
            return False
