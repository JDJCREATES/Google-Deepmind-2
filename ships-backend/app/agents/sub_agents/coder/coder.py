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
        config: Optional[CoderComponentConfig] = None,
        cached_content: Optional[str] = None
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
            reasoning_level="high",  # Coder needs high reasoning
            artifact_manager=artifact_manager,
            cached_content=cached_content
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

🚨 ABSOLUTELY CRITICAL - CODE FILES ONLY CONTAIN CODE 🚨
- NEVER write reasoning, thinking, or planning inside code files
- NEVER include comments like "Let's think about...", "Wait, I need to...", "Actually..."
- NEVER include multi-line reasoning comments in CSS, JS, or any code file
- Code files contain ONLY: functional code, brief technical comments, JSDoc/docstrings
- If you need to reason, do it BEFORE calling write_file_to_disk, not inside the file content
- VIOLATION OF THIS RULE PRODUCES BROKEN CODE AND IS UNACCEPTABLE

=======================================================================
⚠️ MANDATORY SCAFFOLDING CHECK - READ THIS FIRST ⚠️
=======================================================================
BEFORE you write ANY files, you MUST check if the project needs scaffolding!

🔴 STEP 1: ALWAYS call list_directory(".") FIRST
🔴 STEP 2: Check if package.json, node_modules, or framework files exist
🔴 STEP 3: If NOT found → YOU MUST SCAFFOLD!

IF SCAFFOLDING IS NEEDED:
✅ DO THIS (use run_terminal_command):
   1. npx -y create-vite@latest . --template react     (for React/Vite)
   2. npx -y create-next-app@latest . --typescript --yes  (for Next.js)
   3. npm install                                      (always run after scaffold)
   4. THEN write your custom code files

⚠️ IMPORTANT: Always use -y or --yes flags to avoid interactive prompts!

❌ NEVER DO THIS:
   - Writing package.json manually
   - Writing vite.config.js manually
   - Writing index.html manually
   - Writing scaffolding files yourself

🚨 DETECTION LOGIC:
- No package.json? → SCAFFOLD
- Empty directory? → SCAFFOLD
- Task mentions "create", "new project", "vite", "next"? → SCAFFOLD
- Only .ships/ directory exists? → SCAFFOLD

Common Commands (NON-INTERACTIVE):
- Vite + React: `npx -y create-vite@latest . --template react`
- Vite + React + TS: `npx -y create-vite@latest . --template react-ts`
- Next.js: `npx -y create-next-app@latest . --typescript --yes --app --no-src-dir`
- Vue: `npx -y create-vue@latest . --default`

🔴 THIS IS NOT OPTIONAL. IF YOU SKIP SCAFFOLDING WHEN NEEDED, YOU FAIL.
=======================================================================

CODE QUALITY REQUIREMENTS:
- Follow detected repository patterns (naming, style, structure)
- Include proper error handling
- Add type annotations where applicable
- Write clear, concise comments only where non-obvious

AVAILABLE TOOLS:
⭐ PREFERRED FOR MODIFICATIONS (saves tokens!):
- apply_source_edits: Robust Search/Replace blocks (Fuzzy Matched). USE THIS FOR EDITS!
- insert_content: Insert new code after a unique context block.

📁 FILE OPERATIONS:
- write_file_to_disk: Create NEW files or full rewrites only
- read_file_from_disk: Read existing files
- list_directory: See project structure  

🖥️ TERMINAL (for scaffolding):
- run_terminal_command: Execute npm, npx, git commands
- get_allowed_terminal_commands: See what commands are allowed

TOKEN EFFICIENCY RULES:
1. For NEW files → use write_file_to_disk
2. For EDITING existing files → use apply_source_edits (SAVES TOKENS!)
3. Don't rewrite entire files when you can do targeted edits

OUTPUT FORMAT:
Use the tools directly to write/edit files.
For scaffolding, call run_terminal_command FIRST.
For modifications, use apply_source_edits.
ALWAYS provide unique surrounding context in your "search" blocks.

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
        import logging
        logger = logging.getLogger("ships.coder")
        
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
            if isinstance(content, list):
                text_parts = [p.get('text', '') if isinstance(p, dict) else str(p) for p in content]
                content = ''.join(text_parts)
            
            if not content:
                logger.warning("[CODER] LLM returned empty content")
                return {"error": "Empty content", "files": []}
            
            return self._parse_code_response(content)
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
        
        TWO-PHASE EXECUTION:
        1. Analyze task and plan implementation approach
        2. Execute file writing using create_react_agent with CODER_TOOLS
        
        Args:
            state: Current agent state
            
        Returns:
            Dict with 'artifacts' key containing all coder artifacts
        """
        from langgraph.prebuilt import create_react_agent
        from app.agents.tools.coder import CODER_TOOLS
        from app.prompts import AGENT_PROMPTS
        from app.core.llm_factory import LLMFactory
        from pathlib import Path
        
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
        # Build coding prompt with full context
        # ================================================================
        coder_prompt = f"""PROJECT PATH: {project_path}

IMPLEMENTATION PLAN:
{plan_content[:4000] if plan_content else 'No plan provided - implement based on task description.'}

CURRENT TASK:
{json.dumps(task, indent=2) if isinstance(task, dict) else str(task)}

FILES ALREADY CREATED:
{chr(10).join(['- ' + f for f in completed_files]) if completed_files else '- None yet'}

YOUR INSTRUCTIONS:
1. Analyze the task and implementation plan
2. Write the NEXT file that needs to be created using write_file_to_disk
3. Write COMPLETE, WORKING code - no TODOs or placeholders
4. After each file, check if more files need to be created
5. When ALL files from the plan are done, respond with "Implementation complete."

IMPORTANT:
- Check what files exist before writing
- Write complete React/TypeScript/Python code
- Follow the folder structure in the plan
- Include all necessary imports
- Each file should be self-contained and work correctly"""

        # ================================================================
        # Execute using create_react_agent with CODER_TOOLS
        # ================================================================
        try:
            llm = LLMFactory.get_model("coder")
            coder_agent = create_react_agent(
                model=llm,
                tools=CODER_TOOLS,
                prompt=AGENT_PROMPTS.get("coder", "You are a code implementation agent."),
            )
            
            result = await coder_agent.ainvoke(
                {"messages": [HumanMessage(content=coder_prompt)]},
                config={"recursion_limit": 50}  # Allow many file writes
            )
            
            # Extract completion status from messages
            new_messages = result.get("messages", [])
            implementation_complete = False
            files_written = []
            
            for msg in new_messages:
                if hasattr(msg, 'content') and msg.content:
                    content = str(msg.content).lower()
                    if "implementation complete" in content:
                        implementation_complete = True
                
                # Track tool calls for file writes
                if hasattr(msg, 'tool_calls') and msg.tool_calls:
                    for tc in msg.tool_calls:
                        if tc.get("name") == "write_file_to_disk":
                            path = tc.get("args", {}).get("file_path", "")
                            if path:
                                files_written.append(path)
            
            return {
                "artifacts": {
                    "files_written": files_written,
                    "message_count": len(new_messages),
                },
                "status": "complete" if implementation_complete else "in_progress",
                "success": True,
                "implementation_complete": implementation_complete,
                "completed_files": files_written,
            }
            
        except Exception as e:
            return {
                "artifacts": {},
                "status": "error",
                "success": False,
                "error": str(e),
            }

