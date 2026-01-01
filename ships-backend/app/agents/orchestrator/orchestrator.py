"""
ShipS* Main Orchestrator

The central intelligence of the ShipS* system integrating:
- State Machine: Deterministic state transitions
- Quality Gates: Enforce quality at every step
- Artifact Flow: Coordinate data between agents
- Error Recovery: Smart retries and escalation

This is a ROUTER, not a THINKER. It delegates all reasoning
to specialist agents and enforces quality gates.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass, field
import uuid
import asyncio

from .state_machine import (
    StateMachine,
    OrchestratorState,
    TransitionReason,
    StateTransition,
    TransitionError,
    StateContext,
)
from .quality_gates import (
    QualityGateRegistry,
    QualityGateChecker,
    QualityGate,
)
from .artifact_flow import (
    ArtifactRegistry,
    AgentInvoker,
    ArtifactError,
    ArtifactStale,
    MissingArtifact,
)
from .error_recovery import (
    ErrorRecoverySystem,
    ErrorType,
    RecoveryResult,
    RecoveryStatus,
)
from app.artifacts import ArtifactManager, AgentType, AgentLogEntry


@dataclass
class TaskResult:
    """Result of a complete task execution."""
    task_id: str
    success: bool
    final_state: OrchestratorState
    artifacts_produced: List[str]
    transitions: List[StateTransition]
    duration_seconds: float
    error: Optional[str] = None
    user_escalation: Optional[RecoveryResult] = None


class ShipSOrchestrator:
    """
    Production-grade orchestrator for ShipS*.
    
    This class coordinates the entire code generation workflow:
    1. Receives user request
    2. Routes through specialist agents
    3. Enforces quality gates at each step
    4. Handles errors with smart recovery
    5. Returns working code or escalates to user
    
    Key Principles:
    - Router, not thinker: Delegates all reasoning
    - Deterministic: State machine governs transitions
    - Quality-first: Gates must pass before advancing
    - Self-healing: Auto-fixes up to 3 times
    - Transparent: Full audit trail of decisions
    """
    
    MAX_FIX_ATTEMPTS = 3
    
    def __init__(
        self, 
        project_root: str,
        artifact_manager: Optional[ArtifactManager] = None,
        reasoning_callback: Optional[Callable[[str, Any], None]] = None
    ):
        """
        Initialize the orchestrator.
        
        Args:
            project_root: Path to target project
            artifact_manager: Optional pre-configured artifact manager
            reasoning_callback: Optional callback for streaming reasoning output
                                Signature: (event_type: str, data: Any) -> None
                                event_type can be: "observation", "reasoning", "decision", "confidence"
        """
        self.project_root = project_root
        self.reasoning_callback = reasoning_callback
        
        # Initialize subsystems
        self.artifact_manager = artifact_manager or ArtifactManager(project_root)
        self.state_machine = StateMachine()
        self.gate_registry = QualityGateRegistry()
        self.artifact_registry = ArtifactRegistry()
        self.error_recovery = ErrorRecoverySystem()
        
        # Quality gate checker with artifact integration
        self.gate_checker = QualityGateChecker(self.artifact_manager)
        
        # Agent invoker
        self.agent_invoker = AgentInvoker(self.artifact_registry)
        
        # Registered agents
        self._agents: Dict[str, Any] = {}
        
        # Current task
        self._current_task_id: Optional[str] = None
        self._task_started_at: Optional[datetime] = None
        
        # Initialize LLM for reasoning (used when state machine is ambiguous)
        from app.core.llm_factory import LLMFactory
        self._reasoning_llm = LLMFactory.get_model("orchestrator", reasoning_level="high")
        
        # Wire up gate callbacks
        self._setup_gate_callbacks()
    
    def _setup_gate_callbacks(self) -> None:
        """Wire up quality gate callbacks to state machine."""
        for state in OrchestratorState:
            # Create closure to capture state
            def make_exit_gate_fn(s: OrchestratorState):
                def exit_gate_fn():
                    return self.gate_checker.check_gate(s, "exit")
                return exit_gate_fn
            
            def make_entry_gate_fn(s: OrchestratorState):
                def entry_gate_fn():
                    return self.gate_checker.check_gate(s, "entry")
                return entry_gate_fn
            
            self.state_machine.register_exit_gate(state, make_exit_gate_fn(state))
            self.state_machine.register_entry_gate(state, make_entry_gate_fn(state))
    
    def register_agent(self, name: str, agent: Any) -> None:
        """
        Register an agent for invocation.
        
        Args:
            name: Agent name (e.g., "Planner", "Coder", "Fixer")
            agent: Agent instance with invoke() method
        """
        self._agents[name] = agent
        self.agent_invoker.register_agent(name, agent)
    
    # =========================================================================
    # MAIN ENTRY POINTS
    # =========================================================================
    
    async def execute_task(
        self, 
        user_request: str,
        task_id: Optional[str] = None
    ) -> TaskResult:
        """
        Execute a complete task from user request to working code.
        
        This is the main entry point. It:
        1. Interprets the request
        2. Plans the implementation
        3. Generates code
        4. Validates and fixes
        5. Builds and returns result
        
        Args:
            user_request: Natural language user request
            task_id: Optional task identifier
            
        Returns:
            TaskResult with success/failure and artifacts
        """
        # Initialize task
        self._current_task_id = task_id or str(uuid.uuid4())
        self._task_started_at = datetime.utcnow()
        self.state_machine = StateMachine(self._current_task_id)
        
        # Initialize per-task artifacts
        self.artifact_manager.initialize_for_task(
            self._current_task_id,
            user_request
        )
        
        # Log task start
        self.artifact_manager.log_agent_action(
            agent=AgentType.ORCHESTRATOR,
            action="task_started",
            input_summary=user_request[:200]
        )
        
        try:
            # Run the workflow
            await self._run_workflow(user_request)
            
            # Calculate duration
            duration = (datetime.utcnow() - self._task_started_at).total_seconds()
            
            return TaskResult(
                task_id=self._current_task_id,
                success=self.state_machine.current_state == OrchestratorState.COMPLETE,
                final_state=self.state_machine.current_state,
                artifacts_produced=list(self.artifact_registry._artifacts.keys()),
                transitions=self.state_machine.get_history(),
                duration_seconds=duration
            )
            
        except Exception as e:
            duration = (datetime.utcnow() - self._task_started_at).total_seconds()
            
            return TaskResult(
                task_id=self._current_task_id,
                success=False,
                final_state=self.state_machine.current_state,
                artifacts_produced=list(self.artifact_registry._artifacts.keys()),
                transitions=self.state_machine.get_history(),
                duration_seconds=duration,
                error=str(e)
            )
    
    async def _run_workflow(self, user_request: str) -> None:
        """Run the complete workflow."""
        # Phase 1: Interpret request
        await self._phase_interpret(user_request)
        
        # Phase 2: Plan
        await self._phase_plan()
        
        # Phase 3: Code
        await self._phase_code()
        
        # Phase 4: Validate (with fix loop)
        await self._phase_validate()
        
        # Phase 5: Build
        await self._phase_build()
        
        # Complete
        self.state_machine.transition(
            OrchestratorState.COMPLETE,
            TransitionReason.BUILD_SUCCEEDED
        )
    
    # =========================================================================
    # WORKFLOW PHASES
    # =========================================================================
    
    async def _phase_interpret(self, user_request: str) -> None:
        """Phase 1: Interpret user request."""
        # Transition to INTERPRETING
        self.state_machine.transition(
            OrchestratorState.INTERPRETING,
            TransitionReason.USER_REQUEST,
            {"request": user_request}
        )
        
        # Register request as artifact
        self.artifact_registry.register(
            "user_request",
            {"request": user_request},
            "User"
        )
        
        # Invoke Request Interpreter agent (Intent Classifier)
        if "Request Interpreter" in self._agents:
            result = await self.agent_invoker.invoke(
                agent_name="Request Interpreter",
                required_artifacts=["user_request"],
                expected_outputs=["structured_intent"],
                parameters={"request": user_request}
            )
            
            if not result.success:
                raise ValueError(f"Request interpretation failed: {result.error}")
            
            # Check for ambiguous requests
            intent = self.artifact_registry.get_data("structured_intent")
            if intent.get("is_ambiguous", False):
                # Extract clarification questions
                questions = intent.get("clarification_questions", [])
                confidence = intent.get("confidence", 0.0)
                
                # Log and escalate
                self.artifact_manager.log_agent_action(
                    agent=AgentType.ORCHESTRATOR,
                    action="ambiguous_request_detected",
                    input_summary=user_request[:100],
                    output_summary=f"Confidence: {confidence}, Questions: {len(questions)}",
                    reasoning="Request needs user clarification"
                )
                
                # Transition to ESCALATED
                self.state_machine.transition(
                    OrchestratorState.ESCALATED,
                    TransitionReason.UNRECOVERABLE_ERROR,
                    {"reason": "ambiguous_request", "questions": questions},
                    skip_gates=True
                )
                
                # Format escalation message
                questions_text = "\n".join(f"  - {q}" for q in questions)
                raise ValueError(
                    f"Request needs clarification:\n{questions_text}"
                )
    
    async def _phase_plan(self) -> None:
        """Phase 2: Generate plan."""
        # Transition to PLANNING
        self.state_machine.transition(
            OrchestratorState.PLANNING,
            TransitionReason.REQUEST_INTERPRETED
        )
        
        # Invoke Planner agent
        if "Planner" in self._agents:
            result = await self.agent_invoker.invoke(
                agent_name="Planner",
                required_artifacts=["structured_intent"],
                expected_outputs=["plan", "pattern_registry", "contract_definitions"]
            )
            
            if not result.success:
                raise ValueError(f"Planning failed: {result.error}")
    
    async def _phase_code(self) -> None:
        """Phase 3: Generate code."""
        # Transition to CODING
        self.state_machine.transition(
            OrchestratorState.CODING,
            TransitionReason.PLAN_APPROVED
        )
        
        # Invoke Coder agent
        if "Coder" in self._agents:
            coder = self._agents["Coder"]
            
            # Inject context from Planner artifacts (avoids disk I/O)
            try:
                folder_map = self.artifact_registry.get_data("folder_map") if self.artifact_registry.has("folder_map") else None
                api_contracts = self.artifact_registry.get_data("api_contracts") if self.artifact_registry.has("api_contracts") else None
                project_type = self.artifact_registry.get_data("structured_intent").get("project_type", "web_app") if self.artifact_registry.has("structured_intent") else "web_app"
                
                # Get thought signature from Planner if available
                thought_sig = None
                if hasattr(self, '_thought_signatures'):
                    thought_sig = self._thought_signatures.get("Planner")
                
                # Inject context into Coder (pre-loads prompt with artifacts)
                if hasattr(coder, 'inject_context_from_state'):
                    coder.inject_context_from_state(
                        folder_map=folder_map,
                        api_contracts=api_contracts,
                        project_type=project_type,
                        thought_signature=thought_sig
                    )
                    logger.info("[ORCHESTRATOR] ✅ Injected context into Coder from state")
            except Exception as inject_err:
                logger.warning(f"[ORCHESTRATOR] Context injection failed: {inject_err}")
            
            result = await self.agent_invoker.invoke(
                agent_name="Coder",
                required_artifacts=["plan", "pattern_registry", "contract_definitions"],
                expected_outputs=["code_changes", "diffs"]
            )
            
            if not result.success:
                raise ValueError(f"Code generation failed: {result.error}")
    
    async def _phase_validate(self) -> None:
        """Phase 4: Validate code with fix loop."""
        fix_attempts = 0
        
        while fix_attempts < self.MAX_FIX_ATTEMPTS:
            # Transition to VALIDATING
            try:
                self.state_machine.transition(
                    OrchestratorState.VALIDATING,
                    TransitionReason.CODE_GENERATED,
                    skip_gates=True  # We'll check manually
                )
            except TransitionError:
                pass  # Already in VALIDATING from a retry
            
            # Invoke Validator agent
            if "Validator" in self._agents:
                result = await self.agent_invoker.invoke(
                    agent_name="Validator",
                    required_artifacts=["code_changes"],
                    expected_outputs=["validation_report"]
                )
                
                if result.success:
                    # Check if validation passed
                    validation = self.artifact_registry.get_data("validation_report")
                    if validation.get("passed", False):
                        # Validation passed, proceed
                        return
            
            # Validation failed, try to fix
            fix_attempts += 1
            
            # Transition to FIXING
            self.state_machine.transition(
                OrchestratorState.FIXING,
                TransitionReason.VALIDATION_FAILED,
                {"attempt": fix_attempts}
            )
            
            # Invoke Fixer agent
            if "Fixer" in self._agents:
                result = await self.agent_invoker.invoke(
                    agent_name="Fixer",
                    required_artifacts=["code_changes", "validation_report"],
                    expected_outputs=["code_changes", "fix_report"]
                )
                
                if result.success:
                    continue  # Try validation again
            
            # Fix failed
            break
        
        # Max attempts exceeded, escalate
        self.state_machine.transition(
            OrchestratorState.ESCALATED,
            TransitionReason.MAX_RETRIES_EXCEEDED
        )
        
        raise ValueError(f"Validation failed after {fix_attempts} fix attempts")
    
    async def _phase_build(self) -> None:
        """Phase 5: Build the code."""
        # Transition to BUILDING
        self.state_machine.transition(
            OrchestratorState.BUILDING,
            TransitionReason.VALIDATION_PASSED
        )
        
        # In production, invoke build system
        # For now, register success
        self.artifact_registry.register(
            "build_log",
            {"success": True, "duration": 0},
            "BuildSystem"
        )
    
    # =========================================================================
    # ERROR HANDLING
    # =========================================================================
    
    def handle_error(
        self, 
        error_type: ErrorType, 
        context: Dict[str, Any]
    ) -> RecoveryResult:
        """
        Handle an error with the recovery system.
        
        Args:
            error_type: Type of error
            context: Error context
            
        Returns:
            RecoveryResult with action to take
        """
        error_id = f"{self._current_task_id}_{error_type.value}"
        return self.error_recovery.handle_error(error_type, error_id, context)
    
    # =========================================================================
    # STATUS AND INTROSPECTION
    # =========================================================================
    
    def get_status(self) -> Dict[str, Any]:
        """Get current orchestrator status."""
        return {
            "task_id": self._current_task_id,
            "current_state": self.state_machine.current_state.value,
            "transition_count": len(self.state_machine.get_history()),
            "artifacts": self.artifact_registry.get_summary(),
            "started_at": self._task_started_at.isoformat() if self._task_started_at else None
        }
    
    def get_audit_trail(self) -> Dict[str, Any]:
        """Get full audit trail for debugging."""
        return {
            "task_id": self._current_task_id,
            "state_transitions": [
                {
                    "from": t.from_state.value,
                    "to": t.to_state.value,
                    "reason": t.reason.value,
                    "timestamp": t.timestamp.isoformat(),
                    "gate_results": t.gate_results
                }
                for t in self.state_machine.get_history()
            ],
            "artifacts": self.artifact_registry.get_summary(),
            "error_attempts": self.error_recovery.get_summary()
        }
    
    # =========================================================================
    # LLM REASONING (For Ambiguous Situations)
    # =========================================================================
    
    def _stream_reasoning(self, event_type: str, data: Any) -> None:
        """Stream reasoning events to callback if registered."""
        if self.reasoning_callback:
            self.reasoning_callback(event_type, data)
    
    async def _llm_reason(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Use LLM to reason about next action when state machine is ambiguous.
        
        This is called when deterministic rules are insufficient,
        e.g., when multiple valid actions exist or edge cases are hit.
        
        Args:
            context: Current context including state, artifacts, errors
            
        Returns:
            Structured reasoning result with decision and confidence
        """
        import json
        import re
        
        # Build reasoning prompt
        current_state = self.state_machine.current_state.value
        transitions = len(self.state_machine.get_history())
        error_summary = self.error_recovery.get_summary()
        
        prompt = f"""<role>You are the ShipS* Orchestrator reasoning about next steps.</role>

<state>
CURRENT_STATE: {current_state}
TRANSITIONS_MADE: {transitions}
TASK_ID: {self._current_task_id}
ERROR_HISTORY: {error_summary}
</state>

<context>
{json.dumps(context, indent=2, default=str)}
</context>

<task>
Think step-by-step:
1. OBSERVE: What is the current state and context?
2. ANALYZE: What rules or patterns apply?
3. RISKS: What could go wrong with each option?
4. DECIDE: What is the safest next action?
</task>

<output_format>
Respond with JSON only:
{{
  "observations": ["key observations about current state"],
  "reasoning": "step-by-step analysis",
  "decision": "continue" | "retry" | "escalate" | "skip_gate" | "abort",
  "confidence": 0.0 to 1.0,
  "risks": ["potential issues if we proceed"],
  "suggested_action": "specific action to take"
}}
</output_format>"""
        
        # Stream observation
        self._stream_reasoning("thinking", {"status": "analyzing state..."})
        
        # Call LLM
        from langchain_core.messages import HumanMessage, SystemMessage
        messages = [
            SystemMessage(content=prompt),
            HumanMessage(content="Analyze and decide. Respond with JSON.")
        ]
        
        response = await self._reasoning_llm.ainvoke(messages)
        response_text = response.content if hasattr(response, 'content') else str(response)
        
        # Parse structured response
        result = {
            "observations": [],
            "reasoning": "",
            "decision": "continue",
            "confidence": 0.5,
            "risks": [],
            "suggested_action": ""
        }
        
        try:
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                parsed = json.loads(json_match.group())
                result.update(parsed)
        except (json.JSONDecodeError, AttributeError):
            result["reasoning"] = response_text
        
        # Stream reasoning events
        for obs in result.get("observations", []):
            self._stream_reasoning("observation", obs)
        
        self._stream_reasoning("reasoning", result.get("reasoning", ""))
        self._stream_reasoning("decision", result.get("decision", "continue"))
        self._stream_reasoning("confidence", result.get("confidence", 0.5))
        
        for risk in result.get("risks", []):
            self._stream_reasoning("risk", risk)
        
        # Self-critique if confidence is low
        if result.get("confidence", 0) < 0.8:
            critique = await self._self_critique(result, context)
            if critique.get("should_revise", False):
                result = await self._revise_decision(result, critique, context)
                self._stream_reasoning("revised", True)
        
        return result
    
    async def _self_critique(
        self, 
        decision: Dict[str, Any], 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Self-critique a decision to catch mistakes."""
        import json
        import re
        
        self._stream_reasoning("thinking", {"status": "self-critiquing..."})
        
        prompt = f"""<role>You are auditing an orchestrator decision. Find flaws.</role>

<decision>
Action: {decision.get('decision')}
Reasoning: {decision.get('reasoning')}
Confidence: {decision.get('confidence')}
Risks: {decision.get('risks')}
</decision>

<critique_checklist>
1. Did the decision consider edge cases?
2. Are there safer alternatives?
3. Is the confidence appropriate?
4. Any logical errors?
</critique_checklist>

<output_format>
JSON:
{{
  "should_revise": true/false,
  "issues": "description of issues or 'None'",
  "suggested_decision": "alternative action or null"
}}
</output_format>"""
        
        from langchain_core.messages import HumanMessage, SystemMessage
        messages = [
            SystemMessage(content=prompt),
            HumanMessage(content="Critique honestly. Find flaws if they exist.")
        ]
        
        response = await self._reasoning_llm.ainvoke(messages)
        response_text = response.content if hasattr(response, 'content') else str(response)
        
        result = {"should_revise": False, "issues": "None", "suggested_decision": None}
        
        try:
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                result = json.loads(json_match.group())
        except:
            pass
        
        if result.get("should_revise"):
            self._stream_reasoning("critique", result.get("issues", "Issues found"))
        
        return result
    
    async def _revise_decision(
        self,
        original: Dict[str, Any],
        critique: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Revise a decision based on critique."""
        import json
        import re
        
        self._stream_reasoning("thinking", {"status": "revising decision..."})
        
        prompt = f"""<role>Revise your decision based on critique.</role>

<original>
Decision: {original.get('decision')}
Reasoning: {original.get('reasoning')}
</original>

<critique>
Issues: {critique.get('issues')}
Suggested: {critique.get('suggested_decision')}
</critique>

<output_format>
JSON:
{{
  "decision": "continue" | "retry" | "escalate" | "skip_gate" | "abort",
  "reasoning": "revised reasoning",
  "confidence": 0.0 to 1.0
}}
</output_format>"""
        
        from langchain_core.messages import HumanMessage, SystemMessage
        messages = [
            SystemMessage(content=prompt),
            HumanMessage(content="Make final decision.")
        ]
        
        response = await self._reasoning_llm.ainvoke(messages)
        response_text = response.content if hasattr(response, 'content') else str(response)
        
        result = original.copy()
        result["was_revised"] = True
        
        try:
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                parsed = json.loads(json_match.group())
                result.update(parsed)
        except:
            pass
        
        self._stream_reasoning("decision", result.get("decision"))
        self._stream_reasoning("confidence", result.get("confidence"))
        
        return result
