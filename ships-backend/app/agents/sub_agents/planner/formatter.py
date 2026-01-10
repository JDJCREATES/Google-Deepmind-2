"""
Artifact Formatter
Converts Planner artifacts (Pydantic models) into human-readable Markdown files
that are compatible with the frontend Artifact Viewer.

Outputs the full 19-section ShipS* implementation plan template.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime


def format_implementation_plan(artifacts: Dict[str, Any], project_name: str = "Project") -> str:
    """
    Format implementation plan as a LEAN DESIGN DOCUMENT.
    
    This should NOT duplicate content from JSON artifacts:
    - task_list.json → Tasks
    - folder_map.json → File structure
    - dependency_plan.json → Dependencies
    - api_contracts.json → API endpoints
    
    Instead, it provides:
    - High-level summary and design decisions
    - Architecture overview
    - References to detailed JSON artifacts
    """
    try:
        manifest = _to_dict(artifacts.get("plan_manifest", {}))
        task_list = _to_dict(artifacts.get("task_list", {}))
        folder_map = _to_dict(artifacts.get("folder_map", {}))
        dep_data = _to_dict(artifacts.get("dependency_plan", {}))
        assumptions = _to_dict(manifest.get("assumptions", {}))
        
        md = []
        
        # === Header ===
        summary = manifest.get("summary", project_name)
        version = manifest.get("version", "1.0.0")
        timestamp = datetime.utcnow().isoformat() + "Z"
        
        md.append(f"# {summary}")
        md.append(f"**Version**: {version} | **Updated**: {timestamp}")
        md.append("")
        
        # === Summary ===
        description = manifest.get("detailed_description", "")
        if description:
            md.append(description)
            md.append("")
        
        # === Tech Stack (concise) ===
        md.append("## Tech Stack")
        stack_items = []
        if assumptions.get("framework"):
            stack_items.append(f"**Framework**: {assumptions['framework']}")
        if assumptions.get("styling"):
            stack_items.append(f"**Styling**: {assumptions['styling']}")
        if assumptions.get("state_management"):
            stack_items.append(f"**State**: {assumptions['state_management']}")
        
        # Also check runtime deps for key libraries
        runtime_deps = dep_data.get("runtime_dependencies", [])
        key_libs = [d.get("name") for d in runtime_deps if d.get("name") in 
                   ["framer-motion", "zustand", "react-query", "axios", "lucide-react"]]
        if key_libs:
            stack_items.append(f"**Key Libraries**: {', '.join(key_libs)}")
        
        if stack_items:
            md.append(" | ".join(stack_items))
        else:
            md.append("React + TypeScript + TailwindCSS")
        md.append("")
        
        # === Architecture (only if there are interesting decisions) ===
        decision_notes = manifest.get("decision_notes", [])
        if decision_notes:
            md.append("## Architecture Decisions")
            for note in decision_notes[:5]:  # Max 5 decisions
                md.append(f"- {note}")
            md.append("")
        
        # === Project Structure Summary (reference to folder_map.json) ===
        entries = folder_map.get("entries", [])
        if entries:
            md.append("## Project Structure")
            # Show top-level directories only
            dirs = sorted(set(
                e.get("path", "").split("/")[0] 
                for e in entries 
                if "/" in e.get("path", "") and not e.get("path", "").startswith(".")
            ))
            if dirs:
                md.append("```")
                for d in dirs[:8]:  # Max 8 top-level dirs
                    md.append(f"├── {d}/")
                md.append("```")
            md.append(f"*Full structure: See `folder_map.json` ({len(entries)} files)*")
            md.append("")
        
        # === Tasks Summary (reference to task_list.json) ===
        tasks = task_list.get("tasks", [])
        if tasks:
            md.append("## Implementation Tasks")
            completed = sum(1 for t in tasks if t.get("status") == "completed")
            in_progress = sum(1 for t in tasks if t.get("status") == "in_progress")
            pending = sum(1 for t in tasks if t.get("status") == "pending")
            
            md.append(f"**Progress**: {completed}/{len(tasks)} complete")
            if in_progress > 0:
                md.append(f" | {in_progress} in progress")
            md.append("")
            
            # Show first 3 tasks as preview
            for task in tasks[:3]:
                status_icon = {"completed": "✅", "in_progress": "🔄", "pending": "⬜"}.get(
                    task.get("status", "pending"), "⬜"
                )
                md.append(f"- {status_icon} {task.get('title', 'Untitled')}")
            
            if len(tasks) > 3:
                md.append(f"- ... and {len(tasks) - 3} more tasks")
            md.append("")
            md.append("*Full task list: See `task_list.json`*")
            md.append("")
        
        # === Dependencies Summary ===
        runtime = dep_data.get("runtime_dependencies", [])
        dev = dep_data.get("dev_dependencies", [])
        if runtime or dev:
            md.append("## Dependencies")
            md.append(f"**Runtime**: {len(runtime)} packages | **Dev**: {len(dev)} packages")
            md.append("")
            md.append("*Full list: See `dependency_plan.json`*")
            md.append("")
        
        return "\n".join(md)
        
    except Exception as e:
        return f"# Error formatting plan\nDetails: {str(e)}"


def _to_dict(obj: Any) -> Dict[str, Any]:
    """Convert Pydantic model or dict to dict."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    return obj if isinstance(obj, dict) else {}


