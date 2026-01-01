"""
TypeScript Checker Module

Runs `tsc --noEmit` to check TypeScript projects for type errors.

Detection:
- Looks for `tsconfig.json` in project root

Output Format:
- file(line,col): error TS1234: message
"""

import re
from typing import List

from app.agents.tools.validator.checkers.base import (
    BaseChecker, CheckerError, CheckerSeverity
)


class TypeScriptChecker(BaseChecker):
    """
    TypeScript type checker using the TypeScript compiler.
    
    Runs `npx tsc --noEmit --pretty false` to check for type errors
    without producing output files.
    """
    
    @property
    def name(self) -> str:
        return "typescript"
    
    @property
    def detection_files(self) -> List[str]:
        return ["tsconfig.json"]
    
    @property
    def command(self) -> List[str]:
        return ["npx", "tsc", "--noEmit", "--pretty", "false"]
    
    def parse_output(self, output: str, project_path: str) -> List[CheckerError]:
        """
        Parse TypeScript compiler output.
        
        Format: path/file.ts(10,5): error TS2339: Property 'x' does not exist
        """
        errors = []
        # Pattern: file(line,col): error TS1234: message
        pattern = r"([^(]+)\((\d+),(\d+)\):\s*error\s+TS(\d+):\s*(.+)"
        
        for line in output.split("\n"):
            match = re.match(pattern, line.strip())
            if match:
                errors.append(CheckerError(
                    file=match.group(1).strip(),
                    line=int(match.group(2)),
                    column=int(match.group(3)),
                    code=f"TS{match.group(4)}",
                    message=match.group(5).strip(),
                    severity=CheckerSeverity.ERROR,
                    source=self.name
                ))
        
        return errors
