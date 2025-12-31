/**
 * Tool Progress Component
 * 
 * Displays a collapsible card showing tool execution progress.
 * Shows files being created, commands running, etc.
 */

import { useState, useEffect } from 'react';
import { FiChevronDown, FiChevronRight, FiCheck, FiLoader, FiX, FiFile, FiTerminal, FiEdit } from 'react-icons/fi';
import './ToolProgress.css';

export interface ToolEvent {
  id: string;
  type: 'tool_start' | 'tool_result';
  tool: string;
  file?: string;
  success?: boolean;
  timestamp: number;
}

interface ToolProgressProps {
  events: ToolEvent[];
  isCollapsed?: boolean;
  onToggleCollapse?: () => void;
}

// Map tool names to icons
const getToolIcon = (tool: string) => {
  switch (tool) {
    case 'write_file_to_disk':
    case 'read_file_from_disk':
    case 'edit_file_content':
      return <FiFile size={14} />;
    case 'run_terminal_command':
      return <FiTerminal size={14} />;
    case 'list_directory':
      return <FiFile size={14} />;
    default:
      return <FiEdit size={14} />;
  }
};

// Get friendly tool name
const getToolDisplayName = (tool: string): string => {
  switch (tool) {
    case 'write_file_to_disk':
      return 'Created';
    case 'read_file_from_disk':
      return 'Read';
    case 'edit_file_content':
      return 'Edited';
    case 'run_terminal_command':
      return 'Running';
    case 'list_directory':
      return 'Listed';
    default:
      return tool.replace(/_/g, ' ');
  }
};

export function ToolProgress({ events, isCollapsed = false, onToggleCollapse }: ToolProgressProps) {
  const [expanded, setExpanded] = useState(!isCollapsed);
  
  // Sync state with prop if it changes (e.g., auto-collapse on done)
  useEffect(() => {
    setExpanded(!isCollapsed);
  }, [isCollapsed]);
  
  // Group events by completion status
  const completedCount = events.filter(e => e.type === 'tool_result' && e.success).length;
  const failedCount = events.filter(e => e.type === 'tool_result' && !e.success).length;
  const pendingCount = events.filter(e => e.type === 'tool_start').length - completedCount - failedCount;
  
  // Get unique completed files (dedupe start/result pairs)
  const fileResults = events
    .filter(e => e.type === 'tool_result')
    .reduce((acc, e) => {
      const key = e.file || e.tool;
      if (!acc.has(key)) {
        acc.set(key, e);
      }
      return acc;
    }, new Map<string, ToolEvent>());

  if (events.length === 0) return null;

  return (
    <div className="tool-progress">
      <div 
        className="tool-progress-header"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="tool-progress-toggle">
          {expanded ? <FiChevronDown size={14} /> : <FiChevronRight size={14} />}
        </div>
        <div className="tool-progress-summary">
          <span className="tool-progress-icon">📁</span>
          <span className="tool-progress-title">
            {pendingCount > 0 ? 'Working...' : 'Files Created'}
          </span>
          <span className="tool-progress-count">
            {completedCount > 0 && (
              <span className="count-badge success">{completedCount}</span>
            )}
            {failedCount > 0 && (
              <span className="count-badge error">{failedCount}</span>
            )}
            {pendingCount > 0 && (
              <span className="count-badge pending">{pendingCount}</span>
            )}
          </span>
        </div>
      </div>
      
      {expanded && (
        <div className="tool-progress-list">
          {Array.from(fileResults.values()).map((event, idx) => (
            <div 
              key={event.id || idx} 
              className={`tool-progress-item ${event.success ? 'success' : 'error'}`}
            >
              <span className="tool-item-status">
                {event.success ? (
                  <FiCheck className="status-icon success" />
                ) : (
                  <FiX className="status-icon error" />
                )}
              </span>
              <span className="tool-item-icon">
                {getToolIcon(event.tool)}
              </span>
              <span className="tool-item-file">
                {event.file || event.tool}
              </span>
            </div>
          ))}
          
          {fileResults.size === 0 && (
             <div className="tool-progress-empty">No files created yet.</div>
          )}
        </div>
      )}
    </div>
  );
}
