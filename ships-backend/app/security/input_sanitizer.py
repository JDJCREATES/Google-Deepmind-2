"""
Input Sanitizer

Detects prompt injection and system prompt extraction attempts.
Returns sanitized input with risk metadata - does NOT reject.
"""

import re
import unicodedata
from dataclasses import dataclass, field
from typing import List, Tuple, Optional
import logging

from app.security.patterns import get_compiled_patterns

logger = logging.getLogger("ships.security")


@dataclass
class SanitizationResult:
    """Result of input sanitization."""
    original_input: str
    sanitized_input: str
    risk_score: float  # 0.0 to 1.0
    detected_patterns: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    is_suspicious: bool = False
    
    def to_dict(self) -> dict:
        return {
            "original_input": self.original_input[:100] + "..." if len(self.original_input) > 100 else self.original_input,
            "risk_score": self.risk_score,
            "detected_patterns": self.detected_patterns,
            "warnings": self.warnings,
            "is_suspicious": self.is_suspicious,
        }


class InputSanitizer:
    """
    Sanitizes user input for prompt injection attacks.
    
    Features:
    - Pattern-based injection detection
    - Risk scoring (0-1 scale)
    - Text normalization
    - Non-blocking (returns metadata, doesn't reject)
    """
    
    def __init__(self, log_suspicious: bool = True):
        self.log_suspicious = log_suspicious
        self._injection_patterns = get_compiled_patterns("injection")
        self._extraction_patterns = get_compiled_patterns("extraction")
        self._exfiltration_patterns = get_compiled_patterns("exfiltration")
    
    def sanitize(self, user_input: str) -> SanitizationResult:
        """
        Sanitize user input and detect injection attempts.
        
        Args:
            user_input: Raw user input
            
        Returns:
            SanitizationResult with sanitized text and risk metadata
        """
        if not user_input:
            return SanitizationResult(
                original_input="",
                sanitized_input="",
                risk_score=0.0
            )
        
        # Step 1: Normalize text
        normalized = self._normalize_text(user_input)
        
        # Step 2: Detect patterns
        detected = []
        total_severity = 0
        
        # Check injection patterns
        for pattern, description, severity in self._injection_patterns:
            if pattern.search(normalized):
                detected.append(f"[INJECTION] {description}")
                total_severity += severity
        
        # Check extraction patterns
        for pattern, description, severity in self._extraction_patterns:
            if pattern.search(normalized):
                detected.append(f"[EXTRACTION] {description}")
                total_severity += severity
        
        # Check exfiltration patterns
        for pattern, description, severity in self._exfiltration_patterns:
            if pattern.search(normalized):
                detected.append(f"[EXFIL] {description}")
                total_severity += severity
        
        # Step 3: Calculate risk score (0-1)
        # Max possible severity is ~100 (10 patterns at severity 10)
        risk_score = min(1.0, total_severity / 30.0)  # Normalize to 0-1
        is_suspicious = risk_score > 0.3 or len(detected) > 0
        
        # Step 4: Generate warnings
        warnings = []
        if risk_score > 0.7:
            warnings.append("High risk input detected - review recommended")
        elif risk_score > 0.3:
            warnings.append("Moderate risk input - patterns detected")
        
        # Step 5: Log if suspicious
        if is_suspicious and self.log_suspicious:
            logger.warning(
                f"[SECURITY] Suspicious input detected. "
                f"Risk: {risk_score:.2f}, Patterns: {detected}"
            )
        
        # Step 6: Return result (input is passed through, not blocked)
        return SanitizationResult(
            original_input=user_input,
            sanitized_input=normalized,
            risk_score=risk_score,
            detected_patterns=detected,
            warnings=warnings,
            is_suspicious=is_suspicious
        )
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text to catch obfuscation attempts."""
        # Remove zero-width characters
        text = re.sub(r'[\u200b\u200c\u200d\ufeff]', '', text)
        
        # Normalize unicode (e.g., 'ａ' -> 'a')
        text = unicodedata.normalize('NFKC', text)
        
        # Remove control characters (except newlines/tabs)
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
        
        # Collapse multiple spaces (but preserve newlines for code)
        text = re.sub(r' +', ' ', text)
        
        return text.strip()
    
    def get_risk_level(self, risk_score: float) -> str:
        """Convert risk score to human-readable level."""
        if risk_score >= 0.7:
            return "HIGH"
        elif risk_score >= 0.3:
            return "MEDIUM"
        elif risk_score > 0:
            return "LOW"
        return "NONE"


# Singleton instance
_default_sanitizer: Optional[InputSanitizer] = None


def get_sanitizer() -> InputSanitizer:
    """Get or create default sanitizer instance."""
    global _default_sanitizer
    if _default_sanitizer is None:
        _default_sanitizer = InputSanitizer()
    return _default_sanitizer


def sanitize_input(user_input: str) -> SanitizationResult:
    """Convenience function to sanitize input with default settings."""
    return get_sanitizer().sanitize(user_input)
