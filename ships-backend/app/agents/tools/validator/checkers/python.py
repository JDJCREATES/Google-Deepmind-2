"""
Python Checker Module

Runs `ruff check` for fast Python linting (syntax, style, complexity).
Falls back to `python -m py_compile` if ruff not installed.

Detection:
- pyproject.toml, setup.py, setup.cfg, requirements.txt
"""

import json
import re
from typing import List

from app.agents.tools.validator.checkers.base import (
    BaseChecker, CheckerError, CheckerSeverity
)


class PythonChecker(BaseChecker):
    """
    Python linter using Ruff (fast, Rust-based linter).
    
    Falls back to py_compile for basic syntax checking if Ruff unavailable.
    """
    
    @property
    def name(self) -> str:
        return "python"
    
    @property
    def detection_files(self) -> List[str]:
        return ["pyproject.toml", "setup.py", "setup.cfg", "requirements.txt"]
    
    @property
    def command(self) -> List[str]:
        # Use JSON output for easier parsing
        return ["ruff", "check", ".", "--output-format=json"]
    
    def parse_output(self, output: str, project_path: str) -> List[CheckerError]:
        """
        Parse Ruff JSON output.
        
        JSON format:
        [{"code": "E501", "message": "...", "filename": "...", "location": {"row": 1, "column": 1}}]
        """
        errors = []
        
        # Try parsing as JSON (ruff --output-format=json)
        try:
            # Find JSON array in output
            if "[" in output:
                json_start = output.index("[")
                json_end = output.rindex("]") + 1
                json_str = output[json_start:json_end]
                data = json.loads(json_str)
                
                for item in data:
                    location = item.get("location", {})
                    errors.append(CheckerError(
                        file=item.get("filename", ""),
                        line=location.get("row", 1),
                        column=location.get("column", 1),
                        code=item.get("code", ""),
                        message=item.get("message", ""),
                        severity=CheckerSeverity.ERROR,
                        source=self.name
                    ))
                return errors
        except (json.JSONDecodeError, ValueError):
            pass
        
        # Fallback: Parse text output
        # Format: path/file.py:10:5: E501 line too long
        pattern = r"([^:]+):(\d+):(\d+):\s*(\w+)\s+(.+)"
        for line in output.split("\n"):
            match = re.match(pattern, line.strip())
            if match:
                errors.append(CheckerError(
                    file=match.group(1),
                    line=int(match.group(2)),
                    column=int(match.group(3)),
                    code=match.group(4),
                    message=match.group(5),
                    severity=CheckerSeverity.ERROR,
                    source=self.name
                ))
        
        return errors
