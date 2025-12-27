"""
ShipS* Coder Agent

The Coder converts Planner tasks into minimal, reviewable code changes (file diffs),
tests, and commit metadata that downstream systems can run, validate, and ship.

Uses Gemini 3 Pro with low temperature (0.0-0.2) for deterministic code generation.

Responsibilities:
- Accept a single task and produce discrete implementation
- Produce machine-readable file diffs (not prose)
- Produce unit/integration tests per Validation Checklist
- Respect Folder Map, API Contracts, Dependency Plan
- Output Implementation Report and Commit Intent
- Avoid TODOs and placeholders
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

from app.agents.sub_agents.coder.models import (
    FileChangeSet, FileChange, FileDiff, FileOperation, ChangeRisk,
    TestBundle, TestCase, TestType,
    CommitIntent, SemanticVersionBump,
    ImplementationReport, InferredItem, EdgeCase,
    PreflightCheck, CheckResult, CheckStatus,
    FollowUpTasks, FollowUpTask,
    CoderOutput, CoderMetadata,
)
from app.agents.sub_agents.coder.components import (
    CoderComponentConfig, TaskInterpreter, ContextConsumer,
    StyleEnforcer, ImplementationSynthesizer, DependencyVerifier,
    TestAuthor, PreflightChecker,
)
from app.agents.sub_agents.coder.tools import CodeTools, DiffGenerator


class Coder(BaseAgent):
    """
    Coder Agent - Produces Minimal, Reviewable Code Changes.
    
    Uses Gemini 3 Pro for heavy reasoning and code quality.
    Produces 6 discrete artifacts consumed by Validator and Fixer.
    
    Features:
    - Modular subcomponents for each responsibility
    - Streaming support for real-time feedback
    - Deterministic outputs with low temperature
    - Minimal-change bias for reviewable diffs
    - No TODO policy - creates follow-up tasks instead
    """
    
    def __init__(
        self,
        artifact_manager: Optional[ArtifactManager] = None,
        config: Optional[CoderComponentConfig] = None
    ):
        """
        Initialize the Coder.
        
        Args:
            artifact_manager: Optional artifact manager
            config: Coder configuration
        """
        super().__init__(
            name="Coder",
            agent_type="coder",  # Uses Pro model
            reasoning_level="standard",
            artifact_manager=artifact_manager
        )
        
        self.config = config or CoderComponentConfig()
        
        # Initialize subcomponents
        self.task_interpreter = TaskInterpreter(self.config)
        self.context_consumer = ContextConsumer(self.config)
        self.style_enforcer = StyleEnforcer(self.config)
        self.impl_synthesizer = ImplementationSynthesizer(self.config)
        self.dep_verifier = DependencyVerifier(self.config)
        self.test_author = TestAuthor(self.config)
        self.preflight_checker = PreflightChecker(self.config)
        
        # Tools
        self.tools = CodeTools
    
    def _get_system_prompt(self) -> str:
        """Get the system prompt for code generation."""
        return """You are the Coder for ShipS*, an AI coding system that SHIPS WORKING CODE.

Your job is to produce MINIMAL, REVIEWABLE code changes that exactly satisfy task acceptance criteria.

CRITICAL RULES:
1. MINIMAL CHANGES: Produce the smallest diff that satisfies the acceptance criteria
2. NO TODOS: Never use TODO, FIXME, or placeholders. If incomplete, create follow-up task
3. ATOMIC COMMITS: Each output should be a single committable unit
4. TESTABLE: Every change must be testable - produce tests for each acceptance criterion
5. DETERMINISTIC: Use consistent patterns, avoid creative flourishes

CODE QUALITY REQUIREMENTS:
- Follow detected repository patterns (naming, style, structure)
- Include proper error handling
- Add type annotations where applicable
- Write clear, concise comments only where non-obvious

OUTPUT FORMAT:
Produce a JSON object with this structure:
{
    "files": [
        {
            "path": "relative/path/to/file.ts",
            "operation": "add|modify|delete",
            "content": "full file content here",
            "reason": "Why this change (tied to acceptance criteria)",
            "acceptance_criteria": ["criteria_id_1"]
        }
    ],
    "tests": [
        {
            "path": "relative/path/to/file.test.ts",
            "content": "test file content",
            "description": "What this tests"
        }
    ],
    "summary": "One-paragraph summary of changes",
    "confidence": 0.95,
    "new_dependencies": ["package-name"],
    "edge_cases": [{"description": "Edge case", "handling": "How handled"}],
    "follow_up_tasks": []
}

