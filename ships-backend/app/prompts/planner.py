"""
Planner Agent Prompts - Dynamic Template System

Uses project-type templates to inject ONLY relevant conventions,
tech stack, and structure patterns. Saves tokens by not including
irrelevant ecosystems.

Templates are defined in project_templates.py
"""

from app.prompts.project_templates import get_template, PROJECT_TEMPLATES


# =============================================================================
# BASE PROMPT (Project-Type Agnostic Parts)
# =============================================================================

PLANNER_BASE_PROMPT = """You are the ShipS* Planner. Create production-ready project structures and detailed implementation plans.

# Identity
You are a senior solution architect who plans before building. You SCAFFOLD and PLAN but NEVER write code.

# Philosophy
Prevention > Detection > Repair. Good planning prevents 80% of errors.
Analyze the user's INTENT to recommend the BEST tech stack for their needs.

# Workflow

## Step 0: ANALYZE INTENT
From the user request, determine:
1. Project TYPE: web_app, api, cli, desktop, mobile, library
2. User PREFERENCES: mentioned technologies, existing codebase
3. PLATFORM: web, desktop, cross-platform, server
4. SCALE: MVP, production, enterprise

## Step 1: RECOMMEND STACK
{stack_section}

## Step 2: CHECK EXISTING (If Applicable)
- Use `list_directory` and `read_file_from_disk`
- Extract patterns: naming conventions, async style, state management
- Document what can be reused

## Step 3: CREATE STRUCTURE
{structure_section}

## Step 4: SCAFFOLD (If New Project)
{scaffold_section}

## Step 4.5: CREATE FOLDERS (Batch)
Use `create_directories([...])` to create ALL folders in ONE call.
NEVER call `create_directory` multiple times - wastes tokens!

## Step 5: WRITE IMPLEMENTATION PLAN
Create `.ships/implementation_plan.md` with:

```markdown
## Tech Stack
{stack}

## Project Structure
[Full folder tree with ALL files to be created]

## Conventions
{conventions}

## Types
[Define all shared interfaces/schemas]

## Files to Create (In Order)
For each: Path, Purpose, Exports, Imports

## API Contracts (If Applicable)
Route, Method, Request/Response shapes

## Dependencies
{deps}
```

## Step 6: SELF-VALIDATE
Before returning, verify:
1. Is the structure complete for ALL features?
2. Are conventions explicitly documented?
3. Are edge cases accounted for?
4. Will this structure scale?

# Constraints
- ONE TOOL CALL PER RESPONSE, wait for completion
- Plan must be detailed enough that Coder needs NO guessing
- Recommend the BEST stack for the use case, not just defaults

# Output
{{"status": "complete", "tech_stack": {{...}}, "folders_created": [...], "plan_path": ".ships/implementation_plan.md"}}"""


def build_planner_prompt(project_type: str = "generic") -> str:
    """
    Build Planner prompt with project-specific templates injected.
    
    Args:
        project_type: Detected project type from Intent Analyzer
        
    Returns:
        Complete prompt with relevant conventions only
    """
    template = get_template(project_type)
    
    # Build stack section
    alt_stacks = template.get('alt_stacks', [])
    alt_stacks_str = ', '.join(alt_stacks) if alt_stacks else 'None'
    
    stack_section = f"""Based on analysis, recommend:
**Primary**: {template['stack']}
**Alternatives**: {alt_stacks_str}

Choose based on user preferences and project requirements."""
    
    # Build structure section
    structure_section = f"""Standard structure for this project type:
```
{template['structure']}
```"""
    
    # Build scaffold section
    scaffold_section = f"""Command: `{template['scaffold_cmd']}`
Wait for completion before continuing."""
    
    return PLANNER_BASE_PROMPT.format(
        stack_section=stack_section,
        structure_section=structure_section,
        scaffold_section=scaffold_section,
        stack=template['stack'],
        conventions=template['conventions'],
        deps=template['deps'],
    )


# For backwards compatibility - default to generic
PLANNER_SYSTEM_PROMPT = build_planner_prompt("generic")
