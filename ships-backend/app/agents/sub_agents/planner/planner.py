"""
ShipS* Planner Agent

The Planner converts validated Intent Specs into actionable Plan artifacts.
It is the translator from intent → artifact-first execution plan.

Uses Gemini 3 Pro for complex planning with streaming support.

Responsibilities:
- Translate intent into scope-limited, prioritized tasks
- Produce folder structure guidance
- Produce API/data contracts
- Produce dependency and run-plan
- Produce test plan and validation checklist
- Flag blockers and emit clarifying questions
"""

from datetime import datetime
from typing import Optional, Dict, Any, List, AsyncIterator
import json
import re
import uuid

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.base.base_agent import BaseAgent
from app.graphs.state import AgentState
from app.artifacts import ArtifactManager

from app.agents.sub_agents.planner.models import (
    PlanManifest, TaskList, FolderMap, APIContracts,
    DependencyPlan, ValidationChecklist, RiskReport,
    ArtifactMetadata, Task, TaskComplexity, TaskPriority,
    PlannerComponentConfig,
)

# Tools are in central location: app/agents/tools/planner/
from app.agents.tools.planner import PlannerTools


class Planner(BaseAgent):
    """
    Planner Agent - Converts Intent to Actionable Plan.
    
    Uses Gemini 3 Pro for complex planning tasks.
    Produces 7 discrete artifacts consumed by downstream agents.
    
    Features:
    - Modular subcomponents for each artifact type
    - Streaming support for real-time feedback
    - Deterministic heuristics for reproducible plans
    - Vertical-slice-first prioritization
    """
    
    def __init__(
        self,
        artifact_manager: Optional[ArtifactManager] = None,
        config: Optional[PlannerComponentConfig] = None
    ):
        """
        Initialize the Planner.
        
        Args:
            artifact_manager: Optional artifact manager
            config: Planner configuration
        """
        super().__init__(
            name="Planner",
            agent_type="planner",  # Uses Pro model
            reasoning_level="standard",
            artifact_manager=artifact_manager
        )
        
        self.config = config or PlannerComponentConfig()
        
        # Initialize subcomponents
        self.scoper = Scoper(self.config)
        self.folder_architect = FolderArchitect(self.config)
        self.contract_author = ContractAuthor(self.config)
        self.dependency_planner = DependencyPlanner(self.config)
        self.test_designer = TestDesigner(self.config)
        self.risk_assessor = RiskAssessor(self.config)
        
        # Tools
        self.tools = PlannerTools()
    
    def _get_system_prompt(self) -> str:
        """Get the system prompt for planning."""
        return """You are the Planner for ShipS*, an AI coding system that SHIPS WORKING CODE.

Your job is to convert Intent Specs into actionable Plans.

CORE RULES:
1. ARTIFACT-FIRST: Output machine-readable, verifiable artifacts
2. VERTICAL-SLICE BIAS: Always structure for earliest runnable preview
3. CONSERVATIVE INFERENCE: Mark inferred items with confidence < 1.0
4. DETERMINISTIC: Behaviors driven by explicit heuristics, not creativity
5. TRACEABLE: Every decision must be explainable in one sentence

DO NOT generate implementation code. You produce PLANS, not CODE.

TASK SIZING RULES:
- TINY: < 30 minutes
- SMALL: 30 min - 2 hours
- MEDIUM: 2-4 hours
- LARGE: 4-8 hours (should be decomposed)

PRIORITIZATION:
1. Setup/boilerplate tasks first (critical)
2. Core functionality (high)
3. Integration/wiring (high)
4. Testing/polish (medium)

OUTPUT FORMAT:
Produce a JSON object with the following structure:
{
    "summary": "One-line plan summary",
    "tasks": [
        {
            "title": "Task title",
            "description": "Detailed description",
            "complexity": "tiny|small|medium|large",
            "priority": "critical|high|medium|low",
            "target_area": "frontend|backend|database|full-stack|config",
            "acceptance_criteria": ["Criterion 1", "Criterion 2"],
            "expected_outputs": [{"path": "path/to/file", "action": "create|modify"}],
            "estimated_minutes": 60
        }
    ],
    "folders": [
        {"path": "src/components/", "description": "React components", "is_directory": true}
    ],
    "api_endpoints": [
        {"path": "/api/resource", "method": "GET", "description": "Get resources"}
    ],
    "dependencies": {
        "runtime": [{"name": "react", "version": "^18.0.0"}],
        "dev": [{"name": "typescript", "is_dev": true}]
    },
    "risks": [
        {"title": "Risk title", "level": "low|medium|high", "mitigation": "How to address"}
    ],
    "clarifying_questions": ["Question if needed"],
    "decision_notes": ["Rationale for key decision"]
}"""
    
    async def plan(
        self,
        intent: Dict[str, Any],
        app_blueprint: Optional[Dict[str, Any]] = None,
        constraints: Optional[Dict[str, Any]] = None,
        environment: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate a complete plan from intent.
        
        This is the main entry point for planning.
        
        Args:
            intent: Structured intent from Intent Classifier
            app_blueprint: Optional app blueprint
            constraints: Optional policy/constraints
            environment: Optional environment profile
            
        Returns:
            Dict containing all 7 plan artifacts
        """
        # Build context
        context = {
            "intent": intent,
            "app_blueprint": app_blueprint or {},
            "constraints": constraints or {},
            "environment": environment or {},
        }
        
        # Detect framework
        framework = self.tools.detect_framework(context)
        context["framework"] = framework
        
        # ================================================================
        # SCAFFOLDING DETECTION: Check if project needs setup
        # ================================================================
        project_path = environment.get("project_path") if environment else None
        user_request = intent.get("description", "")
        
        scaffolding_result = self.tools.analyze_project_for_scaffolding(
            project_path, 
            user_request
        )
        context["scaffolding"] = scaffolding_result
        
        # Step 1: Use LLM for high-level planning
        llm_plan = await self._generate_llm_plan(intent, context)
        
        # Step 2: Run subcomponents to produce artifacts
        # Scoper: Task decomposition
        scope_result = self.scoper.process(context)
        task_list = scope_result["task_list"]
        
        # ================================================================
        # INJECT SCAFFOLDING TASK: Add as Task 0 if needed
        # ================================================================
        if scaffolding_result.get("scaffolding_task"):
            scaffolding_task_dict = scaffolding_result["scaffolding_task"]
            from app.agents.sub_agents.planner.models import Task, TaskComplexity, TaskPriority
            
            scaffold_task = Task(
                id=scaffolding_task_dict.get("id", "task_scaffold_0"),
                title=scaffolding_task_dict.get("title", "Setup Project"),
                description=scaffolding_task_dict.get("description", ""),
                complexity=TaskComplexity.SMALL,
                priority=TaskPriority.CRITICAL,
                order=0,
                estimated_minutes=5,
            )
            
            # Store terminal commands in metadata for coder to use
            scaffold_task.metadata = {
                "terminal_commands": scaffolding_task_dict.get("terminal_commands", []),
                "is_scaffolding_task": True,
            }
            
            # Insert at beginning of task list
            task_list.tasks.insert(0, scaffold_task)
            
            # Reorder all other tasks
            for i, task in enumerate(task_list.tasks[1:], start=1):
                task.order = i
        
        # Enrich task list with LLM insights
        self._enrich_task_list(task_list, llm_plan)
        context["task_list"] = task_list
        
        # FolderArchitect: Folder structure
        folder_result = self.folder_architect.process(context)
        folder_map = folder_result["folder_map"]
        self._enrich_folder_map(folder_map, llm_plan)
        context["folder_map"] = folder_map
        
        # ContractAuthor: API contracts
        contract_result = self.contract_author.process(context)
        api_contracts = contract_result["api_contracts"]
        self._enrich_api_contracts(api_contracts, llm_plan)
        context["api_contracts"] = api_contracts
        
        # DependencyPlanner: Dependencies
        dep_result = self.dependency_planner.process(context)
        dependency_plan = dep_result["dependency_plan"]
        self._enrich_dependencies(dependency_plan, llm_plan)
        context["dependency_plan"] = dependency_plan
        
        # TestDesigner: Validation checklist
        test_result = self.test_designer.process(context)
        validation_checklist = test_result["validation_checklist"]
        
        # RiskAssessor: Risk report
        risk_result = self.risk_assessor.process(context)
        risk_report = risk_result["risk_report"]
        self._enrich_risks(risk_report, llm_plan)
        
        # Step 3: Assemble Plan Manifest
        plan_manifest = self.tools.assemble_plan_manifest(
            intent_spec_id=intent.get("id", str(uuid.uuid4())),
            summary=llm_plan.get("summary", "Implementation plan"),
            task_list=task_list,
            folder_map=folder_map,
            api_contracts=api_contracts,
            dependency_plan=dependency_plan,
            validation_checklist=validation_checklist,
            risk_report=risk_report
        )
        
        # Add decision notes from LLM
        plan_manifest.metadata.decision_notes = llm_plan.get("decision_notes", [])
        
        # Log action
        if self._artifact_manager:
            self.log_action(
                action="plan_generated",
                input_summary=intent.get("description", "")[:100],
                output_summary=f"{len(task_list.tasks)} tasks, {len(folder_map.entries)} files",
                reasoning=plan_manifest.summary
            )
        
        return {
            "plan_manifest": plan_manifest,
            "task_list": task_list,
            "folder_map": folder_map,
            "api_contracts": api_contracts,
            "dependency_plan": dependency_plan,
            "validation_checklist": validation_checklist,
            "risk_report": risk_report,
        }
    
    async def _generate_llm_plan(
        self, 
        intent: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Use LLM for high-level planning insights."""
        prompt = self._build_planning_prompt(intent, context)
        
        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=prompt)
        ]
        
        try:
            response = await self.llm.ainvoke(messages)
            return self._parse_llm_response(response.content)
        except Exception as e:
            # Fallback to minimal plan
            return {
                "summary": intent.get("description", "Implementation plan"),
                "tasks": [],
                "decision_notes": [f"LLM planning failed: {str(e)}"]
            }
    
    def _build_planning_prompt(
        self, 
        intent: Dict[str, Any],
        context: Dict[str, Any]
    ) -> str:
        """Build the prompt for LLM planning."""
        parts = []
        
        # Intent
        parts.append(f"INTENT:\n{json.dumps(intent, indent=2)}")
        
        # Framework
        parts.append(f"FRAMEWORK: {context.get('framework', 'react')}")
        
        # Constraints
        if context.get("constraints"):
            parts.append(f"CONSTRAINTS:\n{json.dumps(context['constraints'], indent=2)[:500]}")
        
        parts.append("\nCreate a detailed plan following the output format. Output ONLY valid JSON:")
        
        return "\n\n".join(parts)
    
    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """Parse LLM response to JSON."""
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass
        
        # Try extracting JSON
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass
        
        return {"summary": "Plan generated", "tasks": []}
    
    def _enrich_task_list(self, task_list: TaskList, llm_plan: Dict[str, Any]) -> None:
        """Enrich task list with LLM insights."""
        llm_tasks = llm_plan.get("tasks", [])
        for llm_task in llm_tasks:
            # Find matching task or create new
            title = llm_task.get("title", "")
            existing = next((t for t in task_list.tasks if title.lower() in t.title.lower()), None)
            
            if existing:
                # Enrich existing task
                if llm_task.get("acceptance_criteria"):
                    from app.agents.sub_agents.planner.models import AcceptanceCriterion
                    for criterion in llm_task["acceptance_criteria"]:
                        existing.acceptance_criteria.append(
                            AcceptanceCriterion(description=criterion)
                        )
            else:
                # Add new task from LLM
                new_task = Task(
                    title=title,
                    description=llm_task.get("description", ""),
                    complexity=TaskComplexity(llm_task.get("complexity", "small")),
                    priority=TaskPriority(llm_task.get("priority", "medium")),
                    estimated_minutes=llm_task.get("estimated_minutes", 60)
                )
                task_list.add_task(new_task)
    
    def _enrich_folder_map(self, folder_map: FolderMap, llm_plan: Dict[str, Any]) -> None:
        """Enrich folder map with LLM insights."""
        llm_folders = llm_plan.get("folders", [])
        existing_paths = {e.path for e in folder_map.entries}
        
        for folder in llm_folders:
            path = folder.get("path", "")
            if path and path not in existing_paths:
                from app.agents.sub_agents.planner.models import FolderEntry
                folder_map.entries.append(FolderEntry(
                    path=path,
                    is_directory=folder.get("is_directory", True),
                    description=folder.get("description", "")
                ))
    
    def _enrich_api_contracts(self, api_contracts: APIContracts, llm_plan: Dict[str, Any]) -> None:
        """Enrich API contracts with LLM insights."""
        llm_endpoints = llm_plan.get("api_endpoints", [])
        existing_paths = {e.path for e in api_contracts.endpoints}
        
        for endpoint in llm_endpoints:
            path = endpoint.get("path", "")
            if path and path not in existing_paths:
                from app.agents.sub_agents.planner.models import APIEndpoint, HTTPMethod
                api_contracts.endpoints.append(APIEndpoint(
                    path=path,
                    method=HTTPMethod(endpoint.get("method", "GET")),
                    description=endpoint.get("description", "")
                ))
    
    def _enrich_dependencies(self, dependency_plan: DependencyPlan, llm_plan: Dict[str, Any]) -> None:
        """Enrich dependencies with LLM insights."""
        llm_deps = llm_plan.get("dependencies", {})
        existing_names = {d.name for d in dependency_plan.runtime_dependencies}
        
        for dep in llm_deps.get("runtime", []):
            name = dep.get("name", "")
            if name and name not in existing_names:
                from app.agents.sub_agents.planner.models import PackageDependency
                dependency_plan.runtime_dependencies.append(PackageDependency(
                    name=name,
                    version=dep.get("version", "latest")
                ))
    
    def _enrich_risks(self, risk_report: RiskReport, llm_plan: Dict[str, Any]) -> None:
        """Enrich risk report with LLM insights."""
        llm_risks = llm_plan.get("risks", [])
        
        for risk in llm_risks:
            from app.agents.sub_agents.planner.models import RiskItem, RiskLevel
            risk_report.add_risk(RiskItem(
                title=risk.get("title", "Risk"),
                risk_level=RiskLevel(risk.get("level", "medium")),
                mitigation=risk.get("mitigation", "")
            ))
        
        # Add clarifying questions
        questions = llm_plan.get("clarifying_questions", [])
        if questions:
            from app.agents.sub_agents.planner.models import RiskItem
            risk_report.add_risk(RiskItem(
                title="Clarifications Needed",
                category="unknown",
                requires_human_input=True,
                clarifying_questions=questions
            ))
    
    async def plan_streaming(
        self,
        intent: Dict[str, Any],
        app_blueprint: Optional[Dict[str, Any]] = None
    ) -> AsyncIterator[str]:
        """
        Plan with streaming output for real-time feedback.
        
        Yields chunks of the plan as they're generated.
        """
        context = {
            "intent": intent,
            "app_blueprint": app_blueprint or {},
            "framework": self.tools.detect_framework({"app_blueprint": app_blueprint})
        }
        
        prompt = self._build_planning_prompt(intent, context)
        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=prompt)
        ]
        
        full_response = ""
        async for chunk in self.llm.astream(messages):
            if hasattr(chunk, 'content'):
                full_response += chunk.content
                yield chunk.content
        
        # Parse and produce final artifacts
        llm_plan = self._parse_llm_response(full_response)
        yield f"\n\n__PLAN_PARSED__"
    
    async def invoke(self, state: AgentState) -> Dict[str, Any]:
        """
        Invoke the Planner as part of orchestrator workflow.
        
        Args:
            state: Current agent state
            
        Returns:
            Dict with 'artifacts' key containing all plan artifacts
        """
        artifacts = state.get("artifacts", {})
        parameters = state.get("parameters", {})
        
        # Get structured intent
        intent = artifacts.get("structured_intent", {})
        app_blueprint = artifacts.get("app_blueprint")
        constraints = artifacts.get("constraints")
        
        # Generate plan
        plan_result = await self.plan(
            intent=intent,
            app_blueprint=app_blueprint,
            constraints=constraints
        )
        
        # Convert to serializable dict
        return {
            "artifacts": {
                "plan_manifest": plan_result["plan_manifest"].model_dump(),
                "task_list": plan_result["task_list"].model_dump(),
                "folder_map": plan_result["folder_map"].model_dump(),
                "api_contracts": plan_result["api_contracts"].model_dump(),
                "dependency_plan": plan_result["dependency_plan"].model_dump(),
                "validation_checklist": plan_result["validation_checklist"].model_dump(),
                "risk_report": plan_result["risk_report"].model_dump(),
            }
        }
