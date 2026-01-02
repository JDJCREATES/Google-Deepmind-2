"""
Attack Pattern Database

Regex patterns for detecting prompt injection and system prompt extraction attempts.
Based on OWASP Top 10 LLM 2025 and real-world attack patterns.
"""

import re
from typing import List, Tuple

# =============================================================================
# PROMPT INJECTION PATTERNS
# =============================================================================

INJECTION_PATTERNS: List[Tuple[str, str, int]] = [
    # (pattern, description, severity 1-10)
    
    # Direct instruction override attempts
    (r"ignore\s+(all\s+)?(previous|prior|above|earlier)\s+(instructions?|prompts?|rules?|context)", 
     "Instruction override attempt", 9),
    (r"disregard\s+(all\s+)?(previous|prior|above)\s+(instructions?|prompts?)", 
     "Instruction disregard attempt", 9),
    (r"forget\s+(everything|all|what)\s+(you|i)\s+(told|said|know)", 
     "Memory wipe attempt", 8),
    (r"you\s+are\s+now\s+(a|an)\s+\w+", 
     "Role reassignment attempt", 7),
    (r"new\s+instructions?:?\s*", 
     "New instruction injection", 8),
    (r"override\s+(your\s+)?(instructions?|programming|directives?)", 
     "Override directive", 9),
    
    # Jailbreak patterns
    (r"(dan|developer)\s+mode", 
     "DAN jailbreak attempt", 10),
    (r"pretend\s+(you|to)\s+(are|be|have)\s+no\s+(restrictions?|limits?|rules?)", 
     "Restriction bypass attempt", 9),
    (r"act\s+as\s+if\s+(you\s+)?(have|had)\s+no\s+(rules?|restrictions?|limits?)", 
     "Behavior modification attempt", 9),
    (r"roleplay\s+as\s+(an?\s+)?unrestricted", 
     "Unrestricted roleplay attempt", 8),
    (r"jailbreak", 
     "Explicit jailbreak keyword", 10),
    
    # Code injection via prompts
    (r"execute\s+(this|the\s+following)\s+(code|command|script)", 
     "Code execution request", 7),
    (r"run\s+(this|the)\s+(shell|bash|cmd)\s+command", 
     "Shell command injection", 8),
    (r"```\s*(bash|sh|cmd|powershell|exec)\s*\n.*\n```", 
     "Embedded shell command", 6),
]

# =============================================================================
# SYSTEM PROMPT EXTRACTION PATTERNS
# =============================================================================

EXTRACTION_PATTERNS: List[Tuple[str, str, int]] = [
    # Direct extraction attempts
    (r"(show|reveal|display|print|output|tell\s+me)\s+(your\s+)?(system\s+)?(prompt|instructions?|rules?|guidelines?)", 
     "Direct prompt extraction attempt", 10),
    (r"what\s+(are|is)\s+your\s+(system\s+)?(prompt|instructions?|initial\s+instructions?)", 
     "Prompt inquiry", 9),
    (r"repeat\s+(your\s+)?(initial|original|system)\s+(prompt|instructions?|message)", 
     "Prompt repetition request", 9),
    (r"(copy|paste|echo)\s+(your\s+)?(system|initial)\s+(prompt|instructions?)", 
     "Prompt echo request", 9),
    
    # Indirect extraction
    (r"what\s+were\s+you\s+told\s+(to\s+do|before\s+this)", 
     "Indirect prompt extraction", 8),
    (r"(summarize|describe)\s+(your\s+)?(guidelines?|restrictions?|limitations?)", 
     "Guideline summary request", 7),
    (r"how\s+(are|were)\s+you\s+(programmed|instructed|configured)", 
     "Configuration inquiry", 7),
    (r"what\s+(can|can't|cannot)\s+you\s+(do|tell\s+me)", 
     "Capability probing", 5),
    
    # Sneaky extraction via encoding
    (r"(encode|base64|hex|rot13)\s+(your\s+)?(system\s+)?prompt", 
     "Encoded extraction attempt", 10),
    (r"translate\s+(your\s+)?prompt\s+to\s+\w+", 
     "Translation extraction attempt", 8),
]

# =============================================================================
# DATA EXFILTRATION PATTERNS  
# =============================================================================

EXFILTRATION_PATTERNS: List[Tuple[str, str, int]] = [
    (r"(send|post|transmit|upload)\s+(this|the|my)\s+(data|info|information)\s+to", 
     "Data transmission request", 8),
    (r"(fetch|get|retrieve)\s+from\s+(https?://|ftp://)", 
     "External fetch request", 7),
    (r"curl|wget|fetch\s+https?://", 
     "HTTP request attempt", 7),
]

# =============================================================================
# SENSITIVE DATA PATTERNS (for output filtering)
# =============================================================================

SENSITIVE_OUTPUT_PATTERNS: List[Tuple[str, str, int]] = [
    # API Keys and tokens
    (r"(api[_-]?key|apikey)\s*[:=]\s*['\"]?[\w\-]{20,}['\"]?", 
     "API key exposure", 10),
    (r"(bearer|token)\s+[\w\-\.]{20,}", 
     "Bearer token exposure", 10),
    (r"(sk|pk)[-_](live|test)[-_][\w]{20,}", 
     "Stripe key exposure", 10),
    (r"(ghp|gho|ghu|ghs|ghr)_[\w]{36,}", 
     "GitHub token exposure", 10),
    (r"xox[baprs]-[\w\-]{10,}", 
     "Slack token exposure", 10),
    
    # Passwords and secrets
    (r"password\s*[:=]\s*['\"]?[^\s'\"]{8,}['\"]?", 
     "Password exposure", 10),
    (r"(secret|private[_-]?key)\s*[:=]\s*['\"]?[\w\-]{16,}['\"]?", 
     "Secret key exposure", 10),
    
    # Connection strings
    (r"(postgres|mysql|mongodb)://[\w:@\.\-/]+", 
     "Database connection string", 9),
    (r"redis://[\w:@\.\-/]+", 
     "Redis connection string", 9),
]

# =============================================================================
# COMPILED PATTERNS (for performance)
# =============================================================================

_COMPILED_INJECTION = [(re.compile(p, re.IGNORECASE), d, s) for p, d, s in INJECTION_PATTERNS]
_COMPILED_EXTRACTION = [(re.compile(p, re.IGNORECASE), d, s) for p, d, s in EXTRACTION_PATTERNS]
_COMPILED_EXFILTRATION = [(re.compile(p, re.IGNORECASE), d, s) for p, d, s in EXFILTRATION_PATTERNS]
_COMPILED_SENSITIVE = [(re.compile(p, re.IGNORECASE), d, s) for p, d, s in SENSITIVE_OUTPUT_PATTERNS]


def get_compiled_patterns(category: str):
    """Get compiled patterns for a category."""
    mapping = {
        "injection": _COMPILED_INJECTION,
        "extraction": _COMPILED_EXTRACTION,
        "exfiltration": _COMPILED_EXFILTRATION,
        "sensitive": _COMPILED_SENSITIVE,
    }
    return mapping.get(category, [])
