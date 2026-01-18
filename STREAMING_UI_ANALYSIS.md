# Streaming UI Analysis & Modernization Plan

## Current State Analysis

### What We Have ✅
1. **StreamBlock Protocol** - Backend sends structured events:
   - `block_start` - Creates new UI block
   - `block_delta` - Appends content token-by-token
   - `block_end` - Finalizes block
   - Block types: `text`, `code`, `command`, `plan`, `thinking`, `tool_use`, `error`, `preflight`

2. **Frontend Components**:
   - `BlockStreamRenderer.tsx` - Renders individual blocks
   - `ThinkingSection.tsx` - Shows agent reasoning
   - `ToolProgress.tsx` - Shows files created/commands run
   - `PhaseIndicator.tsx` - Shows agent phase (planning/coding/validating/fixing)
   - `ActivityIndicator.tsx` - Shows current activity

3. **State Management**:
   - `useAgentRuns` - Manages runs and messages
   - `useStreamingStore` - Manages real-time streaming state
   - Messages have `blocks[]` array for structured content

### What's Broken 🔴
1. **JSON Wall Dumps** - Raw JSON appearing instead of parsed UI blocks
2. **Missing Block Rendering** - Blocks not rendering in chat UI
3. **No Debug Logs** - Can't see what's received on frontend
4. **Inconsistent Event Handling** - Multiple event types, unclear flow

---

## Root Cause: Event Handling Mismatch

### Backend Output (ships-backend/app/streaming/pipeline.py)
```python
# Lines 152-165: Currently emitting
yield block_mgr.start_block(BlockType.THINKING, "Thinking...") + "\n"
yield block_mgr.append_delta(content) + "\n"
yield block_mgr.end_block() + "\n"
```

**Problem**: `StreamBlockManager` yields JSON strings, but frontend expects parsed objects.

### Frontend Input (prism-frontend/prism-ai-web/src/services/agentService.ts)
```typescript
// Lines 163-174: Parsing chunks
const chunk = JSON.parse(line);
console.log('[AgentService] 📥 Chunk received:', chunk.type, chunk);
onChunk(chunk);
```

**Expected**: `chunk.type` should be `block_start`, `block_delta`, `block_end`

### Frontend Handler (prism-frontend/prism-ai-web/src/components/chat/hooks/useChatLogic.ts)
```typescript
// Lines 141-172: Handling blocks
if (chunk.type === 'block_start' && chunk.block_type) {
   const block: StreamBlock = {
       id: chunk.id!,
       type: chunk.block_type,
       title: chunk.title,
       content: '',
       isComplete: false
   };
   upsertRunMessageBlock(targetRunId, aiMessageId, block);
}
```

---

## Modern 2025 Best Practices

### 1. Vercel AI SDK Pattern
**Structure**: Stream text chunks + tool calls in standardized format
```typescript
{
  type: 'text-delta' | 'tool-call' | 'tool-result',
  content?: string,
  toolName?: string,
  toolArgs?: object,
  result?: any
}
```

### 2. Claude/Cursor Pattern  
**Structure**: Reasoning steps + tool execution + final response
```typescript
{
  type: 'thinking' | 'action' | 'result',
  title: string,
  content: string,
  complete: boolean
}
```

### 3. LangGraph Pattern
**Structure**: Node events + state updates
```typescript
{
  event: 'on_chain_start' | 'on_chain_stream' | 'on_chain_end',
  name: string,
  data: { output?: string, input?: any }
}
```

**Our Implementation Aligns Best With:** Cursor pattern (reasoning + action + result)

---

## What's Missing

### Critical Issues
1. ❌ **Event Type Mismatch** - Backend emits different types than frontend expects
2. ❌ **No Fallback Rendering** - When blocks fail, shows raw JSON
3. ❌ **No Debug Visibility** - Can't see what's streaming through
4. ❌ **Duplicate Event Handlers** - Multiple places handling same events
5. ❌ **No Error Boundaries** - One malformed chunk breaks entire UI

### Feature Gaps vs Modern Agents
1. ⚠️ **No Artifact Preview** - No inline preview of code changes
2. ⚠️ **No Diff View** - Can't see before/after comparisons
3. ⚠️ **No Step Timeline** - Can't see sequence of actions
4. ⚠️ **No Collapsible Sections** - Everything expanded always
5. ⚠️ **No Markdown Rendering** - Plain text only in thinking blocks

---

## Modernization Plan

### Phase 1: Fix Current System (URGENT)
**Goal**: Stop JSON dumps, render blocks properly

#### 1.1 Add Comprehensive Debug Logging
**File**: `prism-frontend/prism-ai-web/src/services/agentService.ts`
```typescript
// Add detailed logging
const chunk = JSON.parse(line);
console.group('[AgentService] Chunk Received');
console.log('Raw line:', line);
console.log('Parsed chunk:', chunk);
console.log('Chunk type:', chunk.type);
console.log('Block type:', chunk.block_type);
console.log('Has ID:', !!chunk.id);
console.groupEnd();
onChunk(chunk);
```

