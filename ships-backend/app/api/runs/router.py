"""
Agent Runs API

FastAPI router for managing agent runs.
Each run represents a feature branch with its own agent pipeline.
"""

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
import uuid
import json
import asyncio

router = APIRouter(prefix="/api/runs", tags=["runs"])

# In-memory storage for MVP (replace with database later)
runs_store: dict = {}
websocket_connections: List[WebSocket] = []


# ============================================================================
# Pydantic Models
# ============================================================================

class Screenshot(BaseModel):
    id: str
    run_id: str = Field(alias="runId")
    timestamp: str
    image_path: str = Field(alias="imagePath")
    thumbnail_path: Optional[str] = Field(None, alias="thumbnailPath")
    git_commit_hash: str = Field(alias="gitCommitHash")
    agent_phase: str = Field(alias="agentPhase")
    description: str = ""
    
    class Config:
        populate_by_name = True


class AgentRun(BaseModel):
    id: str
    title: str
    prompt: str
    branch: str
    port: int = 0
    status: str = "pending"
    current_agent: Optional[str] = Field(None, alias="currentAgent")
    agent_message: str = Field("", alias="agentMessage")
    screenshots: List[Screenshot] = []
    files_changed: List[str] = Field([], alias="filesChanged")
    commit_count: int = Field(0, alias="commitCount")
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")
    is_primary: bool = Field(False, alias="isPrimary")
    
    class Config:
        populate_by_name = True


class CreateRunRequest(BaseModel):
    prompt: str
    title: Optional[str] = None


class FeedbackRequest(BaseModel):
    message: str


class RollbackRequest(BaseModel):
    screenshot_id: str = Field(alias="screenshotId")
    commit_hash: str = Field(alias="commitHash")
    
    class Config:
        populate_by_name = True


# ============================================================================
# WebSocket Event Broadcasting
# ============================================================================

async def broadcast_event(event: dict):
    """Broadcast an event to all connected WebSocket clients."""
    if not websocket_connections:
        return
    
    message = json.dumps(event)
    disconnected = []
    
    for ws in websocket_connections:
        try:
            await ws.send_text(message)
        except Exception:
            disconnected.append(ws)
    
    # Remove disconnected clients
    for ws in disconnected:
        if ws in websocket_connections:
            websocket_connections.remove(ws)


# ============================================================================
# REST Endpoints
# ============================================================================

@router.get("", response_model=List[AgentRun])
async def list_runs():
    """Get all agent runs."""
    return list(runs_store.values())


@router.post("", response_model=AgentRun)
async def create_run(request: CreateRunRequest):
    """Create a new agent run."""
    run_id = str(uuid.uuid4())[:8]
    now = datetime.utcnow().isoformat() + "Z"
    
    # Generate branch name
    slug = request.prompt.lower().replace(" ", "-")[:20]
    branch = f"work/{slug}-{run_id}"
    
    # Determine if this is the first (primary) run
    is_primary = len(runs_store) == 0
    
    run = AgentRun(
        id=run_id,
        title=request.title or request.prompt[:50],
        prompt=request.prompt,
        branch=branch,
        port=3000 + len(runs_store),  # Assign sequential port
        status="pending",
        currentAgent=None,
        agentMessage="",
        screenshots=[],
        filesChanged=[],
        commitCount=0,
        createdAt=now,
        updatedAt=now,
        isPrimary=is_primary,
    )
    
    runs_store[run_id] = run.model_dump(by_alias=True)
    
    # Broadcast creation event
    await broadcast_event({
        "type": "run_created",
        "run": runs_store[run_id],
    })
    
    # TODO: Trigger agent pipeline via Electron IPC
    # For now, just set status to running after a delay
    asyncio.create_task(_simulate_agent_start(run_id))
    
    return runs_store[run_id]


async def _simulate_agent_start(run_id: str):
    """Simulate agent starting (for development)."""
    await asyncio.sleep(1)
    
    if run_id not in runs_store:
        return
    
    runs_store[run_id]["status"] = "planning"
    runs_store[run_id]["currentAgent"] = "planner"
    runs_store[run_id]["agentMessage"] = "Analyzing request..."
    runs_store[run_id]["updatedAt"] = datetime.utcnow().isoformat() + "Z"
    
    await broadcast_event({
        "type": "run_status",
        "runId": run_id,
        "status": "planning",
        "currentAgent": "planner",
        "agentMessage": "Analyzing request...",
    })


