"""
Tests for ShipS* Artifact System

This module contains comprehensive tests for:
- Artifact Pydantic models
- ArtifactManager load/save operations
- Agent integration with artifacts
"""

import pytest
import tempfile
import json
from pathlib import Path
from datetime import datetime

# Add parent to path for imports
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.artifacts import (
    # Enums
    GateStatus,
    PitfallStatus,
    AgentType,
    
    # Models
    PatternRegistry,
    NamingConventions,
    ContractDefinitions,
    ContractEndpoint,
    RequestSchema,
    ResponseSchema,
    QualityGateResults,
    QualityGate,
    GateCheck,
    AgentConversationLog,
    AgentLogEntry,
    ContextMap,
    RelevantFile,
    DependencyGraph,
    FixHistory,
    PitfallCoverageMatrix,
    
    # Manager
    ArtifactManager,
    ArtifactPaths,
)


class TestPatternRegistry:
    """Tests for PatternRegistry model."""
    
    def test_create_empty_registry(self):
        """Test creating an empty pattern registry."""
        registry = PatternRegistry()
        assert registry.version == "1.0.0"
        assert registry.naming_conventions.variables == "camelCase"
        assert registry.async_patterns.preferred == "async/await"
    
    def test_update_naming_conventions(self):
        """Test updating naming conventions."""
        registry = PatternRegistry()
        registry.naming_conventions.variables = "snake_case"
        registry.naming_conventions.confidence = 0.95
        
        assert registry.naming_conventions.variables == "snake_case"
        assert registry.naming_conventions.confidence == 0.95
    
    def test_serialization(self):
        """Test JSON serialization."""
        registry = PatternRegistry()
        registry.naming_conventions.components = "PascalCase"
        
        data = registry.model_dump(mode='json')
        assert data['naming_conventions']['components'] == "PascalCase"
        
        # Deserialize
        restored = PatternRegistry.model_validate(data)
        assert restored.naming_conventions.components == "PascalCase"


class TestContractDefinitions:
    """Tests for ContractDefinitions model."""
    
    def test_create_contract(self):
        """Test creating a contract endpoint."""
        endpoint = ContractEndpoint(
            endpoint="POST /api/users",
            description="Create a new user",
            request=RequestSchema(
                body={"email": "string", "password": "string"}
            ),
            success_response=ResponseSchema(
                status=201,
                body={"user": {"id": "string"}}
            )
        )
        
        assert endpoint.endpoint == "POST /api/users"
        assert endpoint.success_response.status == 201
    
    def test_invalid_endpoint_format(self):
        """Test that invalid endpoint format raises error."""
        with pytest.raises(ValueError):
            ContractEndpoint(
                endpoint="invalid",  # Missing method
                success_response=ResponseSchema(status=200, body={})
            )
    
    def test_add_and_get_contract(self):
        """Test adding and retrieving contracts."""
        contracts = ContractDefinitions()
        
        endpoint = ContractEndpoint(
            endpoint="GET /api/users/:id",
            success_response=ResponseSchema(status=200, body={"user": {}})
        )
        contracts.add_contract(endpoint)
        
        retrieved = contracts.get_contract("GET /api/users/:id")
        assert retrieved is not None
        assert retrieved.success_response.status == 200
    
    def test_update_existing_contract(self):
        """Test updating an existing contract."""
        contracts = ContractDefinitions()
        
        # Add initial contract
        contracts.add_contract(ContractEndpoint(
            endpoint="GET /api/users",
            success_response=ResponseSchema(status=200, body={"users": []})
        ))
        
        # Update contract
        contracts.add_contract(ContractEndpoint(
            endpoint="GET /api/users",
            success_response=ResponseSchema(status=200, body={"users": [], "total": 0})
        ))
        
        # Should only have one contract
        assert len(contracts.contracts) == 1
        assert "total" in contracts.get_contract("GET /api/users").success_response.body


