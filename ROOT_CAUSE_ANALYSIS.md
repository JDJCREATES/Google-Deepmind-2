# Root Cause Analysis - Critical Issues

## Issue 1: Scaffolding Still Runs Despite Prompt Fixes

### Symptoms
```
npx create-next-app@latest crimson-todo-app --typescript --tailwind...
```

### Root Cause
The **Planner** has a `Scaffolder` component (lines 622-801 in `planner/components.py`) that **autonomously decides** when scaffolding is needed by calling `check_needs_scaffolding()`.

The flow is:
1. Planner LLM creates a plan with folder structure
2. **Scaffolder.detect_framework()** analyzes folder map entries
3. **Scaffolder.get_scaffolding_command()** returns the `npx create-next-app` command
4. Planner **executes this command using a tool-calling agent** (NOT the Coder)
5. This happens BEFORE our prompt fixes even reach the Coder

**Why prompt fixes didn't work:**
- We fixed CODER prompts (forbidding scaffolding)
- We fixed PLANNER text prompts (preferring manual structure)
- BUT: The Scaffolder is **code-driven logic**, not prompt-driven
- It has hardcoded framework detection and command generation

### Solutions

**Option A: Disable Scaffolding Component** (RECOMMENDED)
- Remove or disable the Scaffolder component entirely
- Force manual file-by-file creation via folder_map
- Pros: Deterministic, controllable, no black boxes
- Cons: Requires complete folder_map planning

**Option B: Make Scaffolding Opt-In Only**
- Scaffolder only runs if user explicitly requests it
- Add a flag like `allow_scaffolding: false` to config
- Pros: Keeps capability for complex frameworks
- Cons: Still has edge cases where it might run

**Option C: Whitelist Approved Scaffolds Only**
- Only allow specific, well-tested scaffolds (e.g., `npm init -y`)
- Block interactive/complex ones like create-next-app
- Pros: Balance between automation and control
- Cons: Requires maintaining whitelist

### Recommended Fix
```python
# In planner/components.py Scaffolder class
def check_needs_scaffolding(self, existing_files: List[str]) -> bool:
    """DISABLED: Manual file creation preferred over scaffolding."""
    return False  # Force manual creation
```

Or better yet, remove Scaffolder from the planner pipeline entirely.

---

## Issue 2: Fixer Makes Zero Changes (Infinite Loop)

### Symptoms
```
[GIT] No changes to commit for fix_applied (repeated 3 times)
```

### Root Cause
The Fixer receives **insufficient context** about what actually failed:

1. **Validator fails** with specific violations (e.g., "Missing file: src/components/TodoList.tsx")
2. **error_log only contains:** `["Validation Failed [structural]"]` 
3. **Fixer receives:**
   ```python
   recent_errors = error_log[-5:]  # ["Validation Failed [structural]"]
   ```
4. **Fixer prompt contains:**
   ```
   ERRORS TO FIX:
   - Validation Failed [structural]
   ```

**The LLM has NO IDEA what's actually broken!** It sees "structural" but doesn't know:
- Which files are missing
- Which files are unexpected
- What the actual violations are

The **validation_report** artifact EXISTS and contains all violations with details, but the Fixer **never reads it**.

### Current Flow (BROKEN)
```
Validator → validation_report (artifact) → error_log (generic string)
                                                  ↓
Fixer → reads error_log → "Validation Failed [structural]" → ???
```

### Fixed Flow
```
Validator → validation_report (artifact) 
                     ↓
Fixer → reads validation_report → violation details → targeted fixes
```

### Solutions

**Solution 1: Pass Validation Report to Fixer** (RECOMMENDED)
```python
# In fixer.py invoke() method
artifacts = state.get("artifacts", {})
validation_report = artifacts.get("validation_report", {})
layer_results = validation_report.get("layer_results", {})
failure_layer = validation_report.get("failure_layer", "unknown")

# Get actual violations
violations = []
if failure_layer in layer_results:
    violations = layer_results[failure_layer].get("violations", [])

# Build detailed error context
fixer_prompt = f"""PROJECT PATH: {project_path}

FIX ATTEMPT: {fix_attempts}/{max_attempts}

VALIDATION FAILED AT: {failure_layer} layer

SPECIFIC VIOLATIONS:
{chr(10).join([f"- [{v['severity']}] {v['message']}" + (f"\\n  Details: {v['details']}" if v.get('details') else "") for v in violations[:5]])}

YOUR TASK:
1. Read the relevant files mentioned in violations
2. Fix EXACTLY what's broken (missing files, syntax errors, etc.)
3. Use write_file_to_disk for missing files
4. Use apply_source_edits for fixing existing files
"""
```

