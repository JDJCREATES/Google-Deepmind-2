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
        console.log('[ChatMessage] Rendering', message.blocks.length, 'blocks for message', message.id);
        return (
            <div className={`message ${isSystem ? 'message-system' : 'message-ai'}`}>
                <div className="message-content no-bubble" style={{ width: '100%' }}>
                    {message.blocks.map((block, index) => {
                        console.log('[ChatMessage] Rendering block', index, ':', block.type, block.id);
                        return <BlockRenderer key={block.id} block={block} />;
                    })}
                </div>
            </div>
        );
    }
    
    // Fallback: If content looks like JSON, format it nicely
    let displayContent = message.content;
    let isJsonContent = false;
    
    if (typeof message.content === 'string' && message.content.trim().startsWith('{')) {
      try {
        const parsed = JSON.parse(message.content);
        displayContent = JSON.stringify(parsed, null, 2);
        isJsonContent = true;
        console.warn('[ChatMessage] ⚠️ Displaying raw JSON (blocks failed):', parsed);
      } catch (e) {
        // Not valid JSON, display as-is
      }
    }
    
    // Legacy / Text Fallback
    return (
      <div className={`message ${isSystem ? 'message-system' : 'message-ai'}`}>
        <div className="message-content no-bubble">
          {isJsonContent ? (
            <pre style={{ 
              background: '#1e1e1e', 
              color: '#d4d4d4',
              padding: '12px', 
              borderRadius: '6px',
              overflow: 'auto',
              fontSize: '12px',
              border: '1px solid #ff5e57'
            }}>
              <div style={{ 
                color: '#ff5e57', 
                marginBottom: '8px', 
                fontWeight: 'bold' 
              }}>
                ⚠️ DEBUG: Raw JSON (blocks not rendering)
              </div>
              {displayContent}
            </pre>
          ) : displayContent}
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
