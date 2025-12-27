"""
ShipS* Base Agent

Abstract base class for all agents in the ShipS* system. Provides:
- Gemini 3 model integration via LLMFactory
- Artifact system integration for coordination and logging
- Common message handling and LLM execution utilities
- Structured error handling and performance tracking

All concrete agents (Orchestrator, Planner, Coder, Fixer, Mini-Agents) 
inherit from this class.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Any, Literal, Optional
import time

from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

from app.core.llm_factory import LLMFactory
from app.graphs.state import AgentState
from app.artifacts import (
    ArtifactManager,
    PatternRegistry,
    ContractDefinitions,
    QualityGateResults,
    AgentType,
    AgentLogEntry,
)


class BaseAgent(ABC):
    """
    Abstract base class for all ShipS* agents.
    
    This class provides the foundation for all agents in the system,
    handling model initialization, artifact management, and common
    utilities for LLM interaction.
    
    Attributes:
        name: Human-readable name of the agent
        agent_type: Type classification for model selection
        reasoning_level: 'standard' or 'high' for Deep Think
        llm: The configured LangChain LLM instance
        artifact_manager: Optional manager for reading/writing artifacts
        
    Example:
        class MyAgent(BaseAgent):
            def __init__(self):
                super().__init__(
                    name="MyAgent",
                    agent_type="mini",
                    reasoning_level="standard"
                )
            
            def _get_system_prompt(self) -> str:
                return "You are a helpful assistant."
            
            async def invoke(self, state: AgentState) -> dict:
                # Implementation
                pass
    """
    
    # Mapping from agent_type to AgentType enum for artifact logging
    _AGENT_TYPE_MAP: Dict[str, AgentType] = {
        "orchestrator": AgentType.ORCHESTRATOR,
        "planner": AgentType.PLANNER,
        "coder": AgentType.CODER,
        "fixer": AgentType.FIXER,
        "mini": AgentType.VALIDATOR,  # Default for mini-agents
    }
    
    def __init__(
        self, 
        name: str, 
        agent_type: Literal["orchestrator", "planner", "coder", "fixer", "mini"],
        reasoning_level: Literal["standard", "high"] = "standard",
        artifact_manager: Optional[ArtifactManager] = None
    ):
        """
        Initialize the base agent.
        
        Args:
            name: Human-readable name for the agent
            agent_type: Type for model selection and logging
            reasoning_level: 'standard' or 'high' (Deep Think)
            artifact_manager: Optional artifact manager for coordination
        """
        self.name = name
        self.agent_type = agent_type
        self.reasoning_level = reasoning_level
        self.llm = LLMFactory.get_model(agent_type, reasoning_level)
        self.system_prompt = self._get_system_prompt()
        self._artifact_manager = artifact_manager
        
        # Get the enum type for logging
        self._log_agent_type = self._AGENT_TYPE_MAP.get(
            agent_type, 
            AgentType.VALIDATOR
        )
    
    @property
    def artifact_manager(self) -> Optional[ArtifactManager]:
        """Get the artifact manager if available."""
        return self._artifact_manager
    
    @artifact_manager.setter
    def artifact_manager(self, manager: ArtifactManager) -> None:
        """Set the artifact manager."""
        self._artifact_manager = manager
    
    @abstractmethod
    def _get_system_prompt(self) -> str:
        """
        Returns the system prompt for the specific agent.
        
        Must be implemented by subclasses to define the agent's
        personality, capabilities, and constraints.
        
        Returns:
            The system prompt string
        """
        pass
    
    @abstractmethod
    async def invoke(self, state: AgentState) -> dict:
        """
        Main entry point for the agent in the LangGraph.
        
        Process the current state and return updates to be merged
        into the shared state.
        
        Args:
            state: Current agent state from the graph
            
        Returns:
            Dictionary of state updates
        """
        pass
    
    def get_messages_for_llm(self, state: AgentState) -> list:
        """
        Construct the message history for the LLM.
        
        Prepends the system prompt and converts state messages
        to LangChain message format.
        
        Args:
            state: Current agent state
            
        Returns:
            List of LangChain message objects
        """
        messages = [SystemMessage(content=self.system_prompt)]
        
        for msg in state.get('messages', []):
            if isinstance(msg, dict):
                role = msg.get('role', '')
                content = msg.get('content', '')
                
                if role == 'user':
                    messages.append(HumanMessage(content=content))
                elif role == 'assistant':
                    messages.append(AIMessage(content=content))
                # Skip system messages as we already have our own
            else:
                # Assume it's already a BaseMessage
                messages.append(msg)
        
        return messages
    
    async def run_llm(self, messages: list) -> str:
        """
        Execute the LLM and return the response content.
        
        Args:
            messages: List of LangChain messages
            
        Returns:
            The LLM response as a string
        """
        response = await self.llm.ainvoke(messages)
        return response.content
    
    async def run_llm_with_logging(
        self, 
        messages: list,
        action: str,
        input_summary: Optional[str] = None
    ) -> tuple[str, Optional[AgentLogEntry]]:
        """
        Execute the LLM with automatic logging to artifacts.
        
        This method wraps run_llm and automatically logs the action
        to the agent conversation log if an artifact manager is available.
        
        Args:
            messages: List of LangChain messages
            action: Action description for logging
            input_summary: Optional summary of input for the log
            
        Returns:
            Tuple of (response_content, log_entry or None)
        """
        start_time = time.time()
        
        try:
            response = await self.run_llm(messages)
            duration_ms = int((time.time() - start_time) * 1000)
            
            log_entry = None
            if self._artifact_manager:
                log_entry = self._artifact_manager.log_agent_action(
                    agent=self._log_agent_type,
                    action=action,
                    input_summary=input_summary,
                    output_summary=response[:200] + "..." if len(response) > 200 else response,
                    duration_ms=duration_ms
                )
            
            return response, log_entry
            
        except Exception as e:
            # Log the error if possible
            if self._artifact_manager:
                self._artifact_manager.log_agent_action(
                    agent=self._log_agent_type,
                    action=f"{action}_error",
                    input_summary=input_summary,
                    output_summary=str(e)
                )
            raise
    
    # =========================================================================
    # ARTIFACT HELPER METHODS
    # =========================================================================
    
    def get_pattern_registry(self) -> Optional[PatternRegistry]:
        """
        Load the pattern registry if artifact manager is available.
        
        Returns:
            PatternRegistry instance or None
        """
        if self._artifact_manager:
            return self._artifact_manager.get_pattern_registry()
        return None
    
    def get_contract_definitions(self) -> Optional[ContractDefinitions]:
        """
        Load contract definitions if artifact manager is available.
        
        Returns:
            ContractDefinitions instance or None
        """
        if self._artifact_manager:
            return self._artifact_manager.get_contract_definitions()
        return None
    
    def get_quality_gates(self) -> Optional[QualityGateResults]:
        """
        Load quality gate results if artifact manager is available.
        
        Returns:
            QualityGateResults instance or None
        """
        if self._artifact_manager:
            return self._artifact_manager.get_quality_gate_results()
        return None
    
    def log_action(
        self,
        action: str,
        input_summary: Optional[str] = None,
        output_summary: Optional[str] = None,
        reasoning: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> Optional[AgentLogEntry]:
        """
        Log an action to the agent conversation log.
        
        Args:
            action: Action type (e.g., 'generated_code', 'validation_failed')
            input_summary: Optional summary of input
            output_summary: Optional summary of output
            reasoning: Optional reasoning for the action
            details: Optional additional details
            
        Returns:
            AgentLogEntry if logged, None otherwise
        """
        if self._artifact_manager:
            log = self._artifact_manager.get_agent_log()
            entry = log.log(
                agent=self._log_agent_type,
                action=action,
                input_summary=input_summary,
                output_summary=output_summary,
                reasoning=reasoning,
                details=details
            )
            self._artifact_manager.save_agent_log(log)
            return entry
        return None
    
    def update_quality_gate(
        self,
        gate_name: str,
        passed: bool,
        issues: Optional[list[str]] = None
    ) -> None:
        """
        Update a quality gate check result.
        
        Args:
            gate_name: Name of the quality gate
            passed: Whether the check passed
            issues: List of issues if failed
        """
        if not self._artifact_manager:
            return
            
        from app.artifacts import GateCheck, GateStatus
        
        gates = self._artifact_manager.get_quality_gate_results()
        gate = gates.get_gate(gate_name)
        
        if not gate:
            gate = gates.add_gate(gate_name)
        
        check = GateCheck(
            name=f"{self.name} check",
            passed=passed,
            issues=issues or []
        )
        gate.run_checks([check])
        gates.update_proceed_status()
        
        self._artifact_manager.save_quality_gate_results(gates)
