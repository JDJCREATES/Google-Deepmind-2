"""
ShipS* Validator Agent

The Validator is the GATE - the last word before builds, previews, and success signals.

It does NOT negotiate.
It does NOT suggest.
It PASSES or FAILS.

If it fails:
- The Orchestrator MUST act
- No other agent may proceed unchecked

Uses Gemini 3 Flash for:
- High precision
- Low creativity
- Schema adherence
- Fast iteration

This agent should be BORING, RUTHLESS, and CHEAP.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
import uuid

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.base.base_agent import BaseAgent
from app.graphs.state import AgentState
from app.artifacts import ArtifactManager

from app.agents.sub_agents.validator.models import (
    ValidationStatus, FailureLayer, RecommendedAction,
    ViolationSeverity, Violation, ValidationReport, LayerResult,
    ValidatorConfig, ValidatorInput,
)

# Layers are in central location: app/agents/tools/validator/
from app.agents.tools.validator.layers import (
    ValidationLayer, StructuralLayer, CompletenessLayer,
    DependencyLayer, ScopeLayer, TypeScriptLayer,
)


class Validator(BaseAgent):
    """
    Validator Agent - The Gate Before Execution.
    
    Uses Gemini 3 Flash for fast, precise, deterministic validation.
    
    Runs 4 validation layers IN ORDER:
    1. Structural: Did Coder obey Folder Map?
    2. Completeness: Are there TODOs/placeholders?
    3. Dependency: Do imports resolve?
    4. Scope: Does implementation match Blueprint?
    
    IF ANY LAYER FAILS, VALIDATION STOPS.
    
    Output is a HARD CONTRACT: pass | fail
    There is NO "warning-only" mode.
    """
    
    def __init__(
        self,
        artifact_manager: Optional[ArtifactManager] = None,
        config: Optional[ValidatorConfig] = None
    ):
        """
        Initialize the Validator.
        
        Args:
            artifact_manager: Optional artifact manager
            config: Validator configuration
        """
        super().__init__(
            name="Validator",
            agent_type="mini",  # Uses Flash model - boring, ruthless, cheap
            reasoning_level="standard",
            artifact_manager=artifact_manager
        )
        
        self.config = config or ValidatorConfig()
        
        # Initialize validation layers
        self.layers: List[ValidationLayer] = []
        
        if self.config.run_structural:
            self.layers.append(StructuralLayer(self.config))
        if self.config.run_completeness:
            self.layers.append(CompletenessLayer(self.config))
        if self.config.run_dependency:
            self.layers.append(DependencyLayer(self.config))
        if self.config.run_scope:
            self.layers.append(ScopeLayer(self.config))
        
        # TypeScript layer always runs for TS projects (auto-detects tsconfig)
        self.layers.append(TypeScriptLayer(self.config))
    
    def _get_system_prompt(self) -> str:
        """Get the system prompt for validation."""
        return """You are the Validator for ShipS*, an AI coding system that SHIPS WORKING CODE.

Your job is to answer ONE question only:
"Is the system safe to proceed?"

NOT: "Is this elegant?"
NOT: "Is this optimal?"
NOT: "Is this finished?"
ONLY: "Can the system move forward without lying?"

You are a GATE, not a helper.
You PASS or FAIL.
You do NOT negotiate.
You do NOT suggest improvements.

If you find ANY issue that would cause:
- Build failures
- Runtime errors
- Incomplete functionality
- Broken contracts

You MUST FAIL the validation.

