"""
ShipS* Planner Tool Functions

Helper functions for the Planner agent.
These include artifact assembly, project analysis, and validation utilities.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime

from app.agents.sub_agents.planner.models import (
    PlanManifest, TaskList, FolderMap, APIContracts,
    DependencyPlan, ValidationChecklist, RiskReport,
    ArtifactReference, ArtifactMetadata,
)


class PlannerTools:
    """
    Tools available to the Planner agent.
    
    These are non-LLM operations that help assemble and validate
    the plan artifacts.
    """
    
    @staticmethod
    def assemble_plan_manifest(
        intent_spec_id: str,
        summary: str,
        task_list: TaskList,
        folder_map: FolderMap,
        api_contracts: APIContracts,
        dependency_plan: DependencyPlan,
        validation_checklist: ValidationChecklist,
        risk_report: RiskReport
    ) -> PlanManifest:
        """
        Assemble all artifacts into a PlanManifest.
        
        Args:
            All produced artifacts
            
        Returns:
            Complete PlanManifest
        """
        manifest = PlanManifest(
            intent_spec_id=intent_spec_id,
            summary=summary,
            metadata=ArtifactMetadata(intent_spec_id=intent_spec_id)
        )
        
        # Add artifact references
        manifest.artifacts = [
            ArtifactReference(artifact_type="task_list", artifact_id="task_list"),
            ArtifactReference(artifact_type="folder_map", artifact_id="folder_map"),
            ArtifactReference(artifact_type="api_contracts", artifact_id="api_contracts"),
            ArtifactReference(artifact_type="dependency_plan", artifact_id="dependency_plan"),
            ArtifactReference(artifact_type="validation_checklist", artifact_id="validation_checklist"),
            ArtifactReference(artifact_type="risk_report", artifact_id="risk_report"),
        ]
        
        # Update stats
        manifest.total_tasks = len(task_list.tasks)
        manifest.estimated_total_minutes = task_list.total_estimated_minutes
        manifest.blocked_tasks = task_list.blocked_task_count
        
        # Get top priority tasks
        ready_tasks = task_list.get_ready_tasks()
        priority_tasks = task_list.get_by_priority()
        manifest.top_priority_tasks = [t.id for t in priority_tasks[:3]]
        
        # Check for blockers
        if risk_report.has_blockers:
            manifest.is_blocked = True
            manifest.blocking_reasons = [r.title for r in risk_report.risks if r.requires_human_input]
            manifest.clarifying_questions = []
            for risk in risk_report.risks:
                manifest.clarifying_questions.extend(risk.clarifying_questions)
            manifest.recommended_next_agent = "planner"  # Re-run after clarification
        else:
            manifest.is_complete = True
            manifest.recommended_next_agent = "coder"
        
        return manifest
    
    @staticmethod
    def validate_task_list(task_list: TaskList) -> Dict[str, Any]:
        """
        Validate a task list for common issues.
        
        Returns:
            Dict with 'valid', 'issues', 'warnings'
        """
        issues = []
        warnings = []
        
        # Check for empty task list
        if not task_list.tasks:
            issues.append("Task list is empty")
        
        # Check for tasks without acceptance criteria
        for task in task_list.tasks:
            if not task.acceptance_criteria:
                warnings.append(f"Task '{task.title}' has no acceptance criteria")
        
        # Check for circular dependencies
        task_ids = {t.id for t in task_list.tasks}
        for task in task_list.tasks:
            for dep in task.dependencies:
                if dep.task_id not in task_ids:
                    issues.append(f"Task '{task.title}' has unknown dependency: {dep.task_id}")
        
        # Check for oversized tasks
        large_tasks = [t for t in task_list.tasks if t.estimated_minutes > 240]
        if large_tasks:
            warnings.append(f"{len(large_tasks)} task(s) exceed 4 hours, consider decomposition")
        
        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings
        }
    
    @staticmethod
    def detect_framework(context: Dict[str, Any]) -> str:
        """
        Detect framework from context or app blueprint.
        
        Returns:
            Framework name (react, nextjs, fastapi, etc.)
        """
        blueprint = context.get("app_blueprint", {})
        
        # Check blueprint
        tech_stack = blueprint.get("tech_stack", {})
        frontend = tech_stack.get("frontend", "")
        backend = tech_stack.get("backend", "")
        
        if "next" in frontend.lower():
            return "nextjs"
        elif "react" in frontend.lower():
            return "react"
        elif "fastapi" in backend.lower():
            return "fastapi"
        elif "flask" in backend.lower():
            return "flask"
        elif "django" in backend.lower():
            return "django"
        
        # Default to React
        return "react"
    
    @staticmethod
    def estimate_confidence(artifacts: Dict[str, Any]) -> float:
        """
        Calculate overall plan confidence.
        
        Lower confidence if:
        - Many inferred items
        - Ambiguous intent
        - Missing information
        """
        confidence = 1.0
        
        # Check risk report
        risk_report = artifacts.get("risk_report")
        if risk_report and hasattr(risk_report, 'high_risk_count'):
            confidence -= risk_report.high_risk_count * 0.1
        
        # Check for blockers
        if risk_report and hasattr(risk_report, 'has_blockers') and risk_report.has_blockers:
            confidence -= 0.2
        
        return max(0.0, min(1.0, confidence))
    
    @staticmethod
    def analyze_project_for_scaffolding(
        project_path: Optional[str], 
        user_request: str = ""
    ) -> Dict[str, Any]:
        """
        Analyze project to determine if scaffolding is needed.
        
        Args:
            project_path: Path to the project directory
            user_request: The user's request (for framework hints)
            
        Returns:
            Dict with:
            - needs_scaffolding: bool
            - scaffolding_task: Optional task dict
            - analysis: Full analysis result
        """
        from app.agents.sub_agents.planner.project_analyzer import (
            analyze_project, 
            create_scaffolding_task
        )
        
        if not project_path:
            return {
                "needs_scaffolding": False,
                "scaffolding_task": None,
                "analysis": None,
                "error": "No project path provided"
            }
        
        analysis = analyze_project(project_path, user_request)
        scaffolding_task = create_scaffolding_task(analysis)
        
        return {
            "needs_scaffolding": analysis.needs_scaffolding,
            "scaffolding_task": scaffolding_task,
            "analysis": {
                "project_type": analysis.project_type.value,
                "detected_framework": analysis.detected_framework,
                "has_package_json": analysis.has_package_json,
                "has_node_modules": analysis.has_node_modules,
                "scaffold_command": analysis.scaffold_command,
                "install_command": analysis.install_command,
                "recommendation": analysis.recommendation,
            }
        }
