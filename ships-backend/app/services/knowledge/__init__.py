"""
Knowledge service package.

Collective Intelligence system for capturing and retrieving
proven solutions from past successful fixes and patterns.
"""

from app.services.knowledge.capture import (
    capture_successful_fix,
    capture_successful_pattern,
    record_failure,
)
from app.services.knowledge.retrieval import (
    retrieve_relevant_knowledge,
    retrieve_for_fixer,
    retrieve_for_coder,
    format_suggestions_for_prompt,
    KnowledgeSuggestion,
    EntryType,
)
from app.services.knowledge.validation import (
    validate_for_capture,
    ValidationResult,
    SessionContext,
    BuildState,
)
from app.services.knowledge.normalization import (
    normalize_error,
    generate_error_signature,
    extract_tech_stack,
    extract_solution_pattern,
)
from app.services.knowledge.integration import (
    KnowledgeIntegration,
    FixerKnowledge,
    CoderKnowledge,
)
from app.services.knowledge.hooks import (
    capture_coder_pattern,
    capture_fixer_success,
)

__all__ = [
    # Agent-specific integration
    "FixerKnowledge",
    "CoderKnowledge",
    "KnowledgeIntegration",  # Legacy
    # Graph hooks
    "capture_coder_pattern",
    "capture_fixer_success",
    # Capture
    "capture_successful_fix",
    "capture_successful_pattern",
    "record_failure",
    # Retrieval
    "retrieve_relevant_knowledge",
    "retrieve_for_fixer",
    "retrieve_for_coder",
    "format_suggestions_for_prompt",
    "KnowledgeSuggestion",
    "EntryType",
    # Validation
    "validate_for_capture",
    "ValidationResult",
    "SessionContext",
    "BuildState",
    # Normalization
    "normalize_error",
    "generate_error_signature",
    "extract_tech_stack",
    "extract_solution_pattern",
]
