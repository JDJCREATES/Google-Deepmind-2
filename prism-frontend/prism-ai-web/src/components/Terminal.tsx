/**
 * Terminal Component
 * 
 * Displays terminal output from agent command execution.
 * Shows stdout/stderr streams in real-time.
 * Can be embedded inline (IDE-style) or floating.
 */

import { useEffect, useRef } from 'react';
import { FiTerminal, FiX, FiChevronDown, FiChevronUp } from 'react-icons/fi';
import './Terminal.css';

export interface TerminalLine {
  type: 'stdout' | 'stderr' | 'command' | 'system';
  content: string;
  timestamp: number;
}

interface TerminalProps {
  lines: TerminalLine[];
  isVisible: boolean;
  isCollapsed?: boolean;
  onClose: () => void;
  onToggleCollapse?: () => void;
  /** If true, renders inline (for sidebar). If false, renders floating. */
  inline?: boolean;
}

export function Terminal({ 
  lines, 
  isVisible, 
  isCollapsed = false,
  onClose, 
  onToggleCollapse,
  inline = false 
}: TerminalProps) {
  const terminalRef = useRef<HTMLDivElement>(null);
  
  // Auto-scroll to bottom on new lines
  useEffect(() => {
    if (terminalRef.current && !isCollapsed) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
    }
  }, [lines, isCollapsed]);
  
  if (!isVisible) return null;
  
  const containerClass = inline 
    ? `terminal-inline ${isCollapsed ? 'terminal-collapsed' : ''}` 
    : 'terminal-floating';
  
  return (
    <div className={containerClass}>
      <div className="terminal-header" onClick={onToggleCollapse}>
        <div className="terminal-title">
          <FiTerminal size={14} />
          <span>Terminal</span>
          {lines.length > 0 && (
            <span className="terminal-count">{lines.length}</span>
          )}
        </div>
        <div className="terminal-actions">
          {onToggleCollapse && (
            <button onClick={(e) => { e.stopPropagation(); onToggleCollapse(); }}>
              {isCollapsed ? <FiChevronUp size={14} /> : <FiChevronDown size={14} />}
            </button>
          )}
          <button onClick={(e) => { e.stopPropagation(); onClose(); }}>
            <FiX size={14} />
          </button>
        </div>
      </div>
      
      {!isCollapsed && (
        <div className="terminal-content" ref={terminalRef}>
          {lines.length === 0 ? (
            <div className="terminal-empty">No terminal output yet...</div>
          ) : (
            lines.map((line, index) => (
              <div key={index} className={`terminal-line terminal-${line.type}`}>
                <span className="terminal-prefix">
                  {line.type === 'command' ? '$ ' : 
                   line.type === 'stderr' ? '⚠ ' : 
                   line.type === 'system' ? '→ ' : ''}
                </span>
                <span className="terminal-text">{line.content}</span>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
