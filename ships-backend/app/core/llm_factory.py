"""
LLM Factory for ShipS* Agents

Creates configured Gemini 3 model instances with appropriate thinking levels.
Gemini 3 Pro/Flash support `thinking_level` parameter for built-in reasoning.

thinking_level options:
- 'high': Maximum reasoning depth (Planner, Coder, Fixer)
- 'low': Fast responses (Orchestrator, Mini-agents)
- 'medium': Balanced (Flash only)
- 'minimal': Least reasoning (Flash only)
"""

import os
from typing import Literal
from langchain_google_genai import ChatGoogleGenerativeAI

# Model Constants
MODEL_FLASH = "gemini-3-flash-preview"
MODEL_PRO = "gemini-3-pro-preview"


class LLMFactory:
    """
    Factory class to create configured Gemini 3 model instances.
    
    Enforces model selection based on agent type and configures
    appropriate thinking_level for Gemini 3's built-in reasoning.
    """
    
    @staticmethod
    def get_model(
        agent_type: Literal["orchestrator", "planner", "coder", "fixer", "mini"],
        reasoning_level: Literal["standard", "high"] = "standard",
        cached_content: str = None  # Explicit caching support
    ) -> ChatGoogleGenerativeAI:
        """
        Returns a configured ChatGoogleGenerativeAI instance.
        
        Args:
            agent_type: Type of agent for model/config selection
            reasoning_level: 'standard' or 'high' for deep thinking
            
        Returns:
            Configured ChatGoogleGenerativeAI instance with thinking_level
        """
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            print("WARNING: GEMINI_API_KEY not found in environment variables.")

        # Default configuration
        model_name = MODEL_FLASH
        temperature = 0.7
        thinking_level = "low"
        
        # Configure based on agent type
        if agent_type == "mini":
            # Fast validation - use Flash with low reasoning
            model_name = MODEL_FLASH
            temperature = 0.5
            thinking_level = "low"
            
        elif agent_type == "orchestrator":
            # Orchestrator needs DEEP reasoning for routing decisions
            model_name = MODEL_FLASH
            temperature = 0.5
            thinking_level = "high"
            
        elif agent_type == "planner":
            # Complex planning requires deep reasoning
            model_name = MODEL_FLASH
            temperature = 0.7
            thinking_level = "high"
            
        elif agent_type in ["coder", "fixer"]:
            # Code generation/fixing needs careful reasoning
            model_name = MODEL_FLASH
            temperature = 0.2
            thinking_level = "high"
        
        # Override if explicit high reasoning requested
        if reasoning_level == "high":
            thinking_level = "high"
            
        # Safety Settings
        safety_settings = {
           "HARM_CATEGORY_HARASSMENT": "BLOCK_ONLY_HIGH",
           "HARM_CATEGORY_HATE_SPEECH": "BLOCK_ONLY_HIGH",
           "HARM_CATEGORY_SEXUALLY_EXPLICIT": "BLOCK_ONLY_HIGH",
           "HARM_CATEGORY_DANGEROUS_CONTENT": "BLOCK_ONLY_HIGH",
        }

        llm = ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=api_key,
            temperature=temperature,
            safety_settings=safety_settings,
            convert_system_message_to_human=True,
            # Gemini 3 thinking_level for built-in reasoning
            thinking_level=thinking_level,
            cached_content=cached_content, # Pass explicit cache name
            max_retries=30, # Aggressive retries for Hackathon rate limits
        )
        
        return llm


# Global factory instance
llm_factory = LLMFactory()