**Solution 2: Improve Error Log** (BAND-AID)
Instead of just `"Validation Failed [structural]"`, include top 3 violations:
```python
# In validator_node when adding to error_log
error_details = []
for v in violations[:3]:
    error_details.append(f"{v['message']} ({v.get('file_path', 'unknown')})")

error_log.append(f"Validation Failed [{failure_layer}]: " + "; ".join(error_details))
```

### Recommended Fix
Implement Solution 1 - pass full validation_report to Fixer with parsed violations.

---

## Issue 3: CHAT Node Does Nothing Useful

### Symptoms
After 3 failed fix attempts:
```
2026-01-17 21:57:00 - [ORCHESTRATOR] Routing decision: chat
2026-01-17 21:57:02 - [CODER] 📂 Listed directory: . (4 items)
2026-01-17 21:57:03 - [CODER] 📂 Listed directory: crimson-todo-app (15 items)
...
(Just lists directories and reads files, then does nothing)
```

### Root Cause
The CHAT node is **not designed for escalation** - it's designed for **interactive clarification during planning**.

Looking at the code:
1. `fixer_node` hits max attempts
2. Sets `phase: "chat"`
3. Deterministic router sees phase="chat" and routes to `chat_setup`
4. `chat_setup` just sets project_root and returns
5. `chat_cleanup` marks phase as "complete" 
6. **No user interaction, no error summary, no help**

The CHAT node expects to be in a **conversational loop** with a user, but after fixer failure, there's **no user present** - it's an autonomous agent run.

### What Should Happen
When max fix attempts are reached:
1. **Summarize what went wrong** (failed layer, top violations)
2. **Return control to user** with actionable error message
3. **Stop the agent run** with status="failed" and clear next steps

### Current CHAT Flow (BROKEN)
```
Fixer (max attempts) → phase="chat" → chat_setup → chat_cleanup → phase="complete"
                                                                           ↓
                                                                  END (silently)
```

### Desired Flow
```
Fixer (max attempts) → Generate failure summary → Return to user with context
                                                           ↓
                                                   User can manually fix or retry
```

### Solutions

**Option A: Remove CHAT Escalation** (RECOMMENDED)
```python
# In fixer_node
if fix_attempts > max_attempts:
    # Build failure summary
    validation_report = state.get("artifacts", {}).get("validation_report", {})
    failure_layer = validation_report.get("failure_layer", "unknown")
    violations = []
    
    layer_results = validation_report.get("layer_results", {})
    if failure_layer in layer_results:
        violations = layer_results[failure_layer].get("violations", [])[:5]
    
    failure_summary = f"""Failed to fix {failure_layer} layer issues after {max_attempts} attempts.

Top Issues:
{chr(10).join([f"- {v.get('message', 'Unknown error')}" for v in violations])}

Please review the code and try again, or provide more specific instructions."""
    
    return {
        "phase": "done",  # Mark as done, not "chat"
        "status": "failed",
        "fix_attempts": fix_attempts,
        "messages": [AIMessage(content=failure_summary)],
        "artifacts": {
            **artifacts,
            "failure_reason": "max_fix_attempts_exceeded",
            "failure_summary": failure_summary
        }
    }
```

**Option B: Implement Proper Escalation Handler**
Create a dedicated `escalation_node` that:
1. Analyzes validation failures
2. Generates user-friendly summary
3. Suggests manual fixes or alternative approaches
4. Awaits user input with specific questions

### Recommended Fix
Option A - remove CHAT escalation, return clean failure with summary.

---

## Implementation Priority

1. **Issue 2 (Fixer)** - CRITICAL, causes infinite loops and wastes tokens
2. **Issue 3 (CHAT)** - HIGH, blocks proper error visibility 
3. **Issue 1 (Scaffolding)** - MEDIUM, causes unwanted behavior but at least completes

## Testing Plan

After fixes:
1. Create a test run that will fail validation (e.g., request missing file)
2. Verify fixer receives detailed violations
3. Verify fixer attempts to fix specific issues
4. Verify max attempts returns useful error summary
5. Verify no scaffolding runs unless explicitly requested
