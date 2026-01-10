"""
ShipS* Intent Classifier (Request Interpreter)

A cheap, simple agent that transforms ambiguous user requests into
structured, project-specific inputs for downstream agents.

Uses Gemini 3 Flash for speed and cost efficiency.
Runs FIRST in the orchestrator workflow, before any other agents.

Key Features:
- Classifies request type (feature, fix, refactor, question)
- Identifies target area (frontend, backend, full-stack)
- Detects ambiguous requests for user clarification
- Project-aware: uses blueprint and folder map for context
- Streaming compatible for real-time feedback
- Security: Detects prompt injection attempts
"""

from datetime import datetime
from typing import Optional, Dict, Any, List, AsyncIterator
from enum import Enum
import json
import re
import uuid

from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.base.base_agent import BaseAgent
from app.graphs.state import AgentState
from app.artifacts import ArtifactManager
from app.security.input_sanitizer import sanitize_input, SanitizationResult
from app.core.logger import get_logger, dev_log, truncate_for_log

logger = get_logger("intent")
from app.prompts.security_prefix import wrap_system_prompt


# ============================================================================
# STRUCTURED OUTPUT MODELS
# ============================================================================

class TaskType(str, Enum):
    """Types of tasks that can be classified."""
    FEATURE = "feature"         # Add new functionality
    FIX = "fix"                 # Fix a bug or issue
    REFACTOR = "refactor"       # Improve code without changing behavior
    MODIFY = "modify"           # Change existing functionality
    DELETE = "delete"           # Remove functionality
    QUESTION = "question"       # User asking a question (no code changes)
    CONFIRMATION = "confirmation" # User approving a plan or action
    UNCLEAR = "unclear"         # Cannot determine task type


class ActionType(str, Enum):
    """Actions to perform on the codebase."""
    CREATE = "create"           # Create new files/components
    MODIFY = "modify"           # Modify existing files
    DELETE = "delete"           # Delete files/code
    EXPLAIN = "explain"         # Just explain something
    ANALYZE = "analyze"         # Analyze without changes
    PROCEED = "proceed"         # Proceed with current state


class TargetArea(str, Enum):
    """Target areas of the codebase."""
    FRONTEND = "frontend"
    BACKEND = "backend"
    DATABASE = "database"
    FULL_STACK = "full-stack"
    CONFIGURATION = "configuration"
    DOCUMENTATION = "documentation"
    TESTING = "testing"
    UNKNOWN = "unknown"
    SYSTEM = "system"           # System level (pipeline control)


class StructuredIntent(BaseModel):
    """
    The structured output of the Intent Classifier.
    
    This artifact is consumed by all downstream agents to understand
    exactly what the user wants to accomplish.
    """
    # Core classification
    task_type: TaskType = Field(
        description="Type of task being requested"
    )
    action: ActionType = Field(
        description="Action to perform on the codebase"
    )
    target_area: TargetArea = Field(
        description="Which part of the codebase is affected"
    )
    
    # Clarified description
    description: str = Field(
        description="Clear, specific description of what needs to be done"
    )
    original_request: str = Field(
        description="The original user request"
    )
    
    # Predicted impact
    affected_areas: List[str] = Field(
        default_factory=list,
        description="Predicted areas/files that will be affected"
    )
    suggested_files: List[str] = Field(
        default_factory=list,
        description="Suggested files to create or modify"
    )
    
    # Dependencies and constraints
    requires_database: bool = Field(
        default=False,
        description="Whether this task requires database changes"
    )
    requires_api: bool = Field(
        default=False,
        description="Whether this task requires API changes"
    )
    
    # Ambiguity handling
    is_ambiguous: bool = Field(
        default=False,
        description="True if the request needs clarification"
    )
    clarification_questions: List[str] = Field(
        default_factory=list,
        description="Questions to ask user if ambiguous"
    )
    assumptions: List[str] = Field(
        default_factory=list,
        description="Assumptions made during classification"
    )
    
    # Confidence
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence in the classification (0.0-1.0)"
    )
    
    # Security (from input sanitizer)
    security_risk_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Security risk score from input sanitization (0.0-1.0)"
    )
    security_warnings: List[str] = Field(
        default_factory=list,
        description="Security warnings from input sanitization"
    )
    
    # Metadata
    classified_at: datetime = Field(
        default_factory=datetime.utcnow
    )
    
    class Config:
        use_enum_values = True


