/**
 * Terminal Component
 * 
 * Displays terminal output from agent command execution.
 * Shows stdout/stderr streams in real-time.
 */

import { useState, useEffect, useRef } from 'react';
import { FiTerminal, FiX, FiMaximize2, FiMinimize2 } from 'react-icons/fi';
import './Terminal.css';

interface TerminalLine {
  type: 'stdout' | 'stderr' | 'command' | 'system';
  content: string;
  timestamp: number;
}

interface TerminalProps {
  lines: TerminalLine[];
  isVisible: boolean;
  onClose: () => void;
}

export function Terminal({ lines, isVisible, onClose }: TerminalProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const terminalRef = useRef<HTMLDivElement>(null);
  
  // Auto-scroll to bottom on new lines
  useEffect(() => {
    if (terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
    }
  }, [lines]);
  
  if (!isVisible) return null;
  
  return (
    <div className={`terminal-container ${isExpanded ? 'terminal-expanded' : ''}`}>
      <div className="terminal-header">
        <div className="terminal-title">
          <FiTerminal />
          <span>Terminal</span>
        </div>
        <div className="terminal-actions">
          <button onClick={() => setIsExpanded(!isExpanded)}>
            {isExpanded ? <FiMinimize2 /> : <FiMaximize2 />}
          </button>
          <button onClick={onClose}>
            <FiX />
          </button>
        </div>
      </div>
      
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
    </div>
  );
}

export type { TerminalLine };