#### 1.2 Add Fallback Renderer
**File**: `prism-frontend/prism-ai-web/src/components/chat/ChatMessage.tsx`
```typescript
// Render unknown chunks as formatted JSON
{message.content && !message.blocks?.length && (
  <pre style={{ 
    background: '#1e1e1e', 
    padding: '12px', 
    borderRadius: '6px',
    overflow: 'auto'
  }}>
    {typeof message.content === 'object' 
      ? JSON.stringify(message.content, null, 2)
      : message.content
    }
  </pre>
)}
```

#### 1.3 Normalize Backend Events
**File**: `ships-backend/app/streaming/stream_events.py`
```python
# Ensure ALL events have consistent structure
def to_event(self, event_type: str, delta: str = None) -> str:
    payload = {
        "type": event_type,      # REQUIRED
        "id": self.id,            # REQUIRED
        "block_type": self.type.value,  # REQUIRED for block_start
        "timestamp": int(time.time() * 1000)
    }
    
    # ALWAYS include these fields
    if self.title:
        payload["title"] = self.title
    if self.metadata:
        payload["metadata"] = self.metadata
        
    # Type-specific fields
    if event_type == "block_delta":
        payload["content"] = delta or ""
        
    if event_type == "block_end":
        payload["final_content"] = self.content
        
    return json.dumps(payload)
```

### Phase 2: Enhance UI Components (NEXT)
**Goal**: Modern, polished agent UI

#### 2.1 Add Markdown Rendering
- Install `react-markdown` and `remark-gfm`
- Render thinking blocks with proper formatting
- Support code syntax highlighting

#### 2.2 Add Collapsible Sections
- Thinking blocks collapse after completion
- Show summary line when collapsed
- Click to expand full reasoning

#### 2.3 Add Diff Viewer
- Use Monaco diff editor for file changes
- Show before/after side-by-side
- Highlight changed lines

#### 2.4 Add Timeline View
- Vertical timeline of all actions
- Icons for each step type
- Duration indicators

### Phase 3: Advanced Features (FUTURE)
**Goal**: Best-in-class agent UX

#### 3.1 Artifact Previews
- Live preview of React components
- Inline preview of UI changes
- Hot reload when code updates

#### 3.2 Interactive Tool Calls
- Click to re-run tool
- Edit tool arguments
- Fork conversation from tool result

#### 3.3 Streaming Optimizations
- Virtual scrolling for long outputs
- Streaming diffs
- Progressive image loading

---

## Implementation Priority

### IMMEDIATE (Today)
1. ✅ Add debug logging to `agentService.ts`
2. ✅ Add debug logging to `useChatLogic.ts`
3. ✅ Add fallback JSON renderer to `ChatMessage.tsx`
4. ✅ Verify StreamBlock events in backend

### HIGH (This Week)
1. Add markdown rendering to blocks
2. Add collapsible thinking sections
3. Add error boundaries around block rendering
4. Add event type validation

### MEDIUM (Next Week)
1. Add diff viewer for code changes
2. Add timeline view
3. Add step duration tracking
4. Polish UI transitions

### LOW (Future)
1. Artifact previews
2. Interactive tool calls
3. Virtual scrolling

---

## Debug Checklist

When JSON wall appears:
1. ✅ Check browser console for `[AgentService] Chunk Received`
2. ✅ Verify `chunk.type` is one of: `block_start`, `block_delta`, `block_end`
3. ✅ Verify `chunk.block_type` exists for `block_start`
4. ✅ Verify `chunk.id` is present and consistent
5. ✅ Check `[useChatLogic]` logs for block upsert calls
6. ✅ Check React DevTools for `message.blocks` array
7. ✅ Check if `BlockStreamRenderer` is being called
8. ✅ Check for JavaScript errors in console

---

## Key Files to Modify

### Backend
- ✅ `ships-backend/app/streaming/stream_events.py` - Normalize event structure
- ✅ `ships-backend/app/streaming/pipeline.py` - Verify event emission

### Frontend  
- ✅ `prism-frontend/prism-ai-web/src/services/agentService.ts` - Add debug logs
- ✅ `prism-frontend/prism-ai-web/src/components/chat/hooks/useChatLogic.ts` - Add debug logs
- ✅ `prism-frontend/prism-ai-web/src/components/chat/ChatMessage.tsx` - Add fallback renderer
- ⚠️ `prism-frontend/prism-ai-web/src/components/chat/BlockStreamRenderer.tsx` - Enhance rendering
- ⚠️ `prism-frontend/prism-ai-web/src/components/streaming/ThinkingSection.tsx` - Add collapse

---

## Success Criteria

### Must Have (MVP)
- ✅ No JSON dumps in chat
- ✅ All blocks render correctly
- ✅ Clear visual separation between blocks
- ✅ Proper typing indicators
- ✅ Error messages are readable

### Should Have (Polish)
- ⚠️ Markdown in thinking blocks
- ⚠️ Code syntax highlighting
- ⚠️ Collapsible sections
- ⚠️ Smooth animations
- ⚠️ Mobile responsive

### Nice to Have (Future)
- ❌ Live previews
- ❌ Diff views
- ❌ Timeline view
- ❌ Interactive tools
- ❌ Virtual scrolling
