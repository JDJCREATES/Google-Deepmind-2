from fastapi import FastAPI, Depends, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from app.auth import router as auth_router, get_current_user
from app.services.preview_manager import preview_manager
from app.services.usage_tracker import usage_tracker
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

app = FastAPI(title="ShipS* Backend")

# CORS
origins = [
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:5175",
    "http://localhost:5176",
    # Allow electron preview if needed, or specific origins
    "*" 
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
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
    return {
        "is_running": preview_manager.is_running,
        "logs": preview_manager.logs[-50:],
        "url": preview_manager.current_url
    }

# ---------------------------------------------------------
# Agent/Prompt Router (Placeholder for now)
# ---------------------------------------------------------
agent_router = APIRouter(prefix="/agent", tags=["agent"])

class PromptRequest(BaseModel):
    prompt: str

from fastapi.responses import StreamingResponse
import json
from app.agents.agent_graph import stream_pipeline

@agent_router.post("/run")
async def run_agent(request: Request, body: PromptRequest):
    # Manual Auth Check
    auth_header = request.headers.get("Authorization")
    user_id = None
    # (Auth logic skipped for brevity as per existing implementation)
            
    # Check limit
    client_ip = request.client.host
    if not usage_tracker.can_run_prompt(client_ip, user_id):
        raise HTTPException(status_code=402, detail="Free limit exceeded. Please login to continue.")

    usage_tracker.record_usage(client_ip, user_id)

    async def response_generator():
        try:
            async for event in stream_pipeline(body.prompt):
                # Format event for frontend
                # event is a dict like {'node_name': {state_updates}}
                for node_name, state_update in event.items():
                    messages = state_update.get("messages", [])
                    # Extract the latest message content
                    latest_msg = messages[-1] if messages else None
                    if latest_msg:
                        content = latest_msg.content if hasattr(latest_msg, "content") else str(latest_msg)
                        chunk = {
                            "type": "message",
                            "node": node_name,
                            "content": content
                        }
                        yield json.dumps(chunk) + "\n"
                        
                    # Also yield phase updates if preset
                    if "phase" in state_update:
                        yield json.dumps({
                            "type": "phase",
                            "phase": state_update["phase"]
                        }) + "\n"
        except Exception as e:
            yield json.dumps({"type": "error", "content": str(e)}) + "\n"

    return StreamingResponse(response_generator(), media_type="application/x-ndjson")

# Include Routers
app.include_router(auth_router, tags=["Authentication"])
app.include_router(preview_router)
app.include_router(agent_router)

# Import and include Artifacts Router
from app.api.artifacts import router as artifacts_router
app.include_router(artifacts_router)

@app.get("/")
def read_root():
    return {"message": "ShipS* Backend is Running"}
