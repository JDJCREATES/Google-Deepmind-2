/**
 * Timeline Node Component
 * 
 * Displays a single node in the timeline (feature, fix, deploy, etc.)
 */

import type { TimelineNode as TimelineNodeType, NodeStatus } from '../../types/timeline';
import './TimelineNode.css';

interface TimelineNodeProps {
  node: TimelineNodeType;
  isActive?: boolean;
  isCurrent?: boolean;
  onClick?: () => void;
  onHover?: (hovering: boolean) => void;
}

// Get status emoji
const getStatusEmoji = (status: NodeStatus): string => {
  switch (status) {
    case 'success': return '✅';
    case 'failed': return '❌';
    case 'warning': return '⚠️';
    case 'in-progress': return '🔄';
    case 'pending': return '○';
    default: return '○';
  }
};

// Get node shape based on type and status
const getNodeShape = (status: NodeStatus, isCurrent: boolean): string => {
  if (isCurrent) return 'diamond'; // ◆
  if (status === 'pending') return 'circle-empty'; // ○
  return 'circle-filled'; // ●
};

// Format duration
const formatDuration = (ms: number): string => {
  const seconds = Math.floor(ms / 1000);
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  
  if (minutes > 0) {
    return `${minutes}m ${remainingSeconds}s`;
  }
  return `${seconds}s`;
};

export function TimelineNode({ 
  node, 
  isActive = false, 
  isCurrent = false,
  onClick,
  onHover 
}: TimelineNodeProps) {
  const shape = getNodeShape(node.status, isCurrent);
  const emoji = getStatusEmoji(node.status);
  
  const statusText = 
    node.status === 'success' ? 'Completed' : 
    node.status === 'failed' ? 'Failed' : 
    node.status === 'in-progress' ? 'In Progress' : 
    node.status === 'warning' ? 'Success with warnings' : 
    'Pending';
  
  return (
    <div 
      className={`timeline-node ${shape} ${node.status} ${isActive ? 'active' : ''} ${isCurrent ? 'current' : ''}`}
      onClick={onClick}
      onMouseEnter={() => onHover?.(true)}
      onMouseLeave={() => onHover?.(false)}
      role="button"
      tabIndex={0}
      aria-label={`${node.title} - ${statusText}`}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onClick?.();
        }
      }}
    >
      <div className="timeline-node-dot" aria-hidden="true">
        {node.status === 'in-progress' && <div className="pulse-ring" />}
        <div className="node-shape" />
      </div>
      
      <div className="timeline-node-label">
        {node.title}
      </div>
      
      <div className="timeline-node-status" aria-label={statusText}>
        <span className="status-emoji" role="img" aria-label={statusText}>{emoji}</span>
      </div>
      
      {/* Hover tooltip */}
      <div className="timeline-node-tooltip" role="tooltip">
        <div className="tooltip-title">{node.title}</div>
        <div className="tooltip-status">
          {emoji} {statusText}
        </div>
        {node.duration_ms > 0 && (
          <div className="tooltip-duration">{formatDuration(node.duration_ms)}</div>
        )}
        <div className="tooltip-files">{node.files_changed.length} files changed</div>
        {node.status !== 'pending' && (
          <div className="tooltip-action">
            <button className="tooltip-btn">View Details</button>
          </div>
        )}
      </div>
    </div>
  );
}
