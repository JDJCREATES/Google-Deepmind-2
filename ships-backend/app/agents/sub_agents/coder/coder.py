"""
ShipS* Coder Agent

The Coder converts Planner tasks into minimal, reviewable code changes (file diffs),
tests, and commit metadata that downstream systems can run, validate, and ship.

Integrates with Collective Intelligence system to leverage proven patterns and
avoid known pitfalls from past successful code generations.

Uses Gemini 3 flash preview for deterministic code generation.

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

# Use centralized logging
from app.core.logger import get_logger, dev_log, truncate_for_log
logger = get_logger("coder")

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.base.base_agent import BaseAgent
from app.graphs.state import AgentState
from app.artifacts import ArtifactManager

from app.prompts.coder import CODER_SYSTEM_PROMPT

from app.agents.sub_agents.coder.models import (
    FileChangeSet, FileChange, FileDiff, FileOperation, ChangeRisk,
    TestBundle, TestCase, TestType,
    CommitIntent, SemanticVersionBump,
    ImplementationReport, InferredItem, EdgeCase,
    PreflightCheck, CheckResult, CheckStatus,
    FollowUpTasks, FollowUpTask,
    CoderOutput, CoderMetadata,
    CoderComponentConfig,
)

# Tools are in central location: app/agents/tools/coder/
from app.agents.tools.coder import (
    generate_file_diff,
    detect_language,
    assess_change_risk,
    create_file_change,
)

# Subcomponents for code generation
from app.agents.sub_agents.coder.components import (
    TaskInterpreter, ContextConsumer, StyleEnforcer,
    ImplementationSynthesizer, DependencyVerifier,
    TestAuthor, PreflightChecker, CodeTools,
)

from app.streaming.stream_events import emit_event

# Collective Intelligence integration
from app.services.knowledge import CoderKnowledge


class Coder(BaseAgent):
    """
    Coder Agent - Produces Minimal, Reviewable Code Changes.
    
    Features:
    - Modular subcomponents for each responsibility
    - Streaming support for real-time feedback
    - Context injection from state (avoids disk I/O)
    - Thought signature propagation for Gemini 3
    - Minimal-change bias for reviewable diffs
    - No TODO policy - creates follow-up tasks instead
    """
    
    def __init__(
        self,
        artifact_manager: Optional[ArtifactManager] = None,
        config: Optional[CoderComponentConfig] = None,
        cached_content: Optional[str] = None,
        knowledge: Optional[CoderKnowledge] = None,
    ):
        """
        Initialize the Coder.
        
        Args:
            artifact_manager: Optional artifact manager
            config: Coder configuration
            cached_content: Optional cached content
            knowledge: Optional CoderKnowledge for Collective Intelligence
        """
        # Initialize instance vars BEFORE super().__init__ since it calls _get_system_prompt()
        self.config = config or CoderComponentConfig()
        self._injected_folder_map: Optional[Dict[str, Any]] = None
        self._injected_api_contracts: Optional[Dict[str, Any]] = None
        self._project_type: str = "generic"
        self._last_thought_signature: Optional[str] = None
        self._knowledge = knowledge  # Collective Intelligence
        self._knowledge_prompt: str = ""  # Cached suggestions for current task
        
        super().__init__(
            name="Coder",
            agent_type="coder",  # Uses Pro model
            reasoning_level="high",  # Coder needs high reasoning
            artifact_manager=artifact_manager,
            cached_content=cached_content
        )
        
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
    
    def inject_context_from_state(
        self,
        folder_map: Optional[Dict[str, Any]] = None,
        api_contracts: Optional[Dict[str, Any]] = None,
        project_type: str = "generic",
        thought_signature: Optional[str] = None,
        command_preference: str = "auto"
    ) -> None:
        """
        Inject context from LangGraph state before invoke.
        
        This avoids disk I/O and extra tool calls:
        - folder_map is pre-loaded in prompt (no list_directory needed)
        - api_contracts are available (no read_file needed)
        - thought_signature maintains Gemini 3 reasoning context
        """
        self._injected_folder_map = folder_map
        self._injected_api_contracts = api_contracts
        self._project_type = project_type
        self._last_thought_signature = thought_signature
        
        # Regenerate prompt with injected context
        self.system_prompt = self._get_system_prompt(command_preference=command_preference)
    
    def _get_system_prompt(self, command_preference: str = "auto") -> str:
        """Get enhanced system prompt with injected context."""
        base_prompt = CODER_SYSTEM_PROMPT
        
        # Inject OS Command Instructions
        import platform
        import os
        
        is_windows = False
        if command_preference == "windows":
            is_windows = True
        elif command_preference == "unix" or command_preference == "macos":
            is_windows = False
        else:
            is_windows = platform.system() == "Windows" or os.name == 'nt'
            
        if is_windows:
            base_prompt += """

