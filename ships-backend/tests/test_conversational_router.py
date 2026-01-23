"""
Tests for Conversational Router (Fast-Path Routing)

Validates that conversational queries (questions, confirmations, unclear requests)
are routed to appropriate handlers without invoking the heavy engineering pipeline.
"""

import pytest
from app.graphs.conversational_router import ConversationalRouter, ConversationalDecision


class TestConversationalRouterQuestions:
    """Test routing for question-type requests."""
    
    def test_question_routes_to_chat(self):
        """Questions should route to chat_setup for Chatter agent."""
        router = ConversationalRouter()
        state = {"artifacts": {}, "phase": "planning"}
        intent = {
            "task_type": "question",
            "action": "explain",
            "description": "What does Button.tsx do?",
            "confidence": 0.95
        }
        
        decision = router.route(state, intent)
        
        assert decision.is_fast_path is True
        assert decision.next_phase == "chat_setup"
        assert "question" in decision.reason.lower() or "chatter" in decision.reason.lower()
    
    def test_analyze_action_routes_to_chat(self):
        """Analyze actions (without modifications) should route to chat."""
        router = ConversationalRouter()
        state = {"artifacts": {}}
        intent = {
            "task_type": "question",
            "action": "analyze",
            "description": "Analyze the auth flow",
            "confidence": 0.90
        }
        
        decision = router.route(state, intent)
        
        assert decision.is_fast_path is True
        assert decision.next_phase == "chat_setup"


class TestConversationalRouterConfirmations:
    """Test routing for confirmation requests."""
    
    def test_confirmation_with_plan_continues_to_coder(self):
        """Confirmations with existing plan should continue to coder."""
        router = ConversationalRouter()
        state = {
            "artifacts": {
                "plan": {"tasks": [{"title": "Add auth"}]},
                "implementation_plan": "Plan details..."
            }
        }
        intent = {
            "task_type": "confirmation",
            "action": "proceed",
            "description": "yes, looks good",
            "confidence": 0.95
        }
        
        decision = router.route(state, intent)
        
        assert decision.is_fast_path is True
        assert decision.next_phase == "coder"
        assert "confirmed" in decision.reason.lower() or "plan" in decision.reason.lower()
        assert decision.metadata.get("confirmed_plan") is True
    
    def test_confirmation_without_plan_asks_for_context(self):
        """Confirmations without context should route to chat for clarification."""
        router = ConversationalRouter()
        state = {"artifacts": {}}  # No plan
        intent = {
            "task_type": "confirmation",
            "action": "proceed",
            "description": "yes",
            "confidence": 0.90
        }
        
        decision = router.route(state, intent)
        
        assert decision.is_fast_path is True
        assert decision.next_phase == "chat_setup"
        assert "context" in decision.reason.lower() or "clarification" in decision.reason.lower()
        assert decision.metadata.get("missing_context") == "no_plan"


class TestConversationalRouterUnclear:
    """Test routing for unclear/ambiguous requests."""
    
    def test_unclear_with_questions_routes_to_chat(self):
        """Unclear requests with clarification questions should route to chat."""
        router = ConversationalRouter()
        state = {"artifacts": {}}
        intent = {
            "task_type": "unclear",
            "action": "analyze",
            "is_ambiguous": True,
            "clarification_questions": [
                "Do you want a new app or to modify existing?",
                "What framework?"
            ],
            "confidence": 0.3
        }
        
        decision = router.route(state, intent)
        
        assert decision.is_fast_path is True
        assert decision.next_phase == "chat_setup"
        assert "unclear" in decision.reason.lower() or "clarification" in decision.reason.lower()
        assert len(decision.metadata.get("clarification_questions", [])) == 2
    
    def test_unclear_without_questions_routes_to_planner(self):
        """Unclear requests without questions might need planning for scope."""
        router = ConversationalRouter()
        state = {"artifacts": {}}
        intent = {
            "task_type": "unclear",
            "action": "analyze",
            "is_ambiguous": True,
            "clarification_questions": [],  # No specific questions
            "confidence": 0.4
        }
        
        decision = router.route(state, intent)
        
        assert decision.is_fast_path is True
        assert decision.next_phase == "planner"
    
    def test_low_confidence_ambiguous_routes_to_chat(self):
        """Low confidence + ambiguous should route to chat."""
        router = ConversationalRouter()
        state = {"artifacts": {}}
        intent = {
            "task_type": "feature",  # Not marked unclear
            "action": "create",
            "is_ambiguous": True,
            "confidence": 0.5,  # Below threshold
            "clarification_questions": ["What should this feature do?"]
        }
        
        decision = router.route(state, intent)
        
        assert decision.is_fast_path is True
        assert decision.next_phase == "chat_setup"


