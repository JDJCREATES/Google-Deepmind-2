"""
Call Graph Package - Language-Specific Analyzers

Uses specialized tools for accurate call graph generation:
- Python: PyCG + jedi
- TypeScript/JavaScript: TS Compiler API (via Node.js sidecar)
- Fallback: tree-sitter for basic symbols
"""

from .python_analyzer import PythonCallGraphAnalyzer
from .typescript_analyzer import TypeScriptCallGraphAnalyzer
from .merger import CallGraphMerger

__all__ = [
    "PythonCallGraphAnalyzer",
    "TypeScriptCallGraphAnalyzer",
    "CallGraphMerger",
]
