from app.agents.base_agent import BaseAgent
from app.agents.state import AgentState

class FixerAgent(BaseAgent):
    """
    Fixes validation errors, build issues, and bugs.
    """
    
    def __init__(self):
        super().__init__(
            name="Fixer",
            agent_type="fixer",
            reasoning_level="high"
        )
        
    def _get_system_prompt(self) -> str:
        return """You are the Fixer. Apply MINIMAL, SURGICAL fixes.

CRITICAL RULES:
1. Fix ONLY the reported issue
2. Change as little code as possible
3. Preserve existing functionality
4. Never introduce new bugs
5. Verify fix resolves the error
"""

    async def invoke(self, state: AgentState) -> dict:
        messages = self.get_messages_for_llm(state)
        response = await self.run_llm(messages)
        return {"messages": [response]}
