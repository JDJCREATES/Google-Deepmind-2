# UI Message Issues - Fixes Applied

## Issues Identified

1. **Intent JSON showing in UI** - Structured intent object being displayed as text
2. **Messages losing styling after stream ends** - Messages transfer to basic divs
3. **Messages not clearing between runs** - Chat persists when starting new run
4. **run_id None crash** - preview_manager fails with AttributeError

---

## Fixes Applied

### 1. Fixed run_id None Crash (CRITICAL)

**File:** `ships-backend/app/graphs/agent_graph.py`

**Problem:** `complete_node` tried to call `preview_manager.get_or_start(run_id, project_path)` but `run_id` was `None`

**Fix:**
```python
run_id = artifacts.get("run_id")

# CRITICAL FIX: run_id can be None if not set - generate fallback
if not run_id:
    import uuid
    run_id = str(uuid.uuid4())
    logger.warning(f"[COMPLETE] run_id was None - generated fallback: {run_id}")
```

**Impact:** Prevents crash at completion, allows preview to start

---

### 2. Added Message Clearing on New Run

**File:** `prism-frontend/prism-ai-web/src/store/streamingStore.ts`

**Problem:** `resetStreaming()` kept tool events and terminal output between runs

**Fix:**
```typescript
resetStreaming: () => 
  set({ 
    toolEvents: [], // CLEAR tool events on new run (was kept before)
    agentPhase: 'idle', 
    currentActivity: '',
    activityType: 'thinking',
    awaitingConfirmation: false,
    planSummary: '',
    terminalOutput: '', // CLEAR terminal too (was kept before)
  }),
```

**Impact:** Clean slate for each new run

---

### 3. Intent JSON Still Showing - Root Cause Analysis

**What's happening:**
From the logs, you can see:
```
2026-01-19 20:45:18 - ships.intent - INFO - [INTENT] 📋 Classified: feature/create → frontend | scope: project (conf: 1.00)
```

This is just a LOG entry, not streamed to frontend. But the screenshot shows formatted JSON output like:
```json
{
  "requires_database": false,
  "requires_api": false,
  "is_ambiguous": false,
  "clarification_questions": [],
  "assumptions": [
    "User wants a client-side only todo app...",
    "Standard Vite + React boilerplate..."
  ],
  "confidence": 1.0
}
```

**Where is this coming from?**

The intent classifier uses `structured_output`, so it should NOT be streaming tokens. However, the orchestrator node might be logging or emitting it.

**Check needed:**
1. Is orchestrator_node emitting intent as a message?
2. Is planner prompt including intent in its reasoning output?
3. Is there a debug/reasoning block that includes the full intent?

**Likely culprit:**
Line in `agent_graph.py` around 665:
```python
structured_intent_obj = await intent_agent.classify(...)
```

This runs the intent classifier, which might be streaming its structured output before converting to dict.

**Solution needed:**
Add intent classifier to `suppress_streaming_for` set in pipeline.py to block token streaming from it.

---

### 4. Messages Losing Styling After Stream - Analysis

**Problem:**
Messages appear styled during streaming but become basic divs afterward.

**Root Cause:**
Frontend is likely:
1. Rendering messages differently during active stream vs. after completion
2. Using different component for "streaming" vs "completed" messages
3. Not persisting the block structure (thinking, code, command blocks)

**Where to look:**
- `AgentDashboard.tsx` line 130-170: block handling logic
- `RunCard` component: how it renders completed vs streaming blocks
- Message component: might have different render paths for `isStreaming` flag

**Likely issue:**
When stream ends, blocks are collapsed/merged into plain text instead of preserving their structure and styling.

**Solution needed:**
1. Ensure `block.isComplete = true` preserves block type and styling
2. Add CSS classes that work for both streaming and completed states
3. Save block structure to message when stream ends, don't just concat text

---

### 5. Messages Not Persisting Locally - Analysis

**Current State:**
- Messages are stored in `useAgentRuns` hook state
- No local storage persistence
- Messages lost on page refresh

**Solution Needed:**
Add Zustand persist middleware to message store:

```typescript
// In hooks/useAgentRuns.ts or a new messageStore.ts
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface MessageStore {
  messages: Record<string, ChatMessage[]>; // runId -> messages
  addMessage: (runId: string, message: ChatMessage) => void;
  clearMessages: (runId: string) => void;
}

export const useMessageStore = create<MessageStore>()(
  persist(
    (set) => ({
      messages: {},
      addMessage: (runId, message) =>
        set((state) => ({
          messages: {
            ...state.messages,
            [runId]: [...(state.messages[runId] || []), message]
          }
        })),
      clearMessages: (runId) =>
        set((state) => ({
          messages: {
            ...state.messages,
            [runId]: []
          }
        }))
    }),
    {
      name: 'message-storage', // localStorage key
      partialize: (state) => ({ messages: state.messages }),
    }
  )
);
```

This would persist messages across page refreshes without DB cost.

---

## Remaining Work

### HIGH PRIORITY:

1. **Filter Intent JSON from UI**
   - Add intent_classifier to suppress_streaming set
   - OR: Add filter in orchestrator_node to not emit intent as reasoning block
   - OR: Frontend filter to skip blocks with type "intent" or containing JSON schema

2. **Fix Message Styling Persistence**
   - Investigate RunCard/ChatMessage components
   - Ensure block.isComplete preserves CSS classes
   - Don't merge blocks into plain text on completion

3. **Add Message Local Storage**
   - Create messageStore with persist middleware
   - Hook up to AgentDashboard message rendering
   - Clear on explicit user action (not auto-clear)

### MEDIUM PRIORITY:

4. **Clear Messages UI Control**
   - Add "Clear Chat" button to RunCard
   - Calls clearMessages(runId) from store
   - Shows confirmation dialog

5. **Message Export**
   - "Export Chat" button
   - Downloads messages as markdown or JSON
   - Useful for debugging/sharing

---

## Testing Checklist

- [ ] Start new run → messages clear (tool events + terminal)
- [ ] Intent JSON NOT visible in chat
- [ ] Message blocks keep styling after stream ends
- [ ] Page refresh preserves messages (local storage)
- [ ] run_id None doesn't crash preview start
- [ ] Thinking/code/command blocks render consistently
- [ ] Clear Chat button works

---

## Notes

**Why messages were persisting:**
`resetStreaming()` was keeping `toolEvents` intentionally with comment "Keep toolEvents - they should persist for the run". This caused confusion - they persisted BETWEEN runs, not just during a single run.

**Why styling was lost:**
Need to investigate component code, but likely:
- StreamBlock components only render during active stream
- Completed messages use different render path (plain div)
- CSS classes change based on `isStreaming` boolean

**Why intent JSON showed:**
Intent classifier isn't in the suppress list, so its structured output might be getting streamed as reasoning tokens before being parsed. Need to either:
1. Suppress streaming from intent classifier
2. Filter it in orchestrator before emitting
3. Hide it in frontend with block type filter
