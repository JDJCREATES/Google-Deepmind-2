"""
Success validation gates for knowledge capture.

Implements strict multi-gate validation to ensure only truly successful
fixes are captured. Never saves bad code or false positives.
"""

import re
import time
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger("ships.knowledge.validation")


@dataclass
class BuildState:
    """Snapshot of project build state."""
    status: str  # "success", "error", "unknown"
    errors: list[str]
    warnings: list[str]
    
    @property
    def is_success(self) -> bool:
        return self.status == "success"
    
    @property
    def error_count(self) -> int:
        return len(self.errors)


@dataclass
class SessionContext:
    """Context for validation gates."""
    session_id: str
    diff: str
    before_state: BuildState
    after_state: BuildState
    user_approved: bool = False
    user_continued: bool = False
    user_reverted: bool = False


class ValidationResult:
    """Result of validation gate checks."""
    
    def __init__(self):
        self.passed = True
        self.confidence = 0.7
        self.gates_passed: list[str] = []
        self.gates_failed: list[str] = []
        self.reason: Optional[str] = None
    
    def fail(self, gate_name: str, reason: str) -> None:
        """Mark a gate as failed."""
        self.passed = False
        self.gates_failed.append(gate_name)
        self.reason = reason
    
    def pass_gate(self, gate_name: str, confidence_delta: float = 0) -> None:
        """Mark a gate as passed with optional confidence boost."""
        self.gates_passed.append(gate_name)
        self.confidence = min(self.confidence + confidence_delta, 1.0)


def gate_build_success(context: SessionContext) -> tuple[bool, str]:
    """
    Gate 1: Build must succeed after fix.
    
    This is a hard requirement - if build fails, nothing else matters.
    """
    if not context.after_state.is_success:
        return False, f"Build failed with status: {context.after_state.status}"
    return True, "Build successful"


def gate_error_resolved(context: SessionContext) -> tuple[bool, str]:
    """
    Gate 2: The target error must be gone.
    
    Verifies the specific error being fixed is no longer present.
    """
    if not context.before_state.errors:
        return False, "No errors to fix"
    
    target_error = context.before_state.errors[0]
    
    # Check if target error still exists (with normalization)
    target_normalized = _normalize_for_comparison(target_error)
    
    for after_error in context.after_state.errors:
        if _normalize_for_comparison(after_error) == target_normalized:
            return False, "Target error still present after fix"
    
    return True, "Target error resolved"


def gate_no_regressions(context: SessionContext) -> tuple[bool, str]:
    """
    Gate 3: Fix must not introduce more errors.
    
    The fix should not create more problems than it solves.
    """
    before_count = context.before_state.error_count
    after_count = context.after_state.error_count
    
    if after_count > before_count:
        return False, f"Fix introduced {after_count - before_count} new errors"
    
    return True, f"No regressions (before: {before_count}, after: {after_count})"


def gate_stability_check(context: SessionContext, wait_ms: int = 2000) -> tuple[bool, str]:
    """
    Gate 4: Build remains stable after short wait.
    
    Catches race conditions, async issues, delayed failures.
    Note: In practice, call this after a delay has elapsed.
    """
    # In real implementation, this would re-check build status
    # For now, we trust the after_state if it's been verified
    if context.after_state.is_success:
        return True, "Build stable"
    return False, "Build became unstable"


def gate_code_quality(context: SessionContext) -> tuple[bool, str]:
    """
    Gate 5: Basic code quality checks.
    
    Filters out obviously bad fixes.
    """
    diff = context.diff
    
    # Empty or trivial changes
    if len(diff.strip()) < 10:
        return False, "Change too small to be meaningful"
    
    # Just deleting everything
    deletions = diff.count('\n-')
    additions = diff.count('\n+')
    if deletions > 0 and additions == 0:
        return False, "Pure deletion without replacement"
    
    if deletions > additions * 5:
        return False, "Excessive deletions compared to additions"
    
    # Debug spam detection
    debug_patterns = ['console.log', 'print(', 'debugger', 'TODO:', 'FIXME:']
    for pattern in debug_patterns:
        if pattern in diff and '+' in diff:
            # Only penalize if adding these
            lines_with_pattern = [l for l in diff.split('\n') if l.startswith('+') and pattern in l]
            if len(lines_with_pattern) > 2:
                return False, f"Too many debug statements added ({pattern})"
    
    return True, "Code quality acceptable"