Output ONLY: pass or fail, with specific violations if failing."""
    
    async def validate(
        self,
        file_change_set: Dict[str, Any],
        folder_map: Dict[str, Any],
        task: Optional[Dict[str, Any]] = None,
        app_blueprint: Optional[Dict[str, Any]] = None,
        dependency_plan: Optional[Dict[str, Any]] = None,
        task_id: str = "",
        plan_id: Optional[str] = None,
        project_path: Optional[str] = None
    ) -> ValidationReport:
        """
        Validate the Coder's output.
        
        This is the MAIN ENTRY POINT for validation.
        
        Runs all 4 layers IN ORDER. If any layer fails,
        validation STOPS and returns immediately.
        
        Args:
            file_change_set: The Coder's file changes
            folder_map: Expected folder structure
            task: Current task being validated
            app_blueprint: App context
            dependency_plan: Declared dependencies
            task_id: Task ID for traceability
            plan_id: Plan ID for traceability
            
        Returns:
            ValidationReport with pass/fail status
        """
        start = datetime.utcnow()
        
        # Build context for layers
        context = self._build_context(
            file_change_set=file_change_set,
            folder_map=folder_map,
            task=task,
            app_blueprint=app_blueprint,
            dependency_plan=dependency_plan,
            project_path=project_path
        )
        
        # Create report
        report = ValidationReport(
            status=ValidationStatus.PASS,
            failure_layer=FailureLayer.NONE,
            recommended_action=RecommendedAction.PROCEED,
            task_id=task_id,
            plan_id=plan_id,
            changeset_id=file_change_set.get("id", "")
        )
        
        # Run layers IN ORDER
        for layer in self.layers:
            layer_result = layer.validate(context)
            
            # Store result
            report.layer_results[layer.layer_name.value] = layer_result
            report.total_checks_run += layer_result.checks_run
            
            # Add violations
            for violation in layer_result.violations:
                report.add_violation(violation)
            
            # IF LAYER FAILS, STOP IMMEDIATELY
            if not layer_result.passed:
                report.status = ValidationStatus.FAIL
                report.failure_layer = layer.layer_name
                report.recommended_action = self._determine_action(layer_result)
                
                # Build fixer instructions
                report.fixer_instructions = self._build_fixer_instructions(layer_result)
                report.priority_violations = [
                    v.id for v in layer_result.violations 
                    if v.severity in [ViolationSeverity.CRITICAL, ViolationSeverity.MAJOR]
                ][:5]  # Top 5
                
                break  # STOP - no further layers run
        
        # Calculate confidence
        report.confidence = self._calculate_confidence(report)
        
        # Calculate duration
        report.duration_ms = int((datetime.utcnow() - start).total_seconds() * 1000)
        
        # Log action
        if self._artifact_manager:
            self.log_action(
                action="validation_complete",
                input_summary=f"{len(context.get('file_changes', []))} files",
                output_summary=f"{report.status.value}: {report.total_violations} violations",
                reasoning=f"Failed at layer: {report.failure_layer.value}" if report.status == ValidationStatus.FAIL else "All layers passed"
            )
        
        return report
    
    def _build_context(
        self,
        file_change_set: Dict[str, Any],
        folder_map: Dict[str, Any],
        task: Optional[Dict[str, Any]],
        app_blueprint: Optional[Dict[str, Any]],
        dependency_plan: Optional[Dict[str, Any]],
        project_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """Build context for validation layers."""
        # Extract file changes with content
        file_changes = []
        for change in file_change_set.get("changes", []):
            diff = change.get("diff", {})
            file_changes.append({
                "path": change.get("path", ""),
                "operation": change.get("operation", "add"),
                "content": diff.get("new_content", ""),
                "original_content": diff.get("original_content", "")
            })
        
        return {
            "file_changes": file_changes,
            "folder_map": folder_map,
            "current_task": task or {},
            "app_blueprint": app_blueprint or {},
            "dependency_plan": dependency_plan or {},
            "project_path": project_path or ""
        }
    
    def _determine_action(self, layer_result: LayerResult) -> RecommendedAction:
        """Determine recommended action based on failures."""
        violations = layer_result.violations
        
        # Check for critical violations
        critical = [v for v in violations if v.severity == ViolationSeverity.CRITICAL]
        
        if critical:
            # Check if recoverable
            structural_criticals = [v for v in critical if v.layer == FailureLayer.STRUCTURAL]
            if structural_criticals:
                # Can't fix structural issues easily - may need replan
                return RecommendedAction.REPLAN
            
            scope_criticals = [v for v in critical if v.layer == FailureLayer.SCOPE]
            if scope_criticals:
                # Scope issues may need user input
                return RecommendedAction.ASK_USER
            
            return RecommendedAction.FIX
        
        # Major violations can usually be fixed
        major = [v for v in violations if v.severity == ViolationSeverity.MAJOR]
        if major:
            return RecommendedAction.FIX
        
        # Minor violations - proceed but note
        return RecommendedAction.PROCEED
    
    def _build_fixer_instructions(self, layer_result: LayerResult) -> str:
        """Build instructions for the Fixer agent."""
        violations = layer_result.violations
        
        if not violations:
            return ""
        
        # Group by type
        by_rule = {}
        for v in violations:
            rule = v.rule
            if rule not in by_rule:
                by_rule[rule] = []
            by_rule[rule].append(v)
        
        parts = [f"Fix {len(violations)} violations in layer: {layer_result.layer.value}"]
        
        for rule, vlist in by_rule.items():
            parts.append(f"\n{rule}: {len(vlist)} violations")
            for v in vlist[:3]:  # Show first 3
                parts.append(f"  - {v.file_path}: {v.message[:50]}")
                if v.fix_hint:
                    parts.append(f"    Fix: {v.fix_hint}")
        
        return "\n".join(parts)
    
    def _calculate_confidence(self, report: ValidationReport) -> float:
        """Calculate validator confidence in the result."""
        confidence = 1.0
        
        # Lower confidence if many checks
        if report.total_checks_run > 100:
            confidence -= 0.1
        
        # Lower confidence if close to threshold
        if report.total_violations > 0 and report.status == ValidationStatus.PASS:
            confidence -= 0.1
        
        # Higher confidence for clean pass
        if report.status == ValidationStatus.PASS and report.total_violations == 0:
            confidence = 1.0
        
        return max(0.0, min(1.0, confidence))
    
    async def validate_quick(
        self,
        file_changes: List[Dict[str, Any]],
        folder_map: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Quick validation - just pass/fail, no report.
        
        Useful for pre-flight checks.
        """
        report = await self.validate(
            file_change_set={"changes": [{"path": f.get("path", ""), "diff": {"new_content": f.get("content", "")}} for f in file_changes]},
            folder_map=folder_map or {}
        )
        return report.status == ValidationStatus.PASS
    
    async def invoke(self, state: AgentState) -> Dict[str, Any]:
        """
        Invoke the Validator as part of orchestrator workflow.
        
        Args:
            state: Current agent state
            
        Returns:
            Dict with 'validation_report' artifact
        """
        artifacts = state.get("artifacts", {})
        parameters = state.get("parameters", {})
        
        # Get required artifacts
        file_change_set = artifacts.get("file_change_set", {})
        folder_map = artifacts.get("folder_map", {})
        current_task = artifacts.get("current_task") or parameters.get("task")
        app_blueprint = artifacts.get("app_blueprint")
        dependency_plan = artifacts.get("dependency_plan")
        
        # Validate
        report = await self.validate(
            file_change_set=file_change_set,
            folder_map=folder_map,
            task=current_task,
            app_blueprint=app_blueprint,
            dependency_plan=dependency_plan,
            task_id=parameters.get("task_id", ""),
            plan_id=parameters.get("plan_id")
        )
        
        return {
            "artifacts": {
                "validation_report": report.model_dump()
            },
            "status": report.status.value,
            "passed": report.status == ValidationStatus.PASS,
            "failure_layer": report.failure_layer.value,
            "recommended_action": report.recommended_action.value,
            "violation_count": report.total_violations
        }
