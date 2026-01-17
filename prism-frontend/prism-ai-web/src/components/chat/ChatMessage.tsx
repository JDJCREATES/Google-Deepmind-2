import { BlockRenderer } from './BlockStreamRenderer';
import type { ChatMessage as ChatMessageType } from '../agent-dashboard/types';

interface ChatMessageProps {
  message: ChatMessageType;
}

export default function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.sender === 'user';
  
  // Centered welcome message
  if (message.centered) {
    return (
      <div className="message message-centered" role="status">
        <div className="welcome-content">{message.content}</div>
      </div>
    );
  }
  
  if (!isUser) {
    const isSystem = message.sender === 'system';
    
    // Structured Streaming: Render Blocks
    if (message.blocks && message.blocks.length > 0) {
        return (
            <div className={`message ${isSystem ? 'message-system' : 'message-ai'}`}>
                <div className="message-content no-bubble" style={{ width: '100%' }}>
                    {message.blocks.map(block => (
                        <BlockRenderer key={block.id} block={block} />
                    ))}
                </div>
            </div>
        );
    }
    
    // Legacy / Text Fallback
    return (
      <div className={`message ${isSystem ? 'message-system' : 'message-ai'}`}>
        <div className="message-content no-bubble">
          {message.content}
        </div>
      </div>
    );
  }

  return (
    <div className="message message-user">
      <div className="message-bubble">
        <div className="message-content">{message.content}</div>
        <div className="message-time">
          {new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </div>
      </div>
    </div>
  );
}
