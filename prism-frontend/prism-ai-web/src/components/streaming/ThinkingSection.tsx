import React, { useState } from 'react';
import './ThinkingSection.css';

interface ThinkingSectionProps {
  title: string;
  node: string;
  content: string;
  isLive?: boolean;
  defaultExpanded?: boolean;
}

/**
 * Collapsible thinking section that shows agent thought process
 */
export const ThinkingSection: React.FC<ThinkingSectionProps> = ({
  title,
  node,
  content,
  isLive = false,
  defaultExpanded = true
}) => {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);

  // Get node color
  const getNodeColor = (nodeName: string): string => {
    const colors: Record<string, string> = {
      orchestrator: '#8b5cf6', // Purple
      planner: '#3b82f6',      // Blue
      coder: '#10b981',        // Green
      validator: '#f59e0b',    // Yellow
      fixer: '#ef4444',        // Red
      chat: '#6366f1',         // Indigo
    };
    return colors[nodeName.toLowerCase()] || '#6b7280';
  };

  const nodeColor = getNodeColor(node);

  return (
    <div 
      className={`thinking-section ${isLive ? 'live' : ''}`}
      style={{ '--node-color': nodeColor } as React.CSSProperties}
    >
      <div 
        className="thinking-header"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <span className="thinking-toggle">
          {isExpanded ? '▼' : '▶'}
        </span>
        <span className="thinking-title">{title}</span>
        {isLive && <span className="thinking-live-badge">●</span>}
      </div>
      
      {isExpanded && (
        <div className="thinking-content">
          {content.split('\n').map((line, i) => (
            <p key={i}>{line}</p>
          ))}
          {isLive && <span className="thinking-cursor">█</span>}
        </div>
      )}
    </div>
  );
};

export default ThinkingSection;
