import React from 'react';
import { ProgressCircular } from 'react-onsenui';
import { PiShippingContainerBold } from 'react-icons/pi';

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
  
  const isDisabled = !inputValue.trim();

  return (
    <footer className="chat-input-container">
      <form 
        onSubmit={(e) => { e.preventDefault(); handleSendMessage(); }} 
        className="chat-form"
      >
        <textarea
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={handleKeyPress}
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
          <PiShippingContainerBold className="send-icon" />
        </button>
      </form>
    </footer>
  );
};
