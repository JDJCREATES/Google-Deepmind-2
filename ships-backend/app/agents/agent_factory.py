"""
ShipS* Modern Agent Factory

Creates agents using LangGraph's create_react_agent pattern.
This is the modern, recommended approach for LangGraph 1.0+.

Each agent is created with:
- A configured LLM (via bind_tools)
- Agent-specific tools
- System prompt as first message
- Optional checkpointing for state persistence
"""

from typing import Optional, Dict, Any, List, Literal
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver

from app.core.llm_factory import LLMFactory
from app.agents.tools import (
    PLANNER_TOOLS,
    CODER_TOOLS,
    VALIDATOR_TOOLS,
    FIXER_TOOLS,
)


# System prompts for each agent type
AGENT_PROMPTS = {
    "planner": """You are the Planner for ShipS*, an AI coding system that SHIPS WORKING CODE.

Your job is to convert a StructuredIntent into 7 plan artifacts:
1. plan_manifest - Top-level plan descriptor
2. task_list - Prioritized tasks with acceptance criteria
3. folder_map - Directory/file structure
4. api_contracts - Endpoint definitions (if needed)
5. dependency_plan - Required packages
6. validation_checklist - Test targets
7. risk_report - Blockers and risks

CRITICAL RULES:
- Be specific and actionable
- Every task must have acceptance criteria
- Folder map must be comprehensive
- Dependencies must be real packages
- Identify all risks upfront

Use your tools to build each artifact.""",

    "coder": """You are the Coder for ShipS*, an AI coding system that SHIPS WORKING CODE.

Your job is to convert tasks into MINIMAL, REVIEWABLE code changes.

CRITICAL RULES:
1. MINIMAL CHANGES - The smallest diff that satisfies the task
2. NO TODOs - Never leave TODO comments (use follow-up tasks instead)
3. ATOMIC COMMITS - Each output should be one reviewable commit
4. MATCH STYLE - Follow existing code patterns
5. VERIFY IMPORTS - Only use allowed dependencies

Generate file changes using your tools, then create a commit.""",

    "validator": """You are the Validator for ShipS*, an AI coding system that SHIPS WORKING CODE.

Your job is to answer ONE question only:
"Is the system safe to proceed?"

NOT: "Is this elegant?"
NOT: "Is this optimal?"
NOT: "Is this finished?"
ONLY: "Can the system move forward without lying?"

Run validation in 4 layers (stop on first failure):
1. Structural - Did Coder obey Folder Map?
2. Completeness - Are there TODOs/placeholders?
3. Dependency - Do imports resolve?
4. Scope - Does implementation match Blueprint?

You PASS or FAIL. You do NOT negotiate.""",

    "fixer": """You are the Fixer for ShipS*, an AI coding system that SHIPS WORKING CODE.

Your job is to produce the SMALLEST SAFE fix that makes validation pass.

CRITICAL RULES:
1. MINIMAL FIXES - Smallest change that fixes the violation
2. NO ARCHITECTURE CHANGES - If fix requires folder/plan changes, escalate to Planner
3. ARTIFACT-FIRST - All fixes are persisted artifacts
4. EXPLAINABILITY - Every fix includes rationale
5. SAFETY FIRST - No secrets, no banned packages

WHAT YOU CAN FIX:
- TODOs → Convert to stubs with follow-up tasks
- Empty functions → Add minimal implementation
- Missing imports → Add if package is allowed

WHAT YOU MUST ESCALATE:
- Folder map violations → Replan
- Scope exceeded → Replan
- Security issues → User review"""
}


