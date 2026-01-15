
import { useState, useRef, useEffect } from 'react';
import { RiShip2Fill } from 'react-icons/ri';
import { VscLayoutSidebarRightOff, VscOpenPreview } from 'react-icons/vsc';
import { ProgressCircular } from 'react-onsenui';

import ChatMessage from './ChatMessage';
import { ToolProgress, PhaseIndicator } from '../streaming';
import { ActivityIndicator } from '../streaming/ActivityIndicator';
import { ThinkingSection } from '../streaming/ThinkingSection';
import { useChatLogic } from './hooks/useChatLogic';


import './ChatInterface.css';

interface ChatInterfaceProps {
  electronProjectPath: string | null;
}

export function ChatInterface({ electronProjectPath }: ChatInterfaceProps) {
  const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001';
  const {
    inputValue,
    setInputValue,
    handleSendMessage,
    handleKeyPress,
    messages,
    thinkingSections,
    toolEvents,
    activeRun,
    activeRunId,
    isAgentRunning,
    agentPhase,
    currentActivity,
    activityType,
    messagesEndRef,
    openFile
  } = useChatLogic({ electronProjectPath });
  
  return (
    <aside className="chat-panel" role="complementary" aria-label="AI Chat Assistant">
      {/* Header */}
      <header className="chat-header">
         <div className="chat-header-left">
           <RiShip2Fill size={20} style={{ marginRight: 8, color: 'var(--primary-color, #ff5e57)' }} />
           <span className="chat-title">ShipS*</span>
           {activeRun && <span className="chat-subtitle"> / {activeRun.branch.split('/').pop()?.replace('work/', '') || activeRun.title.slice(0, 15)}</span>}
         </div>
         <div className="chat-header-right">
            <button
              className="chat-header-btn"
              onClick={async () => {
                // Best method: Use run-based preview (creates window per run)
                if ((window as any).electron?.createRunPreview && activeRunId) {
                  try {
                    const result = await (window as any).electron.createRunPreview(activeRunId);
                    if (result.success) {
                      console.log('[Preview] Created/focused preview:', result.preview);
                      return;
                    }
                    console.warn('[Preview] createRunPreview failed:', result.error);
                  } catch (e) {
                    console.error('[Preview] IPC error:', e);
                  }
                }
                
                // Fallback: Try to get active previews and focus
                if ((window as any).electron?.getActiveRunPreviews) {
                  try {
                    const result = await (window as any).electron.getActiveRunPreviews();
                    if (result.success && result.previews?.length > 0) {
                      console.log('[Preview] Active previews:', result.previews);
                      // Previews exist - the window should be visible
                      return;
                    }
                  } catch (e) {
                    console.error('[Preview] getActiveRunPreviews error:', e);
                  }
                }
                
                // Last resort: HTTP API for focus request
                fetch(`${API_URL}/preview/request-focus`, { method: 'POST' }).catch(console.error);
              }}
              title={activeRunId ? 'Open Preview for Run' : 'Open Preview'}
              disabled={!activeRunId && !electronProjectPath}
            >
              <VscOpenPreview size={16} />
            </button>
            <VscLayoutSidebarRightOff size={16} aria-hidden="true" />
          </div>
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
                 // defaultExpanded={section.isLive} // Controlled by component usually
               />
             ))}
           </div>
         )}
         
         {/* Messages */}
         {messages.length === 0 && !activeRunId && (
            <div className="message-centered">
               <div className="welcome-content">Ready to Ship[s]?</div>
            </div>
         )}
         
         {messages.map((message) => (
           <ChatMessage key={message.id} message={message} />
         ))}

         {/* Activity & Thinking */}
         <div className="activity-section">
            <ActivityIndicator activity={currentActivity} type={activityType} />
         </div>
         
         {/* Bottom Spacer */}
         <div ref={messagesEndRef} />
      </main>

      {/* Tool Progress - Sticky above input, shows files created/commands run */}
      {toolEvents.length > 0 && (
        <div className="tool-progress-container">
          <ToolProgress 
            events={toolEvents} 
            onFileClick={(filePath) => {
              if (electronProjectPath) {
                openFile(filePath);
              }
            }}
          />
        </div>
      )}

      {/* Input Area */}
      <footer className="chat-input-container">
        <form onSubmit={(e) => { e.preventDefault(); handleSendMessage(); }} className="chat-form">
           <textarea
             value={inputValue}
             onChange={(e) => setInputValue(e.target.value)}
             onKeyPress={handleKeyPress}
             placeholder=""
             className="chat-input"
             rows={1}
           />
           <button type="submit" className="send-button" disabled={!inputValue.trim() || (isAgentRunning && activeRun?.status !== 'pending' && activeRun?.status !== 'running' && activeRun?.status !== 'planning')}>
              {isAgentRunning ? (
                <ProgressCircular indeterminate /> 
              ) : (
                <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
                  {/* Shipping Container Icon */}
                  <path d="M3 3h18v18H3V3zm2 2v14h14V5H5zm3 2h2v10H8V7zm4 0h2v10h-2V7zm4 0h2v10h-2V7z" opacity="0.9"/>
                </svg>
              )}
           </button>
        </form>
      </footer>
    </aside>
  );
}
