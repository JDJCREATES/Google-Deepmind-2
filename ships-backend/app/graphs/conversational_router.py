"""
Conversational Router - Fast-Path for Non-Engineering Queries
==============================================================

Handles routing for conversational interactions that don't require
the full engineering pipeline (Planner → Coder → Validator).

Design Philosophy:
- Questions → Chatter (read-only, fast answers)
- Confirmations → Context-aware continuation
- Unclear → Clarification prompts
- Engineering tasks → DeterministicRouter

This module prevents "calling a construction crew to change a lightbulb"
by providing express routes for simple queries.

Usage:
    router = ConversationalRouter()
    decision = router.route(state, structured_intent)
    
    if decision.is_fast_path:
        # Use fast-path routing
        next_phase = decision.next_phase
    else:
        # Fall through to DeterministicRouter
        pass
"""

from typing import Dict, Any, Optional, Literal
from dataclasses import dataclass
from app.core.logger import get_logger

logger = get_logger("conversational_router")


# Valid fast-path phases
FastPathPhase = Literal[
    "chat_setup",     # Route to conversational agent
    "coder",          # Continue with existing plan
    "planner",        # Need clarification/planning
    "fallthrough"     # Not a fast-path, use DeterministicRouter
]


@dataclass
class ConversationalDecision:
    """Result of conversational routing."""
    next_phase: FastPathPhase
    is_fast_path: bool
    reason: str
    metadata: Dict[str, Any]


