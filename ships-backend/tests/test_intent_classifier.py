"""
Tests for ShipS* Intent Classifier (Request Interpreter)

Tests cover:
- Classification of various request types
- Ambiguity detection
- Streaming output
- Project-aware classification
- Error handling
"""

import pytest
import asyncio
from datetime import datetime
from typing import Dict, Any

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.agents.mini_agents.intent_classifier import (
    IntentClassifier,
    StructuredIntent,
    TaskType,
    ActionType,
    TargetArea,
)


class TestStructuredIntent:
    """Tests for the StructuredIntent model."""
    
    def test_create_intent(self):
        """Test creating a basic StructuredIntent."""
        intent = StructuredIntent(
            task_type=TaskType.FEATURE,
            action=ActionType.CREATE,
            target_area=TargetArea.FRONTEND,
            description="Add a user profile page",
            original_request="add user profile"
        )
        
        assert intent.task_type == TaskType.FEATURE
        assert intent.action == ActionType.CREATE
        assert intent.target_area == TargetArea.FRONTEND
        assert intent.is_ambiguous is False
        assert intent.confidence == 1.0
    
    def test_ambiguous_intent(self):
        """Test creating an ambiguous intent."""
        intent = StructuredIntent(
            task_type=TaskType.UNCLEAR,
            action=ActionType.ANALYZE,
            target_area=TargetArea.UNKNOWN,
            description="Cannot determine",
            original_request="make it better",
            is_ambiguous=True,
            clarification_questions=["What specifically should be improved?"],
            confidence=0.3
        )
        
        assert intent.is_ambiguous is True
        assert len(intent.clarification_questions) == 1
        assert intent.confidence == 0.3
    
    def test_intent_serialization(self):
        """Test intent JSON serialization."""
        intent = StructuredIntent(
            task_type=TaskType.FIX,
            action=ActionType.MODIFY,
            target_area=TargetArea.BACKEND,
            description="Fix login bug",
            original_request="login is broken"
        )
        
        json_str = intent.model_dump_json()
        assert "fix" in json_str
        assert "backend" in json_str
    
    def test_intent_from_dict(self):
        """Test creating intent from dict."""
        data = {
            "task_type": "refactor",
            "action": "modify",
            "target_area": "full-stack",
            "description": "Refactor authentication",
            "original_request": "clean up auth code",
            "affected_areas": ["auth", "api"],
            "confidence": 0.85
        }
        
        intent = StructuredIntent(**data)
        assert intent.task_type == TaskType.REFACTOR
        assert intent.confidence == 0.85
        assert "auth" in intent.affected_areas


class TestIntentClassifierParsing:
    """Tests for JSON parsing in IntentClassifier."""
    
    @pytest.fixture
    def classifier(self):
        """Create classifier with mocked LLM."""
        import unittest.mock as mock
        with mock.patch('app.core.llm_factory.LLMFactory.get_model'):
            return IntentClassifier()
    
    def test_parse_clean_json(self, classifier):
        """Test parsing clean JSON response."""
        response = '{"task_type": "feature", "action": "create"}'
        result = classifier._parse_json_response(response)
        
        assert result["task_type"] == "feature"
        assert result["action"] == "create"
    
    def test_parse_json_in_code_block(self, classifier):
        """Test parsing JSON from markdown code block."""
        response = '''Here's the classification:
```json
{"task_type": "fix", "action": "modify"}
```
'''
        result = classifier._parse_json_response(response)
        assert result["task_type"] == "fix"
    
    def test_parse_json_with_text(self, classifier):
        """Test parsing JSON embedded in text."""
        response = '''Based on analysis:
{"task_type": "refactor", "action": "modify"}
That's my classification.'''
        result = classifier._parse_json_response(response)
        assert result["task_type"] == "refactor"
    
    def test_parse_invalid_json_raises(self, classifier):
        """Test that invalid JSON raises ValueError."""
        response = "This is not JSON at all"
        with pytest.raises(ValueError):
            classifier._parse_json_response(response)


class TestIntentClassifierDefaults:
    """Tests for default intent creation."""
    
    @pytest.fixture
    def classifier(self):
        import unittest.mock as mock
        with mock.patch('app.core.llm_factory.LLMFactory.get_model'):
            return IntentClassifier()
    
    def test_default_intent(self, classifier):
        """Test creating default intent for failed classification."""
        intent = classifier._create_default_intent("test request", "Some error")
        
        assert intent.task_type == TaskType.UNCLEAR
        assert intent.is_ambiguous is True
        assert intent.confidence == 0.0
        assert len(intent.clarification_questions) > 0


class TestIntentClassifierPrompts:
    """Tests for prompt building."""
    
    @pytest.fixture
    def classifier(self):
        import unittest.mock as mock
        with mock.patch('app.core.llm_factory.LLMFactory.get_model'):
            return IntentClassifier()
    
    def test_build_basic_prompt(self, classifier):
        """Test building basic prompt without context."""
        prompt = classifier._build_context_prompt("add login button")
        
        assert "add login button" in prompt
        assert "USER REQUEST:" in prompt
    
    def test_build_prompt_with_blueprint(self, classifier):
        """Test building prompt with app blueprint."""
        blueprint = {"name": "TestApp", "type": "web"}
        prompt = classifier._build_context_prompt(
            "add login", 
            app_blueprint=blueprint
        )
        
        assert "PROJECT CONTEXT:" in prompt
        assert "TestApp" in prompt
    
    def test_build_prompt_with_folder_map(self, classifier):
        """Test building prompt with folder structure."""
        folder_map = {"src": ["components", "pages"]}
        prompt = classifier._build_context_prompt(
            "add login",
            folder_map=folder_map
        )
        
        assert "FOLDER STRUCTURE:" in prompt
        assert "components" in prompt


class TestIntentClassifierSystemPrompt:
    """Tests for system prompt configuration."""
    
    def test_system_prompt_method_exists(self):
        """Test that _get_system_prompt method exists."""
        # Don't instantiate (requires API key), just check the class
        assert hasattr(IntentClassifier, '_get_system_prompt')
    
    def test_system_prompt_content(self):
        """Test that system prompt has expected content."""
        # Create a mock instance to get the prompt
        import unittest.mock as mock
        
        with mock.patch('app.core.llm_factory.LLMFactory.get_model'):
            classifier = IntentClassifier()
            prompt = classifier.system_prompt
            
            assert "feature" in prompt.lower()
            assert "fix" in prompt.lower()
            assert "ambiguous" in prompt.lower()
            assert "json" in prompt.lower()


class TestIntentClassifierInvoke:
    """Tests for the invoke method."""
    
    @pytest.fixture
    def classifier(self):
        import unittest.mock as mock
        with mock.patch('app.core.llm_factory.LLMFactory.get_model'):
            return IntentClassifier()
    
    def test_invoke_signature(self, classifier):
        """Test that invoke method has correct signature."""
        import inspect
        sig = inspect.signature(classifier.invoke)
        params = list(sig.parameters.keys())
        assert 'state' in params
    
    def test_classify_signature(self, classifier):
        """Test that classify method has correct signature."""
        import inspect
        sig = inspect.signature(classifier.classify)
        params = list(sig.parameters.keys())
        assert 'user_request' in params
        assert 'app_blueprint' in params
        assert 'folder_map' in params
    
    def test_streaming_signature(self, classifier):
        """Test that classify_streaming method exists."""
        assert hasattr(classifier, 'classify_streaming')


# Run with: py -m pytest tests/test_intent_classifier.py -v
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
