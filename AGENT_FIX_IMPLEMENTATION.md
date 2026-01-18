# Agent Fix Implementation - Task-Type Awareness

## Problem
Agents were rewriting entire projects when asked to fix one file, destroying working code.

**Example**: User said "fix page.tsx connection" → Agent rewrote 9 files → Broke everything

## Root Cause
1. Coder treated all tasks the same (no differentiation between fix vs create)
2. Batch operations encouraged for everything (good for greenfield, bad for fixes)
3. READ-BEFORE-WRITE rule buried in prompts, not enforced

## Solution Implemented

### 1. Task-Type Awareness in Coder (`coder.py`)
- Detects `task_type` from `structured_intent` (already provided by Intent Classifier)
- Creates different workflows:
  - **FIX MODE**: Read first → analyze → surgical edits only
  - **CREATE MODE**: Check plan → batch write → integrate

### 2. Updated Coder Prompts (`prompts/coder.py`)
- Restructured workflows by task type
- Added `FIX_MODE_INSTRUCTIONS` emphasizing:
  - Mandatory `read_file_from_disk` before changes
  - Use `apply_source_edits` (surgical), NOT `write_files_batch`
  - Preserve ALL working code
  - Limit to 1-3 files maximum for fixes
- Tool selection guidance per task type

### 3. Fix-Aware Planner (`prompts/planner.py`, `planner.py`)
- Added `task_type` parameter to `build_planner_prompt()`
- Injects FIX MODE guidance for fix/modify tasks:
  - Create 1-2 task plans (not 5+)
  - First task: read/analyze
  - Second task: surgical fix
  - Example good vs bad fix plans
- Planner reads `task_type` from structured intent

## Expected Behavior Changes

**Before:**
```
User: "fix page.tsx connection"
Intent Classifier: task_type=fix, action=modify
Planner: Creates 5 tasks (restructure, refactor, rebuild...)
Coder: Rewrites 9 files using write_file_to_disk
Result: 💥 Working code destroyed
```

**After:**
```
User: "fix page.tsx connection"
Intent Classifier: task_type=fix, action=modify
Planner: Creates 2 tasks (analyze, surgical fix) - sees FIX MODE guidance
Coder: Reads page.tsx first, identifies issue, uses apply_source_edits for minimal change
Result: ✅ Fixed 1-2 files, preserved working code
```

## Key Principles Applied

Based on research of Cursor, Antigravity, and modern agent best practices:

1. **Dynamic Context Discovery**: Let agents read what they need, don't force-feed everything
2. **Task-Type Specialization**: Different workflows for different tasks
3. **Surgical Edits Over Rewrites**: Preserve working code religiously
4. **Minimal Effective Change**: Fix what's broken, leave the rest alone
5. **Tool Selection by Context**: `apply_source_edits` for fixes, `write_files_batch` for creates

## What We DIDN'T Add (By Design)

- ❌ Post-validation orchestrator checks (premature)
- ❌ Complex rule stacking (agents work better with clear workflows than 50 rules)
- ❌ Over-prompting (too many instructions = confusion)

## Files Modified

1. `ships-backend/app/prompts/coder.py` - Task-type aware prompts
2. `ships-backend/app/agents/sub_agents/coder/coder.py` - Conditional workflow in invoke()
3. `ships-backend/app/prompts/planner.py` - Fix-mode guidance for minimal plans
4. `ships-backend/app/agents/sub_agents/planner/planner.py` - Pass task_type to prompt builder

## Testing Recommendations

1. **Simple Fix Test**: "fix the import in utils.ts"
   - Should read file, identify issue, surgical edit
   - Should modify 1 file max

2. **Component Fix Test**: "fix page.tsx so it shows the TodoList"
   - Should read page.tsx, identify missing import
   - Should edit 1-2 files (page.tsx + maybe TodoList if needed)

3. **Create Test** (verify we didn't break greenfield): "create a new Settings page"
   - Should use write_files_batch efficiently
   - Should wire into app properly

---

**Status**: ✅ Implemented Phase 1 - Core task-type awareness
**Next**: Test with real fix scenarios and iterate based on results