class ConversationalRouter:
    """
    Fast-path router for conversational queries.
    
    Routes questions, confirmations, and unclear requests to appropriate handlers
    WITHOUT invoking the heavy engineering pipeline.
    """
    
    def __init__(self):
        """Initialize conversational router."""
        pass
    
    def route(
        self, 
        state: Dict[str, Any], 
        structured_intent: Optional[Dict[str, Any]] = None
    ) -> ConversationalDecision:
        """
        Determine if request can take fast-path or needs full pipeline.
        
        Args:
            state: Current agent graph state
            structured_intent: Classified intent from IntentClassifier
            
        Returns:
            ConversationalDecision with routing info
        """
        if not structured_intent:
            logger.warning("[CONVERSATIONAL_ROUTER] No intent provided - falling through")
            return ConversationalDecision(
                next_phase="fallthrough",
                is_fast_path=False,
                reason="No intent available",
                metadata={}
            )
        
        task_type = structured_intent.get("task_type")
        action = structured_intent.get("action")
        is_ambiguous = structured_intent.get("is_ambiguous", False)
        confidence = structured_intent.get("confidence", 1.0)
        
        logger.info(
            f"[CONVERSATIONAL_ROUTER] Evaluating: task_type={task_type}, "
            f"action={action}, ambiguous={is_ambiguous}, confidence={confidence:.2f}"
        )
        
        # PRIORITY 1: Security check
        security_risk = structured_intent.get("security_risk_score", 0.0)
        if security_risk > 0.8:
            logger.warning(
                f"[CONVERSATIONAL_ROUTER] ⚠️ High security risk ({security_risk:.2f}) - "
                "routing to chat for safe response"
            )
            return ConversationalDecision(
                next_phase="chat_setup",
                is_fast_path=True,
                reason=f"Security risk detected ({security_risk:.2f})",
                metadata={
                    "security_risk_score": security_risk,
                    "warnings": structured_intent.get("security_warnings", [])
                }
            )
        
        # PRIORITY 2: Questions (read-only queries)
        if task_type == "question" and action == "explain":
            logger.info("[CONVERSATIONAL_ROUTER] ✅ Question detected → Chatter (fast-path)")
            return ConversationalDecision(
                next_phase="chat_setup",
                is_fast_path=True,
                reason="User asking question - routing to Chatter for read-only answer",
                metadata={"original_request": structured_intent.get("original_request")}
            )
        
        # PRIORITY 3: Analyze/Explain without modifications
        if action == "analyze" and task_type not in ["feature", "fix", "modify"]:
            logger.info("[CONVERSATIONAL_ROUTER] ✅ Analysis request → Chatter (fast-path)")
            return ConversationalDecision(
                next_phase="chat_setup",
                is_fast_path=True,
                reason="Analysis/explanation request - routing to Chatter",
                metadata={"task_type": task_type}
            )
        
        # PRIORITY 4: Unclear/Ambiguous requests
        if task_type == "unclear" or (is_ambiguous and confidence < 0.6):
            clarification_questions = structured_intent.get("clarification_questions", [])
            
            # If we have specific questions, route to Chatter to ask them
            if clarification_questions:
                logger.info(
                    f"[CONVERSATIONAL_ROUTER] ✅ Unclear request → Chatter for clarification "
                    f"({len(clarification_questions)} questions)"
                )
                return ConversationalDecision(
                    next_phase="chat_setup",
                    is_fast_path=True,
                    reason="Request unclear - routing to Chatter for clarification",
                    metadata={
                        "clarification_questions": clarification_questions,
                        "original_request": structured_intent.get("original_request")
                    }
                )
            else:
                # No specific questions - might need planning to understand scope
                logger.info("[CONVERSATIONAL_ROUTER] Unclear but no questions - routing to Planner")
                return ConversationalDecision(
                    next_phase="planner",
                    is_fast_path=True,
                    reason="Unclear request - routing to Planner for scope analysis",
                    metadata={"confidence": confidence}
                )
        
        # PRIORITY 5: Confirmations (context-aware)
        if task_type == "confirmation" or action == "proceed":
            artifacts = state.get("artifacts", {})
            
            # Check if there's a plan to confirm
            has_plan = bool(artifacts.get("plan") or artifacts.get("implementation_plan"))
            
            if has_plan:
                logger.info("[CONVERSATIONAL_ROUTER] ✅ Confirmation with plan → Continue to Coder")
                return ConversationalDecision(
                    next_phase="coder",
                    is_fast_path=True,
                    reason="User confirmed plan - proceeding to implementation",
                    metadata={"confirmed_plan": True}
                )
            else:
                # Confirmation without context - ask what they're confirming
                logger.info("[CONVERSATIONAL_ROUTER] Confirmation without context → Chatter")
                return ConversationalDecision(
                    next_phase="chat_setup",
                    is_fast_path=True,
                    reason="Confirmation without context - asking for clarification",
                    metadata={"missing_context": "no_plan"}
                )
        
        # PRIORITY 6: Hybrid requests (question + action)
        # If action involves code changes, prioritize engineering pipeline
        if action in ["create", "modify", "delete"] and task_type != "question":
            logger.info(
                f"[CONVERSATIONAL_ROUTER] Engineering action ({action}) detected - "
                "falling through to DeterministicRouter"
            )
            return ConversationalDecision(
                next_phase="fallthrough",
                is_fast_path=False,
                reason=f"Engineering task ({task_type}/{action}) - needs full pipeline",
                metadata={"task_type": task_type, "action": action}
            )
        
        # DEFAULT: Fall through to DeterministicRouter for engineering tasks
        logger.info(
            f"[CONVERSATIONAL_ROUTER] No fast-path match - falling through "
            f"(task_type={task_type}, action={action})"
        )
        return ConversationalDecision(
            next_phase="fallthrough",
            is_fast_path=False,
            reason=f"Standard engineering task - using DeterministicRouter",
            metadata={"task_type": task_type, "action": action}
        )
    
    def should_clear_intent_lock(self, task_type: str) -> bool:
        """
        Determine if intent_classified flag should be cleared after this task.
        
        Conversational tasks (questions, confirmations) should allow re-classification
        on the next user message. Engineering tasks should lock the intent.
        
        Args:
            task_type: The task type from structured_intent
            
        Returns:
            True if intent lock should be cleared, False to keep it locked
        """
        conversational_types = ["question", "confirmation", "unclear"]
        should_clear = task_type in conversational_types
        
        if should_clear:
            logger.debug(
                f"[CONVERSATIONAL_ROUTER] Will clear intent lock for conversational "
                f"task: {task_type}"
            )
        
        return should_clear


# Singleton instance for easy import
conversational_router = ConversationalRouter()
