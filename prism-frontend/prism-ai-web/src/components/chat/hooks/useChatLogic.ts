import { useState, useRef, useEffect, useCallback } from 'react';
import { useAgentRuns } from '../../agent-dashboard/hooks/useAgentRuns';
import { useStreamingStore } from '../../../store/streamingStore';
import { useFileSystem } from '../../../store/fileSystem';
import { agentService, type AgentChunk } from '../../../services/agentService';
import type { ChatMessage as ChatMessageType, ThinkingSectionData, StreamBlock } from '../../agent-dashboard/types';

interface UseChatLogicProps {
  electronProjectPath: string | null;
}

export function useChatLogic({ electronProjectPath }: UseChatLogicProps) {
  // Refs (must be first to maintain hook order)
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const currentThinkingSectionRef = useRef<string | null>(null);
  const prevRunIdRef = useRef<string | null>(null);

  // Global Agent Runs Store
  const { 
    activeRunId, 
    runs, 
    createRun,
    setActiveRun,
    addRunMessage,
    updateRunMessage,
    appendRunMessageContent,
    addRunThinkingSection,
    updateRunThinking,
    setRunThinkingSectionLive,
    upsertRunMessageBlock,
    appendRunMessageBlockContent,
    setLoading,
    updateRun
  } = useAgentRuns();

  // Local UI state for input
  const [inputValue, setInputValue] = useState('');
  
  // Streaming state
  const { 
    toolEvents, addToolEvent, clearToolEvents,
    agentPhase, setPhase,
    currentActivity, activityType, setActivity,
    appendTerminalOutput, setShowTerminal,
    setAwaitingConfirmation,
    resetStreaming  // Add reset function
  } = useStreamingStore();

  const { refreshFileTree, openFile } = useFileSystem();
  
  // Computed state from active run
  const activeRun = runs.find(r => r.id === activeRunId);
  const messages = activeRun?.messages || [];
  
  // We determine if agent is running based on the run status
  const isAgentRunning = activeRun?.status === 'running' || activeRun?.status === 'planning' || activeRun?.status === 'pending';

  // Reset streaming state when switching runs
  useEffect(() => {
    if (activeRunId && activeRunId !== prevRunIdRef.current) {
      // Only reset when actually switching to a DIFFERENT run
      // Don't clear on initial mount or same run
      if (prevRunIdRef.current !== null) {
        resetStreaming();
        console.log('[useChatLogic] Reset streaming state for new run:', activeRunId);
      }
      prevRunIdRef.current = activeRunId;
    }
  }, [activeRunId, resetStreaming]);

  // Auto-scroll when new content arrives
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages.length, toolEvents.length, activeRun?.agentMessage]);

  const handleSendMessage = async () => {
    if (!inputValue.trim()) return;

    let targetRunId = activeRunId;
    const prompt = inputValue.trim();
    
    // Clear input immediately
    setInputValue('');

    // 1. Create new run if none active
    if (!targetRunId) {
      setLoading(true);
      // Optimistic creation title
      const newRun = await createRun({ 
        prompt,
        title: prompt.slice(0, 50) 
      });
      if (newRun) {
        targetRunId = newRun.id;
        setActiveRun(newRun.id); // IMPORTANT: Set active run so messages display
      }
      setLoading(false);
    }

    if (!targetRunId) return;

    // 2. Add User Message (Optimistic - backend also streams it but as a block)
    const userMessage: ChatMessageType = {
      id: Date.now().toString(),
      content: prompt,
      sender: 'user',
      timestamp: new Date(),
    };
    addRunMessage(targetRunId, userMessage);

    // 3. Reset UI State
    setPhase('planning');
    clearToolEvents();
    setActivity('Initializing...', 'thinking');
    setAwaitingConfirmation(false);
    
    // 4. Create Placeholder AI Message
    const aiMessageId = (Date.now() + 1).toString();
    const initialAiMessage: ChatMessageType = {
      id: aiMessageId,
      content: '', 
      sender: 'ai',
      timestamp: new Date(),
      blocks: [], // Initialize for StreamBlock protocol
    };
    addRunMessage(targetRunId, initialAiMessage);

    // 5. Start Agent Service
    currentThinkingSectionRef.current = null;
    let filesCreated = false;

    // We capture targetRunId in closure to ensure updates go to the correct run
    await agentService.runAgent(
      prompt,
      electronProjectPath, 
      (chunk: AgentChunk) => {
        // ============================================================
        // UNIFIED STREAMING: StreamBlock Protocol Only
        // ============================================================

        // Block Start - Create new block in message
        if (chunk.type === 'block_start' && chunk.block_type) {
             const block: StreamBlock = {
                 id: chunk.id!,
                 type: chunk.block_type,
                 title: chunk.title,
                 content: '',
                 isComplete: false,
                 metadata: { ...chunk, timestamp: Date.now() }
             };
             if (targetRunId) {
               upsertRunMessageBlock(targetRunId, aiMessageId, block);
             }
             
             // Update Activity Indicator
             if (chunk.block_type === 'thinking') setActivity('Thinking...', 'thinking');
             else if (chunk.block_type === 'code') setActivity('Writing code...', 'writing');
             else if (chunk.block_type === 'command') setActivity(chunk.title || 'Running command...', 'command');
             else if (chunk.block_type === 'plan') setActivity('Creating plan...', 'thinking');
             
             // Update activity indicator based on block type
             if (chunk.block_type === 'thinking') setActivity(chunk.title || 'Thinking...', 'thinking');
             else if (chunk.block_type === 'code') setActivity('Writing code...', 'writing');
             else if (chunk.block_type === 'command') setActivity(chunk.title || 'Running command...', 'command');
             else if (chunk.block_type === 'plan') setActivity('Creating plan...', 'thinking');
        } 
        
        // Block Delta - Append content to existing block
        else if (chunk.type === 'block_delta' && chunk.id) {
             if (targetRunId) {
               appendRunMessageBlockContent(targetRunId, aiMessageId, chunk.id, chunk.content || '');
             }
        } 
        
        // Block End - Mark block as complete
        else if (chunk.type === 'block_end' && chunk.id) {
             console.log('[useChatLogic] ✓ Block complete:', chunk.id);
             if (targetRunId) {
               upsertRunMessageBlock(targetRunId, aiMessageId, { 
                  id: chunk.id, 
                  type: 'text',
                  content: '',
                  isComplete: true,
                  final_content: chunk.final_content
               } as StreamBlock);
             }
        }
        
        // Phase updates (for activity indicator only, not duplicate rendering)
        else if (chunk.type === 'phase' && chunk.phase) {
          setPhase(chunk.phase);
          if (chunk.phase === 'planning') setActivity('Planning approach...', 'thinking');
          else if (chunk.phase === 'coding') setActivity('Writing code...', 'writing');
          else if (chunk.phase === 'validating') setActivity('Verifying changes...', 'thinking');
          else if (chunk.phase === 'fixing') setActivity('Fixing issues...', 'thinking');
        }
        
        // ============================================================
        // ESSENTIAL UI UPDATES (Non-Message Components)
        // ============================================================
        
        // Tool tracking - for ToolProgress component at bottom
        else if (chunk.type === 'tool_start') {
          const toolName = chunk.tool || 'unknown';
          let activityText = `Running ${toolName}...`;
          let type: any = 'working';
          
          if (toolName === 'write_file_to_disk') {
             activityText = `Writing ${chunk.file || 'file'}...`;
             type = 'writing';
          } else if (toolName === 'run_terminal_command') {
             activityText = `Running command...`;
             type = 'command';
          } else if (toolName === 'read_file_from_disk') {
             activityText = `Reading ${chunk.file || 'file'}...`;
             type = 'reading';
          }
          
          setActivity(activityText, type);
          const toolEvent = {
            id: `${Date.now()}-${chunk.tool}`,
            type: 'tool_start',
            tool: chunk.tool || 'unknown',
            file: chunk.file,
            timestamp: Date.now()
          };
          console.log('[useChatLogic] tool_start event captured:', toolEvent);
          addToolEvent(toolEvent);
        }
        
        // Tool result tracking - SHOW IN CHAT as blocks
        else if (chunk.type === 'tool_result') {
          setActivity('Thinking...', 'thinking');
          
          // Add to ToolProgress sidebar
          const toolEvent = {
            id: `${Date.now()}-${chunk.tool}-result`,
            type: 'tool_result',
            tool: chunk.tool || 'unknown',
            file: chunk.file,
            success: chunk.success,
            timestamp: Date.now()
          };
          console.log('[useChatLogic] tool_result event captured:', toolEvent);
          addToolEvent(toolEvent);
          
          // ALSO add as a StreamBlock in the message for visibility
          const toolName = chunk.tool || 'unknown';
          let action = '';
          if (toolName.includes('write')) action = 'Created';
          else if (toolName.includes('edit')) action = 'Edited';
          else if (toolName.includes('delete')) action = 'Deleted';
          else action = 'Modified';
          
          const fileBlock: StreamBlock = {
            id: `${Date.now()}-file-op`,
            type: 'tool_use',
            title: `${action}: ${chunk.file}`,
            content: `✓ ${action} \`${chunk.file}\``,
            isComplete: true,
            metadata: chunk
          };
          if (targetRunId) {
            upsertRunMessageBlock(targetRunId, aiMessageId, fileBlock);
          }
        }
        
        // Activity indicator updates from agents
        else if (chunk.type === 'activity') {
          const agent = chunk.agent || 'agent';
          const message = chunk.message || 'Working...';
          console.log('[useChatLogic] activity event:', agent, message);
          setActivity(message, 'working');
          
          if (chunk.tool === 'write_file_to_disk' || chunk.tool === 'edit_file_content') {
            filesCreated = true;
          }
          
          if (chunk.tool === 'run_terminal_command') {
            setShowTerminal(true);
          }
        }
        
        // Files created tracking
        else if (chunk.type === 'files_created') {
          filesCreated = true;
        }
        
        // Terminal output (separate terminal component)
        else if (chunk.type === 'terminal_output') {
          const output = chunk.output || '';
          const stderr = chunk.stderr || '';
          const command = chunk.command || '';
          const fullOutput = `\n\x1b[36m$ ${command}\x1b[0m\n${output}${stderr ? '\n\x1b[31mSTDERR:\x1b[0m ' + stderr : ''}`;
          appendTerminalOutput(fullOutput);
          setShowTerminal(true);
        }
         
         // Run Complete - Capture screenshot and create preview
         else if (chunk.type === 'complete') {
           setPhase('done');
           console.log('[ChatInterface] Run complete, triggering screenshot capture...');
           
           if (targetRunId && (window as any).electron) {
             // Extract project path if available (handles subfolder scaffolding)
             const finalProjectPath = (chunk as any).artifacts?.project_path;
             console.log('[DEBUG] Opening preview for path:', finalProjectPath);
             
             // Update the run with the detected project path so future manual clicks work
             if (finalProjectPath) {
               updateRun(targetRunId, { projectPath: finalProjectPath });
             }

             // Create or focus preview window, then capture screenshot
             (window as any).electron.createRunPreview(targetRunId, finalProjectPath)
               .then((previewResult: any) => {
                 console.log('[ChatInterface] Preview result:', previewResult);
                 
                 // Wait briefly for page to load, then capture screenshot
                 setTimeout(() => {
                   (window as any).electron.captureRunScreenshot(
                     targetRunId,
                     'complete',
                     'Agent run completed successfully'
                   )
                     .then((screenshotResult: any) => {
                       console.log('[ChatInterface] Screenshot captured:', screenshotResult);
                     })
                     .catch((e: any) => {
                       console.warn('[ChatInterface] Screenshot capture failed:', e);
                     });
                 }, 2000); // Wait 2s for preview to load
               })
               .catch((e: any) => {
                 console.warn('[ChatInterface] Preview creation failed:', e);
               });
           }
         }
      },
      (error: any) => {
         setPhase('error');
         if (targetRunId) {
             const errorMsg = `\n⚠️ Network Error: ${error.message}`;
             appendRunMessageContent(targetRunId, aiMessageId, errorMsg);
         }
      }
    );
     
    if (filesCreated) {
      refreshFileTree();
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  return {
    inputValue,
    setInputValue,
    handleSendMessage,
    handleKeyPress,
    messages,
    toolEvents,
    activeRun,
    activeRunId,
    isAgentRunning,
    agentPhase,
    currentActivity,
    activityType,
    messagesEndRef,
    openFile
  };
}
