import sys
import os
import asyncio

# Add parent dir to path so we can import app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.agents.orchestrator import MasterOrchestrator
from app.agents.planner import PlannerAgent
from app.agents.coder import CoderAgent
from app.agents.fixer import FixerAgent
from app.core.llm_factory import MODEL_FLASH, MODEL_PRO

def verify_agent(agent_class, expected_model_name):
    print(f"Verifying {agent_class.__name__}...")
    try:
        agent = agent_class()
        # Access the underlying chat_model from ChatGoogleGenerativeAI
        actual_model = agent.llm.model
        print(f"  - Model: {actual_model}")
        
        if actual_model == expected_model_name:
            print("  - ✅ Model match")
        else:
            print(f"  - ❌ Model MISMATCH. Expected {expected_model_name}, got {actual_model}")
            
        print("  - ✅ Instantiation successful")
    except Exception as e:
        print(f"  - ❌ Instantiation FAILED: {e}")

if __name__ == "__main__":
    print("Starting Agent Verification...")
    print("------------------------------")
    
    # Verify Orchestrator (Flash)
    verify_agent(MasterOrchestrator, MODEL_FLASH)
    
    # Verify Planner (Pro)
    verify_agent(PlannerAgent, MODEL_PRO)
    
    # Verify Coder (Pro)
    verify_agent(CoderAgent, MODEL_PRO)
    
    # Verify Fixer (Pro)
    verify_agent(FixerAgent, MODEL_PRO)
    
    print("------------------------------")
    print("Verification Complete.")
