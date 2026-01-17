"""
ShipS* Fixer Agent

Given a concrete Validation Report (failures), the Fixer produces the
smallest safe, auditable remediation that moves the system toward a
Validator: pass state while strictly honoring Planner artifacts.

Uses Gemini 3 Pro for repair strategy synthesis.

Core Principles:
- Artifact-first fixes (all fixes are persisted artifacts)
- Never re-authorize architecture changes (escalate to Planner)
- Minimize scope (smallest change that satisfies validation)
- Full explainability and traceability
- Safety first (no secrets, no banned packages)
"""

from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple
import uuid
import hashlib

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.base.base_agent import BaseAgent
from app.graphs.state import AgentState
from app.artifacts import ArtifactManager

from app.agents.sub_agents.fixer.models import (
    FixPlan, FixPatch, FixChange, FixTestBundle, FixTest,
    FixReport, FixAttemptLog, ReplanRequest,
    FixScope, FixApproach, FixRisk, FixResult, ApprovalType,
    FixerConfig, FixerOutput, ViolationFix,
)

# Strategies are in central location: app/agents/tools/fixer/
from app.agents.tools.fixer.strategies import (
    FixStrategy, StructuralFixer, CompletenessFixer,
    DependencyFixer, ScopeFixer,
)
from app.agents.sub_agents.validator.models import (
    ValidationReport, Violation, FailureLayer,
    ValidationStatus, ViolationSeverity,
)

from app.streaming.stream_events import emit_event


