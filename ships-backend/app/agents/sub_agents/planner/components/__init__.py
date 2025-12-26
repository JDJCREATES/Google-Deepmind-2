"""
ShipS* Planner Components

Modular subcomponents for the Planner agent:
- Scoper: Task decomposition with vertical-slice priority
- FolderArchitect: Folder structure generation
- ContractAuthor: API contract creation
- DependencyPlanner: Package/env planning
- TestDesigner: Validation checklist
- RiskAssessor: Risk scoring

Each component produces a specific artifact subset.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from pydantic import BaseModel

from app.agents.sub_agents.planner.models import (
    Task, TaskList, TaskComplexity, TaskPriority, TaskStatus,
    AcceptanceCriterion, ExpectedOutput,
    FolderMap, FolderEntry, FileRole,
    APIContracts, APIEndpoint, PayloadSchema, FieldSchema, HTTPMethod,
    DependencyPlan, PackageDependency, EnvironmentVariable, RunCommand,
    ValidationChecklist, ValidationCheck,
    RiskReport, RiskItem, RiskLevel,
)


class PlannerComponentConfig(BaseModel):
    """Configuration for planner components."""
    max_decomposition_depth: int = 3
    max_tasks_per_plan: int = 20
    max_task_complexity: TaskComplexity = TaskComplexity.MEDIUM
    min_test_coverage: float = 0.7
    vertical_slice_first: bool = True


class PlannerComponent(ABC):
    """Base class for planner subcomponents."""
    
    def __init__(self, config: Optional[PlannerComponentConfig] = None):
        self.config = config or PlannerComponentConfig()
    
    @abstractmethod
    def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Process input and produce output artifacts."""
        pass


# ============================================================================
# SCOPER: Task Decomposition
# ============================================================================

