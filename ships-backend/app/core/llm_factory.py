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
        
        # Configure based on agent type (Gemini 3 Flash optimized)
        # thinking_level: minimal (fast) < low < medium < high (deep reasoning)
        # NOTE: Gemini 3 recommends temperature=1.0 - changing can cause loops/degraded performance
        if agent_type == "mini":
            # Fast validation - minimal reasoning
            model_name = MODEL_FLASH
            temperature = 1.0  # Per Gemini 3 guidance
            thinking_level = "minimal"
            
        elif agent_type == "orchestrator":
            # Routing needs solid reasoning, not max
            model_name = MODEL_FLASH
            temperature = 1.0  # Per Gemini 3 guidance
            thinking_level = "medium"
            
        elif agent_type == "planner":
            # Planning needs high reasoning for architecture decisions
            model_name = MODEL_FLASH
            temperature = 1.0  # Per Gemini 3 guidance
            thinking_level = "high"  # Upgraded from medium for better plans
            
        elif agent_type == "coder":
            # Code generation needs high reasoning for correctness
            model_name = MODEL_FLASH
            temperature = 1.0  # Per Gemini 3 guidance
            thinking_level = "high"
            
        elif agent_type == "fixer":
            # Fixing bugs needs high reasoning
            model_name = MODEL_FLASH
            temperature = 1.0  # Per Gemini 3 guidance
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
            # thinking_level passed via bind() to avoid Pydantic errors in older libs
            cached_content=cached_content, 
            max_retries=30,
        )
        
        # Bind the thinking configuration
        # Matches Gemini 3 structure: generation_config={"thinking_config": {"thinking_level": ...}}
        if thinking_level in ["low", "medium", "high", "minimal"]:
             return llm.bind(generation_config={"thinking_config": {"thinking_level": thinking_level}})
        
        return llm


# Global factory instance
llm_factory = LLMFactory()

