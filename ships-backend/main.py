from dotenv import load_dotenv
load_dotenv()  # Load .env file before anything else

from fastapi import FastAPI, Depends, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from app.auth import router as auth_router, get_current_user
from app.api.auth_routes import router as google_auth_router
from app.services.preview_manager import preview_manager
from app.services.usage_tracker import usage_tracker
from app.database import health_check, close_database
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
import os
import logging

# Initialize centralized logging FIRST
from app.core.logger import setup_logging, get_logger
setup_logging()
logger = get_logger("main")

app = FastAPI(title="ShipS* Backend")

# Startup event - check database connection
@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    
    # Silence access logs for /preview/status polling
    # This prevents the console from being flooded by the 1s poll interval
    class EndpointFilter(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:
            return record.getMessage().find("/preview/status") == -1

    # Filter uvicorn access logs
    logging.getLogger("uvicorn.access").addFilter(EndpointFilter())
    
    # Check database health
    db_healthy = await health_check()
    if not db_healthy:
        logger.warning("⚠ Database not available - some features may be limited")
    
    logger.info("✓ Startup complete")

# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Shutting down...")
    await close_database()
    logger.info("✓ Shutdown complete")

# Session middleware (required for OAuth)
# Must be added BEFORE other middleware
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
app.add_middleware(
    SessionMiddleware, 
    secret_key=SECRET_KEY, 
    same_site="lax", 
    https_only=False
)

# Rate limiting middleware
from app.middleware import RateLimitMiddleware
app.add_middleware(RateLimitMiddleware)

# CORS - allow credentials for session cookies
origins = [
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:5175",
    "http://localhost:5176",
    "http://localhost:5177",  # Electron Dev Server
    "ships://preview" # Electron Custom Protocol
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,  # Required for session cookies
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------
# Preview Router
# ---------------------------------------------------------
preview_router = APIRouter(prefix="/preview", tags=["preview"])

class ProjectPath(BaseModel):
    path: str

@preview_router.post("/start")
async def start_preview(project: ProjectPath):
    return preview_manager.start_dev_server(project.path)

@preview_router.post("/stop")
async def stop_preview():
    return preview_manager.stop_dev_server()

class OpenPreviewRequest(BaseModel):
    project_path: str = None  # Required - the project to preview
    run_id: str = None  # Optional - for per-run tracking

@preview_router.post("/open")
async def open_preview(request: OpenPreviewRequest = None):
    """
    ROBUST preview opener using MultiPreviewManager.
    
    - Checks if project needs npm install
    - Allocates unique port
    - Waits for dev server to be ready
    - Returns URL when available
    """
    # Determine project path and run_id
    project_path = request.project_path if request else None
    run_id = request.run_id if request else "default"
    
    if not project_path:
        project_path = preview_manager.current_project_path
    
    if not project_path:
        return {
            "status": "error",
            "message": "No project path provided. Include project_path in request."
        }
    
    if not run_id:
        run_id = "default"
    
    # Use the robust get_or_start method - handles everything
    result = preview_manager.get_or_start(run_id, project_path)
    
    # Always request focus to bring preview window to front
    if result.get("status") == "running":
        preview_manager.request_focus()
    
    result["message"] = "Dev server running." if result.get("status") == "running" else result.get("message")
    return result

@preview_router.get("/status")
async def get_status(run_id: str = None):
    """Get preview status - optionally for a specific run."""
    if run_id:
        return preview_manager.get_status(run_id)
    
    # Check if ANY instance is running
    any_running = False
    running_url = preview_manager.current_url
    running_project = preview_manager.current_project_path
    
    first_error = None
    
    # Check all instances for a running or starting one
    for inst_id, inst in preview_manager.instances.items():
        # Consider both alive processes and "starting" status as running
        if inst.is_alive() or inst.status in ("starting", "running"):
            any_running = True
            running_url = inst.url or running_url
            running_project = inst.project_path or running_project
            break  # Use first running instance
        
        # Capture first error found if no running instance
        if inst.status == "error" and not first_error:
            first_error = inst.error_message
    
    return {
        "is_running": any_running,
        "logs": preview_manager.logs[-50:],
        "url": running_url,
        "project_path": running_project,
        "focus_requested": preview_manager.focus_requested,
        "instances": preview_manager.get_status(),
        "error": first_error
    }

@preview_router.post("/stop/{run_id}")
async def stop_run_preview(run_id: str):
    """Stop preview for a specific run."""
    preview_manager._stop_instance(run_id)
    return {"status": "stopped", "run_id": run_id}

@preview_router.post("/request-focus")
async def request_focus():
    preview_manager.request_focus()
    return {"status": "success"}

@preview_router.post("/ack-focus")
async def ack_focus():
    preview_manager.clear_focus_request()
    return {"status": "success"}

@preview_router.post("/open-terminal")
async def open_system_terminal(project: ProjectPath):
    """Open a native system terminal for the user."""
    return preview_manager.open_system_terminal(project.path)

@preview_router.post("/set-path")
async def set_project_path(project: ProjectPath):
    """Set the project path without starting a dev server. 
    This tells the agent where to write files."""
    if not project.path or not os.path.isdir(project.path):
        return {"status": "error", "message": f"Path does not exist: {project.path}"}
    
    preview_manager.current_project_path = project.path
    return {
        "status": "success", 
        "message": f"Project path set to: {project.path}",
        "project_path": project.path
    }

@preview_router.get("/path")
async def get_project_path():
    """Get the current project path."""
    return {
        "project_path": preview_manager.current_project_path,
        "is_set": preview_manager.current_project_path is not None
    }

# ---------------------------------------------------------
# Agent/Prompt Router (Placeholder for now)
# ---------------------------------------------------------
agent_router = APIRouter(prefix="/agent", tags=["agent"])

class PromptRequest(BaseModel):
    prompt: str
    project_path: Optional[str] = None  # Path to the user's project directory
    settings: Optional[dict] = None     # User settings (e.g. artifacts.fileTreeDepth)
    artifact_context: Optional[dict] = None  # File tree & dependency data from Electron

from fastapi.responses import StreamingResponse
import json
from app.graphs.agent_graph import stream_pipeline

import re

class JsonValueFilter:
    def __init__(self, target_keys=None):
        # Comprehensive list based on planner/models.py
        self.target_keys = target_keys or [
            "title", "description", "summary", "name", "content",
            "path", "command", "assertion", "mitigation", 
            "detailed_description", "mvs_verification", "notes"
        ]
        self.buffer = ""
        self.is_capturing = False
        self.key_pattern = re.compile(r'"(' + '|'.join(self.target_keys) + r')"\s*:\s*"')

    def process_chunk(self, chunk: str) -> str:
        self.buffer += chunk
        output = ""
        
        while True:
            if self.is_capturing:
                # Look for unescaped quote to end the value
                match = re.search(r'(?<!\\)"', self.buffer)
                if match:
                    end_idx = match.start()
                    val = self.buffer[:end_idx]
                    # Use space separator, not newline. Frontend handles line breaks.
                    output += val + " "
                    self.is_capturing = False
                    self.buffer = self.buffer[match.end():]
                else:
                    output += self.buffer
                    self.buffer = "" # Consumed all
                    break
            else:
                match = self.key_pattern.search(self.buffer)
                if match:
                    self.is_capturing = True
                    self.buffer = self.buffer[match.end():] # Start of value
                else:
                    # Keep tail
                    if len(self.buffer) > 40: self.buffer = self.buffer[-40:]
                    break
        return output

@agent_router.post("/run")
async def run_agent(request: Request, body: PromptRequest):
    import logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger = logging.getLogger("ships.agent")
    
    # Determine project path: use provided, fall back to preview_manager's current project
    effective_project_path = body.project_path or preview_manager.current_project_path
    
    # Log the FULL raw input
    logger.info("=" * 60)
    logger.info("[API] 📥 RECEIVED USER INPUT:")
    logger.info(f"[API] Raw prompt (full): {body.prompt}")
    logger.info(f"[API] Prompt length: {len(body.prompt)} chars")
    logger.info(f"[API] Project path (requested): {body.project_path or 'Not provided'}")
    logger.info(f"[API] Project path (from preview): {preview_manager.current_project_path or 'Not set'}")
    logger.info(f"[API] Project path (effective): {effective_project_path or 'Will use backend dir (.)'}")
    logger.info("=" * 60)
    
    # Manual Auth Check
    auth_header = request.headers.get("Authorization")
    user_id = None
    # (Auth logic skipped for brevity as per existing implementation)
            
    # Check limit
    client_ip = request.client.host
    if not usage_tracker.can_run_prompt(client_ip, user_id):
        logger.warning(f"[API] Usage limit exceeded for IP: {client_ip}")
        raise HTTPException(status_code=402, detail="Free limit exceeded. Please login to continue.")

    # ========================================================================
    # CRITICAL: Reject if no project folder is selected
    # ========================================================================
    if not effective_project_path:
        logger.error("[API] ❌ REJECTED: No project folder selected!")
        raise HTTPException(
            status_code=400, 
            detail="No project folder selected. Please use the Electron app to select a project folder first."
        )
    
    usage_tracker.record_usage(client_ip, user_id)
    logger.info(f"[API] Usage recorded for IP: {client_ip}")

    async def response_generator():
        try:
            logger.info("[STREAM] 🚀 Starting agent pipeline stream...")
            logger.info(f"[STREAM] Passing to stream_pipeline: '{body.prompt[:100]}...'")
            current_node = None
            
            planner_filter = JsonValueFilter() # Filter for cleaning up planner JSON stream
            
            async for event in stream_pipeline(body.prompt, project_path=effective_project_path, settings=body.settings, artifact_context=body.artifact_context):
                # DEBUG: Inspect raw event structure (disabled - was spamming logs)
                # import sys
                # print(f"[RAW STREAM] {type(event)}: {str(event)[:200]}...", file=sys.stderr)

                # With subgraphs=True + stream_mode="messages", events are:
                # (namespace_tuple, (message_chunk, metadata))
                # namespace_tuple can be () for main graph or ('node:task_id',) for subgraphs
                
                try:
                    # Handle subgraphs=True format: (namespace, (message_chunk, metadata))
                    # Or simple format: (message_chunk, metadata)
                    message_chunk = None
                    metadata = {}
                    node_name = "agent"

                    # RECURSIVE UNPACKING to find the actual chunk
                    # LangGraph events can be nested like: (('chat:123',), (Chunk, Meta))
                    def unpack_event(evt):
                        if isinstance(evt, tuple) and len(evt) == 2:
                            # Check if second element is the chunk+meta pair
                            if isinstance(evt[1], tuple) and len(evt[1]) == 2 and hasattr(evt[1][0], 'content'):
                                return evt[1][0], evt[1][1] # Found (Chunk, Meta)
                            elif hasattr(evt[0], 'content'):
                                return evt[0], evt[1] # Found (Chunk, Meta) at top level
                            # Recursively check second element (usually where payload is)
                            return unpack_event(evt[1])
                        return None, None

                    # Try to extract chunk
                    extracted_chunk, extracted_meta = unpack_event(event)

                    if extracted_chunk:
                        message_chunk = extracted_chunk
                        metadata = extracted_meta or {}
                        # Extract node name from metadata or namespace
                        if 'langgraph_node' in metadata:
                            node_name = metadata['langgraph_node']
                        elif isinstance(event, tuple) and isinstance(event[0], tuple) and len(event[0]) > 0:
                             # Try to get from namespace ('node:id',)
                             node_raw = str(event[0][0])
                             node_name = node_raw.split(':')[0]
                    else:
                        # Fallback for unexpected formats
                        continue

                    # FILTER: Skip HumanMessage types (internal prompts)
                    msg_type = type(message_chunk).__name__
                    if msg_type in ['HumanMessage', 'HumanMessageChunk']:
                        continue
                    
                    # SPECIAL: Stream Tool Start events (AIMessage with tool_calls)
                    if getattr(message_chunk, 'tool_calls', None):
                        for tc in message_chunk.tool_calls:
                            tool_name = tc.get('name', 'unknown_tool')
                            args = tc.get('args', {})
                            
                            # Extract file path from arguments for file operations
                            file_path = None
                            if isinstance(args, dict):
                                file_path = args.get('file_path') or args.get('path') or args.get('filename')
                            
                            yield json.dumps({
                                "type": "tool_start",
                                "tool": tool_name,
                                "file": file_path,
                                "content": str(args)[:200]  # Truncate for safety
                            }) + "\n"
                    
                    # SPECIAL: Stream ToolMessage results to frontend
                    if msg_type in ['ToolMessage', 'ToolMessageChunk']:
                        try:
                            tool_name = getattr(message_chunk, 'name', 'tool')
                            tool_content = message_chunk.content if hasattr(message_chunk, 'content') else str(message_chunk)
                            # Parse JSON if possible
                            import json as json_mod
                            try:
                                parsed = json_mod.loads(tool_content) if isinstance(tool_content, str) else tool_content
                                if isinstance(parsed, dict):
                                    is_success = parsed.get('success', False)
                                    
                                    # TERMINAL OUTPUT: Stream full output for terminal commands
                                    if tool_name == 'run_terminal_command':
                                        output = parsed.get('output') or parsed.get('stdout') or ''
                                        stderr = parsed.get('stderr') or ''
                                        yield json.dumps({
                                            "type": "terminal_output",
                                            "command": parsed.get('command', ''),
                                            "output": output,
                                            "stderr": stderr,
                                            "success": is_success,
                                            "exit_code": parsed.get('exit_code'),
                                            "duration_ms": parsed.get('duration_ms', 0),
                                            "execution_mode": parsed.get('execution_mode', 'unknown')
                                        }) + "\n"
                                    
                                    # Also send generic tool_result for UI
                                    yield json.dumps({
                                        "type": "tool_result",
                                        "tool": tool_name,
                                        "success": is_success,
                                        "file": parsed.get('relative_path') or parsed.get('path', ''),
                                        "preview": str(tool_content)[:200]
                                    }) + "\n"
                            except:
                                pass
                        except Exception as e:
                            logger.debug(f"[STREAM] ToolMessage parse error: {e}")
                        continue
                    
                    # Extract content from the message chunk
                    content = ""
                    if hasattr(message_chunk, 'content'):
                        raw_content = message_chunk.content
                        # Handle list format: [{'type': 'text', 'text': '...'}]
                        if isinstance(raw_content, list):
                            text_parts = []
                            for item in raw_content:
                                if isinstance(item, dict) and 'text' in item:
                                    text_parts.append(item['text'])
                                elif isinstance(item, str):
                                    text_parts.append(item)
                            content = ''.join(text_parts)
                        else:
                            content = raw_content
                    elif isinstance(message_chunk, dict) and 'content' in message_chunk:
                        content = message_chunk['content']
                    elif isinstance(message_chunk, str):
                        content = message_chunk
                    else:
                        # Skip if not extractable
                        continue
                    
                    # Skip empty content
                    if not content:
                        continue
                    
                    # Track node changes and emit phase events
                    if node_name != current_node:
                        current_node = node_name
                        logger.info(f"[STREAM] Entered node: {node_name}")
                        
                        # Map node names to phase events
                        phase_map = {
                            'planner': 'planning',
                            'coder': 'coding',
                            'validator': 'validating',
                            'fixer': 'coding',  # Fixer is part of coding loop
                            'chat': 'planning', # Chat uses planning phase for UI
                        }
                        phase = phase_map.get(node_name.lower())
                        if phase:
                            yield json.dumps({
                                "type": "phase",
                                "phase": phase
                            }) + "\n"
                            
                            # Emit thinking section start for this node
                            title_map = {
                                'orchestrator': '🧠 Analyzing Request',
                                'planner': '📝 Planning Implementation',
                                'coder': '💻 Writing Code',
                                'validator': '✓ Validating Build',
                                'fixer': '🔧 Fixing Issues',
                                'chat': '💬 Responding',
                            }
                            title = title_map.get(node_name.lower(), f'Processing ({node_name})')
                            yield json.dumps({
                                "type": "thinking_start",
                                "node": node_name,
                                "title": title
                            }) + "\n"
                    
                    # ============================================================
                    # STREAMING: Clean, simple content extraction
                    # Only stream human-readable text to the frontend
                    # ============================================================
                    
                    # Skip if content isn't a string (could be internal data)
                    if not isinstance(content, str):
                        continue
                    
                    # SUPPRESS: Orchestrator streams raw JSON (intent classification)
                    # User doesn't need to see this - they already see "Analyzing Request" status
                    if node_name.lower() == 'orchestrator':
                        continue
                    
                    # FILTER: Planner streams JSON plan - extract only useful text
                    if node_name == 'planner':
                        filtered = planner_filter.process_chunk(content)
                        if not filtered.strip():
                           continue
                        text = filtered.strip()
                    else:
                        text = content.strip()
                    if not text:
                        continue
                    
                    # SKIP: Internal system markers (use EXACT phrases, not substrings)
                    skip_phrases = [
                        'ACTION REQUIRED:', 
                        'MANDATORY FIRST STEP',
                        'SCAFFOLDING CHECK:',
                        '"task_type":',  # JSON field markers
                        '"action":',
                    ]
                    if any(phrase in text for phrase in skip_phrases):
                        continue
                    
                    # Stream as message (chat node) or thinking (other nodes)
                    is_chat = node_name.lower() in ['chat', 'chatter']
                    yield json.dumps({
                        "type": "message" if is_chat else "thinking",
                        "node": node_name,
                        "content": text
                    }) + "\n"
                    
                    # Handle dict format (other stream modes)
                    if isinstance(event, dict):
                        for node_name, state_update in event.items():
                            if node_name != current_node:
                                current_node = node_name
                                logger.info(f"[STREAM] Node update: {node_name}")
                            
                            messages = state_update.get("messages", [])
                            latest_msg = messages[-1] if messages else None
                            if latest_msg:
                                content = latest_msg.content if hasattr(latest_msg, "content") else str(latest_msg)
                                chunk = {
                                    "type": "message",
                                    "node": node_name,
                                    "content": content
                                }
                                yield json.dumps(chunk) + "\n"
                            
                            if "phase" in state_update:
                                logger.info(f"[STREAM] Phase change: {state_update['phase']}")
                                yield json.dumps({
                                    "type": "phase",
                                    "phase": state_update["phase"]
                                }) + "\n"
                            
                except Exception as parse_error:
                    logger.error(f"[STREAM] Error parsing event: {parse_error}", exc_info=True)
                    continue
                    
            logger.info("[STREAM] Pipeline completed successfully")
            
            # Try to get final state info
            preview_url = None
            is_awaiting_confirmation = False
            plan_summary = ""
            
            try:
                # Get final state from the graph
                final_state = await graph.aget_state(config)
                if final_state and hasattr(final_state, 'values'):
                    result = final_state.values.get('result', {})
                    phase = final_state.values.get('phase', '')
                    
                    if result:
                        preview_url = result.get('preview_url')
                        logger.info(f"[STREAM] Preview URL from state: {preview_url}")
                    
                    # Check if we're waiting for user confirmation (HITL)
                    if phase in ['plan_ready', 'complete'] and not preview_url:
                        # Check if scaffolding is done but no files written yet
                        completed_files = final_state.values.get('completed_files', [])
                        if len(completed_files) == 0:
                            is_awaiting_confirmation = True
                            # Try to get plan summary
                            artifacts = final_state.values.get('artifacts', {})
                            plan = artifacts.get('plan', {})
                            if isinstance(plan, dict):
                                plan_summary = plan.get('summary', 'Plan ready for your review.')
                            logger.info("[STREAM] HITL: Awaiting user confirmation")
                            
            except Exception as e:
                logger.debug(f"[STREAM] Could not get preview from state: {e}")
            
            # Emit plan_review event if awaiting confirmation
            if is_awaiting_confirmation:
                yield json.dumps({
                    "type": "plan_review",
                    "content": plan_summary or "Implementation plan is ready. Review and approve to proceed with coding."
                }) + "\n"
            
            # Emit completion with preview_url for Electron to display
            yield json.dumps({
                "type": "complete", 
                "content": "Pipeline completed successfully",
                "preview_url": preview_url
            }) + "\n"
            
        except Exception as e:
            logger.error(f"[STREAM] Pipeline error: {e}", exc_info=True)
            yield json.dumps({"type": "error", "content": str(e)}) + "\n"

    return StreamingResponse(response_generator(), media_type="application/x-ndjson")

# Include Routers
app.include_router(auth_router, tags=["Authentication"])
app.include_router(google_auth_router)  # Google OAuth routes
app.include_router(preview_router)
app.include_router(agent_router)

# Import and include Artifacts Router
from app.api.artifacts import router as artifacts_router
app.include_router(artifacts_router)

# Import and include Diagnostics Router
from app.api.diagnostics import router as diagnostics_router
app.include_router(diagnostics_router)

# Import and include Billing Router
from app.api.billing import router as billing_router
app.include_router(billing_router)

# Import and include Runs Router (Agent Dashboard)
from app.api.runs import router as runs_router
app.include_router(runs_router)

@app.get("/")
def read_root():
    return {"message": "ShipS* Backend is Running"}
