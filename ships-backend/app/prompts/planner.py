"""
Planner Agent Prompts - Dynamic Template System

Uses project-type templates to inject ONLY relevant conventions,
tech stack, and structure patterns. Saves tokens by not including
irrelevant ecosystems.
"""

# =============================================================================
# PROJECT TYPE TEMPLATES
# =============================================================================

PROJECT_TEMPLATES = {
    "web_app": {
        "stack": "Vite + React + TypeScript + TailwindCSS + Zustand",
        "alt_stacks": ["Next.js + TypeScript", "SvelteKit + TypeScript"],
        "scaffold_cmd": "npx -y create-vite@latest . --template react-ts",
        "structure": """src/
├── components/ui/        # Base UI (Button, Input, Card)
├── components/[feature]/ # Feature-specific components
├── hooks/                # Custom React hooks
├── lib/                  # Utils, helpers, constants
├── types/                # TypeScript interfaces
├── stores/               # Zustand stores
└── api/                  # API client functions""",
        "conventions": """- Naming: camelCase vars, PascalCase components, kebab-case files
- Async: async/await with React Query or SWR
- Exports: named exports (ESM)
- State: Zustand for global, useState for local""",
        "deps": "npm install zustand @tanstack/react-query tailwindcss",
    },
    
    "api": {
        "stack": "Python FastAPI + Pydantic + SQLAlchemy",
        "alt_stacks": ["Node Express + TypeScript", "Go Gin", "Rust Actix"],
        "scaffold_cmd": "pip install fastapi uvicorn sqlalchemy pydantic",
        "structure": """app/
├── api/              # Route handlers
├── core/             # Config, security, db
├── models/           # SQLAlchemy models
├── schemas/          # Pydantic schemas
├── services/         # Business logic
└── utils/            # Helpers""",
        "conventions": """- Naming: snake_case vars/funcs, PascalCase classes
- Async: async def with await
- Exports: __all__ in __init__.py
- Validation: Pydantic models for all I/O""",
        "deps": "pip install fastapi uvicorn sqlalchemy pydantic python-dotenv",
    },
    
    "cli": {
        "stack": "Python Click + Rich",
        "alt_stacks": ["Rust Clap", "Go Cobra", "Node Commander"],
        "scaffold_cmd": "pip install click rich",
        "structure": """src/
├── cli.py           # Main CLI entry
├── commands/        # Subcommands
├── utils/           # Helpers
└── config.py        # Configuration""",
        "conventions": """- Naming: snake_case for all Python
- Async: Not typical for CLI
- Exports: Entry points in setup.py/pyproject.toml
- Output: Rich for styled terminal output""",
        "deps": "pip install click rich",
    },
    
    "desktop": {
        "stack": "Electron + React + TypeScript",
        "alt_stacks": ["Tauri + React", "PyQt6", "Electron + Svelte"],
        "scaffold_cmd": "npx -y create-electron-vite@latest . --template react-ts",
        "structure": """src/
├── main/           # Electron main process
├── preload/        # Preload scripts (IPC bridge)
├── renderer/       # React UI
│   ├── components/
│   ├── hooks/
│   └── stores/
└── shared/         # Types shared between processes""",
        "conventions": """- Naming: camelCase vars, PascalCase components
- IPC: Typed channels with preload bridge
- Security: contextIsolation: true, nodeIntegration: false
- State: Zustand in renderer""",
        "deps": "npm install electron-vite zustand",
    },
    
    "mobile": {
        "stack": "Expo + React Native + TypeScript",
        "alt_stacks": ["React Native CLI", "Flutter"],
        "scaffold_cmd": "npx -y create-expo-app@latest . --template blank-typescript",
        "structure": """app/
├── (tabs)/          # Tab navigation
├── components/      # Shared components
├── hooks/           # Custom hooks
├── lib/             # Utils
└── stores/          # Zustand stores""",
        "conventions": """- Naming: camelCase, PascalCase components
- Navigation: Expo Router (file-based)
- Styling: StyleSheet.create or NativeWind
- State: Zustand + AsyncStorage""",
        "deps": "npx expo install zustand @react-native-async-storage/async-storage",
    },
    
    "rust_cli": {
        "stack": "Rust + Clap + Color-Eyre",
        "alt_stacks": ["Rust + Argh"],
        "scaffold_cmd": "cargo new . && cargo add clap color-eyre",
        "structure": """src/
├── main.rs         # Entry point
├── cli.rs          # Clap command definitions
├── commands/       # Subcommand handlers
├── lib.rs          # Library (if also a lib)
└── utils/          # Helpers""",
        "conventions": """- Naming: snake_case vars/funcs, PascalCase types
- Errors: color-eyre or anyhow for ergonomic errors
- Async: tokio if needed
- Tests: #[cfg(test)] mod tests inline""",
        "deps": "cargo add clap --features derive && cargo add color-eyre",
    },
    
    "go_api": {
        "stack": "Go + Gin + GORM",
        "alt_stacks": ["Go + Chi", "Go + Fiber"],
        "scaffold_cmd": "go mod init && go get github.com/gin-gonic/gin gorm.io/gorm",
        "structure": """cmd/
├── server/main.go   # Entry point
internal/
├── handlers/        # HTTP handlers
├── models/          # GORM models
├── services/        # Business logic
├── middleware/      # Auth, logging, etc.
└── config/          # Configuration""",
        "conventions": """- Naming: camelCase private, PascalCase exported
- Errors: explicit error returns (err != nil)
- Async: goroutines + channels
- Interfaces: define where used, not where implemented""",
        "deps": "go get github.com/gin-gonic/gin gorm.io/gorm",
    },
}

# Default for unknown types
DEFAULT_TEMPLATE = PROJECT_TEMPLATES["web_app"]


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


def build_planner_prompt(project_type: str = "web_app") -> str:
    """
    Build Planner prompt with project-specific templates injected.
    
    Args:
        project_type: Detected project type from Intent Analyzer
        
    Returns:
        Complete prompt with relevant conventions only
    """
    template = PROJECT_TEMPLATES.get(project_type, DEFAULT_TEMPLATE)
    
    # Build stack section
    stack_section = f"""Based on analysis, recommend:
**Primary**: {template['stack']}
**Alternatives**: {', '.join(template['alt_stacks'])}

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


# For backwards compatibility - default to web_app
PLANNER_SYSTEM_PROMPT = build_planner_prompt("web_app")
