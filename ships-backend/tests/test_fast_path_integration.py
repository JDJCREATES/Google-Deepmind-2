"""
Integration Tests for Fast-Path Routing

Tests the complete flow from user input → IntentClassifier → ConversationalRouter → Graph
to ensure no regressions in existing engineering workflows.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from app.graphs.agent_graph import orchestrator_node, AgentGraphState
from app.agents.mini_agents.intent_classifier import StructuredIntent


class TestFastPathIntegration:
    """Test integration of fast-path routing in orchestrator_node."""
    
    @pytest.mark.asyncio
    async def test_question_bypasses_deterministic_router(self):
        """Questions should route to chat_setup without hitting DeterministicRouter."""
        state = {
            "phase": "planning",
            "messages": [{"role": "user", "content": "What does Button.tsx do?"}],
            "artifacts": {
                "project_path": "/test/project"
            },
            "loop_detection": {}
        }
        
        # Mock IntentClassifier to return question intent
        with patch("app.graphs.agent_graph.IntentClassifier") as MockClassifier:
            mock_instance = MockClassifier.return_value
            mock_instance.classify = AsyncMock(return_value=StructuredIntent(
                task_type="question",
                action="explain",
                target_area="frontend",
                description="What does Button.tsx do?",
                original_request="What does Button.tsx do?",
                confidence=0.95
            ))
            
            result = await orchestrator_node(state)
            
            # Should route to chat_setup
            assert result["phase"] == "chat_setup"
            assert result["routing_metadata"]["fast_path"] is True
            assert result["routing_metadata"]["route_type"] == "conversational"
    
    @pytest.mark.asyncio
    async def test_feature_uses_deterministic_router(self):
        """Feature requests should use DeterministicRouter (no regression)."""
        state = {
            "phase": "planning",
            "messages": [{"role": "user", "content": "Add dark mode"}],
            "artifacts": {
                "project_path": "/test/project"
            },
            "loop_detection": {}
        }
        
        with patch("app.graphs.agent_graph.IntentClassifier") as MockClassifier:
            mock_instance = MockClassifier.return_value
            mock_instance.classify = AsyncMock(return_value=StructuredIntent(
                task_type="feature",
                action="create",
                target_area="frontend",
                description="Add dark mode toggle",
                original_request="Add dark mode",
                confidence=0.95
            ))
            
            # Mock DeterministicRouter
            with patch("app.graphs.agent_graph.DeterministicRouter") as MockRouter:
                mock_router = MockRouter.return_value
                mock_router.route = Mock(return_value=Mock(
                    next_phase="planner",
                    reason="No plan exists - need planning",
                    requires_llm=False,
                    gate_result=None,
                    metadata={"loop_detection": {"last_node": None, "consecutive_calls": 0}}
                ))
                
                result = await orchestrator_node(state)
                
                # Should route to planner via DeterministicRouter
                assert result["phase"] == "planner"
                # Should NOT be fast-path
                assert result.get("routing_metadata", {}).get("fast_path") is not True


class TestFallbackIntentFix:
    """Test that fallback intent is now 'unclear' instead of 'feature'."""
    
    @pytest.mark.asyncio
    async def test_classification_failure_routes_to_chat(self):
        """When IntentClassifier fails, should default to 'unclear' and route to chat."""
        state = {
            "phase": "planning",
            "messages": [{"role": "user", "content": "test"}],
            "artifacts": {},
            "loop_detection": {}
        }
        
        with patch("app.graphs.agent_graph.IntentClassifier") as MockClassifier:
            mock_instance = MockClassifier.return_value
            # Simulate classification failure
            mock_instance.classify = AsyncMock(side_effect=Exception("Classification failed"))
            
            result = await orchestrator_node(state)
            
            # Should route to chat_setup (because fallback is now 'unclear')
            assert result["phase"] == "chat_setup"
            assert result["routing_metadata"]["fast_path"] is True


class TestIntentLockingBehavior:
    """Test that intent locking works correctly for different task types."""
    
    @pytest.mark.asyncio
    async def test_question_clears_intent_lock(self):
        """Questions should clear intent_classified flag."""
        state = {
            "phase": "planning",
            "messages": [{"role": "user", "content": "What does this do?"}],
            "artifacts": {},
            "loop_detection": {}
        }
        
        with patch("app.graphs.agent_graph.IntentClassifier") as MockClassifier:
            mock_instance = MockClassifier.return_value
            mock_instance.classify = AsyncMock(return_value=StructuredIntent(
                task_type="question",
                action="explain",
                target_area="unknown",
                description="What does this do?",
                original_request="What does this do?",
                confidence=0.90
            ))
            
            result = await orchestrator_node(state)
            
            # intent_classified should be False (cleared for re-classification)
            assert result["artifacts"]["intent_classified"] is False
    
    @pytest.mark.asyncio
    async def test_feature_keeps_intent_locked(self):
        """Feature requests should keep intent_classified=True."""
        state = {
            "phase": "planning",
            "messages": [{"role": "user", "content": "Add auth"}],
            "artifacts": {},
            "loop_detection": {}
        }
        
        with patch("app.graphs.agent_graph.IntentClassifier") as MockClassifier:
            mock_instance = MockClassifier.return_value
            mock_instance.classify = AsyncMock(return_value=StructuredIntent(
                task_type="feature",
                action="create",
                target_area="full-stack",
                description="Add authentication system",
                original_request="Add auth",
                confidence=0.95
            ))
            
            with patch("app.graphs.agent_graph.DeterministicRouter") as MockRouter:
                mock_router = MockRouter.return_value
                mock_router.route = Mock(return_value=Mock(
                    next_phase="planner",
                    reason="Need planning",
                    requires_llm=False,
                    gate_result=None,
                    metadata={"loop_detection": {"last_node": None, "consecutive_calls": 0}}
                ))
                
                result = await orchestrator_node(state)
                
                # intent_classified should remain True (locked)
                assert result["artifacts"]["intent_classified"] is True


class TestEndToEndScenarios:
    """End-to-end integration tests with realistic user journeys."""
    
    @pytest.mark.asyncio
    async def test_question_then_feature_journey(self):
        """
        Scenario:
        1. User asks "What does Button do?" → Chat
        2. User says "Add dark mode" → Planner
        """
        # First message: Question
        state1 = {
            "phase": "planning",
            "messages": [{"role": "user", "content": "What does Button do?"}],
            "artifacts": {"project_path": "/test"},
            "loop_detection": {}
        }
        
        with patch("app.graphs.agent_graph.IntentClassifier") as MockClassifier:
            mock_instance = MockClassifier.return_value
            mock_instance.classify = AsyncMock(return_value=StructuredIntent(
                task_type="question",
                action="explain",
                target_area="frontend",
                description="Explain Button component",
                original_request="What does Button do?",
                confidence=0.95
            ))
            
            result1 = await orchestrator_node(state1)
            
            assert result1["phase"] == "chat_setup"
            assert result1["artifacts"]["intent_classified"] is False  # Cleared
        
        # Second message: Feature request (new classification)
        state2 = {
            "phase": "planning",
            "messages": [
                {"role": "user", "content": "What does Button do?"},
                {"role": "assistant", "content": "Button is a reusable component..."},
                {"role": "user", "content": "Add dark mode"}
            ],
            "artifacts": {"project_path": "/test"},
            "loop_detection": {}
        }
        
        with patch("app.graphs.agent_graph.IntentClassifier") as MockClassifier:
            mock_instance = MockClassifier.return_value
            mock_instance.classify = AsyncMock(return_value=StructuredIntent(
                task_type="feature",
                action="create",
                target_area="frontend",
                description="Add dark mode toggle",
                original_request="Add dark mode",
                confidence=0.92
            ))
            
            with patch("app.graphs.agent_graph.DeterministicRouter") as MockRouter:
                mock_router = MockRouter.return_value
                mock_router.route = Mock(return_value=Mock(
                    next_phase="planner",
                    reason="Need planning",
                    requires_llm=False,
                    gate_result=None,
                    metadata={"loop_detection": {"last_node": None, "consecutive_calls": 0}}
                ))
                
                result2 = await orchestrator_node(state2)
                
                assert result2["phase"] == "planner"
                assert result2["artifacts"]["intent_classified"] is True  # Locked


class TestNoRegressions:
    """Verify existing workflows continue to work correctly."""
    
    @pytest.mark.asyncio
    async def test_existing_feature_workflow_unchanged(self):
        """Existing feature → planner → coder workflow should work unchanged."""
        state = {
            "phase": "planning",
            "messages": [{"role": "user", "content": "Create a todo app"}],
            "artifacts": {},
            "loop_detection": {}
        }
        
        with patch("app.graphs.agent_graph.IntentClassifier") as MockClassifier:
            mock_instance = MockClassifier.return_value
            mock_instance.classify = AsyncMock(return_value=StructuredIntent(
                task_type="feature",
                action="create",
                target_area="full-stack",
                scope="project",
                description="Create a todo app with React frontend",
                original_request="Create a todo app",
                confidence=0.95
            ))
            
            with patch("app.graphs.agent_graph.DeterministicRouter") as MockRouter:
                mock_router = MockRouter.return_value
                mock_router.route = Mock(return_value=Mock(
                    next_phase="planner",
                    reason="No plan exists",
                    requires_llm=False,
                    gate_result=None,
                    metadata={"loop_detection": {"last_node": None, "consecutive_calls": 0}}
                ))
                
                result = await orchestrator_node(state)
                
                # Should route to planner (no regression)
                assert result["phase"] == "planner"
                assert "DeterministicRouter" in result["routing_metadata"]["reason"] or \
                       "Engineering task" in result["routing_metadata"]["reason"]
    
    @pytest.mark.asyncio
    async def test_fix_workflow_unchanged(self):
        """Fix requests should continue using engineering pipeline."""
        state = {
            "phase": "planning",
            "messages": [{"role": "user", "content": "Fix the login bug"}],
            "artifacts": {"project_path": "/test"},
            "loop_detection": {}
        }
        
        with patch("app.graphs.agent_graph.IntentClassifier") as MockClassifier:
            mock_instance = MockClassifier.return_value
            mock_instance.classify = AsyncMock(return_value=StructuredIntent(
                task_type="fix",
                action="modify",
                target_area="frontend",
                description="Fix login bug where users can't submit",
                original_request="Fix the login bug",
                confidence=0.88
            ))
            
            with patch("app.graphs.agent_graph.DeterministicRouter") as MockRouter:
                mock_router = MockRouter.return_value
                mock_router.route = Mock(return_value=Mock(
                    next_phase="planner",
                    reason="Need to plan fix",
                    requires_llm=False,
                    gate_result=None,
                    metadata={"loop_detection": {"last_node": None, "consecutive_calls": 0}}
                ))
                
                result = await orchestrator_node(state)
                
                assert result["phase"] == "planner"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
