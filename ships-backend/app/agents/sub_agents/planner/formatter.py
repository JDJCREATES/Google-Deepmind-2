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
    Format implementation plan as an EXECUTION OVERVIEW.
    
    Antigravity-style: This is a human-readable document that explains
    WHAT the agents are about to do, WHY, and provides predictable checkpoints.
    
    The user should be able to read this and understand:
    - What will be created/modified
    - Key architectural decisions
    - Agent workflow (Planner → Coder → Validator)
    - How to verify success
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
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        
        md.append(f"# 🚀 Execution Plan: {summary}")
        md.append(f"*Generated: {timestamp}*")
        md.append("")
        
        # === What We're Building ===
        description = manifest.get("detailed_description", "")
        if description:
            md.append("## 📋 What We're Building")
            md.append(description)
            md.append("")
        
        # === Agent Workflow ===
        tasks = task_list.get("tasks", [])
        md.append("## 🤖 Execution Workflow")
        md.append("")
        md.append("This plan will be executed in phases:")
        md.append("")
        md.append("### Phase 1: Setup (Planner)")
        md.append("- ✅ Analyzed your request")
        md.append("- ✅ Created project structure plan")
        md.append("- ✅ Identified required dependencies")
        if tasks:
            md.append(f"- ✅ Defined {len(tasks)} implementation tasks")
        md.append("")
        
        md.append("### Phase 2: Implementation (Coder)")
        # List actual files to be created
        entries = folder_map.get("entries", [])
        files = [e for e in entries if not e.get("is_directory", False)]
        dirs = [e for e in entries if e.get("is_directory", False)]
        
        if dirs:
            dir_names = sorted(set(e.get("path", "").split("/")[0] for e in entries if "/" in e.get("path", "")))[:5]
            if dir_names:
                md.append(f"- Create folders: `{', '.join(dir_names)}`")
        
        if files:
            md.append(f"- Generate {len(files)} source files")
            # Show key files
            key_files = [f.get("path") for f in files if any(kw in f.get("path", "") for kw in ["App", "index", "main", "store", "config"])][:5]
            if key_files:
                for kf in key_files:
                    md.append(f"  - `{kf}`")
        
        runtime = dep_data.get("runtime_dependencies", [])
        dev = dep_data.get("dev_dependencies", [])
        if runtime or dev:
            md.append(f"- Install {len(runtime)} runtime + {len(dev)} dev dependencies")
        md.append("")
        
        md.append("### Phase 3: Validation (Validator)")
        md.append("- Run `npm install` to fetch dependencies")
        md.append("- Run `npm run build` to verify compilation")
        md.append("- Check for TypeScript/ESLint errors")
        md.append("- Debug and fix any issues automatically")
        md.append("")
        
        # === Design Decisions ===
        decision_notes = manifest.get("decision_notes", [])
        if decision_notes or assumptions:
            md.append("## 🎯 Design Decisions")
            md.append("")
            
            if assumptions.get("framework"):
                md.append(f"- **Framework**: {assumptions['framework']}")
            if assumptions.get("styling"):
                md.append(f"- **Styling**: {assumptions['styling']}")
            if assumptions.get("state_management"):
                md.append(f"- **State Management**: {assumptions['state_management']}")
            
            for note in decision_notes[:5]:
                md.append(f"- {note}")
            md.append("")
        
        # === Success Criteria ===
        md.append("## ✅ Success Criteria")
        md.append("")
        md.append("The implementation is complete when:")
        md.append("1. All files are created in the project folder")
        md.append("2. `npm run build` completes without errors")
        md.append("3. The application runs with `npm run dev`")
        
        # Add task-specific criteria
        if tasks:
            for task in tasks[:3]:
                criteria = task.get("acceptance_criteria", [])
                if criteria:
                    c = _to_dict(criteria[0])
                    if c.get("then"):
                        md.append(f"4. {c.get('then')}")
                        break
        md.append("")
        
        # === What's Next ===
        md.append("## 📂 Detailed Artifacts")
        md.append("")
        md.append("For granular details, see:")
        md.append("- `task_list.json` - Step-by-step tasks")
        md.append("- `folder_map.json` - Complete file structure")
        md.append("- `dependency_plan.json` - All npm packages")
        md.append("")
        
        md.append("---")
        md.append("*This plan was generated by ShipS* Planner. Execution begins automatically.*")
        
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
