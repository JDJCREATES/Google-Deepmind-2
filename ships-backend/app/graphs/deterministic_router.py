"""
Deterministic Router with Quality Gates
========================================

Production-grade routing system that replaces expensive LLM calls
with fast, deterministic state machine transitions.

Integrates with quality_gates.py for enforcement.

Design Philosophy:
- 95% of routing is deterministic (no LLM needed)
- Quality gates enforce invariants
- LLM only for ambiguous states (loops, escalations)
- Clear audit trail for all decisions

Usage:
    router = DeterministicRouter()
    decision = router.route(state)
    
    if decision.requires_llm:
        # Call LLM orchestrator
        result = await llm_orchestrator(state)
    else:
        # Use deterministic decision
        next_phase = decision.next_phase
"""

from typing import Dict, Any, Optional, Literal, Tuple
from dataclasses import dataclass, field
from app.core.logger import get_logger

logger = get_logger("deterministic_router")
from app.graphs.quality_gates import GateEvaluator, GateResult


# Valid routing phases (aligned with agent_graph.py)
RoutingPhase = Literal[
    "planning",      # Initial state - creating plan
    "planner",       # Route to planner node
    "coder",         # Route to coder node  
    "coding",        # Coding state
    "validator",     # Route to validator node
    "validating",    # Validating state
    "fixer",         # Route to fixer node
    "fixing",        # Fixing state
    "chat",          # User interaction
    "chat_setup",    # Chat initialization
    "complete",      # Success - all done
    "waiting",       # Waiting for locks to release
    "orchestrator"   # Escalation to LLM decision
]


@dataclass
class RoutingDecision:
    """Result of routing decision."""
    next_phase: RoutingPhase
    reason: str
    gate_result: Optional[GateResult] = None
    requires_llm: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


