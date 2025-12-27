# ShipS* Complete Artifact System
## The System That Makes AI Coding Auditable and Intelligent

---

## **YOUR CATEGORIES: GOOD FOUNDATION**

✅ **Input-Focused**: Guides AI before coding
✅ **Output-Focused**: Makes AI actions transparent

**But you're missing the "Runtime Intelligence" layer** — artifacts that agents actively query and update during execution to stay coordinated and learn.

---

## **ENHANCED 3-LAYER ARTIFACT SYSTEM**

### **LAYER 1: PLANNING ARTIFACTS** (Before Coding)
What humans provide to guide AI

### **LAYER 2: RUNTIME ARTIFACTS** (During Coding)
What agents create and query to coordinate

### **LAYER 3: AUDIT ARTIFACTS** (After Coding)
What humans inspect to understand what happened

---

## **LAYER 1: PLANNING ARTIFACTS** (Input-Focused)

### **1.1 App Blueprint** ✅ (You have this)
```yaml
artifact_type: app_blueprint
purpose: High-level project vision
format: YAML or Markdown

contents:
  - project_name: "MyApp"
  - description: "What this app does"
  - target_users: ["developers", "designers"]
  - core_features:
      - "User authentication"
      - "Dashboard with real-time data"
      - "Export to PDF"
  - tech_stack:
      frontend: "React + TypeScript + Tailwind"
      backend: "FastAPI + PostgreSQL"
      hosting: "Vercel + Railway"
  - success_criteria:
      - "Sub-2s page load"
      - "Mobile responsive"
      - "WCAG 2.1 AA compliant"
  - constraints:
      - "No external API dependencies"
      - "Must work offline"

usage:
  - Planner reads this to understand scope
  - Orchestrator uses to validate requests are in scope
  - Pattern Detector checks tech stack to set framework rules
```

**Enhancement**: Add explicit **non-goals** and **out-of-scope** sections so agents don't over-engineer.

---

### **1.2 Folder Map** ✅ (You have this)
```yaml
artifact_type: folder_map
purpose: Directory structure and file organization
format: Tree structure (YAML or text)

example:
  src/
    components/
      ui/           # Reusable UI components
        Button.tsx
        Input.tsx
      features/     # Feature-specific components
        auth/
          LoginForm.tsx
    lib/
      utils.ts      # Pure utility functions
      api.ts        # API client
    app/            # Next.js app directory
      layout.tsx
      page.tsx

conventions:
  - components in PascalCase
  - utilities in camelCase
  - one component per file
  - colocate tests with components

usage:
  - Context Selector uses to find relevant files
  - Coder uses to determine where to place new files
  - Dependency Resolver validates import paths
```

**Enhancement**: Add **ownership** (which agent created each file) and **status** (stable/in-progress/needs-review).

---

### **1.3 Data/State Schema** ✅ (You have this)
```typescript
// artifact_type: data_schema
// purpose: Define all data structures and relationships

interface User {
  id: string;
  email: string;
  name: string;
  role: "admin" | "user";
  createdAt: Date;
}

interface Post {
  id: string;
  authorId: string;  // FK to User.id
  title: string;
  content: string;
  publishedAt: Date | null;
}

// API Contracts
interface API {
  "POST /api/auth/login": {
    request: { email: string; password: string };
    response: { token: string; user: User };
  };
  "GET /api/posts": {
    request: { page?: number; limit?: number };
    response: { posts: Post[]; total: number };
  };
}

// usage:
// - Planner references to maintain consistency
// - Contract Validator enforces these shapes
// - Coder uses to generate type-safe code
```

**Enhancement**: Add **validation rules** (min/max lengths, required fields) and **migration history** so agents understand schema evolution.

---

### **1.4 Flow Diagram** ✅ (You have this)
```yaml
artifact_type: flow_diagram
purpose: User journeys and system sequences
format: Mermaid or structured YAML

example:
  flows:
    - name: "User Login"
      steps:
        - screen: "LoginPage"
          trigger: "User clicks 'Login'"
          action: "Submit credentials"
          next: "Dashboard"
          error: "Show error toast, stay on LoginPage"
        
    - name: "Create Post"
      steps:
        - screen: "Dashboard"
          trigger: "User clicks 'New Post'"
          action: "Navigate to editor"
          next: "PostEditor"
        - screen: "PostEditor"
          trigger: "User clicks 'Publish'"
          action: "POST /api/posts"
          success: "Navigate to Dashboard"
          error: "Show error, stay in editor"

usage:
  - Planner uses to sequence implementation
  - Integration Agent validates flows still work after changes
  - Framework Validator checks navigation patterns
```

