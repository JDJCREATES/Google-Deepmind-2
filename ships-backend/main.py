from dotenv import load_dotenv
load_dotenv()  # Load .env file before anything else

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
from app.graphs.agent_graph import stream_pipeline

@agent_router.post("/run")
async def run_agent(request: Request, body: PromptRequest):
    import logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger = logging.getLogger("ships.agent")
    
    # Log the FULL raw input
    logger.info("=" * 60)
    logger.info("[API] 📥 RECEIVED USER INPUT:")
    logger.info(f"[API] Raw prompt (full): {body.prompt}")
    logger.info(f"[API] Prompt length: {len(body.prompt)} chars")
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

    usage_tracker.record_usage(client_ip, user_id)
    logger.info(f"[API] Usage recorded for IP: {client_ip}")

    async def response_generator():
        try:
            logger.info("[STREAM] 🚀 Starting agent pipeline stream...")
            logger.info(f"[STREAM] Passing to stream_pipeline: '{body.prompt[:100]}...'")
            current_node = None
            
            async for event in stream_pipeline(body.prompt):
                # stream_mode="messages" yields tuples of (message_chunk, metadata)
                # The message_chunk has a .content attribute with the actual text
                
                try:
                    # Handle tuple format from stream_mode="messages"
                    if isinstance(event, tuple) and len(event) >= 2:
                        message_chunk, metadata = event[0], event[1]
                        
                        # FILTER: Skip HumanMessage types (these are internal prompts)
                        msg_type = type(message_chunk).__name__
                        if msg_type == 'HumanMessage' or msg_type == 'HumanMessageChunk':
                            logger.debug(f"[STREAM] Skipping HumanMessage: {str(message_chunk)[:50]}...")
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
                            content = str(message_chunk)
                        
                        # FILTER: Skip internal control messages
                        if isinstance(content, str):
                            skip_patterns = ['EXECUTE NOW', 'Start creating files NOW', 'Use the write_file_to_disk']
                            if any(pattern in content for pattern in skip_patterns):
                                logger.debug(f"[STREAM] Skipping internal message: {content[:50]}...")
                                continue
                        
                        # Get node name from metadata if available
                        node_name = metadata.get('langgraph_node', 'agent') if isinstance(metadata, dict) else 'agent'
                        
                        if node_name != current_node:
                            current_node = node_name
                            logger.info(f"[STREAM] Entered node: {node_name}")
                        
                        if content:
                            logger.debug(f"[STREAM] Chunk from {node_name}: {str(content)[:50]}...")
                            chunk = {
                                "type": "message",
                                "node": node_name,
                                "content": content
                            }
                            yield json.dumps(chunk) + "\n"
                    
                    # Handle dict format (fallback for other stream modes)
                    elif isinstance(event, dict):
                        for node_name, state_update in event.items():
                            if node_name != current_node:
                                current_node = node_name
                                logger.info(f"[STREAM] Node update: {node_name}")
                            
                            messages = state_update.get("messages", [])
                            latest_msg = messages[-1] if messages else None
                            if latest_msg:
                                content = latest_msg.content if hasattr(latest_msg, "content") else str(latest_msg)
                                logger.debug(f"[STREAM] Message from {node_name}: {content[:50]}...")
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
                    else:
                        # Unknown format - log and try to extract something useful
                        logger.warning(f"[STREAM] Unknown event format: {type(event)}")
                        content = str(event) if event else ""
                        if content and content != "None":
                            yield json.dumps({"type": "message", "node": "agent", "content": content}) + "\n"
                            
                except Exception as parse_error:
                    logger.error(f"[STREAM] Error parsing event: {parse_error}", exc_info=True)
                    continue
                    
            logger.info("[STREAM] Pipeline completed successfully")
            
        except Exception as e:
            logger.error(f"[STREAM] Pipeline error: {e}", exc_info=True)
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
