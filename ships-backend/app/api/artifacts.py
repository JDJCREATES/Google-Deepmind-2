from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from typing import List, Optional
import os
import shutil
import uuid
from datetime import datetime
from pydantic import BaseModel

router = APIRouter(prefix="/api", tags=["artifacts"])

# Models
class ArtifactCreate(BaseModel):
    type: str
    projectId: str
    data: dict

class ArtifactUpdate(BaseModel):
    data: dict
    updatedBy: str

# Helper to resolve project path (Mock implementation)
# In production, this should look up from a database or secure registry
def get_project_path(project_id: str) -> str:
    # If project_id is a path, use it. Otherwise, assume it's an ID.
    if os.path.isabs(project_id) and os.path.exists(project_id):
        return project_id
    # Fallback or mapping logic here
    # For now, we assume user passes the absolute path as ID for local dev
    return project_id

# Storage helper
def get_artifact_dir(project_id: str) -> str:
    base_path = get_project_path(project_id)
    artifact_dir = os.path.join(base_path, ".ships", "artifacts")
    os.makedirs(artifact_dir, exist_ok=True)
    return artifact_dir

@router.get("/artifacts/{project_id}")
async def list_artifacts(project_id: str, type: Optional[str] = None):
    try:
        base_path = get_project_path(project_id)
        dot_ships = os.path.join(base_path, ".ships")
        artifacts = []
        
        if not os.path.exists(dot_ships):
            return {"projectId": project_id, "artifacts": [], "total": 0}

        # 1. Auto-discover System Artifacts (Planner outputs)
        # implementation_plan.md -> plan_manifest
        plan_path = os.path.join(dot_ships, "implementation_plan.md")
        if os.path.exists(plan_path):
            stat = os.stat(plan_path)
            artifacts.append({
                "id": "implementation_plan",
                "type": "plan_manifest",
                "title": "Implementation Plan",
                "projectId": project_id,
                "createdAt": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                "updatedAt": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "status": "active",
                "data": {"path": plan_path}
            })

        # task.md -> task_list
        task_path = os.path.join(dot_ships, "task.md")
        if os.path.exists(task_path):
            stat = os.stat(task_path)
            artifacts.append({
                "id": "task_list",
                "type": "task_list",
                "title": "Task Checklist",
                "projectId": project_id,
                "createdAt": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                "updatedAt": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "status": "active",
                "data": {"path": task_path}
            })

        # 2. Discover User/Agent Uploaded Artifacts in .ships/artifacts/
        artifact_dir = os.path.join(dot_ships, "artifacts")
        if os.path.exists(artifact_dir):
            for filename in os.listdir(artifact_dir):
                if filename.endswith(".json"):
                    try:
                        with open(os.path.join(artifact_dir, filename), "r") as f:
                            import json
                            metadata = json.load(f)
                            # Ensure ID maps to filename for easy retrieval
                            metadata["id"] = filename.replace(".json", "") 
                            artifacts.append(metadata)
                    except Exception as e:
                        print(f"Error reading artifact {filename}: {e}")

        # Filter by type if requested
        if type:
            artifacts = [a for a in artifacts if a["type"] == type]

        return {
            "projectId": project_id,
            "artifacts": artifacts,
            "total": len(artifacts)
        }
    except Exception as e:
        print(f"Error listing artifacts: {e}")
        # Return empty list on error instead of 500 to keep UI stable
        return {"projectId": project_id, "artifacts": [], "total": 0}

@router.get("/artifact/{artifact_id}")
async def get_artifact(artifact_id: str):
    # This is tricky because we don't have project_id in the path,
    # but the frontend might send it or we assume a single active project context.
    # For now, we search in the CURRENT active project (passed via query param would be better, 
    # but let's assume we can resolve it or search common paths).
    
    # HACK: Since we don't passed project_id to get_artifact in the frontend service url,
    # we'll look at the PWD or a known global project. 
    # Ideal fix: Update frontend to pass projectId query param.
    
    # For the specific system artifacts, we can rely on PWD or specific request.
    project_path = os.getcwd() # Default to CWD for now
    
    # If the artifact ID contains a path-like structure or is known system ID
    dot_ships = os.path.join(project_path, ".ships")
    
    artifact_data = None
    
    try:
        if artifact_id == "implementation_plan":
            target_path = os.path.join(dot_ships, "implementation_plan.md")
            if os.path.exists(target_path):
                stat = os.stat(target_path)
                with open(target_path, "r", encoding="utf-8") as f:
                    content = f.read()
                artifact_data = {
                    "id": "implementation_plan",
                    "type": "plan_manifest",
                    "title": "Implementation Plan",
                    "data": {
                        "content": content,
                        "language": "markdown"
                    },
                    "updatedAt": datetime.fromtimestamp(stat.st_mtime).isoformat()
                }

        elif artifact_id == "task_list":
            target_path = os.path.join(dot_ships, "task.md")
            if os.path.exists(target_path):
                stat = os.stat(target_path)
                with open(target_path, "r", encoding="utf-8") as f:
                    content = f.read()
                artifact_data = {
                    "id": "task_list",
                    "type": "task_list",
                    "title": "Task Checklist",
                    "data": {
                        "content": content,
                        "language": "markdown"
                    },
                    "updatedAt": datetime.fromtimestamp(stat.st_mtime).isoformat()
                }
        
        else:
            # Check user artifacts
            meta_path = os.path.join(dot_ships, "artifacts", f"{artifact_id}.json")
            if os.path.exists(meta_path):
                import json
                with open(meta_path, "r") as f:
                    artifact_data = json.load(f)
        
        if not artifact_data:
            raise HTTPException(status_code=404, detail="Artifact not found")
            
        return {"artifact": artifact_data}

    except Exception as e:
        print(f"Error getting artifact: {e}")
        raise HTTPException(status_code=500, detail=str(e))

