from typing import Optional, Dict, Any, AsyncGenerator
import logging
from uuid import UUID
from langchain_core.messages import HumanMessage

from app.graphs.agent_graph import create_agent_graph, get_checkpointer
from app.streaming.stream_events import StreamBlockManager, BlockType
from app.database import get_session_factory
from sqlalchemy import select
from app.models import User
from app.utils.debounced_logger import DebouncedLogger

logger = logging.getLogger("ships.streaming")
debounced_log = DebouncedLogger(logger, debounce_seconds=2.0)

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
    current_agent = None  # Track which agent is active
    json_buffer = ""  # Buffer for accumulating JSON tokens
    in_json_stream = False  # Are we currently streaming JSON?
    
    # Track which agents use structured output (no token streaming)
    suppress_streaming_for = set()
    
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
                        
                        # DETECT JSON STREAMING (from planner's structured output)
                        # Check if we're starting JSON or already in JSON
                        if not in_json_stream and content.strip().startswith('{'):
                            in_json_stream = True
                            json_buffer = content
                            # Start a thinking block for extracted reasoning
                            yield block_mgr.start_block(BlockType.THINKING, "Planning...") + "\n"
                            continue  # Don't stream raw JSON
                        elif in_json_stream:
                            json_buffer += content
                            
                            # Try to extract user-facing text fields as they complete
                            import re
                            
                            # Extract "reasoning": "..." field
                            reasoning_match = re.search(r'"reasoning"\s*:\s*"([^"]*(?:\\.[^"]*)*)"', json_buffer)
                            if reasoning_match and '"reasoning": ""' not in json_buffer:
                                reasoning_text = reasoning_match.group(1).replace('\\"', '"').replace('\\n', '\n')
                                delta = block_mgr.append_delta("**Reasoning:**\n" + reasoning_text + "\n\n")
                                if delta:
                                    yield delta + "\n"
                                json_buffer = re.sub(r'"reasoning"\s*:\s*"[^"]*(?:\\.[^"]*)*"', '"reasoning": ""', json_buffer, count=1)
                            
                            # Extract "summary": "..." field  
                            summary_match = re.search(r'"summary"\s*:\s*"([^"]*(?:\\.[^"]*)*)"', json_buffer)
                            if summary_match and '"summary": ""' not in json_buffer:
                                summary_text = summary_match.group(1).replace('\\"', '"').replace('\\n', '\n')
                                delta = block_mgr.append_delta("**Summary:**\n" + summary_text + "\n\n")
                                if delta:
                                    yield delta + "\n"
                                json_buffer = re.sub(r'"summary"\s*:\s*"[^"]*(?:\\.[^"]*)*"', '"summary": ""', json_buffer, count=1)
                            
                            # Extract "description": "..." field
                            description_match = re.search(r'"description"\s*:\s*"([^"]*(?:\\.[^"]*)*)"', json_buffer)
                            if description_match and '"description": ""' not in json_buffer:
                                desc_text = description_match.group(1).replace('\\"', '"').replace('\\n', '\n')
                                delta = block_mgr.append_delta("**Description:**\n" + desc_text + "\n\n")
                                if delta:
                                    yield delta + "\n"
                                json_buffer = re.sub(r'"description"\s*:\s*"[^"]*(?:\\.[^"]*)*"', '"description": ""', json_buffer, count=1)
                            
                            # Extract "assumptions": [...] array
                            assumptions_match = re.search(r'"assumptions"\s*:\s*\[(.*?)\]', json_buffer, re.DOTALL)
                            if assumptions_match and '"assumptions": []' not in json_buffer:
                                assumptions_raw = assumptions_match.group(1)
                                # Extract quoted strings from array
                                assumption_items = re.findall(r'"([^"]*(?:\\.[^"]*)*)"', assumptions_raw)
                                if assumption_items:
                                    delta = block_mgr.append_delta("**Assumptions:**\n")
                                    if delta: yield delta + "\n"
                                    for item in assumption_items:
                                        clean_item = item.replace('\\"', '"').replace('\\n', ' ')
                                        delta = block_mgr.append_delta(f"• {clean_item}\n")
                                        if delta: yield delta + "\n"
                                    delta = block_mgr.append_delta("\n")
                                    if delta: yield delta + "\n"
                                json_buffer = re.sub(r'"assumptions"\s*:\s*\[.*?\]', '"assumptions": []', json_buffer, count=1, flags=re.DOTALL)
                            
                            # Extract "decision_notes": [...] array
                            decisions_match = re.search(r'"decision_notes"\s*:\s*\[(.*?)\]', json_buffer, re.DOTALL)
                            if decisions_match and '"decision_notes": []' not in json_buffer:
                                decisions_raw = decisions_match.group(1)
                                decision_items = re.findall(r'"([^"]*(?:\\.[^"]*)*)"', decisions_raw)
                                if decision_items:
                                    delta = block_mgr.append_delta("**Key Decisions:**\n")
                                    if delta: yield delta + "\n"
                                    for item in decision_items:
                                        clean_item = item.replace('\\"', '"').replace('\\n', ' ')
                                        delta = block_mgr.append_delta(f"• {clean_item}\n")
                                        if delta: yield delta + "\n"
                                    delta = block_mgr.append_delta("\n")
                                    if delta: yield delta + "\n"
                                json_buffer = re.sub(r'"decision_notes"\s*:\s*\[.*?\]', '"decision_notes": []', json_buffer, count=1, flags=re.DOTALL)
                            
                            # Extract "clarifying_questions": [...] array
                            questions_match = re.search(r'"clarifying_questions"\s*:\s*\[(.*?)\]', json_buffer, re.DOTALL)
                            if questions_match and '"clarifying_questions": []' not in json_buffer:
                                questions_raw = questions_match.group(1)
                                question_items = re.findall(r'"([^"]*(?:\\.[^"]*)*)"', questions_raw)
                                if question_items:
                                    delta = block_mgr.append_delta("**Questions:**\n")
                                    if delta: yield delta + "\n"
                                    for item in question_items:
                                        clean_item = item.replace('\\"', '"').replace('\\n', ' ')
                                        delta = block_mgr.append_delta(f"• {clean_item}\n")
                                        if delta: yield delta + "\n"
                                    delta = block_mgr.append_delta("\n")
                                    if delta: yield delta + "\n"
                                json_buffer = re.sub(r'"clarifying_questions"\s*:\s*\[.*?\]', '"clarifying_questions": []', json_buffer, count=1, flags=re.DOTALL)
                            
                            # Check if JSON is complete
                            if json_buffer.count('{') > 0 and json_buffer.count('{') == json_buffer.count('}'):
                                in_json_stream = False
                                json_buffer = ""
                                # Close the thinking block
                                end_block = block_mgr.end_current_block()
                                if end_block:
                                    yield end_block + "\n"
                            
                            continue  # Don't stream raw JSON tokens
                        
                        # Regular token streaming (non-JSON)
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
                
                tool_start_json = json.dumps({
                    "type": "tool_start",
                    "tool": event_name,
                    "file": file_path,
                    "timestamp": int(time.time() * 1000)
                })
                yield tool_start_json + "\n"
                
                # LOG COMPLETE EMITTED JSON
                logger.info(f"🔧 [PIPELINE] EMITTED tool_start NDJSON:")
                logger.info(f"   {tool_start_json}")
                
            elif event_type == "on_tool_end":
                import json
                output = event_data.get("output", "")
                
                # EXTRACT actual content from ToolMessage/AIMessage objects
                output_content = output
                if hasattr(output, 'content'):
                    output_content = output.content
                
                # Parse JSON tool responses for clean display
                formatted_output = None
                if isinstance(output_content, str):
                    try:
                        parsed = json.loads(output_content)
                        # Format common tool response patterns
                        if isinstance(parsed, dict):
                            if parsed.get("success"):
                                parts = [f"✓ Success"]
                                
                                # Use message if available (highest priority)
                                if "message" in parsed:
                                    parts.append(f": {parsed['message']}")
                                # Terminal output - show it formatted
                                elif "output" in parsed and parsed["output"]:
                                    parts.append(f"\n```\n{parsed['output'][:500]}\n```")
                                # Artifact loaded - show name only
                                elif "name" in parsed and event_name == "get_artifact":
                                    parts.append(f": Loaded {parsed['name']}")
                                # File tree - show summary only
                                elif "stats" in parsed and event_name == "get_file_tree":
                                    stats = parsed["stats"]
                                    parts.append(f": Found {stats.get('files', 0)} files, {stats.get('directories', 0)} directories")
                                # Write operations - already have message, skip
                                # For everything else, show success but NO raw data
                                
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
                    block_json = block_mgr.create_block(BlockType.CMD_OUTPUT, f"{event_name} result", formatted_output)
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
                
                tool_result_json = json.dumps({
                    "type": "tool_result",
                    "tool": event_name,
                    "file": file_path,
                    "success": success,
                    "timestamp": int(time.time() * 1000)
                })
                yield tool_result_json + "\n"
                
                # LOG COMPLETE EMITTED JSON
                logger.info(f"✅ [PIPELINE] EMITTED tool_result NDJSON:")
                logger.info(f"   {tool_result_json}")

            # 3. NODE TRANSITIONS
            elif event_type == "on_chain_start":
                current_agent = event_name  # Track which agent started
                if event_name == "planner":
                     # Planner will stream JSON - we'll extract reasoning in on_chat_model_stream
                     pass
                elif event_name == "coder":
                     yield block_mgr.start_block(BlockType.CODE, "Writing Code...") + "\n"
                elif event_name == "validator":
                     yield block_mgr.start_block(BlockType.TEXT, "Validating Changes...") + "\n"
                elif event_name == "fixer":
                     yield block_mgr.start_block(BlockType.PREFLIGHT, "Applying Fixes...") + "\n"

            elif event_type == "on_chain_end":
                
                # SKIP DISPLAY FOR INTERNAL OUTPUTS (routing metadata, not user-facing)
                if event_name in ["orchestrator", "IntentClassifier", "intent_classifier"]:
                    continue  # Internal processing - logged but not streamed to UI
                
                # PARSE STRUCTURED OUTPUTS from planner/coder
                import json
                output = event_data.get("output", {})
                
                # PLANNER STRUCTURED OUTPUT - Display nicely formatted plan
                if event_name == "planner" and isinstance(output, dict):
                    reasoning = output.get("reasoning", "")
                    summary = output.get("summary", "")
                    tasks = output.get("tasks", [])
                    decision_notes = output.get("decision_notes", [])
                    folders = output.get("folders", [])
                    dependencies = output.get("dependencies", {})
                    api_endpoints = output.get("api_endpoints", [])
                    risks = output.get("risks", [])
                    clarifying_questions = output.get("clarifying_questions", [])
                    
                    # Summary first
                    if summary:
                        yield block_mgr.create_block(BlockType.PLAN, "📋 Plan Summary", summary) + "\n"
                    
                    # Reasoning
                    if reasoning:
                        yield block_mgr.create_block(BlockType.THINKING, "💭 Design Thinking", reasoning) + "\n"
                    
                    # Key decisions
                    if decision_notes:
                        notes_text = "\n".join(f"• {note}" for note in decision_notes)
                        yield block_mgr.create_block(BlockType.TEXT, "🎯 Key Decisions", notes_text) + "\n"
                    
                    # Tasks breakdown
                    if tasks:
                        task_summary = f"**{len(tasks)} implementation tasks:**\n\n"
                        for i, task in enumerate(tasks, 1):
                            title = task.get("title", "Untitled")
                            desc = task.get("description", "")
                            complexity = task.get("complexity", "unknown")
                            priority = task.get("priority", "medium")
                            est_minutes = task.get("estimated_minutes", 0)
                            
                            task_summary += f"**{i}. {title}**\n"
                            if desc:
                                task_summary += f"   {desc[:100]}{'...' if len(desc) > 100 else ''}\n"
                            task_summary += f"   _Complexity: {complexity} | Priority: {priority}"
                            if est_minutes:
                                task_summary += f" | ~{est_minutes}min"
                            task_summary += "_\n\n"
                        
                        yield block_mgr.create_block(BlockType.PLAN, "✅ Tasks", task_summary) + "\n"
                    
                    # Files/folders to create
                    if folders:
                        files_list = []
                        for folder in folders[:10]:  # Show first 10
                            path = folder.get("path", "")
                            desc = folder.get("description", "")
                            if path:
                                files_list.append(f"• `{path}`" + (f" - {desc[:50]}" if desc else ""))
                        
                        files_text = "\n".join(files_list)
                        if len(folders) > 10:
                            files_text += f"\n\n... and {len(folders) - 10} more files"
                        
                        yield block_mgr.create_block(BlockType.TEXT, "📁 Files to Create", files_text) + "\n"
                    
                    # Dependencies
                    if dependencies:
                        runtime = dependencies.get("runtime", [])
                        dev = dependencies.get("dev", [])
                        
                        if runtime or dev:
                            dep_text = ""
                            if runtime:
                                dep_text += "**Runtime:**\n" + "\n".join(f"• {pkg.get('name', pkg)}" for pkg in runtime[:10])
                            if dev:
                                if runtime:
                                    dep_text += "\n\n"
                                dep_text += "**Dev:**\n" + "\n".join(f"• {pkg.get('name', pkg)}" for pkg in dev[:10])
                            
                            yield block_mgr.create_block(BlockType.TEXT, "📦 Dependencies", dep_text) + "\n"
                    
                    # Risks/warnings
                    if risks:
                        risk_text = "\n".join(f"⚠️ {risk.get('description', str(risk))}" for risk in risks[:5])
                        yield block_mgr.create_block(BlockType.TEXT, "⚠️ Risks", risk_text) + "\n"
                    
                    # Questions for user
                    if clarifying_questions:
                        q_text = "\n".join(f"{i}. {q}" for i, q in enumerate(clarifying_questions, 1))
                        yield block_mgr.create_block(BlockType.TEXT, "❓ Clarifying Questions", q_text) + "\n"
                
                # CAPTURE CUSTOM NODE EVENTS (e.g. file_written, run:complete)
                # These are returned in the "stream_events" key of the node output
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
