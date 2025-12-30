"""
ShipS* Modern Agent Factory

Creates agents using LangGraph's create_react_agent pattern.
This is the modern, recommended approach for LangGraph 1.0+.

Each agent is created with:
- A configured LLM (via bind_tools)
- Agent-specific tools
- System prompt as first message
- Optional checkpointing for state persistence
- Message trimming to control token usage
"""

from typing import Optional, Dict, Any, List, Literal
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import trim_messages
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver

from app.core.llm_factory import LLMFactory
from app.agents.tools.planner import PLANNER_TOOLS
from app.agents.tools.coder import CODER_TOOLS
from app.agents.tools.validator import VALIDATOR_TOOLS
from app.agents.tools.fixer import FIXER_TOOLS


# Token limits for message trimming (per agent type)
TOKEN_LIMITS = {
    "planner": 15000,   # Planning needs context
    "coder": 10000,      # Coding focuses in tight loop: plan -> file -> done
    "validator": 6000,  # Validation is quick
    "fixer": 8000,      # Fixing needs context of errors
}


def create_message_trimmer(max_tokens: int = 20000):
    """
    Create a pre_model_hook that trims messages to stay under token limit.
    
    Args:
        max_tokens: Maximum tokens to keep in message history
        
    Returns:
        A callable pre_model_hook function
    """
    def pre_model_hook(state):
        """Trim messages before each LLM call to control tokens."""
        messages = state.get("messages", [])
        
        # Use trim_messages to keep most recent, staying under limit
        # Token approximation: ~4 characters = 1 token
        trimmed = trim_messages(
            messages,
            strategy="last",
            max_tokens=max_tokens,
            token_counter=lambda msgs: sum(len(str(m.content)) // 4 for m in msgs),
            start_on="human",   # Keep starting from a human message
            include_system=True,
        )
        
        # Return trimmed messages under llm_input_messages key
        # This sends trimmed to LLM without modifying state
        return {"llm_input_messages": trimmed}
    
    return pre_model_hook


# Import prompts from centralized prompts module
from app.prompts import AGENT_PROMPTS



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
        additional_tools: Optional[List] = None,
        override_system_prompt: Optional[str] = None
    ):
        """
        Create a modern LangGraph agent using create_react_agent.
        
        Args:
            agent_type: Type of agent to create
            checkpointer: Optional checkpointer for state persistence
            additional_tools: Optional extra tools to add
            override_system_prompt: Optional dynamic system prompt to use
            
        Returns:
            A compiled LangGraph agent
        """
        # Map agent types to LLMFactory types
        llm_type_map = {
            "planner": "planner",
            "coder": "coder",
            "validator": "mini",  # Validator uses Flash for speed
            "planner": "planner",
            "coder": "coder",
            "validator": "mini",  # Validator uses Flash for speed
            "fixer": "fixer",
            "orchestrator": "mini" # Orchestrator uses fast reasoning
        }
        
        # Create the LLM using LLMFactory (handles model names and API key)
        llm = LLMFactory.get_model(llm_type_map.get(agent_type, "mini"))
        
        # Get tools for this agent
        tools = list(cls.AGENT_TOOLS.get(agent_type, []))
        if additional_tools:
            tools.extend(additional_tools)
        
        # Get system prompt (dynamic override or static default)
        prompt = override_system_prompt or AGENT_PROMPTS.get(agent_type, "You are a helpful assistant.")
        
        # Get token limit for this agent type
        max_tokens = TOKEN_LIMITS.get(agent_type, 20000)
        
        # Create the modern ReAct agent with message trimming
        # Note: Sequential tool execution is enforced via prompt constraints
        # (Gemini API does not support parallel_tool_calls parameter)
        agent = create_react_agent(
            model=llm,
            tools=tools,
            prompt=prompt,
            checkpointer=checkpointer,
            # trim messages to keep context under control
            pre_model_hook=create_message_trimmer(max_tokens),
            # prevent infinite loops
            # Note: newer LangGraph versions support recursion_limit in create_react_agent
            debug=False,
        )
        # Note: recursion limit is set in invoke/stream config, but can be defaulted here in newer versions.
        # For LangGraph prebuilt, recursion_limit is a runtime config, not compile time.
        # We'll set it in run_agent instead.
        
        return agent
        
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
    def create_orchestrator(cls, checkpointer: Optional[MemorySaver] = None, override_system_prompt: Optional[str] = None):
        """Create an Orchestrator agent."""
        return cls.create_agent("orchestrator", checkpointer, override_system_prompt=override_system_prompt)
    
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
    # Enforce recursion limit to prevent token explosions
    run_config = config or {}
    if "recursion_limit" not in run_config:
        run_config["recursion_limit"] = 15

    result = await agent.ainvoke(
        {"messages": lc_messages},
        config=run_config
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
    
    # Enforce recursion limit
    run_config = config or {}
    if "recursion_limit" not in run_config:
        run_config["recursion_limit"] = 15

    async for event in agent.astream(
        {"messages": lc_messages},
        config=run_config,
        stream_mode="values"
    ):
        yield event
