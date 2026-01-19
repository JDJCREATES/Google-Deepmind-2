# STREAMING ARCHITECTURE - COMPLETE FILE MAP

## CRITICAL PATH (Data Flow Order)

### 1. ENTRY POINT
**File:** `ships-backend/main.py`
- **Line 351:** POST `/agent/run` endpoint
- **Line 395:** Calls `stream_pipeline(body.prompt, project_path, settings, artifact_context)`
- **Line 306:** Import: `from app.streaming.pipeline import stream_pipeline`
- **Status:** ✅ ACTIVE (this is the entry point for all agent runs)

---

### 2. STREAMING ORCHESTRATOR
**File:** `ships-backend/app/streaming/pipeline.py`
- **Function:** `stream_pipeline()` (line ~80)
- **What it does:**
  - Calls `graph.astream_events()` to get LangGraph events
  - Routes events through handlers:
    - `on_chat_model_stream` → Token streaming (line 134)
    - `on_tool_start` → Tool execution start (line 164)
    - `on_tool_end` → Tool execution complete (line 180)
    - `on_chain_start` → Agent starts (line 268)
    - `on_chain_end` → Agent completes (line 282)
  - Yields NDJSON chunks (one JSON object per line)
  - **Logging:** Uses `DebouncedLogger` (2s debounce) to prevent log spam
  
- **Key Functions:**
  - **Lines 164-178:** `on_tool_start`
    - Emits: `{"type": "tool_start", "tool": "...", "file": "..."}`
    - Creates COMMAND block
  
  - **Lines 180-254:** `on_tool_end`
    - Extracts `.content` from ToolMessage
    - Parses JSON responses
    - **Line 200-220:** Formats output (THIS IS WHERE YOU FIXED TOOL OUTPUT)
    - **Line 223:** Emits `cmd_output` block
    - **Line 247:** Emits `{"type": "tool_result", "tool": "...", "success": true}`
  
  - **Lines 282-380:** `on_chain_end`
    - **Lines 286-375:** Parses planner's `LLMPlanOutput` structured data
    - Creates formatted blocks: summary, reasoning, tasks, files, dependencies, risks

- **Status:** ✅ ACTIVE (this is THE file that routes all events)

---

### 3. NETWORK TRANSPORT
**Protocol:** Server-Sent Events (SSE) / NDJSON Stream
- **Format:** Each line is a complete JSON object
- **Example:**
  ```json
  {"type": "block_start", "id": "abc123", "block_type": "thinking", "title": "Thinking..."}
  {"type": "block_delta", "id": "abc123", "content": "Hello"}
  {"type": "tool_start", "tool": "write_files_batch", "file": null}
  {"type": "tool_result", "tool": "write_files_batch", "success": true}
  ```

---

### 4. FRONTEND RECEIVER
**File:** `prism-frontend/prism-ai-web/src/services/agentService.ts`
- **Function:** `runAgentStream()` (line ~45)
- **What it does:**
  - Calls `fetch('/agent/run')` with streaming response
  - Reads response body as stream
  - Splits on newlines (`\n`)
  - Parses each line as JSON
  - Calls `onChunk(chunk)` callback
  - **Logging:** Uses debounced logger (1s debounce) for high-frequency token streams
  
- **Key Code:**
  - **Line 172:** `const chunk = JSON.parse(line);`
  - **Line 181:** `onChunk(chunk);`
  
- **Status:** ✅ ACTIVE (receives all backend chunks)

---

### 5. CHUNK ROUTER
**File:** `prism-frontend/prism-ai-web/src/components/chat/hooks/useChatLogic.ts`
- **Function:** `handleChunk()` callback (line ~130)
- **What it does:**
  - Routes chunks by `chunk.type`:
    - `block_start` → Creates new StreamBlock
    - `block_delta` → Appends content to active block
    - `block_end` → Finalizes block
    - `activity` → Updates sidebar activity
    - `tool_start` → **SHOULD** add to toolEvents array
    - `tool_result` → **SHOULD** add to toolEvents array
    - `error` → Shows error message
  
- **Key Handlers:**
  - **Lines 218-248:** `tool_start` handler
    - Calls `addToolEvent(toolEvent)`
    - Updates `currentActivity`
  
  - **Lines 250-275:** `tool_result` handler
    - Calls `addToolEvent(toolEvent)`
    - **ALSO creates a StreamBlock** (you added this recently)
  
- **Status:** ✅ ACTIVE (this handles all chunk routing)
- **ISSUE:** toolEvents array stays empty despite handlers existing

