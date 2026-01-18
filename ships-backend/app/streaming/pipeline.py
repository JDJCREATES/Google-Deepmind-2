from typing import Optional, Dict, Any, AsyncGenerator
import logging
from uuid import UUID
from langchain_core.messages import HumanMessage

from app.graphs.agent_graph import create_agent_graph, get_checkpointer
from app.streaming.stream_events import StreamBlockManager, BlockType
from app.database import get_session_factory
from sqlalchemy import select
from app.models import User

logger = logging.getLogger("ships.streaming")

async def stream_pipeline(
    user_request: str,
    thread_id: str = "default",
    project_path: Optional[str] = None,
    settings: Optional[dict] = None,
    artifact_context: Optional[dict] = None,
    user_id: Optional[str] = None
) -> AsyncGenerator[str, None]:
    """
    Stream the full agent pipeline with token-by-token streaming.
    
    Refactored from agent_graph.py to use astream_events (v1).
    """
    
    logger.info("=" * 60)
    logger.info(f"[PIPELINE] 📨 Received request: '{user_request[:50]}...'")
    logger.info(f"[PIPELINE] Project path: {project_path or 'Not set'}")
    logger.info("=" * 60)
    
    # 1. Step Tracking (Optional)
    run_id = None
    if user_id and project_path:
        try:
            from app.services.step_tracking import start_run
            run_id = await start_run(
                user_id=UUID(user_id) if isinstance(user_id, str) else user_id,
                project_path=project_path,
                user_request=user_request[:500]
            )
            if run_id:
                logger.info(f"[PIPELINE] 📊 Step tracking started: run_id={run_id}")
        except Exception as e:
    
            if run_id:
                logger.info(f"[PIPELINE] 📊 Step tracking started: run_id={run_id}")
        except Exception as e:
            logger.debug(f"[PIPELINE] Step tracking unavailable: {e}")

    # 1.5. GIT BRANCH ISOLATION (Production Hardening)
    if project_path:
        try:
            from app.services.git_checkpointer import get_checkpointer as get_git_service
            
            # Use run_id for branch name (or timestamp if missing)
            import time
            branch_id = str(run_id) if run_id else f"dev-{int(time.time())}"
            # Shorten UUID for readability
            short_id = branch_id[:8] if "-" in branch_id else branch_id
            branch_name = f"ships/run/{short_id}"
            
            git_service = get_git_service(project_path, str(run_id))
            if git_service.create_and_checkout_branch(branch_name):
                logger.info(f"[PIPELINE] 🌿 Isolated run in git branch: {branch_name}")
            else:
                logger.warning(f"[PIPELINE] ⚠️ Failed to isolate branch {branch_name} - using current branch")
                
        except Exception as git_err:
            logger.error(f"[PIPELINE] ❌ Git branch error: {git_err}")

    # 2. Setup Graph
    checkpointer = get_checkpointer()
    graph = create_agent_graph(checkpointer)
    
    human_msg = HumanMessage(content=user_request)
    
    initial_state = {
        "messages": [human_msg],
        "phase": "planning",
        "artifacts": {
            "project_path": project_path,
            "settings": settings or {},
            "artifact_context": artifact_context,
            "run_id": str(run_id) if run_id else None,
            "user_id": user_id,
        },
        # Initialize other required state fields with defaults
        "current_task_index": 0,
        "validation_passed": False,
        "fix_attempts": 0,
        "max_fix_attempts": 3,
        "result": None,
        "tool_results": {},
        "plan": {},
        "completed_files": [],
        "active_file": None,
        "project_structure": [],
        "error_log": [],
        "loop_detection": {},
        "implementation_complete": False,
        "agent_status": {},
        "current_step": 0,
        "fix_request": None,
        "stream_events": []
    }
    
    config = {
        "configurable": {"thread_id": thread_id},
        "run_name": f"ShipS* Pipeline: {user_request[:50]}...",
        "metadata": {
            "project_path": project_path,
            "run_id": str(run_id) if run_id else None,
        },
        "recursion_limit": 100,
    }
    
    block_mgr = StreamBlockManager()
    
    try:
        logger.info(f"[STREAM] 🚀 Starting graph.astream_events() with thread_id={thread_id}")
        
        # Use astream_events v1 for token streaming
        async for event in graph.astream_events(initial_state, config=config, version="v1"):
            event_type = event["event"]
            event_name = event.get("name", "unknown")
            event_data = event.get("data", {})
            
            # 1. TOKEN STREAMING
            if event_type == "on_chat_model_stream":
                chunk = event_data.get("chunk")
                if chunk and hasattr(chunk, "content"):
                    content = chunk.content
                    if content:
                        # Parsing Logic for Complex Chunks (Lists/Dicts)
                        if isinstance(content, list):
                            # Handle [{"type": "text", "text": "..."}] format
                            extracted = []
                            for item in content:
                                if isinstance(item, dict):
                                    if item.get("type") == "text":
                                        extracted.append(item.get("text", ""))
                                elif isinstance(item, str):
                                    extracted.append(item)
                            content = "".join(extracted)
                        elif not isinstance(content, str):
                            content = str(content)
                            
                        # Default to Thinking if no block active
                        if not block_mgr.active_block or block_mgr.active_block.type not in [
                            BlockType.THINKING, BlockType.TEXT, BlockType.CODE, BlockType.PLAN
                        ]:
                             yield block_mgr.start_block(BlockType.THINKING, "Thinking...") + "\n"
                        
                        delta = block_mgr.append_delta(content)
                        if delta: yield delta + "\n"

            # 2. TOOL EXECUTION
            elif event_type == "on_tool_start":
                # Skip internal tools if needed, but showing all is usually transparent
                yield block_mgr.start_block(BlockType.COMMAND, f"Running {event_name}...") + "\n"
                
            elif event_type == "on_tool_end":
                output = event_data.get("output", "")
                output_str = str(output)[:500] + "..." if len(str(output)) > 500 else str(output)
                end_block = block_mgr.end_current_block()
                if end_block:
                     yield end_block + "\n"
                if output_str:
                    yield block_mgr.create_block(BlockType.CMD_OUTPUT, f"{event_name} Output", output_str) + "\n"

            # 3. NODE TRANSITIONS
            elif event_type == "on_chain_start":
                if event_name == "planner":
                     yield block_mgr.start_block(BlockType.PLAN, "Developing Implementation Plan") + "\n"
                     yield block_mgr.start_block(BlockType.THINKING, "Analyzing request...") + "\n"
                elif event_name == "coder":
                     yield block_mgr.start_block(BlockType.CODE, "Writing Code...") + "\n"
                elif event_name == "validator":
                     yield block_mgr.start_block(BlockType.TEXT, "Validating Changes...") + "\n"
                elif event_name == "fixer":
                     yield block_mgr.start_block(BlockType.PREFLIGHT, "Applying Fixes...") + "\n"

            elif event_type == "on_chain_end":
                # CAPTURE CUSTOM NODE EVENTS (e.g. file_written, run:complete)
                # These are returned in the "stream_events" key of the node output
                output = event_data.get("output", {})
                if isinstance(output, dict):
                    # 1. SYNC PREVIEW MANAGER (Frontend Deep Linking)
                    # This controller layer logic ensures the API knows about path changes (e.g. scaffolding)
                    # without coupling the Graph logic to the Service layer.
                    new_path = output.get("artifacts", {}).get("project_path")
                    if new_path:
                        from app.services.preview_manager import preview_manager
                        if preview_manager.current_project_path != new_path:
                            preview_manager.current_project_path = new_path
                            logger.info(f"[PIPELINE] 🔄 Synced preview_manager path to: {new_path}")

                    # 2. CAPTURE CUSTOM EVENTS
                    if "stream_events" in output:
                        import json
                        for custom_event in output["stream_events"]:
                            # Yield as raw JSON event line
                            yield json.dumps(custom_event) + "\n"
                            logger.debug(f"[STREAM] 📤 Emitted custom event: {custom_event.get('type')}")

            
            # Log debug info
            if event_type not in ["on_chat_model_stream", "on_chat_model_start"]:
                 logger.debug(f"[STREAM] Event: {event_type} - {event_name}")

        final = block_mgr.end_current_block()
        if final: yield final + "\n"

    except Exception as e:
        logger.error(f"[STREAM] Error: {e}", exc_info=True)
        err = block_mgr.start_block(BlockType.ERROR, "Stream Error")
        if err: yield err + "\n"
        yield block_mgr.append_delta(str(e)) + "\n"
        yield block_mgr.end_current_block() + "\n"
        raise e # Re-raise for upper handlers

    finally:
        # Step Tracking Finalization
        # (Simplified for now - can be expanded)
        pass
