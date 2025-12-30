"""
Artifact Formatter
Converts Planner artifacts (Pydantic models) into human-readable Markdown files
that are compatible with the frontend Artifact Viewer.
"""

from typing import Dict, Any, List
from datetime import datetime
from app.agents.sub_agents.planner.models import (
    PlanManifest, TaskList, FolderMap, APIContracts,
    DependencyPlan, ValidationChecklist, RiskReport
)

def format_implementation_plan(artifacts: Dict[str, Any]) -> str:
    """
    Format generic artifacts dict into implementation_plan.md
    """
    # Extract sub-models
    try:
        manifest_data = artifacts.get("plan_manifest", {})
        task_list_data = artifacts.get("task_list", {})
        folder_map_data = artifacts.get("folder_map", {})
        api_data = artifacts.get("api_contracts", {})
        dep_data = artifacts.get("dependency_plan", {})
        test_data = artifacts.get("validation_checklist", {})
        risk_data = artifacts.get("risk_report", {})
        
        # We assume the caller passed model_dump() output, but handle objects too just in case
        if hasattr(manifest_data, "model_dump"): manifest_data = manifest_data.model_dump()
        if hasattr(task_list_data, "model_dump"): task_list_data = task_list_data.model_dump()
        if hasattr(folder_map_data, "model_dump"): folder_map_data = folder_map_data.model_dump()
        if hasattr(api_data, "model_dump"): api_data = api_data.model_dump()
        if hasattr(dep_data, "model_dump"): dep_data = dep_data.model_dump()
        if hasattr(test_data, "model_dump"): test_data = test_data.model_dump()
        if hasattr(risk_data, "model_dump"): risk_data = risk_data.model_dump()

        md = []
        
        # Header
        summary = manifest_data.get("summary", "Implementation Plan")
        md.append(f"# {summary}\n")
        
        desc = manifest_data.get("detailed_description", "")
        if desc:
            md.append(f"{desc}\n")
            
        # User Review Required
        risks = risk_data.get("risks", [])
        blockers = [r for r in risks if r.get("requires_human_input") or r.get("requires_external_approval")]
        high_risks = [r for r in risks if r.get("risk_level") in ["high", "critical"]]
        
        if blockers or high_risks:
            md.append("## User Review Required\n")
            for blocker in blockers:
                md.append(f"> [!IMPORTANT]\n> **{blocker.get('title')}**: {blocker.get('mitigation')}\n")
            for risk in high_risks:
                if risk not in blockers:
                    md.append(f"> [!WARNING]\n> **{risk.get('title')}**: {risk.get('mitigation')}\n")
            md.append("")

        # Proposed Changes (Folder Map)
        md.append("## Proposed Changes\n")
        entries = folder_map_data.get("entries", [])
        
        # Group by folder (naive grouping)
        # Or just list files with [NEW]/[MODIFY]
        # Let's try to infer component groups if possible, otherwise flat list is okay
        # Implementation Plan format expects Component groupings
        
        # Simple clustering by top-level dir
        components = {}
        for entry in entries:
            path = entry.get("path", "")
            if "/" in path:
                root = path.split("/")[0] if not path.startswith("src/") else path.split("/")[1]
            else:
                root = "root"
            
            if root not in components: components[root] = []
            components[root].append(entry)
            
        for comp_name, comp_entries in components.items():
            if not comp_entries: continue
            md.append(f"### {comp_name.capitalize()}\n")
            for entry in comp_entries:
                path = entry.get("path")
                action = entry.get("action", "create").upper()
                desc = entry.get("description", "")
                
                # Format: #### [MODIFY] [file basename](file:///absolute/path/to/modifiedfile)
                # We don't have abs path easily here without project root context
                # So we just use relative path in link default
                
                icon = "NEW" if action == "CREATE" else action
                md.append(f"#### [{icon}] [{path}](file:///{path})\n{desc}\n")
            
            md.append("---\n") # Horizontal rule

        # API Contracts
        endpoints = api_data.get("endpoints", [])
        if endpoints:
            md.append("## API Contract\n")
            for ep in endpoints:
                method = ep.get("method", "GET")
                path = ep.get("path", "/")
                desc = ep.get("description", "")
                md.append(f"- **{method}** `{path}`: {desc}")
            md.append("")

        # Dependencies
        pkgs = dep_data.get("runtime_dependencies", [])
        if pkgs:
            md.append("## Dependencies\n")
            for pkg in pkgs:
                name = pkg.get("name")
                ver = pkg.get("version", "latest")
                purpose = pkg.get("purpose", "")
                md.append(f"- `{name}@{ver}`: {purpose}")
            md.append("")

        # Verification Plan
        md.append("## Verification Plan\n")
        
        # Automated
        md.append("### Automated Tests")
        checks = test_data.get("unit_checks", []) + test_data.get("integration_checks", [])
        if checks:
            for check in checks:
                cmd = check.get("command", "npm test")
                assertion = check.get("assertion", "")
                md.append(f"- Run `{cmd}` to verify: {assertion}")
        else:
            md.append("- Run standard test suite")
        md.append("")
        
        # Manual
        md.append("### Manual Verification")
        manual = test_data.get("manual_checks", [])
        if manual:
            for check in manual:
                 md.append(f"- {check.get('assertion')}")
        else:
            md.append("- Inspect UI for visual correctness")
            
        return "\n".join(md)
        
    except Exception as e:
        return f"# Error formatting plan\nDetails: {str(e)}"

