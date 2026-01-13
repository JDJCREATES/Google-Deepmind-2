export interface Message {
  id: string;
  content: string;
  sender: 'user' | 'ai' | 'system';
  timestamp: Date;
  centered?: boolean;
}

interface ChatMessageProps {
  message: Message;
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
          {message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </div>
      </div>
    </div>
  );
}