REMEMBER: You are judged by how SMALL and CORRECT your diffs are, not how much code you write."""
    
    async def code(
        self,
        task: Dict[str, Any],
        folder_map: Optional[Dict[str, Any]] = None,
        api_contracts: Optional[Dict[str, Any]] = None,
        dependency_plan: Optional[Dict[str, Any]] = None,
        existing_code: Optional[Dict[str, str]] = None,
        policy: Optional[Dict[str, Any]] = None
    ) -> CoderOutput:
        """
        Generate code for a task.
        
        This is the main entry point for code generation.
        
        Args:
            task: Task artifact from Planner
            folder_map: Folder structure
            api_contracts: API definitions
            dependency_plan: Allowed dependencies
            existing_code: Map of path -> content for context
            policy: Style and security policies
            
        Returns:
            CoderOutput with all artifacts
        """
        task_id = task.get("id", str(uuid.uuid4())[:8])
        plan_id = task.get("plan_id")
        
        # Step 1: Interpret task
        context = {"task": task}
        interpretation = self.task_interpreter.process(context)
        
        if not interpretation["is_valid"]:
            return CoderOutput(
                success=False,
                is_blocking=True,
                blocking_reasons=interpretation["blocking_reasons"]
            )
        
        # Step 2: Gather context
        context.update({
            "folder_map": folder_map or {},
            "existing_code": existing_code or {},
            "objectives": interpretation["objectives"],
        })
        context_result = self.context_consumer.process(context)
        context.update(context_result)
        
        # Step 3: Determine style
        framework = self._detect_framework(folder_map)
        context["framework"] = framework
        style_result = self.style_enforcer.process(context)
        context.update(style_result)
        
        # Step 4: Use LLM for actual code generation
        llm_result = await self._generate_code_with_llm(task, context)
        
        if not llm_result.get("files"):
            return CoderOutput(
                success=False,
                is_blocking=True,
                blocking_reasons=["LLM failed to generate code"]
            )
        
        # Step 5: Create FileChangeSet
        changes = []
        for file_info in llm_result.get("files", []):
            path = file_info.get("path", "")
            operation = FileOperation(file_info.get("operation", "add"))
            new_content = file_info.get("content", "")
            original = existing_code.get(path, "") if existing_code else ""
            
            change = DiffGenerator.create_file_change(
                path=path,
                operation=operation,
                original_content=original if operation == FileOperation.MODIFY else None,
                new_content=new_content,
                reason=file_info.get("reason", ""),
                acceptance_criteria_ids=file_info.get("acceptance_criteria", [])
            )
            changes.append(change)
        
        # Step 6: Verify dependencies
        new_deps = llm_result.get("new_dependencies", [])
        if new_deps:
            dep_context = {
                "new_imports": [{"name": d} for d in new_deps],
                "dependency_plan": dependency_plan or {},
                "ecosystem": "npm" if framework in ["react", "nextjs"] else "pip"
            }
            dep_result = self.dep_verifier.process(dep_context)
            
            if dep_result["has_blockers"]:
                return CoderOutput(
                    success=False,
                    is_blocking=True,
                    blocking_reasons=[f"Blocked dependency: {b['name']}" for b in dep_result["blocked"]]
                )
        
        # Step 7: Generate tests
        test_context = {
            "objectives": interpretation["objectives"],
            "suggested_changes": [{"path": c.path} for c in changes],
            "test_patterns": style_result.get("test_patterns", {})
        }
        test_result = self.test_author.process(test_context)
        
        # Create TestBundle
        test_bundle = TestBundle(
            metadata=CoderMetadata(task_id=task_id, plan_id=plan_id),
            tests=test_result["test_cases"]
        )
        
        # Step 8: Run preflight checks
        preflight_context = {
            "changes": [{"path": c.path, "content": c.diff.new_content or ""} for c in changes],
            "policy": policy or {}
        }
        preflight_result = self.preflight_checker.process(preflight_context)
        preflight_check = preflight_result["preflight_check"]
        
        # Step 9: Assemble output
        confidence = llm_result.get("confidence", 0.8)
        summary = llm_result.get("summary", task.get("title", "Implementation"))
        
        output = self.tools.assemble_coder_output(
            task_id=task_id,
            changes=changes,
            tests=test_result["test_cases"],
            summary=summary,
            confidence=confidence,
            plan_id=plan_id
        )
        
        # Add test bundle and preflight
        output.test_bundle = test_bundle
        output.preflight_check = preflight_check
        
        # Handle follow-up tasks
        follow_ups = llm_result.get("follow_up_tasks", [])
        if follow_ups:
            output.follow_up_tasks = FollowUpTasks(
                tasks=[FollowUpTask(
                    title=f["title"],
                    description=f.get("description", ""),
                    reason=f.get("reason", "Incomplete implementation"),
                    acceptance_criteria=f.get("acceptance_criteria", [])
                ) for f in follow_ups],
                parent_task_id=task_id
            )
        
        # Update report with edge cases
        if output.implementation_report:
            output.implementation_report.edge_cases = [
                EdgeCase(**ec) for ec in llm_result.get("edge_cases", [])
            ]
            output.implementation_report.new_dependencies = new_deps
        
        # Log action
        if self._artifact_manager:
            self.log_action(
                action="code_generated",
                input_summary=task.get("title", "")[:100],
                output_summary=f"{len(changes)} files, {output.total_lines_changed} lines",
                reasoning=summary
            )
        
        return output
    
    async def _generate_code_with_llm(
        self,
        task: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Use LLM for actual code generation."""
        prompt = self._build_coding_prompt(task, context)
        
        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=prompt)
        ]
        
        try:
            response = await self.llm.ainvoke(messages)
            return self._parse_code_response(response.content)
        except Exception as e:
            return {"error": str(e), "files": []}
    
    def _build_coding_prompt(
        self,
        task: Dict[str, Any],
        context: Dict[str, Any]
    ) -> str:
        """Build the prompt for code generation."""
        parts = []
        
        # Task info
        parts.append(f"TASK:\nTitle: {task.get('title', 'Unknown')}")
        parts.append(f"Description: {task.get('description', '')}")
        
        # Acceptance criteria
        criteria = task.get("acceptance_criteria", [])
        if criteria:
            parts.append("ACCEPTANCE CRITERIA:")
            for i, c in enumerate(criteria):
                desc = c.get("description", c) if isinstance(c, dict) else str(c)
                parts.append(f"  {i+1}. {desc}")
        
        # Expected outputs
        outputs = task.get("expected_outputs", [])
        if outputs:
            parts.append("EXPECTED FILES:")
            for o in outputs:
                path = o.get("file_path", o.get("path", "")) if isinstance(o, dict) else str(o)
                parts.append(f"  - {path}")
        
        # Style rules
        style = context.get("naming_rules", {})
        if style:
            parts.append(f"STYLE: {json.dumps(style)}")
        
        # Existing code context
        snippets = context.get("relevant_snippets", {})
        if snippets:
            parts.append("EXISTING CODE CONTEXT:")
            for path, content in list(snippets.items())[:3]:  # Limit to 3 files
                parts.append(f"--- {path} ---")
                parts.append(content[:1000])  # Limit size
        
        parts.append("\nGenerate the implementation. Output ONLY valid JSON:")
        
        return "\n\n".join(parts)
    
    def _parse_code_response(self, response: str) -> Dict[str, Any]:
        """Parse LLM response to JSON."""
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass
        
        # Try extracting JSON from code block
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', response)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass
        
        # Try extracting JSON object
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass
        
        return {"files": [], "error": "Failed to parse response"}
    
    def _detect_framework(self, folder_map: Optional[Dict[str, Any]]) -> str:
        """Detect framework from folder map or structure."""
        if not folder_map:
            return "react"
        
        entries = folder_map.get("entries", [])
        paths = [e.get("path", "") for e in entries]
        
        if any("app/" in p for p in paths):
            return "nextjs"
        if any("src/components" in p for p in paths):
            return "react"
        if any("app/api" in p or "main.py" in p for p in paths):
            return "fastapi"
        
        return "react"
    
    async def code_streaming(
        self,
        task: Dict[str, Any],
        folder_map: Optional[Dict[str, Any]] = None
    ) -> AsyncIterator[str]:
        """
        Generate code with streaming output for real-time feedback.
        
        Yields chunks of the code as they're generated.
        """
        context = {"task": task, "folder_map": folder_map or {}}
        prompt = self._build_coding_prompt(task, context)
        
        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=prompt)
        ]
        
        full_response = ""
        async for chunk in self.llm.astream(messages):
            if hasattr(chunk, 'content'):
                full_response += chunk.content
                yield chunk.content
        
        # Parse and signal completion
        yield f"\n\n__CODE_COMPLETE__"
    
    async def invoke(self, state: AgentState) -> Dict[str, Any]:
        """
        Invoke the Coder as part of orchestrator workflow.
        
        Args:
            state: Current agent state
            
        Returns:
            Dict with 'artifacts' key containing all coder artifacts
        """
        artifacts = state.get("artifacts", {})
        parameters = state.get("parameters", {})
        
        # Get task from parameters or artifacts
        task = parameters.get("task") or artifacts.get("current_task", {})
        folder_map = artifacts.get("folder_map")
        api_contracts = artifacts.get("api_contracts")
        dependency_plan = artifacts.get("dependency_plan")
        
        # Generate code
        result = await self.code(
            task=task,
            folder_map=folder_map,
            api_contracts=api_contracts,
            dependency_plan=dependency_plan
        )
        
        # Convert to serializable dict
        return {
            "artifacts": {
                "file_change_set": result.file_change_set.model_dump() if result.file_change_set else None,
                "test_bundle": result.test_bundle.model_dump() if result.test_bundle else None,
                "commit_intent": result.commit_intent.model_dump() if result.commit_intent else None,
                "implementation_report": result.implementation_report.model_dump() if result.implementation_report else None,
                "preflight_check": result.preflight_check.model_dump() if result.preflight_check else None,
                "follow_up_tasks": result.follow_up_tasks.model_dump() if result.follow_up_tasks else None,
            },
            "success": result.success,
            "is_blocking": result.is_blocking,
            "blocking_reasons": result.blocking_reasons,
            "recommended_next_agent": result.recommended_next_agent
        }
