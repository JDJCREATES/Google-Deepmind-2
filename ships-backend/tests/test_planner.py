"""
Tests for ShipS* Planner Sub-Agent

Tests cover:
- Artifact models
- Planner components  
- Main planner functionality
- Tools
"""

import pytest
from datetime import datetime
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.agents.sub_agents.planner.models import (
    PlanManifest, TaskList, Task, TaskComplexity, TaskPriority, TaskStatus,
    FolderMap, FolderEntry, FileRole,
    APIContracts, APIEndpoint, HTTPMethod,
    DependencyPlan, PackageDependency,
    ValidationChecklist, ValidationCheck,
    RiskReport, RiskItem, RiskLevel,
    AcceptanceCriterion, ExpectedOutput,
)
from app.agents.sub_agents.planner.components import (
    PlannerComponentConfig, Scoper, FolderArchitect,
    ContractAuthor, DependencyPlanner, TestDesigner, RiskAssessor,
)
from app.agents.sub_agents.planner.tools import PlannerTools


class TestPlannerModels:
    """Tests for Planner artifact models."""
    
    def test_create_task(self):
        """Test creating a Task."""
        task = Task(
            title="Setup Project",
            description="Initialize the project",
            complexity=TaskComplexity.SMALL,
            priority=TaskPriority.CRITICAL
        )
        
        assert task.title == "Setup Project"
        assert task.complexity == TaskComplexity.SMALL
        assert task.status == TaskStatus.PENDING
        assert task.id.startswith("task_")
    
    def test_task_with_acceptance_criteria(self):
        """Test task with acceptance criteria."""
        task = Task(
            title="Build API",
            description="Create REST API",
            acceptance_criteria=[
                AcceptanceCriterion(description="API responds to GET /"),
                AcceptanceCriterion(description="Returns 200 status")
            ]
        )
        
        assert len(task.acceptance_criteria) == 2
    
    def test_task_list_add_and_stats(self):
        """Test TaskList add and stats."""
        task_list = TaskList()
        
        task_list.add_task(Task(
            title="Task 1",
            description="First task",
            estimated_minutes=60,
            is_blocked=False
        ))
        task_list.add_task(Task(
            title="Task 2", 
            description="Second task",
            estimated_minutes=120,
            is_blocked=True
        ))
        
        assert len(task_list.tasks) == 2
        assert task_list.total_estimated_minutes == 180
        assert task_list.blocked_task_count == 1
    
    def test_folder_map(self):
        """Test FolderMap creation."""
        folder_map = FolderMap()
        folder_map.entries.append(FolderEntry(
            path="src/components/",
            is_directory=True,
            role=FileRole.COMPONENT
        ))
        
        assert len(folder_map.entries) == 1
        assert folder_map.entries[0].role == FileRole.COMPONENT
    
    def test_api_endpoint(self):
        """Test APIEndpoint creation."""
        endpoint = APIEndpoint(
            path="/api/users",
            method=HTTPMethod.GET,
            description="List users"
        )
        
        assert endpoint.path == "/api/users"
        assert endpoint.method == HTTPMethod.GET
    
    def test_dependency_plan(self):
        """Test DependencyPlan creation."""
        plan = DependencyPlan()
        plan.runtime_dependencies.append(PackageDependency(name="react"))
        
        assert plan.package_manager == "npm"
        assert len(plan.runtime_dependencies) == 1
    
    def test_risk_report_add(self):
        """Test RiskReport add and stats."""
        report = RiskReport()
        
        report.add_risk(RiskItem(
            title="Low Risk",
            risk_level=RiskLevel.LOW
        ))
        report.add_risk(RiskItem(
            title="High Risk",
            risk_level=RiskLevel.HIGH,
            requires_human_input=True
        ))
        
        assert len(report.risks) == 2
        assert report.has_blockers is True
        assert report.high_risk_count == 1
    
    def test_plan_manifest(self):
        """Test PlanManifest creation."""
        manifest = PlanManifest(
            intent_spec_id="intent_123",
            summary="Create todo app"
        )
        
        assert manifest.intent_spec_id == "intent_123"
        assert manifest.is_complete is True
        assert manifest.recommended_next_agent == "coder"


