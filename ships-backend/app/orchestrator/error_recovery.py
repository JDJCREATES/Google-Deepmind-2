"""
ShipS* Error Recovery System

Determines recovery strategy based on error type with:
- Smart retries for auto-fixable errors
- Clear escalation paths for user intervention
- Actionable error messages and options

Error Categories:
1. Auto-fixable (retry 3x): TODOs, imports, type errors
2. Sometimes fixable (retry 2x): build failures, contract mismatches
3. Rarely fixable (retry 1x): breaking changes, circular deps
4. Never auto-fix (immediate escalation): ambiguous requests, missing input
"""

from enum import Enum
from datetime import datetime
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass, field
from pydantic import BaseModel, Field


class ErrorType(str, Enum):
    """Types of errors that can occur during orchestration."""
    # Category 1: Auto-fixable (always retry)
    VALIDATION_FAILED = "VALIDATION_FAILED"
    IMPORT_ERROR = "IMPORT_ERROR"
    TYPE_MISMATCH = "TYPE_MISMATCH"
    TODO_FOUND = "TODO_FOUND"
    
    # Category 2: Sometimes fixable (limited retry)
    BUILD_FAILED = "BUILD_FAILED"
    CONTRACT_MISMATCH = "CONTRACT_MISMATCH"
    
    # Category 3: Rarely fixable (one retry)
    BREAKING_CHANGE = "BREAKING_CHANGE"
    CIRCULAR_DEPENDENCY = "CIRCULAR_DEPENDENCY"
    
    # Category 4: Never auto-fix
    AMBIGUOUS_REQUEST = "AMBIGUOUS_REQUEST"
    MISSING_BLUEPRINT = "MISSING_BLUEPRINT"
    MISSING_INPUT = "MISSING_INPUT"
    TIMEOUT = "TIMEOUT"
    UNKNOWN = "UNKNOWN"


class RecoveryStrategy(str, Enum):
    """Strategies for error recovery."""
    FIX_AND_RETRY = "FIX_AND_RETRY"
    ANALYZE_AND_FIX = "ANALYZE_AND_FIX"
    SYNC_AND_RETRY = "SYNC_AND_RETRY"
    REVERT_OR_UPDATE = "REVERT_OR_UPDATE"
    REFACTOR_REQUIRED = "REFACTOR_REQUIRED"
    CLARIFY_WITH_USER = "CLARIFY_WITH_USER"
    REQUEST_INPUT = "REQUEST_INPUT"
    ESCALATE = "ESCALATE"


class RecoveryStatus(str, Enum):
    """Status of recovery attempt."""
    RECOVERED = "RECOVERED"
    RETRY = "RETRY"
    ESCALATED = "ESCALATED"
    FAILED = "FAILED"


@dataclass
class UserOption:
    """An option presented to the user for error resolution."""
    action: str
    label: str
    description: str = ""
    is_recommended: bool = False


@dataclass
class RecoveryResult:
    """Result of a recovery attempt."""
    status: RecoveryStatus
    error_type: ErrorType
    message: str
    attempts: int = 0
    options: List[UserOption] = field(default_factory=list)
    artifacts: List[str] = field(default_factory=list)
    fix_applied: Optional[str] = None


@dataclass
class ErrorRecoveryConfig:
    """Configuration for error recovery."""
    strategy: RecoveryStrategy
    max_attempts: int
    agent: str
    escalate_after: int
    escalate_immediately: bool = False
    user_decision_required: bool = False
    reason: str = ""