---

### 6. STATE MANAGEMENT
**File:** `prism-frontend/prism-ai-web/src/store/streamingStore.ts`
- **Store:** Zustand state management
- **State:**
  - `toolEvents: ToolEvent[]` - Array of tool executions
  - `currentActivity: string` - Current agent activity
  - `activityType: string` - Activity icon type
  
- **Actions:**
  - `addToolEvent(event)` - Push to array
  - `clearToolEvents()` - Reset array
  - `setActivity(activity, type)` - Update activity display
  
- **Status:** ✅ ACTIVE (state management works)
- **ISSUE:** Array stays empty (length: 0)

---

### 7. UI COMPONENTS

#### A. Chat Message Display
**File:** `prism-frontend/prism-ai-web/src/components/chat/ChatMessage.tsx`
- **Line ~70:** Renders `<BlockRenderer block={block} />` for each block
- **Status:** ✅ ACTIVE (renders StreamBlocks correctly)

#### B. Block Renderer
**File:** `prism-frontend/prism-ai-web/src/components/chat/BlockStreamRenderer.tsx`
- **Switch Cases:**
  - `thinking` → Gray thinking block
  - `text` → Markdown formatted text
  - `code` → Monaco editor
  - `cmd_output` → Dark terminal-style output
  - `tool_use` → Blue file operation display
  - `plan` → Plan summary block
  
- **Status:** ✅ ACTIVE (you added cmd_output and tool_use cases)

#### C. Tool Progress Sidebar
**File:** `prism-frontend/prism-ai-web/src/components/streaming/ToolProgress.tsx`
- **Props:** `toolEvents: ToolEvent[]`
- **Display:** Shows list of files being created/read/updated
- **Status:** ✅ EXISTS
- **ISSUE:** Never renders because toolEvents.length === 0

#### D. Chat Interface (Container)
**File:** `prism-frontend/prism-ai-web/src/components/chat/ChatInterface.tsx`
- **Line ~70:** Conditionally renders ToolProgress
  ```tsx
  {toolEvents.length > 0 && <ToolProgress toolEvents={toolEvents} />}
  ```
- **Status:** ✅ ACTIVE
- **ISSUE:** Condition never true (toolEvents always empty)

---

## UTILITIES

### Debounced Logging
**Purpose:** Prevent console/log spam from high-frequency events (token streaming, repeated tool calls)

**Backend:** `ships-backend/app/utils/debounced_logger.py`
- **Class:** `DebouncedLogger(logger, debounce_seconds=1.0)`
- **Behavior:** 
  - Tracks identical log messages by (level, message) key
  - Only logs if `debounce_seconds` has passed since last identical message
  - Appends suppression count: `"Message (suppressed 47 similar logs)"`
- **Usage:**
  ```python
  from app.utils.debounced_logger import DebouncedLogger
  debounced_log = DebouncedLogger(logger, debounce_seconds=2.0)
  debounced_log.info("Streaming tokens...")  # Won't spam
  ```

**Frontend:** `prism-frontend/prism-ai-web/src/utils/debouncedLogger.ts`
- **Class:** `DebouncedLogger(debounceMs=1000)`
- **Singleton:** `debouncedLogger` exported for convenience
- **Behavior:**
  - Caches log messages with timestamps
  - Flushes suppressed logs periodically
  - Shows count: `"Token stream active (×234 suppressed)"`
  - **Never debounces errors** - always shown immediately
- **Usage:**
  ```typescript
  import { debouncedLogger } from '../utils/debouncedLogger';
  debouncedLogger.info('Parsing chunk...');  // Auto-debounced
  debouncedLogger.error('Critical error');    // Never suppressed
  ```

---

## DEAD CODE / UNUSED FILES

### ❌ NOT FOUND / NOT IN USE:
- `route_events()` function - Does NOT exist
- `stream_agent_run()` function - Does NOT exist
- Any file that imports `route_events` - None found

### ⚠️ POTENTIALLY UNUSED:
- `JsonValueFilter` class in main.py (lines 310-347) - Defined but never instantiated
- `ships-backend/app/api/runs/router.py` - Defines agent runs but doesn't call pipeline.py

---

## KNOWN ISSUES

### 1. toolEvents Array Always Empty
**Expected Flow:**
1. Backend emits `{"type": "tool_start", ...}` at line 175
2. Backend emits `{"type": "tool_result", ...}` at line 247
3. Frontend parses in agentService.ts at line 169
4. Frontend routes in useChatLogic.ts at lines 218-275
5. State updated in streamingStore.ts via `addToolEvent()`
6. UI re-renders ChatInterface → ToolProgress displays

