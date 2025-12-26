from app.agents.base.base_agent import BaseAgent
from app.agents.state import AgentState

class CoderAgent(BaseAgent):
    """
    Generates production-ready code based on the Planner's specs.
    """
    
    def __init__(self):
        super().__init__(
            name="Coder",
            agent_type="coder",
            reasoning_level="high"
        )
        
    def _get_system_prompt(self) -> str:
        return """You are the Coder for ShipS*. You write COMPLETE, PRODUCTION-READY code.

ABSOLUTE RULES:
1. NEVER write TODO, FIXME, PLACEHOLDER, or stub implementations
2. NEVER truncate functions - write them completely
3. ALWAYS include error handling (try/catch on async)
4. ALWAYS add loading states for async UI components
5. ALWAYS follow the patterns provided

Generate COMPLETE code.
"""

    async def invoke(self, state: AgentState) -> dict:
        messages = self.get_messages_for_llm(state)
        response = await self.run_llm(messages)
        return {"messages": [response]}
