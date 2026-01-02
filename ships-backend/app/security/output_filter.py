"""
Output Filter

Detects system prompt leakage and sensitive data in LLM responses.
Redacts or warns about suspicious content.
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
import logging

from app.security.patterns import get_compiled_patterns

logger = logging.getLogger("ships.security")


@dataclass
class FilterResult:
    """Result of output filtering."""
    original_output: str
    filtered_output: str
    was_modified: bool
    detected_issues: List[str] = field(default_factory=list)
    redacted_count: int = 0
    risk_level: str = "NONE"
    
    def to_dict(self) -> dict:
        return {
            "was_modified": self.was_modified,
            "detected_issues": self.detected_issues,
            "redacted_count": self.redacted_count,
            "risk_level": self.risk_level,
        }


# Patterns that indicate system prompt leakage
LEAKAGE_INDICATORS = [
    (r"my\s+(system\s+)?instructions?\s+(are|is|say)", "System instruction disclosure", 10),
    (r"i\s+(was|am)\s+(told|instructed|programmed)\s+to", "Programming disclosure", 8),
    (r"my\s+(initial|original)\s+prompt\s+(was|is|says?)", "Prompt disclosure", 10),
    (r"here\s+(is|are)\s+my\s+(system\s+)?(prompt|instructions?)", "Direct prompt leak", 10),
    (r"the\s+system\s+prompt\s+(says?|states?|is)", "System prompt reference", 9),
]

_COMPILED_LEAKAGE = [(re.compile(p, re.IGNORECASE), d, s) for p, d, s in LEAKAGE_INDICATORS]


class OutputFilter:
    """
    Filters LLM output for sensitive information leakage.
    
    Features:
    - System prompt leakage detection
    - Sensitive data redaction (API keys, passwords)
    - Risk assessment
    - Audit logging
    """
    
    def __init__(self, redact_sensitive: bool = True, log_leaks: bool = True):
        self.redact_sensitive = redact_sensitive
        self.log_leaks = log_leaks
        self._sensitive_patterns = get_compiled_patterns("sensitive")
    
    def filter(self, llm_output: str) -> FilterResult:
        """
        Filter LLM output for leakage and sensitive data.
        
        Args:
            llm_output: Raw LLM response
            
        Returns:
            FilterResult with filtered output and metadata
        """
        if not llm_output:
            return FilterResult(
                original_output="",
                filtered_output="",
                was_modified=False
            )
        
        filtered = llm_output
        detected_issues = []
        redacted_count = 0
        max_severity = 0
        
        # Step 1: Check for system prompt leakage
        for pattern, description, severity in _COMPILED_LEAKAGE:
            if pattern.search(filtered):
                detected_issues.append(f"[LEAK] {description}")
                max_severity = max(max_severity, severity)
        
        # Step 2: Redact sensitive data
        if self.redact_sensitive:
            for pattern, description, severity in self._sensitive_patterns:
                matches = pattern.findall(filtered)
                if matches:
                    filtered = pattern.sub("[REDACTED]", filtered)
                    redacted_count += len(matches)
                    detected_issues.append(f"[SENSITIVE] {description} ({len(matches)} instances)")
                    max_severity = max(max_severity, severity)
        
        # Step 3: Calculate risk level
        if max_severity >= 8:
            risk_level = "HIGH"
        elif max_severity >= 5:
            risk_level = "MEDIUM"
        elif max_severity > 0:
            risk_level = "LOW"
        else:
            risk_level = "NONE"
        
        was_modified = filtered != llm_output
        
        # Step 4: Log if issues detected
        if detected_issues and self.log_leaks:
            logger.warning(
                f"[SECURITY] Output filter detected issues. "
                f"Risk: {risk_level}, Issues: {detected_issues}"
            )
        
        return FilterResult(
            original_output=llm_output,
            filtered_output=filtered,
            was_modified=was_modified,
            detected_issues=detected_issues,
            redacted_count=redacted_count,
            risk_level=risk_level
        )
    
    def check_for_leakage(self, output: str) -> Tuple[bool, List[str]]:
        """
        Quick check for system prompt leakage.
        
        Returns:
            Tuple of (has_leakage, list of detected patterns)
        """
        detected = []
        for pattern, description, _ in _COMPILED_LEAKAGE:
            if pattern.search(output):
                detected.append(description)
        return len(detected) > 0, detected


# Singleton instance
_default_filter: Optional[OutputFilter] = None


def get_filter() -> OutputFilter:
    """Get or create default filter instance."""
    global _default_filter
    if _default_filter is None:
        _default_filter = OutputFilter()
    return _default_filter


def filter_output(llm_output: str) -> FilterResult:
    """Convenience function to filter output with default settings."""
    return get_filter().filter(llm_output)
