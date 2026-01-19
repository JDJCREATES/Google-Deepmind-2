import { useState } from 'react';
import { VscEdit, VscDebugRestart, VscCheck, VscClose } from 'react-icons/vsc';
import { BlockRenderer } from './BlockStreamRenderer';
import type { ChatMessage as ChatMessageType } from '../agent-dashboard/types';

interface ChatMessageProps {
  message: ChatMessageType;
  onEdit?: (messageId: string, newContent: string) => void;
  onRewind?: (messageId: string) => void;
}

export default function ChatMessage({ message, onEdit, onRewind }: ChatMessageProps) {
  const isUser = message.sender === 'user';
  const [isEditing, setIsEditing] = useState(false);
  const [editContent, setEditContent] = useState(message.content);

  const handleSaveEdit = () => {
    if (onEdit && editContent.trim() !== message.content) {
      onEdit(message.id, editContent);
    }
    setIsEditing(false);
  };
  
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
                    {message.blocks.map((block) => {
                        return <BlockRenderer key={block.id} block={block} />;
                    })}
                </div>
            </div>
        );
    }
    
    // Legacy text fallback - just display content normally
    return (
      <div className={`message ${isSystem ? 'message-system' : 'message-ai'}`}>
        <div className="message-content no-bubble">
          {message.content}
        </div>
      </div>
    );
  }

  // USER MESSAGE with Controls
  return (
    <div className="message message-user group flex flex-col items-end">
      <div 
        className={`message-bubble relative group ${!isEditing ? 'cursor-pointer hover:brightness-90 active:scale-[0.99] transition-all !p-3' : ''}`}
        onClick={() => {
          if (!isEditing && onEdit) {
            setEditContent(message.content);
            setIsEditing(true);
          }
        }}
        title={!isEditing ? "Click to edit" : ""}
      >
        {isEditing ? (
          <div className="edit-container min-w-[300px]" onClick={(e) => e.stopPropagation()}>
            <textarea 
              className="w-full bg-slate-800 text-white rounded p-2 text-sm focus:outline-none resize-none border border-slate-600"
              value={editContent}
              onChange={(e) => setEditContent(e.target.value)}
              rows={Math.max(2, editContent.split('\n').length)}
              autoFocus
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSaveEdit();
                }
                if (e.key === 'Escape') setIsEditing(false);
              }}
            />
            <div className="flex justify-end gap-2 mt-2">
              <button 
                onClick={(e) => {
                    e.stopPropagation();
                    setIsEditing(false);
                }}
                className="p-1 hover:bg-slate-700 rounded text-xs text-slate-400 flex items-center gap-1"
                title="Cancel (Esc)"
              >
                <VscClose /> Cancel
              </button>
              <button 
                onClick={(e) => {
                    e.stopPropagation();
                    handleSaveEdit();
                }}
                className="p-1 bg-blue-600 hover:bg-blue-500 rounded text-xs text-white flex items-center gap-1 px-2"
                title="Save & Resend (Enter)"
              >
                <VscCheck /> Save
              </button>
            </div>
          </div>
        ) : (
          <div className="message-content whitespace-pre-wrap">{message.content}</div>
        )}
      </div>

      {/* Timestamp & Actions Row (BELOW BUBBLE) */}
      {!isEditing && (
        <div className="message-footer flex items-center justify-end mt-1 gap-3 mr-1 opacity-0 group-hover:opacity-100 transition-opacity">
            <div className="message-time text-[10px] opacity-40">
            {new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </div>
            
            <div className="message-actions flex items-center gap-2">
                {onEdit && (
                    <button 
                        onClick={() => {
                            setEditContent(message.content);
                            setIsEditing(true);
                        }}
                        className="p-1 hover:bg-white/10 rounded text-slate-400 hover:text-white transition-colors flex items-center gap-1 text-[10px]"
                        title="Edit message"
                    >
                        <VscEdit size={12} /> Edit
                    </button>
                )}
                {onRewind && (
                    <button 
                        onClick={() => onRewind(message.id)}
                        className="p-1 hover:bg-white/10 rounded text-slate-400 hover:text-white transition-colors flex items-center gap-1 text-[10px]"
                        title="Revert to this message (clears history after)"
                    >
                        <VscDebugRestart size={12} /> Rewind
                    </button>
                )}
            </div>
        </div>
      )}
    </div>
  );
}
