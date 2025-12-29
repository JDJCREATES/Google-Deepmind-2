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
import os

app = FastAPI(title="ShipS* Backend")

# CORS
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
        "url": preview_manager.current_url,
        "project_path": preview_manager.current_project_path
    }

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
            
            async for event in stream_pipeline(body.prompt, project_path=effective_project_path):
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
                            
                        # FILTER: Skip internal control messages
                        if isinstance(content, str):
                            skip_patterns = ['EXECUTE NOW', 'Start creating files NOW', 'Use the write_file_to_disk', 'ACTION REQUIRED', 'MANDATORY FIRST STEP', 'SCAFFOLDING CHECK']
                            if any(pattern in content for pattern in skip_patterns):
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
                            }
                            phase = phase_map.get(node_name.lower())
                            if phase:
                                yield json.dumps({
                                    "type": "phase",
                                    "phase": phase
                                }) + "\n"
                        
                        # ============================================================
                        # CRITICAL: Convert content to displayable string
                        # ============================================================
                        display_content = content
                        
                        # Handle list content (e.g., [{'type': 'text', 'text': '...'}])
                        if isinstance(content, list):
                            text_parts = []
                            for item in content:
                                if isinstance(item, dict) and 'text' in item:
                                    text_parts.append(item['text'])
                                elif isinstance(item, str):
                                    text_parts.append(item)
                            display_content = "".join(text_parts) if text_parts else None
                        
                        # Handle dict content (shouldn't display as object)
                        elif isinstance(content, dict):
                            # Try to get text from common fields
                            display_content = content.get('text') or content.get('content') or None
                        
                        # Skip if nothing to display
                        if not display_content:
                            continue
                        
                        # Stream the content to frontend
                        logger.debug(f"[STREAM] Chunk from {node_name}: {str(display_content)[:50]}...")
                        chunk = {
                            "type": "message",
                            "node": node_name,
                            "content": str(display_content)  # Ensure string
                        }
                        yield json.dumps(chunk) + "\n"
                    
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
            yield json.dumps({"type": "complete", "content": "Pipeline completed successfully"}) + "\n"
            
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
