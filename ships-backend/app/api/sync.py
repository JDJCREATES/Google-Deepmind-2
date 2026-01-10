"""
Artifact Sync API Endpoints

Provides REST endpoints for:
- Starting/stopping sync
- Force full sync
- Getting sync status
"""

from fastapi import APIRouter, HTTPException
from typing import Optional
import os

from app.services.sync import start_sync, stop_sync, get_sync_engine

router = APIRouter(prefix="/api/sync", tags=["sync"])


@router.post("/start")
async def start_artifact_sync(project_path: str):
    """Start watching a project for file changes."""
    if not os.path.exists(project_path):
        raise HTTPException(status_code=404, detail="Project path not found")
    
    try:
        engine = start_sync(project_path)
        return {
            "success": True,
            "message": f"Sync started for {project_path}",
            "watching": True
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stop")
async def stop_artifact_sync():
    """Stop watching for file changes."""
    stop_sync()
    return {
        "success": True,
        "message": "Sync stopped",
        "watching": False
    }


@router.post("/full")
async def force_full_sync(project_path: Optional[str] = None):
    """Force a full artifact resync."""
    engine = get_sync_engine()
    
    if not engine and not project_path:
        raise HTTPException(
            status_code=400, 
            detail="No active sync. Provide project_path or start sync first."
        )
    
    if project_path:
        from app.services.sync import ArtifactSyncEngine
        engine = ArtifactSyncEngine(project_path)
    
    success = engine.force_full_sync()
    
    return {
        "success": success,
        "message": "Full sync complete" if success else "Full sync failed"
    }


@router.get("/status")
async def get_sync_status():
    """Get current sync engine status."""
    engine = get_sync_engine()
    
    if not engine:
        return {
            "active": False,
            "project_path": None,
            "last_sync": None
        }
    
    return {
        "active": engine.observer and engine.observer.is_alive() if engine.observer else False,
        "project_path": str(engine.project_path),
        "last_sync": {
            k: v.isoformat() for k, v in engine.last_sync.items()
        },
        "pending_events": len(engine.pending_events)
    }


@router.get("/health")
async def get_sync_health(project_path: str):
    """Get sync health from sync_health.json."""
    import json
    from pathlib import Path
    
    health_path = Path(project_path) / ".ships" / "sync_health.json"
    
    if not health_path.exists():
        return {
            "status": "not_synced",
            "message": "No sync has been performed yet"
        }
    
    try:
        with open(health_path, "r") as f:
            return json.load(f)
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }
