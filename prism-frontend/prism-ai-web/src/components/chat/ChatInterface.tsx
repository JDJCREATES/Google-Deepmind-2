import { useState, useRef, useEffect } from 'react';
import { PiShippingContainerFill } from "react-icons/pi";
import { RiShip2Fill } from 'react-icons/ri';
import { VscLayoutSidebarRightOff } from 'react-icons/vsc';

import ChatMessage, { type Message } from './ChatMessage';
import { agentService, type AgentChunk } from '../../services/agentService';
import { ToolProgress, PhaseIndicator } from '../streaming';
import { ActivityIndicator } from '../streaming/ActivityIndicator';
import { PlanReviewActions } from '../streaming/PlanReviewActions';
import { ThinkingSection } from '../streaming/ThinkingSection';
import { useStreamingStore } from '../../store/streamingStore';
import { useFileSystem } from '../../store/fileSystem';

import '../../App.css'; // Keep existing styles for now

// Thinking section state
interface ThinkingSectionData {
  id: string;
  title: string;
  node: string;
  content: string;
  isLive: boolean;
}

interface ChatInterfaceProps {
  electronProjectPath: string | null;
}

export function ChatInterface({ electronProjectPath }: ChatInterfaceProps) {
  // Local state for chat messages and input (UI state)
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      content: 'Ready to Ship?',
      sender: 'ai',
      timestamp: new Date(),
    },
  ]);
  const [inputValue, setInputValue] = useState('');
  const [isAgentRunning, setIsAgentRunning] = useState(false);
  
  // Thinking sections state
  const [thinkingSections, setThinkingSections] = useState<ThinkingSectionData[]>([]);
  const currentThinkingSectionRef = useRef<string | null>(null);
  
  // Preview state
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewStatus, setPreviewStatus] = useState<'idle' | 'starting' | 'running' | 'error'>('idle');
  
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const { refreshFileTree, openFile } = useFileSystem();
  
  // Streaming state from store
  const { 
    toolEvents, addToolEvent, clearToolEvents,
    agentPhase, setPhase,
    currentActivity, activityType, setActivity,
    appendTerminalOutput, setShowTerminal,
    awaitingConfirmation, planSummary, setAwaitingConfirmation
  } = useStreamingStore();

  const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001';

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Sync with existing preview on mount
  useEffect(() => {
    const syncExistingPreview = async () => {
      try {
        const response = await fetch(`${API_URL}/preview/status`);
        const status = await response.json();
        
        if (status.is_running) {
          console.log('[Chat] Found existing preview server:', status);
          
          if (status.url) {
            setPreviewUrl(status.url);
            setPreviewStatus('running');
            appendTerminalOutput(`\n\x1b[32m[System] ✓ Dev server running at: ${status.url}\x1b[0m\n`);
          } else {
            setPreviewStatus('starting');
          }
        }
      } catch (e) {
        console.warn('[Chat] Could not fetch preview status:', e);
      }
    };
    syncExistingPreview();
  }, []);

  // Cleanup on page unload - stop dev server to prevent orphan processes
  useEffect(() => {
    const handleBeforeUnload = () => {
      // Use sendBeacon for reliable delivery during unload
      const url = `${API_URL}/preview/stop`;
      navigator.sendBeacon(url);
    };
    
    window.addEventListener('beforeunload', handleBeforeUnload);
    
    return () => {
      window.removeEventListener('beforeunload', handleBeforeUnload);
    };
  }, [API_URL]);

  const handleSendMessage = async () => {
    if (!inputValue.trim()) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      content: inputValue,
      sender: 'user',
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInputValue('');
    setIsAgentRunning(true);
    
    // Reset streaming state
    setPhase('planning');
    clearToolEvents();
    setActivity('Initializing...', 'thinking');
    setAwaitingConfirmation(false);
    
    // Clear previous thinking sections for new conversation
    setThinkingSections([]);
    currentThinkingSectionRef.current = null;

    // Placeholder AI message
    const aiMessageId = (Date.now() + 1).toString();
    const initialAiMessage: Message = {
      id: aiMessageId,
      content: '', 
      sender: 'ai',
      timestamp: new Date(),
    };
    
    setMessages(prev => [...prev, initialAiMessage]);

    let filesCreated = false;

    await agentService.runAgent(
      userMessage.content,
      null, 
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
          
          setMessages(prev => prev.map(msg => {
            if (msg.id === aiMessageId) {
              return { 
                ...msg, 
                content: planText
              };
            }
            return msg;
          }));
          
          // Show Accept/Reject buttons
          setAwaitingConfirmation(true, `Ready to implement: ${summary}`);
          setActivity('Plan ready - awaiting your approval', 'thinking');
        }
        
        // Plan Review (HITL) - fallback for direct plan_review events
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
        
        // Thinking Section Start - new section with title
        else if (chunk.type === 'thinking_start') {
          const sectionId = `${chunk.node}-${Date.now()}`;
          
          // Mark previous sections as not live
          setThinkingSections(prev => prev.map(s => ({ ...s, isLive: false })));
          
          // Create new section
          setThinkingSections(prev => [...prev, {
            id: sectionId,
            title: chunk.title || `Processing (${chunk.node})`,
            node: chunk.node || 'agent',
            content: '',
            isLive: true
          }]);
          
          currentThinkingSectionRef.current = sectionId;
        }
        
        // Thinking Content - append to current section
        else if (chunk.type === 'thinking' && chunk.content) {
          const sectionId = currentThinkingSectionRef.current;
          
          if (sectionId) {
            setThinkingSections(prev => prev.map(s => {
              if (s.id === sectionId) {
                return {
                  ...s,
                  content: s.content + (s.content ? '\n' : '') + chunk.content
                };
              }
              return s;
            }));
          }
        }
        
        // AI Message
        else if (chunk.type === 'message' && chunk.content) {
          const content = chunk.content;
          const skipPatterns = [
            'ACTION REQUIRED', 'MANDATORY FIRST STEP', 'SCAFFOLDING CHECK',
            'list_directory', '{"type": "tool_result"',
          ];
          
          if (skipPatterns.some(p => content.includes(p))) {
            return; 
          }
          
          setMessages(prev => prev.map(msg => {
            if (msg.id === aiMessageId) {
              return { 
                ...msg, 
                content: msg.content + (msg.content && !msg.content.endsWith('\n') ? ' ' : '') + content
              };
            }
            return msg;
          }));
        }
        
        // Agent Reasoning (from planner, coder, orchestrator, etc.)
        else if (chunk.type === 'reasoning' && chunk.content) {
          const content = chunk.content;
          const node = chunk.node || 'agent';
          
          // Skip the same internal patterns
          const skipPatterns = [
            'ACTION REQUIRED', 'MANDATORY FIRST STEP', 'SCAFFOLDING CHECK',
            'list_directory', '{"type": "tool_result"',
          ];
          
          if (skipPatterns.some(p => content.includes(p))) {
            return; 
          }
          
          // Append reasoning with node indicator
          setMessages(prev => prev.map(msg => {
            if (msg.id === aiMessageId) {
              const nodeLabel = node.charAt(0).toUpperCase() + node.slice(1);
              const formattedContent = `\n**[${nodeLabel}]** ${content}`;
              return { 
                ...msg, 
                content: msg.content + formattedContent
              };
            }
            return msg;
          }));
        }
        
        // Complete
        else if (chunk.type === 'complete') {
          setPhase('done');
          
          if (chunk.preview_url) {
            setPreviewUrl(chunk.preview_url);
            console.log('[Chat] Preview ready at:', chunk.preview_url);
            
            if (window.electron?.openPreview) {
              window.electron.openPreview(chunk.preview_url);
            } else {
              window.open(chunk.preview_url, '_blank');
              appendTerminalOutput(`\n\n[System] Preview ready at: ${chunk.preview_url}\n(Popup might be blocked by browser)`);
            }
          }
        }
        
        // Error
        else if (chunk.type === 'error') {
          setPhase('error');
          setMessages(prev => prev.map(msg => {
            if (msg.id === aiMessageId) {
              return { ...msg, content: msg.content + `\n🛑 Error: ${chunk.content}` };
            }
            return msg;
          }));
        }
      },
      (error: any) => {
        setIsAgentRunning(false);
        setPhase('error');
        setMessages(prev => prev.map(msg => {
          if (msg.id === aiMessageId) {
            return { ...msg, content: msg.content + `\n⚠️ Network Error: ${error.message}` };
          }
          return msg;
        }));
      }
    );
    
    setIsAgentRunning(false);
    setPhase('done');
    setActivity('');
    // Don't clear awaitingConfirmation here - user may still need to respond
    
    if (filesCreated) {
      refreshFileTree();
    }
  };

  // HITL Handlers
  const handleAcceptPlan = () => {
    setAwaitingConfirmation(false);
    // Send confirmation to backend
    setInputValue('Proceed with the plan');
    setTimeout(() => {
      handleSendMessage();
    }, 100);
  };

  const handleRejectPlan = () => {
    setAwaitingConfirmation(false);
    setMessages(prev => [...prev, {
      id: Date.now().toString(),
      content: 'Plan rejected. Please describe what you\'d like to change:',
      sender: 'ai',
      timestamp: new Date(),
    }]);
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  return (
    <div className="chat-panel">
      <div className="chat-header">
        <div className="chat-header-left">
           <RiShip2Fill size={20} style={{ marginRight: 8, color: 'var(--primary-color, #ff5e57)' }} />
           <span className="chat-title">ShipS*</span>
        </div>
        <div className="chat-header-center" style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          {previewStatus === 'running' && previewUrl && (
            <span style={{ color: '#4ec9b0', fontSize: '12px' }}>● Server Running (Check Desktop App)</span>
          )}
          {previewStatus === 'starting' && (
            <span style={{ color: '#dcdcaa', fontSize: '12px' }}>○ Starting...</span>
          )}
          {previewStatus === 'error' && (
            <span style={{ color: '#f44747', fontSize: '12px' }}>✖ Error</span>
          )}
          
          <button 
            className="preview-btn"
            onClick={async () => {
              if (isAgentRunning) return;

              if (!electronProjectPath) {
                 appendTerminalOutput('\n\x1b[31m[Error] No project folder selected.\x1b[0m\n');
                 return;
              }

              try {
                setPreviewStatus('starting');
                setShowTerminal(true);
                appendTerminalOutput('\n\n\x1b[36m[System] ▶ Starting development server...\x1b[0m\n');
                
                const response = await fetch(`${API_URL}/preview/start`, {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({ path: electronProjectPath })
                });
                
                const result = await response.json();
                
                if (result.status === 'error') {
                   setPreviewStatus('error');
                   appendTerminalOutput(`\n\x1b[31m[Error] ${result.message}\x1b[0m\n`);
                   return;
                }

                // Poll for URL
                let attempts = 0;
                const maxAttempts = 30; 
                let lastLogCount = 0;  // Track how many logs we've seen
                
                const pollInterval = setInterval(async () => {
                  attempts++;
                  try {
                      const statusRes = await fetch(`${API_URL}/preview/status`);
                      const status = await statusRes.json();
                      
                      // Display ALL new logs since last poll
                      if (status.logs && status.logs.length > lastLogCount) {
                         const newLogs = status.logs.slice(lastLogCount);
                         for (const logLine of newLogs) {
                             if (logLine) {
                                 appendTerminalOutput(`\n${logLine}`);
                             }
                         }
                         lastLogCount = status.logs.length;
                      }
                      
                      if (status.url) {
                          clearInterval(pollInterval);
                          setPreviewUrl(status.url);
                          setPreviewStatus('running');
                          appendTerminalOutput(`\n\x1b[32m[System] ✓ Server ready at: ${status.url}\x1b[0m\n`);
                          
                          if (window.electron?.openPreview) {
                              window.electron.openPreview(status.url);
                          } else {
                              const shipsUrl = `ships://preview?url=${encodeURIComponent(status.url)}&path=${encodeURIComponent(electronProjectPath || '')}`;
                              
                              const protocolFrame = document.createElement('iframe');
                              protocolFrame.style.display = 'none';
                              protocolFrame.src = shipsUrl;
                              document.body.appendChild(protocolFrame);
                              
                              setTimeout(() => {
                                  document.body.removeChild(protocolFrame);
                                  appendTerminalOutput(`\n\x1b[36m[System] Preview launched. If Electron doesn't open, visit: ${status.url}\x1b[0m\n`);
                              }, 1000);
                          }
                      } else if (attempts >= maxAttempts) {
                          clearInterval(pollInterval);
                          setPreviewStatus('error');
                          appendTerminalOutput('\n\x1b[33m[System] ⚠ Server timed out. Check terminal for errors.\x1b[0m\n');
                      }
                  } catch (err) {
                      console.error("Poll error", err);
                  }
                }, 500);

              } catch (e) {
                 setPreviewStatus('error');
                 appendTerminalOutput(`\n\x1b[31m[Error] Preview launch failed: ${e}\x1b[0m\n`);
              }
            }}
            style={{
              background: previewStatus === 'starting' ? '#555' : (isAgentRunning ? '#555' : 'var(--primary-color, #ff5e57)'),
              color: 'white',
              border: 'none',
              padding: '6px 16px',
              borderRadius: '4px',
              cursor: (isAgentRunning || previewStatus === 'starting') ? 'not-allowed' : 'pointer',
              fontSize: '13px',
              fontWeight: 500,
              opacity: (isAgentRunning || previewStatus === 'starting') ? 0.7 : 1
            }}
            disabled={isAgentRunning || previewStatus === 'starting'}
          >
            {previewStatus === 'starting' ? 'Starting...' : (isAgentRunning ? 'Busy...' : 'Preview')}
          </button>
        </div>
        <div className="chat-header-right">
          <VscLayoutSidebarRightOff size={16} />
        </div>
      </div>

      <div className="chat-messages">
        {isAgentRunning && agentPhase !== 'idle' && (
          <PhaseIndicator phase={agentPhase} />
        )}

        {/* Thinking Sections - collapsible agent thought process */}
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

        {messages.map((message) => (
          <ChatMessage key={message.id} message={message} />
        ))}

        <div className="activity-section">
           <ActivityIndicator 
              activity={currentActivity} 
              type={activityType} 
           />
        </div>
        
        {awaitingConfirmation && (
          <PlanReviewActions
            planSummary={planSummary}
            onAccept={handleAcceptPlan}
            onReject={handleRejectPlan}
            isLoading={isAgentRunning}
          />
        )}
        
        <div ref={messagesEndRef} />
      </div>

      {toolEvents.length > 0 && (
        <ToolProgress 
          events={toolEvents} 
          isCollapsed={agentPhase === 'done' || agentPhase === 'idle'}
          onFileClick={(filePath: string) => {
            if (filePath) {
              const fullPath = electronProjectPath 
                ? `${electronProjectPath}/${filePath}`.replace(/\\/g, '/')
                : filePath;
              openFile(fullPath);
              console.log('[Chat] Opening file in editor:', fullPath);
            }
          }}
        />
      )}

      <div className="chat-input-container">
        <textarea
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyPress={handleKeyPress}
          placeholder="Time to ShipS*?"
          className="chat-input"
          rows={1}
          style={{ minHeight: '40px' }}
        />
          <button
            className="send-button"
            onClick={handleSendMessage}
            disabled={!inputValue.trim() || isAgentRunning}
          >
            <PiShippingContainerFill size={24} />
          </button>
      </div>
    </div>
  );
}
