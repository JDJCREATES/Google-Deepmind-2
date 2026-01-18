import React from 'react';
import { ProgressCircular } from 'react-onsenui';

interface ChatInputProps {
  inputValue: string;
  setInputValue: (value: string) => void;
  handleSendMessage: () => void;
  handleKeyPress: (e: React.KeyboardEvent) => void;
  isAgentRunning: boolean;
  activeRunStatus?: string;
}

export const ChatInput: React.FC<ChatInputProps> = ({
  inputValue,
  setInputValue,
  handleSendMessage,
  handleKeyPress,
  isAgentRunning,
  activeRunStatus
}) => {
  
  const isDisabled = !inputValue.trim() || 
    (isAgentRunning && activeRunStatus !== 'pending' && activeRunStatus !== 'running' && activeRunStatus !== 'planning');

  return (
    <footer className="chat-input-container">
      <form 
        onSubmit={(e) => { e.preventDefault(); handleSendMessage(); }} 
        className="chat-form"
      >
        <textarea
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={handleKeyPress} // Changed to onKeyDown for better compatibility
          placeholder=""
          className="chat-input"
          rows={1}
        />
        <button 
          type="submit" 
          className="send-button" 
          disabled={isDisabled}
          aria-label="Send message"
        >
          {isAgentRunning ? (
            <ProgressCircular indeterminate /> 
          ) : (
            <svg 
              xmlns="http://www.w3.org/2000/svg"
              width="24" 
              height="24" 
              viewBox="0 0 24 24" 
              fill="none" 
              stroke="currentColor" 
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              {/* Shipping Container Icon - Classic Corrugated Design */}
              <rect x="4" y="6" width="16" height="12" rx="1" />
              <line x1="8" y1="6" x2="8" y2="18" />
              <line x1="12" y1="6" x2="12" y2="18" />
              <line x1="16" y1="6" x2="16" y2="18" />
              <rect x="10" y="10" width="4" height="4" fill="currentColor" opacity="0.3" />
            </svg>
          )}
        </button>
      </form>
    </footer>
  );
};