def format_task_list(task_list_data: Dict[str, Any]) -> str:
    """
    Format task list into task.md checklist
    """
    try:
        tasks = task_list_data.get("tasks", [])
        
        # We assume the caller passed model_dump() output
        if hasattr(task_list_data, "model_dump"): 
             # Re-fetch if it was a model object
             tasks = task_list_data.tasks
             # Convert tasks to dicts if needed
             if tasks and hasattr(tasks[0], "model_dump"):
                 tasks = [t.model_dump() for t in tasks]

        md = []
        md.append("# Task Checklist\n")
        
        # Sort by order
        try:
             sorted_tasks = sorted(tasks, key=lambda x: x.get("order", 999))
        except:
             sorted_tasks = tasks
             
        for task in sorted_tasks:
            title = task.get("title", "")
            status = task.get("status", "pending")
            
            # Checkbox state
            box = "[ ]"
            if status == "completed": box = "[x]"
            elif status == "in_progress": box = "[/]"
            elif status == "failed": box = "[-]"
            
            md.append(f"- {box} {title}")
            
            # Sub-items (acceptance criteria)
            criteria = task.get("acceptance_criteria", [])
            for c in criteria:
                c_desc = c.get("description", "") if isinstance(c, dict) else str(c)
                md.append(f"  - [ ] {c_desc}")
                
        return "\n".join(md)
        
    except Exception as e:
        return f"# Error formatting task list\nDetails: {str(e)}"

def format_folder_map(folder_map_data: Dict[str, Any]) -> str:
    """Format FolderMap to Markdown."""
    try:
        entries = folder_map_data.get("entries", [])
        if hasattr(folder_map_data, "model_dump"): entries = folder_map_data.entries
        
        md = ["# Project Folder Structure\n"]
        
        # Sort by path
        sorted_entries = sorted(entries, key=lambda x: x.get("path", "") if isinstance(x, dict) else x.path)
        
        for entry in sorted_entries:
            path = entry.get("path") if isinstance(entry, dict) else entry.path
            desc = entry.get("description", "") if isinstance(entry, dict) else entry.description
            is_dir = entry.get("is_directory") if isinstance(entry, dict) else entry.is_directory
            
            icon = "📁" if is_dir else "📄"
            md.append(f"- {icon} `{path}`: {desc}")
            
        return "\n".join(md)
    except Exception as e:
        return f"# Error formatting folder map\nDetails: {str(e)}"

def format_api_contracts(api_data: Dict[str, Any]) -> str:
    """Format APIContracts to Markdown."""
    try:
        endpoints = api_data.get("endpoints", [])
        if hasattr(api_data, "model_dump"): endpoints = api_data.endpoints
        
        md = ["# API Contracts\n"]
        
        for ep in endpoints:
            if hasattr(ep, "model_dump"): ep = ep.model_dump()
            
            method = ep.get("method", "GET")
            path = ep.get("path", "/")
            desc = ep.get("description", "")
            
            md.append(f"## {method} {path}")
            md.append(f"{desc}\n")
            
            # Request
            if ep.get("query_params"):
                md.append("### Query Params")
                for p in ep.get("query_params", []):
                    md.append(f"- `{p.get('name')}` ({p.get('type')}): {p.get('description')}")
                md.append("")
                
            if ep.get("request_schema"):
                md.append("### Request Body")
                fields = ep.get("request_schema", {}).get("fields", [])
                for f in fields:
                    md.append(f"- `{f.get('name')}` ({f.get('type')}): {f.get('description')}")
                md.append("")
                
            # Response
            success = ep.get("success_response")
            if success:
                md.append("### Success Response")
                fields = success.get("fields", [])
                for f in fields:
                    md.append(f"- `{f.get('name')}` ({f.get('type')}): {f.get('description')}")
                md.append("")
                
            md.append("---\n")
            
        return "\n".join(md)
    except Exception as e:
        return f"# Error formatting API contracts\nDetails: {str(e)}"

def format_dependency_plan(dep_data: Dict[str, Any]) -> str:
    """Format DependencyPlan to Markdown."""
    try:
        if hasattr(dep_data, "model_dump"): dep_data = dep_data.model_dump()
        
        md = ["# Dependency Plan\n"]
        
        # Package Manager
        pm = dep_data.get("package_manager", "npm")
        md.append(f"**Package Manager**: `{pm}`\n")
        
        # Runtime
        runtime = dep_data.get("runtime_dependencies", [])
        if runtime:
            md.append("## Runtime Dependencies")
            for dep in runtime:
                md.append(f"- `{dep.get('name')}@{dep.get('version')}`: {dep.get('purpose')}")
            md.append("")
            
        # Dev
        dev = dep_data.get("dev_dependencies", [])
        if dev:
            md.append("## Dev Dependencies")
            for dep in dev:
                md.append(f"- `{dep.get('name')}@{dep.get('version')}`: {dep.get('purpose')}")
            md.append("")
            
        # Commands
        cmds = dep_data.get("commands", [])
        if cmds:
            md.append("## Commands")
            for cmd in cmds:
                md.append(f"- **{cmd.get('name')}**: `{cmd.get('command')}` - {cmd.get('description')}")
                
        return "\n".join(md)
    except Exception as e:
        return f"# Error formatting dependency plan\nDetails: {str(e)}"