class Scoper(PlannerComponent):
    """
    Breaks intent into digestible tasks using heuristics.
    
    Key behaviors:
    - Vertical-slice-first: Prioritize tasks that produce runnable preview
    - Max granularity: No task larger than MEDIUM unless approved
    - Parallelizability: Mark tasks that can be concurrent
    """
    
    def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Decompose intent into tasks.
        
        Args:
            context: Contains 'intent', 'app_blueprint', 'constraints'
            
        Returns:
            Dict with 'task_list' artifact
        """
        intent = context.get("intent", {})
        
        task_list = TaskList()
        
        # Generate tasks based on intent type
        task_type = intent.get("task_type", "feature")
        target_area = intent.get("target_area", "full-stack")
        description = intent.get("description", "")
        
        # Always start with setup task for vertical slice
        if self.config.vertical_slice_first:
            setup_task = self._create_setup_task(intent)
            task_list.add_task(setup_task)
        
        # Create main implementation tasks
        main_tasks = self._decompose_by_area(intent, target_area)
        for task in main_tasks:
            task_list.add_task(task)
        
        # Add integration/wiring task
        wiring_task = self._create_wiring_task(intent, main_tasks)
        task_list.add_task(wiring_task)
        
        # Add test task
        test_task = self._create_test_task(intent)
        task_list.add_task(test_task)
        
        return {"task_list": task_list}
    
    def _create_setup_task(self, intent: Dict[str, Any]) -> Task:
        """Create initial setup/boilerplate task."""
        return Task(
            title="Setup and Configuration",
            description="Initialize project structure, install dependencies, verify dev server runs",
            complexity=TaskComplexity.SMALL,
            priority=TaskPriority.CRITICAL,
            target_area="config",
            acceptance_criteria=[
                AcceptanceCriterion(
                    description="Dev server starts without errors",
                    is_automated=True,
                    validation_command="npm run dev"
                ),
                AcceptanceCriterion(
                    description="All dependencies installed",
                    is_automated=True
                )
            ],
            expected_outputs=[
                ExpectedOutput(file_path="package.json", action="modify"),
            ],
            estimated_minutes=30
        )
    
    def _decompose_by_area(
        self, 
        intent: Dict[str, Any], 
        target_area: str
    ) -> List[Task]:
        """Create tasks based on target area."""
        tasks = []
        description = intent.get("description", "Implement feature")
        
        if target_area in ["frontend", "full-stack"]:
            tasks.append(Task(
                title="Frontend UI Implementation",
                description=f"Implement frontend UI for: {description}",
                complexity=TaskComplexity.MEDIUM,
                priority=TaskPriority.HIGH,
                target_area="frontend",
                is_parallelizable=True,
                acceptance_criteria=[
                    AcceptanceCriterion(
                        description="UI renders without errors",
                        is_automated=True
                    ),
                    AcceptanceCriterion(
                        description="Component matches design requirements",
                        is_automated=False
                    )
                ],
                estimated_minutes=120
            ))
        
        if target_area in ["backend", "full-stack"]:
            tasks.append(Task(
                title="Backend API Implementation",
                description=f"Implement backend API for: {description}",
                complexity=TaskComplexity.MEDIUM,
                priority=TaskPriority.HIGH,
                target_area="backend",
                is_parallelizable=True,
                acceptance_criteria=[
                    AcceptanceCriterion(
                        description="API endpoint responds correctly",
                        is_automated=True
                    ),
                    AcceptanceCriterion(
                        description="Data validation works",
                        is_automated=True
                    )
                ],
                estimated_minutes=120
            ))
        
        if target_area in ["database", "full-stack"]:
            tasks.append(Task(
                title="Database Schema/Model",
                description=f"Create database schema for: {description}",
                complexity=TaskComplexity.SMALL,
                priority=TaskPriority.HIGH,
                target_area="database",
                acceptance_criteria=[
                    AcceptanceCriterion(
                        description="Migrations run successfully",
                        is_automated=True
                    )
                ],
                estimated_minutes=60
            ))
        
        return tasks
    
    def _create_wiring_task(
        self, 
        intent: Dict[str, Any], 
        main_tasks: List[Task]
    ) -> Task:
        """Create integration/wiring task."""
        deps = [{"task_id": t.id, "dependency_type": "required_before"} for t in main_tasks]
        return Task(
            title="Integration and Wiring",
            description="Connect all components, wire up API calls, verify end-to-end flow",
            complexity=TaskComplexity.SMALL,
            priority=TaskPriority.HIGH,
            target_area="full-stack",
            dependencies=[{"task_id": t.id, "dependency_type": "required_before"} for t in main_tasks],
            acceptance_criteria=[
                AcceptanceCriterion(
                    description="End-to-end flow works",
                    is_automated=True
                )
            ],
            estimated_minutes=60
        )
    
    def _create_test_task(self, intent: Dict[str, Any]) -> Task:
        """Create testing task."""
        return Task(
            title="Testing and Validation",
            description="Write unit tests, integration tests, verify coverage",
            complexity=TaskComplexity.SMALL,
            priority=TaskPriority.MEDIUM,
            target_area="full-stack",
            acceptance_criteria=[
                AcceptanceCriterion(
                    description=f"Test coverage >= {self.config.min_test_coverage * 100}%",
                    is_automated=True,
                    validation_command="npm test -- --coverage"
                )
            ],
            estimated_minutes=90
        )


# ============================================================================
# FOLDER ARCHITECT
# ============================================================================

class FolderArchitect(PlannerComponent):
    """
    Produces Folder Map consistent with stack and App Blueprint.
    
    Key behaviors:
    - Align naming with Policy Table
    - Indicate generated vs hand-written code locations
    - Match framework conventions
    """
    
    FRAMEWORK_STRUCTURES = {
        "react": {
            "src/": FileRole.SOURCE,
            "src/components/": FileRole.COMPONENT,
            "src/pages/": FileRole.SOURCE,
            "src/hooks/": FileRole.UTILITY,
            "src/services/": FileRole.SERVICE,
            "src/utils/": FileRole.UTILITY,
            "src/types/": FileRole.MODEL,
            "src/styles/": FileRole.STYLE,
            "tests/": FileRole.TEST,
            "public/": FileRole.ASSET,
        },
        "nextjs": {
            "app/": FileRole.SOURCE,
            "app/api/": FileRole.API,
            "components/": FileRole.COMPONENT,
            "lib/": FileRole.SERVICE,
            "hooks/": FileRole.UTILITY,
            "types/": FileRole.MODEL,
            "styles/": FileRole.STYLE,
            "tests/": FileRole.TEST,
            "public/": FileRole.ASSET,
        },
        "fastapi": {
            "app/": FileRole.SOURCE,
            "app/api/": FileRole.API,
            "app/models/": FileRole.MODEL,
            "app/services/": FileRole.SERVICE,
            "app/core/": FileRole.UTILITY,
            "tests/": FileRole.TEST,
        }
    }
    
    def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate folder structure.
        
        Args:
            context: Contains 'intent', 'task_list', 'framework'
            
        Returns:
            Dict with 'folder_map' artifact
        """
        intent = context.get("intent", {})
        task_list = context.get("task_list")
        framework = context.get("framework", "react")
        
        folder_map = FolderMap()
        
        # Get base structure for framework
        base_structure = self.FRAMEWORK_STRUCTURES.get(framework, {})
        
        # Add base directories
        for path, role in base_structure.items():
            folder_map.entries.append(FolderEntry(
                path=path,
                is_directory=True,
                role=role,
                description=f"Standard {framework} directory",
                is_existing=True
            ))
        
        # Add files from task outputs
        if task_list:
            for task in task_list.tasks:
                for output in task.expected_outputs:
                    folder_map.entries.append(FolderEntry(
                        path=output.file_path,
                        is_directory=False,
                        description=output.description,
                        owner_task_id=task.id,
                        action=output.action,
                        role=self._infer_role(output.file_path)
                    ))
        
        return {"folder_map": folder_map}
    
    def _infer_role(self, path: str) -> FileRole:
        """Infer file role from path."""
        path_lower = path.lower()
        if "test" in path_lower or "spec" in path_lower:
            return FileRole.TEST
        if "component" in path_lower:
            return FileRole.COMPONENT
        if "service" in path_lower:
            return FileRole.SERVICE
        if "api" in path_lower or "route" in path_lower:
            return FileRole.API
        if "model" in path_lower or "type" in path_lower:
            return FileRole.MODEL
        if "util" in path_lower or "helper" in path_lower:
            return FileRole.UTILITY
        if "style" in path_lower or ".css" in path_lower:
            return FileRole.STYLE
        return FileRole.SOURCE