**Enhancement**: Add **state machines** for complex flows and **error recovery paths**.

---

### **1.5 UI/UX Sketch** ✅ (You have this)
```yaml
artifact_type: ui_sketch
purpose: Visual guidance for interface creation
format: Images + annotations or Figma links

example:
  pages:
    - name: "Dashboard"
      layout: "sidebar + main content"
      components:
        - Header with user avatar (top right)
        - Sidebar navigation (left)
        - Main content area (grid of cards)
      interactions:
        - "Click card → navigate to detail page"
        - "Hover card → show quick actions"
      style_notes:
        - "Use dark mode by default"
        - "Card shadows: shadow-lg"
        - "Primary color: blue-600"

usage:
  - Coder generates components matching these specs
  - Framework Validator checks accessibility patterns
```

**Enhancement**: Add **responsive breakpoints** and **accessibility requirements** (keyboard nav, screen reader text).

---

## **LAYER 2: RUNTIME ARTIFACTS** (Agent Intelligence)

**These are MISSING from your design and are CRITICAL for agent coordination.**

---

### **2.1 Pattern Registry** 🆕 CRITICAL
```yaml
artifact_type: pattern_registry
purpose: Store detected patterns from existing codebase
created_by: Pattern Detector
updated_by: Pattern Detector, Planner
format: JSON

contents:
  naming_conventions:
    variables: "camelCase"
    functions: "camelCase"
    components: "PascalCase"
    files: "kebab-case"
    confidence: 0.95
  
  async_patterns:
    preferred: "async/await"
    error_handling: "try/catch on all async"
    confidence: 1.0
  
  state_management:
    approach: "React Context + useReducer"
    location: "src/contexts/"
    pattern: |
      // Example pattern found
      const [state, dispatch] = useReducer(reducer, initialState);
    confidence: 0.9
  
  error_handling:
    pattern: "try/catch with toast notification"
    example: |
      try {
        await apiCall();
      } catch (error) {
        toast.error(error.message);
      }
  
  api_patterns:
    client_location: "src/lib/api.ts"
    base_url_pattern: "process.env.NEXT_PUBLIC_API_URL"
    authentication: "Bearer token in headers"
  
  import_aliases:
    "@/components": "src/components"
    "@/lib": "src/lib"
    "@/app": "src/app"

usage:
  - Coder MUST read this before generating code
  - Pattern Detector updates as new patterns emerge
  - Validator enforces these patterns
  - Fixer uses to correct violations
```

**Why Critical**: Without this, agents generate inconsistent code. This is the "style guide" that keeps everything coherent.

---

### **2.2 Context Map** 🆕 CRITICAL
```yaml
artifact_type: context_map
purpose: Track which files are relevant for current task
created_by: Context Selector
updated_by: Context Selector (per task)
format: JSON

example:
  current_task: "Add user profile editing"
  relevant_files:
    - path: "src/components/features/auth/UserProfile.tsx"
      reason: "Component being modified"
      priority: 1
      lines_of_interest: [45-67]  # specific functions
    
    - path: "src/lib/api.ts"
      reason: "Contains API client used by UserProfile"
      priority: 2
    
    - path: "src/app/types/User.ts"
      reason: "User type definition"
      priority: 1
    
    - path: "src/contexts/AuthContext.tsx"
      reason: "Provides user state management"
      priority: 2
  
  excluded_files: 127
  token_estimate: 3450
  
  dependency_graph:
    UserProfile.tsx:
      imports: ["api.ts", "User.ts", "AuthContext.tsx"]
      imported_by: ["app/profile/page.tsx"]

usage:
  - Coder receives ONLY files in this map
  - Prevents token waste on irrelevant files
  - Dependency Resolver validates against this graph
```

**Why Critical**: Prevents context loss and token waste. Agents only see what matters.

---

