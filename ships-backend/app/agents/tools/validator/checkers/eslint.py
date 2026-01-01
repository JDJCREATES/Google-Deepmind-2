"""
ESLint Checker Module

Runs `npx eslint` for JavaScript/TypeScript projects.
Catches linting issues, code style, potential bugs.

Detection:
- .eslintrc, .eslintrc.js, .eslintrc.json, eslint.config.js
"""

import json
import re
from typing import List

from app.agents.tools.validator.checkers.base import (
    BaseChecker, CheckerError, CheckerSeverity
)


class ESLintChecker(BaseChecker):
    """
    JavaScript/TypeScript linter using ESLint.
    
    Runs `npx eslint . --format json`.
    """
    
    @property
    def name(self) -> str:
        return "eslint"
    
    @property
    def detection_files(self) -> List[str]:
        return [
            ".eslintrc",
            ".eslintrc.js",
            ".eslintrc.cjs",
            ".eslintrc.json",
            ".eslintrc.yaml",
            ".eslintrc.yml",
            "eslint.config.js",
            "eslint.config.mjs",
        ]
    
    @property
    def command(self) -> List[str]:
        return [
            "npx", "eslint", ".", 
            "--format", "json",
            "--ext", ".js,.jsx,.ts,.tsx",
            "--ignore-pattern", "node_modules/**"
        ]
    
    def parse_output(self, output: str, project_path: str) -> List[CheckerError]:
        """
        Parse ESLint JSON output.
        
        Format: [{"filePath": "...", "messages": [{"line": 1, "message": "..."}]}]
        """
        errors = []
        
        try:
            # Find JSON array in output
            if "[" in output:
                json_start = output.index("[")
                json_end = output.rindex("]") + 1
                data = json.loads(output[json_start:json_end])
                
                for file_result in data:
                    file_path = file_result.get("filePath", "")
                    for msg in file_result.get("messages", []):
                        # ESLint severity: 1 = warning, 2 = error
                        severity = (
                            CheckerSeverity.ERROR 
                            if msg.get("severity", 1) == 2
                            else CheckerSeverity.WARNING
                        )
                        errors.append(CheckerError(
                            file=file_path,
                            line=msg.get("line", 1),
                            column=msg.get("column", 1),
                            code=msg.get("ruleId", ""),
                            message=msg.get("message", ""),
                            severity=severity,
                            source=self.name
                        ))
        except (json.JSONDecodeError, ValueError):
            # Fallback: parse text output
            # Format: path/file.js:10:5: message [rule]
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
