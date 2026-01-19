# NDJSON TRACING GUIDE

## What is NDJSON?
**Newline Delimited JSON** - Each line is a complete, valid JSON object.

Example stream:
```
{"type":"block_start","id":"abc","block_type":"thinking"}\n
{"type":"block_delta","id":"abc","content":"Hello"}\n
{"type":"tool_start","tool":"write_file","file":"test.js"}\n
{"type":"tool_result","tool":"write_file","success":true}\n
```

## Critical Points to Check

### 1. Backend Emission (ships-backend/app/streaming/pipeline.py)

**Lines to Watch:**
- **Line ~177:** `tool_start` JSON emission
- **Line ~259:** `tool_result` JSON emission

**Log Format:**
```
🔧 [PIPELINE] EMITTED tool_start NDJSON:
   {"type": "tool_start", "tool": "write_files_batch", "file": null, "timestamp": 1768785489195}

✅ [PIPELINE] EMITTED tool_result NDJSON:
   {"type": "tool_result", "tool": "write_files_batch", "file": null, "success": true, "timestamp": 1768785489200}
```

**What to Check:**
- ✅ Is the JSON valid? (copy-paste into JSON validator)
- ✅ Does it have required fields? (`type`, `tool`)
- ✅ Is it followed by `\n`? (newline terminates NDJSON line)
- ❌ Is it missing `timestamp` field?

---

### 2. Network Transport

**Check Browser DevTools:**
1. Open DevTools → Network tab
2. Filter: `run` (to find `/agent/run` request)
3. Click the request → Response tab
4. Look for NDJSON lines

**Expected:**
```
{"type":"tool_start","tool":"write_files_batch","file":null,"timestamp":1768785489195}
{"type":"tool_result","tool":"write_files_batch","file":null,"success":true,"timestamp":1768785489200}
```

**Common Issues:**
- ❌ JSON objects split across multiple lines (invalid NDJSON)
- ❌ Missing newlines between objects
- ❌ Extra whitespace or formatting
- ❌ Tool events missing entirely from stream

---

### 3. Frontend Parsing (prism-frontend/prism-ai-web/src/services/agentService.ts)

**Lines to Watch:**
- **Line ~172:** Split on `\n` and parse each line
- **Line ~175:** Tool event logging

**Log Format:**
```
🔧 [AgentService] TOOL EVENT: tool_start
Full JSON: {
  "type": "tool_start",
  "tool": "write_files_batch",
  "file": null,
  "timestamp": 1768785489195
}
Raw line: {"type":"tool_start","tool":"write_files_batch","file":null,"timestamp":1768785489195}
```

**What to Check:**
- ✅ Is `chunk.type === 'tool_start'`?
- ✅ Does the JSON structure match backend emission?
- ❌ Is the chunk being filtered before reaching handler?
- ❌ Is JSON.parse() throwing an error?

---

### 4. Chunk Routing (prism-frontend/prism-ai-web/src/components/chat/hooks/useChatLogic.ts)

**Lines to Watch:**
- **Line ~222:** `tool_start` handler
- **Line ~251:** `tool_result` handler

**Log Format:**
```
[useChatLogic] tool_start event captured: {
  id: "1768785489195-write_files_batch",
  type: "tool_start",
  tool: "write_files_batch",
  file: null,
  timestamp: 1768785489195
}
```

**What to Check:**
- ✅ Is the handler being called?
- ✅ Is `addToolEvent()` being invoked?
- ❌ Is `chunk.type` not matching the if condition?
- ❌ Is the handler code not executing?

---

### 5. State Update (prism-frontend/prism-ai-web/src/store/streamingStore.ts)

**Lines to Watch:**
- **Line ~75:** `addToolEvent` implementation

**Log Format:**
```
[streamingStore] addToolEvent called. New array length: 1 Event: {
  id: "1768785489195-write_files_batch",
  type: "tool_start",
  tool: "write_files_batch",
  file: null,
  timestamp: 1768785489195
}
```

**What to Check:**
- ✅ Is `addToolEvent` being called?
- ✅ Does array length increment (0 → 1 → 2)?
- ❌ Is Zustand not triggering re-render?
- ❌ Is array being cleared immediately after?

---

### 6. UI Render (prism-frontend/prism-ai-web/src/components/chat/ChatInterface.tsx)

**Lines to Watch:**
- **Line ~70:** Conditional ToolProgress render

**Code:**
```tsx
{toolEvents.length > 0 && <ToolProgress toolEvents={toolEvents} />}
```

**What to Check:**
- ✅ Is `toolEvents.length > 0`?
- ✅ Is ToolProgress component mounting?
- ❌ Is ChatInterface not re-rendering when toolEvents changes?
- ❌ Is ToolProgress component throwing an error?

---

## Debugging Workflow

### Step 1: Verify Backend Emission
```bash
# Run agent and check backend terminal
# Look for:
🔧 [PIPELINE] EMITTED tool_start NDJSON:
✅ [PIPELINE] EMITTED tool_result NDJSON:
```

**If missing:** Backend is NOT emitting tool events
- Check `on_tool_start` and `on_tool_end` handlers
- Verify `yield` statements are executing
- Check if tools are actually being called

**If present:** Continue to Step 2