### **2.3 Contract Definitions** 🆕 CRITICAL
```yaml
artifact_type: contract_definitions
purpose: Define API contracts between frontend/backend
created_by: Planner
enforced_by: Contract Validator
format: TypeScript-like schema

contracts:
  - endpoint: "POST /api/users"
    request:
      body:
        email: string
        password: string (min: 8, max: 100)
        name: string
      headers:
        Content-Type: "application/json"
    
    response:
      success:
        status: 201
        body:
          user: User
          token: string
      error:
        status: 400 | 409
        body:
          error: string
          field?: string
    
    validation_rules:
      - "email must be valid format"
      - "password must contain uppercase, lowercase, number"
      - "email must be unique (409 if exists)"
  
  - endpoint: "GET /api/users/:id"
    request:
      params:
        id: string (uuid format)
      headers:
        Authorization: "Bearer {token}"
    
    response:
      success:
        status: 200
        body: User
      error:
        status: 404 | 401
        body:
          error: string

usage:
  - Contract Validator checks frontend calls match these
  - Contract Validator checks backend implements these
  - Coder uses to generate correct API calls
  - Fixer uses to fix mismatches
```

**Why Critical**: Prevents the #1 runtime failure mode (API mismatch). This is your single source of truth.

---

### **2.4 Dependency Graph** 🆕 CRITICAL
```yaml
artifact_type: dependency_graph
purpose: Visual map of all imports and dependencies
created_by: Dependency Resolver
updated_by: Dependency Resolver (on file changes)
format: Graph structure (JSON)

graph:
  nodes:
    - id: "src/components/UserProfile.tsx"
      type: "component"
      exports: ["UserProfile", "UserProfileProps"]
    
    - id: "src/lib/api.ts"
      type: "utility"
      exports: ["apiClient", "fetchUser", "updateUser"]
    
    - id: "src/app/types/User.ts"
      type: "type"
      exports: ["User", "UserRole"]
  
  edges:
    - from: "src/components/UserProfile.tsx"
      to: "src/lib/api.ts"
      imports: ["fetchUser", "updateUser"]
    
    - from: "src/components/UserProfile.tsx"
      to: "src/app/types/User.ts"
      imports: ["User"]
    
    - from: "src/app/profile/page.tsx"
      to: "src/components/UserProfile.tsx"
      imports: ["UserProfile"]
  
  circular_dependencies: []  # MUST be empty
  orphaned_files: ["src/components/OldComponent.tsx"]  # unused files

usage:
  - Integration Agent checks impact of changes
  - Dependency Resolver validates no circular deps
  - Context Selector uses to find related files
  - Fixer uses to understand what broke
```

**Why Critical**: Prevents breaking changes and circular dependency hell. This is your safety net.

---

### **2.5 Quality Gate Results** 🆕 CRITICAL
```yaml
artifact_type: quality_gate_results
purpose: Track which quality gates passed/failed
created_by: Orchestrator
updated_by: All agents
format: JSON

gates:
  - gate: "Plan Quality"
    status: "PASSED"
    timestamp: "2025-12-26T10:30:00Z"
    checks:
      - name: "Plan has all required fields"
        passed: true
      - name: "No duplicate work"
        passed: true
      - name: "All patterns identified"
        passed: true
  
  - gate: "Code Quality"
    status: "FAILED"
    timestamp: "2025-12-26T10:35:00Z"
    checks:
      - name: "Validator (no TODOs)"
        passed: false
        issues: ["Line 42: TODO: implement auth"]
      - name: "Dependency Resolver"
        passed: true
      - name: "Pattern Detector"
        passed: true
    
    fix_attempts:
      - attempt: 1
        agent: "Fixer"
        timestamp: "2025-12-26T10:36:00Z"
        result: "SUCCESS"
        changes: "Implemented auth at line 42"
  
  - gate: "Integration Quality"
    status: "PENDING"
    
current_gate: "Code Quality"
can_proceed: false

usage:
  - Orchestrator checks before proceeding to next phase
  - Prevents proceeding past failures
  - Provides audit trail of fix attempts
  - User can see exactly where process is stuck
```

**Why Critical**: Enforces quality. Without this, bad code proceeds to next phase.

---

