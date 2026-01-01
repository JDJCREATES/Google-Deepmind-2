"""
ShipS* Language Checkers Package

Production-grade, modular syntax and type checkers for multiple languages.
Each checker auto-detects project type and runs the appropriate linting tool.

Supported Languages:
- TypeScript/JavaScript (tsc, eslint)
- Python (ruff)
- Rust (cargo check)
- Go (go vet)
- CSS/SCSS (stylelint)

Usage:
    from app.agents.tools.validator.checkers import CheckerRegistry
    
    registry = CheckerRegistry()
    errors = registry.run_all(project_path)
"""

from app.agents.tools.validator.checkers.base import (
    BaseChecker,
    CheckerResult,
    CheckerError,
)
from app.agents.tools.validator.checkers.registry import CheckerRegistry
from app.agents.tools.validator.checkers.typescript import TypeScriptChecker
from app.agents.tools.validator.checkers.python import PythonChecker
from app.agents.tools.validator.checkers.rust import RustChecker
from app.agents.tools.validator.checkers.go import GoChecker
from app.agents.tools.validator.checkers.css import CSSChecker
from app.agents.tools.validator.checkers.eslint import ESLintChecker

__all__ = [
    # Base
    "BaseChecker",
    "CheckerResult",
    "CheckerError",
    "CheckerRegistry",
    # Checkers
    "TypeScriptChecker",
    "PythonChecker",
    "RustChecker",
    "GoChecker",
    "CSSChecker",
    "ESLintChecker",
]
