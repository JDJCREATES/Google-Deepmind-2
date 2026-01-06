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
                # Handle both dict and Pydantic model (defensive)
                if hasattr(t_data, 'model_dump'):
                    t_data = t_data.model_dump()
                elif not isinstance(t_data, dict):
                    # Skip invalid task entries
                    continue
                    
                # Create structured AcceptanceCriterion objects
                criteria = []
                for ac_text in t_data.get("acceptance_criteria", []):
                    if isinstance(ac_text, str):
                        criteria.append(AcceptanceCriterion(description=ac_text))
                
                # Parse output files
                outputs = []
                for out in t_data.get("expected_outputs", []):
                    # Handle both 'path' (LLM output) and 'file_path' (model field)
                    file_path = out.get("file_path") or out.get("path", "")
                    outputs.append(ExpectedOutput(
                        file_path=file_path,
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

                )
                task_list.add_task(task)
        else:
            # Fallback: Generate granular tasks from description
            description = intent.get("description", "")
            
            # Always create foundational tasks
            tasks_to_create = [
                Task(
                    id="task_001",
                    title="Create Core Types and Interfaces",
                    description=f"Define TypeScript types for: {description[:100]}",
                    complexity=TaskComplexity.TINY,
                    priority=TaskPriority.HIGH,
                    status=TaskStatus.PENDING,
                    estimated_minutes=30,
                    acceptance_criteria=[
                        AcceptanceCriterion(description="All types are defined in src/types/"),
                        AcceptanceCriterion(description="Types are exported and importable")
                    ],
                    expected_outputs=[
                        ExpectedOutput(file_path="src/types/index.ts", description="Type definitions")
                    ],

                ),
                Task(
                    id="task_002",
                    title="Create State Management Hook",
                    description=f"Implement state logic for: {description[:100]}",
                    complexity=TaskComplexity.SMALL,
                    priority=TaskPriority.HIGH,
                    status=TaskStatus.PENDING,
                    estimated_minutes=45,
                    acceptance_criteria=[
                        AcceptanceCriterion(description="Hook manages component state"),
                        AcceptanceCriterion(description="State updates trigger re-renders")
                    ],
                    expected_outputs=[
                        ExpectedOutput(file_path="src/hooks/useApp.ts", description="Main state hook")
                    ],

                ),
                Task(
                    id="task_003",
                    title="Create Main UI Component",
                    description=f"Build the primary UI for: {description[:100]}",
                    complexity=TaskComplexity.SMALL,
                    priority=TaskPriority.HIGH,
                    status=TaskStatus.PENDING,
                    estimated_minutes=60,
                    acceptance_criteria=[
                        AcceptanceCriterion(description="Component renders without errors"),
                        AcceptanceCriterion(description="UI matches expected design")
                    ],
                    expected_outputs=[
                        ExpectedOutput(file_path="src/components/Main.tsx", description="Main component")
                    ],

                ),
                Task(
                    id="task_004",
                    title="Integrate Components in App",
                    description="Wire up all components in App.tsx",
                    complexity=TaskComplexity.TINY,
                    priority=TaskPriority.HIGH,
                    status=TaskStatus.PENDING,
                    estimated_minutes=20,
                    acceptance_criteria=[
                        AcceptanceCriterion(description="App renders main component"),
                        AcceptanceCriterion(description="Application runs in browser")
                    ],
                    expected_outputs=[
                        ExpectedOutput(file_path="src/App.tsx", description="App composition")
                    ],

                ),
                Task(
                    id="task_005",
                    title="Apply Styling",
                    description="Add CSS styling for visual appearance",
                    complexity=TaskComplexity.TINY,
                    priority=TaskPriority.MEDIUM,
                    status=TaskStatus.PENDING,
                    estimated_minutes=30,
                    acceptance_criteria=[
                        AcceptanceCriterion(description="Styles are applied"),
                        AcceptanceCriterion(description="Layout looks professional")
                    ],
                    expected_outputs=[
                        ExpectedOutput(file_path="src/index.css", description="Global styles")
                    ],

                ),
            ]
            
            for task in tasks_to_create:
                task_list.add_task(task)
        
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
        
        # Populate existing paths from file tree to prevent duplicates
        file_tree = context.get("file_tree", {})
        if file_tree.get("success"):
            for entry in file_tree.get("entries", []):
                existing_paths.add(entry["path"])
        
        for f_data in llm_folders:
            # Handle Pydantic objects or non-dicts defensively
            if hasattr(f_data, 'model_dump'):
                f_data = f_data.model_dump()
            elif not isinstance(f_data, dict):
                continue

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
        
        # NO FALLBACKS during testing - log warning so we can diagnose LLM output
        if not entries:
            import logging
            logger = logging.getLogger("ships.planner")
            logger.warning(
                f"[FOLDER_ARCHITECT] ⚠️ LLM returned no folders! "
                f"llm_folders was: {llm_folders}"
            )
        
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
            # Handle Pydantic objects or non-dicts defensively
            if hasattr(ep_data, 'model_dump'):
                ep_data = ep_data.model_dump()
            elif not isinstance(ep_data, dict):
                continue
                
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
        
        # Handle list structure (legacy/bad LLM output)
        if isinstance(llm_deps, list):
             llm_deps = {"runtime": llm_deps, "dev": []}
        # Handle Pydantic model
        elif hasattr(llm_deps, 'model_dump'):
            llm_deps = llm_deps.model_dump()
        
        # Runtime
        existing_runtime = {d.name for d in dependency_plan.runtime_dependencies}
        for dep in llm_deps.get("runtime", []) or []:
            # Handle Pydantic objects or non-dicts defensively
            if hasattr(dep, 'model_dump'):
                dep = dep.model_dump()
            elif not isinstance(dep, dict):
                continue

            name = dep.get("name", "")
            if name and name not in existing_runtime:
                dependency_plan.runtime_dependencies.append(PackageDependency(
                    name=name,
                    version=dep.get("version", "latest"),
                    purpose="Added by planner"
                ))
        
        # Dev
        existing_dev = {d.name for d in dependency_plan.dev_dependencies}
        for dep in llm_deps.get("dev", []) or []:
            # Handle Pydantic objects or non-dicts defensively
            if hasattr(dep, 'model_dump'):
                dep = dep.model_dump()
            elif not isinstance(dep, dict):
                continue

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
                category="technical",
                risk_level=RiskLevel.LOW,
                description="Project needs initial scaffolding",
                mitigation="Scaffold task added to plan",
                requires_human_input=False
            ))
            
        # 2. LLM Identified Risks
        for risk in llm_plan.get("risks", []):
            # Handle Pydantic objects or non-dicts defensively
            if hasattr(risk, 'model_dump'):
                risk = risk.model_dump()
            elif not isinstance(risk, dict):
                continue

            risk_report.add_risk(RiskItem(
                title=risk.get("title", "Identified Risk"),
                category="technical",
                risk_level=RiskLevel(risk.get("level", "medium")),
                description=risk.get("description", ""),
                mitigation=risk.get("mitigation", "")
            ))
        
        # 3. Clarifying Questions
        questions = llm_plan.get("clarifying_questions", [])
        if questions:
            risk_report.add_risk(RiskItem(
                title="Clarification Needed",
                category="unknown",
                risk_level=RiskLevel.HIGH,
                description="The following questions need answers:",
                requires_human_input=True,
                clarifying_questions=questions
            ))
        
        return {"risk_report": risk_report}