# ============================================================================
# CONTRACT AUTHOR
# ============================================================================

class ContractAuthor(PlannerComponent):
    """
    Produces minimal, precise API contracts.
    
    Key behaviors:
    - Minimal API surface to start
    - Mark unresolvable items with clarifying questions
    - Include example payloads for parallel work
    """
    
    def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate API contracts.
        
        Args:
            context: Contains 'intent', 'task_list'
            
        Returns:
            Dict with 'api_contracts' artifact
        """
        intent = context.get("intent", {})
        task_list = context.get("task_list")
        
        contracts = APIContracts()
        
        # Extract API needs from intent
        requires_api = intent.get("requires_api", False)
        
        if requires_api or intent.get("target_area") in ["backend", "full-stack"]:
            # Create basic CRUD endpoints based on intent
            endpoints = self._generate_crud_endpoints(intent)
            contracts.endpoints.extend(endpoints)
        
        return {"api_contracts": contracts}
    
    def _generate_crud_endpoints(self, intent: Dict[str, Any]) -> List[APIEndpoint]:
        """Generate CRUD endpoints from intent."""
        description = intent.get("description", "resource")
        # Extract noun from description (simplified)
        resource = description.split()[0].lower() if description else "item"
        
        endpoints = []
        
        # GET list
        endpoints.append(APIEndpoint(
            path=f"/api/{resource}s",
            method=HTTPMethod.GET,
            description=f"List all {resource}s",
            success_status=200,
            success_response=PayloadSchema(
                fields=[
                    FieldSchema(name="items", type="array", description=f"List of {resource}s"),
                    FieldSchema(name="total", type="integer", description="Total count")
                ]
            )
        ))
        
        # POST create
        endpoints.append(APIEndpoint(
            path=f"/api/{resource}s",
            method=HTTPMethod.POST,
            description=f"Create new {resource}",
            success_status=201,
            request_schema=PayloadSchema(
                fields=[
                    FieldSchema(name="data", type="object", description="Resource data")
                ]
            ),
            success_response=PayloadSchema(
                fields=[
                    FieldSchema(name="id", type="string", description="Created ID"),
                    FieldSchema(name="data", type="object", description="Created resource")
                ]
            )
        ))
        
        # GET single
        endpoints.append(APIEndpoint(
            path=f"/api/{resource}s/{{id}}",
            method=HTTPMethod.GET,
            description=f"Get single {resource}",
            path_params=[FieldSchema(name="id", type="string")],
            success_status=200
        ))
        
        return endpoints


# ============================================================================
# DEPENDENCY PLANNER
# ============================================================================

class DependencyPlanner(PlannerComponent):
    """
    Proposes packages and dev environment.
    
    Key behaviors:
    - Prefer well-known, stable packages
    - Flag new/unvetted libraries as high risk
    - Detect conflicts with Policy Table
    """
    
    # Common packages by framework
    FRAMEWORK_DEPS = {
        "react": [
            PackageDependency(name="react", version="^18.0.0"),
            PackageDependency(name="react-dom", version="^18.0.0"),
        ],
        "nextjs": [
            PackageDependency(name="next", version="^14.0.0"),
            PackageDependency(name="react", version="^18.0.0"),
            PackageDependency(name="react-dom", version="^18.0.0"),
        ],
        "fastapi": [
            PackageDependency(name="fastapi", version=">=0.100.0"),
            PackageDependency(name="uvicorn", version=">=0.20.0"),
            PackageDependency(name="pydantic", version=">=2.0.0"),
        ]
    }
    
    def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate dependency plan.
        
        Args:
            context: Contains 'intent', 'framework', 'constraints'
            
        Returns:
            Dict with 'dependency_plan' artifact
        """
        intent = context.get("intent", {})
        framework = context.get("framework", "react")
        
        plan = DependencyPlan()
        
        # Set package manager based on framework
        if framework in ["react", "nextjs"]:
            plan.package_manager = "npm"
            plan.node_version = ">=18.0.0"
        elif framework == "fastapi":
            plan.package_manager = "pip"
            plan.python_version = ">=3.10"
        
        # Add framework dependencies
        framework_deps = self.FRAMEWORK_DEPS.get(framework, [])
        plan.runtime_dependencies.extend(framework_deps)
        
        # Add dev dependencies
        plan.dev_dependencies.extend([
            PackageDependency(name="typescript", is_dev=True) if framework != "fastapi" else PackageDependency(name="pytest", is_dev=True),
        ])
        
        # Add common commands
        if framework in ["react", "nextjs"]:
            plan.commands = [
                RunCommand(name="dev", command="npm run dev", description="Start dev server"),
                RunCommand(name="build", command="npm run build", description="Production build"),
                RunCommand(name="test", command="npm test", description="Run tests"),
            ]
        elif framework == "fastapi":
            plan.commands = [
                RunCommand(name="dev", command="uvicorn main:app --reload", description="Start dev server"),
                RunCommand(name="test", command="pytest", description="Run tests"),
            ]
        
        return {"dependency_plan": plan}