### **2.6 Agent Conversation Log** 🆕 CRITICAL
```yaml
artifact_type: agent_conversation_log
purpose: Record of all agent actions and decisions
created_by: Orchestrator
updated_by: All agents
format: JSON (chronological)

conversation:
  - timestamp: "2025-12-26T10:30:00Z"
    agent: "Orchestrator"
    action: "received_request"
    details:
      request: "Add user profile editing"
    
  - timestamp: "2025-12-26T10:30:15Z"
    agent: "Orchestrator"
    action: "invoked_planner"
    input:
      context: "Existing codebase analysis"
    
  - timestamp: "2025-12-26T10:31:00Z"
    agent: "Planner"
    action: "created_plan"
    output:
      plan_id: "plan_001"
      files_to_modify: ["UserProfile.tsx"]
      files_to_create: []
    reasoning: "UserProfile component already exists, just needs edit form"
  
  - timestamp: "2025-12-26T10:31:30Z"
    agent: "Context Selector"
    action: "selected_context"
    output:
      files: ["UserProfile.tsx", "api.ts", "User.ts"]
      excluded: 127
    reasoning: "Only 3 files needed for this change"
  
  - timestamp: "2025-12-26T10:32:00Z"
    agent: "Pattern Detector"
    action: "extracted_patterns"
    output:
      patterns: "pattern_registry_v1"
    reasoning: "Found consistent async/await pattern"
  
  - timestamp: "2025-12-26T10:33:00Z"
    agent: "Coder"
    action: "generated_code"
    output:
      file: "UserProfile.tsx"
      lines_changed: 45
    
  - timestamp: "2025-12-26T10:33:30Z"
    agent: "Validator"
    action: "validation_failed"
    issues:
      - "Line 42: TODO found"
    
  - timestamp: "2025-12-26T10:34:00Z"
    agent: "Fixer"
    action: "applied_fix"
    changes: "Implemented auth logic"
    result: "SUCCESS"

usage:
  - Debugging: understand why agent made a decision
  - Audit: see complete history of changes
  - Learning: identify patterns in successful vs failed tasks
  - User transparency: show what's happening in real-time
```

**Why Critical**: Explainability. Users can see exactly what agents are doing and why.

---

### **2.7 Fix History** 🆕 IMPORTANT
```yaml
artifact_type: fix_history
purpose: Record all fixes applied and their outcomes
created_by: Fixer
updated_by: Fixer
format: JSON

fixes:
  - fix_id: "fix_001"
    timestamp: "2025-12-26T10:34:00Z"
    trigger: "Validator found TODO"
    file: "src/components/UserProfile.tsx"
    line: 42
    original_code: "// TODO: implement auth"
    fixed_code: |
      try {
        const token = await getAuthToken();
        if (!token) throw new Error("Not authenticated");
        // ... implementation
      } catch (error) {
        toast.error("Authentication failed");
      }
    reasoning: "Implemented complete auth flow with error handling"
    validation_result: "PASSED"
    
  - fix_id: "fix_002"
    timestamp: "2025-12-26T10:35:00Z"
    trigger: "Build error: Cannot find module 'lodash'"
    file: "package.json"
    change: "Added lodash@4.17.21 to dependencies"
    reasoning: "Code uses lodash but not in package.json"
    build_result: "SUCCESS"

usage:
  - Learn from successful fixes
  - Avoid repeating same mistakes
  - Provide context for future fixes
  - Show user what was automatically fixed
```

**Why Important**: Learning and transparency. Agents get smarter over time.

---

### **2.8 Pitfall Coverage Matrix** 🆕 IMPORTANT
```yaml
artifact_type: pitfall_coverage_matrix
purpose: Track which pitfalls were checked and caught
created_by: Orchestrator
updated_by: All validators
format: JSON

coverage:
  - pitfall_id: "1.1"
    name: "TODO Placeholders"
    status: "CHECKED"
    result: "CAUGHT"
    details:
      agent: "Validator"
      location: "UserProfile.tsx:42"
      fixed_by: "Fixer"
  
  - pitfall_id: "6.1"
    name: "Wrong Import Paths"
    status: "CHECKED"
    result: "CLEAN"
    details:
      agent: "Dependency Resolver"
      all_imports_valid: true
  
  - pitfall_id: "8.1"
    name: "API Contract Mismatches"
    status: "CHECKED"
    result: "CLEAN"
    details:
      agent: "Contract Validator"
      contracts_validated: 3
  
  - pitfall_id: "7.2"
    name: "Async Race Conditions"
    status: "SKIPPED"
    reason: "Requires runtime testing (accepted gap)"

summary:
  total_pitfalls: 45
  checked: 38
  caught: 2
  clean: 36
  skipped: 7
  coverage: 84%

usage:
  - Show user how thorough the validation was
  - Identify gaps in coverage
  - Justify confidence in generated code
```

