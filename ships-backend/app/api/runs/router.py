"""
Agent Runs API

FastAPI router for managing agent runs.
Each run represents a feature branch with its own agent pipeline.
Now persists to PostgreSQL via SQLAlchemy.
"""

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Depends, Request
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
import uuid
import json
import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, String

from app.database.connection import get_session
from app.models.agent_runs import AgentRun as AgentRunModel
from app.models import User

logger = logging.getLogger("ships.runs")

router = APIRouter(prefix="/api/runs", tags=["runs"])

# WebSocket connections (still in-memory - that's fine for real-time)
websocket_connections: List[WebSocket] = []


async def get_current_user_id(
    request: Request,
    db: AsyncSession = Depends(get_session)
) -> uuid.UUID:
    """
    Get current authenticated user's ID from session.
    
    Requires user to be logged in via OAuth (Google/GitHub).
    Raises 401 if not authenticated.
    """
    session_user = request.session.get('user')
    
    if not session_user or not session_user.get('email'):
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Please log in."
        )
    
    # Fetch user from database to get the UUID
    result = await db.execute(
        select(User).where(User.email == session_user['email'])
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=401,
            detail="User not found. Please log in again."
        )
    
    return user.id


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
    base_branch: str = Field("main", alias="baseBranch")  # Branch this was forked from
    project_path: str = Field("", alias="projectPath")  # Filesystem path to project
    port: int = 0
    status: str = "pending"
    current_agent: Optional[str] = Field(None, alias="currentAgent")
    agent_message: str = Field("", alias="agentMessage")
    screenshots: List[Screenshot] = []
    files_changed: List[str] = Field([], alias="filesChanged")
    commit_count: int = Field(0, alias="commitCount")
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")
    
    class Config:
        populate_by_name = True


class CreateRunRequest(BaseModel):
    prompt: str
    title: Optional[str] = None
    project_path: Optional[str] = Field(None, alias="projectPath")
    command_preference: Optional[str] = Field(None, alias="commandPreference")
    
    class Config:
        populate_by_name = True


class FeedbackRequest(BaseModel):
    message: str
    model: Optional[str] = "gemini-1.5-pro-002"


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
async def list_runs(
    db: AsyncSession = Depends(get_session),
    user_id: uuid.UUID = Depends(get_current_user_id)
):
    """Get all agent runs for the current user."""
    result = await db.execute(
        select(AgentRunModel)
        .where(AgentRunModel.user_id == user_id)
        .order_by(desc(AgentRunModel.created_at))
    )
    runs = result.scalars().all()
    
    # Convert to API response format
    return [_model_to_response(run) for run in runs]


@router.post("", response_model=AgentRun)
async def create_run(
    request: CreateRunRequest,
    db: AsyncSession = Depends(get_session),
    user_id: uuid.UUID = Depends(get_current_user_id)
):
    """Create a new agent run."""
    run_id = uuid.uuid4()
    
    # Generate branch name - industry standard feature branch naming
    from datetime import datetime
    slug = request.prompt.lower()
    slug = ''.join(c if c.isalnum() or c == ' ' else '' for c in slug)  # Remove special chars
    slug = slug.strip().replace(' ', '-')[:30]  # Hyphenate, limit length
    slug = '-'.join(filter(None, slug.split('-')))  # Remove empty parts
    timestamp = datetime.now().strftime('%m%d')
    branch = f"feature/ships-{slug}-{timestamp}"
    
    # Create database model
    db_run = AgentRunModel(
        id=run_id,
        user_id=user_id,
        project_path=request.project_path or "/tmp/ships",  # TODO: Get from context
        branch_name=branch,
        user_request=request.prompt,
        status="pending",
        run_metadata={
            "title": request.title or request.prompt[:50],
            "port": 3000,
            "command_preference": request.command_preference or "auto",
        }
    )
    
    db.add(db_run)
    await db.commit()
    await db.refresh(db_run)
    
    run_response = _model_to_response(db_run)
    
    # Broadcast creation event
    await broadcast_event({
        "type": "run_created",
        "run": run_response,
    })
    
    logger.info(f"[RUNS] Created run {run_id} for user {user_id}")
    
    return run_response


