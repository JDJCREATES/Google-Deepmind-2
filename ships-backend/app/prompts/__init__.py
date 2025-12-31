"""
ShipS* Agent Prompts

PHILOSOPHY: Prevention > Detection > Repair

Centralized prompt management for all agents.
Each prompt is designed to PREVENT pitfalls before they happen.
"""

from .planner import PLANNER_SYSTEM_PROMPT
from .coder import CODER_SYSTEM_PROMPT
from .validator import VALIDATOR_SYSTEM_PROMPT
from .fixer import FIXER_SYSTEM_PROMPT
from .orchestrator import ORCHESTRATOR_SYSTEM_PROMPT

# Agent name to prompt mapping for easy lookup
AGENT_PROMPTS = {
    "planner": PLANNER_SYSTEM_PROMPT,
    "coder": CODER_SYSTEM_PROMPT,
    "validator": VALIDATOR_SYSTEM_PROMPT,
    "fixer": FIXER_SYSTEM_PROMPT,
    "orchestrator": ORCHESTRATOR_SYSTEM_PROMPT,
}

# Pitfall coverage by agent (for documentation)
PITFALL_COVERAGE = {
    "planner": ["2.1 Naming", "2.2 Duplicates", "2.3 Ignoring existing", "3.2 API contracts", "4.1 Mixed patterns"],
    "coder": ["1.1 TODO", "1.2 Truncated", "1.3 Stubs", "5.1 Error handling", "5.2 Loading", "5.3 Null", "10.1 React"],
    "validator": ["All TIER 1 - detection layer"],
    "fixer": ["Repair layer - fixes what Detection catches"],
}

__all__ = [
    "PLANNER_SYSTEM_PROMPT",
    "CODER_SYSTEM_PROMPT",
    "VALIDATOR_SYSTEM_PROMPT",
    "FIXER_SYSTEM_PROMPT",
    "ORCHESTRATOR_SYSTEM_PROMPT",
    "AGENT_PROMPTS",
    "PITFALL_COVERAGE",
]