**Why Important**: Confidence metric. Users know exactly what was validated.

---

## **LAYER 3: AUDIT ARTIFACTS** (Output-Focused)

### **3.1 Plan Logs** ✅ (You have this - enhance)
```yaml
artifact_type: plan_log
purpose: Step-by-step reasoning and decisions

enhanced_contents:
  - step_number: 1
    action: "Analyze existing UserProfile component"
    reasoning: "Need to understand current structure before modifying"
    duration: "2.3s"
    agent: "Planner"
  
  - step_number: 2
    decision: "Modify existing component rather than create new"
    reasoning: "Component already exists with 80% of needed functionality"
    alternatives_considered:
      - "Create new UserProfileEdit component"
      - "Refactor into modal"
    why_rejected:
      - "Would duplicate code"
      - "Inconsistent with existing patterns"
  
  - step_number: 3
    action: "Define API contract for user update"
    contract: "PATCH /api/users/:id"
    reasoning: "RESTful convention, partial updates"

usage:
  - Human reviews to understand agent reasoning
  - Helps debug why certain decisions were made
  - Training data for improving prompts
```

---

### **3.2 Diffs** ✅ (You have this - enhance)
```yaml
artifact_type: diff
purpose: Track file changes

enhanced_format:
  file: "src/components/UserProfile.tsx"
  changes:
    - type: "ADDED"
      lines: [45-67]
      code: |
        const handleSave = async () => {
          try {
            await updateUser(user.id, formData);
            toast.success("Profile updated");
          } catch (error) {
            toast.error("Failed to update");
          }
        };
      reason: "Add save handler with error handling"
    
    - type: "MODIFIED"
      line: 23
      old: "const [user, setUser] = useState<User>();"
      new: "const [user, setUser] = useState<User | null>(null);"
      reason: "Fix type safety - user can be null initially"
    
    - type: "REMOVED"
      lines: [80-85]
      code: "// Old authentication check"
      reason: "Replaced with new auth pattern from Pattern Registry"
  
  metadata:
    agent: "Coder"
    validation_passed: true
    fix_applied: false

usage:
  - Code review: see exactly what changed
  - Rollback: undo specific changes if needed
  - Learning: understand what changes were made and why
```

---

### **3.3 Validation Reports** ✅ (You have this - enhance)
```yaml
artifact_type: validation_report
purpose: Comprehensive validation results

enhanced_contents:
  file: "src/components/UserProfile.tsx"
  
  checks:
    - check: "No TODO/FIXME"
      passed: true
      scanned_lines: 150
    
    - check: "Error handling on async"
      passed: true
      async_functions_found: 3
      all_have_try_catch: true
    
    - check: "React anti-patterns"
      passed: false
      issues:
        - line: 67
          issue: "Missing key prop in .map()"
          severity: "HIGH"
          code: "users.map(u => <div>{u.name}</div>)"
          fix: "Add key={u.id}"
    
    - check: "Import validation"
      passed: true
      imports_checked: 12
      all_valid: true
    
    - check: "Type safety"
      passed: true
      any_count: 0
      typescript_errors: 0
  
  summary:
    total_checks: 15
    passed: 14
    failed: 1
    warnings: 0
    critical_issues: 0
    
  requires_fix: true
  fix_applied: true (by Fixer)

usage:
  - Quality assurance: comprehensive validation
  - Fix guidance: tells Fixer exactly what to fix
  - User confidence: show thoroughness of checks
```

---

### **3.4 Build Logs** ✅ (You have this - enhance)
```yaml
artifact_type: build_log
purpose: Real execution feedback

enhanced_contents:
  build_id: "build_001"
  timestamp: "2025-12-26T10:40:00Z"
  command: "npm run build"
  
  phases:
    - phase: "Dependency Installation"
      duration: "12.3s"
      status: "SUCCESS"
      output: "Added 247 packages"
    
    - phase: "TypeScript Compilation"
      duration: "8.7s"
      status: "SUCCESS"
      files_compiled: 156
      errors: 0
      warnings: 2
      warnings_list:
        - file: "src/lib/utils.ts"
          line: 23
          message: "Unused variable 'temp'"
    
    - phase: "Build"
      duration: "15.2s"
      status: "SUCCESS"
      bundle_size: "245 KB"
      output_files:
        - ".next/static/chunks/pages/index.js (45 KB)"
        - ".next/static/chunks/pages/profile.js (32 KB)"
  
  result: "SUCCESS"
  total_duration: "36.2s"
  
  performance:
    - metric: "First Contentful Paint"
      value: "1.2s"
      status: "GOOD"
    - metric: "Time to Interactive"
      value: "2.8s"
      status: "NEEDS IMPROVEMENT"

usage:
  - Debug build failures
  - Monitor build performance
  - Catch warnings that might cause issues
  - Verify output quality
```

