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
        
        # STEP 0: Check intent classification for non-engineering tasks
        # If we're in planning phase, check if this is actually a question/chat request
        if current_phase == "planning":
            artifacts = state.get("artifacts", {})
            structured_intent = artifacts.get("structured_intent", {})
            task_type = structured_intent.get("task_type")
            
            # Handle confirmations specially - check if there's a plan to confirm
            if task_type == "confirmation":
                has_plan = bool(artifacts.get("plan") or artifacts.get("implementation_plan"))
                if has_plan:
                    # User confirmed plan - proceed to coding
                    logger.info("[DETERMINISTIC_ROUTER] Confirmation with existing plan - proceeding to coder")
                    return RoutingDecision(
                        next_phase="coder",
                        reason="User confirmed plan - starting implementation",
                        requires_llm=False,
                        metadata={"task_type": task_type, "confirmed": True}
                    )
                else:
                    # No plan to confirm - ask what they're confirming
                    logger.info("[DETERMINISTIC_ROUTER] Confirmation without plan - routing to chat for clarification")
                    return RoutingDecision(
                        next_phase="chat_setup",
                        reason="Confirmation without context - asking for clarification",
                        requires_llm=False,
                        metadata={"task_type": task_type, "missing_context": True}
                    )
            
            # Route questions/unclear to chat
            if task_type in ["question", "unclear"]:
                logger.info(f"[DETERMINISTIC_ROUTER] task_type={task_type} - routing to chat instead of engineering pipeline")
                return RoutingDecision(
                    next_phase="chat_setup",
                    reason=f"Non-engineering task ({task_type}) - routing to chat",
                    requires_llm=False,
                    metadata={"task_type": task_type}
                )
        
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
            return self._finalize_decision(state, self._route_from_planning(state))
        
        if current_phase in ("coding", "coder"):
            return self._finalize_decision(state, self._route_from_coding(state))
        
        if current_phase in ("validating", "validator"):
            return self._finalize_decision(state, self._route_from_validating(state))
        
        if current_phase in ("fixing", "fixer"):
            return self._finalize_decision(state, self._route_from_fixing(state))
        
        # Unknown phase - escalate to LLM
        logger.warning(f"[DETERMINISTIC_ROUTER] Unknown phase '{current_phase}', escalating to LLM")
        return self._finalize_decision(state, RoutingDecision(
            next_phase="orchestrator",
            reason=f"Unknown phase: {current_phase}",
            requires_llm=True
        ))
    
    def _finalize_decision(self, state: Dict[str, Any], decision: RoutingDecision) -> RoutingDecision:
        """Apply loop detection and final metadata updates."""
        is_loop, loop_msg, loop_info = self.check_loop_detection(state, decision.next_phase)
        
        # Update metadata with new loop info (to be persisted by orchestrator)
        decision.metadata["loop_detection"] = loop_info
        
        if is_loop:
            # ESCALATE TO ORCHESTRATOR LLM - let it decide what to do
            return RoutingDecision(
                next_phase="orchestrator",
                reason=f"Loop detected: {loop_msg} - escalating to orchestrator for decision",
                requires_llm=True,
                metadata={"loop_warning": loop_msg, "loop_detection": loop_info}
            )
        return decision
    
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
            # Can't fix (max attempts exceeded or other issues)
            logger.error(f"[DETERMINISTIC_ROUTER] Fixing entry gate FAILED: {entry_gate.checks_failed}")
            
            # ALWAYS escalate gate failures to orchestrator LLM
            # Let it decide whether to ask user, retry differently, or escalate
            return RoutingDecision(
                next_phase="orchestrator",
                reason=f"Cannot enter fixing state: {', '.join(entry_gate.checks_failed)} - escalating to orchestrator",
                gate_result=entry_gate,
                requires_llm=True,
                metadata={"failed_gate_checks": entry_gate.checks_failed}
            )
        
        # Proceed to fixing
        logger.info("[DETERMINISTIC_ROUTER] ✅ Validating → Fixing (validation failed, fix available)")
        return RoutingDecision(
            next_phase="fixer",
            reason="Validation failed - entering fix phase",
            gate_result=exit_gate,
            requires_llm=False,
            # Fix: GateResult doesn't have error_details, read from state safely
            metadata={"error_details": (state.get("error_log") or ["Unknown error"])[-1]}
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
        2. Agents explicitly escalate for decision (rare)
        3. Loops or stuck states are detected
        
        We enforce deterministic rules to avoid expensive LLM calls.
        """
        loop_info = state.get("loop_detection", {})
        escalated_from = loop_info.get("escalated_from")
        fix_attempts = state.get("fix_attempts", 0)
        
        # RULE 1: Max Fix Attempts -> STOP (Ask User)
        if fix_attempts >= 3:
             logger.warning(f"[DETERMINISTIC_ROUTER] 🚨 Max fix attempts ({fix_attempts}) reached - One more try with detailed context")
             # On 3rd attempt, give Fixer more context and one final shot
             return RoutingDecision(
                next_phase="fixer",
                reason="Final fix attempt with enhanced context",
                requires_llm=False
             )

        # RULE 2: Explicit Escalation (Loops/Locks) -> RETRY with different strategy
        if escalated_from:
            logger.warning(f"[DETERMINISTIC_ROUTER] 🚨 Systematic escalation from {escalated_from} - Retrying with reset")
            return RoutingDecision(
                next_phase="fixer" if escalated_from == "validator" else "validator", 
                reason=f"Retry after stuck in {escalated_from}",
                requires_llm=False
            )
        
        # RULE 3: Inference (Normal Flow)
        # Check completion flags in REVERSE order of operations (Fix/Valid -> Code -> Plan)
        
        artifacts = state.get("artifacts", {})
        
        # PRIORITY 1: Validation Status
        validation_status = state.get("validation_status")
        
        # Import Enum for comparison (Lazy import to avoid circular dependency if router is imported early)
        from app.agents.sub_agents.validator.models import ValidationStatus
        
        if validation_status == ValidationStatus.PENDING:
             logger.info("[DETERMINISTIC_ROUTER] Validation PENDING - Routing to VALIDATOR")
             return RoutingDecision(next_phase="validator", reason="Validation pending", requires_llm=False)
             
        if validation_status in [ValidationStatus.PASSED, ValidationStatus.FAILED_RECOVERABLE, ValidationStatus.FAILED_CRITICAL]:
             return self._route_from_validating(state)
        
        # PRIORITY 2: Are we in a fix loop?
        # Only check this if we didn't just pass validation
        if fix_attempts > 0:
             return self._route_from_fixing(state)

        # PRIORITY 3: Just finished coding?
        if artifacts.get("implementation_complete"):
             return self._route_from_coding(state)
        
        # PRIORITY 4: Just finished planning?
        if artifacts.get("scaffolding_complete") or artifacts.get("plan"):
             return self._route_from_planning(state)
        
        # Fallback: Start from planning if no clear state
        logger.warning("[DETERMINISTIC_ROUTER] Could not infer state from context - Defaulting to PLANNER")
        return RoutingDecision(
            next_phase="planner",
            reason="State inference failed - ensuring plan exists",
            requires_llm=False
        )

    def check_loop_detection(self, state: Dict[str, Any], next_phase: str) -> Tuple[bool, Optional[str], Dict[str, Any]]:
        """
        Check if we're in an infinite loop using Pattern Matching.
        
        Detection Strategy:
        1. Consecutive Repeats: A -> A (Threshold: 3)
        2. Simple Cycles: A -> B -> A -> B (Threshold: 3 cycles)
        3. Long Cycles: A -> B -> C -> A -> B -> C (Threshold: 2 cycles)
        """
        loop_info = state.get("loop_detection", {}).copy()
        history = list(loop_info.get("phase_history", []))
        
        # Add current decision to history (max last 20 steps)
        history.append(next_phase)
        if len(history) > 20:
            history.pop(0)
            
        loop_info["phase_history"] = history
        loop_info["last_node"] = next_phase # Keep for backward compat
        
        # 1. Consecutive Repeats (A -> A -> A)
        if len(history) >= 3:
            if history[-1] == history[-2] == history[-3]:
                 warning = f"Stuck in phase: {next_phase} (3x repeats)"
                 logger.warning(f"[DETERMINISTIC_ROUTER] ⚠️ {warning}")
                 return True, warning, loop_info

        # 2. Cycle Detection (A -> B -> A -> B ...)
        # We look for patterns of length 2 to 5 repeating
        if len(history) >= 6:
            for pattern_len in range(2, 6):
                # Need at least 2 full repetitions to call it a loop
                # e.g. pattern A-B (len 2) needs A-B-A-B (len 4)
                required_len = pattern_len * 2
                if len(history) < required_len:
                    continue
                    
                # Extract potential pattern and comparison slice
                current_slice = history[-pattern_len:]
                previous_slice = history[-required_len:-pattern_len]
                
                if current_slice == previous_slice:
                    # Found a cycle!
                    # Check if we have a THIRD repetition to be sure it's a "God Loop" (infinite)
                    # and not just a retry (which might be valid once)
                    if len(history) >= pattern_len * 3:
                        third_slice = history[-(pattern_len*3):-(pattern_len*2)]
                        if third_slice == current_slice:
                             pattern_str = "->".join(current_slice)
                             warning = f"Infinite Cycle Detected: [{pattern_str}] x3"
                             logger.warning(f"[DETERMINISTIC_ROUTER] ⚠️ {warning}")
                             return True, warning, loop_info
                             
        return False, None, loop_info
