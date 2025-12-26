"""
ShipS* Mini-Agents Package

Mini-agents are lightweight, specialized agents that use Gemini 3 Flash
for simple, focused tasks.
"""

from app.agents.mini_agents.intent_classifier import (
    IntentClassifier,
    StructuredIntent,
    TaskType,
    ActionType,
    TargetArea,
)

__all__ = [
    "IntentClassifier",
    "StructuredIntent",
    "TaskType",
    "ActionType",
    "TargetArea",
]