**Actual Behavior:**
- toolEvents.length: 0 (never increases)
- ToolProgress never renders

**Possible Causes:**
- Backend never actually emits tool_start/tool_result JSON
- Frontend filters them out somewhere
- State update doesn't trigger re-render
- JSON parsing fails silently

### 2. Planner Structured Output Shows Raw JSON
**Root Cause:**
- Planner uses `.with_structured_output(LLMPlanOutput)` at line 466 of planner/planner.py
- This causes LLM to stream JSON tokens: `{"reasoning": "...", "tasks": [...]}`
- Tokens stream through `on_chat_model_stream` → creates THINKING block with JSON content

**Current Fix:**
- `on_chain_end` parses the final LLMPlanOutput at lines 286-375
- Emits formatted blocks (summary, reasoning, tasks, files)
- **BUT:** Raw JSON still shows first, formatted blocks show after

**Attempted Fix (reverted):**
- Suppress tokens during planner chain → Broke all streaming

**Correct Fix:**
- Unknown - can't suppress tokens without breaking UX
- Can't prevent `.with_structured_output()` from streaming JSON
- Could hide THINKING blocks when chain_name === "planner"?

### 3. Tool Output Showing Raw Data
**Was Fixed:**
- Line 210 was appending raw Python repr of dicts/arrays
- Fixed by parsing tool-specific responses:
  - `get_artifact` → "✓ Success: Loaded {name}"
  - `get_file_tree` → "✓ Success: Found X files, Y directories"
  - Terminal commands → Show formatted output

---

## VERIFICATION COMMANDS

### Backend Check:
1. Run agent with tool usage
2. Check backend logs for:
   ```
   [PIPELINE DEBUG] Emitted tool_start JSON: tool=write_files_batch
   [PIPELINE DEBUG] Emitted tool_result JSON: tool=write_files_batch, success=True
   ```

### Frontend Check:
1. Open browser devtools → Console
2. Look for chunk logs showing:
   ```javascript
   {type: 'tool_start', tool: 'write_files_batch', ...}
   {type: 'tool_result', tool: 'write_files_batch', success: true}
   ```

### State Check:
1. Add temporary log in `streamingStore.ts` after `addToolEvent`:
   ```typescript
   console.log('[Store] toolEvents after add:', get().toolEvents.length);
   ```

---

## FILES YOU EDITED (Recent Session)

1. ✅ `ships-backend/app/streaming/pipeline.py`
   - Added debug logging
   - Fixed tool output formatting (lines 200-220)
   - Added on_chain_end planner parsing (lines 286-375)

2. ✅ `prism-frontend/prism-ai-web/src/components/chat/hooks/useChatLogic.ts`
   - Added tool_result handler (lines 250-275)
   - Already had tool_start handler (lines 218-248)

3. ✅ `prism-frontend/prism-ai-web/src/components/chat/BlockStreamRenderer.tsx`
   - Added cmd_output case
   - Added tool_use case

4. ✅ `prism-frontend/prism-ai-web/src/components/agent-dashboard/types.ts`
   - Added 'cmd_output' to StreamBlock type union

5. ✅ `prism-frontend/prism-ai-web/src/services/agentService.ts`
   - Removed excessive logging

6. ✅ `prism-frontend/prism-ai-web/src/components/chat/ChatInterface.tsx`
   - Removed debug log

---

## NEXT STEPS TO DEBUG toolEvents Issue

1. **Add granular logging:**
   ```typescript
   // In agentService.ts after parsing
   if (chunk.type === 'tool_start' || chunk.type === 'tool_result') {
       console.log('[AgentService] TOOL EVENT:', chunk);
   }
   ```

2. **Check if events reach useChatLogic:**
   ```typescript
   // In useChatLogic.ts handleChunk
   if (chunk.type?.startsWith('tool')) {
       console.log('[useChatLogic] Tool chunk received:', chunk.type);
   }
   ```

3. **Verify state updates:**
   ```typescript
   // In streamingStore.ts addToolEvent
   addToolEvent: (event) => {
       const current = get().toolEvents;
       console.log('[Store] Before:', current.length, 'After:', current.length + 1);
       set({ toolEvents: [...current, event] });
   }
   ```

4. **Check backend emission:**
   - Look for "Emitted tool_start JSON" and "Emitted tool_result JSON" in backend logs
   - If missing → Backend isn't emitting
   - If present → Frontend filtering or parsing issue