class TestQualityGateResults:
    """Tests for QualityGateResults model."""
    
    def test_create_gates(self):
        """Test creating quality gates."""
        results = QualityGateResults(
            task_id="test-123",
            task_description="Test task"
        )
        
        gate = results.add_gate("Code Quality")
        assert gate.gate_name == "Code Quality"
        assert gate.status == GateStatus.PENDING
        assert results.current_gate == "Code Quality"
    
    def test_run_checks(self):
        """Test running quality checks."""
        results = QualityGateResults()
        gate = results.add_gate("Validation")
        
        checks = [
            GateCheck(name="No TODOs", passed=True),
            GateCheck(name="No console.log", passed=False, issues=["Found at line 42"])
        ]
        gate.run_checks(checks)
        
        assert gate.status == GateStatus.FAILED
        assert len(gate.checks) == 2
    
    def test_proceed_status(self):
        """Test can_proceed status update."""
        results = QualityGateResults()
        
        gate1 = results.add_gate("Plan")
        gate1.run_checks([GateCheck(name="Complete", passed=True)])
        
        gate2 = results.add_gate("Code")
        gate2.run_checks([GateCheck(name="Valid", passed=True)])
        
        results.update_proceed_status()
        assert results.can_proceed is True
        
        # Now fail a gate
        gate2.run_checks([GateCheck(name="Valid", passed=False)])
        results.update_proceed_status()
        assert results.can_proceed is False


class TestAgentConversationLog:
    """Tests for AgentConversationLog model."""
    
    def test_log_action(self):
        """Test logging an action."""
        log = AgentConversationLog(task_description="Build feature")
        
        entry = log.log(
            agent=AgentType.ORCHESTRATOR,
            action="received_request",
            input_summary="User wants a login form"
        )
        
        assert len(log.entries) == 1
        assert entry.agent == AgentType.ORCHESTRATOR
        assert entry.action == "received_request"
    
    def test_filter_by_agent(self):
        """Test filtering entries by agent."""
        log = AgentConversationLog()
        
        log.log(agent=AgentType.ORCHESTRATOR, action="start")
        log.log(agent=AgentType.PLANNER, action="plan")
        log.log(agent=AgentType.ORCHESTRATOR, action="route")
        
        orchestrator_entries = log.get_entries_by_agent(AgentType.ORCHESTRATOR)
        assert len(orchestrator_entries) == 2


class TestContextMap:
    """Tests for ContextMap model."""
    
    def test_add_relevant_file(self):
        """Test adding relevant files."""
        context = ContextMap(current_task="Add user profile")
        
        context.add_file(
            path="src/components/UserProfile.tsx",
            reason="Component being modified",
            priority=1
        )
        
        assert len(context.relevant_files) == 1
        assert context.relevant_files[0].priority == 1
    
    def test_get_files_by_priority(self):
        """Test filtering files by priority."""
        context = ContextMap(current_task="Test")
        
        context.add_file("file1.ts", "Primary", priority=1)
        context.add_file("file2.ts", "Secondary", priority=2)
        context.add_file("file3.ts", "Primary", priority=1)
        
        priority1 = context.get_files_by_priority(1)
        assert len(priority1) == 2


class TestDependencyGraph:
    """Tests for DependencyGraph model."""
    
    def test_add_nodes_and_edges(self):
        """Test building a dependency graph."""
        graph = DependencyGraph()
        
        graph.add_node("src/api.ts", "utility", ["fetchUser"])
        graph.add_node("src/UserProfile.tsx", "component", ["UserProfile"])
        graph.add_edge("src/UserProfile.tsx", "src/api.ts", ["fetchUser"])
        
        assert len(graph.nodes) == 2
        assert len(graph.edges) == 1
    
    def test_get_dependents(self):
        """Test finding dependents of a node."""
        graph = DependencyGraph()
        
        graph.add_node("src/api.ts", "utility")
        graph.add_node("src/A.tsx", "component")
        graph.add_node("src/B.tsx", "component")
        
        graph.add_edge("src/A.tsx", "src/api.ts", ["fetch"])
        graph.add_edge("src/B.tsx", "src/api.ts", ["fetch"])
        
        dependents = graph.get_dependents("src/api.ts")
        assert len(dependents) == 2


