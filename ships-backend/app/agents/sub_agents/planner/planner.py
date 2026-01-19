"""
ShipS* Planner Agent

The Planner converts validated Intent Specs into actionable Plan artifacts.
It is the translator from intent → artifact-first execution plan.

Uses Gemini 3 Flash preview for complex planning with streaming support.

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

from pydantic import BaseModel, Field

# Use centralized logging
from app.core.logger import get_logger, dev_log, truncate_for_log
logger = get_logger("planner")

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.base.base_agent import BaseAgent
from app.graphs.state import AgentState
from app.artifacts import ArtifactManager

from app.agents.sub_agents.planner.models import (
    PlanManifest, TaskList, FolderMap, APIContracts,
    DependencyPlan, ValidationChecklist, RiskReport,
    ArtifactMetadata, Task, TaskComplexity, TaskPriority,
    PlannerComponentConfig,
    # LLM Output Schemas
    LLMPlanOutput, LLMPlanTask, LLMPlanFolder
)

from app.agents.sub_agents.planner.enricher import PlanEnricher

# Dynamic prompt builder (injects project-type-specific conventions)
from app.prompts.planner import build_planner_prompt

# Tools are in central location: app/agents/tools/planner/
from app.agents.tools.planner import PlannerTools

# Subcomponents for artifact production
from app.agents.sub_agents.planner.components import (
    Scoper, FolderArchitect, ContractAuthor,
    DependencyPlanner, TestDesigner, RiskAssessor,
)

from app.streaming.stream_events import emit_event

# Persistence Imports (Moved from agent_graph.py)
from sqlalchemy import update
from app.database import get_session_factory
from app.models import AgentRun
from app.services.git_checkpointer import get_checkpointer



class Planner(BaseAgent):
    """
    Planner Agent - Converts Intent to Actionable Plan.
    
    Uses Gemini 3 Pro for complex planning tasks.
    Produces 7 discrete artifacts consumed by downstream agents.
    
    Features:
    - Dynamic prompts based on project type
    - Modular subcomponents for each artifact type
    - Streaming support for real-time feedback
    - Deterministic heuristics for reproducible plans
    - Vertical-slice-first prioritization
    """
    
    def __init__(
        self,
        artifact_manager: Optional[ArtifactManager] = None,
        config: Optional[PlannerComponentConfig] = None,
        cached_content: Optional[str] = None,
        project_type: str = "web_app"  # Default, can be updated from intent
    ):
        """
        Initialize the Planner.
        
        Args:
            artifact_manager: Optional artifact manager
            config: Planner configuration
            project_type: Project type for prompt template
        """
        self.current_project_type = project_type
        
        super().__init__(
            name="Planner",
            agent_type="planner",  # Uses Pro model
            reasoning_level="high",  # Planner needs deep thought
            artifact_manager=artifact_manager,
            cached_content=cached_content
        )
        
        self.config = config or PlannerComponentConfig()
        
        # Initialize subcomponents
        self.scoper = Scoper(self.config)
        self.folder_architect = FolderArchitect(self.config)
        self.contract_author = ContractAuthor(self.config)
        self.dependency_planner = DependencyPlanner(self.config)
        self.test_designer = TestDesigner(self.config)
        self.test_designer = TestDesigner(self.config)
        self.risk_assessor = RiskAssessor(self.config)
        
        # Data Enricher
        self.enricher = PlanEnricher()
        
        # Tools
        self.tools = PlannerTools()
    
    def _get_system_prompt(self, artifacts: Dict[str, Any] = None) -> str:
        """Get the system prompt with project-type-specific conventions injected."""
        environment = self.environment if hasattr(self, 'environment') else {}
        file_tree = environment.get("file_tree", {})
        project_has_files = False
        
        if file_tree and "children" in file_tree:
            project_has_files = True
        
        # EDIT MODE DETECTION
        # Use structured INTENT scope from Intent Classifier
        is_edit_mode = False
        
        # Get scope and task_type from artifacts (passed from plan())
        intent_scope = "feature"
        task_type = "feature"
        if artifacts:
             intent_scope = artifacts.get("scope", "feature")
             task_type = artifacts.get("task_type", "feature")
             
        if project_has_files:
            # If scope is PROJECT, allow scaffolding (Edit Mode OFF)
            # Otherwise (feature, layer, component, etc), enforce Edit Mode
            if intent_scope == "project":
                is_edit_mode = False
                logger.info("[PLANNER] 🏗️ Scope 'project' detected - Edit Mode DISABLED (Full Scaffolding Allowed)")
            else:
                is_edit_mode = True
                logger.info(f"[PLANNER] ✏️ Edit Mode ACTIVATED (Scope: {intent_scope})")

        # Get base prompt with conventions for this project type (passing edit mode and task type)
        base_prompt = build_planner_prompt(
            self.current_project_type, 
            is_edit_mode=is_edit_mode,
            task_type=task_type
        )
        
        scaffold_warning = ""
        if project_has_files:
            scaffold_warning = """
# CRITICAL: EXISTING PROJECT DETECTED
You are operating on an **EXISTING PROJECT**.
- **DO NOT SCAFFOLD** a new app (no `create-react-app`, `create-vite`, etc.).
- **DO NOT** create a new root subfolder unless explicitly asked to "create a NEW app".
- **DO NOT** overwrite existing configuration unless asked.
- **DO** simply add the requested feature files to the EXISTING structure.
- **DO** update `package.json` only if adding dependencies.
"""
        else:
             # Only show subfolder rule if NEW project
             scaffold_warning = """