class TestPlannerComponents:
    """Tests for Planner components."""
    
    @pytest.fixture
    def config(self):
        return PlannerComponentConfig()
    
    @pytest.fixture
    def basic_context(self):
        return {
            "intent": {
                "task_type": "feature",
                "target_area": "full-stack",
                "description": "Add user login"
            },
            "framework": "react"
        }
    
    def test_scoper_creates_tasks(self, config, basic_context):
        """Test Scoper creates task list."""
        scoper = Scoper(config)
        result = scoper.process(basic_context)
        
        assert "task_list" in result
        task_list = result["task_list"]
        assert len(task_list.tasks) >= 3  # Setup, main, wiring, test
    
    def test_scoper_vertical_slice(self, config, basic_context):
        """Test Scoper prioritizes vertical slice."""
        scoper = Scoper(config)
        result = scoper.process(basic_context)
        
        task_list = result["task_list"]
        # First task should be setup (critical priority)
        assert task_list.tasks[0].priority == TaskPriority.CRITICAL
    
    def test_folder_architect(self, config, basic_context):
        """Test FolderArchitect creates folder map."""
        architect = FolderArchitect(config)
        result = architect.process(basic_context)
        
        assert "folder_map" in result
        folder_map = result["folder_map"]
        assert len(folder_map.entries) > 0
    
    def test_contract_author(self, config, basic_context):
        """Test ContractAuthor creates API contracts."""
        basic_context["intent"]["requires_api"] = True
        author = ContractAuthor(config)
        result = author.process(basic_context)
        
        assert "api_contracts" in result
        contracts = result["api_contracts"]
        assert len(contracts.endpoints) > 0
    
    def test_dependency_planner(self, config, basic_context):
        """Test DependencyPlanner creates dependency plan."""
        planner = DependencyPlanner(config)
        result = planner.process(basic_context)
        
        assert "dependency_plan" in result
        plan = result["dependency_plan"]
        assert len(plan.runtime_dependencies) > 0
        assert len(plan.commands) > 0
    
    def test_test_designer(self, config, basic_context):
        """Test TestDesigner creates validation checklist."""
        # First create task list
        scoper = Scoper(config)
        scope_result = scoper.process(basic_context)
        basic_context["task_list"] = scope_result["task_list"]
        
        designer = TestDesigner(config)
        result = designer.process(basic_context)
        
        assert "validation_checklist" in result
        checklist = result["validation_checklist"]
        assert len(checklist.smoke_tests) > 0
    
    def test_risk_assessor(self, config, basic_context):
        """Test RiskAssessor creates risk report."""
        assessor = RiskAssessor(config)
        result = assessor.process(basic_context)
        
        assert "risk_report" in result


class TestPlannerTools:
    """Tests for PlannerTools."""
    
    def test_detect_framework_react(self):
        """Test framework detection for React."""
        context = {"app_blueprint": {"tech_stack": {"frontend": "React"}}}
        framework = PlannerTools.detect_framework(context)
        assert framework == "react"
    
    def test_detect_framework_nextjs(self):
        """Test framework detection for Next.js."""
        context = {"app_blueprint": {"tech_stack": {"frontend": "Next.js"}}}
        framework = PlannerTools.detect_framework(context)
        assert framework == "nextjs"
    
    def test_detect_framework_fastapi(self):
        """Test framework detection for FastAPI."""
        context = {"app_blueprint": {"tech_stack": {"backend": "FastAPI"}}}
        framework = PlannerTools.detect_framework(context)
        assert framework == "fastapi"
    
    def test_validate_task_list_empty(self):
        """Test validation of empty task list."""
        task_list = TaskList()
        result = PlannerTools.validate_task_list(task_list)
        
        assert result["valid"] is False
        assert "empty" in result["issues"][0].lower()
    
    def test_validate_task_list_valid(self):
        """Test validation of valid task list."""
        task_list = TaskList()
        task_list.add_task(Task(
            title="Test",
            description="Test task",
            acceptance_criteria=[AcceptanceCriterion(description="Works")]
        ))
        
        result = PlannerTools.validate_task_list(task_list)
        assert result["valid"] is True
    
    def test_assemble_plan_manifest(self):
        """Test plan manifest assembly."""
        task_list = TaskList()
        task_list.add_task(Task(title="T1", description="D1"))
        
        manifest = PlannerTools.assemble_plan_manifest(
            intent_spec_id="intent_1",
            summary="Test plan",
            task_list=task_list,
            folder_map=FolderMap(),
            api_contracts=APIContracts(),
            dependency_plan=DependencyPlan(),
            validation_checklist=ValidationChecklist(),
            risk_report=RiskReport()
        )
        
        assert manifest.total_tasks == 1
        assert manifest.summary == "Test plan"
        assert len(manifest.artifacts) == 6


# Run with: py -m pytest tests/test_planner.py -v
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
