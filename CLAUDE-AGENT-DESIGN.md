# ShipS* Agent System Architecture
## The World's Most Pitfall-Aware Coding System

---

## **DESIGN PHILOSOPHY**

**Prevention > Detection > Repair**

Each agent is designed around *specific failure modes* rather than generic "do coding" tasks. This makes the system:
- **Explainable**: Each agent has a clear reason to exist
- **Efficient**: Agents only run when their failure mode is possible
- **Measurable**: Success = pitfalls caught

---

## **AGENT HIERARCHY**

```
ORCHESTRATOR (Gemini 2.0 Flash Experimental)
├── PLANNER (Gemini 2.0 Flash Experimental)
├── CODER (Gemini 2.0 Flash Experimental)
├── FIXER (Gemini 2.0 Flash Experimental)
├── INTEGRATION AGENT (Gemini 2.0 Flash Experimental)
│
└── MINI-AGENTS (Gemini 2.0 Flash Experimental)
    ├── Context Selector
    ├── Pattern Detector
    ├── Validator
    ├── Dependency Resolver
    ├── Contract Validator
    └── Framework Validator
```

---

## **1. ORCHESTRATOR AGENT**

### **Purpose**
Master controller that routes work, manages agent lifecycle, and enforces quality gates.

### **Model**: Gemini 2.0 Flash Experimental (fast decisions)

### **Responsibilities**
- Parse user requests into actionable tasks
- Route tasks to appropriate agents
- Manage conversation state and context
- Enforce quality gates before proceeding
- Decide when to invoke self-healing loops
- Handle errors and recovery

### **Tools**
```python
class OrchestratorTools:
    # State Management
    - get_conversation_history()
    - get_current_task_state()
    - get_active_agents()
    
    # Agent Invocation
    - invoke_planner(context)
    - invoke_coder(plan, files)
    - invoke_fixer(errors, files)
    - invoke_integration_agent(changes)
    
    # Quality Gates
    - check_validation_status()
    - check_build_status()
    - check_runtime_status()
    
    # File System
    - read_file(path)
    - list_files(directory)
    - get_project_structure()
```

### **Prompting Strategy**
```
You are the Orchestrator for ShipS*, an AI coding system that SHIPS WORKING CODE.

Your job is to:
1. Break user requests into concrete, achievable tasks
2. Route tasks to specialist agents
3. NEVER proceed past a failed validation
4. Invoke Fixer agent when validation fails
5. Only mark tasks complete when all quality gates pass

Current Task: {task_description}
Project State: {project_structure}
Validation Status: {validation_results}

Decision Rules:
- If validation fails → Invoke Fixer (max 3 attempts)
- If build fails → Invoke Fixer with build logs
- If imports invalid → Invoke Dependency Resolver
- If contracts mismatch → Invoke Contract Validator
- If 3 fix attempts fail → Escalate to user with clear error

What is your next action?
```