class ErrorRecoverySystem:
    """
    Determines recovery strategy based on error type.
    
    This system:
    - Categorizes errors by fixability
    - Tracks retry attempts
    - Routes to appropriate fix agents
    - Escalates to user with clear options
    """
    
    # Recovery strategies per error type
    RECOVERY_CONFIGS: Dict[ErrorType, ErrorRecoveryConfig] = {
        # Category 1: Auto-fixable (always retry up to 3x)
        ErrorType.VALIDATION_FAILED: ErrorRecoveryConfig(
            strategy=RecoveryStrategy.FIX_AND_RETRY,
            max_attempts=3,
            agent="Fixer",
            escalate_after=3
        ),
        ErrorType.IMPORT_ERROR: ErrorRecoveryConfig(
            strategy=RecoveryStrategy.FIX_AND_RETRY,
            max_attempts=3,
            agent="Dependency Resolver",
            escalate_after=3
        ),
        ErrorType.TYPE_MISMATCH: ErrorRecoveryConfig(
            strategy=RecoveryStrategy.FIX_AND_RETRY,
            max_attempts=3,
            agent="Fixer",
            escalate_after=3
        ),
        ErrorType.TODO_FOUND: ErrorRecoveryConfig(
            strategy=RecoveryStrategy.FIX_AND_RETRY,
            max_attempts=3,
            agent="Fixer",
            escalate_after=3
        ),
        
        # Category 2: Sometimes fixable (limited retry)
        ErrorType.BUILD_FAILED: ErrorRecoveryConfig(
            strategy=RecoveryStrategy.ANALYZE_AND_FIX,
            max_attempts=2,
            agent="Fixer",
            escalate_after=2
        ),
        ErrorType.CONTRACT_MISMATCH: ErrorRecoveryConfig(
            strategy=RecoveryStrategy.SYNC_AND_RETRY,
            max_attempts=2,
            agent="Contract Validator",
            escalate_after=2
        ),
        
        # Category 3: Rarely fixable (one retry, then escalate)
        ErrorType.BREAKING_CHANGE: ErrorRecoveryConfig(
            strategy=RecoveryStrategy.REVERT_OR_UPDATE,
            max_attempts=1,
            agent="Integration Agent",
            escalate_after=1,
            user_decision_required=True
        ),
        ErrorType.CIRCULAR_DEPENDENCY: ErrorRecoveryConfig(
            strategy=RecoveryStrategy.REFACTOR_REQUIRED,
            max_attempts=1,
            agent="Integration Agent",
            escalate_after=1,
            user_decision_required=True
        ),
        
        # Category 4: Never auto-fix (immediate escalation)
        ErrorType.AMBIGUOUS_REQUEST: ErrorRecoveryConfig(
            strategy=RecoveryStrategy.CLARIFY_WITH_USER,
            max_attempts=0,
            agent="",
            escalate_after=0,
            escalate_immediately=True
        ),
        ErrorType.MISSING_BLUEPRINT: ErrorRecoveryConfig(
            strategy=RecoveryStrategy.REQUEST_INPUT,
            max_attempts=0,
            agent="",
            escalate_after=0,
            escalate_immediately=True
        ),
        ErrorType.MISSING_INPUT: ErrorRecoveryConfig(
            strategy=RecoveryStrategy.REQUEST_INPUT,
            max_attempts=0,
            agent="",
            escalate_after=0,
            escalate_immediately=True
        ),
        ErrorType.TIMEOUT: ErrorRecoveryConfig(
            strategy=RecoveryStrategy.ESCALATE,
            max_attempts=0,
            agent="",
            escalate_after=0,
            escalate_immediately=True,
            reason="Operation took too long"
        ),
        ErrorType.UNKNOWN: ErrorRecoveryConfig(
            strategy=RecoveryStrategy.ESCALATE,
            max_attempts=0,
            agent="",
            escalate_after=0,
            escalate_immediately=True,
            reason="Unknown error type"
        ),
    }
    
    # Error message templates
    MESSAGE_TEMPLATES: Dict[ErrorType, str] = {
        ErrorType.VALIDATION_FAILED: """
Code validation failed after {attempts} attempt(s).

Issues found:
{issues}

What happened:
{explanation}

Suggested actions:
1. Review the validation report
2. Manually fix the issues
3. Or adjust validation rules if they're too strict
""".strip(),
        
        ErrorType.BREAKING_CHANGE: """
The requested change would break existing code.

Impact: {impact}

Affected files:
{affected_files}

Options:
1. Update all affected files (may be risky)
2. Revert this change and try a different approach
3. Manually review and decide
""".strip(),
        
        ErrorType.AMBIGUOUS_REQUEST: """
I need more information to proceed.

Your request: "{request}"

What's unclear:
{ambiguities}

Please clarify:
{questions}
""".strip(),
        
        ErrorType.BUILD_FAILED: """
Build failed after {attempts} attempt(s).

Error: {error}

Build log excerpt:
{log_excerpt}
""".strip(),
        
        ErrorType.CIRCULAR_DEPENDENCY: """
Circular dependency detected.

Cycle: {cycle}

This requires refactoring to resolve.
""".strip(),
    }
    
    # User options per error type
    USER_OPTIONS: Dict[ErrorType, List[UserOption]] = {
        ErrorType.VALIDATION_FAILED: [
            UserOption("manual_fix", "Let me fix it manually", is_recommended=True),
            UserOption("retry", "Try again with adjusted rules"),
            UserOption("skip_validation", "Skip this validation (not recommended)"),
        ],
        ErrorType.BREAKING_CHANGE: [
            UserOption("update_dependents", "Update all affected files automatically"),
            UserOption("revert", "Revert this change"),
            UserOption("review", "Show me the changes and let me decide", is_recommended=True),
        ],
        ErrorType.BUILD_FAILED: [
            UserOption("view_logs", "Show me the build logs"),
            UserOption("retry", "Try building again"),
            UserOption("reset", "Start over with this feature"),
        ],
        ErrorType.AMBIGUOUS_REQUEST: [
            UserOption("clarify", "Let me clarify", is_recommended=True),
        ],
        ErrorType.MISSING_BLUEPRINT: [
            UserOption("provide_blueprint", "I'll provide the blueprint", is_recommended=True),
            UserOption("generate", "Generate a basic blueprint for me"),
        ],
    }
    
    def __init__(self):
        """Initialize error recovery system."""
        self._attempt_counts: Dict[str, int] = {}
    
    def get_config(self, error_type: ErrorType) -> ErrorRecoveryConfig:
        """Get recovery config for error type."""
        return self.RECOVERY_CONFIGS.get(
            error_type,
            self.RECOVERY_CONFIGS[ErrorType.UNKNOWN]
        )
    
    def record_attempt(self, error_id: str) -> int:
        """Record a recovery attempt and return new count."""
        if error_id not in self._attempt_counts:
            self._attempt_counts[error_id] = 0
        self._attempt_counts[error_id] += 1
        return self._attempt_counts[error_id]
    
    def get_attempts(self, error_id: str) -> int:
        """Get attempt count for an error."""
        return self._attempt_counts.get(error_id, 0)
    
    def reset_attempts(self, error_id: str) -> None:
        """Reset attempt count (after success)."""
        self._attempt_counts[error_id] = 0
    
    def handle_error(
        self,
        error_type: ErrorType,
        error_id: str,
        context: Dict[str, Any]
    ) -> RecoveryResult:
        """
        Route error to appropriate recovery strategy.
        
        Args:
            error_type: Type of error
            error_id: Unique identifier for this error (for tracking attempts)
            context: Error context (issues, affected_files, etc.)
            
        Returns:
            RecoveryResult with status and action
        """
        config = self.get_config(error_type)
        attempts = self.get_attempts(error_id)
        
        # Check if immediate escalation
        if config.escalate_immediately:
            return self._escalate(error_type, context, config, attempts)
        
        # Check attempt count
        if attempts >= config.max_attempts:
            return self._escalate(error_type, context, config, attempts)
        
        # Record this attempt
        self.record_attempt(error_id)
        
        # Route to recovery strategy
        return self._attempt_recovery(error_type, error_id, context, config, attempts + 1)
    
    def _attempt_recovery(
        self,
        error_type: ErrorType,
        error_id: str,
        context: Dict[str, Any],
        config: ErrorRecoveryConfig,
        attempts: int
    ) -> RecoveryResult:
        """Execute recovery strategy."""
        return RecoveryResult(
            status=RecoveryStatus.RETRY,
            error_type=error_type,
            message=f"Attempting fix with {config.agent} (attempt {attempts}/{config.max_attempts})",
            attempts=attempts,
            fix_applied=config.agent
        )
    
    def _escalate(
        self,
        error_type: ErrorType,
        context: Dict[str, Any],
        config: ErrorRecoveryConfig,
        attempts: int
    ) -> RecoveryResult:
        """Escalate to user with clear explanation and options."""
        message = self._build_message(error_type, context, attempts)
        options = self.USER_OPTIONS.get(error_type, [
            UserOption("view_details", "Show me more details"),
            UserOption("abort", "Stop and let me fix this"),
        ])
        
        return RecoveryResult(
            status=RecoveryStatus.ESCALATED,
            error_type=error_type,
            message=message,
            attempts=attempts,
            options=list(options),
            artifacts=context.get("artifacts", [])
        )
    
    def _build_message(
        self,
        error_type: ErrorType,
        context: Dict[str, Any],
        attempts: int
    ) -> str:
        """Build user-facing error message."""
        template = self.MESSAGE_TEMPLATES.get(
            error_type,
            "An error occurred: {error}"
        )
        
        # Add attempts to context
        context_with_attempts = {**context, "attempts": attempts}
        
        try:
            return template.format(**context_with_attempts)
        except KeyError:
            # Missing context variables, return generic message
            return f"Error: {error_type.value}. {context.get('error', 'Unknown error')}"
    
    def mark_recovered(self, error_id: str) -> None:
        """Mark an error as recovered (resets attempts)."""
        self.reset_attempts(error_id)
    
    def get_summary(self) -> Dict[str, int]:
        """Get summary of attempt counts."""
        return self._attempt_counts.copy()
