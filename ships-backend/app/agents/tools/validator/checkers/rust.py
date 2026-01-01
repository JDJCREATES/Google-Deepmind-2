"""
Rust Checker Module

Runs `cargo check` for Rust projects.
Catches type errors and borrow-checker issues without building.

Detection:
- Cargo.toml
"""

import re
from typing import List

from app.agents.tools.validator.checkers.base import (
    BaseChecker, CheckerError, CheckerSeverity
)


class RustChecker(BaseChecker):
    """
    Rust type checker using Cargo.
    
    Runs `cargo check --message-format=short` for fast type checking.
    """
    
    @property
    def name(self) -> str:
        return "rust"
    
    @property
    def detection_files(self) -> List[str]:
        return ["Cargo.toml"]
    
    @property
    def command(self) -> List[str]:
        return ["cargo", "check", "--message-format=short"]
    
    def parse_output(self, output: str, project_path: str) -> List[CheckerError]:
        """
        Parse Cargo check output.
        
        Short format: path/file.rs:10:5: error[E0001]: message
        """
        errors = []
        # Pattern: file.rs:line:col: level[code]: message
        pattern = r"([^:]+):(\d+):(\d+):\s*(error|warning)\[?(\w+)?\]?:\s*(.+)"
        
        for line in output.split("\n"):
            match = re.match(pattern, line.strip())
            if match:
                level = match.group(4)
                severity = (
                    CheckerSeverity.ERROR if level == "error" 
                    else CheckerSeverity.WARNING
                )
                errors.append(CheckerError(
                    file=match.group(1),
                    line=int(match.group(2)),
                    column=int(match.group(3)),
                    code=match.group(5) or "",
                    message=match.group(6),
                    severity=severity,
                    source=self.name
                ))
        
        return errors
