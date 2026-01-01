"""
Go Checker Module

Runs `go vet` for Go projects.
Catches common mistakes like unreachable code, suspicious constructs.

Detection:
- go.mod, go.sum
"""

import re
from typing import List

from app.agents.tools.validator.checkers.base import (
    BaseChecker, CheckerError, CheckerSeverity
)


class GoChecker(BaseChecker):
    """
    Go static analyzer using go vet.
    
    Runs `go vet ./...` to check all packages.
    """
    
    @property
    def name(self) -> str:
        return "go"
    
    @property
    def detection_files(self) -> List[str]:
        return ["go.mod", "go.sum"]
    
    @property
    def command(self) -> List[str]:
        return ["go", "vet", "./..."]
    
    def parse_output(self, output: str, project_path: str) -> List[CheckerError]:
        """
        Parse go vet output.
        
        Format: # package
                path/file.go:10:5: message
        """
        errors = []
        # Pattern: file.go:line:col: message (or file.go:line: message)
        pattern = r"([^:]+\.go):(\d+):(?:(\d+):)?\s*(.+)"
        
        for line in output.split("\n"):
            # Skip package headers
            if line.startswith("#"):
                continue
            
            match = re.match(pattern, line.strip())
            if match:
                errors.append(CheckerError(
                    file=match.group(1),
                    line=int(match.group(2)),
                    column=int(match.group(3)) if match.group(3) else 1,
                    message=match.group(4),
                    severity=CheckerSeverity.ERROR,
                    source=self.name
                ))
        
        return errors
