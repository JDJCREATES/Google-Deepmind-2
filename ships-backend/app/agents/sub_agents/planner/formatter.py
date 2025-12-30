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
    Format complete implementation plan using ShipS* 19-section template.
    
    Sections:
    1. Summary
    2. Assumptions & Defaults
    3. Success Criteria
    4. Minimal Vertical Slice (MVS)
    5. Tech Stack
    6. Project Structure (Folder Map)
    7. Conventions & Style
    8. Shared Types
    9. Tasks
    10. API Contracts
    11. Dependencies
    12. Validation Checklist
    13. Risk Log
    14. Change Management
    15. CI / Preflight Hooks
    16. Rollback Strategy
    17. Rollout & Demo
    18. Audit & Trace
    19. Post-implementation Notes
    """
    try:
        # Extract sub-models (handle both dict and Pydantic objects)
        manifest = _to_dict(artifacts.get("plan_manifest", {}))
        task_list = _to_dict(artifacts.get("task_list", {}))
        folder_map = _to_dict(artifacts.get("folder_map", {}))
        api_data = _to_dict(artifacts.get("api_contracts", {}))
        dep_data = _to_dict(artifacts.get("dependency_plan", {}))
        validation = _to_dict(artifacts.get("validation_checklist", {}))
        risk_data = _to_dict(artifacts.get("risk_report", {}))
        assumptions = _to_dict(manifest.get("assumptions", {}))
        
        md = []
        
        # === Header ===
        summary = manifest.get("summary", project_name)
        version = manifest.get("version", "1.0.0")
        intent_id = manifest.get("intent_spec_id", "N/A")
        timestamp = datetime.utcnow().isoformat() + "Z"
        
        md.append(f"# Implementation Plan — {summary}")
        md.append(f"**PLAN VERSION**: {version}")
        md.append(f"**ORIGIN INTENT_SPEC**: `{intent_id}`")
        md.append(f"**LAST EDITED**: {timestamp}")
        md.append(f"**PLANNER_VERSION**: 1.0.0")
        md.append("")
        
        # === Section 1: Summary ===
        md.append("## 1 — Summary")
        md.append(manifest.get("detailed_description", summary))
        md.append("")
        
        # === Section 2: Assumptions & Defaults ===
        md.append("## 2 — Assumptions & Defaults")
        md.append(f"- **Framework**: {assumptions.get('framework', 'Vite + React + TypeScript')}")
        md.append(f"- **Language**: {assumptions.get('language', 'TypeScript')}")
        md.append(f"- **Node Version**: {assumptions.get('node_version', '18.x')}")
        md.append(f"- **Package Manager**: {assumptions.get('package_manager', 'npm')}")
        md.append(f"- **Styling**: {assumptions.get('styling', 'TailwindCSS')}")
        md.append(f"- **State Management**: {assumptions.get('state_management', 'Zustand')}")
        md.append(f"- **Default Auth**: {assumptions.get('default_auth', 'none')}")
        md.append(f"- **Auto-Apply Threshold**: {assumptions.get('auto_apply_threshold', 0.85)}")
        md.append("")
        
        # === Section 3: Success Criteria ===
        md.append("## 3 — Success Criteria")
        tasks = task_list.get("tasks", [])
        criteria_count = 0
        for task in tasks[:5]:  # Top 5 tasks' criteria
            for criterion in task.get("acceptance_criteria", []):
                criteria_count += 1
                # Format as Gherkin if available
                given = criterion.get("given")
                when = criterion.get("when")
                then = criterion.get("then")
                if given and when and then:
                    md.append(f"- **Criterion {criteria_count}**: Given {given}, When {when}, Then {then}")
                else:
                    md.append(f"- **Criterion {criteria_count}**: {criterion.get('description', '')}")
        if criteria_count == 0:
            md.append("- Criterion 1: Given the app loads, When I open '/', Then no errors occur")
        md.append("")
        
        # === Section 4: Minimal Vertical Slice (MVS) ===
        md.append("## 4 — Minimal Vertical Slice (MVS)")
        mvs_steps = manifest.get("mvs_steps", ["npm install", "npm run dev"])
        md.append("**Path to run:**")
        for i, step in enumerate(mvs_steps, 1):
            md.append(f"{i}. `{step}`")
        md.append("")
        mvs_files = manifest.get("mvs_expected_files", [])
        if mvs_files:
            md.append("**Files expected:**")
            for f in mvs_files:
                md.append(f"- `{f}`")
        mvs_verify = manifest.get("mvs_verification")
        if mvs_verify:
            md.append(f"\n**Verification:** {mvs_verify}")
        md.append("")
        
        # === Section 5: Tech Stack ===
        md.append("## 5 — Tech Stack")
        md.append(f"- **Framework**: {assumptions.get('framework', 'Vite + React + TypeScript')}")
        md.append(f"- **Styling**: {assumptions.get('styling', 'TailwindCSS')}")
        md.append(f"- **State**: {assumptions.get('state_management', 'Zustand')}")
        md.append(f"- **Test Runner**: {assumptions.get('test_runner', 'vitest')}")
        md.append(f"- **E2E**: {assumptions.get('e2e_runner', 'playwright')}")
        md.append(f"- **Linting**: ESLint + Prettier")
        md.append("")
        
        # === Section 6: Project Structure (Folder Map) ===
        md.append("## 6 — Project Structure")
        entries = folder_map.get("entries", [])
        if entries:
            md.append("```")
            # Group by directory
            sorted_entries = sorted(entries, key=lambda x: x.get("path", ""))
            for entry in sorted_entries:
                path = entry.get("path", "")
                desc = entry.get("description", "")
                is_dir = entry.get("is_directory", False)
                is_immutable = entry.get("is_immutable", False)
                icon = "📁" if is_dir else "📄"
                immutable_flag = " [IMMUTABLE]" if is_immutable else ""
                owner = entry.get("owner_task_id", "")
                owner_str = f" (owner: {owner})" if owner else ""
                md.append(f"{path}{immutable_flag}{owner_str}")
            md.append("```")
            md.append("")
            md.append("> Each entry includes: path, description, owner_task, immutable_flag")
        else:
            md.append("*Folder structure to be defined*")
        md.append("")
        
        # === Section 7: Conventions & Style ===
        md.append("## 7 — Conventions & Style")
        md.append("- **Naming**: camelCase vars, PascalCase components, kebab-case files")
        md.append("- **Exports**: Prefer named exports")
        md.append("- **Async**: async/await, try/catch at service boundaries")
        md.append("- **Type Policy**: strict(true) — avoid `any`; explain exceptions")
        md.append("")
        
        # === Section 8: Shared Types ===
        md.append("## 8 — Shared Types")
        md.append("```typescript")
        md.append("// Define shared interfaces here")
        md.append("interface IAppConfig {")
        md.append("  // App configuration")
        md.append("}")
        md.append("```")
        md.append("")
        
        # === Section 9: Tasks ===
        md.append("## 9 — Tasks (Ordered by Priority)")
        if tasks:
            for i, task in enumerate(tasks, 1):
                task_id = task.get("id", f"TASK-{i:03d}")
                title = task.get("title", "Untitled")
                status = task.get("status", "pending")
                complexity = task.get("complexity", "small")
                
                # Checkbox based on status
                checkbox = "[ ]"
                if status == "completed": checkbox = "[x]"
                elif status == "in_progress": checkbox = "[/]"
                elif status == "blocked": checkbox = "[-]"
                
                md.append(f"- {checkbox} **{task_id}**: {title}")
                md.append(f"  - Estimated: {complexity}")
                
                # Acceptance criteria
                for criterion in task.get("acceptance_criteria", []):
                    given = criterion.get("given")
                    when = criterion.get("when")
                    then = criterion.get("then")
                    if given and when and then:
                        md.append(f"  - AC: Given {given}, When {when}, Then {then}")
                    elif criterion.get("description"):
                        md.append(f"  - AC: {criterion.get('description')}")
        else:
            md.append("*Tasks to be defined*")
        md.append("")
        
        # === Section 10: API Contracts ===
        md.append("## 10 — API Contracts")
        endpoints = api_data.get("endpoints", [])
        if endpoints:
            for ep in endpoints:
                method = ep.get("method", "GET")
                path = ep.get("path", "/")
                desc = ep.get("description", "")
                md.append(f"- **{method}** `{path}` → {desc}")
        else:
            md.append("*No API endpoints defined*")
        md.append("")
        
        # === Section 11: Dependencies ===
        md.append("## 11 — Dependencies")
        runtime = dep_data.get("runtime_dependencies", [])
        dev = dep_data.get("dev_dependencies", [])
        if runtime:
            md.append("**Runtime:**")
            for dep in runtime:
                name = dep.get("name", "")
                ver = dep.get("version", "latest")
                md.append(f"- `{name}@{ver}`")
        if dev:
            md.append("\n**Dev:**")
            for dep in dev:
                name = dep.get("name", "")
                ver = dep.get("version", "latest")
                md.append(f"- `{name}@{ver}`")
        if not runtime and not dev:
            md.append("*Dependencies to be defined*")
        md.append("")
        
        # === Section 12: Validation Checklist ===
        md.append("## 12 — Validation Checklist")
        md.append("- [ ] **Structural**: No files outside Folder Map")
        md.append("- [ ] **Completeness**: No TODO placeholders")
        md.append("- [ ] **Dependency**: All imports resolvable")
        md.append("- [ ] **Contract**: API endpoints match contract")
        md.append("- [ ] **Runtime**: App boots without errors")
        md.append("")
        
        # === Section 13: Risk Log ===
        md.append("## 13 — Risk Log")
        risks = risk_data.get("risks", [])
        if risks:
            for i, risk in enumerate(risks, 1):
                title = risk.get("title", "Untitled risk")
                level = risk.get("risk_level", "low")
                mitigation = risk.get("mitigation", "TBD")
                md.append(f"- **R{i}**: {title} — {level} risk — mitigation: {mitigation}")
        else:
            md.append("*No risks identified*")
        md.append("")
        
        # === Section 14: Change Management ===
        md.append("## 14 — Change Management")
        md.append("- Plan edits must increment `PLAN VERSION`")
        md.append("- To change the plan:")
        md.append("  1. Create a `replan_request` artifact (reason + diff)")
        md.append("  2. Planner runs, produces new Plan Version")
        md.append("  3. Orchestrator requires Validator to re-run")
        md.append("- Small UX changes allowed at Coder level if they don't violate Folder Map")
        md.append("")
        
        # === Section 15: CI / Preflight Hooks ===
        md.append("## 15 — CI / Preflight Hooks")
        md.append("- **On PR**: Run linter, unit tests, build step")
        md.append(f"- **Coverage Gate**: ≥ {int(assumptions.get('coverage_threshold', 0.5) * 100)}% for critical modules")
        md.append("- **Flaky Test Handling**: Tag flaky tests; do not block")
        md.append("")
        
        # === Section 16: Rollback Strategy ===
        md.append("## 16 — Rollback Strategy")
        md.append("- Every FileChangeSet maps to TASK-ID")
        md.append("- To revert: `git revert <commit>` or use Fixer")
        md.append("- Hotfix: Create emergency TASK with high priority")
        md.append("")
        
        # === Section 17: Rollout & Demo ===
        md.append("## 17 — Rollout & Demo")
        md.append("- Demo script: Sequence of tasks to show vertical slice")
        md.append("- Live preview available at dev server URL")
        md.append("")
        
        # === Section 18: Audit & Trace ===
        md.append("## 18 — Audit & Trace")
        md.append(f"- **Intent Spec ID**: `{intent_id}`")
        md.append(f"- **Plan ID**: `{manifest.get('id', 'N/A')}`")
        md.append("- All artifacts carry traceability metadata")
        md.append("")
        
        # === Section 19: Post-implementation Notes ===
        md.append("## 19 — Post-implementation Notes")
        md.append("- **Request replan**: Use Orchestrator with `replan` flag")
        md.append("- **Known issues**: *None*")
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
