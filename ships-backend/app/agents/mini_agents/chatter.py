"""
ShipS* Chatter Agent

A specialized agent for answering questions about the codebase.
It has READ-ONLY access to the file system to provide accurate, context-aware answers.
"""

from typing import Dict, Any, List, Optional
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.prebuilt import create_react_agent

from app.agents.base.base_agent import BaseAgent
from app.agents.tools.coder import read_file_from_disk, list_directory
from app.artifacts import ArtifactManager

class Chatter(BaseAgent):
    """
    Chatter Agent - The Project Librarian.
    
    Capabilities:
    - Read files
    - List directories
    - Answer technical questions
    - REFUSES to modify code
    
    Uses Gemini Flash for speed/cost, since it only needs to read and summarize.
    """
    
    def __init__(
        self,
        artifact_manager: Optional[ArtifactManager] = None
    ):
        super().__init__(
            name="Chatter",
            agent_type="mini", # Flash model
            reasoning_level="standard",
            artifact_manager=artifact_manager
        )
        
        # Define Read-Only Toolset
        self.tools = [read_file_from_disk, list_directory]
        
    def _get_system_prompt(self, project_path: str = ".") -> str:
        """Build the system prompt with project context."""
        return f"""You are the Chatter Agent for ShipS*, an expert developer assistant.

CONTEXT:
Project Root: {project_path}

YOUR GOAL:
Answer user questions about the specific codebase located at the Project Root.

CAPABILITIES:
1. READ FILES: Use `read_file_from_disk` to inspect code.
2. EXPLORE: Use `list_directory` to see file structure.
3. EXPLAIN: Provide technical, accurate explanations based on ACTUAL code.

RULES:
- You are READ-ONLY. You cannot write, edit, or delete files.
- If asked to change code, explain you cannot and suggest the user say "change X" or "fix X".
- ALWAYS verify your answers by reading the relevant files first. Do not hallucinate.
- Be concise.
"""

    def get_graph(self):
        """
        Return the compiled graph for this agent.
        This allows it to be added as a subgraph in the main AgentGraph,
        enabling full token streaming via astream(subgraphs=True).
        """
        # Dynamic System Prompt
        def prompt_fn(state):
            # Extract artifacts to get project path
            artifacts = state.get("artifacts", {})
            project_path = artifacts.get("project_path", ".")
            
            system_prompt = self._get_system_prompt(project_path)
            
            # Allow user to provide messages
            messages = state.get("messages", [])
            
            return [SystemMessage(content=system_prompt)] + messages

        # Create the graph once
        agent = create_react_agent(
            self.llm, 
            self.tools, 
            prompt=prompt_fn
        )
        return agent

    async def invoke(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Legacy invoke for direct calls (non-streaming).
        """
        agent = self.get_graph()
        return await agent.ainvoke(state)
