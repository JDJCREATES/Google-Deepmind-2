"""
ShipS* Dependency Resolver

Prevents hallucinated or unsafe dependencies.
NOT an LLM agent - this is deterministic logic with curated lists.
"""

from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass
from enum import Enum
import re


class DependencyStatus(str, Enum):
    """Status of a dependency check."""
    ALLOWED = "allowed"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"
    NEEDS_REVIEW = "needs_review"


@dataclass
class DependencyCheckResult:
    """Result of checking a dependency."""
    package: str
    version: Optional[str]
    status: DependencyStatus
    reason: str
    alternatives: List[str]


class DependencyResolver:
    """
    Prevents hallucinated or unsafe dependencies.
    
    NOT an LLM agent - this is deterministic logic with curated lists.
    
    Benefits:
    - Eliminates common Fixer failure mode
    - Makes demos more reliable
    - Catches security issues early
    """
    
    KNOWN_SAFE: Dict[str, str] = {
        "react": "^18.2.0", "react-dom": "^18.2.0", "next": "^14.0.0",
        "zustand": "^4.4.0", "jotai": "^2.5.0", "@tanstack/react-query": "^5.0.0",
        "tailwindcss": "^3.3.0", "lodash": "^4.17.21", "date-fns": "^2.30.0",
        "zod": "^3.22.0", "axios": "^1.6.0", "react-hook-form": "^7.48.0",
        "lucide-react": "^0.294.0", "pydantic": "^2.0.0", "fastapi": "^0.104.0",
        "langchain": "^0.1.0", "langchain-core": "^0.1.0", "langgraph": "^1.0.0",
    }
    
    BLOCKED_PACKAGES: Set[str] = {
        "event-stream", "flatmap-stream", "electron-native-notify",
        "cross-env-shell", "mongose", "babelcli", "crossenv", "d3.js",
    }
    
    NEEDS_REVIEW_PATTERNS: List[str] = [
        r".*-native.*", r".*crypto.*", r".*password.*",
        r".*auth.*", r".*payment.*", r".*stripe.*",
    ]
    
    def __init__(self, ecosystem: str = "npm"):
        self.ecosystem = ecosystem
    
    def check(self, package: str, version: Optional[str] = None) -> DependencyCheckResult:
        """Check if a dependency is allowed."""
        package_lower = package.lower().strip()
        
        if package_lower in self.BLOCKED_PACKAGES:
            return DependencyCheckResult(
                package=package, version=version,
                status=DependencyStatus.BLOCKED,
                reason="Package is in blocked list",
                alternatives=self._get_alternatives(package_lower)
            )
        
        if package_lower in self.KNOWN_SAFE:
            return DependencyCheckResult(
                package=package,
                version=version or self.KNOWN_SAFE[package_lower],
                status=DependencyStatus.ALLOWED,
                reason="Package is in known-safe list",
                alternatives=[]
            )
        
        for pattern in self.NEEDS_REVIEW_PATTERNS:
            if re.match(pattern, package_lower):
                return DependencyCheckResult(
                    package=package, version=version,
                    status=DependencyStatus.NEEDS_REVIEW,
                    reason=f"Package matches sensitive pattern: {pattern}",
                    alternatives=[]
                )
        
        return DependencyCheckResult(
            package=package, version=version,
            status=DependencyStatus.UNKNOWN,
            reason="Package not in known lists",
            alternatives=[]
        )
    
    def check_many(self, packages: List[str]) -> Dict[str, DependencyCheckResult]:
        """Check multiple packages at once."""
        return {pkg: self.check(pkg) for pkg in packages}
    
    def is_hallucinated(self, package: str) -> bool:
        """Quick check if a package is likely hallucinated."""
        package_lower = package.lower()
        if package_lower in self.KNOWN_SAFE or package_lower in self.BLOCKED_PACKAGES:
            return False
        
        hallucination_patterns = [
            r"^react-[a-z]+-component$",
            r"^use-[a-z]+$",
            r"^python-[a-z]+$",
        ]
        return any(re.match(p, package_lower) for p in hallucination_patterns)
    
    def _get_alternatives(self, blocked_package: str) -> List[str]:
        alternatives = {
            "mongose": ["mongoose"], "babelcli": ["@babel/cli"],
            "crossenv": ["cross-env"], "d3.js": ["d3"],
        }
        return alternatives.get(blocked_package, [])
