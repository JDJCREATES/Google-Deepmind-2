"""
ShipS* Planner Subcomponents

Subcomponents that produce individual planning artifacts.
Each component is responsible for one artifact type.

Components:
- Scoper: Task decomposition → TaskList
- FolderArchitect: Project structure → FolderMap
- ContractAuthor: API design → APIContracts
- DependencyPlanner: Package planning → DependencyPlan
- TestDesigner: Validation planning → ValidationChecklist
- RiskAssessor: Risk identification → RiskReport
"""

from typing import Dict, Any, Optional
from app.agents.sub_agents.planner.models import (
    TaskList, Task, TaskComplexity, TaskPriority, TaskStatus,
    AcceptanceCriterion, TaskDependency, ExpectedOutput,
    FolderMap, FolderEntry, FileRole,
    APIContracts, APIEndpoint, HTTPMethod, PayloadSchema, FieldSchema,
    DependencyPlan, PackageDependency, RunCommand,
    ValidationChecklist, ValidationCheck,
    RiskReport, RiskItem, RiskLevel,
    ArtifactMetadata, PlannerComponentConfig,
)


class Scoper:
    """
    Task decomposition component.
    
    Analyzes intent and produces a prioritized TaskList
    with acceptance criteria and dependencies.
    """
    
    def __init__(self, config: Optional[PlannerComponentConfig] = None):
        self.config = config or PlannerComponentConfig()
    
    def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process context and produce TaskList.
        
        Returns:
            Dict with 'task_list' key containing TaskList
        """
        intent = context.get("intent", {})
        description = intent.get("description", "")
        
        task_list = TaskList(
            metadata=ArtifactMetadata(
                intent_spec_id=intent.get("id", "")
            )
        )
        
        # Create a main implementation task
        main_task = Task(
            id="task_main_001",
            title="Implement Core Features",
            description=f"Implement: {description[:200]}",
            complexity=TaskComplexity.MEDIUM,
            priority=TaskPriority.HIGH,
            status=TaskStatus.PENDING,
            estimated_minutes=120,
            acceptance_criteria=[
                AcceptanceCriterion(
                    given="the application is running",
                    when="user interacts with it",
                    then="expected behavior occurs"
                )
            ]
        )
        task_list.add_task(main_task)
        
        return {"task_list": task_list}


class FolderArchitect:
    """
    Project structure component.
    
    Produces a FolderMap based on framework and scope.
    """
    
    def __init__(self, config: Optional[PlannerComponentConfig] = None):
        self.config = config or PlannerComponentConfig()
    
    def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process context and produce FolderMap.
        
        Returns:
            Dict with 'folder_map' key containing FolderMap
        """
        framework = context.get("framework", "react")
        intent = context.get("intent", {})
        
        folder_map = FolderMap(
            metadata=ArtifactMetadata(
                intent_spec_id=intent.get("id", "")
            ),
            project_root=self.config.project_root
        )
        
        # Standard React/Vite structure
        if framework in ["react", "vite"]:
            entries = [
                FolderEntry(path="src", is_directory=True, description="Source code", role=FileRole.SOURCE),
                FolderEntry(path="src/components", is_directory=True, description="React components", role=FileRole.COMPONENT),
                FolderEntry(path="src/components/ui", is_directory=True, description="Base UI components", role=FileRole.COMPONENT),
                FolderEntry(path="src/hooks", is_directory=True, description="Custom React hooks", role=FileRole.UTILITY),
                FolderEntry(path="src/lib", is_directory=True, description="Utilities and helpers", role=FileRole.UTILITY),
                FolderEntry(path="src/types", is_directory=True, description="TypeScript types", role=FileRole.MODEL),
                FolderEntry(path="src/App.tsx", is_directory=False, description="Main App component", role=FileRole.COMPONENT),
                FolderEntry(path="src/main.tsx", is_directory=False, description="Entry point", role=FileRole.SOURCE),
                FolderEntry(path="src/index.css", is_directory=False, description="Global styles", role=FileRole.STYLE),
            ]
        else:
            # Generic structure
            entries = [
                FolderEntry(path="src", is_directory=True, description="Source code", role=FileRole.SOURCE),
            ]
        
        folder_map.entries = entries
        return {"folder_map": folder_map}