class Fixer(BaseAgent):
    """
    Fixer Agent - Produces Minimal, Safe Remediations.
    
    Uses Gemini 3 Pro for repair strategy synthesis.
    
    Key Behaviors:
    1. Triage violations into fixable vs escalate
    2. Generate minimal fix patches
    3. Never violate Planner artifacts (escalate instead)
    4. Track all attempts for audit
    5. Re-validate after applying (Validator must pass)
    
    Outputs are first-class artifacts:
    - FixPlan: Proposed strategy
    - FixPatch: Actual changes
    - FixReport: Results
    - FixAttemptLog: Audit trail
    """
    
    def __init__(
        self,
        artifact_manager: Optional[ArtifactManager] = None,
        config: Optional[FixerConfig] = None
    ):
        """Initialize the Fixer."""
        super().__init__(
            name="Fixer",
            agent_type="coder",  # Uses Pro for heavy reasoning
            reasoning_level="standard",
            artifact_manager=artifact_manager
        )
        
        self.config = config or FixerConfig()
        
        # Initialize strategies for each layer
        self.strategies: Dict[FailureLayer, FixStrategy] = {
            FailureLayer.STRUCTURAL: StructuralFixer(self.config),
            FailureLayer.COMPLETENESS: CompletenessFixer(self.config),
            FailureLayer.DEPENDENCY: DependencyFixer(self.config),
            FailureLayer.SCOPE: ScopeFixer(self.config),
        }
    
    def _get_system_prompt(self) -> str:
        """Get system prompt for fix generation."""
        return """You are the Fixer for ShipS*, an AI coding system that SHIPS WORKING CODE.

YOUR MISSION: Fix code errors so the build passes. You are a capable developer.

YOU HAVE FULL ACCESS TO:
- read_file_from_disk: Read any source file to understand what's happening
- write_file_to_disk: Write or overwrite files with fixed code
- apply_source_edits: Make targeted line-by-line edits (preferred for modifications)
- insert_content: Insert new content at specific locations
- run_terminal_command: Run build commands, type-check, run tests to verify

APPROACH:
1. Read the error messages carefully - understand what's actually broken
2. Read the relevant source files to see the context
3. Reason about the root cause - don't just patch symptoms
4. Make the minimal fix needed - smallest change that solves the problem
5. Verify by running build/type-check if needed

YOU CAN FIX:
- Syntax errors
- Type errors  
- Missing imports
- Build configuration issues
- Runtime errors
- Broken references
- Any code issue you can diagnose

STYLE:
- Be surgical - smallest change that fixes the issue
- Preserve existing code style and formatting
- Add comments if the fix is non-obvious
- If you genuinely cannot fix something after trying, explain clearly why

Output your reasoning, then use tools to implement the fix."""
    
    async def fix(
        self,
        validation_report: ValidationReport,
        file_contents: Optional[Dict[str, str]] = None,
        folder_map: Optional[Dict[str, Any]] = None,
        app_blueprint: Optional[Dict[str, Any]] = None,
        attempt_number: int = 1,
        project_path: Optional[str] = None
    ) -> FixerOutput:
        """
        Attempt to fix validation failures.
        
        This is the MAIN ENTRY POINT for fixing.
        
        Args:
            validation_report: The failing validation report
            file_contents: Map of file path -> content
            folder_map: Folder structure (for checking fixes)
            app_blueprint: App context
            attempt_number: Current attempt (for retry limits)
            project_path: Project root path (for diagnostics lookup)
            
        Returns:
            FixerOutput with fix plan, patch, and recommendations
        """
        start = datetime.utcnow()
        
        # Fetch diagnostics from store (TypeScript errors from Validator)
        diagnostics_context = ""
        if project_path:
            ts_errors = self._fetch_diagnostics(project_path)
            if ts_errors:
                diagnostics_context = "\n\n## TYPESCRIPT ERRORS (from tsc):\n"
                for err in ts_errors[:10]:  # First 10 errors
                    diagnostics_context += f"- {err.get('file', '?')}:{err.get('line', '?')} - {err.get('message', '')}\n"
        
        # Initialize attempt log
        attempt_log = FixAttemptLog(
            fix_plan_id="pending",
            attempt_number=attempt_number,
            max_attempts=self.config.max_auto_fix_attempts
        )
        
        # Check retry limit
        if attempt_number > self.config.max_auto_fix_attempts:
            attempt_log.add_step("check_retry_limit", False, "Max attempts exceeded")
            attempt_log.escalated = True
            attempt_log.escalation_reason = "Max automatic fix attempts exceeded"
            
            return FixerOutput(
                success=False,
                requires_approval=True,
                fix_attempt_log=attempt_log,
                recommended_action="request_user_approval",
                confidence=0.0,
                next_agent="user"
            )
        
        # Triage violations
        attempt_log.add_step("triage_violations", True)
        triage = self._triage_violations(validation_report)
        
        # Check if any violations require replan
        if triage["requires_replan"]:
            return self._create_replan_output(
                validation_report, triage, attempt_log
            )
        
        # Check if any violations are policy-blocked
        if triage["policy_blocked"] and not triage["fixable"]:
            attempt_log.add_step("policy_check", False, "All violations policy-blocked")
            return FixerOutput(
                success=False,
                requires_approval=True,
                fix_attempt_log=attempt_log,
                recommended_action="request_security_approval",
                confidence=0.0,
                next_agent="user"
            )
        
        # Generate fix plan
        attempt_log.add_step("generate_fix_plan", True)
        fix_plan = self._create_fix_plan(validation_report, triage)
        attempt_log.fix_plan_id = fix_plan.id
        
        # Generate fix patches
        attempt_log.add_step("generate_patches", True)
        fix_patch, violation_fixes = self._generate_patches(
            triage["fixable"],
            file_contents or {},
            fix_plan.id
        )
        
        # Update fix plan with violation fixes
        fix_plan.violation_fixes = violation_fixes
        
        # Run preflight checks on patch
        attempt_log.add_step("preflight_checks", True)
        self._run_preflight_checks(fix_patch, folder_map)
        
        # Check if patch passed preflight
        if not fix_patch.preflight_passed:
            attempt_log.add_step("preflight_validation", False, "Preflight checks failed")
            fix_plan.auto_apply_allowed = False
            fix_plan.required_approvals.append(ApprovalType.USER)
        
        # Determine approval requirements
        if fix_plan.needs_approval() or not self.config.allow_auto_apply:
            return FixerOutput(
                success=True,
                requires_approval=True,
                fix_plan=fix_plan,
                fix_patch=fix_patch,
                fix_attempt_log=attempt_log,
                recommended_action="request_user_approval",
                confidence=fix_plan.confidence,
                next_agent="user"
            )
        
        # Create fix report (for auto-apply case)
        fix_report = FixReport(
            fix_plan_id=fix_plan.id,
            fix_patch_id=fix_patch.id,
            result=FixResult.PENDING_APPROVAL,  # Will be updated after apply
            final_confidence=fix_plan.confidence,
            rationale=fix_plan.summary
        )
        
        attempt_log.add_step("fix_complete", True)
        attempt_log.final_result = FixResult.PENDING_APPROVAL
        
        # Log action
        if self._artifact_manager:
            self.log_action(
                action="fix_generated",
                input_summary=f"{len(validation_report.violations)} violations",
                output_summary=f"{len(fix_patch.changes)} patches, confidence={fix_plan.confidence:.2f}",
                reasoning=fix_plan.summary
            )
        
        return FixerOutput(
            success=True,
            requires_approval=not fix_plan.auto_apply_allowed,
            fix_plan=fix_plan,
            fix_patch=fix_patch,
            fix_report=fix_report,
            fix_attempt_log=attempt_log,
            recommended_action="apply_patch" if fix_plan.auto_apply_allowed else "request_user_approval",
            confidence=fix_plan.confidence,
            next_agent="validator"
        )
    
    def _triage_violations(
        self,
        validation_report: ValidationReport
    ) -> Dict[str, List[Violation]]:
        """Classify violations into fixable vs escalate."""
        result = {
            "fixable": [],
            "requires_replan": [],
            "policy_blocked": [],
            "unknown": []
        }
        
        for violation in validation_report.violations:
            layer = violation.layer
            strategy = self.strategies.get(layer)
            
            if not strategy:
                result["unknown"].append(violation)
                continue
            
            can_fix, scope = strategy.can_fix(violation)
            
            if can_fix and scope == FixScope.LOCAL:
                result["fixable"].append(violation)
            elif scope == FixScope.ARCHITECTURAL:
                result["requires_replan"].append(violation)
            elif scope == FixScope.POLICY_BLOCKED:
                result["policy_blocked"].append(violation)
            else:
                result["unknown"].append(violation)
        
        return result
    
    def _create_fix_plan(
        self,
        validation_report: ValidationReport,
        triage: Dict[str, List]
    ) -> FixPlan:
        """Create a fix plan from triaged violations."""
        fixable = triage["fixable"]
        
        # Determine primary approach
        approaches = set()
        for v in fixable:
            if "todo" in v.rule.lower():
                approaches.add(FixApproach.REMOVE_TODO)
            elif "placeholder" in v.rule.lower():
                approaches.add(FixApproach.ADD_MOCK)
            elif "import" in v.rule.lower():
                approaches.add(FixApproach.FIX_IMPORT)
            else:
                approaches.add(FixApproach.PATCH_FILE)
        
        primary_approach = list(approaches)[0] if approaches else FixApproach.PATCH_FILE
        
        # Calculate confidence
        confidence = 0.9 if len(fixable) <= 3 else 0.8
        if triage["requires_replan"]:
            confidence -= 0.1
        if triage["policy_blocked"]:
            confidence -= 0.1
        
        # Determine risk
        risk = FixRisk.LOW
        if len(fixable) > 5:
            risk = FixRisk.MEDIUM
        if any(v.severity == ViolationSeverity.CRITICAL for v in fixable):
            risk = FixRisk.HIGH
        
        return FixPlan(
            origin_validation_report_id=validation_report.id,
            plan_id=validation_report.plan_id,
            task_id=validation_report.task_id,
            summary=f"Fix {len(fixable)} violations using {primary_approach.value}",
            failure_layer=validation_report.failure_layer.value,
            approach=primary_approach,
            estimated_risk=risk,
            confidence=max(0.0, confidence),
            auto_apply_allowed=risk == FixRisk.LOW and confidence >= self.config.auto_apply_threshold,
            expected_outputs=["fix_patch", "fix_report"]
        )
    
    def _generate_patches(
        self,
        violations: List[Violation],
        file_contents: Dict[str, str],
        fix_plan_id: str
    ) -> Tuple[FixPatch, List[ViolationFix]]:
        """Generate patches for fixable violations."""
        fix_patch = FixPatch(
            fix_plan_id=fix_plan_id,
            summary=f"Fixes for {len(violations)} violations"
        )
        violation_fixes = []
        
        for violation in violations:
            layer = violation.layer
            strategy = self.strategies.get(layer)
            
            if not strategy:
                continue
            
            context = {"file_contents": file_contents}
            violation_fix, change = strategy.generate_fix(violation, context)
            
            if violation_fix:
                violation_fixes.append(violation_fix)
            
            if change:
                fix_patch.add_change(change)
        
        # Generate commit message
        fix_patch.commit_message = f"fix: Address {len(violations)} validation violations"
        fix_patch.rollback_command = "git checkout HEAD~1 -- ."
        
        return fix_patch, violation_fixes
    
    def _run_preflight_checks(
        self,
        fix_patch: FixPatch,
        folder_map: Optional[Dict[str, Any]]
    ) -> None:
        """Run preflight checks on the fix patch."""
        fix_patch.preflight_passed = True
        
        # Check 1: No protected paths
        if folder_map:
            protected = [".git/", "node_modules/", ".env"]
            for change in fix_patch.changes:
                for p in protected:
                    if p in change.path:
                        fix_patch.preflight_passed = False
                        fix_patch.dependency_conflicts.append(f"Protected path: {change.path}")
        
        # Check 2: Lint (simplified)
        for change in fix_patch.changes:
            content = change.new_content or ""
            # Check for obvious syntax issues
            if content.count("(") != content.count(")"):
                fix_patch.lint_passed = False
                fix_patch.preflight_passed = False
        
        # Check 3: Size limits
        if fix_patch.total_files > self.config.max_files_per_fix:
            fix_patch.preflight_passed = False
        if fix_patch.total_lines_added > self.config.max_lines_per_fix:
            fix_patch.preflight_passed = False
    
    def _create_replan_output(
        self,
        validation_report: ValidationReport,
        triage: Dict[str, List],
        attempt_log: FixAttemptLog
    ) -> FixerOutput:
        """Create output that requests replan."""
        attempt_log.add_step("check_replan_needed", True)
        attempt_log.escalated = True
        attempt_log.escalation_reason = "Violations require architectural changes"
        
        # Create replan request
        replan_violations = triage["requires_replan"]
        first_violation = replan_violations[0] if replan_violations else None
        
        # Get appropriate strategy to create replan request
        replan_request = None
        if first_violation:
            strategy = self.strategies.get(first_violation.layer)
            if hasattr(strategy, 'create_replan_request'):
                replan_request = strategy.create_replan_request(
                    first_violation,
                    validation_report.id,
                    f"fixplan_{uuid.uuid4().hex[:8]}"
                )
        
        if not replan_request:
            replan_request = ReplanRequest(
                origin_validation_report_id=validation_report.id,
                origin_fix_plan_id="none",
                reason="Violations require plan changes",
                violated_artifact="folder_map",
                violation_details="; ".join(v.message for v in replan_violations[:3])
            )
        
        return FixerOutput(
            success=False,
            requires_replan=True,
            replan_request=replan_request,
            fix_attempt_log=attempt_log,
            recommended_action="ask_user",
            confidence=0.0,
            next_agent="user"  # Don't escalate to planner - ask user what to do
        )
    
    async def invoke(self, state: AgentState) -> Dict[str, Any]:
        """
        Invoke the Fixer as part of orchestrator workflow.
        
        TWO-PHASE EXECUTION:
        1. Analyze validation errors and generate fix plan
        2. Apply fixes using create_react_agent with FIXER_TOOLS
        
        Args:
            state: Current agent state
            
        Returns:
            Dict with fix results
        """
        events = []
        events.append(emit_event(
            "agent_start",
            "fixer",
            "Applying fixes...",
            {"phase": "fixing"}
        ))
        
        events.append(emit_event(
            "thinking",
            "fixer",
            "Analyzing validation errors and generating fix plan...",
            {}
        ))
        
        from langgraph.prebuilt import create_react_agent
        from app.agents.tools.fixer import FIXER_TOOLS
        from app.prompts import AGENT_PROMPTS
        from app.core.llm_factory import LLMFactory
        from pathlib import Path
        
        artifacts = state.get("artifacts", {})
        parameters = state.get("parameters", {})
        project_path = artifacts.get("project_path")
        error_log = state.get("error_log", [])
        fix_attempts = parameters.get("attempt_number", 1)
        
        # Check if we should escalate to user (not planner - that causes rebuilds)
        max_attempts = self.config.max_auto_fix_attempts
        if fix_attempts > max_attempts:
            return {
                "success": False,
                "requires_user_help": True,
                "artifacts": {"reason": "Max fix attempts exceeded. Need human guidance."},
                "recommended_action": "ask_user",
                "recommended_action": "ask_user",
                "next_agent": "user",
                "stream_events": events,
            }
        
        # Get recent errors for context
        recent_errors = error_log[-5:] if error_log else ["No specific errors"]
        
        # ================================================================
        # Build fix prompt with error context
        # ================================================================
        fixer_prompt = f"""PROJECT PATH: {project_path}

FIX ATTEMPT: {fix_attempts}/{max_attempts}

ERRORS TO FIX:
{chr(10).join(['- ' + str(e) for e in recent_errors])}

YOUR TASK:
1. Read the relevant files using read_file_from_disk
2. Analyze what's broken based on the errors
3. Apply TARGETED fixes using write_file_to_disk
4. Only fix what is broken - do NOT rewrite entire files

IMPORTANT CONSTRAINTS:
- Make MINIMAL changes
- Do NOT change file structure
- Do NOT add new dependencies without good reason
- If the fix requires architecture changes, respond with:
  {{"escalate": true, "reason": "..."}}

When done, respond with:
{{"status": "fixed", "files_patched": [...]}}"""

        # ================================================================
        # Execute using create_react_agent with FIXER_TOOLS
        # ================================================================
        try:
            llm = LLMFactory.get_model("fixer")
            fixer_agent = create_react_agent(
                model=llm,
                tools=FIXER_TOOLS,
                prompt=AGENT_PROMPTS.get("fixer", "You are a code fixing agent."),
            )
            
            result = await fixer_agent.ainvoke(
                {"messages": [HumanMessage(content=fixer_prompt)]},
                config={"recursion_limit": 25}
            )
            
            # Analyze result
            new_messages = result.get("messages", [])
            needs_escalate = False
            escalation_reason = ""
            files_patched = []
            
            import json as json_mod
            import re as re_mod
            
            for msg in new_messages:
                if hasattr(msg, 'content') and msg.content:
                    content = str(msg.content)
                    
                    # Check for escalation
                    try:
                        json_match = re_mod.search(r'\{[^}]*"escalate"[^}]*\}', content)
                        if json_match:
                            parsed = json_mod.loads(json_match.group())
                            if parsed.get("escalate"):
                                needs_escalate = True
                                escalation_reason = parsed.get("reason", "Fixer requested escalation")
                    except:
                        pass
                
                # Track file patches from tool calls
                if hasattr(msg, 'tool_calls') and msg.tool_calls:
                    for tc in msg.tool_calls:
                        if tc.get("name") == "write_file_to_disk":
                            path = tc.get("args", {}).get("file_path", "")
                            if path:
                                files_patched.append(path)
                                # Emit fix_applied event
                                events.append(emit_event(
                                    "fix_applied",
                                    "fixer",
                                    path,
                                    {"action": "patch"}
                                ))
            
            if needs_escalate:
                events.append(emit_event(
                    "agent_complete",
                    "fixer",
                    f"Escalating: {escalation_reason}",
                    {"escalated": True}
                ))
                return {
                    "success": False,
                    "requires_user_help": True,
                    "artifacts": {"escalation_reason": escalation_reason},
                    "recommended_action": "ask_user",
                    "next_agent": "user",
                    "stream_events": events,
                }
            
            events.append(emit_event(
                "agent_complete",
                "fixer",
                f"Fixes applied to {len(files_patched)} files",
                {"files_count": len(files_patched), "complete": True}
            ))
            
            return {
                "success": True,
                "requires_replan": False,
                "artifacts": {
                    "files_patched": files_patched,
                    "message_count": len(new_messages),
                },
                "status": "fixed",
                "recommended_action": "validate",
                "recommended_action": "validate",
                "next_agent": "validator",
                "stream_events": events,
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "artifacts": {},
                "recommended_action": "error",
            }
    
    def _fetch_diagnostics(self, project_path: str) -> list:
        """
        Fetch diagnostics from the diagnostics store.
        
        Args:
            project_path: Project root path
            
        Returns:
            List of diagnostic errors (or empty list)
        """
        try:
            import httpx
            response = httpx.get(
                f"http://localhost:8001/diagnostics/status",
                params={"project_path": project_path},
                timeout=5.0
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("errors", [])
        except Exception as e:
            print(f"[Fixer] Failed to fetch diagnostics: {e}")
        return []

