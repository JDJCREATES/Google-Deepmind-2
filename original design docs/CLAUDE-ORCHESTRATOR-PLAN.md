# Orchestrator Design: Critical Expansions

## What's Already Good ✅

The current document nails:
- Clear role boundaries (router, not thinker)
- Minimal tool set (4 core capabilities)
- Request Interpreter separation (prevents prompt drift)
- State machine approach (deterministic transitions)
- Anti-pattern warnings (don't make it reason)

**This foundation is solid.** But 3 areas need expansion based on your artifact + agent system:

---

## **EXPANSION 1: Quality Gates Integration** 🚨 CRITICAL

### The Gap
The document mentions "artifacts required before advancing" but doesn't connect this to your Quality Gate system from the artifact design.

### What's Missing
**HOW** the Orchestrator enforces quality gates at each state transition.

---

### Quality Gate Integration Model

```python
class OrchestratorStateMachine:
    def __init__(self):
        self.current_state = "IDLE"
        self.quality_gates = QualityGateRegistry()
        self.artifacts = ArtifactRegistry()
        self.fix_attempts = {}
    
    def transition(self, new_state, reason):
        """
        Transitions are GATED by quality checks.
        This is the enforcement mechanism.
        """
        # Check if current state's exit gate passes
        exit_gate = self.get_exit_gate(self.current_state)
        
        if not exit_gate.check():
            return self.handle_gate_failure(exit_gate)
        
        # Check if new state's entry gate passes
        entry_gate = self.get_entry_gate(new_state)
        
        if not entry_gate.check():
            return self.handle_gate_failure(entry_gate)
        
        # Only transition if both gates pass
        self.log_transition(self.current_state, new_state, reason)
        self.current_state = new_state
        return True
    
    def get_exit_gate(self, state):
        """Define what must be true to EXIT a state"""
        gates = {
            "PLANNED": QualityGate(
                name="Plan Quality",
                checks=[
                    ("plan_exists", self.artifacts.has("plan")),
                    ("plan_complete", self.validate_plan_completeness()),
                    ("patterns_extracted", self.artifacts.has("pattern_registry")),
                    ("contracts_defined", self.artifacts.has("contract_definitions"))
                ]
            ),
            "CODED": QualityGate(
                name="Code Quality",
                checks=[
                    ("validator_passed", self.artifacts.get("validation_report").passed),
                    ("deps_resolved", self.artifacts.get("dependency_check").passed),
                    ("no_todos", self.check_no_todos()),
                    ("imports_valid", self.check_imports())
                ]
            ),
            "VALIDATED": QualityGate(
                name="Integration Quality",
                checks=[
                    ("no_breaking_changes", self.artifacts.get("integration_check").passed),
                    ("contracts_match", self.artifacts.get("contract_validation").passed),
                    ("framework_rules", self.artifacts.get("framework_validation").passed)
                ]
            )
        }
        return gates.get(state, QualityGate.always_pass())
    
    def handle_gate_failure(self, gate):
        """
        This is where self-healing happens.
        CRITICAL: Max 3 attempts before escalation.
        """
        gate_id = gate.name
        
        # Initialize attempt counter
        if gate_id not in self.fix_attempts:
            self.fix_attempts[gate_id] = 0
        
        self.fix_attempts[gate_id] += 1
        
        # Hard limit: 3 attempts
        if self.fix_attempts[gate_id] > 3:
            return self.escalate_to_user(
                gate=gate,
                reason="Max fix attempts exceeded",
                attempts=self.fix_attempts[gate_id]
            )
        
        # Route to appropriate fixer
        return self.invoke_fixer(gate)
    
    def invoke_fixer(self, failed_gate):
        """
        Route failures to the right fixer based on what failed.
        """
        routing = {
            "validator_passed": ("Fixer", "validation_errors"),
            "deps_resolved": ("Dependency Resolver", "import_errors"),
            "contracts_match": ("Fixer", "contract_mismatches"),
            "no_breaking_changes": ("Integration Agent", "breaking_changes")
        }
        
        failed_checks = failed_gate.get_failed_checks()
        
        for check_name in failed_checks:
            agent, error_type = routing.get(check_name, ("Fixer", "general"))
            
            self.run_agent(
                agent_name=agent,
                inputs={
                    "error_type": error_type,
                    "failed_gate": failed_gate.name,
                    "artifacts": self.artifacts.get_relevant(error_type)
                },
                expected_outputs=["fixed_files", "fix_report"]
            )
        
        # Re-validate after fix
        if failed_gate.recheck():
            self.fix_attempts[failed_gate.name] = 0  # Reset counter on success
            return True
        
        return False  # Fix didn't work, will retry or escalate
```

---

### State Transition Examples with Gates

```python
# Example 1: Happy path - PLANNED → CODED
orchestrator.current_state = "PLANNED"

# User requests coding
result = orchestrator.transition("CODED", "user_requested_implementation")

# What happens:
# 1. Check exit gate for PLANNED state
#    - plan_exists ✅
#    - plan_complete ✅
#    - patterns_extracted ✅
#    - contracts_defined ✅
# 2. Exit gate PASSES
# 3. Invoke Coder with artifacts
# 4. Coder produces code
# 5. Check entry gate for CODED state
#    - (entry gates validate the OUTPUT of the transition action)
# 6. State = CODED
```

```python
# Example 2: Gate failure - CODED → VALIDATED
orchestrator.current_state = "CODED"

result = orchestrator.transition("VALIDATED", "code_generation_complete")

# What happens:
# 1. Check exit gate for CODED state
#    - validator_passed ❌ (found 2 TODOs)
#    - deps_resolved ✅
#    - no_todos ❌ (duplicate check, failed)
#    - imports_valid ✅
# 2. Exit gate FAILS
# 3. invoke_fixer(gate) called
# 4. Fixer addresses TODO issues
# 5. Gate rechecks
#    - validator_passed ✅ (TODOs implemented)
#    - no_todos ✅
# 6. Exit gate PASSES on retry
# 7. State = VALIDATED
```

```python
# Example 3: Max attempts exceeded
orchestrator.current_state = "CODED"
orchestrator.fix_attempts["Code Quality"] = 3

result = orchestrator.transition("VALIDATED", "retry_after_fixes")

# What happens:
# 1. Check exit gate for CODED state
#    - validator_passed ❌ (still failing)
# 2. Exit gate FAILS
# 3. handle_gate_failure() checks attempts
# 4. Attempts = 4 (exceeds max)
# 5. escalate_to_user() called
# 6. User sees:
#    "Code Quality gate failed after 3 fix attempts.
#     Issues: [list of still-failing checks]
#     Last error: [validation report]
#     Suggest: Review Validator prompt or manual intervention"
```

---

### Why This Matters

Without explicit gate integration, the Orchestrator becomes a "vibes-based" router. With gates:

✅ **Deterministic**: Every transition has clear pass/fail criteria
✅ **Self-healing**: Failed gates trigger automatic fixes
✅ **Fail-safe**: Max attempts prevents infinite loops
✅ **Auditable**: Every gate result is logged
✅ **Explainable**: Users see exactly why progress stopped

This is **the** mechanism that makes ShipS* different from Bolt/Cursor.

---

## **EXPANSION 2: Artifact Flow Protocol** 🔄 CRITICAL

### The Gap
You defined all artifacts and all agents, but not the **handoff protocol** between agents.

### What's Missing
**HOW** artifacts flow from one agent to the next. Without this, agents will fetch wrong/stale artifacts.

---

### Artifact Flow Protocol

```python
class ArtifactRegistry:
    """
    Single source of truth for all artifacts.
    Agents NEVER access files directly - they go through this.
    """
    
    def __init__(self, project_path):
        self.project_path = project_path
        self.artifacts = {}
        self.versions = {}
        self.locks = {}
    
    def register(self, artifact_type, data, produced_by):
        """
        Register a new artifact version.
        Immutable - creates new version, doesn't modify.
        """
        if artifact_type not in self.versions:
            self.versions[artifact_type] = []
        
        version = len(self.versions[artifact_type]) + 1
        
        artifact = {
            "type": artifact_type,
            "version": version,
            "data": data,
            "produced_by": produced_by,
            "timestamp": datetime.now().isoformat(),
            "hash": hashlib.sha256(str(data).encode()).hexdigest()
        }
        
        self.artifacts[artifact_type] = artifact
        self.versions[artifact_type].append(artifact)
        
        return artifact
    
    def get(self, artifact_type, version="latest"):
        """
        Retrieve artifact by type.
        Always returns specific version (no ambiguity).
        """
        if artifact_type not in self.artifacts:
            raise ArtifactNotFound(f"Artifact {artifact_type} does not exist")
        
        if version == "latest":
            return self.artifacts[artifact_type]
        
        if version <= len(self.versions[artifact_type]):
            return self.versions[artifact_type][version - 1]
        
        raise ArtifactVersionNotFound(f"Version {version} of {artifact_type} not found")
    
    def lock(self, artifact_type, agent_name):
        """
        Lock artifact for modification.
        Prevents concurrent modification race conditions.
        """
        if artifact_type in self.locks:
            raise ArtifactLocked(f"{artifact_type} locked by {self.locks[artifact_type]}")
        
        self.locks[artifact_type] = agent_name
    
    def unlock(self, artifact_type, agent_name):
        """
        Release lock after modification.
        """
        if self.locks.get(artifact_type) != agent_name:
            raise UnauthorizedUnlock(f"{agent_name} doesn't own lock on {artifact_type}")
        
        del self.locks[artifact_type]
    
    def get_dependencies(self, artifact_type):
        """
        Return which artifacts this artifact depends on.
        Critical for invalidation cascades.
        """
        dependencies = {
            "plan": ["app_blueprint", "pattern_registry"],
            "code": ["plan", "pattern_registry", "contract_definitions"],
            "validation_report": ["code"],
            "dependency_graph": ["code"],
            "integration_check": ["code", "dependency_graph"],
            "build_log": ["code", "validation_report", "integration_check"]
        }
        return dependencies.get(artifact_type, [])
    
    def invalidate(self, artifact_type):
        """
        Mark artifact as stale.
        Also invalidates all dependents (cascade).
        """
        if artifact_type in self.artifacts:
            self.artifacts[artifact_type]["status"] = "stale"
        
        # Cascade to dependents
        for atype, deps in self.get_dependencies_map().items():
            if artifact_type in deps:
                self.invalidate(atype)
```

---

### Agent Invocation with Artifact Protocol

```python
class Orchestrator:
    def run_agent(self, agent_name, inputs, expected_outputs):
        """
        Run an agent with strict artifact contracts.
        """
        # 1. Validate all input artifacts exist and are fresh
        for artifact_type in inputs.get("required_artifacts", []):
            if not self.artifacts.has(artifact_type):
                raise MissingArtifact(f"{agent_name} requires {artifact_type}")
            
            if self.artifacts.get(artifact_type).get("status") == "stale":
                raise StaleArtifact(f"{artifact_type} is stale, regenerate first")
        
        # 2. Lock artifacts this agent will modify
        for artifact_type in expected_outputs:
            self.artifacts.lock(artifact_type, agent_name)
        
        try:
            # 3. Fetch input artifacts (specific versions, immutable)
            agent_inputs = {
                "artifacts": {
                    atype: self.artifacts.get(atype)
                    for atype in inputs.get("required_artifacts", [])
                },
                "parameters": inputs.get("parameters", {})
            }
            
            # 4. Run agent
            result = self.invoke_agent(agent_name, agent_inputs)
            
            # 5. Validate outputs match expectations
            for artifact_type in expected_outputs:
                if artifact_type not in result.get("artifacts", {}):
                    raise MissingOutput(f"{agent_name} didn't produce {artifact_type}")
            
            # 6. Register new artifact versions
            for artifact_type, data in result.get("artifacts", {}).items():
                self.artifacts.register(
                    artifact_type=artifact_type,
                    data=data,
                    produced_by=agent_name
                )
            
            # 7. Unlock artifacts
            for artifact_type in expected_outputs:
                self.artifacts.unlock(artifact_type, agent_name)
            
            return result
            
        except Exception as e:
            # Unlock on failure
            for artifact_type in expected_outputs:
                if artifact_type in self.artifacts.locks:
                    self.artifacts.unlock(artifact_type, agent_name)
            raise
```

---

### Example: Complete Flow with Artifacts

```python
# User: "Add user profile editing"

# Step 1: Request Interpreter
orchestrator.run_agent(
    agent_name="Request Interpreter",
    inputs={
        "required_artifacts": ["app_blueprint"],
        "parameters": {"user_request": "Add user profile editing"}
    },
    expected_outputs=["structured_intent"]
)
# Produces: structured_intent artifact

# Step 2: Planner
orchestrator.run_agent(
    agent_name="Planner",
    inputs={
        "required_artifacts": [
            "app_blueprint",
            "folder_map",
            "structured_intent"
        ],
        "parameters": {}
    },
    expected_outputs=["plan", "pattern_registry", "contract_definitions"]
)
# Produces: plan (v3), pattern_registry (v1), contract_definitions (v2)

# Step 3: Context Selector
orchestrator.run_agent(
    agent_name="Context Selector",
    inputs={
        "required_artifacts": ["plan", "folder_map", "dependency_graph"],
        "parameters": {}
    },
    expected_outputs=["context_map"]
)
# Produces: context_map (v15)

# Step 4: Coder
orchestrator.run_agent(
    agent_name="Coder",
    inputs={
        "required_artifacts": [
            "plan",
            "context_map",
            "pattern_registry",
            "contract_definitions"
        ],
        "parameters": {}
    },
    expected_outputs=["code_changes", "diffs"]
)
# Produces: code_changes (v48), diffs (v48)

# Step 5: Validator
orchestrator.run_agent(
    agent_name="Validator",
    inputs={
        "required_artifacts": ["code_changes"],
        "parameters": {}
    },
    expected_outputs=["validation_report"]
)
# Produces: validation_report (v52)

# If validation fails:
if not orchestrator.artifacts.get("validation_report")["passed"]:
    # Step 6: Fixer
    orchestrator.run_agent(
        agent_name="Fixer",
        inputs={
            "required_artifacts": [
                "code_changes",
                "validation_report",
                "context_map"
            ],
            "parameters": {}
        },
        expected_outputs=["code_changes", "fix_report"]
    )
    # Produces: code_changes (v49), fix_report (v1)
    
    # Re-validate
    # (repeat Step 5 with new code_changes v49)
```

---

### Why This Matters

Without a strict artifact protocol:

❌ Agents fetch stale artifacts
❌ Race conditions on concurrent edits
❌ No audit trail of what changed when
❌ Can't rollback to previous versions
❌ Debugging is impossible ("which version did Fixer see?")

With the protocol:

✅ **Immutable versions**: Every artifact version is preserved
✅ **Dependency tracking**: Know what invalidates what
✅ **Locking**: Prevent concurrent modification
✅ **Auditability**: Complete history of artifact evolution
✅ **Rollback**: Can revert to any previous version

---

## **EXPANSION 3: Error Recovery Paths** 🛠️ IMPORTANT

### The Gap
The document says "escalate to user" but doesn't specify the recovery paths for each failure type.

### What's Missing
A decision tree for **when to retry, when to escalate, when to give up**.

---

### Error Recovery Decision Tree

```python
class ErrorRecoverySystem:
    """
    Determines recovery strategy based on error type.
    """
    
    def __init__(self):
        self.recovery_strategies = {
            # CATEGORY 1: Auto-fixable (always retry)
            "VALIDATION_FAILED": {
                "strategy": "FIX_AND_RETRY",
                "max_attempts": 3,
                "agent": "Fixer",
                "escalate_after": 3
            },
            "IMPORT_ERROR": {
                "strategy": "FIX_AND_RETRY",
                "max_attempts": 3,
                "agent": "Dependency Resolver",
                "escalate_after": 3
            },
            "TYPE_MISMATCH": {
                "strategy": "FIX_AND_RETRY",
                "max_attempts": 3,
                "agent": "Fixer",
                "escalate_after": 3
            },
            
            # CATEGORY 2: Sometimes fixable (limited retry)
            "BUILD_FAILED": {
                "strategy": "ANALYZE_AND_FIX",
                "max_attempts": 2,
                "agent": "Fixer",
                "escalate_after": 2
            },
            "CONTRACT_MISMATCH": {
                "strategy": "SYNC_AND_RETRY",
                "max_attempts": 2,
                "agent": "Contract Validator + Fixer",
                "escalate_after": 2
            },
            
            # CATEGORY 3: Rarely fixable (one retry, then escalate)
            "BREAKING_CHANGE": {
                "strategy": "REVERT_OR_UPDATE",
                "max_attempts": 1,
                "agent": "Integration Agent",
                "escalate_after": 1,
                "user_decision_required": True
            },
            "CIRCULAR_DEPENDENCY": {
                "strategy": "REFACTOR_REQUIRED",
                "max_attempts": 1,
                "agent": "Integration Agent",
                "escalate_after": 1,
                "user_decision_required": True
            },
            
            # CATEGORY 4: Never auto-fix (immediate escalation)
            "AMBIGUOUS_REQUEST": {
                "strategy": "CLARIFY_WITH_USER",
                "max_attempts": 0,
                "escalate_immediately": True
            },
            "MISSING_BLUEPRINT": {
                "strategy": "REQUEST_INPUT",
                "max_attempts": 0,
                "escalate_immediately": True
            },
            "TIMEOUT": {
                "strategy": "ESCALATE",
                "max_attempts": 0,
                "escalate_immediately": True,
                "reason": "Operation took too long"
            }
        }
    
    def handle_error(self, error_type, context):
        """
        Route error to appropriate recovery strategy.
        """
        strategy = self.recovery_strategies.get(
            error_type,
            {
                "strategy": "ESCALATE",
                "max_attempts": 0,
                "escalate_immediately": True,
                "reason": "Unknown error type"
            }
        )
        
        # Check if immediate escalation
        if strategy.get("escalate_immediately"):
            return self.escalate(error_type, context, strategy)
        
        # Check attempt count
        attempts = context.get("attempts", 0)
        
        if attempts >= strategy["max_attempts"]:
            return self.escalate(error_type, context, strategy)
        
        # Try recovery
        return self.attempt_recovery(error_type, context, strategy)
    
    def attempt_recovery(self, error_type, context, strategy):
        """
        Execute recovery strategy.
        """
        strategy_map = {
            "FIX_AND_RETRY": self.fix_and_retry,
            "ANALYZE_AND_FIX": self.analyze_and_fix,
            "SYNC_AND_RETRY": self.sync_and_retry,
            "REVERT_OR_UPDATE": self.revert_or_update,
            "REFACTOR_REQUIRED": self.refactor
        }
        
        handler = strategy_map.get(strategy["strategy"], self.escalate)
        return handler(error_type, context, strategy)
    
    def fix_and_retry(self, error_type, context, strategy):
        """
        Simple fix loop: invoke Fixer, re-validate, retry.
        """
        agent = strategy["agent"]
        
        # Invoke fixer
        fix_result = orchestrator.run_agent(
            agent_name=agent,
            inputs={
                "required_artifacts": context["artifacts"],
                "parameters": {
                    "error": context["error"],
                    "error_type": error_type
                }
            },
            expected_outputs=["fixed_code", "fix_report"]
        )
        
        # Re-validate
        validation = orchestrator.validate_current_state()
        
        if validation.passed:
            return {"status": "RECOVERED", "attempts": context["attempts"] + 1}
        
        return {"status": "RETRY", "attempts": context["attempts"] + 1}
    
    def escalate(self, error_type, context, strategy):
        """
        Escalate to user with clear explanation and options.
        """
        return {
            "status": "ESCALATED",
            "error_type": error_type,
            "message": self.build_user_message(error_type, context, strategy),
            "options": self.get_user_options(error_type, context),
            "artifacts": self.get_relevant_artifacts(error_type, context)
        }
    
    def build_user_message(self, error_type, context, strategy):
        """
        Generate clear, actionable error message for user.
        """
        templates = {
            "VALIDATION_FAILED": """
                Code validation failed after {attempts} attempts.
                
                Issues found:
                {issues}
                
                What happened:
                {explanation}
                
                Suggested actions:
                1. Review the validation report (see artifacts)
                2. Manually fix the issues
                3. Or adjust validation rules if they're too strict
            """,
            "BREAKING_CHANGE": """
                The requested change would break existing code.
                
                Impact:
                {impact}
                
                Affected files:
                {affected_files}
                
                Options:
                1. Update all affected files (may be risky)
                2. Revert this change and try a different approach
                3. Manually review and decide
            """,
            "AMBIGUOUS_REQUEST": """
                I need more information to proceed.
                
                Your request: "{request}"
                
                What's unclear:
                {ambiguities}
                
                Please clarify:
                {questions}
            """
        }
        
        template = templates.get(error_type, "An error occurred: {error}")
        return template.format(**context)
    
    def get_user_options(self, error_type, context):
        """
        Provide actionable options for user.
        """
        options = {
            "VALIDATION_FAILED": [
                {"action": "manual_fix", "label": "Let me fix it manually"},
                {"action": "retry_with_changes", "label": "Try again with adjusted rules"},
                {"action": "skip_validation", "label": "Skip this validation (not recommended)"}
            ],
            "BREAKING_CHANGE": [
                {"action": "update_dependents", "label": "Update all affected files automatically"},
                {"action": "revert", "label": "Revert this change"},
                {"action": "review", "label": "Show me the changes and let me decide"}
            ],
            "BUILD_FAILED": [
                {"action": "view_logs", "label": "Show me the build logs"},
                {"action": "retry", "label": "Try building again"},
                {"action": "reset", "label": "Start over with this feature"}
            ]
        }
        
        return options.get(error_type, [
            {"action": "view_details", "label": "Show me more details"},
            {"action": "abort", "label": "Stop and let me fix this"}
        ])
```

---

### Recovery Examples

```python
# Example 1: Auto-fixable error (validation)
error = {
    "type": "VALIDATION_FAILED",
    "context": {
        "attempts": 1,
        "error": "TODO found at line 42",
        "artifacts": ["code", "validation_report"]
    }
}

result = error_recovery.handle_error(error["type"], error["context"])
# Result: Invokes Fixer, retries validation
# If fails again: retry (max 3 times)
# After 3 failures: escalate to user

# Example 2: Sometimes fixable (build failure)
error = {
    "type": "BUILD_FAILED",
    "context": {
        "attempts": 1,
        "error": "TypeScript error: Cannot find name 'User'",
        "artifacts": ["code", "build_log"]
    }
}

result = error_recovery.handle_error(error["type"], error["context"])
# Result: Analyzes build log, identifies missing import
# Invokes Fixer to add import
# Retries build
# Max 2 attempts, then escalate

# Example 3: Requires user decision (breaking change)
error = {
    "type": "BREAKING_CHANGE",
    "context": {
        "attempts": 0,
        "impact": "Changing User interface affects 12 files",
        "affected_files": ["UserProfile.tsx", "UserCard.tsx", ...],
        "artifacts": ["integration_check"]
    }
}

result = error_recovery.handle_error(error["type"], error["context"])
# Result: IMMEDIATE escalation
# Shows user impact analysis
# Offers options: update all, revert, or manual review
# Waits for user decision

# Example 4: Immediate escalation (ambiguous request)
error = {
    "type": "AMBIGUOUS_REQUEST",
    "context": {
        "attempts": 0,
        "request": "make it better",
        "ambiguities": ["What specifically should be improved?"],
        "artifacts": []
    }
}

result = error_recovery.handle_error(error["type"], error["context"])
# Result: IMMEDIATE escalation
# Asks user for clarification
# No auto-fix attempts
```

---

### Why This Matters

Without structured error recovery:

❌ Orchestrator doesn't know when to stop trying
❌ Wastes tokens on unfixable errors
❌ Users see cryptic "something failed" messages
❌ No clear path forward after failure

With structured recovery:

✅ **Smart retries**: Only retry errors that are actually fixable
✅ **Clear escalation**: Users know exactly what went wrong
✅ **Actionable options**: Users get specific choices, not vague messages
✅ **Efficiency**: Don't waste attempts on unfixable errors
✅ **Learning**: Track which errors are auto-fixable vs require human help

---

## **SUMMARY: What to Add to Orchestrator Doc**

### Priority 1 (Must Add)
1. **Quality Gate Integration** (CRITICAL)
   - How gates connect to state transitions
   - Gate failure → Fixer invocation logic
   - Max attempts enforcement

2. **Artifact Flow Protocol** (CRITICAL)
   - Immutable artifact versions
   - Lock/unlock mechanism
   - Dependency tracking and invalidation

### Priority 2 (Should Add)
3. **Error Recovery Paths** (IMPORTANT)
   - Decision tree for error types
   - When to retry vs escalate
   - User escalation messages and options

### What NOT to Add
- More agent implementation details (belongs in agent specs)
- Prompt engineering techniques (belongs in agent prompts)
- UI/UX details (out of scope for orchestrator)
- Business logic (belongs in agents)

---

## **FINAL ANSWER**

**The orchestrator document is 80% there, but needs these 3 expansions:**

1. **Connect Quality Gates to state transitions** (without this, gates are just documentation)
2. **Define the artifact handoff protocol** (without this, agents will use stale/wrong data)
3. **Specify error recovery decision trees** (without this, it will waste attempts on unfixable errors)

**Everything else in the document is intentionally minimal and correct.**

The document correctly avoids:
- Making the orchestrator "think"
- Dynamic prompting in the orchestrator
- Business logic in the orchestrator

It correctly delegates:
- Request interpretation → Request Interpreter
- Code generation → Coder
- Validation → Validators
- Fixes → Fixer

**Add those 3 expansions and the orchestrator design is production-ready.**