class DeterministicRouter:
    """
    Deterministic state machine router with quality gate integration.
    
    Implements the designed flow:
    planning → coding → validating → (pass → complete | fail → fixing → validating)
    
    Uses quality gates to enforce transitions.
    LLM only called for ambiguous states (5% of cases).
    """
    
    def __init__(self):
        self.gate_evaluator = GateEvaluator()
        
    def route(self, state: Dict[str, Any]) -> RoutingDecision:
        """
        Determine next phase based on current state.
        
        Args:
            state: Current agent graph state
            
        Returns:
            RoutingDecision with next phase and reasoning
        """
        current_phase = state.get("phase", "planning")
        
        logger.info(f"[DETERMINISTIC_ROUTER] Current phase: {current_phase}")
        
        # Handle special phases first
        if current_phase == "chat":
            return self._route_chat(state)
        
        if current_phase == "waiting":
            return self._route_waiting(state)
        
        if current_phase == "orchestrator":
            return self._route_orchestrator_escalation(state)
        
        if current_phase == "complete":
            return RoutingDecision(
                next_phase="complete",
                reason="Already in complete state",
                requires_llm=False
            )
        
        # Deterministic state machine routing
        if current_phase in ("planning", "planner"):
            return self._route_from_planning(state)
        
        if current_phase in ("coding", "coder"):
            return self._route_from_coding(state)
        
        if current_phase in ("validating", "validator"):
            return self._route_from_validating(state)
        
        if current_phase in ("fixing", "fixer"):
            return self._route_from_fixing(state)
        
        # Unknown phase - escalate to LLM
        logger.warning(f"[DETERMINISTIC_ROUTER] Unknown phase '{current_phase}', escalating to LLM")
        return RoutingDecision(
            next_phase="orchestrator",
            reason=f"Unknown phase: {current_phase}",
            requires_llm=True
        )
    
    def _route_from_planning(self, state: Dict[str, Any]) -> RoutingDecision:
        """
        Route from PLANNING state.
        
        Flow: planning → (gate check) → coding
        """
        # Check if we can exit planning state
        exit_gate = self.gate_evaluator.can_exit_state(state, "planning")
        
        if not exit_gate.passed:
            logger.warning(f"[DETERMINISTIC_ROUTER] Planning exit gate FAILED: {exit_gate.checks_failed}")
            return RoutingDecision(
                next_phase="planner",
                reason="Planning exit gate failed - need to complete planning",
                gate_result=exit_gate,
                requires_llm=False,
                metadata={"failed_checks": exit_gate.checks_failed}
            )
        
        # Check if we can enter coding state
        entry_gate = self.gate_evaluator.can_enter_state(state, "coding")
        
        if not entry_gate.passed:
            logger.error(f"[DETERMINISTIC_ROUTER] Coding entry gate FAILED: {entry_gate.checks_failed}")
            return RoutingDecision(
                next_phase="planner",
                reason="Coding entry gate failed - planning incomplete",
                gate_result=entry_gate,
                requires_llm=False,
                metadata={"failed_checks": entry_gate.checks_failed}
            )
        
        # Both gates passed - proceed to coding
        logger.info("[DETERMINISTIC_ROUTER] ✅ Planning → Coding (gates passed)")
        return RoutingDecision(
            next_phase="coder",
            reason="Planning complete, entering coding phase",
            gate_result=exit_gate,
            requires_llm=False
        )
    
    def _route_from_coding(self, state: Dict[str, Any]) -> RoutingDecision:
        """
        Route from CODING state.
        
        Flow: coding → (gate check) → validating
        """
        # Check if we can exit coding state
        exit_gate = self.gate_evaluator.can_exit_state(state, "coding")
        
        if not exit_gate.passed:
            logger.warning(f"[DETERMINISTIC_ROUTER] Coding exit gate FAILED: {exit_gate.checks_failed}")
            
            # Check if we're waiting for locks
            if "not_waiting" in exit_gate.checks_failed:
                return RoutingDecision(
                    next_phase="waiting",
                    reason="Waiting for file locks to release",
                    gate_result=exit_gate,
                    requires_llm=False
                )
            
            # Continue coding
            return RoutingDecision(
                next_phase="coder",
                reason="Coding exit gate failed - need to complete implementation",
                gate_result=exit_gate,
                requires_llm=False,
                metadata={"failed_checks": exit_gate.checks_failed}
            )
        
        # Check if we can enter validation state
        entry_gate = self.gate_evaluator.can_enter_state(state, "validating")
        
        if not entry_gate.passed:
            logger.error(f"[DETERMINISTIC_ROUTER] Validation entry gate FAILED: {entry_gate.checks_failed}")
            return RoutingDecision(
                next_phase="coder",
                reason="Validation entry gate failed - need files to validate",
                gate_result=entry_gate,
                requires_llm=False,
                metadata={"failed_checks": entry_gate.checks_failed}
            )
        
        # Both gates passed - proceed to validation
        logger.info("[DETERMINISTIC_ROUTER] ✅ Coding → Validating (gates passed)")
        return RoutingDecision(
            next_phase="validator",
            reason="Coding complete, entering validation phase",
            gate_result=exit_gate,
            requires_llm=False
        )
    
    def _route_from_validating(self, state: Dict[str, Any]) -> RoutingDecision:
        """
        Route from VALIDATING state.
        
        Flow: validating → (pass → complete | fail → fixing)
        """
        # Check if we can exit validation state
        exit_gate = self.gate_evaluator.can_exit_state(state, "validating")
        
        if exit_gate.passed:
            # Validation passed - we're done!
            logger.info("[DETERMINISTIC_ROUTER] ✅ Validation → Complete (validation passed)")
            return RoutingDecision(
                next_phase="complete",
                reason="Validation passed - implementation successful",
                gate_result=exit_gate,
                requires_llm=False
            )
        
        # Validation failed - need to fix
        logger.warning(f"[DETERMINISTIC_ROUTER] Validation FAILED: {exit_gate.checks_failed}")
        
        # Check if we can enter fixing state
        entry_gate = self.gate_evaluator.can_enter_state(state, "fixing")
        
        if not entry_gate.passed:
            # Can't fix (max attempts exceeded)
            logger.error(f"[DETERMINISTIC_ROUTER] Fixing entry gate FAILED: {entry_gate.checks_failed}")
            
            if "fix_attempts_valid" in entry_gate.checks_failed:
                # Max fix attempts exceeded - escalate to user
                return RoutingDecision(
                    next_phase="chat",
                    reason="Max fix attempts exceeded - need user guidance",
                    gate_result=entry_gate,
                    requires_llm=False,
                    metadata={"escalation_reason": "max_fix_attempts"}
                )
            
            # Other failure - escalate to LLM
            return RoutingDecision(
                next_phase="orchestrator",
                reason="Validation failed but cannot enter fixing state",
                gate_result=entry_gate,
                requires_llm=True
            )
        
        # Proceed to fixing
        logger.info("[DETERMINISTIC_ROUTER] ✅ Validating → Fixing (validation failed, fix available)")
        return RoutingDecision(
            next_phase="fixer",
            reason="Validation failed - entering fix phase",
            gate_result=exit_gate,
            requires_llm=False,
            metadata={"error_details": exit_gate.error_details}
        )
    
    def _route_from_fixing(self, state: Dict[str, Any]) -> RoutingDecision:
        """
        Route from FIXING state.
        
        Flow: fixing → (gate check) → validating
        """
        # Check if we can exit fixing state
        exit_gate = self.gate_evaluator.can_exit_state(state, "fixing")
        
        if not exit_gate.passed:
            logger.warning(f"[DETERMINISTIC_ROUTER] Fixing exit gate FAILED: {exit_gate.checks_failed}")
            
            # Check if we're waiting for locks
            if "not_waiting" in exit_gate.checks_failed:
                return RoutingDecision(
                    next_phase="waiting",
                    reason="Waiting for file locks to release",
                    gate_result=exit_gate,
                    requires_llm=False
                )
            
            # Check if max attempts exceeded
            if "fix_attempts_valid" in exit_gate.checks_failed:
                return RoutingDecision(
                    next_phase="chat",
                    reason="Max fix attempts exceeded - need user guidance",
                    gate_result=exit_gate,
                    requires_llm=False,
                    metadata={"escalation_reason": "max_fix_attempts"}
                )
            
            # Continue fixing
            return RoutingDecision(
                next_phase="fixer",
                reason="Fixing exit gate failed - continue fixing",
                gate_result=exit_gate,
                requires_llm=False
            )
        
        # Exit gate passed - go back to validation
        logger.info("[DETERMINISTIC_ROUTER] ✅ Fixing → Validating (fix applied, re-validating)")
        return RoutingDecision(
            next_phase="validator",
            reason="Fix applied - re-validating code",
            gate_result=exit_gate,
            requires_llm=False
        )
    
    def _route_waiting(self, state: Dict[str, Any]) -> RoutingDecision:
        """
        Route from WAITING state (file locks).
        
        Flow: waiting → (retry same agent | escalate after 5 attempts)
        """
        loop_info = state.get("loop_detection", {})
        wait_count = loop_info.get("wait_attempts", 0)
        last_node = loop_info.get("last_node", "coder")
        
        # Check if max waits exceeded
        if wait_count >= 5:
            logger.error(f"[DETERMINISTIC_ROUTER] Max wait attempts ({wait_count}) exceeded - escalating")
            return RoutingDecision(
                next_phase="orchestrator",
                reason="Max wait attempts exceeded - need LLM decision",
                requires_llm=True,
                metadata={"wait_count": wait_count, "last_node": last_node}
            )
        
        # Retry the same agent that was waiting
        logger.info(f"[DETERMINISTIC_ROUTER] Waiting → {last_node} (retry {wait_count}/5)")
        return RoutingDecision(
            next_phase=last_node,
            reason=f"Retrying {last_node} after wait (attempt {wait_count}/5)",
            requires_llm=False,
            metadata={"wait_count": wait_count}
        )
    
    def _route_chat(self, state: Dict[str, Any]) -> RoutingDecision:
        """
        Route from CHAT state.
        
        Chat is a terminal state that routes to chat_setup.
        """
        return RoutingDecision(
            next_phase="chat_setup",
            reason="User interaction needed",
            requires_llm=False
        )
    
    def _route_orchestrator_escalation(self, state: Dict[str, Any]) -> RoutingDecision:
        """
        Route when phase="orchestrator".
        
        This happens when:
        1. Agents return to orchestrator after completing work (normal flow)
        2. Agents explicitly escalate for LLM decision (rare)
        
        We infer the actual state from context and route accordingly.
        """
        # Check if this is an explicit escalation
        loop_info = state.get("loop_detection", {})
        escalated_from = loop_info.get("escalated_from")
        
        if escalated_from:
            logger.info(f"[DETERMINISTIC_ROUTER] Explicit escalation from {escalated_from} - LLM decision required")
            return RoutingDecision(
                next_phase="orchestrator",
                reason=f"Explicit escalation from {escalated_from}",
                requires_llm=True,
                metadata={"escalated_from": escalated_from}
            )
        
        # Normal return from agent - infer state from artifacts
        # Priority: Check what just completed to determine next phase
        
        # Just finished planning? (scaffolding_complete or plan exists)
        artifacts = state.get("artifacts", {})
        if artifacts.get("scaffolding_complete") or artifacts.get("plan"):
            logger.info("[DETERMINISTIC_ROUTER] Returning from planner - routing from planning state")
            return self._route_from_planning(state)
        
        # Just finished coding? (implementation_complete flag)
        if state.get("implementation_complete"):
            logger.info("[DETERMINISTIC_ROUTER] Returning from coder - routing from coding state")
            return self._route_from_coding(state)
        
        # Just finished validation? (validation_passed flag exists)
        if "validation_passed" in state:
            logger.info("[DETERMINISTIC_ROUTER] Returning from validator - routing from validating state")
            return self._route_from_validating(state)
        
        # Just finished fixing? (fix_attempts incremented)
        if state.get("fix_attempts", 0) > 0:
            logger.info("[DETERMINISTIC_ROUTER] Returning from fixer - routing from fixing state")
            return self._route_from_fixing(state)
        
        # Fallback: Start from planning if no clear state
        logger.warning("[DETERMINISTIC_ROUTER] Could not infer state from context - starting from planning")
        return RoutingDecision(
            next_phase="planner",
            reason="Could not infer state - starting planning phase",
            requires_llm=False
        )
    
    def check_loop_detection(self, state: Dict[str, Any], next_phase: str) -> Tuple[bool, Optional[str]]:
        """
        Check if we're in an infinite loop.
        
        Args:
            state: Current state
            next_phase: Phase we're about to route to
            
        Returns:
            (is_loop, warning_message)
        """
        loop_info = state.get("loop_detection", {})
        last_node = loop_info.get("last_node")
        consecutive_count = loop_info.get("consecutive_calls", 0)
        
        # If routing to same node again
        if last_node == next_phase:
            consecutive_count += 1
            
            # Warn after 3 consecutive calls
            if consecutive_count >= 3:
                warning = f"Loop detected: {next_phase} called {consecutive_count} times consecutively"
                logger.warning(f"[DETERMINISTIC_ROUTER] ⚠️ {warning}")
                
                # Force escalation after 5 consecutive calls
                if consecutive_count >= 5:
                    logger.error(f"[DETERMINISTIC_ROUTER] 🚨 INFINITE LOOP: {next_phase} called {consecutive_count} times")
                    return True, warning
                
                return False, warning
        
        return False, None