class TestConversationalRouterSecurity:
    """Test security risk handling."""
    
    def test_high_security_risk_routes_to_chat(self):
        """High security risk should route to chat for safe response."""
        router = ConversationalRouter()
        state = {"artifacts": {}}
        intent = {
            "task_type": "feature",
            "action": "create",
            "security_risk_score": 0.85,
            "security_warnings": ["Potential command injection detected"],
            "confidence": 0.9
        }
        
        decision = router.route(state, intent)
        
        assert decision.is_fast_path is True
        assert decision.next_phase == "chat_setup"
        assert "security" in decision.reason.lower()
        assert decision.metadata.get("security_risk_score") == 0.85


class TestConversationalRouterEngineering:
    """Test that engineering tasks fall through to DeterministicRouter."""
    
    def test_feature_request_falls_through(self):
        """Feature requests should use DeterministicRouter."""
        router = ConversationalRouter()
        state = {"artifacts": {}}
        intent = {
            "task_type": "feature",
            "action": "create",
            "description": "Add dark mode",
            "confidence": 0.95
        }
        
        decision = router.route(state, intent)
        
        assert decision.is_fast_path is False
        assert decision.next_phase == "fallthrough"
        assert "engineering" in decision.reason.lower() or "pipeline" in decision.reason.lower()
    
    def test_fix_request_falls_through(self):
        """Fix requests should use DeterministicRouter."""
        router = ConversationalRouter()
        state = {"artifacts": {}}
        intent = {
            "task_type": "fix",
            "action": "modify",
            "description": "Fix button alignment",
            "confidence": 0.90
        }
        
        decision = router.route(state, intent)
        
        assert decision.is_fast_path is False
        assert decision.next_phase == "fallthrough"
    
    def test_modify_action_falls_through(self):
        """Modify actions should use DeterministicRouter."""
        router = ConversationalRouter()
        state = {"artifacts": {}}
        intent = {
            "task_type": "modify",
            "action": "modify",
            "description": "Change button color to blue",
            "confidence": 0.95
        }
        
        decision = router.route(state, intent)
        
        assert decision.is_fast_path is False
        assert decision.next_phase == "fallthrough"
    
    def test_delete_action_falls_through(self):
        """Delete actions should use DeterministicRouter."""
        router = ConversationalRouter()
        state = {"artifacts": {}}
        intent = {
            "task_type": "delete",
            "action": "delete",
            "description": "Remove old component",
            "confidence": 0.92
        }
        
        decision = router.route(state, intent)
        
        assert decision.is_fast_path is False
        assert decision.next_phase == "fallthrough"


class TestConversationalRouterEdgeCases:
    """Test edge cases and error handling."""
    
    def test_missing_intent_falls_through(self):
        """Missing intent should fall through with warning."""
        router = ConversationalRouter()
        state = {"artifacts": {}}
        intent = None
        
        decision = router.route(state, intent)
        
        assert decision.is_fast_path is False
        assert decision.next_phase == "fallthrough"
        assert "no intent" in decision.reason.lower()
    
    def test_hybrid_question_action_prioritizes_action(self):
        """Hybrid requests (question + action) should prioritize action."""
        router = ConversationalRouter()
        state = {"artifacts": {}}
        intent = {
            "task_type": "question",  # Marked as question
            "action": "create",  # But wants to create
            "description": "What does Button do? Change it to blue.",
            "confidence": 0.80
        }
        
        decision = router.route(state, intent)
        
        # Should fall through because action is "create" (engineering task)
        assert decision.is_fast_path is False
        assert decision.next_phase == "fallthrough"


