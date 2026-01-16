import React from 'react';
import { RiShip2Fill } from 'react-icons/ri';
import { VscLayoutSidebarRightOff, VscOpenPreview } from 'react-icons/vsc';
import { useAgentRuns } from '../agent-dashboard/hooks/useAgentRuns';

interface ChatHeaderProps {
  activeRun: any; // Type this properly if possible, or use the hook inside
  activeRunId: string | null;
  electronProjectPath: string | null;
  onOpenPreview: () => void;
}

export const ChatHeader: React.FC<ChatHeaderProps> = ({ 
  activeRun, 
  activeRunId, 
  electronProjectPath,
  onOpenPreview 
}) => {
  return (
    <header className="chat-header">
      <div className="chat-header-left">
        <RiShip2Fill size={20} style={{ marginRight: 8, color: 'var(--primary-color, #ff5e57)' }} />
        <span className="chat-title">ShipS*</span>
        {activeRun && (
          <span className="chat-subtitle">
            {' / '}
            {activeRun.branch?.split('/').pop()?.replace('work/', '') || activeRun.title.slice(0, 15)}
          </span>
        )}
      </div>
      
      <div className="chat-header-right">
        <button
          className="chat-header-btn"
          onClick={onOpenPreview}
          title={activeRunId ? 'Open Preview for Run' : 'Open Preview'}
          disabled={!activeRunId && !electronProjectPath}
        >
          <VscOpenPreview size={16} />
        </button>
        <VscLayoutSidebarRightOff size={16} aria-hidden="true" className="chat-header-icon" />
      </div>
    </header>
  );
};
