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
    
    # Kill orphaned preview processes (survived from previous backend crash/restart)
    logger.info("[STARTUP] Cleaning up orphaned preview processes...")
    result = preview_manager.kill_zombies()
    if result["killed_count"] > 0:
        logger.info(f"[STARTUP] 🧟 Killed {result['killed_count']} orphaned processes")
    
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

@preview_router.post("/stop/{run_id}")
async def stop_preview_by_id(run_id: str):
    preview_manager._stop_instance(run_id)
    return {"status": "stopped", "run_id": run_id}

@preview_router.post("/cleanup")
async def cleanup_previews(run_id: str = None, project_path: str = None):
    """
    Force kill processes.
    If run_id provided: Kill only the port for that run (Targeted).
    If no run_id: Kill ALL preview ports (Zombie Nuke).
    """
    if run_id:
        return preview_manager.kill_run_process(run_id, project_path)
    return preview_manager.kill_zombies()

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
    
    # =========================================================================
    # SMART CONTEXT DETECTION (Fix for "Open Preview" button sending root path)
    # =========================================================================
    from pathlib import Path

    def find_project_root(search_path: Path, depth: int = 2) -> Optional[Path]:
        """Recursively find a directory containing package.json or requirements.txt"""
        if not search_path.exists():
            return None
            
        # Check current level
        if (search_path / "package.json").exists() or (search_path / "requirements.txt").exists():
            return search_path
            
        if depth <= 0:
            return None
            
        # Check subdirectories
        try:
            # Sort to ensure consistent order, prefer shorter names (likely root apps)
            for item in sorted(search_path.iterdir(), key=lambda p: len(p.name)):
                if item.is_dir() and not item.name.startswith('.') and item.name != 'node_modules':
                    found = find_project_root(item, depth - 1)
                    if found:
                        return found
        except Exception as e:
            logger.warning(f"[API] Error scanning {search_path}: {e}")
            
        return None

    # 1. Resolve Path object
    path_obj = Path(project_path).resolve()
    
    # 2. Try to find logic root
    detected_path = find_project_root(path_obj)
    
    if detected_path:
        # If we found a valid root, use it
        if str(detected_path) != str(path_obj):
             logger.info(f"[API] 🔍 Auto-detected project root: {detected_path} (was {project_path})")
             project_path = str(detected_path)
             # Sync back to manager for future consistency
             preview_manager.current_project_path = project_path
    else:
        # 3. Fallback: Check synced path (from Pipeline/Graph)
        logger.info(f"[API] ⚠️ No package.json found in {project_path} or subfolders. Checking synced context...")
        synced_path = preview_manager.current_project_path
        if synced_path and synced_path != project_path:
            synced_obj = Path(synced_path)
            if find_project_root(synced_obj, depth=0): # Check if synced path is valid
                logger.info(f"[API] 🔄 Redirecting to synced agent path: {synced_path}")
                project_path = synced_path
    
    # =========================================================================

    
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
from app.streaming.pipeline import stream_pipeline

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
            
            # CRITICAL FIX: Pass user_id so run_id can be generated for step tracking
            async for chunk in stream_pipeline(
                body.prompt, 
                project_path=effective_project_path, 
                settings=body.settings, 
                artifact_context=body.artifact_context,
                user_id=user_id  # Pass user_id for run tracking
            ):
                yield chunk

            
            logger.info("[STREAM] Pipeline completed successfully")
            
            # Emit completion event (if not already handled by stream_pipeline)
            yield json.dumps({
                "type": "block_end",
                "final_content": "Pipeline completed.",
                "duration_ms": 0
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