CRITICAL OS INSTRUCTIONS (WINDOWS):
- Environment: Windows (Powershell/CMD)
- Use 'findstr' instead of 'grep'
- Use 'dir' instead of 'ls'
- Use 'type' instead of 'cat'
- Use 'del' instead of 'rm'
- Do NOT chain commands with '&&' unless sure it's CMD. Run sequentially.
"""
        else:
            base_prompt += """

CRITICAL OS INSTRUCTIONS (UNIX):
- Environment: Unix/Linux/MacOS
- Use standard bash commands (ls, grep, cat, rm)
"""
        
        # Inject folder map if available (saves list_directory calls)
        if self._injected_folder_map:
            import json
            folder_str = json.dumps(self._injected_folder_map, indent=2)
            base_prompt += f"""

# Pre-Loaded Project Structure
The following folder structure is already loaded.
**AUTONOMY RULE**: This is a snapshot. If you need to explore deeper or if files are missing, USE `list_directory` to find them.
```json
{folder_str}
```"""
        
        # Inject API contracts if available
        if self._injected_api_contracts:
            import json
            contracts_str = json.dumps(self._injected_api_contracts, indent=2)
            base_prompt += f"""

# Pre-Loaded API Contracts
Use these type definitions. Do NOT read from disk.
```json
{contracts_str}
```"""
        
        return base_prompt
    
    async def code(
        self,
        task: Dict[str, Any],
        folder_map: Optional[Dict[str, Any]] = None,
        api_contracts: Optional[Dict[str, Any]] = None,
        dependency_plan: Optional[Dict[str, Any]] = None,
        existing_code: Optional[Dict[str, str]] = None,
        policy: Optional[Dict[str, Any]] = None,
        artifact_context: Optional[Dict[str, Any]] = None  # File tree & deps from Electron
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
            artifact_context: File tree & dependency data from Electron
            
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
            "artifact_context": artifact_context,  # Pass artifact data for LLM context
        })
        context_result = self.context_consumer.process(context)
        context.update(context_result)
        
        # Step 3: Determine style
        framework = self._detect_framework(folder_map)
        context["framework"] = framework
        style_result = self.style_enforcer.process(context)
        context.update(style_result)

        # Step 3.5: Integrate Collective Intelligence knowledge
        if self._knowledge:
            try:
                feature_request = task.get("description", task.get("title", ""))
                await self._knowledge.get_suggestions(feature_request)
                self._knowledge_prompt = self._knowledge.format_for_prompt()
            except Exception as e:
                # Knowledge retrieval is non-blocking - log and continue
                import logging
                logging.getLogger("ships.coder").warning(f"Knowledge retrieval failed: {e}")
                self._knowledge_prompt = ""
        
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
            
            # Use the tool to generate diff and analysis
            change_data = create_file_change.invoke({
                "path": path,
                "operation": operation.value,
                "new_content": new_content,
                "original_content": original if operation == FileOperation.MODIFY else None,
                "reason": file_info.get("reason", "")
            })
            
            # Create the model
            change = FileChange(
                **change_data,
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
            
            # Defensive: Check for None response
            if response is None:
                logger.error("[CODER] LLM returned None response")
                return {"error": "LLM returned None", "files": []}
            
            # Defensive: Check for None content
            content = response.content
            if content is None:
                logger.warning("[CODER] LLM response.content is None, checking for tool calls")
                # Could be tool calls instead of content
                if hasattr(response, 'tool_calls') and response.tool_calls:
                    logger.info(f"[CODER] Found {len(response.tool_calls)} tool calls")
                    return {"error": "Tool-based response", "files": [], "tool_calls": response.tool_calls}
                return {"error": "Empty LLM response", "files": []}
            
            # Handle list content (Gemini format)
            captured_signature = None
            if isinstance(content, list):
                # Extract thought signature from extras before flattening
                for part in content:
                    if isinstance(part, dict):
                        extras = part.get("extras", {})
                        if "signature" in extras:
                            captured_signature = extras["signature"]
                            break
                        # Some versions might have it at top level
                        if "signature" in part:
                            captured_signature = part["signature"]
                            break
                            
                text_parts = [p.get('text', '') if isinstance(p, dict) else str(p) for p in content]
                content = ''.join(text_parts)
            
            if not content:
                logger.warning("[CODER] LLM returned empty content")
                return {"error": "Empty content", "files": []}
            
            result = self._parse_code_response(content)
            
            # Attach captured signature to result
            if captured_signature:
                result["thought_signature"] = captured_signature
                logger.info("[CODER] Captured Gemini 3 Thought Signature")
                
            return result
        except Exception as e:
            logger.error(f"[CODER] LLM generation failed: {e}")
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
        
        # ================================================================
        # ARTIFACT CONTEXT - Prevents LLM hallucinations
        # ================================================================
        artifact_context = context.get("artifact_context") or {}
        file_tree = artifact_context.get("fileTree", {})
        files = file_tree.get("files", {})
        
        if files:
            # Get relevant files for this task
            scope_files = [
                o.get("file_path", o.get("path", "")) if isinstance(o, dict) else str(o)
                for o in outputs
            ]
            
            # Build valid functions list
            valid_functions = []
            valid_imports = []
            
            for file_path in scope_files:
                file_data = files.get(file_path, {})
                symbols = file_data.get("symbols", {})
                
                # Functions
                for func in symbols.get("functions", []):
                    name = func.get("name", "")
                    params = ", ".join(func.get("parameters", []))
                    visibility = func.get("visibility", "")
                    valid_functions.append(f"  {'[export] ' if visibility == 'export' else ''}{name}({params})")
                
                # Imports
                for imp in symbols.get("imports", []):
                    module = imp.get("module", "")
                    items = imp.get("items", [])
                    if items:
                        valid_imports.append(f"  from '{module}': {', '.join(items)}")
                    else:
                        valid_imports.append(f"  import '{module}'")
            
            if valid_functions:
                parts.append("VALID FUNCTIONS (Do NOT invent new ones):")
                parts.extend(valid_functions[:15])  # Limit to 15
            
            if valid_imports:
                parts.append("VALID IMPORTS (Use ONLY these):")
                parts.extend(valid_imports[:10])  # Limit to 10
        
        # Style rules
        style = context.get("naming_rules", {})
        if style:
            parts.append(f"STYLE: {json.dumps(style)}")
        
        # Collective Intelligence - inject proven patterns
        if self._knowledge_prompt:
            parts.append(self._knowledge_prompt)
        
        # Existing code context
        snippets = context.get("relevant_snippets", {})
        if snippets:
            parts.append("EXISTING CODE CONTEXT:")
            for path, content in list(snippets.items())[:3]:  # Limit to 3 files
                parts.append(f"--- {path} ---")
                parts.append(content[:1000])  # Limit size
        
        parts.append("\nGenerate the implementation. Use the REASONING block first, then the JSON block:")
        
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
        
        TWO-PHASE EXECUTION:
        1. Analyze task and plan implementation approach
        2. Execute file writing using create_react_agent with CODER_TOOLS
        
        Args:
            state: Current agent state
            
        Returns:
            Dict with 'artifacts' key containing all coder artifacts
        """
        logger.info("[CODER] 🚀 Invoking Coder...")
        print("[CODER] Invoked.")
        
        events = []
        events.append(emit_event(
            "agent_start", 
            "coder", 
            "Starting coding implementation...",
            {"phase": "coding"}
        ))
        from langgraph.prebuilt import create_react_agent
        from app.agents.tools.coder import CODER_TOOLS
        from app.prompts import AGENT_PROMPTS
        from app.core.llm_factory import LLMFactory
        from app.core.llm_factory import LLMFactory
        from pathlib import Path
        import os
        import os
        
        artifacts = state.get("artifacts", {})
        parameters = state.get("parameters", {})
        project_path = artifacts.get("project_path")
        
        # Get task from parameters or artifacts
        task = parameters.get("task") or artifacts.get("current_task")
        
        # If no structured task, create one from user_request
        if not task:
            user_request = parameters.get("user_request", "")
            # Also check messages for user request
            messages = state.get("messages", [])
            for m in messages:
                if hasattr(m, 'content') and m.content:
                    user_request = m.content
                    break
            
            task = {
                "id": f"task_{uuid.uuid4().hex[:8]}",
                "title": user_request[:100] if user_request else "Implementation Task",
                "description": user_request,
                "acceptance_criteria": ["Code should work as requested"],
            }
        
        folder_map = artifacts.get("folder_map", {})
        plan_content = artifacts.get("plan_content", "")
        
        # Get implementation plan from disk if not in artifacts
        if not plan_content and project_path:
            plan_path = Path(project_path) / ".ships" / "implementation_plan.md"
            if plan_path.exists():
                try:
                    plan_content = plan_path.read_text(encoding="utf-8")
                except Exception:
                    pass
        
        # Get project structure for context
        project_structure = artifacts.get("project_structure", "")
        completed_files = state.get("completed_files", [])
        
        # ================================================================
        # OPTIMIZATION: Generate File Tree Context
        # ================================================================
        file_tree_context = ""
        if project_path and Path(project_path).exists():
            try:
                tree_lines = []
                ignore_names = {
                    'node_modules', 'dist', 'build', 'coverage', '__pycache__', 
                    'venv', '.venv', 'env', '.env', 'target', 'bin', 'obj', 
                    'vendor', 'bower_components', 'jspm_packages', '.git',
                    '.idea', '.vscode', '.next', '.nuxt', 'out', '.output'
                }
                
                for root, dirs, files in os.walk(project_path):
                    # Skip heavy/hidden folders
                    dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ignore_names]
                    
                    level = root.replace(project_path, '').count(os.sep)
                    indent = ' ' * 4 * (level)
                    tree_lines.append(f"{indent}{os.path.basename(root)}/")
                    subindent = ' ' * 4 * (level + 1)
                    for f in files:
                        if not f.startswith('.'):
                            tree_lines.append(f"{subindent}{f}")
                
                # Limit size
                file_tree_context = "\n".join(tree_lines[:200]) # First 200 lines
                if len(tree_lines) > 200:
                    file_tree_context += "\n... (truncated)"
            except Exception as e:
                file_tree_context = f"Error reading structure: {e}"

        # ================================================================
        # ARTIFACT INTEGRATION: Read structured artifacts
        # ================================================================
        artifact_context = ""
        ships_dir = Path(project_path) / ".ships" if project_path else None
        
        if ships_dir and ships_dir.exists():
            # Read task_list.json
            task_list_path = ships_dir / "task_list.json"
            if task_list_path.exists():
                try:
                    task_list_data = json.loads(task_list_path.read_text(encoding="utf-8"))
                    tasks = task_list_data.get("tasks", [])
                    if tasks:
                        artifact_context += "\n## TASK LIST (from artifacts):\n"
                        for i, t in enumerate(tasks[:5]):  # First 5 tasks
                            title = t.get("title", "Untitled")
                            artifact_context += f"  {i+1}. {title}\n"
                except Exception:
                    pass
            
            # Read folder_map_plan.json - FULL JSON with descriptions
            folder_map_path = ships_dir / "folder_map_plan.json"
            if folder_map_path.exists():
                try:
                    folder_data = json.loads(folder_map_path.read_text(encoding="utf-8"))
                    entries = folder_data.get("entries", [])
                    files_to_create = [e for e in entries if not e.get("is_directory", False)]
                    
                    # DEBUG: Log expected files
                    logger.info(f"[CODER] 📋 Expected files from folder_map_plan: {len(files_to_create)}")
                    for f in files_to_create[:10]:
                        logger.info(f"[CODER]    📄 {f.get('path', 'unknown')}")
                    if len(files_to_create) > 10:
                        logger.info(f"[CODER]    ... and {len(files_to_create) - 10} more")
                    
                    if files_to_create:
                        artifact_context += "\n## FOLDER_MAP_PLAN - Files you MUST create:\n```json\n"
                        # Include path, description, and role for each file
                        compact_entries = [
                            {
                                "path": e.get("path"),
                                "description": e.get("description", ""),
                                "role": e.get("role", "source")
                            }
                            for e in files_to_create[:20]  # Limit to prevent token bloat
                        ]
                        artifact_context += json.dumps(compact_entries, indent=2)
                        artifact_context += "\n```\n"
                except Exception as e:
                    logger.warning(f"[CODER] ⚠️ Failed to read folder_map: {e}")
            
            # Read api_contracts.json
            api_path = ships_dir / "api_contracts.json"
            if api_path.exists():
                try:
                    api_data = json.loads(api_path.read_text(encoding="utf-8"))
                    endpoints = api_data.get("endpoints", [])
                    if endpoints:
                        artifact_context += "\n## API CONTRACTS:\n"
                        for ep in endpoints[:5]:
                            method = ep.get("method", "GET")
                            path = ep.get("path", "/")
                            artifact_context += f"  - {method} {path}\n"
                except Exception:
                    pass

        # ================================================================
        # PRE-READ: Load content of files that will be modified
        # ================================================================
        pre_read_context = ""
        expected_outputs = task.get("expected_outputs", []) if isinstance(task, dict) else []
        
        # Normalize list format
        normalized_outputs = []
        for o in expected_outputs:
            path = o.get("file_path", o.get("path", "")) if isinstance(o, dict) else str(o)
            if path:
                normalized_outputs.append(path)
        
        # SORTING: Prioritize Entry Points (page.tsx, layout.tsx, App.tsx)
        # This ensures the LLM always "sees" the main entry file to wire up components
        def implementation_priority(path: str) -> int:
            lower = path.lower()
            if "page." in lower or "layout." in lower or "app." in lower or "main." in lower or "index." in lower:
                return 0 # Highest priority
            if "types" in lower or "interfaces" in lower:
                return 1 # High priority (context)
            return 2 # Standard priority
            
        normalized_outputs.sort(key=implementation_priority)
        
        # Limit to 15 files (was 3) to allow full context
        for file_path in normalized_outputs[:15]: 
            if file_path and project_path:
                full_path = Path(project_path) / file_path
                if full_path.exists():
                    try:
                        content = full_path.read_text(encoding="utf-8")[:8000] # Increased limit to 8kb
                        pre_read_context += f"\n### {file_path} (EXISTING):\n```\n{content}\n```\n"
                    except Exception:
                        pass

        # ================================================================
        # Context Scoping: Filter task object to prevent bloat
        # ================================================================
        scoped_task = {}
        if isinstance(task, dict):
            # Whitelist essential fields to avoid "unused fields" spam
            essential_keys = {"id", "title", "description", "acceptance_criteria", "expected_outputs", "type", "priority"}
            for k, v in task.items():
                if k in essential_keys:
                    # Truncate lists if too long
                    if isinstance(v, list) and len(v) > 20:
                        scoped_task[k] = v[:20] + [f"... ({len(v)-20} more)"]
                    else:
                        scoped_task[k] = v
        else:
            scoped_task = {"description": str(task)}
        
        scoped_task_str = json.dumps(scoped_task, indent=2) if scoped_task else str(task)

        # ================================================================
        # Build coding prompt with TASK-TYPE AWARENESS
        # ================================================================
        
        # Detect task type from structured intent
        structured_intent = artifacts.get("structured_intent", {})
        task_type = structured_intent.get("task_type", "feature")
        is_fix_task = task_type in ["fix", "modify"]
        
        logger.info(f"[CODER] 🎯 Task Type: {task_type} | Fix Mode: {is_fix_task}")
        
        # Build different instructions based on task type
        if is_fix_task:
            # FIX MODE: Emphasize read-first, surgical edits
            task_instructions = f"""## 🔧 FIX MODE ACTIVATED

⚠️ **YOU MUST EDIT AT LEAST ONE FILE TO COMPLETE THIS TASK** ⚠️

You are FIXING existing code, not creating new features.

MANDATORY WORKFLOW (NO EXCEPTIONS):

**STEP 1: CAPTURE THE ACTUAL ERROR (if not provided)**
If the user mentions "runtime error", "build error", "error", or "not loading" but didn't provide the actual error message:
1. Use `run_command` to execute: `npm run build` or `npm run dev`
2. Look for the actual error message in the output (e.g., "Module not found", "Unexpected token", "Cannot find module")
3. Note the file path and line number from the error

**STEP 2: READ THE BROKEN FILE**
- Use `read_file_from_disk` to read the file mentioned in the error (MAX 2-3 files)
- Find the exact line causing the problem

**STEP 3: IDENTIFY THE EXACT BUG**
- Look at the error message - what is it complaining about?
- Common issues:
  * "Module not found" → Missing import or wrong path
  * "Unexpected token" → Syntax error (missing bracket, comma, etc.)
  * "Cannot find module" → Typo in import path
  * Duplicate CSS directives → Remove duplicate @tailwind lines
  * Missing dependencies → Wrong import statement

**STEP 4: FIX IT NOW (REQUIRED)**
- Use `apply_source_edits` or `write_file_to_disk` to fix the broken code
- Fix ONLY the specific error - don't rewrite working code

**STEP 5: VERIFY & COMPLETE**
- (Optional) Run `npm run build` again to confirm fix
- Say "Implementation complete."

🚫 **FORBIDDEN RESPONSES:**
- ❌ "I found the issue: [explanation]" WITHOUT editing the file
- ❌ "The problem is [description]" WITHOUT fixing it
- ❌ Reading 5+ files without making edits
- ❌ Skipping Step 1 when the error isn't clear

✅ **REQUIRED RESPONSE:**
1. Run diagnostic command (if error unclear)
2. Read broken file  
3. Apply fix using `apply_source_edits` or `write_file_to_disk`
4. Say "Implementation complete."

**CRITICAL RULES:**
- You MUST call `apply_source_edits` or `write_file_to_disk` at least ONCE
- Understanding the problem ≠ completing the task
- Modify 1-3 files MAXIMUM for a fix
- Preserve ALL working code
- Make the MINIMAL change needed

**COMPLETION CRITERIA:**
✅ Complete = You edited at least ONE file with the fix
❌ Incomplete = You only read files and explained the problem

CURRENT TASK:
{scoped_task_str}

PRE-LOADED CONTEXT (but READ MORE if needed):
{pre_read_context if pre_read_context else '(No files pre-loaded - use read_file_from_disk to get context)'}"""  
        else:
            # CREATE/FEATURE MODE: Emphasize efficiency and integration
            task_instructions = f"""## ✨ CREATE/FEATURE MODE

You are CREATING new functionality or files.

WORKFLOW:
1. **CHECK PLAN**: Review folder_map_plan for exact paths
2. **BATCH CREATE**: Use `write_files_batch` for multiple new files
3. **INTEGRATE**: Wire components together (imports/exports)
4. **VERIFY**: Ensure no orphan components - everything must be used

CRITICAL RULES:
- Use `write_files_batch` for efficiency (multiple files in one call)
- Wire new components into existing entry points (page.tsx, App.tsx, etc.)
- Never create orphan components that are never imported
- Check if main entry point is in context - if not, read it first

CURRENT TASK:
{scoped_task_str}

FILES ALREADY CREATED:
{chr(10).join(['- ' + f for f in completed_files]) if completed_files else '- None yet'}

PRE-LOADED CONTEXT:
{pre_read_context if pre_read_context else '(Use read_file_from_disk if you need more context)'}"""  
        
        coder_prompt = f"""PROJECT PATH: {project_path}

CURRENT FILE STRUCTURE:
{file_tree_context}

ARTIFACTS (folder_map, tasks, APIs):
{artifact_context}

IMPLEMENTATION PLAN:
{plan_content[:4000] if plan_content else 'No plan provided - implement based on task description.'}

{task_instructions}

COMPLETION CRITERIA:
{"- You MUST edit at least ONE file with write_file_to_disk or apply_source_edits" if is_fix_task else "- Write complete working code (no TODOs)"}
{"- Understanding the problem is NOT completion - you must APPLY THE FIX" if is_fix_task else "- When ALL files are created and integrated, respond with 'Implementation complete.'"}
{"- Respond 'Implementation complete.' ONLY after editing the file" if is_fix_task else ""}
"""

        # ================================================================
        # Execute using create_react_agent with CODER_TOOLS
        # ================================================================
        try:
            # ================================================================
            # CONTEXT CACHING: Cache static content to reduce token cost
            # The ReAct loop re-sends the system prompt on each iteration.
            # By caching static content, we pay for it ONCE.
            # ================================================================
            from app.core.cache import cache_manager
            import hashlib
            
            cache_name = None
            if project_path:
                # Create a unique cache key from project + plan hash
                plan_hash = hashlib.md5(plan_content[:500].encode()).hexdigest()[:8] if plan_content else "noplan"
                project_id = f"{Path(project_path).name}-{plan_hash}"
                
                # Build cacheable content (system prompt + static context)
                cache_artifacts = {
                    "folder_map": file_tree_context[:3000] if file_tree_context else "",
                    "dependencies": artifact_context[:1500] if artifact_context else "",
                }
                
                # Only cache if we have substantial content (Gemini requires min 1024 tokens, ~4000 chars)
                total_cache_chars = len(file_tree_context) + len(artifact_context)
                if total_cache_chars > 4500:  # ~1125 tokens minimum
                    cache_name = cache_manager.create_project_context_cache(
                        project_id=project_id,
                        artifacts=cache_artifacts,
                        ttl_minutes=30  # Cache for 30 mins (covers typical session)
                    )
                    if cache_name:
                        logger.info(f"[CODER] 🗄️ Created context cache: {cache_name}")
                else:
                    logger.info(f"[CODER] ⏭️ Skipping cache: content too small ({total_cache_chars} chars, need 4500+)")
            
            llm = LLMFactory.get_model("coder", cached_content=cache_name)
            
            # ================================================================
            # MESSAGE TRIMMING: Prevent token bloat in ReAct loop
            # Use pre_model_hook to trim messages before each LLM call
            # ================================================================
            from langchain_core.messages.utils import trim_messages
            
            def pre_model_hook(state):
                """Trim messages to prevent context overflow in ReAct loop."""
                messages = state.get("messages", [])
                
                # Simple token estimation: ~4 chars per token
                def estimate_tokens(msgs):
                    total = 0
                    for m in msgs:
                        content = m.content if hasattr(m, 'content') else str(m)
                        if isinstance(content, list):
                            content = str(content)
                        total += len(content) // 4
                    return total
                
                # Trim to keep last ~4000 tokens worth of messages
                trimmed = trim_messages(
                    messages,
                    strategy="last",
                    token_counter=estimate_tokens,
                    max_tokens=4000,
                    start_on="human",  # Always keep the original human message
                    include_system=True,
                )
                
                # Return trimmed messages via llm_input_messages (doesn't alter state)
                return {"llm_input_messages": trimmed}
            
            # Get settings and command preference
            settings = artifacts.get("settings", {})
            command_pref = settings.get("command_preference", "auto")
            
            # Use instance method for prompt to inject OS-specific context
            system_prompt = self._get_system_prompt(command_preference=command_pref)
            
            # ================================================================
            # DIAGNOSTIC LOGGING: Track what context we're giving the LLM
            # ================================================================
            prompt_size = len(coder_prompt)
            artifact_size = len(artifact_context)
            has_folder_map = "FOLDER_MAP_PLAN" in artifact_context
            has_task_details = "CURRENT TASK" in artifact_context
            file_count_in_context = artifact_context.count('"path":') if artifact_context else 0
            
            logger.info(f"[CODER] 📊 Context Stats: prompt={prompt_size//1000}KB, artifacts={artifact_size//1000}KB, folder_map={has_folder_map}, files_in_context={file_count_in_context}")
            
            coder_agent = create_react_agent(
                model=llm,
                tools=CODER_TOOLS,
                prompt=system_prompt,
                pre_model_hook=pre_model_hook,  # Trim before each LLM call
            )
            
            # Emit thinking event before LLM call with rich task context
            task_title = task.get("title", "") if isinstance(task, dict) else ""
            task_description = task.get("description", "") if isinstance(task, dict) else ""
            acceptance_criteria = task.get("acceptance_criteria", []) if isinstance(task, dict) else []
            
            events.append(emit_event(
                "thinking",
                "coder",
                "Analyzing code requirements and file structure...",
                {
                    "files_expected": len(expected_outputs) if expected_outputs else 0,
                    "task_title": task_title,
                    "task_description": task_description,
                    "expected_files": expected_outputs[:10] if expected_outputs else [],  # First 10 files
                    "acceptance_criteria": acceptance_criteria[:5] if acceptance_criteria else []  # First 5 criteria
                }
            ))
            
            logger.info(f"[CODER] 🎬 Starting ReAct agent (recursion_limit=25)")
            result = await coder_agent.ainvoke(
                {"messages": [HumanMessage(content=coder_prompt)]},
                config={"recursion_limit": 25}  # Increased to 25 for complex features with many files
            )
            
            # Extract completion status from messages
            new_messages = result.get("messages", [])
            implementation_complete = False
            files_written = []
            
            # ================================================================
            # DIAGNOSTIC LOGGING: Track LLM's ReAct behavior turn-by-turn
            # ================================================================
            tool_sequence = []
            for i, msg in enumerate(new_messages):
                msg_type = type(msg).__name__
                if isinstance(msg, AIMessage) and hasattr(msg, 'tool_calls') and msg.tool_calls:
                    for tc in msg.tool_calls:
                        tc_name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", None)
                        tool_sequence.append(tc_name)
                elif hasattr(msg, 'name'):
                    tool_name = getattr(msg, 'name', None)
                    if tool_name:
                        tool_sequence.append(f"✓{tool_name}")  # ✓ = completed
            
            logger.info(f"[CODER] 🔍 ReAct Tool Sequence ({len(tool_sequence)} calls): {' → '.join(tool_sequence[:15])}")
            if len(tool_sequence) > 15:
                logger.info(f"[CODER]    ... and {len(tool_sequence) - 15} more tool calls")
            
            # Count writes vs reads
            write_calls = sum(1 for t in tool_sequence if 'write' in t.lower())
            read_calls = sum(1 for t in tool_sequence if 'read' in t.lower() or 'get' in t.lower())
            logger.info(f"[CODER] 📈 Action Ratio: {write_calls} writes, {read_calls} reads")
            
            # IMPROVED: Track files from both AIMessage.tool_calls AND ToolMessage responses
            from langchain_core.messages import AIMessage, ToolMessage
            
            for msg in new_messages:
                # Check completion status
                if hasattr(msg, 'content') and msg.content:
                    content = str(msg.content).lower()
                    if "implementation complete" in content:
                        implementation_complete = True
                
                # Method 1: Track from AIMessage tool_calls (what LLM requested)
                if isinstance(msg, AIMessage) and hasattr(msg, 'tool_calls') and msg.tool_calls:
                    for tc in msg.tool_calls:
                        # Handle both dict and TypedDict access patterns
                        tc_name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", None)
                        tc_args = tc.get("args", {}) if isinstance(tc, dict) else getattr(tc, "args", {})
                        
                        # Track all file modification tools
                        if tc_name in ["write_file_to_disk", "write_to_file"]:
                            path = tc_args.get("file_path", tc_args.get("TargetFile", ""))
                            if path:
                                files_written.append(path)
                                # Emit file_written event
                                events.append(emit_event(
                                    "file_written",
                                    "coder",
                                    path,
                                    {"action": "write"}
                                ))
                        
                        elif tc_name == "write_files_batch":
                            files_arg = tc_args.get("files", []) if isinstance(tc_args, dict) else []
                            for file_entry in files_arg:
                                if isinstance(file_entry, dict):
                                    path = file_entry.get("path", file_entry.get("file_path", ""))
                                    if path:
                                        files_written.append(path)
                                        # Emit file_written event
                                        events.append(emit_event(
                                            "file_written",
                                            "coder",
                                            path,
                                            {"action": "batch_write"}
                                        ))
                        
                        elif tc_name in ["replace_file_content", "multi_replace_file_content"]:
                            path = tc_args.get("TargetFile", tc_args.get("file_path", ""))
                            if path:
                                files_written.append(path)
                                # Emit file_written event
                                events.append(emit_event(
                                    "file_written",
                                    "coder",
                                    path,
                                    {"action": "edit"}
                                ))
                        
                        elif tc_name == "apply_source_edits":
                            # Check common argument names for source file
                            path = tc_args.get("source_file", tc_args.get("path", tc_args.get("file_path", "")))
                            if path: files_written.append(path)
                            
                        elif tc_name == "delete_file_from_disk":
                            path = tc_args.get("file_path", tc_args.get("path", ""))
                            if path:
                                files_written.append(path)
                                events.append(emit_event(
                                    "file_deleted",
                                    "coder",
                                    path,
                                    {"action": "delete"}
                                ))
                
                # Method 2: Track from ToolMessage responses (what actually executed)
                elif isinstance(msg, ToolMessage):
                    tool_name = getattr(msg, 'name', '')
                    # Parse tool response for file paths
                    if tool_name in ["write_file_to_disk", "write_files_batch", "apply_source_edits"]:
                        # Tool response content often contains the file path
                        if hasattr(msg, 'artifact') and isinstance(msg.artifact, dict):
                            if 'file_path' in msg.artifact:
                                files_written.append(msg.artifact['file_path'])
                            elif 'files' in msg.artifact:
                                files_written.extend(msg.artifact['files'])
            
            # Normalize paths to be relative to project root
            final_files_written = []
            for f in files_written:
                if project_path:
                    try:
                        # robust relative path calculation
                        rel_path = os.path.relpath(f, project_path)
                        if not rel_path.startswith(".."):
                             final_files_written.append(rel_path.replace("\\", "/"))
                             continue
                    except ValueError:
                        pass
                # fallback or already relative
                final_files_written.append(str(f).replace("\\", "/"))
            
            # FALLBACK: If no files tracked from messages, scan disk for changed files
            # This happens when tool execution doesn't properly record in messages
            if not final_files_written and project_path:
                logger.warning(f"[CODER] ⚠️ No files tracked from messages - scanning disk for changes")
                try:
                    from pathlib import Path
                    project_root = Path(project_path)
                    
                    # Get all source files from folder_map if available
                    folder_map = parameters.get("folder_map", {})
                    if folder_map and "entries" in folder_map:
                        for entry in folder_map["entries"]:
                            if not entry.get("is_directory") and entry.get("path"):
                                file_path = project_root / entry["path"]
                                if file_path.exists() and file_path.is_file():
                                    rel_path = str(entry["path"]).replace("\\", "/")
                                    final_files_written.append(rel_path)
                                    logger.info(f"[CODER] 📁 Tracked existing file from disk: {rel_path}")
                except Exception as scan_err:
                    logger.debug(f"[CODER] Disk scan failed: {scan_err}")

            # CRITICAL: For fix mode, if zero writes happened, force incomplete status
            # This must happen AFTER message processing to override any LLM "implementation complete" claim
            is_fix_mode = task_type == "fix"
            if is_fix_mode and write_calls == 0:
                logger.warning(f"[CODER] ❌ FIX MODE: Zero writes detected - marking incomplete (read-only analysis is not a fix)")
                implementation_complete = False  # Override any "implementation complete" from LLM

            # Emit agent_complete event
            if implementation_complete:
                events.append(emit_event(
                    "agent_complete",
                    "coder",
                    f"Implementation complete. {len(final_files_written)} files created/updated.",
                    {"files_count": len(final_files_written), "complete": True}
                ))
            else:
                events.append(emit_event(
                    "agent_complete",
                    "coder",
                    f"Partial implementation. {len(final_files_written)} files created.",
                    {"files_count": len(final_files_written), "complete": False}
                ))

            return {
                "artifacts": {
                    "files_written": final_files_written,
                    "message_count": len(new_messages),
                },
                "status": "complete" if implementation_complete else "in_progress",
                "success": True,
                "implementation_complete": implementation_complete,
                "completed_files": final_files_written,
                "stream_events": events,
            }
            
        except Exception as e:
            return {
                "artifacts": {},
                "status": "error",
                "success": False,
                "error": str(e),
            }

