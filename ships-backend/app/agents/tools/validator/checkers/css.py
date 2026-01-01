"""
CSS/SCSS Checker Module

Runs `npx stylelint` for CSS/SCSS projects.
Catches syntax errors, deprecated features, naming issues.

Detection:
- .stylelintrc, .stylelintrc.json, stylelint.config.js
- Or presence of .css/.scss files with package.json
"""

import json
import re
from pathlib import Path
from typing import List

from app.agents.tools.validator.checkers.base import (
    BaseChecker, CheckerError, CheckerSeverity
)


class CSSChecker(BaseChecker):
    """
    CSS/SCSS linter using Stylelint.
    
    Runs `npx stylelint "**/*.css" "**/*.scss" --formatter json`.
    """
    
    @property
    def name(self) -> str:
        return "css"
    
    @property
    def detection_files(self) -> List[str]:
        return [
            ".stylelintrc",
            ".stylelintrc.json",
            ".stylelintrc.js",
            "stylelint.config.js",
            "stylelint.config.cjs",
        ]
    
    def detect(self, project_path: str) -> bool:
        """
        Detect CSS project.
        
        Returns True if stylelint config exists OR
        if there are CSS/SCSS files and package.json exists.
        """
        path = Path(project_path)
        
        # Check for stylelint config
        for config in self.detection_files:
            if (path / config).exists():
                return True
        
        # Check for CSS files + package.json (likely a web project)
        if (path / "package.json").exists():
            # Look for CSS/SCSS files
            css_files = list(path.glob("**/*.css"))[:1]
            scss_files = list(path.glob("**/*.scss"))[:1]
            if css_files or scss_files:
                return True
        
        return False
    
    @property
    def command(self) -> List[str]:
        return [
            "npx", "stylelint", 
            "**/*.css", "**/*.scss",
            "--formatter", "json",
            "--ignore-pattern", "node_modules/**"
        ]
    
    def parse_output(self, output: str, project_path: str) -> List[CheckerError]:
        """
        Parse Stylelint JSON output.
        
        Format: [{"source": "path", "warnings": [{"line": 1, "text": "..."}]}]
        """
        errors = []
        
        try:
            # Find JSON array in output
            if "[" in output:
                json_start = output.index("[")
                json_end = output.rindex("]") + 1
                data = json.loads(output[json_start:json_end])
                
                for file_result in data:
                    source = file_result.get("source", "")
                    for warning in file_result.get("warnings", []):
                        severity = (
                            CheckerSeverity.ERROR 
                            if warning.get("severity") == "error"
                            else CheckerSeverity.WARNING
                        )
                        errors.append(CheckerError(
                            file=source,
                            line=warning.get("line", 1),
                            column=warning.get("column", 1),
                            code=warning.get("rule", ""),
                            message=warning.get("text", ""),
                            severity=severity,
                            source=self.name
                        ))
        except (json.JSONDecodeError, ValueError):
            # Fallback: parse text output
            pattern = r"([^:]+):(\d+):(\d+):\s*(.+)"
            for line in output.split("\n"):
                match = re.match(pattern, line.strip())
                if match:
                    errors.append(CheckerError(
                        file=match.group(1),
                        line=int(match.group(2)),
                        column=int(match.group(3)),
                        message=match.group(4),
                        severity=CheckerSeverity.WARNING,
                        source=self.name
                    ))
        
        return errors