# CRITICAL: NEW PROJECT DETECTED
You are creating a **NEW PROJECT from scratch**.
- You MUST scaffold into a **NAMED SUBFOLDER** (e.g. `todo-frontend/`), NOT root (`.`).
- Prefix all file paths in `folder_map_plan.json` with this subfolder.
"""

        # Append task granularity rules (these are project-agnostic)
        task_rules = f"""
{scaffold_warning}

# TASK GRANULARITY REQUIREMENTS (CRITICAL)

You MUST generate **4-6 granular tasks minimum** for any request.
Each task should be:
- Completable in ONE coding session (under 2 hours)
- Focused on ONE specific feature or file group
- Have CONCRETE file outputs (not abstract goals)
- Independently testable

TASK SIZING:
- TINY: < 30 min (single file)
- SMALL: 30 min - 2 hours (2-3 files)
- MEDIUM: 2-4 hours (decompose if possible)
- LARGE: MUST be decomposed into smaller tasks

OUTPUT: Produce JSON with tasks, folders, api_endpoints, dependencies, risks.

REMEMBER: Fewer than 4 tasks = WRONG. Break it down further!"""
        
        # Add validation feedback if retrying
        feedback_section = ""
        if artifacts:
            validation_feedback = artifacts.get("validation_feedback", [])
            previous_plan = artifacts.get("previous_plan")  # Get previous attempt
            
            if validation_feedback and previous_plan:
                # Format previous plan for context
                plan_summary = previous_plan.get("summary", "")
                task_count = len(previous_plan.get("tasks", []))
                
                feedback_section = f"""

# INCREMENTAL EDIT MODE (Fix Existing Plan)

Your previous plan needs minor improvements. DO NOT regenerate from scratch.
Instead, EDIT the existing plan to address the issues below.

PREVIOUS PLAN SUMMARY:
{plan_summary}
({task_count} tasks defined)

ISSUES TO FIX:
{chr(10).join(f"- {item}" for item in validation_feedback)}

INSTRUCTIONS:
1. Keep the good parts of the previous plan
2. Add/modify ONLY what's needed to address the issues above
3. Maintain consistency with existing structure

