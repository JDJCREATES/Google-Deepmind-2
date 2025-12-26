from abc import ABC, abstractmethod
from typing import Dict, Any, Literal
from langchain_core.messages import HumanMessage, SystemMessage
from app.core.llm_factory import LLMFactory
from app.agents.state import AgentState

class BaseAgent(ABC):
    """
    Abstract base class for all ShipS* agents.
    Wraps the Gemini 3 model and enforces standard behavior.
    """
    
    def __init__(self, 
                 name: str, 
                 agent_type: Literal["orchestrator", "planner", "coder", "fixer", "mini"],
                 reasoning_level: Literal["standard", "high"] = "standard"):
        self.name = name
        self.agent_type = agent_type
        self.reasoning_level = reasoning_level
        self.llm = LLMFactory.get_model(agent_type, reasoning_level)
        self.system_prompt = self._get_system_prompt()

    @abstractmethod
    def _get_system_prompt(self) -> str:
        """
        Returns the system prompt for the specific agent.
        Must be implemented by subclasses.
        """
        pass

    @abstractmethod
    async def invoke(self, state: AgentState) -> dict:
        """
        Main entry point for the agent in the LangGraph.
        Process the state and return updates.
        """
        pass

    def get_messages_for_llm(self, state: AgentState) -> list:
        """
        Helper to construct the message history for the LLM.
        Prepends the system prompt.
        """
        messages = [SystemMessage(content=self.system_prompt)]
        
        # Convert state messages to LangChain format if needed
        # Assuming state['messages'] are already dicts or LangChain objects
        # This is a simplification; in production, we'd validate/convert strictly.
        for msg in state['messages']:
            if isinstance(msg, dict):
                 # Simple conversion for demo
                if msg.get('role') == 'user':
                    messages.append(HumanMessage(content=msg.get('content')))
                # Add other roles as needed
            else:
                # Assume it's already a BaseMessage
                messages.append(msg)
                
        return messages

    async def run_llm(self, messages: list) -> str:
        """
        Executes the LLM and returns the string content.
        """
        response = await self.llm.ainvoke(messages)
        return response.content
