## LLM Application Coding PITFALLS

## **COMPLETE PITFALL TAXONOMY**

### **CATEGORY 1: CODE COMPLETENESS** ⚠️ CRITICAL

**Pitfall 1.1: TODO/FIXME Placeholders**
- LLM writes `// TODO: implement auth` instead of real code
- **Severity:** HIGH (non-functional code)
- **Detection:** Regex scan for TODO, FIXME, PLACEHOLDER
- **Prevention:** Coder prompt: "NEVER use placeholders"
- **Fix:** Fixer agent implements the TODO

**Pitfall 1.2: Truncated Code**
- Response cuts off mid-function due to token limits
- **Severity:** CRITICAL (syntax errors, won't run)
- **Detection:** Check for unclosed brackets, incomplete functions
- **Prevention:** Break large files into smaller chunks
- **Fix:** Fixer completes the truncated section

**Pitfall 1.3: Stub Implementations**
- Empty catch blocks: `catch(e) {}`
- Mock data instead of real logic
- **Severity:** HIGH (appears to work but doesn't)
- **Detection:** Check for empty blocks, mock data patterns
- **Prevention:** Coder prompt rules
- **Fix:** Fixer implements proper logic

---

### **CATEGORY 2: CONTEXT LOSS** 🧠 CRITICAL

**Pitfall 2.1: Inconsistent Naming**
- File 1 uses `userId`, File 10 uses `user_id`
- **Severity:** HIGH (runtime errors, maintenance nightmare)
- **Detection:** Pattern Detector mini-agent
- **Prevention:** Planner extracts naming conventions first
- **Fix:** Fixer standardizes naming

**Pitfall 2.2: Duplicate Definitions**
- Defines `User` interface twice with different fields
- **Severity:** HIGH (type conflicts, confusion)
- **Detection:** Check for duplicate type/interface names
- **Prevention:** Planner maps existing types
- **Fix:** Fixer consolidates definitions

**Pitfall 2.3: Ignores Existing Code**
- Generates API endpoint that already exists
- Duplicates utility functions
- **Severity:** MEDIUM (bloat, confusion)
- **Detection:** Context Selector checks for duplicates
- **Prevention:** Planner analyzes existing codebase first
- **Fix:** Integration Agent deduplicates

**Pitfall 2.4: Forgets Earlier Decisions**
- Architecture choice in file 1 contradicted in file 10
- **Severity:** HIGH (architectural inconsistency)
- **Detection:** Pattern Detector validates consistency
- **Prevention:** Spec document enforced throughout
- **Fix:** Refactor to match original decision

---

### **CATEGORY 3: BREAKING CHANGES** 💥 CRITICAL

**Pitfall 3.1: Modifies Shared Types**
- Changes interface used by 10 other files
- **Severity:** CRITICAL (breaks entire app)
- **Detection:** Dependency graph analysis
- **Prevention:** Integration Agent checks impact
- **Fix:** Update all dependents OR revert change

**Pitfall 3.2: Changes API Contracts**
- Backend changes response shape, frontend not updated
- **Severity:** CRITICAL (runtime failures)
- **Detection:** Contract Validator
- **Prevention:** Planner defines contracts upfront
- **Fix:** Sync frontend/backend changes

**Pitfall 3.3: Removes Used Functions**
- Deletes function still called elsewhere
- **Severity:** CRITICAL (immediate crashes)
- **Detection:** Dependency graph + static analysis
- **Prevention:** Check references before deletion
- **Fix:** Restore function OR update callers

---

### **CATEGORY 4: ARCHITECTURAL INCONSISTENCY** 🏗️ HIGH

**Pitfall 4.1: Mixed Async Patterns**
- Some files use async/await, others use .then()
- **Severity:** MEDIUM (maintainability issue)
- **Detection:** Pattern Detector
- **Prevention:** Enforce pattern from Planner spec
- **Fix:** Standardize to one pattern

**Pitfall 4.2: Inconsistent State Management**
- Mix of Context API, props drilling, Redux
- **Severity:** MEDIUM (confusing, hard to maintain)
- **Detection:** Pattern Detector
- **Prevention:** Planner specifies state strategy
- **Fix:** Refactor to single approach

**Pitfall 4.3: Wrong Abstraction Level**
- Business logic in UI components
- Database queries in frontend
- **Severity:** HIGH (security, maintainability)
- **Detection:** File classification + heuristics
- **Prevention:** Planner enforces separation of concerns
- **Fix:** Extract to proper layer

**Pitfall 4.4: Over-Engineering**
- Design patterns for simple tasks
- 10 files for 1 function
- **Severity:** MEDIUM (complexity, hard to understand)
- **Detection:** Complexity metrics
- **Prevention:** Coder prompt: "simplest solution"
- **Fix:** Refactor Agent simplifies

---

### **CATEGORY 5: MISSING CRITICAL CODE** 🚨 CRITICAL

**Pitfall 5.1: No Error Handling**
- API calls without try/catch
- No validation on inputs
- **Severity:** CRITICAL (crashes, security)
- **Detection:** Validator checks for try/catch around async
- **Prevention:** Coder prompt rules
- **Fix:** Fixer adds error handling

**Pitfall 5.2: Missing Loading States**
- Components assume data always present
- **Severity:** HIGH (poor UX, crashes)
- **Detection:** Check for loading flags in async components
- **Prevention:** Coder prompt checklist
- **Fix:** Fixer adds loading states

**Pitfall 5.3: No Null Checks**
- Accesses properties without checking existence
- **Severity:** HIGH (runtime crashes)
- **Detection:** Check for `?.` usage, null guards
- **Prevention:** Coder uses optional chaining
- **Fix:** Fixer adds null checks

**Pitfall 5.4: Missing Security**
- No input sanitization
- SQL injection vulnerabilities
- Exposed secrets
- **Severity:** CRITICAL (security breaches)
- **Detection:** Security patterns scan
- **Prevention:** Coder security checklist
- **Fix:** Security Agent (post-MVP) OR Fixer

**Pitfall 5.5: No Type Safety**
- Uses `any` everywhere
- No prop validation
- **Severity:** MEDIUM (loses TypeScript benefits)
- **Detection:** Count `any` usage
- **Prevention:** Coder avoids `any`
- **Fix:** Fixer adds proper types

---

### **CATEGORY 6: IMPORT/DEPENDENCY HELL** 📦 HIGH

**Pitfall 6.1: Wrong Import Paths**
- `import { Button } from '@/components/Button'` doesn't exist
- Relative paths wrong
- **Severity:** HIGH (won't compile)
- **Detection:** Monaco + Dependency Resolver
- **Prevention:** Validate imports against file list
- **Fix:** Fixer corrects paths

**Pitfall 6.2: Missing Dependencies**
- Uses lodash without package.json entry
- **Severity:** HIGH (install fails)
- **Detection:** Dependency Resolver
- **Prevention:** Check package.json before generating
- **Fix:** Add to package.json

**Pitfall 6.3: Circular Dependencies**
- File A imports B, B imports A
- **Severity:** HIGH (runtime errors)
- **Detection:** Dependency graph analysis
- **Prevention:** BLOCK generation if detected
- **Fix:** Refactor to break cycle

**Pitfall 6.4: Missing Peer Dependencies**
- React component without React
- **Severity:** HIGH (install warnings/errors)
- **Detection:** Check peer dependencies
- **Prevention:** Include peer deps
- **Fix:** Add missing peers

---

### **CATEGORY 7: RUNTIME ERRORS** 🐛 HIGH

**Pitfall 7.1: Type Mismatches**
- Passes string where number expected
- **Severity:** HIGH (crashes)
- **Detection:** Monaco TypeScript analysis
- **Prevention:** Coder follows types
- **Fix:** Fixer corrects types

**Pitfall 7.2: Async Race Conditions**
- State updates out of order
- **Severity:** HIGH (data corruption)
- **Detection:** ❌ HARD (needs runtime)
- **Prevention:** Code review patterns (ACCEPT GAP)
- **Fix:** Manual user testing

**Pitfall 7.3: Memory Leaks**
- Event listeners not removed
- useEffect without cleanup
- **Severity:** MEDIUM (performance degradation)
- **Detection:** Pattern matching (missing cleanup)
- **Prevention:** Coder checklist
- **Fix:** Fixer adds cleanup

**Pitfall 7.4: Undefined Function Calls**
- Calls function that doesn't exist
- **Severity:** CRITICAL (immediate crash)
- **Detection:** Monaco + static analysis
- **Prevention:** Validate function exists
- **Fix:** Implement function OR fix call

---

### **CATEGORY 8: INTEGRATION FAILURES** 🔌 CRITICAL

**Pitfall 8.1: API Contract Mismatches**
- Frontend expects `userId`, backend sends `user_id`
- **Severity:** CRITICAL (data doesn't flow)
- **Detection:** Contract Validator
- **Prevention:** Planner defines contracts
- **Fix:** Sync frontend/backend

**Pitfall 8.2: Wrong HTTP Methods**
- POST when should be GET
- **Severity:** HIGH (requests fail)
- **Detection:** API pattern validation
- **Prevention:** Follow REST conventions
- **Fix:** Correct HTTP method

**Pitfall 8.3: CORS Issues**
- Missing CORS headers
- **Severity:** HIGH (requests blocked)
- **Detection:** Check for CORS middleware
- **Prevention:** Include CORS setup
- **Fix:** Add CORS config

**Pitfall 8.4: Environment Variables**
- Hardcoded localhost URLs
- Missing .env handling
- **Severity:** HIGH (breaks in production)
- **Detection:** Check for hardcoded URLs
- **Prevention:** Use environment variables
- **Fix:** Replace with env vars

---

### **CATEGORY 9: BUILD/DEPLOY ISSUES** 🚀 HIGH

**Pitfall 9.1: Missing Build Config**
- No tsconfig.json
- Missing build scripts
- **Severity:** HIGH (can't build)
- **Detection:** Check for required config files
- **Prevention:** Include all configs
- **Fix:** Generate missing configs

**Pitfall 9.2: Wrong File Paths**
- Import paths break in production
- **Severity:** HIGH (builds locally, fails deployed)
- **Detection:** Path validation
- **Prevention:** Use relative/absolute correctly
- **Fix:** Correct paths

**Pitfall 9.3: Missing .env.example**
- No documentation of required env vars
- **Severity:** MEDIUM (setup confusion)
- **Detection:** Check for .env.example
- **Prevention:** Always generate .env.example
- **Fix:** Create from .env usage

---

### **CATEGORY 10: FRAMEWORK-SPECIFIC** ⚛️ HIGH

**Pitfall 10.1: React Anti-Patterns**
- Mutating state directly
- Missing keys in lists
- Hooks in conditionals
- **Severity:** HIGH (bugs, warnings)
- **Detection:** Framework Validator
- **Prevention:** Follow React rules
- **Fix:** Apply correct patterns

**Pitfall 10.2: Next.js Confusion**
- Client code in Server Components
- Missing "use client" directive
- **Severity:** HIGH (won't work)
- **Detection:** Framework Validator
- **Prevention:** Detect component type
- **Fix:** Add directives OR move code

**Pitfall 10.3: Wrong Data Fetching**
- Using useEffect when should use getServerSideProps
- **Severity:** MEDIUM (performance/UX)
- **Detection:** Pattern validation
- **Prevention:** Use framework conventions
- **Fix:** Refactor to correct method

---

### **CATEGORY 11: DATABASE ISSUES** 🗄️ HIGH

**Pitfall 11.1: Schema Mismatches**
- Queries fields that don't exist
- **Severity:** CRITICAL (queries fail)
- **Detection:** Schema Validator
- **Prevention:** Validate against schema
- **Fix:** Correct queries OR update schema

**Pitfall 11.2: Missing Indexes**
- Queries without indexes (slow)
- **Severity:** MEDIUM (performance)
- **Detection:** Query analysis
- **Prevention:** Add indexes for queries
- **Fix:** Migration to add indexes

**Pitfall 11.3: SQL Injection**
- String concatenation in queries
- **Severity:** CRITICAL (security)
- **Detection:** SQL injection patterns
- **Prevention:** Use parameterized queries
- **Fix:** Rewrite with parameters

**Pitfall 11.4: Missing Transactions**
- Operations that should be atomic aren't
- **Severity:** HIGH (data corruption)
- **Detection:** Multi-step operation analysis
- **Prevention:** Wrap in transactions
- **Fix:** Add transaction wrapper

---

### **CATEGORY 12: CODE QUALITY** 📝 MEDIUM

**Pitfall 12.1: Massive Functions**
- 500-line functions
- **Severity:** MEDIUM (hard to maintain)
- **Detection:** Cyclomatic complexity check
- **Prevention:** Break into smaller functions
- **Fix:** Refactor Agent

**Pitfall 12.2: Code Duplication**
- Same logic repeated
- **Severity:** MEDIUM (DRY violation)
- **Detection:** Similarity analysis
- **Prevention:** Extract to utilities
- **Fix:** Refactor Agent

**Pitfall 12.3: Poor Naming**
- Variables named `data`, `temp`, `x`
- **Severity:** LOW (readability)
- **Detection:** Name quality heuristics
- **Prevention:** Descriptive names
- **Fix:** Rename variables

**Pitfall 12.4: Missing Comments**
- Complex logic unexplained
- **Severity:** LOW (maintainability)
- **Detection:** Complexity without comments
- **Prevention:** Comment complex sections
- **Fix:** Documentation Agent

---

### **CATEGORY 13: PERFORMANCE** ⚡ MEDIUM

**Pitfall 13.1: Inefficient Algorithms**
- O(n²) when O(n) possible
- **Severity:** MEDIUM (slowness)
- **Detection:** Algorithm analysis
- **Prevention:** Suggest efficient algorithms
- **Fix:** Performance Agent

**Pitfall 13.2: N+1 Queries**
- Fetches in loop
- **Severity:** HIGH (database hammering)
- **Detection:** Loop with DB calls inside
- **Prevention:** Batch operations
- **Fix:** Rewrite with joins/batch

**Pitfall 13.3: No Memoization**
- Expensive calculations every render
- **Severity:** MEDIUM (performance)
- **Detection:** React performance patterns
- **Prevention:** Add useMemo/useCallback
- **Fix:** Add memoization

**Pitfall 13.4: Bundle Size**
- Imports entire library for one function
- **Severity:** MEDIUM (slow loading)
- **Detection:** Import analysis
- **Prevention:** Tree-shakeable imports
- **Fix:** Import specific functions

---

### **CATEGORY 14: EDGE CASES** 🎯 MEDIUM

**Pitfall 14.1: Empty States**
- Doesn't handle empty arrays, null
- **Severity:** MEDIUM (crashes/bad UX)
- **Detection:** Check for empty checks
- **Prevention:** Always handle empty
- **Fix:** Add empty state handling

**Pitfall 14.2: Off-by-One Errors**
- Array index mistakes
- **Severity:** HIGH (wrong data)
- **Detection:** ❌ HARD (needs tests)
- **Prevention:** Careful index math
- **Fix:** Test and correct

**Pitfall 14.3: Timezone Issues**
- Assumes user timezone
- **Severity:** MEDIUM (wrong times)
- **Detection:** Hardcoded timezone usage
- **Prevention:** Use UTC, convert locally
- **Fix:** Proper timezone handling

**Pitfall 14.4: Special Characters**
- Breaks on quotes, apostrophes
- **Severity:** MEDIUM (data corruption)
- **Detection:** No sanitization
- **Prevention:** Escape/sanitize inputs
- **Fix:** Add sanitization

---

### **CATEGORY 15: META-ISSUES** 🤖 CRITICAL

**Pitfall 15.1: Hallucinated APIs**
- Invents functions that don't exist
- **Severity:** CRITICAL (won't work)
- **Detection:** Validate against real APIs
- **Prevention:** Dependency Resolver checks
- **Fix:** Replace with real APIs

**Pitfall 15.2: Outdated Patterns**
- Uses deprecated APIs
- Old React patterns
- **Severity:** MEDIUM (technical debt)
- **Detection:** Pattern matching against modern standards
- **Prevention:** Train on current best practices
- **Fix:** Update to modern patterns

**Pitfall 15.3: Framework Confusion**
- Mixes React and Vue syntax
- **Severity:** CRITICAL (won't compile)
- **Detection:** Framework Validator
- **Prevention:** Enforce single framework
- **Fix:** Correct to target framework

---

## **PITFALL PRIORITY MATRIX**

### **TIER 1: MUST CATCH (MVP)** - 15 Pitfalls
```
1.1 TODO Placeholders → Validator
1.2 Truncated Code → Completeness check
2.1 Inconsistent Naming → Pattern Detector
3.1 Breaking Changes → Dependency graph
3.2 API Contract Mismatch → Contract Validator
5.1 No Error Handling → Validator
5.3 No Null Checks → Validator
6.1 Wrong Import Paths → Monaco + Dependency Resolver
6.2 Missing Dependencies → Dependency Resolver
6.3 Circular Dependencies → Dependency Resolver
7.1 Type Mismatches → Monaco
8.1 API Contract Mismatch → Contract Validator
10.1 React Anti-Patterns → Framework Validator
11.1 Schema Mismatches → Schema Validator
15.1 Hallucinated APIs → Dependency Resolver
```

### **TIER 2: SHOULD CATCH (Post-MVP)** - 15 Pitfalls
```
1.3 Stub Implementations → Enhanced Validator
2.3 Ignores Existing Code → Context awareness
4.1 Mixed Patterns → Pattern Enforcer
4.3 Wrong Abstraction → Architecture review
5.2 Missing Loading States → UI pattern check
5.4 Security Issues → Security Agent
7.3 Memory Leaks → Pattern check
9.1 Missing Build Config → Config generator
10.2 Next.js Issues → Framework Validator
11.2 Missing Indexes → Performance Agent
11.3 SQL Injection → Security Agent
12.1 Massive Functions → Refactor Agent
12.2 Code Duplication → Refactor Agent
13.2 N+1 Queries → Performance Agent
14.1 Empty States → Edge case handler
```

### **TIER 3: NICE TO CATCH (Future)** - 15 Pitfalls
```
2.4 Forgets Decisions → Long-context tracking
4.2 State Management Mix → Refactor Agent
4.4 Over-Engineering → Complexity analysis
5.5 Type Safety → Stricter typing
7.2 Race Conditions → ❌ Accept gap
9.2 Wrong Paths → Deployment validator
12.3 Poor Naming → Style enforcer
12.4 Missing Comments → Documentation Agent
13.1 Inefficient Algorithms → Performance Agent
13.3 No Memoization → Performance Agent
13.4 Bundle Size → Build optimizer
14.2 Off-by-One → ❌ Needs tests
14.3 Timezone Issues → i18n Agent
14.4 Special Characters → Input sanitizer
15.2 Outdated Patterns → Pattern updater
```

---

## **COVERAGE BY AGENT/TOOL**

| Agent/Tool | Pitfalls Covered | Coverage % |
|------------|------------------|------------|
| **Validator (Mini)** | 8 pitfalls | 18% |
| **Monaco** | 5 pitfalls | 11% |
| **Pattern Detector** | 6 pitfalls | 13% |
| **Dependency Resolver** | 6 pitfalls | 13% |
| **Contract Validator** | 2 pitfalls | 4% |
| **Framework Validator** | 4 pitfalls | 9% |
| **Fixer Agent** | 25 pitfalls | 56% |
| **Integration Agent** | 3 pitfalls | 7% |
| **Refactor Agent** | 4 pitfalls | 9% |
| **Security Agent** | 3 pitfalls | 7% |
| **Performance Agent** | 5 pitfalls | 11% |

---