class ContractAuthor:
    """
    API contract component.
    
    Produces APIContracts based on requirements.
    """
    
    def __init__(self, config: Optional[PlannerComponentConfig] = None):
        self.config = config or PlannerComponentConfig()
    
    def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process context and produce APIContracts.
        
        Returns:
            Dict with 'api_contracts' key containing APIContracts
        """
        intent = context.get("intent", {})
        
        api_contracts = APIContracts(
            metadata=ArtifactMetadata(
                intent_spec_id=intent.get("id", "")
            )
        )
        
        # No endpoints by default (frontend-only)
        # LLM will enrich if needed
        
        return {"api_contracts": api_contracts}


class DependencyPlanner:
    """
    Dependency planning component.
    
    Produces DependencyPlan with required packages.
    """
    
    def __init__(self, config: Optional[PlannerComponentConfig] = None):
        self.config = config or PlannerComponentConfig()
    
    def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process context and produce DependencyPlan.
        
        Returns:
            Dict with 'dependency_plan' key containing DependencyPlan
        """
        framework = context.get("framework", "react")
        intent = context.get("intent", {})
        
        dependency_plan = DependencyPlan(
            metadata=ArtifactMetadata(
                intent_spec_id=intent.get("id", "")
            ),
            package_manager="npm"
        )
        
        # React/Vite defaults
        if framework in ["react", "vite"]:
            dependency_plan.runtime_dependencies = [
                PackageDependency(name="react", version="^18.2.0", purpose="UI library"),
                PackageDependency(name="react-dom", version="^18.2.0", purpose="React DOM renderer"),
            ]
            dependency_plan.dev_dependencies = [
                PackageDependency(name="typescript", version="^5.0.0", purpose="Type checking"),
                PackageDependency(name="@types/react", version="^18.2.0", purpose="React types"),
                PackageDependency(name="vite", version="^5.0.0", purpose="Build tool"),
            ]
            
        dependency_plan.commands = [
            RunCommand(name="dev", command="npm run dev", description="Start dev server"),
            RunCommand(name="build", command="npm run build", description="Build for production"),
        ]
        
        return {"dependency_plan": dependency_plan}


class TestDesigner:
    """
    Validation checklist component.
    
    Produces ValidationChecklist with test plan.
    """
    
    def __init__(self, config: Optional[PlannerComponentConfig] = None):
        self.config = config or PlannerComponentConfig()
    
    def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process context and produce ValidationChecklist.
        
        Returns:
            Dict with 'validation_checklist' key containing ValidationChecklist
        """
        intent = context.get("intent", {})
        task_list = context.get("task_list")
        
        validation_checklist = ValidationChecklist(
            metadata=ArtifactMetadata(
                intent_spec_id=intent.get("id", "")
            )
        )
        
        # Default checks
        validation_checklist.unit_checks = [
            ValidationCheck(
                name="App Renders",
                description="Main app component renders without errors",
                check_type="unit",
                assertion="App component mounts successfully",
                is_automated=True
            )
        ]
        
        validation_checklist.runtime_checks = [
            ValidationCheck(
                name="Dev Server Boots",
                description="Development server starts without errors",
                check_type="runtime",
                assertion="npm run dev produces no errors",
                command="npm run dev",
                is_automated=True
            )
        ]
        
        return {"validation_checklist": validation_checklist}


class RiskAssessor:
    """
    Risk assessment component.
    
    Produces RiskReport with identified risks and blockers.
    """
    
    def __init__(self, config: Optional[PlannerComponentConfig] = None):
        self.config = config or PlannerComponentConfig()
    
    def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process context and produce RiskReport.
        
        Returns:
            Dict with 'risk_report' key containing RiskReport
        """
        intent = context.get("intent", {})
        scaffolding = context.get("scaffolding", {})
        
        risk_report = RiskReport(
            metadata=ArtifactMetadata(
                intent_spec_id=intent.get("id", "")
            )
        )
        
        # Check for scaffolding needs (potential setup issues)
        if scaffolding.get("needs_scaffolding"):
            risk_report.add_risk(RiskItem(
                title="Project Setup Required",
                category="setup",
                risk_level=RiskLevel.LOW,
                description="Project needs initial scaffolding",
                mitigation="Scaffold task added to plan",
                requires_human_input=False
            ))
        
        return {"risk_report": risk_report}


__all__ = [
    "Scoper",
    "FolderArchitect",
    "ContractAuthor",
    "DependencyPlanner",
    "TestDesigner",
    "RiskAssessor",
]
