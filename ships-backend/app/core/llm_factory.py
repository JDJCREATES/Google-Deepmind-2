import os
from typing import Optional, Literal
from langchain_google_genai import ChatGoogleGenerativeAI

# Model Constants
MODEL_FLASH = "gemini-3-flash-preview"
MODEL_PRO = "gemini-3-pro-preview"

class LLMFactory:
    """
    Factory class to create configured Gemini 3 model instances.
    Enforces the 'No Flash' rule for complex agents while allowing it for simple ones.
    """
    
    @staticmethod
    def get_model(
        agent_type: Literal["orchestrator", "planner", "coder", "fixer", "mini"],
        reasoning_level: Literal["standard", "high"] = "standard"
    ) -> ChatGoogleGenerativeAI:
        """
        Returns a configured ChatGoogleGenerativeAI instance based on the agent type and reasoning level.
        """
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            print("WARNING: GEMINI_API_KEY not found in environment variables.")

        model_name = MODEL_FLASH
        temperature = 0.7
        
        if agent_type in ["orchestrator", "mini"]:
            model_name = MODEL_FLASH
            temperature = 0.5
            
        elif agent_type == "planner":
            model_name = MODEL_PRO
            temperature = 0.7
            
        elif agent_type in ["coder", "fixer"]:
            model_name = MODEL_PRO
            temperature = 0.2
            
        # Basic Safety Settings
        # Using simple dictionary to avoid importing from legacy google.generativeai
        # LangChain handles the conversion for the new google-genai SDK
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
            convert_system_message_to_human=True
        )
        
        return llm

# Global factory instance
llm_factory = LLMFactory()