# ============================================================================
# TEST DESIGNER
# ============================================================================

class TestDesigner(PlannerComponent):
    """
    Translates acceptance criteria into concrete checks.
    
    Key behaviors:
    - At least one measurable assertion per task
    - Provide smoke tests for runtime sanity
    - Deterministic test cases
    """
    
    def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate validation checklist.
        
        Args:
            context: Contains 'task_list', 'api_contracts'
            
        Returns:
            Dict with 'validation_checklist' artifact
        """
        task_list = context.get("task_list")
        
        checklist = ValidationChecklist()
        checklist.min_unit_test_coverage = self.config.min_test_coverage
        
        # Add smoke tests
        checklist.smoke_tests = [
            "Application boots without errors",
            "Main route responds with 200",
            "No console errors in browser",
        ]
        
        # Generate checks from task acceptance criteria
        if task_list:
            for task in task_list.tasks:
                for criterion in task.acceptance_criteria:
                    check = ValidationCheck(
                        name=f"Check: {criterion.description[:50]}",
                        description=criterion.description,
                        check_type="unit" if criterion.is_automated else "manual",
                        assertion=criterion.description,
                        command=criterion.validation_command,
                        is_automated=criterion.is_automated,
                        owner_task_id=task.id
                    )
                    
                    if criterion.is_automated:
                        checklist.unit_checks.append(check)
                    else:
                        checklist.manual_checks.append(check)
        
        # Add runtime checks
        checklist.runtime_checks = [
            ValidationCheck(
                name="App Boots",
                description="Application starts without 500 errors",
                check_type="runtime",
                assertion="GET / returns 200 or 3xx"
            )
        ]
        
        return {"validation_checklist": checklist}


# ============================================================================
# RISK ASSESSOR
# ============================================================================

class RiskAssessor(PlannerComponent):
    """
    Estimates technical risk and recommends mitigations.
    
    Key behaviors:
    - Score risk per task
    - Group clarifying questions
    - Recommend spike tasks for high-risk items
    """
    
    def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate risk report.
        
        Args:
            context: Contains 'task_list', 'dependency_plan', 'intent'
            
        Returns:
            Dict with 'risk_report' artifact
        """
        intent = context.get("intent", {})
        task_list = context.get("task_list")
        dependency_plan = context.get("dependency_plan")
        
        report = RiskReport()
        
        # Check for ambiguous intent
        if intent.get("is_ambiguous"):
            report.add_risk(RiskItem(
                title="Ambiguous Requirements",
                description="The original request was flagged as ambiguous",
                risk_level=RiskLevel.MEDIUM,
                category="unknown",
                requires_human_input=True,
                clarifying_questions=intent.get("clarification_questions", [])
            ))
        
        # Check for high complexity tasks
        if task_list:
            large_tasks = [t for t in task_list.tasks if t.complexity == TaskComplexity.LARGE]
            if large_tasks:
                report.add_risk(RiskItem(
                    title="Large Task Detected",
                    description=f"{len(large_tasks)} task(s) exceed recommended complexity",
                    risk_level=RiskLevel.MEDIUM,
                    category="technical",
                    mitigation="Consider decomposing into smaller tasks",
                    affected_tasks=[t.id for t in large_tasks]
                ))
        
        # Check for new dependencies
        if dependency_plan:
            new_deps = [d for d in dependency_plan.runtime_dependencies if d.confidence < 0.8]
            if new_deps:
                report.add_risk(RiskItem(
                    title="New Dependencies",
                    description=f"{len(new_deps)} dependency decisions have low confidence",
                    risk_level=RiskLevel.LOW,
                    category="dependency",
                    mitigation="Review and confirm package choices"
                ))
        
        return {"risk_report": report}
