import ChatMessage from './ChatMessage';
import { ToolProgress, PhaseIndicator } from '../streaming';
import { ActivityIndicator } from '../streaming/ActivityIndicator';
import { PlanReviewActions } from '../streaming/PlanReviewActions';
import { useChatLogic } from './hooks/useChatLogic';
import { useStreamingStore } from '../../store/streamingStore';
import { useAgentRuns } from '../agent-dashboard/hooks/useAgentRuns';
import { ChatHeader } from './ChatHeader';
import { ChatInput } from './ChatInput';


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
    toolEvents,
    activeRun,
    activeRunId,
    isAgentRunning,
    agentPhase,
    currentActivity,
    activityType,
    messagesEndRef,
    openFile,
    handleMessageEdit,
    handleMessageRewind
  } = useChatLogic({ electronProjectPath });
  
  // HITL state - reactive subscription
  const { awaitingConfirmation, planSummary, setAwaitingConfirmation } = useStreamingStore();
  
  return (
    <aside className="chat-panel" role="complementary" aria-label="AI Chat Assistant">
      <ChatHeader 
        activeRun={activeRun}
        activeRunId={activeRunId}
        electronProjectPath={electronProjectPath}
        onOpenPreview={async () => {
          if (activeRunId) {
            console.log('[ChatInterface] Opening preview for run:', activeRunId);
            const { openPreview } = useAgentRuns.getState();
            await openPreview(activeRunId);
          } else {
             // Fallback for no run
             fetch(`${API_URL}/preview/request-focus`, { method: 'POST' }).catch(console.error);
          }
        }}
      />

      <main className="chat-messages">
         {/* Phase Indicator */}
         {isAgentRunning && agentPhase !== 'idle' && agentPhase !== 'done' && (
           <PhaseIndicator phase={agentPhase} />
         )}
         
         {/* Messages - All content (including thinking) rendered as StreamBlocks */}
         {messages.length === 0 && !activeRunId && (
            <div className="message-centered">
               <div className="welcome-content">Ready to Ship[s]?</div>
            </div>
         )}
         
         {messages.map((message) => (
           <ChatMessage 
             key={message.id} 
             message={message} 
             onEdit={handleMessageEdit}
             onRewind={handleMessageRewind}
           />
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
          {console.log('[ChatInterface] Rendering ToolProgress with', toolEvents.length, 'events:', toolEvents)}
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

      {/* HITL Plan Review Actions - Shows when awaiting user confirmation */}
      {awaitingConfirmation && (
        <PlanReviewActions
          planSummary={planSummary}
          onAccept={() => {
            setAwaitingConfirmation(false);
            setInputValue('proceed');
            handleSendMessage();
          }}
          onReject={() => {
            setAwaitingConfirmation(false);
            setInputValue('');
          }}
        />
      )}

      <ChatInput 
        inputValue={inputValue}
        setInputValue={setInputValue}
        handleSendMessage={handleSendMessage}
        handleKeyPress={handleKeyPress}
        isAgentRunning={isAgentRunning}
        activeRunStatus={activeRun?.status}
      />
    </aside>
  );
}