EFFICIENCY: This should be a quick targeted edit, not a full rewrite.
"""
        
        return base_prompt + task_rules + feedback_section
    
    def set_project_type(self, project_type: str) -> None:
        """Update project type and regenerate system prompt."""
        self.current_project_type = project_type
        self.system_prompt = self._get_system_prompt()
    
    async def invoke(self, state: AgentState) -> Dict[str, Any]:
        """
        Main entry point for the Planner.
        Maps AgentState to plan() arguments, ensuring environment is passed.
        """
        # Unpack state
        artifacts = state.get("artifacts", {})
        intent = artifacts.get("structured_intent")
        
        # Get optional components
        app_blueprint = artifacts.get("app_blueprint")
        constraints = artifacts.get("constraints")
        environment = state.get("environment") # Automatically injected by planner_node
        
        return await self.plan(
            intent=intent,
            app_blueprint=app_blueprint,
            constraints=constraints,
            environment=environment
        )

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
        
        # Save environment to self for _get_system_prompt
        self.environment = context["environment"]
        
        # ================================================================
        # FILE SYSTEM AWARENESS: Inject real file tree (from system)
        # ================================================================
        context["file_tree"] = context["environment"].get("file_tree", {})
        if context["file_tree"].get("success"):
            logger.info(f"[PLANNER] 🌳 Using system-injected file tree with {context['file_tree'].get('stats', {}).get('files', 0)} files")
        
        # Detect framework
        framework = self.tools.detect_framework(context)
        context["framework"] = framework
        
        # ================================================================
        # SCAFFOLDING DETECTION: Check if project needs setup
        # ================================================================        # Build environment context
        project_path = environment.get("project_path") if environment else None
        file_tree = environment.get("file_tree", {}) if environment else {}
        
        logger.info(f"[PLANNER.plan] 📋 Planning for request: {intent.get('description', 'N/A')[:100]}...")
        
        # Get the system prompt (with validation feedback if retrying)
        # Pass artifacts from state for incremental editing
        planner_artifacts = {}
        if intent and isinstance(intent, dict):
            planner_artifacts = {
                "validation_feedback": intent.get("validation_feedback"),
                "previous_plan": intent.get("previous_plan"),
                "scope": intent.get("scope"),  # Pass scope to _get_system_prompt
                "intent": intent,              # Pass full intent for context
            }
        
        self.system_prompt = self._get_system_prompt(artifacts=planner_artifacts)
        
        # Define user_request for scaffolding analysis
        user_request = intent.get("description", "")
        
        scaffolding_result = self.tools.analyze_project_for_scaffolding(
            project_path, 
            user_request
        )
        context["scaffolding"] = scaffolding_result
        
        # Step 1: Use LLM for high-level planning
        llm_plan = await self._generate_llm_plan(intent, context)
        context["llm_plan"] = llm_plan
        
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
                estimated_minutes=5,
            )
            
            # Store terminal commands in description for visibility
            cmds = scaffolding_task_dict.get("terminal_commands", [])
            if cmds:
                 scaffold_task.description += f"\n\nCommands to run: {', '.join(cmds)}"
            
            # Insert at beginning of task list
            task_list.tasks.insert(0, scaffold_task)
            
            # Reorder not needed - list order implies execution order

        
        # Enrich task list with LLM insights
        self.enricher.enrich_task_list(task_list, llm_plan)
        context["task_list"] = task_list
        
        # FolderArchitect: Folder structure
        folder_result = self.folder_architect.process(context)
        folder_map = folder_result["folder_map"]
        self.enricher.enrich_folder_map(folder_map, llm_plan)
        context["folder_map"] = folder_map
        
        # ContractAuthor: API contracts
        contract_result = self.contract_author.process(context)
        api_contracts = contract_result["api_contracts"]
        self.enricher.enrich_api_contracts(api_contracts, llm_plan)
        context["api_contracts"] = api_contracts
        
        # DependencyPlanner: Dependencies
        dep_result = self.dependency_planner.process(context)
        dependency_plan = dep_result["dependency_plan"]
        self.enricher.enrich_dependencies(dependency_plan, llm_plan)
        context["dependency_plan"] = dependency_plan
        
        # TestDesigner: Validation checklist
        test_result = self.test_designer.process(context)
        validation_checklist = test_result["validation_checklist"]
        
        # RiskAssessor: Risk report
        risk_result = self.risk_assessor.process(context)
        risk_report = risk_result["risk_report"]
        self.enricher.enrich_risks(risk_report, llm_plan)
        
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
        
        # SCALABILITY FIX: In Edit Mode, we implicitly assume scaffolding is complete.
        # This prevents the Router/Quality Gates from blocking "Edit" runs.
        is_edit_mode = context.get("scaffolding", {}).get("scaffolding_needed", True) is False
        
        return {
            "plan_manifest": plan_manifest,
            "task_list": task_list,
            "folder_map": folder_map,
            "api_contracts": api_contracts,
            "dependency_plan": dependency_plan,
            "validation_checklist": validation_checklist,
            "risk_report": risk_report,
            # Critical routing flags
            "scaffolding_complete": True if is_edit_mode else False,
            "scaffolding_skipped": True if is_edit_mode else False,
        }
    
    async def _generate_llm_plan(
        self, 
        intent: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Use LLM for high-level planning insights with structured output."""
        prompt = self._build_planning_prompt(intent, context)
        
        # DEV: Log prompt preview (never in production - may contain user data)
        dev_log(logger, f"[PLANNER] 📤 Prompt Preview: {truncate_for_log(prompt, 500)}")
        
        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=prompt)
        ]
        
        try:
            # Use Pydantic schema for guaranteed structured output
            structured_llm = self.llm.with_structured_output(LLMPlanOutput)
            
            logger.info(f"[PLANNER] 🎯 Invoking LLM with structured output (LLMPlanOutput schema)")
            
            result: LLMPlanOutput = await structured_llm.ainvoke(messages)
            
            # Convert Pydantic model to dict for downstream compatibility
            plan_dict = result.model_dump()
            
            # ================================================================
            # VISIBILITY LOGS: Show what Planner produced
            # ================================================================
            logger.info(
                f"[PLANNER] ✅ Structured output received: "
                f"{len(plan_dict.get('tasks', []))} tasks, "
                f"{len(plan_dict.get('folders', []))} folders"
            )
            dev_log(logger, f"[PLANNER] 📋 Summary: {truncate_for_log(plan_dict.get('summary', 'N/A'), 200)}")
            
            # Log task titles in dev mode for debugging
            for i, task in enumerate(plan_dict.get('tasks', [])[:5]):
                dev_log(logger, f"[PLANNER]   Task {i+1}: {task.get('title', 'Untitled')}")
            
            return plan_dict
            
        except Exception as e:
            logger.warning(f"[PLANNER] ⚠️ Structured output failed: {e}, falling back to raw parsing")
            
            # Fallback to raw parsing if structured output fails
            try:
                response = await self.llm.ainvoke(messages)
                
                # Handle Gemini's response format - content can be string or list of parts
                raw_content = response.content
                if isinstance(raw_content, list):
                    text_parts = []
                    for part in raw_content:
                        if isinstance(part, str):
                            text_parts.append(part)
                        elif hasattr(part, 'text'):
                            text_parts.append(part.text)
                        elif isinstance(part, dict) and 'text' in part:
                            text_parts.append(part['text'])
                    raw_content = ''.join(text_parts)
                elif not isinstance(raw_content, str):
                    raw_content = str(raw_content)
                
                logger.info(f"[PLANNER] 📥 Fallback: Raw LLM response length: {len(raw_content)} chars")
                
                parsed = self._parse_llm_response(raw_content)
                
                if not parsed.get("tasks") and not parsed.get("folders"):
                    logger.warning(f"[PLANNER] ⚠️ Parsed plan has no tasks or folders!")
                
                return parsed
            except Exception as fallback_error:
                logger.error(f"[PLANNER] ❌ LLM planning completely failed: {fallback_error}")
                raise
    
    def _build_planning_prompt(
        self, 
        intent: Dict[str, Any],
        context: Dict[str, Any]
    ) -> str:
        """Build the prompt for LLM planning."""
        parts = []
        
        # EXPLICITLY Surface the raw request to prevent summarization loss
        raw_req = intent.get("original_request") or intent.get("description")
        parts.append(f"USER RAW REQUEST: \"{raw_req}\"\n")
        
        # Intent
        parts.append(f"INTENT ANALYSIS:\n{json.dumps(intent, indent=2, default=str)}")
        
        # CRITICAL: Detect if this is a FIX/MODIFY request
        action = intent.get("action", "create")
        task_type = intent.get("task_type", "feature")
        is_fix_or_modify = action in ["fix", "modify", "update", "change"] or task_type == "fix"
        
        if is_fix_or_modify:
            parts.append("""
⚠️ IMPORTANT: This is a FIX/MODIFY request, NOT a new feature!

STRATEGY FOR FIXES:
1. Create a SINGLE diagnostic task that:
   - Reads the mentioned file(s) to understand current state
   - Identifies the specific issue
   - Makes targeted minimal changes
   - Does NOT rewrite entire files

2. Keep the plan MINIMAL:
   - 1-2 tasks maximum
   - Only modify files explicitly mentioned or directly related
   - Preserve all existing functionality

3. Expected outputs should list ONLY the file(s) that need changes
   - NOT all files in the project
   - NOT dependencies or components that already work

EXAMPLE FIX PLAN:
{
  "summary": "Fix missing connection in page.tsx",
  "tasks": [{
    "title": "Diagnose and fix page.tsx integration",
    "description": "Read page.tsx, identify missing import/component reference, add the connection",
    "complexity": "small",
    "expected_outputs": [{"path": "app/page.tsx", "description": "Add missing component import"}]
  }]
}""")
        
        # Framework
        parts.append(f"\nFRAMEWORK: {context.get('framework', 'react')}")
        
        # Constraints
        if context.get("constraints"):
            parts.append(f"CONSTRAINTS:\n{json.dumps(context['constraints'], indent=2, default=str)[:500]}")
            
        # Current File Tree
        file_tree = context.get("file_tree")
        if file_tree and file_tree.get("success"):
             tree_summary = []
             entries = file_tree.get("entries", [])
             
             # Prioritize displaying source files over config/assets if truncated
             # (Simple slice for now)
             display_entries = entries[:50]
             
             for entry in display_entries:
                 summary = entry['path'] + ("/" if entry.get("is_directory") else "")
                 if entry.get("definitions"):
                     # Show first 3 symbols
                     syms = entry['definitions'][:3]
                     more = "..." if len(entry['definitions']) > 3 else ""
                     summary += f"  [Defs: {', '.join(syms)}{more}]"
                 tree_summary.append(summary)
             
             tree_text = "\n".join(tree_summary)
             parts.append(f"CURRENT PROJECT STRUCTURE:\n{tree_text}")
             
             if len(entries) > 50:
                 parts.append(f"...and {len(entries) - 50} more files.")
        
        # Schema Definition
        parts.append("""
REQUIRED OUTPUT FORMAT (JSON ONLY):
{
  "summary": "Brief executive summary of the plan",
  "decision_notes": ["List of key technical decisions made"],
  "tasks": [
    {
      "title": "Task Title",
      "description": "Detailed description of what to do",
      "complexity": "small|medium|large",
      "priority": "high|medium|low",
      "estimated_minutes": 60,
      "acceptance_criteria": ["Criteria 1", "Criteria 2"],
      "expected_outputs": [{"path": "src/file.ts", "description": "What this file contains"}]
    }
  ],
  "folders": [
    {"path": "src/components", "is_directory": true, "description": "UI components"}
  ],
  "api_endpoints": [
    {"path": "/api/v1/resource", "method": "GET", "description": "Fetch resources"}
  ],
  "dependencies": [
    {"name": "react", "version": "18.x", "type": "production"}
  ],
  "risks": [
    {"description": "Potential risk", "severity": "medium", "mitigation": "How to handle it"}
  ]
}

Create a detailed plan following this EXACT JSON format. Output ONLY valid JSON, no markdown formatting or intro text.
""")
        
        return "\n\n".join(parts)
    
    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """Parse LLM response to JSON."""
        logger.info(f"[PLANNER] 📄 Parsing LLM response ({len(response)} chars)")
        
        def normalize_result(result):
            """Ensure result is a dict, wrap arrays as needed."""
            if isinstance(result, list):
                # LLM returned an array - wrap it as tasks
                logger.info(f"[PLANNER] 📦 Wrapping array response as tasks ({len(result)} items)")
                return {"tasks": result, "summary": "Plan generated from task array"}
            elif isinstance(result, dict):
                return result
            else:
                return {"summary": str(result), "tasks": []}
        
        # Try direct parse
        try:
            result = json.loads(response)
            result = normalize_result(result)
            logger.info(f"[PLANNER] ✅ Direct JSON parse succeeded: {len(result.get('tasks', []))} tasks")
            return result
        except json.JSONDecodeError as e:
            logger.warning(f"[PLANNER] Direct parse failed: {e}")
        
        # Try extracting JSON from markdown code block
        code_block_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', response)
        if code_block_match:
            try:
                result = json.loads(code_block_match.group(1).strip())
                result = normalize_result(result)
                logger.info(f"[PLANNER] ✅ Code block JSON parse succeeded: {len(result.get('tasks', []))} tasks")
                return result
            except json.JSONDecodeError as e:
                logger.warning(f"[PLANNER] Code block parse failed: {e}")
        
        # Try extracting JSON object
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            try:
                result = json.loads(json_match.group(0))
                result = normalize_result(result)
                logger.info(f"[PLANNER] ✅ Extracted JSON parse succeeded: {len(result.get('tasks', []))} tasks")
                return result
            except json.JSONDecodeError as e:
                logger.warning(f"[PLANNER] Extracted JSON parse failed: {e}")
                logger.debug(f"[PLANNER] Failed JSON: {json_match.group(0)[:500]}...")
        
        # Log the raw response for debugging
        logger.error(f"[PLANNER] ❌ All JSON parsing failed! Response preview: {response[:300]}...")
        return {"summary": "Plan generated", "tasks": []}
    

    
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
        
        TWO-PHASE EXECUTION:
        1. Generate plan artifacts (tasks, folders, deps, etc.)
        2. Execute scaffolding using create_react_agent with tools
        
        Args:
            state: Current agent state
            
        Returns:
            Dict with 'artifacts' key containing all plan artifacts
        """
        logger.info("[PLANNER] 🚀 Invoking Planner...")
        print("[PLANNER] Invoked.")
        
        events = []
        events.append(emit_event(
            "agent_start", 
            "planner", 
            "Designing implementation plan...",
            {"phase": "planning"}
        ))
        
        # 1. State extraction
        intent = state.get("intent", {})
        # If no intent, maybe user_request is raw text?
        if not intent or not intent.get("goal"):
            # Try to build intent from last user message if missing
            msgs = state.get("messages", [])
            last_msg = msgs[-1].content if msgs else ""
            intent = {"goal": last_msg, "context": {}}
        
        # 2. Plan Generation
        # (This uses the LLM to generate the manifest)
        
        # Emit thinking start with requirements context
        goal = intent.get("goal", intent.get("description", ""))
        context = intent.get("context", {})
        events.append(emit_event(
            "thinking", 
            "planner", 
            "Analyzing requirements...",
            {
                "goal": goal[:200] if goal else "",  # First 200 chars
                "has_context": bool(context)
            }
        ))
        
        plan_artifacts = await self.plan(intent)
        if not plan_artifacts:
            plan_artifacts = {}

        
        # 3. Artifact Persistence
        # (Already done in self.plan? No, self.plan returns them)
        if self.artifact_manager:
            for name, content in plan_artifacts.items():
                await self.artifact_manager.save_artifact(name, content)
        
        # 4. Scaffolding (Optional - if Planner creates folders directly)
        # Assuming self.plan handles logic.
        
        # Emit plan created event
        # Emit plan created event
        task_list_obj = plan_artifacts.get("task_list")
        if hasattr(task_list_obj, "tasks") and isinstance(task_list_obj.tasks, list):
            task_count = len(task_list_obj.tasks)
        elif isinstance(task_list_obj, list):
            task_count = len(task_list_obj)
        else:
             task_count = 0

        # Extract task titles and files for UI display
        task_titles = []
        files_to_create = []
        if hasattr(task_list_obj, "tasks") and isinstance(task_list_obj.tasks, list):
            for t in task_list_obj.tasks[:5]:  # First 5 tasks
                if hasattr(t, "title"):
                    task_titles.append(t.title)
                if hasattr(t, "expected_outputs"):
                    for out in t.expected_outputs:
                        if hasattr(out, "file_path"):
                            files_to_create.append(out.file_path)
        
        events.append(emit_event(
            "plan_created", 
            "planner", 
            "Implementation plan created.",
            {
                "task_count": task_count,
                "task_titles": task_titles[:5],  # First 5 task titles
                "files_to_create": files_to_create[:10],  # First 10 files
                "total_files": len(files_to_create)
            }
        ))
        
        # SCAFFOLDING LOGIC CONTINUES BELOW...
        # We need to bridge 'plan_artifacts' to the 'artifacts' var expected below
        artifacts = plan_artifacts
        from langgraph.prebuilt import create_react_agent
        from app.agents.tools.planner import PLANNER_TOOLS
        from app.prompts import AGENT_PROMPTS
        from app.core.llm_factory import LLMFactory
        from pathlib import Path
        import os
        
        artifacts = state.get("artifacts", {})
        parameters = state.get("parameters", {})
        project_path = artifacts.get("project_path")
        
        # Get structured intent or build from raw request
        intent = artifacts.get("structured_intent", {})
        if not intent:
            # Get raw request from messages
            messages = state.get("messages", [])
            raw_request = ""
            for m in messages:
                if hasattr(m, 'content'):
                    raw_request = m.content
                    break
            intent = {
                "description": raw_request,
                "id": str(uuid.uuid4()),
            }
        
        # ================================================================
        # USE INTENT CLASSIFICATION TO SELECT CORRECT TEMPLATE
        # Map task_type and target_area to project template keys
        # ================================================================
        task_type = intent.get("task_type", "feature")
        target_area = intent.get("target_area", "frontend")
        
        # Map target_area to template key
        template_mapping = {
            "frontend": "react-vite",  # Default frontend
            "backend": "fastapi",      # Default backend
            "full-stack": "nextjs",    # Full-stack default
            "database": "fastapi",     # DB work -> backend
            "testing": "react-vite",   # Testing inherits from project type
            "configuration": "generic",
            "documentation": "generic",
            "system": "generic",
            "unknown": "generic",
        }
        
        # ================================================================
        # INTELLIGENT TEMPLATE SELECTION
        # Priority: 
        # 1. User Explicit Request (e.g. "Use Next.js", "switch to Django")
        # 2. Existing Project Config (e.g. vite.config.js, pyproject.toml)
        # 3. Default Mapping (target_area -> template)
        # ================================================================
        
        detected_template = None
        user_request_lower = intent.get("description", "").lower() + " " + intent.get("original_request", "").lower()
        
        # 1. Check User Explicit Request (Keyword Search)
        # This allows users to override everything by just asking
        framework_keywords = {
            "nextjs": ["next.js", "nextjs", "next app"],
            "react-vite": ["vite", "react app", "standard react"],
            "vue": ["vue", "nuxt"], # Nuxt will match vue for now unless we separate
            "angular": ["angular"],
            "svelte": ["svelte", "sveltekit"],
            "astro": ["astro"],
            "fastapi": ["fastapi", "python backend"],
            "django": ["django"],
            "flask": ["flask"],
            "express": ["express", "node backend"],
            "nestjs": ["nest", "nestjs"],
        }
        
        for key, keywords in framework_keywords.items():
            if any(kw in user_request_lower for kw in keywords):
                detected_template = key
                logger.info(f"[PLANNER] 🧠 user_intent: Detected explicit request for '{key}'")
                break
        
        # 2. If no explicit request, check File System (Project Context)
        if not detected_template and project_path:
             project_dir = Path(project_path)
             fs_template = None
             
             # Frontend Configs
             if (project_dir / "vite.config.js").exists() or (project_dir / "vite.config.ts").exists():
                 fs_template = "react-vite"
                 if (project_dir / "src" / "App.vue").exists():
                     fs_template = "vue"
                 
             elif (project_dir / "next.config.js").exists() or (project_dir / "next.config.mjs").exists() or (project_dir / "next.config.ts").exists():
                 fs_template = "nextjs"
                 
             elif (project_dir / "angular.json").exists():
                 fs_template = "angular"
            
             # Backend Configs (Python)
             # Check these SEPARATELY. If target_area is backend, these take precedence over frontend configs in a split repo.
             backend_fs_template = None
             if (project_dir / "pyproject.toml").exists() or (project_dir / "requirements.txt").exists():
                 try:
                     content = ""
                     if (project_dir / "pyproject.toml").exists():
                         content = (project_dir / "pyproject.toml").read_text()
                     
                     if "fastapi" in content.lower():
                         backend_fs_template = "fastapi"
                     elif "django" in content.lower():
                         backend_fs_template = "django"
                     elif "flask" in content.lower():
                         backend_fs_template = "flask"
                     elif "fastapi" in user_request_lower: # fallback if file check insufficient but context implies
                         backend_fs_template = "fastapi"
                 except: pass

             # DECISION LOGIC: Combine file findings with target_area
             if target_area in ["backend", "database"]:
                 # Prefer backend template if found, otherwise stick to default mapping (don't force frontend)
                 if backend_fs_template:
                     detected_template = backend_fs_template
                     logger.info(f"[PLANNER] 📂 file_system: Backend task + Python config -> '{detected_template}'")
                 elif fs_template == "nextjs": 
                     # Next.js IS a backend too, so valid to keep if detected
                     detected_template = "nextjs"
                     logger.info(f"[PLANNER] 📂 file_system: Backend task + Next.js config -> '{detected_template}'")
                 # Else: Do NOT use fs_template (React/Vue/Angular) for backend task. Keep default (e.g. fastapi).
                 
             elif target_area in ["frontend", "full-stack", "unknown"]:
                 # Prefer Frontend/Fullstack template
                 if fs_template:
                     detected_template = fs_template
                     logger.info(f"[PLANNER] 📂 file_system: Frontend/Full-stack task + Frontend config -> '{detected_template}'")
                 elif backend_fs_template and target_area == "full-stack":
                     # If only backend found but asking for full stack, maybe generic or backend?
                     # Let's fallback to default mapping (Next.js)?? NO, that caused the issue.
                     # If we have Python but no frontend config, and user asks for fullstack, maybe it's Python + generic JS?
                     pass # Fallback to default mapping logic is safer here, OR detected_template = backend_fs_template?

        # 3. Fallback to Default Mapping
        if not detected_template:
            detected_template = template_mapping.get(target_area, "react-vite")
            logger.info(f"[PLANNER] 🤷 default: Falling back to target_area mapping -> '{detected_template}'")
        
        # FINAL: Update current_project_type
        self.current_project_type = detected_template
        logger.info(f"[PLANNER] 🎯 Final Template Selection: '{detected_template}'")
        
        app_blueprint = artifacts.get("app_blueprint")
        constraints = artifacts.get("constraints")
        environment = {"project_path": project_path}
        
        # ================================================================
        # PHASE 1: Generate Plan Artifacts
        # ================================================================
        plan_result = await self.plan(
            intent=intent,
            app_blueprint=app_blueprint,
            constraints=constraints,
            environment=environment
        )
        
        # Convert to serializable dict (mode='json' handles datetime -> ISO string)
        plan_artifacts = {
            "plan_manifest": plan_result["plan_manifest"].model_dump(mode='json'),
            "task_list": plan_result["task_list"].model_dump(mode='json'),
            "folder_map": plan_result["folder_map"].model_dump(mode='json'),
            "api_contracts": plan_result["api_contracts"].model_dump(mode='json'),
            "dependency_plan": plan_result["dependency_plan"].model_dump(mode='json'),
            "validation_checklist": plan_result["validation_checklist"].model_dump(mode='json'),
            "risk_report": plan_result["risk_report"].model_dump(mode='json'),
        }
        
        # ================================================================
        # PHASE 2: Execute Scaffolding using create_react_agent
        # (Moved BEFORE artifact writing so directory is empty for scaffolders)
        # ================================================================
        if project_path:
            try:
                # ============================================================
                # SCOPE-AWARE SCAFFOLDING DECISION
                # ============================================================
                scope = intent.get("scope", "feature")
                target_area = intent.get("target_area", "frontend")
                project_dir = Path(project_path)
                
                # Determine if scaffolding is needed based on scope
                needs_scaffolding = False
                
                if scope == "project":
                    needs_scaffolding = True
                    logger.info(f"[PLANNER] 🏗️ Scope 'project' → Scaffolding required")
                    
                elif scope == "layer":
                    # Check if the target layer exists
                    layer_indicators = {
                        "backend": [project_dir / "server", project_dir / "backend", project_dir / "api"],
                        "database": [project_dir / "prisma", project_dir / "db", project_dir / "migrations"],
                        "frontend": [project_dir / "src", project_dir / "app", project_dir / "pages"],
                    }
                    
                    indicators = layer_indicators.get(target_area, [])
                    layer_exists = any(ind.exists() for ind in indicators)
                    
                    if not layer_exists:
                        needs_scaffolding = True
                        logger.info(f"[PLANNER] 🏗️ Scope 'layer' + missing {target_area} → Scaffolding required")
                    else:
                        logger.info(f"[PLANNER] ✅ Scope 'layer' but {target_area} exists → No scaffolding")
                        
                elif scope == "component":
                    # Check if basic project structure exists in the PROJECT PATH (user's folder)
                    # NOT in the current working directory
                    actual_project_dir = Path(self.project_root) if self.project_root else project_dir
                    
                    project_indicators = [
                        actual_project_dir / "package.json",
                        actual_project_dir / "src",
                        actual_project_dir / "app",
                        actual_project_dir / "index.html",  # Vite apps
                        actual_project_dir / "tsconfig.json"  # TypeScript projects
                    ]
                    has_project = any(ind.exists() for ind in project_indicators)
                    
                    if not has_project:
                        needs_scaffolding = True
                        logger.info(f"[PLANNER] 🏗️ Scope 'component' but no project found at {actual_project_dir} → Scaffolding required")
                    else:
                        logger.info(f"[PLANNER] ✅ Scope 'component' and project exists at {actual_project_dir} → No scaffolding")
                        needs_scaffolding = False  # CRITICAL FIX: Don't scaffold if project exists!
                        
                else: # feature
                    needs_scaffolding = False
                    logger.info(f"[PLANNER] ✅ Scope 'feature' → No scaffolding")

                # Execute scaffolding if needed
                if needs_scaffolding:
                    
                    # Get user request for context in scaffolding
                    user_request_summary = intent.get("description", "")
                    
                    # ============================================================
                    # USE DETECTED TEMPLATE FOR SCAFFOLD COMMAND
                    # ============================================================
                    from app.agents.sub_agents.planner.project_analyzer import _get_scaffold_command
                    
                    scaffold_command = _get_scaffold_command(self.current_project_type)
                    
                    # ============================================================
                    # SMART NAMING & SUBFOLDER LOGIC (Must come BEFORE prefix calc)
                    # ============================================================
                    import re
                    
                    # Generate a suggested slug for the LLM, but it may pick its own name
                    # We'll detect the actual folder post-scaffolding
                    raw_desc = intent.get("description", "my-app")
                    suggested_slug = re.sub(r'[^a-z0-9]+', '-', raw_desc.lower()).strip('-')
                    if not suggested_slug: suggested_slug = "my-app"
                    suggested_slug = suggested_slug[:30]
                    
                    current_dir_name = project_dir.name.lower()
                    
                    # Decide if we scaffold here (.) or in a subfolder
                    if current_dir_name == suggested_slug:
                        target_arg = "."
                        logger.info(f"[PLANNER] 🎯 Current dir matches slug '{suggested_slug}'. Scaffolding here.")
                    else:
                        # Tell the LLM to scaffold into a subfolder, but don't update project_path yet
                        # We'll detect the actual created folder post-scaffolding
                        target_arg = suggested_slug
                        logger.info(f"[PLANNER] 📦 Will scaffold into subfolder (suggested: '{suggested_slug}')")
                    
                    # 3. Update scaffold command with target
                    # Use regex to replace " ." with " target" (handling both middle and end of string)
                    scaffold_command = re.sub(r'\s\.(?:\s|$)', f" {target_arg} ", scaffold_command).strip()

                    
                    logger.info(f"[PLANNER] 🔧 Final Scaffold Command: {scaffold_command}")
                    
                    scaffold_prompt = f"""PROJECT PATH: {project_dir}
