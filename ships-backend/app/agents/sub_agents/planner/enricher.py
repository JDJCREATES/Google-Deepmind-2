"""
Plan Enricher Component.

Responsible for enriching domain models (TaskList, FolderMap, etc.) with insights 
from the LLM's structured output. This separates data transformation logic from 
the core agent orchestration.
"""

from typing import Dict, Any, List
import logging

from app.agents.sub_agents.planner.models import (
    TaskList, FolderMap, APIContracts, DependencyPlan, RiskReport,
    Task, TaskComplexity, TaskPriority, FolderEntry, FileRole,
    APIEndpoint, HTTPMethod, PackageDependency, RiskItem, RiskLevel,
    AcceptanceCriterion
)

logger = logging.getLogger("ships.planner.enricher")

class PlanEnricher:
    """
    Enriches domain models with LLM plan data.
    Acts as a mapper/translator between LLM DTOs and ShipS* Domain Models.
    """
    
    def enrich_task_list(self, task_list: TaskList, llm_plan: Dict[str, Any]) -> None:
        """Enrich task list with LLM insights."""
        llm_tasks = llm_plan.get("tasks", [])
        for llm_task in llm_tasks:
            # Find matching task or create new
            title = llm_task.get("title", "")
            existing = next((t for t in task_list.tasks if title.lower() in t.title.lower()), None)
            
            if existing:
                # Enrich existing task
                if llm_task.get("acceptance_criteria"):
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
    
    def enrich_folder_map(self, folder_map: FolderMap, llm_plan: Dict[str, Any]) -> None:
        """Enrich folder map with LLM insights - folders AND files from tasks."""
        existing_paths = {e.path for e in folder_map.entries}
        
        # 1. Add folders from LLM 'folders' array
        llm_folders = llm_plan.get("folders", [])
        for folder in llm_folders:
            path = folder.get("path", "")
            if path and path not in existing_paths:
                folder_map.entries.append(FolderEntry(
                    path=path,
                    is_directory=folder.get("is_directory", True),
                    description=folder.get("description", "")
                ))
                existing_paths.add(path)
        
        # 2. Extract FILES from tasks' expected_outputs
        llm_tasks = llm_plan.get("tasks", [])
        for task in llm_tasks:
            outputs = task.get("expected_outputs", [])
            for output in outputs:
                # output can be {"path": "src/...", "type": "file"} or just a string
                if isinstance(output, dict):
                    file_path = output.get("path", "")
                elif isinstance(output, str):
                    file_path = output
                else:
                    continue
                    
                if file_path and file_path not in existing_paths:
                    folder_map.entries.append(FolderEntry(
                        path=file_path,
                        is_directory=False,  # These are FILES
                        description=f"From task: {task.get('title', 'Unknown')}"
                    ))
                    existing_paths.add(file_path)
    
    def enrich_api_contracts(self, api_contracts: APIContracts, llm_plan: Dict[str, Any]) -> None:
        """Enrich API contracts with LLM insights."""
        llm_endpoints = llm_plan.get("api_endpoints", [])
        existing_paths = {e.path for e in api_contracts.endpoints}
        
        for endpoint in llm_endpoints:
            path = endpoint.get("path", "")
            if path and path not in existing_paths:
                api_contracts.endpoints.append(APIEndpoint(
                    path=path,
                    method=HTTPMethod(endpoint.get("method", "GET")),
                    description=endpoint.get("description", "")
                ))
    
    def enrich_dependencies(self, dependency_plan: DependencyPlan, llm_plan: Dict[str, Any]) -> None:
        """Enrich dependencies with LLM insights."""
        llm_deps = llm_plan.get("dependencies", {})
        existing_names = {d.name for d in dependency_plan.runtime_dependencies}
        
        for dep in llm_deps.get("runtime", []):
            name = dep.get("name", "")
            if name and name not in existing_names:
                dependency_plan.runtime_dependencies.append(PackageDependency(
                    name=name,
                    version=dep.get("version", "latest")
                ))
    
    def enrich_risks(self, risk_report: RiskReport, llm_plan: Dict[str, Any]) -> None:
        """Enrich risk report with LLM insights."""
        llm_risks = llm_plan.get("risks", [])
        
        for risk in llm_risks:
            risk_report.add_risk(RiskItem(
                title=risk.get("title", "Risk"),
                risk_level=RiskLevel(risk.get("level", "medium")),
                mitigation=risk.get("mitigation", "")
            ))
        
        # Add clarifying questions
        questions = llm_plan.get("clarifying_questions", [])
        if questions:
            risk_report.add_risk(RiskItem(
                title="Clarifications Needed",
                category="unknown",
                requires_human_input=True,
                clarifying_questions=questions
            ))