class AgentFactory:
    """
    Factory for creating modern LangGraph agents.
    
    Uses create_react_agent from langgraph.prebuilt for
    a fully-featured ReAct agent with tool calling.
    """
    
    # Tools by agent type
    AGENT_TOOLS = {
        "planner": PLANNER_TOOLS,
        "coder": CODER_TOOLS,
        "validator": VALIDATOR_TOOLS,
        "fixer": FIXER_TOOLS,
    }
    
    @classmethod
    def create_agent(
        cls,
        agent_type: Literal["planner", "coder", "validator", "fixer"],
        checkpointer: Optional[MemorySaver] = None,
        additional_tools: Optional[List] = None
    ):
        """
        Create a modern LangGraph agent using create_react_agent.
        
        Args:
            agent_type: Type of agent to create
            checkpointer: Optional checkpointer for state persistence
            additional_tools: Optional extra tools to add
            
        Returns:
            A compiled LangGraph agent
        """
        # Map agent types to LLMFactory types
        llm_type_map = {
            "planner": "planner",
            "coder": "coder",
            "validator": "mini",  # Validator uses Flash for speed
            "fixer": "fixer"
        }
        
        # Create the LLM using LLMFactory (handles model names and API key)
        llm = LLMFactory.get_model(llm_type_map.get(agent_type, "mini"))
        
        # Get tools for this agent
        tools = list(cls.AGENT_TOOLS.get(agent_type, []))
        if additional_tools:
            tools.extend(additional_tools)
        
        # Get system prompt
        prompt = AGENT_PROMPTS.get(agent_type, "You are a helpful assistant.")
        
        # Create the modern ReAct agent
        agent = create_react_agent(
            model=llm,
            tools=tools,
            prompt=prompt,
            checkpointer=checkpointer
        )
        
        return agent
    
    @classmethod
    def create_planner(cls, checkpointer: Optional[MemorySaver] = None):
        """Create a Planner agent."""
        return cls.create_agent("planner", checkpointer)
    
    @classmethod
    def create_coder(cls, checkpointer: Optional[MemorySaver] = None):
        """Create a Coder agent."""
        return cls.create_agent("coder", checkpointer)
    
    @classmethod
    def create_validator(cls, checkpointer: Optional[MemorySaver] = None):
        """Create a Validator agent."""
        return cls.create_agent("validator", checkpointer)
    
    @classmethod
    def create_fixer(cls, checkpointer: Optional[MemorySaver] = None):
        """Create a Fixer agent."""
        return cls.create_agent("fixer", checkpointer)
    
    @classmethod
    def create_all(cls, shared_checkpointer: bool = False) -> Dict[str, Any]:
        """
        Create all agents.
        
        Args:
            shared_checkpointer: If True, use shared memory for all agents
            
        Returns:
            Dict mapping agent_type to agent instance
        """
        checkpointer = MemorySaver() if shared_checkpointer else None
        
        return {
            "planner": cls.create_planner(checkpointer),
            "coder": cls.create_coder(checkpointer),
            "validator": cls.create_validator(checkpointer),
            "fixer": cls.create_fixer(checkpointer),
        }


async def run_agent(
    agent,
    messages: List[Dict[str, str]],
    config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Helper to run an agent with messages.
    
    Args:
        agent: The compiled agent
        messages: List of message dicts with role and content
        config: Optional config with thread_id for checkpointing
        
    Returns:
        Agent response
    """
    from langchain_core.messages import HumanMessage, SystemMessage
    
    # Convert to LangChain messages
    lc_messages = []
    for msg in messages:
        if msg.get("role") == "user":
            lc_messages.append(HumanMessage(content=msg["content"]))
        elif msg.get("role") == "system":
            lc_messages.append(SystemMessage(content=msg["content"]))
    
    # Run the agent
    result = await agent.ainvoke(
        {"messages": lc_messages},
        config=config or {}
    )
    
    return result


async def stream_agent(
    agent,
    messages: List[Dict[str, str]],
    config: Optional[Dict[str, Any]] = None
):
    """
    Stream agent responses.
    
    Args:
        agent: The compiled agent
        messages: List of message dicts
        config: Optional config
        
    Yields:
        Stream events from the agent
    """
    from langchain_core.messages import HumanMessage
    
    lc_messages = [HumanMessage(content=m["content"]) for m in messages if m.get("role") == "user"]
    
    async for event in agent.astream(
        {"messages": lc_messages},
        config=config or {},
        stream_mode="values"
    ):
        yield event