def _model_to_response(run: AgentRunModel) -> dict:
    """Convert SQLAlchemy model to API response format."""
    metadata = run.run_metadata or {}
    
    # Merge live preview data if available
    from app.services.preview_manager import preview_manager
    
    # Check both full UUID and short ID to find running instance
    full_id = str(run.id)
    short_id = full_id[:8]
    
    live_status = preview_manager.get_status(full_id)
    if not live_status or not live_status.get("is_alive"):
        live_status = preview_manager.get_status(short_id)
            
    # Use live port if running, otherwise DB metadata
    port = metadata.get("port", 3000)
    status = run.status
    url = None
    
    if live_status:
        port = live_status.get("port", port)
        if live_status.get("is_alive") or live_status.get("status") in ("starting", "running"):
            url = live_status.get("url")

    return {
        "id": str(run.id)[:8],  # Short ID for UI
        "fullId": str(run.id),  # Full UUID for port calculations
        "title": metadata.get("title", run.user_request[:50] if run.user_request else "Untitled"),
        "prompt": run.user_request or "",
        "branch": run.branch_name or "",
        "baseBranch": metadata.get("base_branch", "main"),  # Branch this forked from
        "projectPath": run.project_path,  # Filesystem path for preview
        "port": port,
        "previewUrl": url, 
        "previewStatus": live_status.get("status") if live_status else "stopped",
        "status": status,
        "currentAgent": metadata.get("current_agent"),
        "agentMessage": metadata.get("agent_message", ""),
        "screenshots": [],  # TODO: Load from separate table
        "filesChanged": metadata.get("files_changed", []),
        "commitCount": metadata.get("commit_count", 0),
        "createdAt": run.created_at.isoformat() + "Z" if run.created_at else "",
        "updatedAt": run.created_at.isoformat() + "Z" if run.created_at else "",
    }



@router.get("/{run_id}", response_model=AgentRun)
async def get_run(
    run_id: str,
    db: AsyncSession = Depends(get_session),
    user_id: uuid.UUID = Depends(get_current_user_id)
):
    """Get a specific run by ID."""
    # Run IDs are stored as short 8-char prefixes in UI, match by prefix
    result = await db.execute(
        select(AgentRunModel)
        .where(AgentRunModel.user_id == user_id)
        .where(AgentRunModel.id.cast(String).like(f"{run_id}%"))
    )
    run = result.scalar_one_or_none()
    
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return _model_to_response(run)


@router.delete("/{run_id}")
async def delete_run(
    run_id: str,
    db: AsyncSession = Depends(get_session),
    user_id: uuid.UUID = Depends(get_current_user_id)
):
    """Delete a run."""
    result = await db.execute(
        select(AgentRunModel)
        .where(AgentRunModel.user_id == user_id)
        .where(AgentRunModel.id.cast(String).like(f"{run_id}%"))
    )
    run = result.scalar_one_or_none()
    
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    
    await db.delete(run)
    await db.commit()
    
    await broadcast_event({
        "type": "run_deleted",
        "runId": run_id,
    })
    
    logger.info(f"[RUNS] Deleted run {run_id}")
    return {"success": True}


@router.post("/{run_id}/pause")
async def pause_run(
    run_id: str,
    db: AsyncSession = Depends(get_session),
    user_id: uuid.UUID = Depends(get_current_user_id)
):
    """Pause a running agent."""
    result = await db.execute(
        select(AgentRunModel)
        .where(AgentRunModel.user_id == user_id)
        .where(AgentRunModel.id.cast(String).like(f"{run_id}%"))
    )
    run = result.scalar_one_or_none()
    
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    
    run.status = "paused"
    run.run_metadata = {**(run.run_metadata or {}), "current_agent": None, "agent_message": "Paused"}
    await db.commit()
    
    await broadcast_event({
        "type": "run_status",
        "runId": run_id,
        "status": "paused",
        "currentAgent": None,
        "agentMessage": "Paused",
    })
    
    return {"success": True}


