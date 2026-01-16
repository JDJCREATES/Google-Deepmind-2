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
        >
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
  );
};