# ============================================================================
# INTENT CLASSIFIER AGENT
# ============================================================================

class IntentClassifier(BaseAgent):
    """
    Intent Classifier (Request Interpreter) Agent.
    
    This agent is the first step in the orchestrator workflow.
    It takes raw user requests and produces structured intents
    that downstream agents can act upon.
    
    Uses Gemini 3 Flash for:
    - Low cost
    - Fast response times
    - Good enough for classification tasks
    
    Features:
    - Streaming compatible
    - Project-aware classification
    - Ambiguity detection
    - Multi-language support
    """
    
    # Confidence threshold below which we mark as ambiguous
    AMBIGUITY_THRESHOLD = 0.6
    
    def __init__(
        self,
        artifact_manager: Optional[ArtifactManager] = None
    ):
        """
        Initialize the Intent Classifier.
        
        Args:
            artifact_manager: Optional artifact manager for context
        """
        super().__init__(
            name="Intent Classifier",
            agent_type="mini",  # Uses Flash model
            reasoning_level="standard",
            artifact_manager=artifact_manager
        )
    
    def _get_system_prompt(self) -> str:
        """Get the system prompt for intent classification."""
        return """You are the Intent Classifier for ShipS*, an AI coding system.

Your job is to transform user requests into structured, actionable intents.

RULES:
1. Be SPECIFIC - vague inputs should produce clarification questions
2. Be PROJECT-AWARE - use provided context about the codebase
3. Be CONSERVATIVE - when unsure, set is_ambiguous=true
4. Be EFFICIENT - output valid JSON only, no explanations

CLASSIFICATION GUIDE:
- "add X" / "create X" / "implement X" → task_type: feature, action: create
- "fix X" / "bug in X" / "X is broken" → task_type: fix, action: modify
- "change X" / "update X" / "modify X" → task_type: modify, action: modify
- "remove X" / "delete X" → task_type: delete, action: delete
- "refactor X" / "clean up X" → task_type: refactor, action: modify
- "what is X" / "how does X work" / "explain X" → task_type: question, action: explain
- "looks good" / "proceed" / "yes" / "go ahead" / "approved" → task_type: confirmation, action: proceed

AMBIGUITY TRIGGERS (set is_ambiguous=true):
- Request mentions multiple unrelated features
- No clear target (e.g., "make it better")
- Contradictory requirements
- References unknown components
- Very short requests without context (< 5 words) BUT EXCLUDE confirmations ("yes", "ok")

OUTPUT FORMAT:
You MUST output a valid JSON object matching this schema:
{
    "task_type": "feature|fix|refactor|modify|delete|question|confirmation|unclear",
    "action": "create|modify|delete|explain|analyze|proceed",
    "target_area": "frontend|backend|database|full-stack|configuration|documentation|testing|system|unknown",
    "description": "MUST preserve the user's EXACT request. Add clarifications, but NEVER remove or abstract away specific details like game names (e.g., 'Tic Tac Toe'), component names, feature specifics, or constraints. If user says 'fantasy tic tac toe', description MUST include 'tic tac toe'.",
    "original_request": "The original request (verbatim copy)",
    "affected_areas": ["area1", "area2"],
    "suggested_files": ["path/to/file.ts"],
    "requires_database": false,
    "requires_api": false,
    "is_ambiguous": false,
    "clarification_questions": [],
    "assumptions": [],
    "confidence": 0.95
}"""
    
    def _build_context_prompt(
        self, 
        user_request: str,
        app_blueprint: Optional[Dict[str, Any]] = None,
        folder_map: Optional[Dict[str, Any]] = None
    ) -> str:
        """Build the context-aware prompt for classification."""
        parts = []
        
        # Add project context if available
        if app_blueprint:
            parts.append(f"PROJECT CONTEXT:\n{json.dumps(app_blueprint, indent=2)[:1000]}")
        
        if folder_map:
            parts.append(f"FOLDER STRUCTURE:\n{json.dumps(folder_map, indent=2)[:500]}")
        
        # Add the user request
        parts.append(f"USER REQUEST:\n{user_request}")
        
        # Add instruction
        parts.append("\nClassify this request and output ONLY valid JSON:")
        
        return "\n\n".join(parts)
    
    def _parse_json_response(self, response: Any) -> Dict[str, Any]:
        """
        Parse JSON from LLM response, handling common issues and list outputs.
        
        Args:
            response: Raw LLM response (str or list)
            
        Returns:
            Parsed JSON dict
            
        Raises:
            ValueError: If JSON cannot be parsed
        """
        text_content = ""
        
        # Handle list-based content (common with Gemini/Vertex)
        if isinstance(response, list):
            # Try to find the first text block
            for item in response:
                if isinstance(item, dict) and item.get("type") == "text":
                    text_content = item.get("text", "")
                    break
                elif isinstance(item, str):
                    text_content = item
                    break
            
            # If still empty, try dumping it (fallback)
            if not text_content:
                text_content = json.dumps(response)
        elif isinstance(response, str):
            text_content = response
        else:
            text_content = str(response)
            
        # Try direct parse
        try:
            return json.loads(text_content)
        except json.JSONDecodeError:
            pass
        
        # Try extracting JSON from markdown code block
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text_content)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass
        
        # Try extracting JSON object
        json_match = re.search(r'\{[\s\S]*\}', text_content)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass
        
        raise ValueError(f"Could not parse JSON from response: {text_content[:200]}...")
    
    def _create_default_intent(
        self, 
        user_request: str, 
        error: Optional[str] = None
    ) -> StructuredIntent:
        """Create a default ambiguous intent when classification fails."""
        return StructuredIntent(
            task_type=TaskType.UNCLEAR,
            action=ActionType.ANALYZE,
            target_area=TargetArea.UNKNOWN,
            description="Could not classify request",
            original_request=user_request,
            is_ambiguous=True,
            clarification_questions=[
                f"I encountered an error understanding your request: {error}" if error else "Could you please provide more details?",
                "Could you rephrase your request?"
            ],
            assumptions=[f"Classification failed: {error}" if error else "Classification failed"],
            confidence=0.0
        )
    
    async def classify(
        self,
        user_request: str,
        app_blueprint: Optional[Dict[str, Any]] = None,
        folder_map: Optional[Dict[str, Any]] = None
    ) -> StructuredIntent:
        """
        Classify a user request into a structured intent.
        
        This is the main entry point for classification.
        
        Args:
            user_request: The raw user request
            app_blueprint: Optional app blueprint for context
            folder_map: Optional folder structure for context
            
        Returns:
            StructuredIntent with classification results
        """
        # Step 0: Security - Sanitize input for injection attempts
        sanitization = sanitize_input(user_request)
        
        # Use sanitized input for classification
        clean_request = sanitization.sanitized_input
        
        # Build context-aware prompt
        prompt = self._build_context_prompt(clean_request, app_blueprint, folder_map)
        
        # Build messages (with security prefix)
        messages = [
            SystemMessage(content=wrap_system_prompt(self.system_prompt)),
            HumanMessage(content=prompt)
        ]
        
        try:
            # Invoke LLM
            start_time = datetime.utcnow()
            response = await self.llm.ainvoke(messages)
            duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            # Parse response
            parsed = self._parse_json_response(response.content)
            
            # Create StructuredIntent
            intent = StructuredIntent(
                task_type=parsed.get("task_type", "unclear"),
                action=parsed.get("action", "analyze"),
                target_area=parsed.get("target_area", "unknown"),
                description=parsed.get("description", user_request),
                original_request=user_request,
                affected_areas=parsed.get("affected_areas", []),
                suggested_files=parsed.get("suggested_files", []),
                requires_database=parsed.get("requires_database", False),
                requires_api=parsed.get("requires_api", False),
                is_ambiguous=parsed.get("is_ambiguous", False),
                clarification_questions=parsed.get("clarification_questions", []),
                assumptions=parsed.get("assumptions", []),
                confidence=parsed.get("confidence", 1.0),
                # Security metadata from sanitization
                security_risk_score=sanitization.risk_score,
                security_warnings=sanitization.detected_patterns
            )
            
            # ================================================================
            # VISIBILITY LOGS: Show what Intent Classifier produced
            # ================================================================
            logger.info(f"[INTENT] 📋 Classified: {intent.task_type}/{intent.action} → {intent.target_area} (conf: {intent.confidence:.2f})")
            dev_log(logger, f"[INTENT] 📝 Description: {truncate_for_log(intent.description, 150)}")
            dev_log(logger, f"[INTENT] 🎯 Original: {truncate_for_log(intent.original_request, 150)}")
            if intent.is_ambiguous:
                logger.info(f"[INTENT] ⚠️ Marked AMBIGUOUS: {intent.clarification_questions[:2]}")
            
            # Check confidence threshold
            if intent.confidence < self.AMBIGUITY_THRESHOLD and not intent.is_ambiguous:
                intent.is_ambiguous = True
                if not intent.clarification_questions:
                    intent.clarification_questions = [
                        "I'm not fully confident about this classification. Could you provide more details?"
                    ]
            
            # Log action if artifact manager available
            if self._artifact_manager:
                security_note = f", Risk: {sanitization.risk_score:.2f}" if sanitization.is_suspicious else ""
                self.log_action(
                    action="classified_intent",
                    input_summary=user_request[:100],
                    output_summary=f"{intent.task_type}/{intent.action}/{intent.target_area}{security_note}",
                    reasoning=f"Confidence: {intent.confidence:.2f}",
                    duration_ms=duration_ms
                )
            
            return intent
            
        except Exception as e:
            # Log error
            if self._artifact_manager:
                self.log_action(
                    action="classification_failed",
                    input_summary=user_request[:100],
                    output_summary=str(e),
                    reasoning="Exception during classification"
                )
            
            return self._create_default_intent(user_request, str(e))
    
    async def classify_streaming(
        self,
        user_request: str,
        app_blueprint: Optional[Dict[str, Any]] = None,
        folder_map: Optional[Dict[str, Any]] = None
    ) -> AsyncIterator[str]:
        """
        Classify with streaming output for real-time feedback.
        
        Yields chunks of the classification as they're generated,
        then yields the final StructuredIntent as JSON.
        
        Args:
            user_request: The raw user request
            app_blueprint: Optional app blueprint for context
            folder_map: Optional folder structure for context
            
        Yields:
            String chunks of the response
        """
        # Build context-aware prompt
        prompt = self._build_context_prompt(user_request, app_blueprint, folder_map)
        
        # Build messages
        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=prompt)
        ]
        
        # Stream response
        full_response = ""
        async for chunk in self.llm.astream(messages):
            if hasattr(chunk, 'content'):
                full_response += chunk.content
                yield chunk.content
        
        # Parse and validate final response
        try:
            parsed = self._parse_json_response(full_response)
            intent = StructuredIntent(
                task_type=parsed.get("task_type", "unclear"),
                action=parsed.get("action", "analyze"),
                target_area=parsed.get("target_area", "unknown"),
                description=parsed.get("description", user_request),
                original_request=user_request,
                affected_areas=parsed.get("affected_areas", []),
                suggested_files=parsed.get("suggested_files", []),
                requires_database=parsed.get("requires_database", False),
                requires_api=parsed.get("requires_api", False),
                is_ambiguous=parsed.get("is_ambiguous", False),
                clarification_questions=parsed.get("clarification_questions", []),
                assumptions=parsed.get("assumptions", []),
                confidence=parsed.get("confidence", 1.0)
            )
            
            # Yield final validated intent
            yield f"\n\n__INTENT_RESULT__:{intent.model_dump_json()}"
            
        except Exception as e:
            intent = self._create_default_intent(user_request, str(e))
            yield f"\n\n__INTENT_RESULT__:{intent.model_dump_json()}"
    
    async def invoke(self, state: AgentState) -> Dict[str, Any]:
        """
        Invoke the agent as part of the orchestrator workflow.
        
        This method is called by the AgentInvoker and follows
        the standard agent invocation protocol.
        
        Args:
            state: Current agent state (contains artifacts and parameters)
            
        Returns:
            Dict with 'artifacts' key containing structured_intent
        """
        # Extract inputs from state
        artifacts = state.get("artifacts", {})
        parameters = state.get("parameters", {})
        
        # Get user request
        user_request = parameters.get("request", "")
        if not user_request:
            user_request_artifact = artifacts.get("user_request", {})
            user_request = user_request_artifact.get("request", "")
        
        if not user_request:
            return {
                "artifacts": {
                    "structured_intent": self._create_default_intent(
                        "", 
                        "No user request provided"
                    ).model_dump()
                }
            }
        
        # Get optional context
        app_blueprint = artifacts.get("app_blueprint")
        folder_map = artifacts.get("folder_map")
        
        # Classify
        intent = await self.classify(
            user_request=user_request,
            app_blueprint=app_blueprint,
            folder_map=folder_map
        )
        
        return {
            "artifacts": {
                "structured_intent": intent.model_dump()
            }
        }
