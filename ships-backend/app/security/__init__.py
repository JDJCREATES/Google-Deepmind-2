"""
ShipS* Security Module

Provides defense layers against prompt injection and system prompt extraction.
"""

from app.security.input_sanitizer import InputSanitizer, sanitize_input
from app.security.output_filter import OutputFilter, filter_output
from app.security.patterns import INJECTION_PATTERNS, EXTRACTION_PATTERNS

__all__ = [
    "InputSanitizer",
    "sanitize_input",
    "OutputFilter", 
    "filter_output",
    "INJECTION_PATTERNS",
    "EXTRACTION_PATTERNS",
]
