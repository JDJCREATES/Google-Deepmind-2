"""
Build/Test Checker Module

Runs build and test commands for projects.
Ensures code compiles and tests pass.

Detection:
- package.json with "build" or "test" scripts
- Cargo.toml (cargo build)
- go.mod (go build)
"""

import json
import subprocess
from pathlib import Path
from typing import List

from app.agents.tools.validator.checkers.base import (
    BaseChecker, CheckerError, CheckerResult, CheckerSeverity
)


class BuildChecker(BaseChecker):
    """
    Build verification checker.
    
    Runs project-specific build commands to verify code compiles.
    """
    
    @property
    def name(self) -> str:
        return "build"
    
    @property
    def detection_files(self) -> List[str]:
        return ["package.json", "Cargo.toml", "go.mod", "pyproject.toml"]
    
    @property
    def command(self) -> List[str]:
        # Dynamic - determined in check() based on project type
        return []
    
    def check(self, project_path: str) -> CheckerResult:
        """Run appropriate build command based on project type."""
        from datetime import datetime
        
        start = datetime.utcnow()
        path = Path(project_path)
        
        # Determine build command based on project type
        cmd = None
        
        if (path / "package.json").exists():
            # Check if build script exists
            try:
                with open(path / "package.json") as f:
                    pkg = json.load(f)
                    scripts = pkg.get("scripts", {})
                    if "build" in scripts:
                        cmd = ["npm", "run", "build"]
            except Exception:
                pass
                
        elif (path / "Cargo.toml").exists():
            cmd = ["cargo", "build", "--release"]
            
        elif (path / "go.mod").exists():
            cmd = ["go", "build", "./..."]
        
        if not cmd:
            return CheckerResult(
                checker_name=self.name,
                skipped=True,
                skip_reason="No build command detected"
            )
        
        try:
            result = subprocess.run(
                cmd,
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=120  # Build can take longer
            )
            
            errors = []
            if result.returncode != 0:
                errors.append(CheckerError(
                    file="",
                    line=0,
                    message=f"Build failed: {result.stderr[:500]}",
                    severity=CheckerSeverity.ERROR,
                    source=self.name
                ))
            
            duration = int((datetime.utcnow() - start).total_seconds() * 1000)
            
            return CheckerResult(
                checker_name=self.name,
                errors=errors,
                passed=len(errors) == 0,
                duration_ms=duration
            )
            
        except subprocess.TimeoutExpired:
            return CheckerResult(
                checker_name=self.name,
                errors=[CheckerError(
                    file="", line=0,
                    message="Build timed out (120s)",
                    source=self.name
                )],
                passed=False
            )
        except FileNotFoundError:
            return CheckerResult(
                checker_name=self.name,
                skipped=True,
                skip_reason="Build tool not installed"
            )
    
    def parse_output(self, output: str, project_path: str) -> List[CheckerError]:
        """Not used - check() handles everything."""
        return []


class TestChecker(BaseChecker):
    """
    Test runner checker.
    
    Runs project-specific test commands.
    """
    
    @property
    def name(self) -> str:
        return "test"
    
    @property
    def detection_files(self) -> List[str]:
        return ["package.json", "Cargo.toml", "go.mod", "pyproject.toml"]
    
    @property
    def command(self) -> List[str]:
        return []
    
    def check(self, project_path: str) -> CheckerResult:
        """Run appropriate test command based on project type."""
        from datetime import datetime
        
        start = datetime.utcnow()
        path = Path(project_path)
        
        cmd = None
        
        if (path / "package.json").exists():
            try:
                with open(path / "package.json") as f:
                    pkg = json.load(f)
                    scripts = pkg.get("scripts", {})
                    if "test" in scripts:
                        cmd = ["npm", "run", "test", "--", "--passWithNoTests"]
            except Exception:
                pass
                
        elif (path / "Cargo.toml").exists():
            cmd = ["cargo", "test"]
            
        elif (path / "go.mod").exists():
            cmd = ["go", "test", "./..."]
            
        elif (path / "pyproject.toml").exists():
            cmd = ["pytest", "--tb=short", "-q"]
        
        if not cmd:
            return CheckerResult(
                checker_name=self.name,
                skipped=True,
                skip_reason="No test command detected"
            )
        
        try:
            result = subprocess.run(
                cmd,
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=180  # Tests can take longer
            )
            
            errors = []
            if result.returncode != 0:
                errors.append(CheckerError(
                    file="",
                    line=0,
                    message=f"Tests failed: {result.stderr[:500] or result.stdout[:500]}",
                    severity=CheckerSeverity.ERROR,
                    source=self.name
                ))
            
            duration = int((datetime.utcnow() - start).total_seconds() * 1000)
            
            return CheckerResult(
                checker_name=self.name,
                errors=errors,
                passed=len(errors) == 0,
                duration_ms=duration
            )
            
        except subprocess.TimeoutExpired:
            return CheckerResult(
                checker_name=self.name,
                errors=[CheckerError(
                    file="", line=0,
                    message="Tests timed out (180s)",
                    source=self.name
                )],
                passed=False
            )
        except FileNotFoundError:
            return CheckerResult(
                checker_name=self.name,
                skipped=True,
                skip_reason="Test tool not installed"
            )
    
    def parse_output(self, output: str, project_path: str) -> List[CheckerError]:
        """Not used - check() handles everything."""
        return []
