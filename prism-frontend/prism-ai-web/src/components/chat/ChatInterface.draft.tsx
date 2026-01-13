
import { useState, useRef, useEffect } from 'react';
import { PiShippingContainerFill } from "react-icons/pi";
import { RiShip2Fill } from 'react-icons/ri';
import { VscLayoutSidebarRightOff } from 'react-icons/vsc';
import { ProgressCircular } from 'react-onsenui';

import ChatMessage from './ChatMessage';
import { agentService, type AgentChunk } from '../../services/agentService';
import { ToolProgress, PhaseIndicator } from '../streaming';
import { ActivityIndicator } from '../streaming/ActivityIndicator';
import { PlanReviewActions } from '../streaming/PlanReviewActions';
import { ThinkingSection } from '../streaming/ThinkingSection';
import { useStreamingStore } from '../../store/streamingStore';
import { useFileSystem } from '../../store/fileSystem';
import { useAgentRuns } from '../agent-dashboard/hooks/useAgentRuns';
import type { ChatMessage as ChatMessageType, ThinkingSectionData } from '../agent-dashboard/types';

import './ChatInterface.css';

interface ChatInterfaceProps {
  electronProjectPath: string | null;
}

export function ChatInterface({ electronProjectPath }: ChatInterfaceProps) {
  // Global Agent Runs Store
  const { 
    activeRunId, 
    runs, 
    createRun,
    addRunMessage,
    updateRunMessage,
    addRunThinkingSection,
    updateRunThinking,
    setRunThinkingSectionLive,
    setLoading,
    activeRunId: currentRunId // Alias for clarity
  } = useAgentRuns();

  // Local UI state for input
  const [inputValue, setInputValue] = useState('');
  
  // Computed state from active run
  const activeRun = runs.find(r => r.id === activeRunId);
  const messages = activeRun?.messages || [];
  const thinkingSections = activeRun?.thinkingSections || [];
  
  // We determine if agent is running based on the run status, or a local override for the transient "starting" state
  const isAgentRunning = activeRun?.status === 'running' || activeRun?.status === 'planning' || activeRun?.status === 'pending';
  
  // Refs
  const currentThinkingSectionRef = useRef<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const { refreshFileTree, openFile } = useFileSystem();
  
  // Streaming state (still used for tool events visualizer - potentially move to store later)
  const { 
    toolEvents, addToolEvent, clearToolEvents,
    agentPhase, setPhase,
    currentActivity, activityType, setActivity,
    appendTerminalOutput, setShowTerminal,
    awaitingConfirmation, planSummary, setAwaitingConfirmation
  } = useStreamingStore();

  const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001';

  // Auto-scroll when new content arrives
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages.length, thinkingSections.length, toolEvents.length, activeRun?.agentMessage]);

  const handleSendMessage = async () => {
    if (!inputValue.trim()) return;

    let targetRunId = activeRunId;
    const prompt = inputValue.trim();
    
    // Clear input immediately
    setInputValue('');

    // 1. Create new run if none active
    if (!targetRunId) {
      setLoading(true);
      // Optimistic creation
      const newRun = await createRun({ 
        prompt,
        title: prompt.slice(0, 50) 
      });
      if (newRun) {
        targetRunId = newRun.id;
      }
      setLoading(false);
    }

    if (!targetRunId) return;

    // 2. Add User Message
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
    };
    addRunMessage(targetRunId, initialAiMessage);

    // 5. Start Agent Service
    // We capture targetRunId in closure to ensure updates go to the correct run
    currentThinkingSectionRef.current = null;
    let filesCreated = false;

    await agentService.runAgent(
      prompt,
      electronProjectPath, 
      (chunk: AgentChunk) => {
        // Phase
        if (chunk.type === 'phase' && chunk.phase) {
          setPhase(chunk.phase);
          if (chunk.phase === 'planning') setActivity('Planning approach...');
          else if (chunk.phase === 'coding') setActivity('Writing code...');
          else if (chunk.phase === 'validating') setActivity('Verifying changes...');
          else if (chunk.phase === 'fixing') setActivity('Fixing issues...');
        }
        
        // Tool Start
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

          addToolEvent({
            id: `${Date.now()}-${chunk.tool}`,
            type: 'tool_start',
            tool: chunk.tool || 'unknown',
            file: chunk.file,
            timestamp: Date.now()
          });
        }
        
        // Tool Result
        else if (chunk.type === 'tool_result') {
          setActivity('Thinking...', 'thinking');

          addToolEvent({
            id: `${Date.now()}-${chunk.tool}-result`,
            type: 'tool_result',
            tool: chunk.tool || 'unknown',
            file: chunk.file,
            success: chunk.success,
            timestamp: Date.now()
          });
          
          if (chunk.tool === 'write_file_to_disk' || chunk.tool === 'edit_file_content') {
            filesCreated = true;
          }
          
          if (chunk.tool === 'run_terminal_command') {
            setShowTerminal(true);
          }
        }
        
        // Files Created
        else if (chunk.type === 'files_created') {
          filesCreated = true;
        }
        
        // Plan Created
        else if (chunk.type === 'plan_created') {
          const summary = (chunk as any).summary || 'Plan created';
          const taskCount = (chunk as any).task_count || 0;
          const folderCount = (chunk as any).folders || 0;
          
          const planText = `📋 **${summary}**\n• ${taskCount} tasks defined\n• ${folderCount} folders to create`;
          
          // Replace content of AI message with plan
          if (targetRunId) {
              updateRunMessage(targetRunId, aiMessageId, { content: planText });
          }
          
          // Show Accept/Reject buttons
          setAwaitingConfirmation(true, `Ready to implement: ${summary}`);
          setActivity('Plan ready - awaiting your approval', 'thinking');
        }
        
        // Plan Review (HITL)
        else if (chunk.type === 'plan_review') {
          const summary = chunk.content || 'Ready to proceed with implementation.';
          setAwaitingConfirmation(true, summary);
          setActivity('Awaiting your approval...', 'thinking');
        }
        
        // Terminal Output
        else if (chunk.type === 'terminal_output') {
          const output = chunk.output || '';
          const stderr = chunk.stderr || '';
          const command = chunk.command || '';
          const fullOutput = `\n\x1b[36m$ ${command}\x1b[0m\n${output}${stderr ? '\n\x1b[31mSTDERR:\x1b[0m ' + stderr : ''}`;
          appendTerminalOutput(fullOutput);
          setShowTerminal(true);
        }
        
        // Thinking Section Start
        else if (chunk.type === 'thinking_start') {
          const sectionId = `${chunk.node}-${Date.now()}`;
          
          if (targetRunId) {
              // 1. Mark all existing sections as not live
              // (This is tricky with the set action, we might need a better bulk update or just iterate)
              // For now we assume the ThinkingSection component handles 'live' visual via index or ID
              // But we can update the previous one if we track strict ID.
              if (currentThinkingSectionRef.current) {
                  setRunThinkingSectionLive(targetRunId, currentThinkingSectionRef.current, false);
              }

              // 2. Add new section
              const newSection: ThinkingSectionData = {
                id: sectionId,
                title: chunk.title || `Processing (${chunk.node})`,
                node: chunk.node || 'agent',
                content: '',
                isLive: true
              };
              addRunThinkingSection(targetRunId, newSection);
              currentThinkingSectionRef.current = sectionId;
          }
        }
        
        // Thinking Content
        else if (chunk.type === 'thinking' && chunk.content) {
          const sectionId = currentThinkingSectionRef.current;
          if (targetRunId && sectionId) {
             updateRunThinking(targetRunId, sectionId, chunk.content);
          }
        }
        
        // AI Message
        else if (chunk.type === 'message' && chunk.content) {
          const content = chunk.content;
          
          const skipPatterns = [
            'ACTION REQUIRED', 'MANDATORY FIRST STEP', 'SCAFFOLDING CHECK',
          ];
          
          if (!skipPatterns.some(p => content.includes(p))) {
            if (targetRunId) {
                // Determine if we need to prepend space
                // This is hard to do without reading previous content.
                // We'll rely on the reducer or just append. 
                // Since updateRunMessage merges props, we actually need to READ the current message to append?
                // The reducer in `useAgentRuns` uses `...msg` but `messages` is an array.
                // We don't have atomic 'append' in the store yet.
                // Hack: We should probably just append to the store. 
                // Or better: The store action `updateRunMessage` should probably accept a callback or we read previous state.
                
                // Let's improve the store usage. 
                // Actually, `activeRun` in this scope is stale!
                // We need to use functional updates in the store. 
                // My `updateRunMessage` implementation takes `updates: Partial<ChatMessage>`.
                // It replaces. It does NOT append.
                
                // CRITICAL ISSUE: I need `appendRunMessageContent` action.
                // See next step.
            }
          }
        }
        // ... (rest of handling)
      },
      (error: any) => {
         // Error handling
         if (targetRunId) {
             const errorMsg = `\n⚠️ Network Error: ${error.message}`;
             // We need append logic here too
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
  
  // Render
  return (
    <aside className="chat-panel" role="complementary" aria-label="AI Chat Assistant">
      {/* ... Header ... */}
      <header className="chat-header">
         <div className="chat-header-left">
           <RiShip2Fill size={20} style={{ marginRight: 8, color: 'var(--primary-color, #ff5e57)' }} />
           <span className="chat-title">ShipS*</span>
           {activeRun && <span className="chat-subtitle"> / {activeRun.branch.split('/').pop()}</span>}
         </div>
         {/* ... (Existing buttons) ... */}
      </header>

      <main className="chat-messages">
         {/* Phase Indicator */}
         {isAgentRunning && agentPhase !== 'idle' && agentPhase !== 'done' && (
           <PhaseIndicator phase={agentPhase} />
         )}

         {/* Thinking Sections */}
         {thinkingSections.length > 0 && (
           <div className="thinking-sections-container">
             {thinkingSections.map((section) => (
               <ThinkingSection
                 key={section.id}
                 title={section.title}
                 node={section.node}
                 content={section.content}
                 isLive={section.isLive}
                 defaultExpanded={section.isLive}
               />
             ))}
           </div>
         )}
         
         {/* Messages */}
         {messages.map((message) => (
             // Convert types.ts ChatMessage to local ChatMessage component props if needed
             // (They are identical interfaces so it's fine)
           <ChatMessage key={message.id} message={message} />
         ))}

         {/* Activity & Thinking */}
         <div className="activity-section">
            <ActivityIndicator activity={currentActivity} type={activityType} />
         </div>
         
         {/* Bottom Spacer */}
         <div ref={messagesEndRef} />
      </main>

      {/* Input Area */}
      <footer className="chat-input-container">
        <form onSubmit={(e) => { e.preventDefault(); handleSendMessage(); }} className="chat-form">
           <textarea
             value={inputValue}
             onChange={(e) => setInputValue(e.target.value)}
             onKeyPress={handleKeyPress}
             placeholder={activeRunId ? "Message agent..." : "Start a new run..."}
             className="chat-input"
             rows={1}
           />
           <button type="submit" className="send-button" disabled={!inputValue.trim() || (isAgentRunning && activeRun?.status !== 'pending')}>
              {isAgentRunning ? <ProgressCircular indeterminate /> : <PiShippingContainerFill size={24} />}
           </button>
        </form>
      </footer>
    </aside>
  );
}