TARGET: {target_arg}
USER REQUEST: "{user_request_summary[:200]}"
TEMPLATE: {self.current_project_type}

SCAFFOLDING TASK - NEW PROJECT SETUP:

You are setting up a NEW project. The workflow is:
1. Run official CLI scaffolder (creates base structure)
2. Verify it worked
3. The Coder will add custom files later

EXECUTE THESE STEPS:

Step 1 - Check current state:
   list_directory(".")

Step 2 - Run scaffolding CLI (PRIORITY):
   run_terminal_command("{scaffold_command}")
   
   This creates:
   - package.json, tsconfig.json, vite.config.ts (or similar configs)
   - Base folder structure (src/, public/, etc)
   - Entry points (index.html, main.tsx)
   
Step 3 - Install dependencies:
   run_terminal_command("npm install")

Step 4 - Verify structure created:
   list_directory(".")

IMPORTANT:
- The CLI scaffolder creates the FOUNDATION
- The Coder will create custom components/pages/features AFTER this
- Do NOT manually create package.json or tsconfig.json (scaffolder does this)
- Do NOT create application code (Coder does this)
- Your job: Run the scaffolder and verify success"""

                    # Create dedicated scaffolder system prompt
                    scaffolder_system_prompt = """You are a Project Scaffolder for ShipS*.

