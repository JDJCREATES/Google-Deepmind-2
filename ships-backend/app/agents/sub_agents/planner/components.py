"""
ShipS* Planner Subcomponents

Subcomponents that produce individual planning artifacts.
Each component is responsible for one artifact type.
Now fully dynamic using LLM plan data.

Components:
- Scoper: Task decomposition → TaskList
- FolderArchitect: Project structure → FolderMap
- ContractAuthor: API design → APIContracts
- DependencyPlanner: Package planning → DependencyPlan
- TestDesigner: Validation planning → ValidationChecklist
- RiskAssessor: Risk identification → RiskReport
"""

from typing import Dict, Any, Optional, List
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
        llm_plan = context.get("llm_plan", {})
        
        task_list = TaskList(
            metadata=ArtifactMetadata(
                intent_spec_id=intent.get("id", "")
            )
        )
        
        # Use LLM plan tasks if available
        llm_tasks = llm_plan.get("tasks", [])
        if llm_tasks:
            for i, t_data in enumerate(llm_tasks):
                # Create structured AcceptanceCriterion objects
                criteria = []
                for ac_text in t_data.get("acceptance_criteria", []):
                    criteria.append(AcceptanceCriterion(description=ac_text))
                
                # Parse output files
                outputs = []
                for out in t_data.get("expected_outputs", []):
                    outputs.append(ExpectedOutput(
                        path=out.get("path", ""),
                        description=out.get("description", "Created file")
                    ))
                
                task = Task(
                    id=t_data.get("id", f"task_{i+1:03d}"),
                    title=t_data.get("title", "Untitled Task"),
                    description=t_data.get("description", ""),
                    complexity=TaskComplexity(t_data.get("complexity", "medium")),
                    priority=TaskPriority(t_data.get("priority", "medium")),
                    status=TaskStatus.PENDING,
                    estimated_minutes=t_data.get("estimated_minutes", 60),
                    acceptance_criteria=criteria,
                    expected_outputs=outputs,
                    order=i + 1
                )
                task_list.add_task(task)
        else:
            # Fallback if no LLM plan (should rare)
            description = intent.get("description", "")
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
        intent = context.get("intent", {})
        llm_plan = context.get("llm_plan", {})
        
        folder_map = FolderMap(
            metadata=ArtifactMetadata(
                intent_spec_id=intent.get("id", "")
            ),
            project_root=self.config.project_root
        )
        
        entries = []
        
        # 1. Use LLM suggested folders
        llm_folders = llm_plan.get("folders", [])
        existing_paths = set()
        
        for f_data in llm_folders:
            path = f_data.get("path", "")
            if path and path not in existing_paths:
                role = FileRole.SOURCE
                if "component" in path.lower(): role = FileRole.COMPONENT
                elif "hook" in path.lower(): role = FileRole.UTILITY
                elif "test" in path.lower(): role = FileRole.TEST
                
                entries.append(FolderEntry(
                    path=path,
                    is_directory=f_data.get("is_directory", True),
                    description=f_data.get("description", ""),
                    role=role
                ))
                existing_paths.add(path)
                
        # 2. If no LLM folders, use framework defaults
        if not entries:
            framework = context.get("framework", "react")
            if framework in ["react", "vite"]:
                 entries = [
                    FolderEntry(path="src", is_directory=True, description="Source code", role=FileRole.SOURCE),
                    FolderEntry(path="src/components", is_directory=True, description="React components", role=FileRole.COMPONENT),
                    FolderEntry(path="src/App.tsx", is_directory=False, description="Main App component", role=FileRole.COMPONENT),
                ]
            else:
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
        llm_plan = context.get("llm_plan", {})
        
        api_contracts = APIContracts(
            metadata=ArtifactMetadata(
                intent_spec_id=intent.get("id", "")
            )
        )
        
        # Use LLM suggested endpoints
        llm_endpoints = llm_plan.get("api_endpoints", [])
        for ep_data in llm_endpoints:
            api_contracts.endpoints.append(APIEndpoint(
                path=ep_data.get("path", "/"),
                method=HTTPMethod(ep_data.get("method", "GET")),
                description=ep_data.get("description", ""),
                request_schema=PayloadSchema(fields=[]), # Simplified
                response_schema=PayloadSchema(fields=[])
            ))
        
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
        llm_plan = context.get("llm_plan", {})
        
        dependency_plan = DependencyPlan(
            metadata=ArtifactMetadata(
                intent_spec_id=intent.get("id", "")
            ),
            package_manager="npm"
        )
        
        # 1. Start with framework defaults
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
        
        # 2. Add LLM suggested dependencies
        llm_deps = llm_plan.get("dependencies", {})
        
        # Runtime
        existing_runtime = {d.name for d in dependency_plan.runtime_dependencies}
        for dep in llm_deps.get("runtime", []):
            name = dep.get("name", "")
            if name and name not in existing_runtime:
                dependency_plan.runtime_dependencies.append(PackageDependency(
                    name=name,
                    version=dep.get("version", "latest"),
                    purpose="Added by planner"
                ))
        
        # Dev
        existing_dev = {d.name for d in dependency_plan.dev_dependencies}
        for dep in llm_deps.get("dev", []):
            name = dep.get("name", "")
            if name and name not in existing_dev:
                dependency_plan.dev_dependencies.append(PackageDependency(
                    name=name,
                    version=dep.get("version", "latest"),
                    purpose="Added by planner"
                ))
        
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
        llm_plan = context.get("llm_plan", {})
        
        risk_report = RiskReport(
            metadata=ArtifactMetadata(
                intent_spec_id=intent.get("id", "")
            )
        )
        
        # 1. Scaffolding Risks
        if scaffolding.get("needs_scaffolding"):
            risk_report.add_risk(RiskItem(
                title="Project Setup Required",
                category="setup",
                risk_level=RiskLevel.LOW,
                description="Project needs initial scaffolding",
                mitigation="Scaffold task added to plan",
                requires_human_input=False
            ))
            
        # 2. LLM Identified Risks
        for risk in llm_plan.get("risks", []):
            risk_report.add_risk(RiskItem(
                title=risk.get("title", "Identified Risk"),
                category="general",
                risk_level=RiskLevel(risk.get("level", "medium")),
                description=risk.get("description", ""),
                mitigation=risk.get("mitigation", "")
            ))
        
        # 3. Clarifying Questions
        questions = llm_plan.get("clarifying_questions", [])
        if questions:
            risk_report.add_risk(RiskItem(
                title="Clarification Needed",
                category="ambiguity",
                risk_level=RiskLevel.HIGH,
                description="The following questions need answers:",
                requires_human_input=True,
                clarifying_questions=questions
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
