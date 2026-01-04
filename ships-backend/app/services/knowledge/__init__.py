"""
Knowledge service package.

Collective Intelligence system for capturing and retrieving
proven solutions from past successful fixes.
"""

from app.services.knowledge.capture import (
    capture_successful_fix,
    record_failure,
)
from app.services.knowledge.retrieval import (
    retrieve_relevant_knowledge,
    format_suggestions_for_prompt,
    KnowledgeSuggestion,
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
from app.services.knowledge.integration import KnowledgeIntegration

__all__ = [
    # Integration
    "KnowledgeIntegration",
    # Capture
    "capture_successful_fix",
    "record_failure",
    # Retrieval
    "retrieve_relevant_knowledge",
    "format_suggestions_for_prompt",
    "KnowledgeSuggestion",
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