YOUR ONLY JOB: Run official scaffolding commands to create project structures.

CRITICAL RULES:
1. ALWAYS use run_terminal_command for scaffolding (npm create, npx create-*, etc)
2. NEVER manually create folders or files
3. NEVER use create_directory, create_directories, or write_file
4. The scaffolder CLI tools (vite, create-react-app, etc) create EVERYTHING

WHY: Scaffolding CLIs are designed by framework authors to create perfect, complete project structures.
Manual creation leads to missing files, incorrect configs, and broken projects.

YOUR WORKFLOW:
1. Check if project exists (list_directory)
2. Run the scaffolding command (run_terminal_command)
3. Install dependencies (run_terminal_command: npm install)
4. Verify success (list_directory)

That's it. Simple. Let the scaffolder do its job."""

                    # Create ReAct agent with planner tools
                    llm = LLMFactory.get_model("planner")
                    planner_agent = create_react_agent(
                        model=llm,
                        tools=PLANNER_TOOLS,
                        prompt=scaffolder_system_prompt,  # Use dedicated prompt
                    )
                    
                    # Execute scaffolding
                    scaffold_result = await planner_agent.ainvoke(
                        {"messages": [HumanMessage(content=scaffold_prompt)]},
                        config={"recursion_limit": 30}
                    )
                    
                    # ============================================================
                    # POST-SCAFFOLDING: Detect what folder was ACTUALLY created
                    # The LLM might pick a creative name different from our slug
                    # ============================================================
                    actual_project_path = None
                    try:
                        # PRIORITIZE: Check if the intended target folder was validated
                        target_path = project_dir / target_arg
                        if target_arg != "." and target_path.exists() and target_path.is_dir():
                             actual_project_path = str(target_path)
                             logger.info(f"[PLANNER] 🎯 Confirmed scaffolded project at target: {actual_project_path}")
                        else:
                            # Fallback: Scan for new directories if we scaffolded to . or something else
                            # Scan for new directories with package.json (indicator of scaffolded project)
                            for item in project_dir.iterdir():
                                if item.is_dir() and not item.name.startswith('.'):
                                    pkg_json = item / "package.json"
                                    if pkg_json.exists():
                                        actual_project_path = str(item)
                                        logger.info(f"[PLANNER] 🔍 Detected scaffolded project at: {actual_project_path}")
                                        break
                        
                        # Update project_path to the ACTUAL created folder
                        if actual_project_path and actual_project_path != project_path:
                            logger.info(f"[PLANNER] 📦 Updating project_path: {project_path} → {actual_project_path}")
                            project_path = actual_project_path
                            plan_artifacts["project_path"] = actual_project_path
                            plan_artifacts["project_name"] = Path(actual_project_path).name
                    except Exception as detect_err:
                        logger.warning(f"[PLANNER] ⚠️ Could not detect scaffolded folder: {detect_err}")
                    
                    plan_artifacts["scaffolding_complete"] = True
                    plan_artifacts["scaffolding_messages"] = len(scaffold_result.get("messages", []))
                else:
                    plan_artifacts["scaffolding_complete"] = True
                    plan_artifacts["scaffolding_skipped"] = True
                    plan_artifacts["scaffolding_reason"] = f"Scope '{scope}' does not require scaffolding"
                    
            except Exception as scaffold_error:
                # Don't fail planning if scaffolding fails
                plan_artifacts["scaffolding_complete"] = False
                plan_artifacts["scaffolding_error"] = str(scaffold_error)
                logger.error(f"[PLANNER] ❌ Scaffolding failed: {scaffold_error}")

        # ================================================================
        # WRITE ALL ARTIFACTS TO DISK
        # ================================================================
        if project_path:
            import json as json_mod
            dot_ships = Path(project_path) / ".ships"
            dot_ships.mkdir(parents=True, exist_ok=True)
            
            # Artifact name mapping - folder_map should be saved as folder_map_plan.json
            artifact_file_names = {
                "task_list": "task_list.json",
                "folder_map": "folder_map_plan.json",  # Renamed to match coder expectations
                "api_contracts": "api_contracts.json",
                "dependency_plan": "dependency_plan.json",
                "validation_checklist": "validation_checklist.json",
                "risk_report": "risk_report.json"
            }
            
            for artifact_name, file_name in artifact_file_names.items():
                try:
                    with open(dot_ships / file_name, "w", encoding="utf-8") as f:
                        # Use default=str to handle any lingering datetime objects
                        f.write(json_mod.dumps(plan_artifacts[artifact_name], indent=2, default=str))
                except Exception as write_err:
                    logger.warning(f"[PLANNER] Failed to write {file_name}: {write_err}")
            
            # ================================================================
            # Write implementation_plan.md using lean formatter
            # References JSON artifacts instead of duplicating content
            # ================================================================
            try:
                from app.agents.sub_agents.planner.formatter import format_implementation_plan
                
                plan_md_content = format_implementation_plan(
                    artifacts=plan_artifacts,
                    project_name=intent.get("description", "Project")[:50]
                )
                
                plan_md_path = dot_ships / "implementation_plan.md"
                with open(plan_md_path, "w", encoding="utf-8") as f:
                    f.write(plan_md_content)
                
                logger.info(f"[PLANNER] 📝 Wrote implementation_plan.md ({len(plan_md_content)} chars)")
            except Exception as plan_write_err:
                logger.error(f"[PLANNER] ❌ Failed to write implementation_plan.md: {plan_write_err}")
            
            logger.info(f"[PLANNER] 💾 Wrote 7 artifacts to {dot_ships}")

            # ================================================================
            # PERSISTENCE (DB & GIT)
            # ================================================================
            # 1. Update Project Path in DB (if run_id exists)
            run_id = state.get("artifacts", {}).get("run_id") or state.get("run_id")
            if run_id and project_path:
                try:
                    run_uuid = uuid.UUID(run_id) if isinstance(run_id, str) else run_id
                    session_factory = get_session_factory()
                    async with session_factory() as session:
                        await session.execute(
                            update(AgentRun)
                            .where(AgentRun.id == run_uuid)
                            .values(project_path=project_path)
                        )
                        await session.commit()
                        logger.info(f"[PLANNER] 💾 Persisted project_path='{project_path}' to DB for run {run_uuid}")
                except Exception as db_err:
                    logger.error(f"[PLANNER] Failed to persist project path to DB: {db_err}")

            # 2. Git Checkpoint
            if project_path:
                try:
                    milestone = "scaffolding_complete" if plan_artifacts.get("scaffolding_complete") else "plan_ready"
                    checkpointer = get_checkpointer(project_path)
                    commit_hash = checkpointer.checkpoint(milestone)
                    if commit_hash:
                        logger.info(f"[PLANNER] 📸 Git checkpoint: {commit_hash[:8]}")
                except Exception as cp_err:
                    logger.debug(f"[PLANNER] Git checkpoint skipped: {cp_err}")
        

        return {
            "artifacts": plan_artifacts, 
            "stream_events": events
        }
