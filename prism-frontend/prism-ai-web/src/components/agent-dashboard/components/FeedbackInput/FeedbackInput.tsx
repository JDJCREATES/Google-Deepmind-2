/**
 * Feedback Input Component
 * 
 * Textarea for sending feedback to the agent for a specific run.
 */

import React, { useState, useRef } from 'react';
import { useAgentRuns } from '../../hooks/useAgentRuns';
import './FeedbackInput.css';

interface FeedbackInputProps {
  runId: string;
  disabled?: boolean;
}

export const FeedbackInput: React.FC<FeedbackInputProps> = ({ 
  runId, 
  disabled = false 
}) => {
  const { sendFeedback } = useAgentRuns();
  const [message, setMessage] = useState('');
  const [isSending, setIsSending] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Handle send
  const handleSend = async () => {
    if (!message.trim() || disabled || isSending) return;
    
    setIsSending(true);
    
    try {
      await sendFeedback(runId, message.trim());
      setMessage('');
      
      // Reset textarea height
      if (textareaRef.current) {
        textareaRef.current.style.height = 'auto';
      }
    } finally {
      setIsSending(false);
    }
  };

  // Handle keyboard shortcut
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // Auto-resize textarea
  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setMessage(e.target.value);
    
    // Auto-resize
    const textarea = e.target;
    textarea.style.height = 'auto';
    textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px';
  };

  return (
    <div className={`feedback-input ${disabled ? 'feedback-input--disabled' : ''}`}>
      <div className="feedback-input__wrapper">
        <textarea
          ref={textareaRef}
          className="feedback-input__textarea"
          placeholder={disabled ? 'Run is not active' : 'Give feedback to the agent...'}
          value={message}
          onChange={handleInput}
          onKeyDown={handleKeyDown}
          disabled={disabled || isSending}
          rows={1}
        />
        <button
          className="feedback-input__send"
          onClick={handleSend}
          disabled={!message.trim() || disabled || isSending}
          title="Send feedback (Enter)"
        >
          {isSending ? (
            <div className="feedback-input__spinner" />
          ) : (
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"/>
            </svg>
          )}
        </button>
      </div>
      <span className="feedback-input__hint">
        Press Enter to send
      </span>
    </div>
  );
};
