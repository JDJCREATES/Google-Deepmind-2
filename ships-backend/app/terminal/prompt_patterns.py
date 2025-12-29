"""
Prompt Patterns Module

Detects interactive prompts in terminal output and provides auto-responses.
This enables the agent to handle interactive commands without manual intervention.

Patterns are checked against the last N characters of output to detect prompts.
"""

import re
from dataclasses import dataclass
from typing import Optional, List, Callable
from enum import Enum
import logging

logger = logging.getLogger("ships.terminal")


class PromptType(Enum):
    """Types of interactive prompts."""
    YES_NO = "yes_no"           # Y/n, yes/no prompts
    CONFIRM = "confirm"          # Press Enter to confirm
    SELECT = "select"            # Select from options (1, 2, 3)
    INPUT = "input"              # Free text input required
    OVERWRITE = "overwrite"      # Overwrite existing files?
    UNKNOWN = "unknown"          # Unrecognized prompt


@dataclass
class PromptPattern:
    """
    A pattern for detecting interactive prompts.
    
    Attributes:
        name: Human-readable name for the prompt.
        pattern: Regex pattern to match the prompt.
        prompt_type: Type of prompt for categorization.
        auto_response: Response to send automatically (None = requires agent decision).
        priority: Higher priority patterns are checked first.
    """
    name: str
    pattern: re.Pattern
    prompt_type: PromptType
    auto_response: Optional[str] = None
    priority: int = 0


# ============================================================================
# KNOWN PROMPT PATTERNS
# ============================================================================

PROMPT_PATTERNS: List[PromptPattern] = [
    # === YES/NO Prompts ===
    PromptPattern(
        name="generic_y_n",
        pattern=re.compile(r"\(y/n\)\s*[:\?]?\s*$", re.IGNORECASE),
        prompt_type=PromptType.YES_NO,
        auto_response="y\n",
        priority=10
    ),
    PromptPattern(
        name="generic_yes_no",
        pattern=re.compile(r"\(yes/no\)\s*[:\?]?\s*$", re.IGNORECASE),
        prompt_type=PromptType.YES_NO,
        auto_response="yes\n",
        priority=10
    ),
    PromptPattern(
        name="npm_confirm",
        pattern=re.compile(r"Is this OK\?\s*\(yes\)\s*$", re.IGNORECASE),
        prompt_type=PromptType.CONFIRM,
        auto_response="\n",  # Just press Enter
        priority=15
    ),
    PromptPattern(
        name="proceed_y_n",
        pattern=re.compile(r"proceed\??\s*\(?y/n\)?\s*$", re.IGNORECASE),
        prompt_type=PromptType.YES_NO,
        auto_response="y\n",
        priority=10
    ),
    
    # === Overwrite Prompts ===
    PromptPattern(
        name="vite_overwrite",
        pattern=re.compile(r"Current directory is not empty.*Remove existing files.*\?\s*›?\s*$", re.IGNORECASE | re.DOTALL),
        prompt_type=PromptType.OVERWRITE,
        auto_response="y\n",
        priority=20
    ),
    PromptPattern(
        name="generic_overwrite",
        pattern=re.compile(r"overwrite\??\s*\(?y/n\)?\s*$", re.IGNORECASE),
        prompt_type=PromptType.OVERWRITE,
        auto_response="y\n",
        priority=15
    ),
    PromptPattern(
        name="file_exists",
        pattern=re.compile(r"already exists.*proceed\??\s*\(?y/n\)?\s*$", re.IGNORECASE | re.DOTALL),
        prompt_type=PromptType.OVERWRITE,
        auto_response="y\n",
        priority=15
    ),
    
    # === Confirm/Continue Prompts ===
    PromptPattern(
        name="press_enter",
        pattern=re.compile(r"press enter to continue|hit enter", re.IGNORECASE),
        prompt_type=PromptType.CONFIRM,
        auto_response="\n",
        priority=10
    ),
    PromptPattern(
        name="continue_question",
        pattern=re.compile(r"Do you want to continue\?\s*\[?Y/n\]?\s*$", re.IGNORECASE),
        prompt_type=PromptType.CONFIRM,
        auto_response="Y\n",
        priority=10
    ),
    
    # === Package Manager Specific ===
    PromptPattern(
        name="npm_init_name",
        pattern=re.compile(r"package name:?\s*\(.*\)\s*$", re.IGNORECASE),
        prompt_type=PromptType.CONFIRM,
        auto_response="\n",  # Accept default
        priority=15
    ),
    PromptPattern(
        name="npm_init_version",
        pattern=re.compile(r"version:?\s*\(.*\)\s*$", re.IGNORECASE),
        prompt_type=PromptType.CONFIRM,
        auto_response="\n",  # Accept default
        priority=15
    ),
    PromptPattern(
        name="npm_init_generic",
        pattern=re.compile(r"^\w+:?\s*\([^)]*\)\s*$", re.IGNORECASE | re.MULTILINE),
        prompt_type=PromptType.CONFIRM,
        auto_response="\n",  # Accept default
        priority=5
    ),
    
    # === Selection Prompts ===
    PromptPattern(
        name="select_framework",
        pattern=re.compile(r"Select a (framework|variant|template).*[:\?›]\s*$", re.IGNORECASE | re.DOTALL),
        prompt_type=PromptType.SELECT,
        auto_response=None,  # Requires context - agent must decide
        priority=20
    ),
    PromptPattern(
        name="arrow_select",
        pattern=re.compile(r"Use arrow keys.*›\s*$", re.IGNORECASE | re.DOTALL),
        prompt_type=PromptType.SELECT,
        auto_response="\n",  # Select first option
        priority=10
    ),
]