class Scaffolder:
    """
    Project scaffolding component.
    
    Builds scaffolding prompts and determines what scaffolding is needed
    based on project state and folder map.
    
    Does NOT execute scaffolding - that's done by the planner_node
    using a tool-calling agent.
    """
    
    def __init__(self, config: Optional[PlannerComponentConfig] = None):
        self.config = config or PlannerComponentConfig()
    
    def detect_framework(self, folder_map: Dict[str, Any]) -> str:
        """Detect target framework from folder map or entries."""
        entries = folder_map.get("entries", [])
        paths = [e.get("path", "") for e in entries]
        
        # Check for Next.js indicators
        if any("app/" in p and "page." in p for p in paths):
            return "nextjs"
        # Check for React/Vite
        if any("src/App" in p or "src/main" in p for p in paths):
            return "react-vite"
        # Check for Python/FastAPI
        if any("main.py" in p or "__init__.py" in p for p in paths):
            return "python"
        # Check for Vue
        if any("App.vue" in p for p in paths):
            return "vue"
        
        return "react-vite"  # Default
    
    def get_scaffold_command(self, framework: str) -> str:
        """Get the npx/npm command for scaffolding."""
        commands = {
            # Default to TypeScript for all React projects
            "react-vite": "npx -y create-vite@latest . --template react-ts",
            "react-vite-ts": "npx -y create-vite@latest . --template react-ts",
            "react": "npx -y create-vite@latest . --template react-ts",
            "nextjs": "npx -y create-next-app@latest . --typescript --yes --app --no-src-dir",
            "vue": "npx -y create-vue@latest . --typescript --default",
            "python": None,  # Python doesn't need npm scaffolding
        }
        return commands.get(framework, commands["react-vite"])
    
    def build_scaffolding_prompt(
        self,
        folder_map: Dict[str, Any],
        project_path: str,
        existing_files: List[str] = None
    ) -> str:
        """
        Build the prompt for the scaffolding agent.
        
        Args:
            folder_map: The FolderMap artifact from planning
            project_path: Path to the project directory
            existing_files: List of existing files in project
            
        Returns:
            Prompt string for the scaffolding agent
        """
        framework = self.detect_framework(folder_map)
        scaffold_cmd = self.get_scaffold_command(framework)
        
        # Build folder creation list
        folders_to_create = []
        files_to_create = []
        
        for entry in folder_map.get("entries", []):
            path = entry.get("path", "")
            is_dir = entry.get("is_directory", False) or path.endswith("/")
            
            if is_dir:
                folders_to_create.append(path.rstrip("/"))
            elif path.endswith("__init__.py") or "stub" in entry.get("role", ""):
                files_to_create.append(path)
        
        prompt_parts = [
            f"You are scaffolding a {framework} project at: {project_path}",
            "",
            "EXECUTE THESE STEPS IN ORDER:",
            "",
            "STEP 1: Check if project is already scaffolded",
            '- Call list_directory(".") to see current files',
            "- If package.json already exists, SKIP step 2",
            "",
        ]
        
        if scaffold_cmd:
            prompt_parts.extend([
                "STEP 2: Run framework scaffolding (ONLY if no package.json)",
                f'- Call run_terminal_command("{scaffold_cmd}")',
                '- Then call run_terminal_command("npm install")',
                "",
            ])
        
        if folders_to_create:
            prompt_parts.extend([
                "STEP 3: Create folder structure",
                "Create these folders using create_directory:",
            ])
            for folder in folders_to_create[:10]:  # Limit to prevent token explosion
                prompt_parts.append(f'  - create_directory("{folder}")')
            prompt_parts.append("")
        
        if files_to_create:
            prompt_parts.extend([
                "STEP 4: Create empty placeholder files",
                "Create these files using write_file_to_disk:",
            ])
            for file in files_to_create[:10]:  # Limit
                if file.endswith("__init__.py"):
                    prompt_parts.append(f'  - write_file_to_disk("{file}", "# {file}\\n")')
                else:
                    prompt_parts.append(f'  - write_file_to_disk("{file}", "// TODO: Implement\\n")')
            prompt_parts.append("")
        
        prompt_parts.extend([
            "STEP 5: Verify scaffolding",
            '- Call list_directory(".") to confirm structure',
            "",
            "IMPORTANT:",
            "- Use -y or --yes flags to avoid interactive prompts",
            "- If a command fails, log the error and continue",
            "- Do NOT write actual code - just create structure",
        ])
        
        return "\n".join(prompt_parts)
    
    def check_needs_scaffolding(self, existing_files: List[str]) -> bool:
        """Check if project needs scaffolding based on existing files."""
        scaffolding_indicators = [
            "package.json",
            "requirements.txt",
            "pyproject.toml",
            "Cargo.toml",
            "go.mod",
        ]
        return not any(ind in existing_files for ind in scaffolding_indicators)
    
    def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process context and return scaffolding configuration.
        
        Returns:
            Dict with scaffolding info (prompt, needs_scaffolding, framework)
        """
        folder_map = context.get("folder_map", {})
        project_path = context.get("project_path", ".")
        existing_files = context.get("existing_files", [])
        
        needs_scaffolding = self.check_needs_scaffolding(existing_files)
        framework = self.detect_framework(folder_map)
        
        result = {
            "needs_scaffolding": needs_scaffolding,
            "framework": framework,
            "scaffold_command": self.get_scaffold_command(framework),
        }
        
        if needs_scaffolding:
            result["scaffolding_prompt"] = self.build_scaffolding_prompt(
                folder_map, project_path, existing_files
            )
        
        return result


__all__ = [
    "Scoper",
    "FolderArchitect",
    "ContractAuthor",
    "DependencyPlanner",
    "TestDesigner",
    "RiskAssessor",
    "Scaffolder",
]

