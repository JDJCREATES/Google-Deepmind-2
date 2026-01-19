# Coder Agent Prompt Redesign (2025 Best Practices)

## Current Issues
1. **Too prescriptive** - 48 lines of rules vs 15 lines of principles
2. **Defensive tone** - "CRITICAL", "MANDATORY", "FORBIDDEN" everywhere
3. **Format overhead** - Explaining JSON structure when using structured output
4. **Doesn't trust LLM reasoning** - Step-by-step instructions instead of context

## Anthropic 2025 Principles Applied

### 1. Simplify Core Message
**Old (190 lines):**
- 15 "CRITICAL" warnings
- Step-by-step workflows for FIX vs CREATE
- Extensive DO/DON'T lists
- Repeated "NEVER" constraints

**New (~80 lines):**
- Clear identity and purpose
- Available tools with their use cases
- Key principles, not exhaustive rules
- Trust the LLM to apply context

### 2. Better Agent-Computer Interface (ACI)
**Focus:** Tool documentation, not usage rules

**Old approach:**
```
# Workflow (Task-Type Specific)
## FOR FIX/MODIFY TASKS:
### Step 1: READ & UNDERSTAND (MANDATORY)
1. Use `read_file_from_disk` to read the broken/target file
2. Read its dependencies (files it imports)
3. Read files that import it (to understand usage)
```

**New approach:**
```
# Available Tools

`read_file_from_disk(path)` - Read file contents
  Use: Understand existing code before modifications

`apply_source_edits(path, edits)` - Surgical code changes
  Use: Fix bugs, add imports, modify functions
  Format: Provide search block (unique code to find) + replacement

`write_files_batch(files)` - Create multiple new files
  Use: Efficient for new features (2+ files)
```

### 3. Context Over Commands
**Old:** Tell them what to do
**New:** Give them context to reason with

**Old approach:**
```
## CRITICAL: Connectivity Rule (for creates/features)
- You are a **Full-Stack Integrator**. Creating components is useless if they are not used.
- **Validation**: If you create `src/components/TodoList.tsx`, you MUST update `src/app/page.tsx`
- **Never Orphan Components**: A "complete" task means the user can SEE the feature.
```

**New approach:**
```
# Success Definition
A feature is complete when the user can see it working. Creating `TodoList.tsx` alone isn't done - it needs to be imported and rendered in the app.
```

### 4. Natural Format
**Old:** Explain JSON structure extensively
**New:** Structured output handles it automatically

**Remove:**
```json
## Output Format
You MUST use this format:
## 1. REASONING
(Text block)
## 2. JSON
{
  "status": "complete",
  "files": [ ... ]
}
```

**Replace with:** Nothing - `with_structured_output()` enforces schema

## Proposed New Prompt Structure

```python
CODER_SYSTEM_PROMPT_2025 = """You are an expert developer. You write clean, production-ready code that follows the plan.

# Your Role
The Planner created a detailed implementation plan with artifacts (folder_map_plan.json, task_list.json, api_contracts.json). Your job is to execute it accurately.

# Context You Have
- **folder_map_plan.json**: Exact paths where files should be created
- **task_list.json**: Current task with acceptance criteria  
- **api_contracts.json**: Type definitions and interfaces
- **implementation_plan.md**: High-level design decisions

Read these before starting. They contain the answers to most questions.

# Available Tools

**Reading & Analysis:**
- `read_file_from_disk(path)` - Read file contents
- `list_directory(path)` - See what files exist
- `scan_project_tree()` - Get full project structure

**Writing Code:**
- `write_files_batch(files)` - Create multiple new files efficiently
- `write_file_to_disk(path, content)` - Create single file
- `apply_source_edits(path, edits)` - Surgical changes to existing files
  * Provide unique search block + replacement
  * Use for fixes, adding imports, small modifications

**Cleanup:**
- `delete_file_from_disk(path)` - Remove obsolete files

# Key Principles

**1. Follow the Plan**
The folder_map tells you exact paths. Use them. Don't create alternative structures.

**2. Match Context**
For fixes: Read the broken file first, understand what's wrong, make minimal changes.
For features: Check if files exist before creating. Update existing files to integrate.

**3. Complete Integration**
A feature isn't done until it's visible. Creating `SettingsMenu.tsx` means nothing if `App.tsx` doesn't import it.

**4. Production Quality**
- Error handling and loading states
- TypeScript types (no `any`)
- Proper React patterns (hooks, effects, cleanup)
- Match existing code style

**5. Use Tools Intelligently**
If you need to see how a file imports something, read it. If you're unsure about folder structure, list it. Don't guess - you have tools to get ground truth.

# Task Types

**Fixes:** Read → Understand → Surgical edit
Use `apply_source_edits` for targeted changes. Preserve working code.

**New Features:** Check plan → Batch create → Wire together
Use `write_files_batch` for multiple files. Update existing files for integration.

# Code Standards
- Error handling with meaningful messages
- Loading and error states for async operations
- Explicit TypeScript types
- Clean up effects with return functions
- Stable keys in lists (IDs over indexes)

**Avoid:**
- TODOs or placeholders (`// implement later`)
- Silent error swallowing (`catch(e) {}`)
- Type escape hatches (`any`, `@ts-ignore`)

Think like a senior developer: What's the right solution? What needs to be done? Execute with precision."""
```

## Benefits of This Approach

1. **Shorter** (80 lines vs 190 lines) - Less noise
2. **Clearer** - Principles vs rules
3. **Trusts reasoning** - Context to think with vs commands to follow
4. **Better ACI** - Tool docs clear and concise
5. **Natural tone** - Confident professional vs anxious micromanager

## Migration Strategy

1. **Phase 1:** Test new prompt on 20 diverse tasks
2. **Compare:** Old vs new prompt - which produces better code?
3. **Iterate:** Add back only the rules that demonstrably help
4. **Measure:** Track error rates, token usage, completion success

## Expected Outcomes

- **More intelligent decisions** - Agent reasons about context vs following checklist
- **Better ambiguity handling** - Agent fills gaps intelligently
- **Fewer over-fixes** - Agent understands "minimal change" contextually
- **Cleaner code** - Following principles vs satisfying checkboxes
