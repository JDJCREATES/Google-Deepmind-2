"""
ShipS* Master Orchestrator

The central intelligence of the ShipS* system. This agent:
- Routes tasks to specialist agents (Planner, Coder, Fixer)
- Manages artifact lifecycle (initializes per-task artifacts)
- Enforces quality gates (never proceeds past failures)
- Logs all decisions for auditability

Uses Gemini 3 Flash for fast, high-frequency routing decisions.
"""

from typing import Optional, Literal
from enum import Enum

from app.agents.base.base_agent import BaseAgent
from app.agents.state import AgentState
from app.artifacts import (
    ArtifactManager,
    AgentType,
    GateStatus,
    QualityGate,
    GateCheck,
)


class RoutingDecision(str, Enum):
    """Possible routing decisions from the orchestrator."""
    ROUTE_TO_PLANNER = "PLANNER"
    ROUTE_TO_CODER = "CODER"
    ROUTE_TO_FIXER = "FIXER"
    ROUTE_TO_VALIDATOR = "VALIDATOR"
    MARK_COMPLETE = "COMPLETE"
    ESCALATE_TO_USER = "ESCALATE"


class MasterOrchestrator(BaseAgent):
    """
    The central intelligence of the ShipS* system.
    
    Routes tasks, manages state, and strictly enforces quality gates.
    This is the entry point for all user requests and the coordinator
    for the entire agent workflow.
    
    Quality Gate Enforcement:
        - Checks quality gates before each routing decision
        - Routes to Fixer if validation fails (max 3 attempts)
        - Escalates to user if fix attempts are exhausted
        
    Artifact Management:
        - Initializes per-task artifacts on new requests
        - Logs all routing decisions
        - Updates quality gate status after each phase
    """
    
    MAX_FIX_ATTEMPTS = 3
    
    def __init__(self, artifact_manager: Optional[ArtifactManager] = None):
        """
        Initialize the orchestrator.
        
        Args:
            artifact_manager: Optional artifact manager for coordination
        """
        super().__init__(
            name="Orchestrator",
            agent_type="orchestrator",
            reasoning_level="standard",
            artifact_manager=artifact_manager
        )
        
    def _get_system_prompt(self) -> str:
        return """You are the Orchestrator for ShipS*, an AI coding system that SHIPS WORKING CODE.

Your job is to:
1. Break user requests into concrete, achievable tasks
2. Route tasks to specialist agents (Planner, Coder, Fixer)
3. NEVER proceed past a failed validation
4. Invoke Fixer agent when validation fails
5. Only mark tasks complete when all quality gates pass

Decision Rules:
- If NEW REQUEST → Route to PLANNER
- If PLAN APPROVED → Route to CODER
- If VALIDATION FAILS → Route to FIXER (max 3 attempts)
- If BUILD FAILS → Route to FIXER
- If 3 FIX ATTEMPTS FAIL → ESCALATE to user
- If ALL CHECKS PASS → Mark COMPLETE

You must respond with a JSON object containing:
{
    "decision": "PLANNER" | "CODER" | "FIXER" | "VALIDATOR" | "COMPLETE" | "ESCALATE",
    "reasoning": "Brief explanation of why this decision was made",
    "task_summary": "Current understanding of the task"
}
"""

    def initialize_task(self, task_id: str, task_description: str) -> None:
        """
        Initialize artifacts for a new task.
        
        Creates fresh per-task artifacts and logs the task start.
        
        Args:
            task_id: Unique identifier for the task
            task_description: Human-readable task description
        """
        if not self._artifact_manager:
            return
            
        # Initialize per-task artifacts
        self._artifact_manager.initialize_for_task(task_id, task_description)
        
        # Log task start
        self.log_action(
            action="task_started",
            input_summary=task_description,
            reasoning="New task received from user"
        )
        
        # Add initial quality gates
        gates = self._artifact_manager.get_quality_gate_results()
        gates.add_gate("Plan Quality")
        gates.add_gate("Code Quality")
        gates.add_gate("Integration Quality")
        self._artifact_manager.save_quality_gate_results(gates)

    def check_quality_gates(self) -> tuple[bool, Optional[str]]:
        """
        Check if all quality gates pass.
        
        Returns:
            Tuple of (can_proceed, failed_gate_name or None)
        """
        if not self._artifact_manager:
            return True, None
            
        gates = self._artifact_manager.get_quality_gate_results()
        
        for gate in gates.gates:
            if gate.status == GateStatus.FAILED:
                return False, gate.gate_name
        
        return True, None
    
    def get_fix_attempt_count(self, gate_name: str) -> int:
        """
        Get the number of fix attempts for a gate.
        
        Args:
            gate_name: Name of the quality gate
            
        Returns:
            Number of fix attempts
        """
        if not self._artifact_manager:
            return 0
            
        gates = self._artifact_manager.get_quality_gate_results()
        gate = gates.get_gate(gate_name)
        
        if gate:
            return len(gate.fix_attempts)
        return 0

    async def invoke(self, state: AgentState) -> dict:
        """
        Make a routing decision based on the current state.
        
        This method:
        1. Checks quality gates
        2. Builds context from state
        3. Invokes LLM for routing decision
        4. Logs the decision
        5. Returns state updates
        
        Args:
            state: Current agent state from the graph
            
        Returns:
            Dictionary of state updates including routing decision
        """
        # Check quality gates first
        can_proceed, failed_gate = self.check_quality_gates()
        
        if not can_proceed and failed_gate:
            fix_attempts = self.get_fix_attempt_count(failed_gate)
            
            if fix_attempts >= self.MAX_FIX_ATTEMPTS:
                # Escalate to user
                self.log_action(
                    action="escalate_to_user",
                    reasoning=f"Max fix attempts ({self.MAX_FIX_ATTEMPTS}) reached for {failed_gate}",
                    output_summary="Unable to fix automatically, user intervention required"
                )
                return {
                    "messages": [f"ESCALATE: Unable to fix {failed_gate} after {fix_attempts} attempts"],
                    "agent_scratchpad": {
                        "orchestrator_decision": RoutingDecision.ESCALATE_TO_USER.value,
                        "failed_gate": failed_gate,
                        "fix_attempts": fix_attempts
                    }
                }
            else:
                # Route to fixer
                self.log_action(
                    action="route_to_fixer",
                    reasoning=f"Quality gate '{failed_gate}' failed, attempt {fix_attempts + 1}",
                    output_summary=f"Routing to Fixer for {failed_gate}"
                )
                return {
                    "messages": [f"Routing to FIXER for {failed_gate}"],
                    "agent_scratchpad": {
                        "orchestrator_decision": RoutingDecision.ROUTE_TO_FIXER.value,
                        "failed_gate": failed_gate,
                        "fix_attempt": fix_attempts + 1
                    }
                }
        
        # Build context for routing decision
        messages = self.get_messages_for_llm(state)
        
        # Add artifact context if available
        artifact_context = ""
        if self._artifact_manager:
            gates = self._artifact_manager.get_quality_gate_results()
            artifact_context = f"""
Quality Gates Status:
{self._format_gate_status(gates)}
"""
        
        context = f"""
Current Task: {state.get('current_task', 'None')}
Plan Status: {state.get('plan', {}).get('status', 'None')}
Validation Results: {state.get('validation_results', 'None')}
Error: {state.get('error', 'None')}
{artifact_context}
"""
        
        messages.append({
            "role": "user", 
            "content": f"Context Update:\n{context}\n\nWhat is your routing decision? Respond with JSON."
        })
        
        # Get LLM decision with logging
        response, _ = await self.run_llm_with_logging(
            messages=messages,
            action="routing_decision",
            input_summary=state.get('current_task', 'Unknown task')
        )
        
        # Parse the decision (simplified - in production, use proper JSON parsing)
        decision = self._parse_decision(response)
        
        return {
            "messages": [response],
            "agent_scratchpad": {
                "orchestrator_decision": decision,
                "raw_response": response
            }
        }
    
    def _format_gate_status(self, gates) -> str:
        """Format quality gate status for context."""
        lines = []
        for gate in gates.gates:
            status_emoji = "✅" if gate.status == GateStatus.PASSED else "❌" if gate.status == GateStatus.FAILED else "⏳"
            lines.append(f"  {status_emoji} {gate.gate_name}: {gate.status.value}")
        return "\n".join(lines) if lines else "  No gates defined yet"
    
    def _parse_decision(self, response: str) -> str:
        """
        Parse routing decision from LLM response.
        
        Args:
            response: Raw LLM response
            
        Returns:
            Decision string
        """
        # Simple keyword matching (in production, use proper JSON parsing)
        response_upper = response.upper()
        
        if "COMPLETE" in response_upper:
            return RoutingDecision.MARK_COMPLETE.value
        elif "ESCALATE" in response_upper:
            return RoutingDecision.ESCALATE_TO_USER.value
        elif "FIXER" in response_upper:
            return RoutingDecision.ROUTE_TO_FIXER.value
        elif "CODER" in response_upper:
            return RoutingDecision.ROUTE_TO_CODER.value
        elif "PLANNER" in response_upper:
            return RoutingDecision.ROUTE_TO_PLANNER.value
        elif "VALIDATOR" in response_upper:
            return RoutingDecision.ROUTE_TO_VALIDATOR.value
        else:
            return RoutingDecision.ROUTE_TO_PLANNER.value  # Default