@router.post("/{run_id}/resume")
async def resume_run(
    run_id: str,
    db: AsyncSession = Depends(get_session),
    user_id: uuid.UUID = Depends(get_current_user_id)
):
    """Resume a paused agent."""
    result = await db.execute(
        select(AgentRunModel)
        .where(AgentRunModel.user_id == user_id)
        .where(AgentRunModel.id.cast(String).like(f"{run_id}%"))
    )
    run = result.scalar_one_or_none()
    
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    
    run.status = "running"
    run.run_metadata = {**(run.run_metadata or {}), "agent_message": "Resuming..."}
    await db.commit()
    
    await broadcast_event({
        "type": "run_status",
        "runId": run_id,
        "status": "running",
        "currentAgent": "coder",
        "agentMessage": "Resuming...",
    })
    
    return {"success": True}


@router.post("/{run_id}/feedback")
async def send_feedback(
    run_id: str, 
    request: FeedbackRequest,
    db: AsyncSession = Depends(get_session),
    user_id: uuid.UUID = Depends(get_current_user_id)
):
    """Send feedback to the agent."""
    result = await db.execute(
        select(AgentRunModel)
        .where(AgentRunModel.user_id == user_id)
        .where(AgentRunModel.id.cast(String).like(f"{run_id}%"))
    )
    run = result.scalar_one_or_none()
    
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    
    # Store feedback in metadata
    run.run_metadata = {
        **(run.run_metadata or {}), 
        "agent_message": f"Processing feedback with {request.model}: {request.message[:50]}...",
        "last_model_used": request.model
    }
    await db.commit()
    
    await broadcast_event({
        "type": "run_status",
        "runId": run_id,
        "status": run.status,
        "currentAgent": "coder",
        "agentMessage": f"Processing feedback: {request.message[:50]}...",
    })
    
    # TODO: Actually process feedback through agent pipeline
    
    return {"success": True}


@router.post("/{run_id}/rollback")
async def rollback_run(
    run_id: str, 
    request: RollbackRequest,
    db: AsyncSession = Depends(get_session),
    user_id: uuid.UUID = Depends(get_current_user_id)
):
    """Rollback to a specific screenshot/commit."""
    result = await db.execute(
        select(AgentRunModel)
        .where(AgentRunModel.user_id == user_id)
        .where(AgentRunModel.id.cast(String).like(f"{run_id}%"))
    )
    run = result.scalar_one_or_none()
    
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    
    # TODO: Execute git checkout to the specified commit
    run.run_metadata = {
        **(run.run_metadata or {}),
        "agent_message": f"Rolling back to commit {request.commit_hash[:7]}..."
    }
    run.status = "running"
    await db.commit()
    
    await broadcast_event({
        "type": "run_status",
        "runId": run_id,
        "status": "running",
        "currentAgent": "coder",
        "agentMessage": f"Rolling back to commit {request.commit_hash[:7]}...",
    })
    
    return {"success": True}


from app.services.preview_manager import preview_manager

@router.delete("/{run_id}")
async def delete_run(
    run_id: str,
    db: AsyncSession = Depends(get_session),
    user_id: uuid.UUID = Depends(get_current_user_id)
):
    """Delete a run and stop its preview."""
    # Find the run
    result = await db.execute(
        select(AgentRunModel)
        .where(AgentRunModel.user_id == user_id)
        .where(AgentRunModel.id.cast(String).like(f"{run_id}%"))
    )
    run = result.scalar_one_or_none()
    
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    
    # 1. STOP PREVIEW (Kills processes)
    # Use full UUID or whatever runs map uses (usually same ID)
    preview_manager.stop_all() # Or stop specific?
    # Actually, preview_manager keys by run_id. Use the full ID from DB if possible, or the one passed?
    # The run_id passed in might be short. Let's use the one from DB.
    try:
        preview_manager._stop_instance(str(run.id))
        # Also try short ID just in case
        if len(run_id) < 32:
             preview_manager._stop_instance(run_id)
    except Exception as e:
        logger.warning(f"[RUNS] Failed to stop preview for {run_id}: {e}")

    # 2. DELETE FROM DB
    await db.delete(run)
    await db.commit()
    
    # 3. BROADCAST DELETION
    await broadcast_event({
        "type": "run_deleted",
        "runId": str(run.id)
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
        # TODO: Fetch initial state from DB if needed
        # For now, just confirm connection
        await websocket.send_text(json.dumps({
            "type": "connected",
            "message": "Connected to Runs WebSocket"
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
    except Exception as e:
        logger.error(f"[WS] WebSocket error: {e}")
    finally:
        if websocket in websocket_connections:
            websocket_connections.remove(websocket)