class TestConversationalRouterIntentLocking:
    """Test intent lock clearing logic."""
    
    def test_should_clear_lock_for_questions(self):
        """Questions should clear intent lock to allow re-classification."""
        router = ConversationalRouter()
        
        assert router.should_clear_intent_lock("question") is True
    
    def test_should_clear_lock_for_confirmations(self):
        """Confirmations should clear intent lock."""
        router = ConversationalRouter()
        
        assert router.should_clear_intent_lock("confirmation") is True
    
    def test_should_clear_lock_for_unclear(self):
        """Unclear requests should clear intent lock."""
        router = ConversationalRouter()
        
        assert router.should_clear_intent_lock("unclear") is True
    
    def test_should_not_clear_lock_for_features(self):
        """Features should keep intent locked."""
        router = ConversationalRouter()
        
        assert router.should_clear_intent_lock("feature") is False
    
    def test_should_not_clear_lock_for_fixes(self):
        """Fixes should keep intent locked."""
        router = ConversationalRouter()
        
        assert router.should_clear_intent_lock("fix") is False
    
    def test_should_not_clear_lock_for_engineering_tasks(self):
        """All engineering tasks should keep intent locked."""
        router = ConversationalRouter()
        
        engineering_types = ["feature", "fix", "refactor", "modify", "delete"]
        for task_type in engineering_types:
            assert router.should_clear_intent_lock(task_type) is False


class TestConversationalRouterIntegration:
    """Integration tests with realistic scenarios."""
    
    def test_scenario_simple_question(self):
        """Scenario: User asks 'What does this file do?'"""
        router = ConversationalRouter()
        state = {
            "artifacts": {"project_path": "/path/to/project"},
            "phase": "planning"
        }
        intent = {
            "task_type": "question",
            "action": "explain",
            "description": "What does src/components/Button.tsx do?",
            "original_request": "What does Button.tsx do?",
            "confidence": 0.95,
            "is_ambiguous": False
        }
        
        decision = router.route(state, intent)
        
        assert decision.is_fast_path is True
        assert decision.next_phase == "chat_setup"
        # Should preserve original request in metadata
        assert decision.metadata.get("original_request") == "What does Button.tsx do?"
    
    def test_scenario_gibberish_input(self):
        """Scenario: User sends 'asdfghjkl' (gibberish)"""
        router = ConversationalRouter()
        state = {"artifacts": {}}
        intent = {
            "task_type": "unclear",
            "action": "analyze",
            "description": "Could not classify request",
            "original_request": "asdfghjkl",
            "is_ambiguous": True,
            "clarification_questions": [
                "I couldn't understand your request. Could you rephrase?"
            ],
            "confidence": 0.0
        }
        
        decision = router.route(state, intent)
        
        assert decision.is_fast_path is True
        assert decision.next_phase == "chat_setup"
    
    def test_scenario_confirmation_after_plan(self):
        """Scenario: User says 'yes' after seeing a plan"""
        router = ConversationalRouter()
        state = {
            "artifacts": {
                "plan": {
                    "tasks": [
                        {"title": "Create auth component"},
                        {"title": "Add login route"}
                    ]
                }
            },
            "phase": "planning"
        }
        intent = {
            "task_type": "confirmation",
            "action": "proceed",
            "description": "yes, looks good",
            "confidence": 0.98
        }
        
        decision = router.route(state, intent)
        
        assert decision.is_fast_path is True
        assert decision.next_phase == "coder"
    
    def test_scenario_add_feature(self):
        """Scenario: User says 'Add dark mode'"""
        router = ConversationalRouter()
        state = {"artifacts": {}}
        intent = {
            "task_type": "feature",
            "action": "create",
            "description": "Add dark mode toggle to settings page",
            "confidence": 0.92,
            "is_ambiguous": False
        }
        
        decision = router.route(state, intent)
        
        assert decision.is_fast_path is False
        assert decision.next_phase == "fallthrough"
        # Should include task details in metadata
        assert decision.metadata.get("task_type") == "feature"
        assert decision.metadata.get("action") == "create"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
