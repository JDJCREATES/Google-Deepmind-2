from app.agents.base.base_agent import BaseAgent
from app.agents.state import AgentState
from typing import Literal

class MasterOrchestrator(BaseAgent):
    """
    The central intelligence of the ShipS* system.
    Routes tasks, manages state, and strictly enforces quality gates.
    """
    
    def __init__(self):
        super().__init__(
            name="Orchestrator",
            agent_type="orchestrator",
            reasoning_level="standard"
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
- If NEW REQUEST -> Route to PLANNER
- If PLAN APPROVED -> Route to CODER
- If VALIDATION FAILS -> Route to FIXER (max 3 attempts)
- If BUILD FAILS -> Route to FIXER
- If ALL CHECKS PASS -> Mark COMPLETE

You must return a structured decision on the next step.
"""

    async def invoke(self, state: AgentState) -> dict:
        """
        Decides the next node in the graph based on the current state.
        """
        # Construction of the prompt with current context
        messages = self.get_messages_for_llm(state)
        
        # Add specific context about the current state to help routing
        # (Simulating usage of tools indirectly via context injection for now)
        context = f"""
        Current Task: {state.get('current_task', 'None')}
        Validation Results: {state.get('validation_results', 'None')}
        Error: {state.get('error', 'None')}
        """
        
        messages.append({"role": "user", "content": f"Context Update:\n{context}\n\nWhat is your next move?"})
        
        response = await self.run_llm(messages)
        
        # In a real implementation, we would parse structured output (JSON) from the LLM 
        # to determine the next node cleanly. For scaffolding, we'll store the raw decision.
        
        return {
            "messages": [response],
            "agent_scratchpad": {"orchestrator_decision": response}
        }
