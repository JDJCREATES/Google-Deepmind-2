"""
Checker Registry Module

Central registry that manages and runs all language checkers.
Provides unified interface for running checks across project types.

Usage:
    registry = CheckerRegistry()
    results = registry.run_all("/path/to/project")
    
    # Or run specific checkers
    results = registry.run(["typescript", "eslint"], "/path/to/project")
"""

from typing import List, Dict, Optional, Type
from dataclasses import dataclass, field
from datetime import datetime
import logging

from app.agents.tools.validator.checkers.base import (
    BaseChecker, CheckerResult, CheckerError
)

logger = logging.getLogger("ships.checkers")


@dataclass
class RegistryResult:
    """
    Aggregated result from running multiple checkers.
    
    Attributes:
        results: Dict mapping checker name to result
        total_errors: Total error count across all checkers
        passed: True if all checkers passed
        duration_ms: Total execution time
    """
    results: Dict[str, CheckerResult] = field(default_factory=dict)
    total_errors: int = 0
    passed: bool = True
    duration_ms: int = 0
    
    def get_all_errors(self) -> List[CheckerError]:
        """Get all errors from all checkers."""
        errors = []
        for result in self.results.values():
            errors.extend(result.errors)
        return errors
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "results": {k: v.to_dict() for k, v in self.results.items()},
            "total_errors": self.total_errors,
            "passed": self.passed,
            "duration_ms": self.duration_ms,
        }


class CheckerRegistry:
    """
    Central registry for managing and running language checkers.
    
    Features:
    - Auto-registers all available checkers
    - Runs only applicable checkers based on project detection
    - Aggregates results from all checkers
    - Reports all errors to diagnostics store
    """
    
    def __init__(self, api_url: str = "http://localhost:8001"):
        """
        Initialize registry with all available checkers.
        
        Args:
            api_url: Backend API URL for diagnostics reporting
        """
        self.api_url = api_url
        self._checkers: Dict[str, BaseChecker] = {}
        self._register_default_checkers()
    
    def _register_default_checkers(self) -> None:
        """Register all built-in checkers."""
        # Import here to avoid circular imports
        from app.agents.tools.validator.checkers.typescript import TypeScriptChecker
        from app.agents.tools.validator.checkers.python import PythonChecker
        from app.agents.tools.validator.checkers.rust import RustChecker
        from app.agents.tools.validator.checkers.go import GoChecker
        from app.agents.tools.validator.checkers.css import CSSChecker
        from app.agents.tools.validator.checkers.eslint import ESLintChecker
        
        self.register(TypeScriptChecker())
        self.register(PythonChecker())
        self.register(RustChecker())
        self.register(GoChecker())
        self.register(CSSChecker())
        self.register(ESLintChecker())
    
    def register(self, checker: BaseChecker) -> None:
        """
        Register a checker.
        
        Args:
            checker: Checker instance to register
        """
        self._checkers[checker.name] = checker
        logger.debug(f"Registered checker: {checker.name}")
    
    def get(self, name: str) -> Optional[BaseChecker]:
        """Get a checker by name."""
        return self._checkers.get(name)
    
    @property
    def available_checkers(self) -> List[str]:
        """List of all registered checker names."""
        return list(self._checkers.keys())
    
    def detect_project_types(self, project_path: str) -> List[str]:
        """
        Detect which checkers apply to this project.
        
        Args:
            project_path: Absolute path to project root
            
        Returns:
            List of checker names that detected the project
        """
        detected = []
        for name, checker in self._checkers.items():
            if checker.detect(project_path):
                detected.append(name)
        return detected
    
    def run(
        self, 
        checker_names: List[str], 
        project_path: str,
        report_diagnostics: bool = True
    ) -> RegistryResult:
        """
        Run specific checkers on a project.
        
        Args:
            checker_names: List of checker names to run
            project_path: Absolute path to project root
            report_diagnostics: Whether to report errors to diagnostics store
            
        Returns:
            RegistryResult with aggregated results
        """
        start = datetime.utcnow()
        registry_result = RegistryResult()
        
        for name in checker_names:
            checker = self._checkers.get(name)
            if not checker:
                logger.warning(f"Unknown checker: {name}")
                continue
            
            result = checker.check(project_path)
            registry_result.results[name] = result
            
            if not result.skipped:
                registry_result.total_errors += result.error_count
                if not result.passed:
                    registry_result.passed = False
        
        registry_result.duration_ms = int(
            (datetime.utcnow() - start).total_seconds() * 1000
        )
        
        # Report all errors to diagnostics store
        if report_diagnostics:
            all_errors = registry_result.get_all_errors()
            if all_errors:
                self._report_all_errors(project_path, all_errors)
        
        return registry_result
    
    def run_all(
        self, 
        project_path: str,
        report_diagnostics: bool = True
    ) -> RegistryResult:
        """
        Run all applicable checkers on a project.
        
        Auto-detects project types and runs only relevant checkers.
        
        Args:
            project_path: Absolute path to project root
            report_diagnostics: Whether to report errors to diagnostics store
            
        Returns:
            RegistryResult with aggregated results
        """
        detected = self.detect_project_types(project_path)
        logger.info(f"Detected project types: {detected}")
        
        if not detected:
            return RegistryResult(passed=True)
        
        return self.run(detected, project_path, report_diagnostics)
    
    def _report_all_errors(
        self, 
        project_path: str, 
        errors: List[CheckerError]
    ) -> bool:
        """Report all errors to the diagnostics store."""
        try:
            import httpx
            response = httpx.post(
                f"{self.api_url}/diagnostics/report",
                json={
                    "project_path": project_path,
                    "errors": [e.to_dict() for e in errors]
                },
                timeout=5.0
            )
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Failed to report diagnostics: {e}")
            return False