@router.get("/{run_id}", response_model=AgentRun)
async def get_run(run_id: str):
    """Get a specific run by ID."""
    if run_id not in runs_store:
        raise HTTPException(status_code=404, detail="Run not found")
    return runs_store[run_id]


@router.delete("/{run_id}")
async def delete_run(run_id: str):
    """Delete a run."""
    if run_id not in runs_store:
        raise HTTPException(status_code=404, detail="Run not found")
    
    # Don't allow deleting primary run
    if runs_store[run_id].get("isPrimary"):
        raise HTTPException(status_code=400, detail="Cannot delete primary run")
    
    del runs_store[run_id]
    
    await broadcast_event({
        "type": "run_deleted",
        "runId": run_id,
    })
    
    return {"success": True}


@router.post("/{run_id}/pause")
async def pause_run(run_id: str):
    """Pause a running agent."""
    if run_id not in runs_store:
        raise HTTPException(status_code=404, detail="Run not found")
    
    runs_store[run_id]["status"] = "paused"
    runs_store[run_id]["currentAgent"] = None
    runs_store[run_id]["updatedAt"] = datetime.utcnow().isoformat() + "Z"
    
    await broadcast_event({
        "type": "run_status",
        "runId": run_id,
        "status": "paused",
        "currentAgent": None,
        "agentMessage": "Paused",
    })
    
    return {"success": True}


@router.post("/{run_id}/resume")
async def resume_run(run_id: str):
    """Resume a paused agent."""
    if run_id not in runs_store:
        raise HTTPException(status_code=404, detail="Run not found")
    
    runs_store[run_id]["status"] = "running"
    runs_store[run_id]["agentMessage"] = "Resuming..."
    runs_store[run_id]["updatedAt"] = datetime.utcnow().isoformat() + "Z"
    
    await broadcast_event({
        "type": "run_status",
        "runId": run_id,
        "status": "running",
        "currentAgent": "coder",
        "agentMessage": "Resuming...",
    })
    
    return {"success": True}


@router.post("/{run_id}/feedback")
async def send_feedback(run_id: str, request: FeedbackRequest):
    """Send feedback to the agent."""
    if run_id not in runs_store:
        raise HTTPException(status_code=404, detail="Run not found")
    
    # Store feedback (in real implementation, this would be processed by agent)
    runs_store[run_id]["agentMessage"] = f"Processing feedback: {request.message[:50]}..."
    runs_store[run_id]["updatedAt"] = datetime.utcnow().isoformat() + "Z"
    
    await broadcast_event({
        "type": "run_status",
        "runId": run_id,
        "status": runs_store[run_id]["status"],
        "currentAgent": "coder",
        "agentMessage": f"Processing feedback: {request.message[:50]}...",
    })
    
    # TODO: Actually process feedback through agent pipeline
    
    return {"success": True}


@router.post("/{run_id}/rollback")
async def rollback_run(run_id: str, request: RollbackRequest):
    """Rollback to a specific screenshot/commit."""
    if run_id not in runs_store:
        raise HTTPException(status_code=404, detail="Run not found")
    
    # TODO: Execute git checkout to the specified commit
    # For now, just update the message
    runs_store[run_id]["agentMessage"] = f"Rolling back to commit {request.commit_hash[:7]}..."
    runs_store[run_id]["updatedAt"] = datetime.utcnow().isoformat() + "Z"
    
    await broadcast_event({
        "type": "run_status",
        "runId": run_id,
        "status": "running",
        "currentAgent": "coder",
        "agentMessage": f"Rolling back to commit {request.commit_hash[:7]}...",
    })
    
    return {"success": True}


# ============================================================================
# WebSocket Endpoint
# ============================================================================

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time run updates."""
    await websocket.accept()
    websocket_connections.append(websocket)
    
    try:
        # Send current runs on connect
        await websocket.send_text(json.dumps({
            "type": "initial_state",
            "runs": list(runs_store.values()),
        }))
        
        # Keep connection alive
        while True:
            try:
                # Wait for messages (ping/pong handled automatically)
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30)
                
                # Handle client messages if needed
                message = json.loads(data)
                if message.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
                    
            except asyncio.TimeoutError:
                # Send keepalive
                await websocket.send_text(json.dumps({"type": "keepalive"}))
                
    except WebSocketDisconnect:
        pass
    finally:
        if websocket in websocket_connections:
            websocket_connections.remove(websocket)
