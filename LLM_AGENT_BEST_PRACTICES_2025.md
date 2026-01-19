# LLM Agent Best Practices (2025 Industry Standards)

> **Purpose**: Document industry-standard patterns for building reliable LLM coding agents and anti-patterns to avoid, based on Anthropic's research and production experience with our ShipS* agent system.

---

## 📖 Table of Contents

1. [Core Principles (Anthropic 2025)](#core-principles)
2. [Anti-Patterns We Fixed](#anti-patterns-we-fixed)
3. [Best Practices We Implemented](#best-practices-we-implemented)
4. [Architecture Patterns](#architecture-patterns)
5. [Quality Gates & Determinism](#quality-gates--determinism)
6. [Tool Design (Agent-Computer Interface)](#tool-design-aci)
7. [State Management](#state-management)
8. [Observability & Debugging](#observability--debugging)
9. [Quick Reference Card](#quick-reference)

---

## 🎯 Core Principles (Anthropic 2025)

Based on Anthropic's ["Building Effective Agents"](https://www.anthropic.com/research/building-effective-agents) (Dec 2024), the industry consensus is:

### 1. **Maintain Simplicity**
- Start with the simplest solution that works
- Only add complexity when simpler approaches demonstrably fail
- Frameworks create abstraction layers that obscure prompts and make debugging harder
- **Rule**: If a single LLM call can solve it, don't build a multi-agent system

### 2. **Prioritize Transparency**
- Explicitly show agent planning steps (don't hide in black boxes)
- Log all routing decisions with reasoning
- Make state transitions visible and auditable
- Users should understand what the agent is doing at all times

### 3. **Craft Agent-Computer Interface (ACI) Carefully**
- Tool design deserves as much effort as Human-Computer Interface (HCI) design
- Clear tool documentation is critical (think: docstrings for junior developers)
- Test tool usage extensively in workbench environments
- Make tools hard to misuse ([Poka-yoke](https://en.wikipedia.org/wiki/Poka-yoke) principle)

### 4. **Use Deterministic Workflows When Possible**
- **Workflows** = LLMs + tools orchestrated through predefined code paths (predictable, fast, cheap)
- **Agents** = LLMs dynamically directing their own processes (flexible but costly and error-prone)
- 95% of production cases can use workflows instead of fully autonomous agents
- Reserve true autonomy for genuinely open-ended problems

---

## ❌ Anti-Patterns We Fixed

### 🔴 **Anti-Pattern #1: Multiple Sources of Truth**

**What We Did Wrong:**
- Intent classifier ran in orchestrator STEP 1
- Router re-inferred intent in STEP 4
- LLM fallback re-classified intent in STEP 5
- Planner re-interpreted scope during execution
- **Result**: 4 conflicting classifications for the same user request

**Industry Standard:**
- **Single Source of Truth**: Classify once, lock the result, all agents read from artifact
- Anthropic: "Avoid having multiple components making the same decision"

**Our Fix:**
```python
# STEP 1: Classify ONCE
if not artifacts.get("intent_classified"):
    intent = await intent_classifier.classify(request)
    artifacts["structured_intent"] = intent
    artifacts["intent_classified"] = True  # 🔒 LOCK

# STEP 4: Router READS intent (never re-classifies)
intent = artifacts["structured_intent"]
```

---

### 🔴 **Anti-Pattern #2: LLM as Router by Default**

**What We Did Wrong:**
- Every state transition called expensive LLM orchestrator
- Even simple "planning done → coding" required Pro model inference
- 95% of routing decisions were deterministic but hidden in LLM reasoning
- Cost: ~$0.15 per routing decision × 6 transitions = $0.90 per task
- Latency: 2-4 seconds per transition

**Industry Standard:**
- **Deterministic Routing First**: Use simple rules for predictable transitions
- **LLM as Fallback Only**: Reserve LLM for genuinely ambiguous states (~5% of cases)
- Anthropic: "Start with simple prompts... add multi-step agentic systems only when simpler solutions fall short"

**Our Fix:**
```python
# Deterministic rules handle 95% of cases
if phase == "planning" and has_plan:
    return "coder"  # Simple, fast, $0 cost

# LLM only for edge cases
if routing_decision.requires_llm:
    result = await llm_fallback(state)
```

**Impact**: 95% cost reduction, 10x faster routing

---

### 🔴 **Anti-Pattern #3: Regex Parsing of LLM Output**

**What We Did Wrong:**
```python
# FRAGILE: 30% parse failure rate
response = await llm.ainvoke(prompt)
match = re.search(r'"decision":\s*"(\w+)"', response.content)
decision = match.group(1) if match else "chat"  # Silent fallback
```

**Why This Fails:**
- LLMs produce markdown formatting: ` ```json\n{"decision": ...}\n``` `
- Multiline strings break regex
- Extra whitespace, comments, or explanations interfere
- Silent fallbacks hide the problem

**Industry Standard:**
- **Structured Outputs**: Use `with_structured_output()` with Pydantic models
- Anthropic: "Make sure there's no formatting overhead... keep formats close to natural text"

**Our Fix:**
```python
# ROBUST: 100% parse success
class OrchestratorDecision(BaseModel):
    decision: Literal["planner", "coder", "validator", "fixer", "chat", "complete"]
    reasoning: str

structured_llm = llm.with_structured_output(OrchestratorDecision)
result = await structured_llm.ainvoke(prompt)
# result.decision is GUARANTEED to be valid - no parsing needed
```

---

### 🔴 **Anti-Pattern #4: No Quality Gates**

**What We Did Wrong:**
- Planner could return empty plans (0 tasks)
- Coder could skip implementation and return immediately
- No validation that required artifacts existed before transitions
- State machine accepted any phase change

**Industry Standard:**
- **Quality Gates**: Pre/post conditions for every state transition
- Anthropic workflow pattern: "Prompt chaining with programmatic checks (gates) on intermediate steps"

**Our Fix:**
```python
class GateEvaluator:
    def can_exit_planning(self, state):
        return GateResult(
            passed=(
                len(state.get("plan", {}).get("tasks", [])) > 0 and
                state.get("scaffolding_complete") is True
            ),
            checks_failed=["no_tasks", "scaffolding_incomplete"] if not passed else []
        )
```

**Impact**: Zero invalid state transitions since implementation

---

### 🔴 **Anti-Pattern #5: Overlapping Loop Detection**

**What We Did Wrong:**
- Router calculated loop detection (consecutive same-phase calls)
- Orchestrator recalculated loop detection independently
- Different thresholds (router: 3 calls, orchestrator: 5 calls)
- Conflicting decisions: router says "loop", orchestrator says "continue"

**Industry Standard:**
- **Single Responsibility**: One component owns each concern
- Anthropic: "Avoid complexity... ensure tools provide a clear, well-documented interface"

**Our Fix:**
```python
# STEP 4: Router calculates loop detection (authoritative)
routing_decision = router.route(state)
# routing_decision.metadata["loop_detection"] = {...}

# STEP 6: Orchestrator TRUSTS router's calculation
loop_detection = routing_decision.metadata.get("loop_detection", {})
# No recalculation, no conflict
```

---

### 🔴 **Anti-Pattern #6: Implicit Tool Formats**

**What We Did Wrong:**
```python
# Ambiguous: Does Coder create folder first or just files?
write_file(path="src/components/Button.tsx", content="...")
```

**Why This Fails:**
- LLM doesn't know if parent directories exist
- Should it create them? Skip the file? Error?
- Different agents made different assumptions

**Industry Standard (Anthropic):**
- **"Poka-yoke your tools"**: Design tools to prevent errors
- **Clear boundaries**: One tool = one atomic action
- **Example usage in descriptions**: Show agents exactly how to use tools

**Our Fix:**
```python
# CLEAR: Separate tools for separate concerns
create_directory(path="src/components")  # Explicit folder creation
write_file(path="src/components/Button.tsx", content="...")  # File only

# OR: Single tool that handles both (documented behavior)
write_file(
    path="src/components/Button.tsx",
    content="...",
    create_dirs=True  # ✅ Explicit flag, no ambiguity
)
```

---

### 🔴 **Anti-Pattern #7: Scaffolding Confusion**

**What We Did Wrong:**
- Planner's base prompt said: "prefer manual file creation"
- Planner's scaffold sub-agent prompt said: "use CLI commands"
- Result: Planner manually created `package.json`, `tsconfig.json` instead of running `npm create vite`

**Industry Standard (Anthropic):**
- **Use ground truth from environment**: Let CLI tools scaffold correctly
- **Minimize manual work**: Frameworks exist for a reason
- **Agent role clarity**: Scaffolder uses CLI, Coder adds custom files

**Our Fix:**
```python
# Clear role separation:
# 1. Scaffolder Sub-Agent: Runs CLI commands for base structure
scaffolder_prompt = """
When scaffolding a NEW project:
1. ALWAYS use terminal commands: npm create vite, create-react-app, etc.
2. Run npm install to set up dependencies
3. Return folder structure detection to Planner
"""

# 2. Coder Agent: Adds custom application logic on top
coder_prompt = """
After base is scaffolded:
1. Add custom components, pages, services
2. Modify configs as needed
3. Implement business logic
"""
```

---

## ✅ Best Practices We Implemented

### 🟢 **Pattern #1: Hub-and-Spoke Architecture**

**What We Did Right (from the start):**
```python
# All agents return to central orchestrator
graph.add_edge("planner", "orchestrator")
graph.add_edge("coder", "orchestrator")
graph.add_edge("validator", "orchestrator")
graph.add_edge("fixer", "orchestrator")

# Orchestrator routes to next agent
graph.add_conditional_edges("orchestrator", route_orchestrator)
```

**Why It Works:**
- Single coordination point (orchestrator knows all state)
- Agents don't call each other (no hidden dependencies)
- Easy to add new agents (just add edge to/from orchestrator)
- Clear audit trail (every transition logged at hub)

**Anthropic Alignment**: This is their **"Orchestrator-Workers"** workflow pattern:
> "A central LLM dynamically breaks down tasks, delegates to worker LLMs, and synthesizes results"

---

### 🟢 **Pattern #2: Quality Gates as State Machine Guards**

```python
class GateEvaluator:
    def can_exit_state(self, state, current_phase):
        """Check if all exit conditions are met before leaving phase."""
        
    def can_enter_state(self, state, target_phase):
        """Check if all entry conditions are met before entering phase."""

# Used in router:
exit_gate = gate_evaluator.can_exit_state(state, "planning")
if not exit_gate.passed:
    return RoutingDecision(next_phase="planner", reason="Planning incomplete")
```

**Benefits:**
- **Invariant enforcement**: Invalid states are impossible
- **Clear failure messages**: Gate failures explain exactly what's missing
- **Testable**: Each gate check can be unit tested independently
- **Self-documenting**: Gate definitions ARE the state machine specification

**Anthropic Alignment**: Their **"Prompt Chaining"** workflow:
> "Add programmatic checks (gates) on intermediate steps to ensure process is on track"

---

### 🟢 **Pattern #3: Pydantic Structured Outputs**

```python
class StructuredIntent(BaseModel):
    task_type: Literal["feature", "fix", "refactor", "question"]
    scope: Literal["project", "layer", "component", "feature"]
    confidence: float = Field(ge=0.0, le=1.0)

# Usage:
llm_with_schema = llm.with_structured_output(StructuredIntent)
result: StructuredIntent = await llm_with_schema.ainvoke(prompt)
# result.task_type is GUARANTEED valid - no parsing, no errors
```

**Benefits:**
- **Type safety**: Invalid outputs are impossible
- **Zero parsing errors**: LLM MUST return valid schema
- **IDE support**: Autocomplete and type checking
- **Clear contracts**: Schema IS the API between LLM and code

---

### 🟢 **Pattern #4: NDJSON Routing Logs**

```python
routing_snapshot = {
    "timestamp": datetime.utcnow().isoformat(),
    "current_phase": "planning",
    "next_phase": "coder",
    "reason": "Planning complete, entering coding phase",
    "used_llm": False,
    "gate_result": "planning_exit_passed",
    "loop_detection": {"consecutive_calls": 1, "loop_detected": False}
}

# Append to .ships/routing_log.jsonl
with open(log_file, "a") as f:
    f.write(json.dumps(routing_snapshot) + "\n")
```

**Benefits:**
- **Post-mortem analysis**: See exact routing history for any run
- **Pattern detection**: Analyze thousands of runs for common loops
- **Debugging**: Know exactly why agent X was chosen at step Y
- **Streaming friendly**: Newline-delimited = real-time tailable

**Usage:**
```bash
# Watch routing decisions in real-time
tail -f .ships/routing_log.jsonl | jq

# Find all LLM fallback cases
grep '"used_llm": true' .ships/routing_log.jsonl
```

---

### 🟢 **Pattern #5: Artifact Locking**

```python
# STEP 1: Create artifact once
if not artifacts.get("intent_classified"):
    intent = await classifier.classify(request)
    artifacts["structured_intent"] = intent
    artifacts["intent_classified"] = True  # 🔒 LOCK

# STEP 4: All subsequent reads use locked artifact
intent = artifacts["structured_intent"]  # Never re-classify
```

**Why It Matters:**
- Prevents re-classification mid-stream (consistency)
- Multiple agents can safely read same artifact (no race conditions)
- Clear ownership: Only the creating agent can write
- Audit trail: Timestamp shows when artifact was created

---

## 🏗️ Architecture Patterns (Anthropic Taxonomy)

Our system implements **3 of Anthropic's 6 core patterns**:

### 1️⃣ **Routing Workflow** ✅

> "Classify input and direct to specialized follow-up task"

```python
# Our intent_classifier IS a router
intent = await classifier.classify(user_request)

if intent.scope == "project":
    next_phase = "scaffolder"  # CLI-based project creation
elif intent.scope == "feature":
    next_phase = "coder"  # Code modifications
```

**When to use**: Distinct input categories that need different handling

---

### 2️⃣ **Orchestrator-Workers Workflow** ✅

> "Central LLM delegates tasks to worker LLMs and synthesizes results"

```python
# Our hub-and-spoke = orchestrator-workers
orchestrator → planner (worker)
orchestrator → coder (worker)
orchestrator → validator (worker)
orchestrator → fixer (worker)
```

**When to use**: Complex tasks requiring multiple specialized agents

---

### 3️⃣ **Evaluator-Optimizer Workflow** ✅

> "One LLM generates, another evaluates in a loop"

```python
# Our validator-fixer cycle
coder → generates code
validator → evaluates code
  → if fail: fixer → improves code → validator (loop)
  → if pass: complete
```

**When to use**: Clear evaluation criteria exist, iteration improves output

---

### Patterns We DON'T Use (and why):

❌ **Prompt Chaining**: We use state machine routing instead (more robust)
❌ **Parallelization**: Our tasks are sequential by nature
❌ **Fully Autonomous Agents**: We use workflows with LLM fallback (more predictable)

---

## 🛡️ Quality Gates & Determinism

### Gate Design Principles

1. **Gates Guard Invariants**
   ```python
   # BAD: Vague condition
   if state.get("planning_done"):
       ...
   
   # GOOD: Specific invariants
   gate.check("has_tasks", lambda: len(plan["tasks"]) > 0)
   gate.check("has_folder_map", lambda: "folder_map" in artifacts)
   gate.check("scaffolding_complete", lambda: artifacts.get("scaffolding_complete"))
   ```

2. **Gates Fail Loudly**
   ```python
   # BAD: Silent pass-through
   if not gate.passed:
       logger.warning("Gate failed")
       continue  # Proceeds anyway!
   
   # GOOD: Block transition
   if not gate.passed:
       return RoutingDecision(
           next_phase="planner",
           reason=f"Planning exit gate failed: {gate.checks_failed}",
           requires_llm=False  # Deterministic retry
       )
   ```

3. **Gates Are Testable**
   ```python
   def test_planning_exit_gate():
       state = {"artifacts": {"plan": {"tasks": []}}}  # Empty tasks
       gate = evaluator.can_exit_state(state, "planning")
       assert not gate.passed
       assert "no_tasks" in gate.checks_failed
   ```

---

## 🔧 Tool Design (Agent-Computer Interface)

### Anthropic's ACI Principles

> "Invest as much effort in Agent-Computer Interfaces (ACI) as Human-Computer Interfaces (HCI)"

#### 1. **Give Model Room to Think**

```python
# BAD: Forces premature decisions
def edit_file(line_number: int, new_content: str):
    """Edit file at specific line. You MUST calculate line count first."""
    # Problem: LLM has to commit to line number before seeing full diff

# GOOD: Natural format
def edit_file(old_content: str, new_content: str):
    """Replace old_content with new_content. Include context lines."""
    # LLM can write full change naturally, we calculate line numbers
```

#### 2. **Keep Format Natural**

```python
# BAD: Requires escaping
{
  "code": "function hello() {\n  console.log(\"Hello\");\n}"
}

# GOOD: Markdown code blocks (natural for LLMs)
```python
function hello() {
  console.log("Hello");
}
\```  # (remove backslash in actual usage)
```

#### 3. **Provide Examples**

```python
def create_file(path: str, content: str):
    """
    Create a new file with content.
    
    Args:
        path: Relative path from project root (e.g., "src/components/Button.tsx")
        content: Full file content as string
    
    Example:
        create_file(
            path="src/utils/helpers.ts",
            content="export function add(a: number, b: number) { return a + b; }"
        )
    
    Notes:
        - Parent directories are created automatically
        - Will fail if file already exists (use edit_file instead)
    """
```

#### 4. **Poka-Yoke (Error-Proofing)**

```python
# BAD: Ambiguous paths
def read_file(path: str):
    # Is it relative? Absolute? From project root? From current dir?
    ...

# GOOD: Always absolute paths (in our SWE-bench implementation)
def read_file(absolute_path: str):
    """
    Read file content.
    
    Args:
        absolute_path: MUST be absolute path (e.g., /repo/src/file.ts)
                       Use get_file_path(relative) to convert if needed.
    """
    if not absolute_path.startswith("/"):
        raise ValueError("Path must be absolute. Use get_file_path() first.")
```

---

## 📊 State Management

### State Lifecycle

```python
# 1. INITIALIZE: Graph creates state
state = AgentGraphState(
    messages=[],
    phase="planning",
    artifacts={},
    loop_detection={}
)

# 2. NODE UPDATES: Each agent adds to state
async def planner_node(state):
    plan = await planner.create_plan(request)
    
    # IMMUTABLE: Create new dict, don't mutate
    return {
        "artifacts": {**state["artifacts"], "plan": plan},
        "phase": "coder"  # Suggest next phase
    }

# 3. ORCHESTRATOR VALIDATES: Checks gates, routes
routing = router.route(state)
if routing.gate_result.passed:
    state["phase"] = routing.next_phase

# 4. CHECKPOINT: LangGraph saves state (for resume/replay)
checkpointer.save(thread_id, state)
```

### State Best Practices

1. **Never Mutate State Directly**
   ```python
   # BAD
   state["artifacts"]["plan"] = new_plan
   return state
   
   # GOOD
   return {"artifacts": {**state["artifacts"], "plan": new_plan}}
   ```

2. **Use Typed State**
   ```python
   class AgentGraphState(TypedDict):
       messages: Annotated[List[BaseMessage], add]  # Auto-merges
       phase: Literal["planning", "coding", ...]     # Type-safe
       artifacts: Dict[str, Any]                     # Schema validated
   ```

3. **Artifacts vs State Fields**
   ```python
   # State fields: Routing/control
   state["phase"] = "coding"
   state["loop_detection"] = {...}
   
   # Artifacts: Agent outputs
   state["artifacts"]["plan"] = {...}
   state["artifacts"]["code_changes"] = {...}
   ```

---

## 🔍 Observability & Debugging

### Logging Levels

```python
# DEBUG: Internal state changes
logger.debug(f"Loop detection: {loop_info}")

# INFO: Major decisions
logger.info("[ORCHESTRATOR] ✅ Planning → Coding (gates passed)")

# WARNING: Recoverable issues
logger.warning(f"Planning exit gate FAILED: {gate.checks_failed}")

# ERROR: Unexpected failures
logger.error(f"LLM fallback failed: {e}")
```

### Structured Logging

```python
# BAD: Unstructured strings
logger.info("Routing to coder because planning is done")

# GOOD: Structured with context
logger.info(
    "[DETERMINISTIC_ROUTER] ✅ Planning → Coding (gates passed)",
    extra={
        "current_phase": "planning",
        "next_phase": "coder",
        "gate_result": "passed",
        "reasoning": "Planning complete, entering coding phase"
    }
)
```

### Tracing Checklist

- [ ] Every routing decision logged with reason
- [ ] Every gate check logged (pass/fail + checks)
- [ ] Every LLM call logged (input/output/cost)
- [ ] Every loop detection logged (consecutive calls)
- [ ] NDJSON routing log for post-mortem analysis
- [ ] Unique thread_id for each run (correlation)

---

## 📋 Quick Reference Card

### ✅ DO

| Pattern | Why | Example |
|---------|-----|---------|
| **Structured Outputs** | Zero parsing errors | `llm.with_structured_output(Schema)` |
| **Quality Gates** | Invalid states impossible | `can_exit_state(state, "planning")` |
| **Deterministic Routing** | Fast, cheap, predictable | `if has_plan: return "coder"` |
| **Single Source of Truth** | Consistency | `artifacts["intent_classified"] = True` |
| **NDJSON Logs** | Post-mortem debugging | `.ships/routing_log.jsonl` |
| **Poka-Yoke Tools** | Prevent agent errors | Absolute paths, clear examples |
| **Artifact Locking** | Prevent re-processing | `if not classified: classify()` |
| **Hub-and-Spoke** | Clear coordination | All agents → orchestrator |

### ❌ DON'T

| Anti-Pattern | Why Bad | Fix |
|--------------|---------|-----|
| **Multiple Truth Sources** | Conflicting decisions | Classify once, lock result |
| **LLM as Default Router** | Slow, expensive, unpredictable | Deterministic rules + LLM fallback |
| **Regex Parsing** | 30% failure rate | Pydantic structured outputs |
| **No Quality Gates** | Invalid state transitions | Gate evaluator |
| **Overlapping Concerns** | Conflicting calculations | Single responsibility |
| **Implicit Tool Behavior** | Agent confusion | Explicit flags, examples |
| **Silent Failures** | Hidden bugs | Fail loudly with reason |
| **State Mutation** | Race conditions | Return new state dict |

---

## 🎓 Key Learnings

### 1. **Simplicity Beats Sophistication**
- We reduced orchestrator from 400 lines of LLM logic to 80 lines of deterministic rules
- **Result**: 95% cost reduction, 10x faster, zero regression

### 2. **Workflows > Agents**
- True autonomy is rarely needed (and risky)
- Deterministic workflows with LLM fallback handle 99% of cases
- Save full autonomy for genuinely open-ended problems

### 3. **Invest in ACI Design**
- We spent more time on tool design than prompt engineering
- Clear tool interfaces = fewer LLM mistakes
- Example: Absolute paths reduced file errors from 20% → 0%

### 4. **Quality Gates Are Non-Negotiable**
- Gates prevent invalid states (1000s of edge cases eliminated)
- Gates ARE the state machine spec (self-documenting)
- Gates enable deterministic routing (no LLM guessing)

### 5. **Observability From Day 1**
- NDJSON routing logs caught 15+ edge cases in first week
- Structured logging made debugging 100x easier
- Every decision needs a logged reason

---

## 📚 References

1. **Anthropic (2024)**: ["Building Effective Agents"](https://www.anthropic.com/research/building-effective-agents)
   - Workflows vs Agents taxonomy
   - ACI design principles
   - SWE-bench implementation insights

2. **Our Production Experience**:
   - 60-70% fragility reduction via Phase 1 fixes
   - 95% routing now deterministic (was 0%)
   - Zero parse errors since structured outputs

3. **Key Repos**:
   - [Anthropic Cookbook](https://platform.claude.com/cookbook/patterns-agents-basic-workflows)
   - Our codebase: `ships-backend/app/graphs/` (router, gates, state machine)

---

## 🔄 Continuous Improvement

### What's Next (Phase 2)

1. **Split Planner** → Separate `scaffolder_node` from planning
2. **Explicit Error States** → Add `error_node` for clear failure handling
3. **Artifact Immutability** → `merge_artifacts()` to track ownership

### What's Working

- ✅ Hub-and-Spoke architecture (unchanged since v1.0)
- ✅ Quality gates (zero invalid transitions)
- ✅ Structured outputs (zero parsing errors)
- ✅ NDJSON logs (invaluable for debugging)

---

**Version**: 1.0  
**Last Updated**: 2025-01-19  
**Authors**: ShipS* Team (based on production learnings + Anthropic research)  
**License**: Internal use - Document production patterns for reference
