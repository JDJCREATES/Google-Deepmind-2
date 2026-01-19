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
                        # DETECT STRUCTURED OUTPUT JSON - Don't stream it!
                        # Planner/Coder use .with_structured_output() which streams raw JSON
                        # We'll get the final structured data in on_chain_end instead
                        if isinstance(content, str):
                            stripped = content.strip()
                            # Skip if it looks like structured output JSON streaming
                            if stripped and (
                                stripped.startswith('{') or 
                                stripped.startswith('[') or
                                '"reasoning"' in stripped or
                                '"tasks"' in stripped or
                                '"complexity"' in stripped or
                                '"priority"' in stripped
                            ):
                                logger.debug(f"[STREAM] Suppressing structured output token: {content[:50]}...")
                                continue
                        
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
                
                # ALSO emit tool_start for ToolProgress sidebar
                import json
                tool_metadata = event_data.get("input", {})
                file_path = None
                if isinstance(tool_metadata, dict):
                    file_path = tool_metadata.get("file_path") or tool_metadata.get("filename")
                
                yield json.dumps({
                    "type": "tool_start",
                    "tool": event_name,
                    "file": file_path
                }) + "\n"
                
            elif event_type == "on_tool_end":
                import json
                output = event_data.get("output", "")
                
                logger.info(f"[PIPELINE DEBUG] on_tool_end for {event_name}")
                logger.info(f"[PIPELINE DEBUG] Raw output type: {type(output)}")
                logger.info(f"[PIPELINE DEBUG] Raw output: {str(output)[:200]}")
                
                # EXTRACT actual content from ToolMessage/AIMessage objects
                output_content = output
                if hasattr(output, 'content'):
                    output_content = output.content
                    logger.info(f"[PIPELINE DEBUG] Extracted .content: {str(output_content)[:200]}")
                
                # Parse JSON tool responses for clean display
                formatted_output = None
                if isinstance(output_content, str):
                    try:
                        parsed = json.loads(output_content)
                        logger.info(f"[PIPELINE DEBUG] Parsed JSON: {parsed}")
                        # Format common tool response patterns
                        if isinstance(parsed, dict):
                            if parsed.get("success"):
                                parts = [f"✓ Success"]
                                if "message" in parsed:
                                    parts.append(f": {parsed['message']}")
                                if "output" in parsed and parsed["output"]:
                                    parts.append(f"\n```\n{parsed['output'][:300]}\n```")
                                if "content" in parsed and parsed["content"]:
                                    parts.append(f"\n{parsed['content'][:200]}")
                                formatted_output = "".join(parts)
                            else:
                                formatted_output = f"✗ Failed: {parsed.get('error', 'Unknown error')}"
                    except:
                        # Not JSON, use as-is but truncate
                        formatted_output = str(output_content)[:300]
                else:
                    formatted_output = str(output_content)[:300]
                
                end_block = block_mgr.end_current_block()
                if end_block:
                     yield end_block + "\n"
                
                # Only show output block if there's meaningful content
                if formatted_output and formatted_output.strip():
                    logger.info(f"[PIPELINE DEBUG] Emitting cmd_output block with content: {formatted_output[:100]}")
                    block_json = block_mgr.create_block(BlockType.CMD_OUTPUT, f"{event_name} result", formatted_output)
                    logger.info(f"[PIPELINE DEBUG] Block JSON: {block_json[:200]}")
                    yield block_json + "\n"
                
                # ALSO emit tool_result for ToolProgress sidebar
                tool_metadata = event_data.get("input", {})
                file_path = None
                if isinstance(tool_metadata, dict):
                    file_path = tool_metadata.get("file_path") or tool_metadata.get("filename")
                
                # Determine success from output
                success = True
                if isinstance(output_content, str):
                    try:
                        parsed = json.loads(output_content)
                        if isinstance(parsed, dict):
                            success = parsed.get("success", True)
                    except:
                        pass
                elif isinstance(output, dict):
                    success = output.get("success", True)
                
                yield json.dumps({
                    "type": "tool_result",
                    "tool": event_name,
                    "file": file_path,
                    "success": success
                }) + "\n"

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

                    # 2. CAPTURE CUSTOM EVENTS (from agents)
                    if "stream_events" in output:
                        import json
                        for custom_event in output["stream_events"]:
                            event_type = custom_event.get("type", "")
                            agent = custom_event.get("agent", "")
                            content_text = custom_event.get("content", "")
                            metadata = custom_event.get("metadata", {})
                            
                            # ROUTE 1: File operations → ToolProgress component
                            if event_type in ["file_written", "file_deleted", "fix_applied"]:
                                action = metadata.get("action", "write")
                                tool_name = {
                                    "write": "write_file_to_disk",
                                    "batch_write": "write_files_batch",
                                    "edit": "apply_source_edits",
                                    "patch": "write_file_to_disk",
                                    "delete": "delete_file_from_disk"
                                }.get(action, "write_file_to_disk")
                                
                                yield json.dumps({
                                    "type": "tool_result",
                                    "tool": tool_name,
                                    "file": content_text,  # file path
                                    "success": True
                                }) + "\n"
                            
                            # ROUTE 2: Thinking/reasoning → StreamBlocks in chat
                            elif event_type in ["thinking", "reasoning"]:
                                # Build rich thinking block with task context
                                title = f"{agent.capitalize()}: {content_text[:50]}..." if len(content_text) > 50 else f"{agent.capitalize()}: Analyzing"
                                
                                # Add task details if available
                                thinking_content = [content_text]
                                
                                if metadata.get("task_title"):
                                    thinking_content.insert(0, f"**Task:** {metadata['task_title']}\n")
                                
                                if metadata.get("task_description"):
                                    desc = metadata['task_description'][:150]
                                    if len(metadata.get('task_description', '')) > 150:
                                        desc += "..."
                                    thinking_content.insert(1, f"**Description:** {desc}\n")
                                
                                if metadata.get("expected_files"):
                                    files = metadata['expected_files'][:3]
                                    thinking_content.append(f"\n\n**Expected Files:** {', '.join(files)}")
                                    if metadata.get('files_expected', 0) > 3:
                                        thinking_content.append(f" (+{metadata['files_expected'] - 3} more)")
                                
                                if metadata.get("acceptance_criteria"):
                                    thinking_content.append("\n\n**Success Criteria:**")
                                    for criterion in metadata['acceptance_criteria'][:3]:
                                        thinking_content.append(f"\n- {criterion}")
                                
                                full_content = "\n".join(str(c) for c in thinking_content)
                                yield block_mgr.create_block(BlockType.THINKING, title, full_content) + "\n"
                            
                            # ROUTE 3: Status updates → Activity indicator
                            elif event_type in ["agent_start", "agent_complete"]:
                                # Simple status message for activity indicator
                                yield json.dumps({
                                    "type": "activity",
                                    "agent": agent,
                                    "message": content_text,
                                    "metadata": metadata
                                }) + "\n"
                            
                            # ROUTE 4: Important events → StreamBlocks with nice formatting
                            elif event_type == "plan_created":
                                task_count = metadata.get("task_count", 0)
                                task_titles = metadata.get("task_titles", [])
                                files_to_create = metadata.get("files_to_create", [])
                                total_files = metadata.get("total_files", len(files_to_create))
                                
                                # Build rich summary
                                summary_parts = [f"Created implementation plan with {task_count} task{'s' if task_count != 1 else ''}"]
                                
                                if task_titles:
                                    summary_parts.append("\n\n**Tasks:**")
                                    for i, title in enumerate(task_titles, 1):
                                        summary_parts.append(f"\n{i}. {title}")
                                    if task_count > len(task_titles):
                                        summary_parts.append(f"\n... and {task_count - len(task_titles)} more")
                                
                                if files_to_create:
                                    summary_parts.append("\n\n**Files to Create:**")
                                    for f in files_to_create[:5]:  # Show first 5
                                        summary_parts.append(f"\n- {f}")
                                    if total_files > 5:
                                        summary_parts.append(f"\n- ... and {total_files - 5} more files")
                                
                                summary = "".join(summary_parts)
                                yield block_mgr.create_block(BlockType.PLAN, "✓ Plan Ready", summary) + "\n"
                            
                            elif event_type == "validation_complete":
                                passed = metadata.get("passed", False)
                                if passed:
                                    yield block_mgr.create_block(BlockType.PREFLIGHT, "✓ Validation Passed", content_text) + "\n"
                                else:
                                    violation_count = metadata.get("violation_count", 0)
                                    layer = metadata.get("layer", "unknown")
                                    
                                    # Build detailed error report
                                    error_parts = [content_text]
                                    error_parts.append(f"\n\n**Failed at:** {layer.upper()} layer")
                                    error_parts.append(f"\n**Violations:** {violation_count}")
                                    
                                    # Show violations if available
                                    if metadata.get("violations"):
                                        error_parts.append("\n\n**Issues Found:**")
                                        for v in metadata["violations"][:5]:  # First 5 violations
                                            if isinstance(v, dict):
                                                error_parts.append(f"\n- {v.get('message', v.get('type', 'Violation'))}")
                                            else:
                                                error_parts.append(f"\n- {v}")
                                    
                                    detail = "".join(error_parts)
                                    yield block_mgr.create_block(BlockType.ERROR, "✗ Validation Failed", detail) + "\n"
                            
                            # ROUTE 5: Errors
                            elif event_type == "error":
                                yield block_mgr.create_block(BlockType.ERROR, f"{agent.capitalize()}: Error", content_text) + "\n"
                            
                            # ROUTE 6: Unknown events → log but don't spam UI
                            else:
                                logger.debug(f"[PIPELINE] Unknown event type: {event_type} from {agent}")

            
            # Log debug info (commented out to reduce noise)
            # if event_type not in ["on_chat_model_stream", "on_chat_model_start"]:
            #      logger.debug(f"[STREAM] Event: {event_type} - {event_name}")

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