---

### Step 2: Verify Network Transport
```javascript
// Open browser console and check Network tab
// Look for tool_start/tool_result in /agent/run response
```

**If missing:** Backend emits but network doesn't receive
- Check FastAPI StreamingResponse
- Verify NDJSON format (newlines)
- Check if response is buffered

**If present:** Continue to Step 3

---

### Step 3: Verify Frontend Parsing
```javascript
// Browser console should show:
🔧 [AgentService] TOOL EVENT: tool_start
```

**If missing:** Network receives but agentService doesn't parse
- Check NDJSON splitting logic (split on `\n`)
- Verify JSON.parse() isn't failing
- Check if tool events are filtered

**If present:** Continue to Step 4

---

### Step 4: Verify Chunk Routing
```javascript
// Browser console should show:
[useChatLogic] tool_start event captured:
```

**If missing:** agentService parses but useChatLogic doesn't handle
- Check `chunk.type` condition matching
- Verify `handleChunk` is being called
- Check if handler is inside try/catch that swallows errors

**If present:** Continue to Step 5

---

### Step 5: Verify State Update
```javascript
// Browser console should show:
[streamingStore] addToolEvent called. New array length: 1
```

**If missing:** Handler called but state not updated
- Check if `addToolEvent` is imported correctly
- Verify Zustand store is initialized
- Check if state is being reset elsewhere

**If present:** Continue to Step 6

---

### Step 6: Verify UI Render
```javascript
// React DevTools → Components
// Find ChatInterface component
// Check props: toolEvents.length should be > 0
```

**If length is 0:** State updated but UI doesn't reflect
- Check if ChatInterface is subscribed to store changes
- Verify `useStreamingStore()` hook is used correctly
- Check if `clearToolEvents()` is being called

**If length > 0 but ToolProgress hidden:** Render condition issue
- Check conditional render logic
- Verify ToolProgress component exists
- Check for CSS display: none

---

## Quick Test Script

Run this in browser console during agent execution:

```javascript
// Subscribe to Zustand store changes
const unsubscribe = useStreamingStore.subscribe(
  (state) => state.toolEvents,
  (toolEvents) => {
    console.log('📊 [STORE WATCHER] toolEvents changed:', toolEvents.length, toolEvents);
  }
);

// Later, unsubscribe:
// unsubscribe();
```

This will show EVERY time toolEvents array changes.

---

## Expected Full Flow Example

### Backend Terminal:
```
🔧 [PIPELINE] EMITTED tool_start NDJSON:
   {"type": "tool_start", "tool": "write_files_batch", "file": null, "timestamp": 1768785489195}

✅ [PIPELINE] EMITTED tool_result NDJSON:
   {"type": "tool_result", "tool": "write_files_batch", "file": null, "success": true, "timestamp": 1768785489200}
```

### Browser DevTools Network → Response:
```
{"type":"block_start","id":"abc","block_type":"thinking","timestamp":1768785489000,"title":"Thinking..."}
{"type":"block_delta","id":"abc","content":"Planning..."}
{"type":"tool_start","tool":"write_files_batch","file":null,"timestamp":1768785489195}
{"type":"tool_result","tool":"write_files_batch","file":null,"success":true,"timestamp":1768785489200}
```

### Browser Console:
```
🔧 [AgentService] TOOL EVENT: tool_start
Full JSON: { "type": "tool_start", "tool": "write_files_batch", ... }

[useChatLogic] tool_start event captured: { id: "...", type: "tool_start", ... }

[streamingStore] addToolEvent called. New array length: 1 Event: { ... }

🔧 [AgentService] TOOL EVENT: tool_result
Full JSON: { "type": "tool_result", "tool": "write_files_batch", ... }

[useChatLogic] tool_result event captured: { id: "...", type: "tool_result", ... }

[streamingStore] addToolEvent called. New array length: 2 Event: { ... }
```

### UI:
- ToolProgress sidebar appears (animated slide-in)
- Shows: "write_files_batch" with checkmark icon
- Updates in real-time as more tools execute

---

## Common Root Causes

### 1. NDJSON Not Actually NDJSON
**Symptom:** Frontend parse errors
**Cause:** Backend emitting `json.dumps()` without `\n`
**Fix:** Ensure every `yield json.dumps({...}) + "\n"`

### 2. Tool Events Filtered Out
**Symptom:** Network shows events, but useChatLogic doesn't log them
**Cause:** `chunk.type` doesn't match condition (typo, case sensitivity)
**Fix:** Check exact string matching: `'tool_start'` vs `'tool-start'`

### 3. State Reset on Every Message
**Symptom:** toolEvents briefly shows items, then resets to []
**Cause:** `clearToolEvents()` called too aggressively
**Fix:** Only clear at start of NEW message, not on every chunk

### 4. Zustand Store Not Reactive
**Symptom:** addToolEvent called, array updates, but UI doesn't re-render
**Cause:** Component not subscribed to store properly
**Fix:** Use `const toolEvents = useStreamingStore(state => state.toolEvents)`

### 5. Backend Never Emits
**Symptom:** No emission logs in backend terminal
**Cause:** `on_tool_start` / `on_tool_end` handlers not executing
**Fix:** Verify tools are actually being called by agents