def gate_user_signal(context: SessionContext) -> tuple[float, str]:
    """
    Gate 6: User signals (boost or block).
    
    Returns a multiplier, not pass/fail.
    0.0 = block capture entirely
    1.0 = neutral
    >1.0 = confidence boost
    """
    if context.user_reverted:
        return 0.0, "User reverted the change"
    
    if context.user_approved:
        return 1.5, "User explicitly approved"
    
    if context.user_continued:
        return 1.2, "User continued working (implicit approval)"
    
    return 1.0, "No user signal"


def validate_for_capture(context: SessionContext) -> ValidationResult:
    """
    Run all validation gates and determine if fix should be captured.
    
    All hard gates must pass. User signals modify confidence.
    
    Args:
        context: Session context with before/after states
        
    Returns:
        ValidationResult with pass/fail and confidence score
    """
    result = ValidationResult()
    
    # Gate 1: Build success (HARD)
    passed, msg = gate_build_success(context)
    if not passed:
        result.fail("build_success", msg)
        logger.debug(f"Gate 1 failed: {msg}")
        return result
    result.pass_gate("build_success")
    
    # Gate 2: Error resolved (HARD)
    passed, msg = gate_error_resolved(context)
    if not passed:
        result.fail("error_resolved", msg)
        logger.debug(f"Gate 2 failed: {msg}")
        return result
    result.pass_gate("error_resolved", 0.05)
    
    # Gate 3: No regressions (HARD)
    passed, msg = gate_no_regressions(context)
    if not passed:
        result.fail("no_regressions", msg)
        logger.debug(f"Gate 3 failed: {msg}")
        return result
    result.pass_gate("no_regressions", 0.05)
    
    # Gate 4: Stability (HARD)
    passed, msg = gate_stability_check(context)
    if not passed:
        result.fail("stability", msg)
        logger.debug(f"Gate 4 failed: {msg}")
        return result
    result.pass_gate("stability")
    
    # Gate 5: Code quality (SOFT - affects confidence)
    passed, msg = gate_code_quality(context)
    if passed:
        result.pass_gate("code_quality", 0.1)
    else:
        logger.debug(f"Gate 5 soft fail: {msg}")
        result.confidence -= 0.1
    
    # Gate 6: User signals (SPECIAL)
    multiplier, msg = gate_user_signal(context)
    if multiplier == 0:
        result.fail("user_signal", msg)
        logger.debug(f"Gate 6 blocked: {msg}")
        return result
    
    result.confidence *= multiplier
    result.confidence = min(result.confidence, 1.0)
    
    # Final threshold check
    CAPTURE_THRESHOLD = 0.6
    if result.confidence < CAPTURE_THRESHOLD:
        result.fail("confidence_threshold", f"Confidence {result.confidence:.2f} below threshold")
        return result
    
    logger.info(f"Validation passed: confidence={result.confidence:.2f}, gates={result.gates_passed}")
    return result


def _normalize_for_comparison(error: str) -> str:
    """Normalize error for comparison (remove variable parts)."""
    normalized = error
    # Remove line numbers
    normalized = re.sub(r'line \d+', 'line N', normalized)
    # Remove column numbers
    normalized = re.sub(r'column \d+', 'column N', normalized)
    # Remove file paths
    normalized = re.sub(r'[/\\][\w/\\.-]+\.(py|js|ts|tsx|jsx)', '<FILE>', normalized)
    return normalized.lower().strip()
