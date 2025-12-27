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
        artifact_dir = get_artifact_dir(project_id)
        artifacts = []
        
        if not os.path.exists(artifact_dir):
            return {"projectId": project_id, "artifacts": [], "total": 0, "groups": []}

        for filename in os.listdir(artifact_dir):
            if filename.endswith(".json"):
                 # In a real DB app, we'd query SQL. Here we read JSON files.
                 # Implementation omitted for brevity in this mock, 
                 # but we'd return metadata.
                 pass
        
        # Mock response for now to unblock frontend
        return {
            "projectId": project_id,
            "artifacts": [],
            "total": 0,
            "groups": []
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/artifacts/upload")
async def upload_artifact(
    projectId: str = Form(...),
    file: UploadFile = File(...)
):
    try:
        artifact_dir = get_artifact_dir(projectId)
        
        # Generate ID
        artifact_id = str(uuid.uuid4())
        
        # Determine type based on extension
        content_type = file.content_type
        ext = os.path.splitext(file.filename)[1].lower()
        
        if content_type.startswith("image/"):
            artifact_type = "image"
        elif ext in [".txt", ".md", ".py", ".ts", ".js", ".json"]:
            artifact_type = "text_document"
        else:
            artifact_type = "generic_file"

        # Save file
        # structured as: <id>_<filename>
        safe_filename = f"{artifact_id}_{file.filename}"
        file_path = os.path.join(artifact_dir, safe_filename)
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # Create metadata JSON
        metadata = {
            "id": artifact_id,
            "type": artifact_type,
            "projectId": projectId,
            "createdBy": "user",
            "createdAt": datetime.now().isoformat(),
            "updatedAt": datetime.now().isoformat(),
            "status": "active",
            "schemaVersion": "1.0",
            "data": {
                "url": f"file://{file_path}", # Local file path for electron/local web
                "filename": file.filename,
                "mimeType": content_type,
                "size": os.path.getsize(file_path)
            }
        }
        
        # Add specific data
        if artifact_type == "text_document":
             with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                 metadata["data"]["content"] = f.read()
                 metadata["data"]["language"] = ext.replace(".", "")

        metadata_path = os.path.join(artifact_dir, f"{artifact_id}.json")
        import json
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)

        return metadata

    except Exception as e:
        print(f"Upload error: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@router.get("/artifact/{artifact_id}")
async def get_artifact(artifact_id: str):
    # Mock implementation - would need project_id context or a global search
    # For now, we stub it.
    raise HTTPException(status_code=404, detail="Artifact not found")

@router.post("/artifact")
async def create_artifact(artifact: ArtifactCreate):
    # Mock implementation
    return {
        "id": str(uuid.uuid4()),
        **artifact.dict(),
        "createdAt": datetime.now().isoformat(),
        "updatedAt": datetime.now().isoformat(),
        "status": "active"
    }

@router.put("/artifact/{artifact_id}")
async def update_artifact(artifact_id: str, update: ArtifactUpdate):
    # Mock implementation
    return {
        "id": artifact_id,
        "data": update.data,
        "updatedAt": datetime.now().isoformat()
    }

@router.delete("/artifact/{artifact_id}")
async def delete_artifact(artifact_id: str):
    return {"success": True}
