from app.agents.base.base_agent import BaseAgent
from app.agents.state import AgentState

class PlannerAgent(BaseAgent):
    """
    Analyzes the codebase and creates detailed implementation plans.
    """
    
    def __init__(self):
        super().__init__(
            name="Planner",
            agent_type="planner",
            reasoning_level="standard"
        )
        
    def _get_system_prompt(self) -> str:
        return """You are the Planner for ShipS*. Your job is to create EXECUTABLE plans.

CRITICAL RULES:
1. ALWAYS analyze the existing codebase first
2. Extract and ENFORCE existing patterns
3. Plans must be step-by-step, file-by-file
4. Define all API contracts UPFRONT

Create a plan that:
- Lists all files to create/modify
- Specifies exact naming conventions to use
- Defines API contracts between frontend/backend
- Identifies dependencies to add
"""

    async def invoke(self, state: AgentState) -> dict:
        messages = self.get_messages_for_llm(state)
        response = await self.run_llm(messages)
        
        return {
            "messages": [response],
            "plan": {"content": response} # Simplification for scaffold
        }
