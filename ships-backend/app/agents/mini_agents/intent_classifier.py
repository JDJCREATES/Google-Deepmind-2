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


class Scope(str, Enum):
    """Scope of the requested change - helps Planner decide scaffolding."""
    FEATURE = "feature"       # Add to EXISTING project (new files OR modify existing)
    LAYER = "layer"           # Add NEW architectural layer (backend, auth, database to existing frontend)
    PROJECT = "project"       # Create brand NEW project from scratch (full scaffolding)
    FILE = "file"             # Single file operation only


class StructuredIntent(BaseModel):
    """
    The structured output of the Intent Classifier.
    
    This artifact is consumed by all downstream agents to understand
    exactly what the user wants to accomplish.
    """
    # Core classification
    task_type: TaskType = Field(
        description="Primary task type: 'feature' (adding new functionality), 'fix' (debugging/correcting), 'refactor' (improving without behavioral changes), 'modify' (changing existing behavior), 'delete' (removing code), 'question' (seeking information only), 'confirmation' (approving a proposal), 'unclear' (cannot determine)"
    )
    action: ActionType = Field(
        description="Concrete action to take: 'create' (new files/components), 'modify' (edit existing files), 'delete' (remove files/code), 'explain' (provide information only), 'analyze' (review without changes), 'proceed' (continue with current plan)"
    )
    target_area: TargetArea = Field(
        description="Primary codebase area affected: 'frontend' (UI/client), 'backend' (server/API), 'database' (schema/queries), 'full-stack' (both frontend and backend), 'configuration' (build/deploy config), 'documentation' (docs/README), 'testing' (test files), 'system' (pipeline/workflow control), 'unknown' (cannot determine)"
    )
    scope: str = Field(
        default="feature",
        description="Change scope determining scaffolding needs: 'feature' (adding to EXISTING project - new files OR modifying existing), 'layer' (adding entirely NEW architectural layer like backend to frontend-only project), 'project' (brand NEW project from scratch requiring full scaffolding), 'file' (single file operation only)"
    )
    
    # Clarified description
    description: str = Field(
        description="Crystal-clear, actionable description of what to build/fix. Remove ambiguity and add specifics. Example: Instead of 'add auth', use 'Implement email/password authentication with JWT tokens, login form, protected routes, and session persistence'"
    )
    original_request: str = Field(
        description="The exact original user request without modification"
    )
    
    # Predicted impact
    affected_areas: List[str] = Field(
        default_factory=list,
        description="Specific areas/directories that will be modified. Examples: ['src/components/auth/', 'src/stores/', 'src/types/user.ts']. Be as specific as possible based on project structure."
    )
    suggested_files: List[str] = Field(
        default_factory=list,
        description="Concrete file paths to create or modify. Examples: ['src/components/LoginForm.tsx', 'src/hooks/useAuth.ts', 'src/stores/authStore.ts']. Include file extensions and organize by layer (components, hooks, types, stores)."
    )
    
    # Dependencies and constraints
    requires_database: bool = Field(
        default=False,
        description="True if task involves database schema changes, migrations, queries, or database configuration. False for pure UI/logic work."
    )
    requires_api: bool = Field(
        default=False,
        description="True if task needs new API endpoints, API client changes, or backend service modifications. False for frontend-only or static changes."
    )
    
    # Ambiguity handling
    is_ambiguous: bool = Field(
        default=False,
        description="True if the request lacks critical information needed for implementation (unclear requirements, missing specifications, multiple valid interpretations). False if intent is clear and actionable."
    )
    clarification_questions: List[str] = Field(
        default_factory=list,
        description="Specific questions to resolve ambiguity. Ask about: missing requirements, technology choices, scope boundaries, edge case handling. Example: 'Should login support OAuth providers or just email/password?'"
    )
    assumptions: List[str] = Field(
        default_factory=list,
        description="Explicit assumptions made when user didn't specify details. Example: 'Assuming JWT tokens for auth', 'Assuming mobile-responsive design', 'Assuming TypeScript for new files'"
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

CLASSIFICATION GUIDE (task_type + action):
- "create new app" / "generate project" / "scaffold X" → task_type: feature, action: create
- "add feature X" / "add X to app" / "implement X" → task_type: feature, action: modify
- "fix X" / "bug in X" / "X is broken" → task_type: fix, action: modify
- "change X" / "update X" / "modify X" → task_type: modify, action: modify
- "remove X" / "delete X" → task_type: delete, action: delete
- "refactor X" / "clean up X" → task_type: refactor, action: modify
- "what is X" / "how does X work" / "explain X" → task_type: question, action: explain
- "looks good" / "proceed" / "yes" / "go ahead" / "approved" → task_type: confirmation, action: proceed

SCOPE CLASSIFICATION (CRITICAL - helps Planner decide scaffolding):

1. scope: "feature" (DEFAULT - NO scaffolding)
   - Adding to EXISTING project (new components, features, pages, etc)
   - Examples: "add settings menu", "add dark mode", "create a Button component", "add login page"
   - Use when: Project already exists (has package.json, src/, etc)
   
2. scope: "layer" (CONDITIONAL scaffolding)
   - Adding NEW architectural layer to existing project
   - Examples: "add backend" (to frontend-only), "add database", "add authentication system"
   - Use when: Adding major new infrastructure to existing codebase
   
3. scope: "project" (FULL scaffolding)
   - Creating brand NEW project from scratch
   - Examples: "create a todo app", "scaffold a React app", "build a new dashboard"
   - Use when: No existing project, starting fresh
   
4. scope: "file" (NO scaffolding)
   - Single file operation
   - Examples: "create utils.ts", "add a helper file"

SCOPE DECISION LOGIC (ALWAYS follow this order):
1. If folder_map provided AND has entries → scope: "feature" (existing project detected)
2. If user says "create NEW app/project" or "scaffold" → scope: "project"
3. If user says "add backend/auth/database" to frontend → scope: "layer"
4. If user says "add X" (anything else) → scope: "feature" (SAFE DEFAULT)
5. When in doubt → scope: "feature" (never scaffold unless explicitly requested)

AMBIGUITY TRIGGERS (set is_ambiguous=true):
- Request is gibberish or truly nonsensical
- Contradictory requirements (e.g., "create a file but delete it")
- Very short requests without context (< 2 words) e.g. "do it"
- DO NOT mark general "build X" or "create X" tasks as ambiguous.
- DO NOT mark requests as ambiguous just because they are open-ended.
- DO NOT ask "what framework?". Let the Planner decide.

OUTPUT FORMAT:
You MUST output a valid JSON object matching this schema:
{
    "task_type": "feature|fix|refactor|modify|delete|question|confirmation|unclear",
    "action": "create|modify|delete|explain|analyze|proceed",
    "target_area": "frontend|backend|database|full-stack|configuration|documentation|testing|system|unknown",
    "scope": "feature|layer|component|project|file",
    "description": "MUST preserve the user's EXACT request. Add clarifications, but NEVER remove or abstract away specific details.",
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
        folder_map: Optional[Dict[str, Any]] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> StructuredIntent:
        """
        Classify a user request into a structured intent.
        
        This is the main entry point for classification.
        
        Args:
            user_request: The raw user request
            app_blueprint: Optional app blueprint for context
            folder_map: Optional folder structure for context
            config: Optional LangChain config (e.g. to disable callbacks)
            
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
            response = await self.llm.ainvoke(messages, config=config)
            duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            # Parse response
            parsed = self._parse_json_response(response.content)
            
            # Create StructuredIntent
            intent = StructuredIntent(
                task_type=parsed.get("task_type", "unclear"),
                action=parsed.get("action", "analyze"),
                target_area=parsed.get("target_area", "unknown"),
                scope=parsed.get("scope", "feature"),  # NEW: scope field
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
            logger.info(f"[INTENT] 📋 Classified: {intent.task_type}/{intent.action} → {intent.target_area} | scope: {intent.scope} (conf: {intent.confidence:.2f})")
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
