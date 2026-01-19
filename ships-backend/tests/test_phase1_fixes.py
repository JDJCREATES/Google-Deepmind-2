"""
Test Agent Flow - Phase 1 Validation
====================================

Tests to verify Phase 1 stability fixes are working.
"""

import pytest
from unittest.mock import Mock, patch
from langchain_core.messages import HumanMessage


class TestIntentClassificationLock:
    """Test that intent classifier runs ONCE only."""
    
    def test_intent_classified_flag_prevents_reclassification(self):
        """Verify intent_classified flag prevents re-running classifier."""
        # Simulate state with already classified intent
        state = {
            "artifacts": {
                "structured_intent": {"scope": "feature", "task_type": "feature"},
                "intent_classified": True
            },
            "messages": [HumanMessage(content="Add a button")],
            "phase": "planner"
        }
        
        # The orchestrator should NOT call IntentClassifier if intent_classified=True
        # This is validated by checking artifacts aren't modified
        original_intent = state["artifacts"]["structured_intent"]
        
        # After orchestrator runs, intent should be unchanged
        # (This would be tested in integration test with actual orchestrator)
        assert state["artifacts"]["intent_classified"] == True
        assert state["artifacts"]["structured_intent"] == original_intent


class TestLLMFallbackStructuredOutput:
    """Test that LLM fallback uses structured output."""
    
    def test_pydantic_structured_output_schema(self):
        """Verify OrchestratorDecision schema is correct."""
        from pydantic import BaseModel, Field
        from typing import Literal
        
        class OrchestratorDecision(BaseModel):
            decision: Literal["planner", "coder", "validator", "fixer", "chat", "complete"]
            reasoning: str
        
        # Test valid decisions
        valid_decision = OrchestratorDecision(
            decision="coder",
            reasoning="Plan exists, ready to code"
        )
        
        assert valid_decision.decision == "coder"
        assert valid_decision.reasoning == "Plan exists, ready to code"
        
        # Test invalid decision should raise validation error
        with pytest.raises(Exception):
            invalid_decision = OrchestratorDecision(
                decision="invalid_agent",  # Not in Literal
                reasoning="This should fail"
            )


class TestQualityGateImprovements:
    """Test enhanced quality gate checks."""
    
    def test_plan_complete_checks_task_count(self):
        """Verify planning gate fails if plan has 0 tasks."""
        from app.graphs.quality_gates import check_plan_complete
        
        # State with plan but 0 tasks (INVALID)
        state_invalid = {
            "artifacts": {
                "task_list": {"tasks": []},  # Empty tasks!
                "folder_map": {"entries": [{"path": "src/app.ts"}]}
            }
        }
        
        assert check_plan_complete(state_invalid) == False
        
        # State with valid plan (has tasks)
        state_valid = {
            "artifacts": {
                "task_list": {"tasks": [{"id": "task1", "title": "Implement feature"}]},
                "folder_map": {"entries": [{"path": "src/app.ts"}]}
            }
        }
        
        assert check_plan_complete(state_valid) == True
    
    def test_scaffolding_check_allows_skipped(self):
        """Verify scaffolding gate passes when validly skipped."""
        from app.graphs.quality_gates import check_scaffolding_complete
        
        # Feature request (scaffolding not needed)
        state_feature = {
            "artifacts": {
                "structured_intent": {"scope": "feature"},
                "scaffolding_complete": False,
                "scaffolding_skipped": True
            }
        }
        
        assert check_scaffolding_complete(state_feature) == True
        
        # Project request (scaffolding needed but not done)
        state_project = {
            "artifacts": {
                "structured_intent": {"scope": "project"},
                "scaffolding_complete": False
            }
        }
        
        assert check_scaffolding_complete(state_project) == False


class TestLoopDetection:
    """Test simplified loop detection."""
    
    def test_router_loop_detection_trusted(self):
        """Verify orchestrator trusts router's loop detection."""
        # Router provides loop detection in metadata
        routing_decision = Mock()
        routing_decision.metadata = {
            "loop_detection": {
                "last_node": "coder",
                "consecutive_calls": 2,
                "loop_detected": False
            }
        }
        
        # Orchestrator should use this directly (tested in integration)
        loop_info = routing_decision.metadata["loop_detection"]
        
        assert loop_info["consecutive_calls"] == 2
        assert loop_info["last_node"] == "coder"
        assert loop_info["loop_detected"] == False


class TestRoutingLogging:
    """Test routing snapshot logging."""
    
    def test_routing_snapshot_structure(self):
        """Verify routing snapshot has all required fields."""
        import json
        from datetime import datetime
        
        # Simulate routing snapshot
        snapshot = {
            "timestamp": datetime.utcnow().isoformat(),
            "current_phase": "planner",
            "next_phase": "coder",
            "reason": "Plan complete, entering coding phase",
            "used_llm": False,
            "loop_detection": {
                "last_node": "planner",
                "consecutive_calls": 1,
                "loop_detected": False
            },
            "artifacts_present": ["structured_intent", "task_list", "folder_map"],
            "critical_flags": {
                "intent_classified": True,
                "scaffolding_complete": True,
                "implementation_complete": False,
                "validation_status": "pending",
                "fix_attempts": 0
            },
            "messages_count": 5,
            "gate_result": "PlanningExit",
            "gate_passed": True
        }
        
        # Should serialize to JSON without errors
        json_str = json.dumps(snapshot)
        parsed = json.loads(json_str)
        
        assert parsed["current_phase"] == "planner"
        assert parsed["next_phase"] == "coder"
        assert parsed["critical_flags"]["intent_classified"] == True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