def format_task_list(task_list_data: Dict[str, Any]) -> str:
    """Format task list into task.md checklist."""
    try:
        data = _to_dict(task_list_data)
        tasks = data.get("tasks", [])
        
        md = ["# Task Checklist\n"]
        
        # Sort by order
        sorted_tasks = sorted(tasks, key=lambda x: x.get("order", 999))
        
        for task in sorted_tasks:
            title = task.get("title", "")
            status = task.get("status", "pending")
            task_id = task.get("id", "")
            
            # Checkbox state
            checkbox = "[ ]"
            if status == "completed": checkbox = "[x]"
            elif status == "in_progress": checkbox = "[/]"
            elif status == "blocked": checkbox = "[-]"
            
            md.append(f"- {checkbox} **{task_id}**: {title}")
            
            # Acceptance criteria as sub-items
            for criterion in task.get("acceptance_criteria", []):
                c_data = _to_dict(criterion)
                # Prefer Gherkin format
                given = c_data.get("given")
                when = c_data.get("when")
                then = c_data.get("then")
                if given and when and then:
                    md.append(f"  - [ ] Given {given}, When {when}, Then {then}")
                elif c_data.get("description"):
                    md.append(f"  - [ ] {c_data.get('description')}")
                    
        return "\n".join(md)
        
    except Exception as e:
        return f"# Error formatting task list\nDetails: {str(e)}"


def format_folder_map(folder_map_data: Dict[str, Any]) -> str:
    """Format FolderMap to Markdown with immutability flags."""
    try:
        data = _to_dict(folder_map_data)
        entries = data.get("entries", [])
        
        md = ["# Project Folder Structure\n"]
        
        # Sort by path
        sorted_entries = sorted(entries, key=lambda x: x.get("path", ""))
        
        for entry in sorted_entries:
            path = entry.get("path", "")
            desc = entry.get("description", "")
            is_dir = entry.get("is_directory", False)
            is_immutable = entry.get("is_immutable", False)
            owner = entry.get("owner_task_id", "")
            
            icon = "📁" if is_dir else "📄"
            flags = []
            if is_immutable: flags.append("🔒")
            if owner: flags.append(f"→ {owner}")
            flag_str = " ".join(flags)
            
            md.append(f"- {icon} `{path}` {flag_str}")
            if desc:
                md.append(f"  {desc}")
                
        return "\n".join(md)
        
    except Exception as e:
        return f"# Error formatting folder map\nDetails: {str(e)}"


def format_api_contracts(api_data: Dict[str, Any]) -> str:
    """Format APIContracts to Markdown."""
    try:
        data = _to_dict(api_data)
        endpoints = data.get("endpoints", [])
        
        md = ["# API Contracts\n"]
        
        for ep in endpoints:
            ep = _to_dict(ep)
            method = ep.get("method", "GET")
            path = ep.get("path", "/")
            desc = ep.get("description", "")
            
            md.append(f"## {method} {path}")
            if desc:
                md.append(f"{desc}\n")
            
            # Query params
            query_params = ep.get("query_params", [])
            if query_params:
                md.append("### Query Parameters")
                for p in query_params:
                    p = _to_dict(p)
                    md.append(f"- `{p.get('name')}` ({p.get('type', 'string')}): {p.get('description', '')}")
                md.append("")
            
            # Request body
            request_schema = ep.get("request_schema", {})
            if request_schema:
                md.append("### Request Body")
                for f in request_schema.get("fields", []):
                    f = _to_dict(f)
                    req = "required" if f.get("required", True) else "optional"
                    md.append(f"- `{f.get('name')}` ({f.get('type', 'string')}, {req})")
                md.append("")
            
            # Response
            success_response = ep.get("success_response", {})
            if success_response:
                md.append("### Success Response")
                status = success_response.get("status_code", 200)
                md.append(f"**Status**: {status}")
                for f in success_response.get("fields", []):
                    f = _to_dict(f)
                    md.append(f"- `{f.get('name')}` ({f.get('type', 'string')})")
                md.append("")
            
            md.append("---\n")
            
        return "\n".join(md)
        
    except Exception as e:
        return f"# Error formatting API contracts\nDetails: {str(e)}"


