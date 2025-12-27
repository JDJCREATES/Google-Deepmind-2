"""
ShipS* Mini-Agents Package

Mini-agents are lightweight, specialized agents that use Gemini 3 Flash
for simple, focused tasks. Also includes deterministic utilities:
- ContextSelector: Token budget filter
- DependencyResolver: Hallucination preventer
"""

from app.agents.mini_agents.intent_classifier import (
    IntentClassifier,
    StructuredIntent,
    TaskType,
    ActionType,
    TargetArea,
)

from app.agents.mini_agents.context_selector import (
    ContextSelector,
    ContextRelevance,
    ContextItem,
)

from app.agents.mini_agents.dependency_resolver import (
    DependencyResolver,
    DependencyStatus,
    DependencyCheckResult,
)

__all__ = [
    # Intent Classifier
    "IntentClassifier",
    "StructuredIntent",
    "TaskType",
    "ActionType",
    "TargetArea",
    
    # Context Selector
    "ContextSelector",
    "ContextRelevance",
    "ContextItem",
    
    # Dependency Resolver
    "DependencyResolver",
    "DependencyStatus",
    "DependencyCheckResult",
]
