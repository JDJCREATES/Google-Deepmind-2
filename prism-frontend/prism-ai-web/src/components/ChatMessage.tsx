export interface Message {
  id: string;
  content: string;
  sender: 'user' | 'ai';
  timestamp: Date;
}

interface ChatMessageProps {
  message: Message;
}

export default function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.sender === 'user';
  
  if (!isUser) {
    return (
      <div className="message message-ai">
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