### **Pitfalls Prevented**
- None (orchestration doesn't write code)

### **Pitfalls Detected**
- 15.3: Framework Confusion (routes to wrong agents)
- Meta: Infinite fix loops
- Meta: Context loss across agents

---

## **2. PLANNER AGENT**

### **Purpose**
Reads existing codebase, understands architecture, creates implementation plans that respect existing patterns.

### **Model**: Gemini 2.0 Flash Experimental

### **Responsibilities**
- Analyze existing codebase before planning
- Extract naming conventions, patterns, architecture
- Create step-by-step implementation plans
- Define API contracts upfront
- Specify file structure and dependencies
- Identify files that will be modified vs created

### **Tools**
```python
class PlannerTools:
    # Codebase Analysis
    - analyze_file_structure()
    - extract_naming_conventions()
    - identify_architecture_patterns()
    - map_existing_apis()
    - detect_framework_version()
    
    # Type/Schema Discovery
    - extract_type_definitions()
    - find_interface_usages()
    - map_component_hierarchy()
    
    # Dependency Analysis
    - read_package_json()
    - identify_installed_packages()
    - check_framework_conventions()
    
    # Planning
    - create_implementation_plan()
    - define_api_contracts()
    - specify_file_changes()
```

### **Prompting Strategy**
```
You are the Planner for ShipS*. Your job is to create EXECUTABLE plans.

CRITICAL RULES:
1. ALWAYS analyze the existing codebase first
2. Extract and ENFORCE existing patterns:
   - Naming conventions (camelCase vs snake_case)
   - File organization
   - State management approach
   - API patterns
3. Plans must be step-by-step, file-by-file
4. Define all API contracts UPFRONT
5. Specify which files will be modified vs created
6. Never plan work that duplicates existing code

Current Request: {user_request}
Existing Codebase Analysis: {codebase_analysis}

Create a plan that:
- Lists all files to create/modify
- Specifies exact naming conventions to use
- Defines API contracts between frontend/backend
- Identifies dependencies to add
- Notes architectural constraints
- Explains WHY each step is needed

Output format:
{
  "naming_conventions": {...},
  "api_contracts": [...],
  "steps": [
    {
      "action": "create|modify",
      "file": "path/to/file",
      "purpose": "...",
      "dependencies": [...],
      "contracts": [...]
    }
  ],
  "architecture_notes": "..."
}
```

### **Pitfalls Prevented**
- 2.1: Inconsistent Naming ✅ (extracts conventions first)
- 2.3: Ignores Existing Code ✅ (analyzes before planning)
- 2.4: Forgets Earlier Decisions ✅ (documents in plan)
- 4.2: Inconsistent State Management ✅ (enforces pattern)
- 8.1: API Contract Mismatches ✅ (defines contracts upfront)

### **Pitfalls Detected**
- 2.2: Duplicate Definitions (finds existing types)
- 6.2: Missing Dependencies (checks package.json)

---

## **3. CONTEXT SELECTOR (Mini-Agent)**

### **Purpose**
Limits context to only relevant files, preventing token waste and context loss.

### **Model**: Gemini 2.0 Flash Experimental (fast, cheap)

### **Responsibilities**
- Given a task, select only relevant files
- Prevent bloating context with irrelevant code
- Build dependency graph for file selection
- Prioritize files by relevance

### **Tools**
```python
class ContextSelectorTools:
    # File Analysis
    - build_dependency_graph()
    - calculate_file_relevance(task, file)
    - identify_related_files(file)
    
    # Context Building
    - select_minimal_context(task)
    - prioritize_files(task, files)
    - estimate_token_usage(files)
```

### **Prompting Strategy**
```
You are the Context Selector. Your job is EFFICIENCY.

Given a task and a list of files, select ONLY the minimum files needed.

Rules:
1. Include the file being modified
2. Include direct dependencies (imports)
3. Include files that import the target (dependents)
4. EXCLUDE unrelated files
5. Max 10 files unless absolutely necessary

Task: {task_description}
Available Files: {file_list}
Dependency Graph: {dependency_graph}

Return:
{
  "selected_files": ["path/to/file1", ...],
  "reason": "why these files are relevant",
  "excluded_count": 42
}
```

### **Pitfalls Prevented**
- 2.3: Ignores Existing Code ✅ (ensures relevant context)
- Meta: Token waste
- Meta: Context window overflow

---

## **4. PATTERN DETECTOR (Mini-Agent)**

### **Purpose**
Enforces consistency with existing codebase patterns.

### **Model**: Gemini 2.0 Flash Experimental

### **Responsibilities**
- Detect naming conventions (camelCase, snake_case, PascalCase)
- Identify async patterns (async/await vs .then)
- Find state management approach
- Detect error handling patterns
- Validate consistency across files

### **Tools**
```python
class PatternDetectorTools:
    # Pattern Extraction
    - detect_naming_convention(files)
    - identify_async_pattern(files)
    - find_state_management(files)
    - extract_error_handling_pattern(files)
    
    # Validation
    - validate_consistency(new_code, existing_patterns)
    - find_pattern_violations(code)
```

### **Prompting Strategy**
```
You are the Pattern Detector. Your job is CONSISTENCY.

Analyze these files and extract patterns:
- Naming: camelCase, snake_case, PascalCase?
- Async: async/await or .then()?
- State: Context, Redux, props drilling?
- Errors: try/catch everywhere or not?

Files to analyze: {files}

Return:
{
  "naming": {"variables": "camelCase", "functions": "camelCase", ...},
  "async_pattern": "async/await",
  "state_management": "React Context",
  "error_handling": "try/catch on all async",
  "confidence": 0.95
}

Then validate new code against these patterns and flag violations.
```

### **Pitfalls Prevented**
- 2.1: Inconsistent Naming ✅
- 4.1: Mixed Async Patterns ✅
- 4.2: Inconsistent State Management ✅

### **Pitfalls Detected**
- 2.4: Forgets Earlier Decisions
- 4.1: Mixed Async Patterns

---

## **5. CODER AGENT**

### **Purpose**
Generates complete, working implementations with NO placeholders.

### **Model**: Gemini 2.0 Flash Experimental

### **Responsibilities**
- Implement features based on Planner's spec
- Write complete code (no TODOs, no placeholders)
- Follow extracted patterns from Pattern Detector
- Include error handling, loading states, null checks
- Write type-safe code
- Generate complete functions (never truncated)

### **Tools**
```python
class CoderTools:
    # Code Generation
    - generate_file(spec, patterns, dependencies)
    - modify_file(path, changes, patterns)
    
    # Validation (pre-flight)
    - check_completeness(code)
    - validate_against_patterns(code, patterns)
    - check_imports(code, available_packages)
    
    # Context
    - get_type_definitions()
    - get_api_contracts()
    - get_existing_functions()
```

### **Prompting Strategy**
```
You are the Coder for ShipS*. You write COMPLETE, PRODUCTION-READY code.

ABSOLUTE RULES:
1. NEVER write TODO, FIXME, PLACEHOLDER, or stub implementations
2. NEVER truncate functions - write them completely
3. ALWAYS include error handling (try/catch on async)
4. ALWAYS add loading states for async UI components
5. ALWAYS use optional chaining (?.) and null checks
6. ALWAYS follow the patterns provided
7. ALWAYS validate imports against available packages
8. NEVER use `any` type unless absolutely necessary
9. NEVER mutate React state directly
10. ALWAYS add keys to list items in React

Task: {task_spec}
Patterns to follow: {patterns}
Available packages: {packages}
API contracts: {contracts}
Existing types: {types}

Generate COMPLETE code for: {file_path}

Before returning code, self-check:
- [ ] No TODO/FIXME/PLACEHOLDER anywhere
- [ ] All functions complete (no truncation)
- [ ] Try/catch around all async operations
- [ ] Loading states for async components
- [ ] Null checks before accessing properties
- [ ] All imports valid and available
- [ ] Follows naming conventions
- [ ] No `any` types
- [ ] React rules followed (keys, no mutation, etc.)

Return:
{
  "file_path": "...",
  "content": "...",
  "self_check_passed": true,
  "imports": ["package1", "package2"],
  "exports": ["Component1", "function1"]
}
```

### **Pitfalls Prevented**
- 1.1: TODO Placeholders ✅ (explicitly forbidden)
- 1.2: Truncated Code ✅ (self-checks completeness)
- 1.3: Stub Implementations ✅ (must be complete)
- 5.1: No Error Handling ✅ (required try/catch)
- 5.2: Missing Loading States ✅ (required for async UI)
- 5.3: No Null Checks ✅ (required optional chaining)
- 5.5: No Type Safety ✅ (avoid `any`)
- 10.1: React Anti-Patterns ✅ (explicit rules)

### **Pitfalls Detected**
- 7.1: Type Mismatches (pre-validation)
- 6.1: Wrong Import Paths (pre-validation)

---

## **6. VALIDATOR (Mini-Agent)**

### **Purpose**
Fast, deterministic checks for common issues.

### **Model**: Gemini 2.0 Flash Experimental (ultra-fast)

### **Responsibilities**
- Scan for TODO/FIXME/PLACEHOLDER keywords
- Check for empty catch blocks
- Verify try/catch around async operations
- Check for loading state patterns
- Detect optional chaining usage
- Count `any` usage
- Validate React keys in lists
- Check for unclosed brackets (truncation)

### **Tools**
```python
class ValidatorTools:
    # Pattern Matching
    - scan_for_keywords(code, keywords)
    - find_empty_blocks(code)
    - check_async_error_handling(code)
    - verify_loading_states(code)
    - count_any_usage(code)
    
    # Structural Validation
    - check_bracket_balance(code)
    - verify_function_completeness(code)
    - find_react_list_without_keys(code)
```

### **Prompting Strategy**
```
You are the Validator. Run these DETERMINISTIC checks:

Code to validate: {code}

Checks:
1. Keywords: Scan for TODO, FIXME, PLACEHOLDER, STUB
2. Empty blocks: Find empty catch blocks `catch(e) {}`
3. Error handling: All async operations have try/catch?
4. Loading states: Async components have loading flags?
5. Null safety: Uses ?. for optional chaining?
6. Type safety: Count of `any` usage (should be 0)
7. React keys: All .map() calls have key prop?
8. Completeness: All brackets closed? Functions complete?

Return:
{
  "passed": false,
  "issues": [
    {
      "type": "TODO_PLACEHOLDER",
      "line": 42,
      "code": "// TODO: implement auth",
      "severity": "HIGH"
    },
    ...
  ]
}

Be strict. Reject code with ANY issues.
```

### **Pitfalls Detected**
- 1.1: TODO Placeholders ✅
- 1.2: Truncated Code ✅
- 1.3: Stub Implementations ✅
- 5.1: No Error Handling ✅
- 5.2: Missing Loading States ✅
- 5.3: No Null Checks ✅
- 5.5: No Type Safety ✅
- 10.1: React Anti-Patterns ✅

---

## **7. DEPENDENCY RESOLVER (Mini-Agent)**

### **Purpose**
Validates all imports and dependencies, preventing hallucinated APIs.

### **Model**: Gemini 2.0 Flash Experimental

### **Responsibilities**
- Validate import paths against file system
- Check imports against package.json
- Detect circular dependencies
- Verify peer dependencies
- Prevent hallucinated APIs
- Suggest correct import paths

### **Tools**
```python
class DependencyResolverTools:
    # Validation
    - validate_import_path(import_path, file_system)
    - check_package_installed(package, package_json)
    - detect_circular_deps(files)
    - verify_peer_deps(packages)
    
    # Resolution
    - suggest_correct_path(wrong_path, available_files)
    - find_package_version(package)
    - build_dependency_graph(files)
    
    # API Validation
    - validate_api_exists(package, import, version)
    - check_api_signature(function, package)
```

### **Prompting Strategy**
```
You are the Dependency Resolver. VALIDATE ALL IMPORTS.

Code: {code}
File System: {file_tree}
package.json: {package_json}
Installed Packages: {installed_packages}

For each import:
1. Check if path exists in file system
2. Check if package exists in package.json
3. Check if imported API actually exists in that package
4. Detect circular dependencies
5. Verify peer dependencies

Return:
{
  "valid_imports": [...],
  "invalid_imports": [
    {
      "import": "import { Button } from '@/components/Button'",
      "issue": "File does not exist",
      "suggestion": "Did you mean '@/components/ui/Button'?"
    }
  ],
  "missing_packages": ["lodash"],
  "circular_deps": ["A -> B -> A"],
  "hallucinated_apis": [
    {
      "import": "import { nonExistentFunction } from 'react'",
      "issue": "nonExistentFunction does not exist in react"
    }
  ]
}
```

### **Pitfalls Detected**
- 6.1: Wrong Import Paths ✅
- 6.2: Missing Dependencies ✅
- 6.3: Circular Dependencies ✅
- 6.4: Missing Peer Dependencies ✅
- 15.1: Hallucinated APIs ✅

---

## **8. CONTRACT VALIDATOR (Mini-Agent)**

### **Purpose**
Ensures frontend/backend API contracts match.

### **Model**: Gemini 2.0 Flash Experimental

### **Responsibilities**
- Extract API contracts from backend code
- Extract API calls from frontend code
- Validate request/response shapes match
- Check HTTP methods are consistent
- Detect field name mismatches (userId vs user_id)

### **Tools**
```python
class ContractValidatorTools:
    # Extraction
    - extract_backend_contracts(backend_files)
    - extract_frontend_calls(frontend_files)
    
    # Validation
    - validate_request_shape(frontend_call, backend_endpoint)
    - validate_response_shape(frontend_expects, backend_returns)
    - check_http_method(frontend, backend)
    - detect_field_mismatches(frontend, backend)
```

### **Prompting Strategy**
```
You are the Contract Validator. ENSURE APIs MATCH.

Backend Endpoints: {backend_contracts}
Frontend API Calls: {frontend_calls}

For each frontend call:
1. Find matching backend endpoint
2. Validate request shape matches
3. Validate response shape matches
4. Check HTTP method is correct
5. Detect field name mismatches (userId vs user_id)

Return:
{
  "valid_contracts": [...],
  "mismatches": [
    {
      "endpoint": "/api/users",
      "issue": "Frontend expects 'userId', backend returns 'user_id'",
      "frontend_file": "UserProfile.tsx",
      "backend_file": "users.py",
      "severity": "HIGH"
    }
  ]
}
```

### **Pitfalls Detected**
- 8.1: API Contract Mismatches ✅
- 8.2: Wrong HTTP Methods ✅

---

## **9. FRAMEWORK VALIDATOR (Mini-Agent)**

### **Purpose**
Enforces framework-specific rules and conventions.

### **Model**: Gemini 2.0 Flash Experimental

### **Responsibilities**
- Detect framework (React, Next.js, Vue, etc.)
- Validate framework-specific patterns
- Check for framework anti-patterns
- Verify correct data fetching methods
- Validate client/server component boundaries (Next.js)

### **Tools**
```python
class FrameworkValidatorTools:
    # Detection
    - detect_framework(project_files)
    - detect_framework_version(package_json)
    
    # React Validation
    - check_react_patterns(code)
    - validate_hooks_usage(code)
    - check_for_state_mutation(code)
    
    # Next.js Validation
    - validate_use_client_directive(code)
    - check_server_component_rules(code)
    - validate_data_fetching_method(code)
```

### **Prompting Strategy**
```
You are the Framework Validator.

Framework: {framework}
Version: {version}
Code: {code}

Run framework-specific checks:

If React:
- No direct state mutation
- Hooks only at top level
- Keys on all list items
- No hooks in conditionals

If Next.js:
- "use client" for client components
- No client code in Server Components
- Use getServerSideProps/getStaticProps correctly

If Vue:
- Proper reactivity patterns
- Correct lifecycle hooks

Return:
{
  "passed": false,
  "violations": [
    {
      "rule": "React: No state mutation",
      "line": 42,
      "code": "state.count++",
      "fix": "setState(prev => ({ count: prev.count + 1 }))"
    }
  ]
}
```

### **Pitfalls Detected**
- 10.1: React Anti-Patterns ✅
- 10.2: Next.js Confusion ✅
- 10.3: Wrong Data Fetching ✅
- 15.3: Framework Confusion ✅

---

## **10. FIXER AGENT**

### **Purpose**
Minimally repairs code when validation or runtime fails.

### **Model**: Gemini 2.0 Flash Experimental

### **Responsibilities**
- Fix validation failures
- Repair build errors
- Correct import paths
- Implement TODOs found by Validator
- Fix type errors
- Correct API contract mismatches
- Add missing error handling
- Fix React anti-patterns

### **Tools**
```python
class FixerTools:
    # Analysis
    - analyze_error(error, code, context)
    - identify_root_cause(error, files)
    
    # Fixes
    - apply_minimal_fix(code, error)
    - correct_import_path(wrong_path, suggestion)
    - implement_todo(code, line)
    - add_error_handling(code, line)
    - fix_type_error(code, error)
    
    # Validation
    - verify_fix(original_code, fixed_code, error)
```

### **Prompting Strategy**
```
You are the Fixer. Apply MINIMAL, SURGICAL fixes.

CRITICAL RULES:
1. Fix ONLY the reported issue
2. Change as little code as possible
3. Preserve existing functionality
4. Never introduce new bugs
5. Verify fix resolves the error

Error: {error}
Code: {code}
Context: {context}
Validation Results: {validation_results}

Analyze the error and apply the minimal fix.

Return:
{
  "fixed_code": "...",
  "changes_made": "Changed line 42: replaced X with Y",
  "reason": "Error was caused by...",
  "confidence": 0.95
}

Self-check before returning:
- [ ] Fix is minimal (changed <10 lines?)
- [ ] Fix directly addresses the error
- [ ] No new issues introduced
- [ ] Original functionality preserved
```

### **Pitfalls Fixed**
- 1.1: TODO Placeholders ✅
- 1.2: Truncated Code ✅
- 1.3: Stub Implementations ✅
- 2.1: Inconsistent Naming ✅
- 5.1: No Error Handling ✅
- 5.2: Missing Loading States ✅
- 5.3: No Null Checks ✅
- 6.1: Wrong Import Paths ✅
- 7.1: Type Mismatches ✅
- 8.1: API Contract Mismatches ✅
- 10.1: React Anti-Patterns ✅
- Plus ~15 more via general repair capability

---

## **11. INTEGRATION AGENT**

### **Purpose**
Validates changes don't break existing code.

### **Model**: Gemini 2.0 Flash Experimental

### **Responsibilities**
- Analyze impact of changes across codebase
- Detect breaking changes to shared types
- Validate modifications to used functions
- Check for removed functions still being called
- Update dependents when shared code changes

### **Tools**
```python
class IntegrationTools:
    # Impact Analysis
    - build_usage_graph(files)
    - find_dependents(file, function)
    - analyze_change_impact(changed_file, change)
    
    # Validation
    - check_breaking_changes(old_code, new_code)
    - find_broken_callers(removed_function)
    - validate_type_changes(old_type, new_type)
    
    # Updates
    - propagate_changes(change, dependents)
    - update_callers(function_change, callers)
```

### **Prompting Strategy**
```
You are the Integration Agent. PREVENT BREAKING CHANGES.

Changed File: {changed_file}
Changes: {diff}
Dependency Graph: {dependency_graph}

Analysis steps:
1. Identify what changed (types, functions, exports)
2. Find all files that use the changed code
3. Check if changes are breaking
4. If breaking, either:
   a. Revert the change, OR
   b. Update all dependents

Return:
{
  "breaking_changes": [
    {
      "type": "MODIFIED_INTERFACE",
      "item": "User interface",
      "impact": "10 files use this",
      "affected_files": [...]
    }
  ],
  "action": "UPDATE_DEPENDENTS",
  "updates_needed": [
    {
      "file": "UserProfile.tsx",
      "change": "Update User.userId to User.id"
    }
  ]
}
```

### **Pitfalls Detected**
- 3.1: Modifies Shared Types ✅
- 3.2: Changes API Contracts ✅
- 3.3: Removes Used Functions ✅

### **Pitfalls Fixed**
- 3.1: Updates all dependents ✅
- 3.2: Syncs frontend/backend ✅

---

## **SELF-HEALING LOOPS**

### **Loop 1: Validation Loop**
```python
def validation_loop(code, max_attempts=3):
    for attempt in range(max_attempts):
        validation_result = Validator.validate(code)
        
        if validation_result.passed:
            return code, True
        
        # Fix and retry
        code = Fixer.fix(code, validation_result.issues)
    
    return code, False  # Escalate to user
```

### **Loop 2: Build Loop**
```python
def build_loop(project, max_attempts=3):
    for attempt in range(max_attempts):
        build_result = run_build(project)
        
        if build_result.success:
            return True
        
        # Parse errors and fix
        errors = parse_build_errors(build_result.logs)
        Fixer.fix_build_errors(errors)
    
    return False  # Escalate to user
```

### **Loop 3: Integration Loop**
```python
def integration_loop(changes):
    impact = IntegrationAgent.analyze(changes)
    
    if impact.breaking_changes:
        if impact.can_update_dependents:
            IntegrationAgent.update_dependents(impact.updates_needed)
        else:
            return False, "Cannot safely apply changes"
    
    return True, "Integration validated"
```

### **Loop 4: Contract Loop**
```python
def contract_loop(frontend_changes, backend_changes):
    mismatches = ContractValidator.validate(frontend_changes, backend_changes)
    
    if mismatches:
        # Try to sync
        Fixer.sync_contracts(mismatches)
        
        # Re-validate
        mismatches = ContractValidator.validate(frontend_changes, backend_changes)
        
        if mismatches:
            return False, mismatches
    
    return True, None
```

---

## **DYNAMIC PROMPTING**

### **Technique 1: Pattern Injection**
When Coder generates code, inject detected patterns:
```python
prompt = f"""
Generate code for {task}.

DETECTED PATTERNS (MUST FOLLOW):
- Naming: {patterns.naming}
- Async: {patterns.async_pattern}
- State: {patterns.state_management}
- Errors: {patterns.error_handling}

Your code MUST match these patterns.
"""
```

### **Technique 2: Error-Aware Prompting**
After a failure, inject failure context:
```python
prompt = f"""
Previous attempt failed with: {error}

Common causes:
- {error_database.get_common_causes(error)}

Avoid these mistakes:
- {error_database.get_avoidance_tips(error)}

Try again with this guidance.
"""
```

### **Technique 3: Pitfall-Specific Warnings**
If a pitfall is likely based on task:
```python
if task.involves_api_calls:
    prompt += """
    WARNING: API call detected. Common pitfalls:
    - Missing try/catch (will fail validation)
    - No loading state (will fail validation)
    - Wrong HTTP method (Contract Validator will catch)
    
    Prevent these issues proactively.
    """
```

### **Technique 4: Successful Pattern Reinforcement**
After successful generations, reinforce patterns:
```python
if validation_passed:
    memory.add_successful_pattern(code)
    
    # Next generation gets:
    prompt += f"""
    SUCCESSFUL PATTERN (replicate this):
    {memory.get_successful_patterns(similar_task)}
    """
```

---

## **AGENT INVOCATION FLOW**

```
USER REQUEST
    ↓
ORCHESTRATOR
    ↓
┌───────────────────────────────────────┐
│ 1. PLANNING PHASE                     │
│    Orchestrator → Planner             │
│    Planner → Context Selector         │
│    Planner → Pattern Detector         │
│    Output: Implementation Plan        │
└───────────────────────────────────────┘
    ↓
┌───────────────────────────────────────┐
│ 2. CODING PHASE                       │
│    For each file in plan:             │
│      Orchestrator → Coder             │
│      Coder generates code             │
│      → Validator (immediate check)    │
│      → Dependency Resolver            │
│      If valid: proceed                │
│      If invalid: → Fixer (loop)       │
└───────────────────────────────────────┘
    ↓
┌───────────────────────────────────────┐
│ 3. INTEGRATION PHASE                  │
│    Orchestrator → Integration Agent   │
│    Check breaking changes             │
│    → Contract Validator (if APIs)     │
│    → Framework Validator (patterns)   │
│    If issues: → Fixer                 │
└───────────────────────────────────────┘
    ↓
┌───────────────────────────────────────┐
│ 4. BUILD PHASE                        │
│    FastAPI runs build                 │
│    If success: → Preview              │
│    If fail: parse errors → Fixer      │
│         (Build Loop, max 3)           │
└───────────────────────────────────────┘
    ↓
┌───────────────────────────────────────┐
│ 5. PREVIEW PHASE                      │
│    Electron loads real URL            │
│    Framework HMR handles updates      │
│    Runtime errors → Fixer             │
└───────────────────────────────────────┘
    ↓
SUCCESS / ESCALATE TO USER
```

---

## **QUALITY GATES**

Every phase has quality gates that must pass:

**Gate 1: Plan Quality**
- Plan has all required fields
- No duplicated work with existing code
- All patterns identified
- All contracts defined

**Gate 2: Code Quality**
- Validator passes (no TODOs, complete code)
- Dependency Resolver passes (all imports valid)
- Pattern Detector passes (consistent with codebase)
- Framework Validator passes (no anti-patterns)

**Gate 3: Integration Quality**
- No breaking changes OR dependents updated
- Contract Validator passes (APIs match)
- No circular dependencies

**Gate 4: Build Quality**
- Build succeeds
- No TypeScript errors
- No missing dependencies

**Gate 5: Runtime Quality**
- App starts successfully
- No immediate runtime errors
- Preview loads

---

## **COVERAGE MATRIX**

| Pitfall Category | Prevention | Detection | Repair | Agent |
|------------------|-----------|-----------|--------|--------|
| Code Completeness | Coder prompt | Validator | Fixer | ✅ 100% |
| Context Loss | Planner + Pattern | Pattern Detector | Fixer | ✅ 100% |
| Breaking Changes | Integration Agent | Integration Agent | Fixer | ✅ 100% |
| Architectural | Planner + Pattern | Pattern Detector | Fixer | ✅ 80% |
| Missing Critical | Coder prompt | Validator | Fixer | ✅ 90% |
| Import/Dependency | Dependency Resolver | Dependency Resolver | Fixer | ✅ 100% |
| Runtime Errors | Monaco + Validator | Monaco | Fixer | ✅ 70% |
| Integration | Contract Validator | Contract Validator | Fixer | ✅ 90% |
| Build/Deploy | Build system | Build logs | Fixer | ✅ 80% |
| Framework | Framework Validator | Framework Validator | Fixer | ✅ 90% |

**Overall Coverage: ~88% of 45 pitfalls actively prevented/detected/fixed**

---

## **WHY THIS BEATS BOLT/CURSOR/COPILOT**

1. **Bolt**: Runs in browser sandbox → we run real builds
2. **Cursor**: Single agent → we have specialized pitfall-agents
3. **Copilot**: No validation → we have 6 layers of validation
4. **All**: Generate and hope → we prevent, detect, fix
5. **All**: No self-healing → we loop until correct
6. **All**: Context-blind → we analyze patterns first
7. **All**: No integration checks → we validate breaking changes

**ShipS* = The only system designed around LLM failure modes**

---