---

### **3.5 Preview URLs** ✅ (You have this - enhance)
```yaml
artifact_type: preview_url
purpose: Live preview with metadata

enhanced_contents:
  url: "http://localhost:3000"
  status: "RUNNING"
  framework: "Next.js"
  hmr_enabled: true
  
  pages:
    - path: "/"
      status: "RENDERED"
      load_time: "1.2s"
      errors: []
    
    - path: "/profile"
      status: "RENDERED"
      load_time: "0.8s"
      errors: []
      notes: "New edit functionality working"
  
  runtime_errors: []
  console_warnings: 2
  console_warnings_list:
    - "Warning: Each child in a list should have a unique key prop"
      location: "UserProfile.tsx:67"
      # This matches validation report finding!
  
  health_check:
    api_reachable: true
    database_connected: true
    all_routes_working: true

usage:
  - User can immediately test changes
  - Correlate runtime errors with code locations
  - Verify app actually works, not just compiles
```

---

### **3.6 Error Knowledge Base** 🆕 IMPORTANT
```yaml
artifact_type: error_knowledge_base
purpose: Learn from errors for faster future fixes
created_by: Fixer
updated_by: Fixer (accumulates over time)
format: JSON

errors:
  - error_signature: "Cannot find module 'X'"
    category: "MISSING_DEPENDENCY"
    frequency: 12
    
    solutions:
      - solution: "Add package to package.json"
        success_rate: 0.95
        example:
          error: "Cannot find module 'lodash'"
          fix: "npm install lodash --save"
      
      - solution: "Fix import path"
        success_rate: 0.83
        example:
          error: "Cannot find module '@/components/Button'"
          fix: "Change to '@/components/ui/Button'"
  
  - error_signature: "TODO: implement X"
    category: "INCOMPLETE_CODE"
    frequency: 8
    
    solutions:
      - solution: "Implement the feature completely"
        success_rate: 0.9
        time_to_fix: "30s"
      
      - solution: "Extract to separate function"
        success_rate: 0.7
        time_to_fix: "45s"

usage:
  - Fixer checks this before attempting fix
  - Suggests most likely solution first
  - Learns from successful/failed fixes
  - Gets faster over time
```

**Why Important**: Agents get smarter with each project.

---

## **ARTIFACT RELATIONSHIPS**

```
App Blueprint
    ↓ guides
Planner
    ↓ creates
Plan Logs + Pattern Registry + Contract Definitions
    ↓ used by
Coder
    ↓ creates
Diffs + Code Files
    ↓ validated by
Validator + Dependency Resolver + Contract Validator
    ↓ creates
Validation Reports + Quality Gate Results
    ↓ used by
Fixer (if needed)
    ↓ creates
Fix History + Updated Code
    ↓ used by
Integration Agent
    ↓ creates
Integration Analysis + Dependency Graph
    ↓ triggers
Build System
    ↓ creates
Build Logs + Preview URLs
    ↓ monitored by
Orchestrator
    ↓ updates
Agent Conversation Log + Pitfall Coverage Matrix
```

---

## **ARTIFACT LIFECYCLE**

### **Created Once**
- App Blueprint
- Folder Map
- Data/State Schema
- Flow Diagram
- UI/UX Sketch

### **Created Per Task**
- Plan Logs
- Context Map
- Quality Gate Results
- Agent Conversation Log
- Diffs

### **Updated Continuously**
- Pattern Registry (as patterns evolve)
- Contract Definitions (as APIs change)
- Dependency Graph (as imports change)
- Fix History (accumulates over time)
- Error Knowledge Base (learns from mistakes)
- Pitfall Coverage Matrix (updated each validation)

