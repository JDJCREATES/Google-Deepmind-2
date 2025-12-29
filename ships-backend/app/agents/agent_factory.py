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
from app.agents.tools import (
    PLANNER_TOOLS,
    CODER_TOOLS,
    VALIDATOR_TOOLS,
    FIXER_TOOLS,
)


# Token limits for message trimming (per agent type)
TOKEN_LIMITS = {
    "planner": 30000,   # Planning needs context
    "coder": 20000,     # Coding can be more focused
    "validator": 10000, # Validation is quick
    "fixer": 20000,     # Fixing needs context of errors
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


# System prompts for each agent type
AGENT_PROMPTS = {
    "planner": """You are the Planner for ShipS*, an AI coding system that SHIPS WORKING CODE.

Your job is to:
1. SCAFFOLD the project framework if needed
2. Create an implementation plan for the Coder

STEP 1 - PROJECT SCAFFOLDING (if creating new project):
- `list_directory(".")` to check current state
- If NO package.json exists:
  - `run_terminal_command("npx -y create-vite@latest . --template react-ts")` for Vite/React
  - `run_terminal_command("npm install")`
- If package.json EXISTS, skip scaffolding

STEP 2 - WRITE PLAN FILES:
- `.ships/implementation_plan.md` - Files to create, technical approach
- `.ships/task.md` - Checklist for the Coder

The Coder will ONLY write custom code - scaffolding is YOUR responsibility.

OUTPUT: 
1. Scaffold if needed
2. Write plan files
3. Say "Project ready. Plan saved."
""",

    "coder": """You are the Coder for ShipS*, an AI coding system that SHIPS WORKING CODE.

YOUR ONLY JOB: Use the write_file_to_disk tool to CREATE FILES.

DO NOT just acknowledge the plan. DO NOT say "ready for execution".
You MUST IMMEDIATELY call write_file_to_disk for each file needed.

AVAILABLE TOOL - write_file_to_disk:
- file_path: relative path like "index.html" or "src/App.tsx"
- content: the COMPLETE file content

EXAMPLE - Creating an HTML file:
Call write_file_to_disk with:
  file_path = "index.html"
  content = "<!DOCTYPE html><html>...</html>"

RULES:
1. IMMEDIATELY call write_file_to_disk - no discussion first
2. Write COMPLETE code - no TODOs, no placeholders
3. Create ALL files needed for the task
4. If the user wants a calculator - write the full calculator code

START WRITING FILES NOW using write_file_to_disk.""",

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
        
        # Get token limit for this agent type
        max_tokens = TOKEN_LIMITS.get(agent_type, 20000)
        
        # Create the modern ReAct agent with message trimming
        agent = create_react_agent(
            model=llm,
            tools=tools,
            prompt=prompt,
            checkpointer=checkpointer,
            pre_model_hook=create_message_trimmer(max_tokens),  # Trim messages for token efficiency
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