def detect_prompt(output: str, check_last_n_chars: int = 500) -> Optional[PromptPattern]:
    """
    Detect if the output ends with an interactive prompt.
    
    Args:
        output: Full terminal output.
        check_last_n_chars: Number of characters from the end to check.
        
    Returns:
        Matched PromptPattern if found, None otherwise.
    """
    if not output:
        return None
    
    # Only check the last N characters for efficiency
    tail = output[-check_last_n_chars:] if len(output) > check_last_n_chars else output
    
    # Sort by priority (higher first)
    sorted_patterns = sorted(PROMPT_PATTERNS, key=lambda p: p.priority, reverse=True)
    
    for pattern in sorted_patterns:
        if pattern.pattern.search(tail):
            logger.info(f"[PROMPT] Detected prompt: {pattern.name} (type: {pattern.prompt_type.value})")
            return pattern
    
    return None


def get_auto_response(prompt: PromptPattern) -> Optional[str]:
    """
    Get the auto-response for a detected prompt.
    
    Args:
        prompt: The detected prompt pattern.
        
    Returns:
        Response string to send, or None if agent must decide.
    """
    if prompt.auto_response is not None:
        logger.info(f"[PROMPT] Auto-responding to '{prompt.name}' with: {repr(prompt.auto_response)}")
        return prompt.auto_response
    
    logger.info(f"[PROMPT] Prompt '{prompt.name}' requires agent decision")
    return None


def is_waiting_for_input(output: str, timeout_seconds: float = 2.0) -> bool:
    """
    Heuristic check if the terminal is waiting for input.
    
    This is used when no known prompt is detected but the command
    hasn't produced output recently.
    
    Args:
        output: Current terminal output.
        timeout_seconds: How long since last output (provided by caller).
        
    Returns:
        True if likely waiting for input.
    """
    if not output:
        return False
    
    # Check for common prompt endings
    prompt_endings = [
        ": ",
        "? ",
        "> ",
        "› ",
        "$ ",
        "# ",
        ">>> ",  # Python REPL
        "... ",  # Python continuation
    ]
    
    tail = output.rstrip()[-10:] if output else ""
    return any(tail.endswith(end.strip()) for end in prompt_endings)