### **Created Per Build**
- Build Logs
- Preview URLs
- Validation Reports

---

## **ARTIFACT STORAGE FORMAT**

```
project_root/
  .ships/                    # ShipS* artifacts directory
    planning/                # Layer 1: Planning
      app_blueprint.yaml
      folder_map.yaml
      data_schema.ts
      flows.yaml
      ui_sketches/
        *.png
    
    runtime/                 # Layer 2: Runtime Intelligence
      pattern_registry.json
      context_map.json       # Updated per task
      contracts.ts
      dependency_graph.json
      quality_gates.json     # Updated per task
      agent_log.json         # Append-only
      fix_history.json       # Append-only
      pitfall_matrix.json    # Updated per task
      error_kb.json          # Grows over time
    
    audit/                   # Layer 3: Audit Trail
      tasks/
        task_001/
          plan_log.json
          diffs/
            UserProfile.tsx.diff
          validation_reports/
            UserProfile.validation.json
          build_logs/
            build_001.json
          preview.json
      
      history/
        2025-12-26_task_summary.json
```

---

## **PRIORITY IMPLEMENTATION ORDER**

### **MVP (Week 1)**
1. ✅ App Blueprint (user provides)
2. ✅ Folder Map (user provides)
3. 🆕 **Pattern Registry** (CRITICAL - agents need this)
4. 🆕 **Contract Definitions** (CRITICAL - prevent API mismatch)
5. 🆕 **Quality Gate Results** (CRITICAL - enforce quality)
6. ✅ Plan Logs (audit)
7. ✅ Validation Reports (audit)
8. ✅ Diffs (audit)

### **Week 2**
9. 🆕 Context Map (efficiency)
10. 🆕 Dependency Graph (safety)
11. 🆕 Agent Conversation Log (transparency)
12. 🆕 Fix History (learning)
13. ✅ Build Logs (audit)
14. ✅ Preview URLs (testing)

### **Post-MVP**
15. 🆕 Pitfall Coverage Matrix (metrics)
16. 🆕 Error Knowledge Base (intelligence)
17. 🆕 Data/State Schema (optional input)
18. 🆕 Flow Diagram (optional input)
19. 🆕 UI/UX Sketch (optional input)

---

## **WHAT WAS MISSING FROM YOUR DESIGN**

### **Critical Gaps**
1. ❌ **Pattern Registry** → Agents had no way to ensure consistency
2. ❌ **Contract Definitions** → No single source of truth for APIs
3. ❌ **Dependency Graph** → Couldn't detect breaking changes
4. ❌ **Quality Gate Results** → No enforcement of quality standards
5. ❌ **Agent Conversation Log** → No transparency into agent decisions

### **Important Gaps**
6. ❌ **Context Map** → Token waste, context loss
7. ❌ **Fix History** → Couldn't learn from mistakes
8. ❌ **Pitfall Coverage Matrix** → No confidence metric
9. ❌ **Error Knowledge Base** → Fixed same errors repeatedly

---

## **ANSWER TO YOUR QUESTION**

**Is your original artifact system robust enough?**

**No, but it's a good start.**

**What you had:**
- ✅ Good planning artifacts (input)
- ✅ Good audit artifacts (output)
- ❌ **Missing the entire "Runtime Intelligence" layer**

**What you need to add:**
- 🆕 Pattern Registry (CRITICAL)
- 🆕 Contract Definitions (CRITICAL)
- 🆕 Dependency Graph (CRITICAL)
- 🆕 Quality Gate Results (CRITICAL)
- 🆕 Context Map (IMPORTANT)
- 🆕 Agent Conversation Log (IMPORTANT)
- 🆕 Fix History (NICE TO HAVE)
- 🆕 Pitfall Coverage Matrix (NICE TO HAVE)
- 🆕 Error Knowledge Base (NICE TO HAVE)

**The key insight:**
Artifacts aren't just for humans. **Agents need artifacts to coordinate with each other.** Without runtime artifacts, agents are blind to each other's work and can't maintain consistency.

**MVP Artifact System:**
1. App Blueprint (user)
2. Pattern Registry (agents)
3. Contract Definitions (agents)
4. Quality Gate Results (agents)
5. Plan Logs (audit)
6. Diffs (audit)
7. Validation Reports (audit)

**This gets you 80% of the value with 20% of the complexity.**