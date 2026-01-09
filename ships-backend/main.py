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

logger = logging.getLogger("ships")

app = FastAPI(title="ShipS* Backend")

# Startup event - check database connection
@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    logger.info("🚀 Ships* Backend starting...")
    
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
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

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

@preview_router.get("/status")
async def get_status():
    # Dynamically check if process is actually running (not just the flag)
    process_exists = preview_manager.process is not None
    process_poll = preview_manager.process.poll() if process_exists else "N/A"
    is_actually_running = process_exists and process_poll is None
    
    # Debug logging
    logger.debug(f"[PREVIEW_STATUS] process={process_exists}, poll={process_poll}, is_running={is_actually_running}, url={preview_manager.current_url}")
    
    return {
        "is_running": is_actually_running,
        "logs": preview_manager.logs[-50:],
        "url": preview_manager.current_url,
        "project_path": preview_manager.current_project_path,
        "focus_requested": preview_manager.focus_requested
    }

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

from fastapi.responses import StreamingResponse
import json
from app.graphs.agent_graph import stream_pipeline

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
            
            async for event in stream_pipeline(body.prompt, project_path=effective_project_path, settings=body.settings):
                # With subgraphs=True + stream_mode="messages", events are:
                # (namespace_tuple, (message_chunk, metadata))
                # namespace_tuple can be () for main graph or ('node:task_id',) for subgraphs
                
                try:
                    # Handle subgraphs=True format: (namespace, (message_chunk, metadata))
                    if isinstance(event, tuple) and len(event) >= 2:
                        first_element = event[0]
                        second_element = event[1]
                        
                        # Check if this is the subgraphs format (namespace, data)
                        # namespace is always a tuple (empty or with node info)
                        if isinstance(first_element, tuple):
                            # This is subgraphs format: (namespace, (message_chunk, metadata))
                            namespace = first_element
                            inner_data = second_element
                            
                            # Extract node name from namespace or inner metadata
                            if namespace and len(namespace) > 0:
                                # namespace looks like ('planner:uuid',) - extract node name
                                node_info = namespace[0] if namespace else ""
                                node_name = node_info.split(':')[0] if ':' in str(node_info) else str(node_info)
                            else:
                                node_name = "agent"
                            
                            # inner_data should be (message_chunk, metadata)
                            if isinstance(inner_data, tuple) and len(inner_data) >= 2:
                                message_chunk = inner_data[0]
                                metadata = inner_data[1]
                            else:
                                # Fallback: treat inner_data as the message
                                message_chunk = inner_data
                                metadata = {}
                        else:
                            # Original format without subgraphs: (message_chunk, metadata)
                            message_chunk = first_element
                            metadata = second_element
                            node_name = metadata.get('langgraph_node', 'agent') if isinstance(metadata, dict) else 'agent'
                        
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
                            content = message_chunk.content
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
                        # STREAMING: Show agent thinking in real-time
                        # ============================================================
                        
                        # Handle string content
                        if isinstance(content, str) and content.strip():
                            text = content.strip()
                            
                            # Check if this is structured JSON output
                            is_json = (text.startswith('{') and text.endswith('}')) or \
                                      (text.startswith('[') and text.endswith(']'))
                            
                            if is_json:
                                # Try to extract meaningful content from JSON
                                try:
                                    import json as json_mod
                                    parsed = json_mod.loads(text)
                                    
                                    # Handle different structured outputs
                                    if isinstance(parsed, dict):
                                        # Planner output - emit plan_created + summary
                                        if 'summary' in parsed and 'tasks' in parsed:
                                            task_count = len(parsed.get('tasks', []))
                                            yield json.dumps({
                                                "type": "plan_created",
                                                "summary": parsed.get('summary', 'Plan created'),
                                                "task_count": task_count,
                                                "folders": len(parsed.get('folders', []))
                                            }) + "\n"
                                            # Also stream as readable thinking
                                            yield json.dumps({
                                                "type": "thinking",
                                                "node": node_name,
                                                "content": f"Created plan: {parsed.get('summary', '')}\n{task_count} tasks to implement."
                                            }) + "\n"
                                        # Orchestrator decision
                                        elif 'decision' in parsed:
                                            decision = parsed.get('decision', '')
                                            reasoning = parsed.get('reasoning', '')[:200] if parsed.get('reasoning') else ''
                                            yield json.dumps({
                                                "type": "thinking",
                                                "node": node_name,
                                                "content": f"Decision: {decision}" + (f"\n{reasoning}" if reasoning else "")
                                            }) + "\n"
                                        # Intent classifier
                                        elif 'task_type' in parsed:
                                            yield json.dumps({
                                                "type": "thinking",
                                                "node": node_name,
                                                "content": f"Detected intent: {parsed.get('task_type', 'unknown')}"
                                            }) + "\n"
                                except:
                                    # JSON parse failed - skip internal JSON
                                    pass
                            else:
                                # Plain text - stream directly
                                # Skip system prompts and internal markers
                                skip_markers = ['ACTION REQUIRED', 'MANDATORY FIRST', 'SCAFFOLDING CHECK']
                                if not any(marker in text for marker in skip_markers):
                                    if node_name.lower() in ['chat', 'chatter']:
                                        yield json.dumps({
                                            "type": "message",
                                            "node": node_name,
                                            "content": text
                                        }) + "\n"
                                    else:
                                        # Other nodes - stream as thinking
                                        yield json.dumps({
                                            "type": "thinking",
                                            "node": node_name,
                                            "content": text
                                        }) + "\n"
                            
                        # Handle list content (Gemini sometimes returns list of dicts)
                        elif isinstance(content, list):
                            for item in content:
                                if isinstance(item, dict) and 'text' in item:
                                    text = item['text'].strip()
                                    if text:
                                        if node_name.lower() in ['chat', 'chatter']:
                                            yield json.dumps({
                                                "type": "message",
                                                "node": node_name,
                                                "content": text
                                            }) + "\n"
                                        else:
                                            yield json.dumps({
                                                "type": "thinking",
                                                "node": node_name,
                                                "content": text
                                            }) + "\n"
                    
                    # Handle dict format (other stream modes)
                    elif isinstance(event, dict):
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

@app.get("/")
def read_root():
    return {"message": "ShipS* Backend is Running"}
