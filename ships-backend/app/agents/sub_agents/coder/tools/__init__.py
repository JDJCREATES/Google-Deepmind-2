"""
ShipS* Coder Tools

Tools for the Coder agent:
- DiffGenerator: Creates file diffs
- CodeTools: File operations and code analysis
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import difflib


class DiffGenerator:
    """
    Generates unified diffs for file changes.
    Used by the Coder to produce reviewable code changes.
    """
    
    @staticmethod
    def generate_diff(
        original_content: str,
        new_content: str,
        file_path: str = "file"
    ) -> str:
        """
        Generate a unified diff between original and new content.
        
        Args:
            original_content: Original file content
            new_content: New file content
            file_path: File path for diff header
            
        Returns:
            Unified diff string
        """
        original_lines = original_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)
        
        diff = difflib.unified_diff(
            original_lines,
            new_lines,
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
            lineterm=""
        )
        
        return "".join(diff)
    
    @staticmethod
    def parse_diff(diff_text: str) -> Dict[str, Any]:
        """
        Parse a unified diff into structured data.
        
        Args:
            diff_text: Unified diff string
            
        Returns:
            Dict with added_lines, removed_lines, file_path
        """
        added = []
        removed = []
        
        for line in diff_text.splitlines():
            if line.startswith("+") and not line.startswith("+++"):
                added.append(line[1:])
            elif line.startswith("-") and not line.startswith("---"):
                removed.append(line[1:])
        
        return {
            "added_lines": added,
            "removed_lines": removed,
            "additions": len(added),
            "deletions": len(removed),
        }


class CodeTools:
    """
    Code-related tools for the Coder agent.
    """
    
    @staticmethod
    def detect_language(file_path: str) -> str:
        """Detect programming language from file extension."""
        ext_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript-react",
            ".jsx": "javascript-react",
            ".css": "css",
            ".scss": "scss",
            ".html": "html",
            ".json": "json",
            ".md": "markdown",
            ".yaml": "yaml",
            ".yml": "yaml",
        }
        
        for ext, lang in ext_map.items():
            if file_path.endswith(ext):
                return lang
        
        return "unknown"
    
    @staticmethod
    def count_lines(content: str) -> Dict[str, int]:
        """Count lines of code, comments, and blanks."""
        lines = content.splitlines()
        total = len(lines)
        blank = sum(1 for line in lines if not line.strip())
        
        return {
            "total": total,
            "blank": blank,
            "code": total - blank,  # Simplified - doesn't count comments
        }
    
    @staticmethod
    def validate_syntax(content: str, language: str) -> Dict[str, Any]:
        """
        Basic syntax validation.
        Note: For full validation, use the Validator agent.
        """
        issues = []
        
        # Check for unclosed brackets
        brackets = {"(": ")", "[": "]", "{": "}"}
        stack = []
        
        for char in content:
            if char in brackets:
                stack.append(brackets[char])
            elif char in brackets.values():
                if not stack or stack.pop() != char:
                    issues.append(f"Mismatched bracket: {char}")
        
        if stack:
            issues.append(f"Unclosed brackets: {len(stack)}")
        
        return {
            "valid": len(issues) == 0,
            "issues": issues,
        }
    
    @staticmethod
    def extract_imports(content: str, language: str) -> List[str]:
        """Extract import statements from code."""
        imports = []
        
        for line in content.splitlines():
            line = line.strip()
            if language in ["python"]:
                if line.startswith("import ") or line.startswith("from "):
                    imports.append(line)
            elif language in ["javascript", "typescript", "typescript-react", "javascript-react"]:
                if line.startswith("import ") or line.startswith("require("):
                    imports.append(line)
        
        return imports


__all__ = [
    "DiffGenerator",
    "CodeTools",
]