class TestArtifactManager:
    """Tests for ArtifactManager service."""
    
    @pytest.fixture
    def temp_project(self):
        """Create a temporary project directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    def test_init_creates_directories(self, temp_project):
        """Test that initialization creates required directories."""
        manager = ArtifactManager(temp_project)
        
        assert (temp_project / ".ships" / "planning").exists()
        assert (temp_project / ".ships" / "runtime").exists()
        assert (temp_project / ".ships" / "audit" / "tasks").exists()
    
    def test_save_and_load_pattern_registry(self, temp_project):
        """Test saving and loading pattern registry."""
        manager = ArtifactManager(temp_project)
        
        # Get (creates default)
        registry = manager.get_pattern_registry()
        registry.naming_conventions.variables = "snake_case"
        registry.async_patterns.confidence = 0.9
        
        # Save
        manager.save_pattern_registry(registry)
        
        # Clear cache and reload
        manager.clear_cache()
        loaded = manager.get_pattern_registry()
        
        assert loaded.naming_conventions.variables == "snake_case"
        assert loaded.async_patterns.confidence == 0.9
    
    def test_save_and_load_contracts(self, temp_project):
        """Test saving and loading contract definitions."""
        manager = ArtifactManager(temp_project)
        
        contracts = manager.get_contract_definitions()
        contracts.add_contract(ContractEndpoint(
            endpoint="POST /api/users",
            success_response=ResponseSchema(status=201, body={"id": "string"})
        ))
        
        manager.save_contract_definitions(contracts)
        manager.clear_cache()
        
        loaded = manager.get_contract_definitions()
        assert len(loaded.contracts) == 1
    
    def test_log_agent_action(self, temp_project):
        """Test convenience method for logging."""
        manager = ArtifactManager(temp_project)
        
        entry = manager.log_agent_action(
            agent=AgentType.ORCHESTRATOR,
            action="test_action",
            input_summary="Test input"
        )
        
        assert entry is not None
        assert entry.action == "test_action"
        
        # Verify it was saved
        log = manager.get_agent_log()
        assert len(log.entries) == 1
    
    def test_initialize_for_task(self, temp_project):
        """Test task initialization."""
        manager = ArtifactManager(temp_project)
        
        manager.initialize_for_task("task-001", "Build login form")
        
        gates = manager.get_quality_gate_results()
        assert gates.task_id == "task-001"
        
        log = manager.get_agent_log()
        assert log.task_description == "Build login form"
    
    def test_artifact_exists(self, temp_project):
        """Test artifact existence check."""
        manager = ArtifactManager(temp_project)
        
        assert not manager.artifact_exists("pattern_registry")
        
        manager.save_pattern_registry(PatternRegistry())
        
        assert manager.artifact_exists("pattern_registry")
    
    def test_artifact_summary(self, temp_project):
        """Test artifact summary."""
        manager = ArtifactManager(temp_project)
        
        # Initially nothing exists
        summary = manager.get_artifact_summary()
        assert all(not exists for exists in summary.values())
        
        # Create some artifacts
        manager.save_pattern_registry(PatternRegistry())
        manager.save_contract_definitions(ContractDefinitions())
        
        summary = manager.get_artifact_summary()
        assert summary['pattern_registry'] is True
        assert summary['contracts'] is True
        assert summary['quality_gates'] is False


class TestPitfallCoverageMatrix:
    """Tests for PitfallCoverageMatrix model."""
    
    def test_add_checks(self):
        """Test adding pitfall checks."""
        matrix = PitfallCoverageMatrix()
        
        matrix.add_check("1.1", "TODO Placeholders", PitfallStatus.CAUGHT, AgentType.VALIDATOR)
        matrix.add_check("6.1", "Wrong Import Paths", PitfallStatus.CLEAN, AgentType.DEPENDENCY_RESOLVER)
        matrix.add_check("7.2", "Race Conditions", PitfallStatus.SKIPPED)
        
        assert len(matrix.coverage) == 3
    
    def test_summary_calculation(self):
        """Test coverage summary calculation."""
        matrix = PitfallCoverageMatrix()
        
        matrix.add_check("1.1", "TODO", PitfallStatus.CAUGHT)
        matrix.add_check("1.2", "FIXME", PitfallStatus.CLEAN)
        matrix.add_check("1.3", "Stubs", PitfallStatus.CLEAN)
        matrix.add_check("2.1", "Race", PitfallStatus.SKIPPED)
        
        summary = matrix.summary
        assert summary["total_pitfalls"] == 4
        assert summary["caught"] == 1
        assert summary["clean"] == 2
        assert summary["skipped"] == 1
        assert summary["coverage_percent"] == 75.0  # 3/4


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