def format_dependency_plan(dep_data: Dict[str, Any]) -> str:
    """Format DependencyPlan to Markdown."""
    try:
        data = _to_dict(dep_data)
        
        md = ["# Dependency Plan\n"]
        
        # Package Manager
        pm = data.get("package_manager", "npm")
        md.append(f"**Package Manager**: `{pm}`\n")
        
        # Runtime dependencies
        runtime = data.get("runtime_dependencies", [])
        if runtime:
            md.append("## Runtime Dependencies")
            for dep in runtime:
                dep = _to_dict(dep)
                name = dep.get("name", "")
                ver = dep.get("version", "latest")
                purpose = dep.get("purpose", "")
                md.append(f"- `{name}@{ver}`: {purpose}")
            md.append("")
        
        # Dev dependencies
        dev = data.get("dev_dependencies", [])
        if dev:
            md.append("## Dev Dependencies")
            for dep in dev:
                dep = _to_dict(dep)
                name = dep.get("name", "")
                ver = dep.get("version", "latest")
                purpose = dep.get("purpose", "")
                md.append(f"- `{name}@{ver}`: {purpose}")
            md.append("")
        
        # Commands
        commands = data.get("commands", [])
        if commands:
            md.append("## Scripts")
            for cmd in commands:
                cmd = _to_dict(cmd)
                name = cmd.get("name", "")
                command = cmd.get("command", "")
                desc = cmd.get("description", "")
                md.append(f"- **{name}**: `{command}` — {desc}")
            md.append("")
        
        return "\n".join(md)
        
    except Exception as e:
        return f"# Error formatting dependency plan\nDetails: {str(e)}"


def format_repo_profile(repo_data: Dict[str, Any]) -> str:
    """Format RepoProfile to Markdown."""
    try:
        data = _to_dict(repo_data)
        
        md = ["# Repository Profile\n"]
        
        # Discovery summary
        is_empty = data.get("is_empty_project", False)
        approach = data.get("suggested_approach", "scaffold")
        md.append(f"**Project Status**: {'Empty' if is_empty else 'Existing code found'}")
        md.append(f"**Suggested Approach**: {approach}\n")
        
        # Versions
        md.append("## Detected Versions")
        md.append(f"- Node: {data.get('node_version', 'N/A')}")
        md.append(f"- Python: {data.get('python_version', 'N/A')}")
        md.append(f"- Package Manager: {data.get('package_manager', 'N/A')}")
        md.append(f"- Framework: {data.get('framework', 'N/A')}")
        md.append(f"- Test Runner: {data.get('test_runner', 'N/A')}")
        md.append("")
        
        # Patterns
        patterns = data.get("patterns", [])
        if patterns:
            md.append("## Detected Patterns")
            for p in patterns:
                p = _to_dict(p)
                ptype = p.get("pattern_type", "")
                value = p.get("value", "")
                md.append(f"- **{ptype}**: {value}")
            md.append("")
        
        # Reuse candidates
        candidates = data.get("reuse_candidates", [])
        if candidates:
            md.append("## Reuse Candidates")
            for c in candidates:
                c = _to_dict(c)
                path = c.get("path", "")
                reusability = c.get("reusability", "reuse")
                md.append(f"- `{path}` → {reusability}")
            md.append("")
        
        # Conflicts
        conflicts = data.get("conflicts", [])
        if conflicts:
            md.append("## Conflicts with Plan")
            for conf in conflicts:
                conf = _to_dict(conf)
                cat = conf.get("category", "")
                existing = conf.get("existing_value", "")
                planned = conf.get("planned_value", "")
                severity = conf.get("severity", "medium")
                md.append(f"- **{cat}** ({severity}): existing=`{existing}`, planned=`{planned}`")
            md.append("")
        
        return "\n".join(md)
        
    except Exception as e:
        return f"# Error formatting repo profile\nDetails: {str(e)}"
