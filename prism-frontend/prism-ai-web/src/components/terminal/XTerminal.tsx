/**
 * XTerminal Component
 * 
 * Professional-grade interactive terminal using xterm.js connected to
 * Electron's node-pty via IPC.
 */

import { useEffect, useRef, useState, useCallback } from 'react';
import { Terminal } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import { WebLinksAddon } from '@xterm/addon-web-links';
import { FiTerminal, FiX, FiMaximize2, FiMinimize2, FiPlus } from 'react-icons/fi';
import '@xterm/xterm/css/xterm.css';
import './XTerminal.css';

// Electron PTY API (exposed via preload)
// Electron PTY API (exposed via preload)
declare global {
  interface Window {
    electron?: {
      ptySpawn: (projectPath: string, options?: { cols?: number; rows?: number }) => Promise<{ sessionId: string } | { error: string }>;
      ptyWrite: (sessionId: string, data: string) => Promise<boolean>;
      ptyResize: (sessionId: string, cols: number, rows: number) => Promise<boolean>;
      ptyKill: (sessionId: string) => Promise<boolean>;
      onPTYData: (callback: (event: { sessionId: string; data: string }) => void) => () => void;
      onPTYExit: (callback: (event: { sessionId: string; exitCode: number }) => void) => () => void;
      getLastProject: () => Promise<{ path: string | null; exists: boolean }>;
      selectProjectFolder: () => Promise<{ success: boolean; path: string | null; error?: string }>;
    };
  }
}

interface XTerminalProps {
  projectPath: string | null;
  isVisible: boolean;
  onClose: () => void;
  onToggleCollapse?: () => void;
  isCollapsed?: boolean;
}

export function XTerminal({ 
  projectPath, 
  isVisible, 
  onClose, 
  onToggleCollapse,
  isCollapsed = false 
}: XTerminalProps) {
  const terminalRef = useRef<HTMLDivElement>(null);
  const xtermRef = useRef<Terminal | null>(null);
  const fitAddonRef = useRef<FitAddon | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Initialize xterm.js
  useEffect(() => {
    if (!terminalRef.current || xtermRef.current) return;

    const term = new Terminal({
      cursorBlink: true,
      fontSize: 13,
      fontFamily: "'JetBrains Mono', 'Fira Code', 'Consolas', monospace",
      theme: {
        background: '#1a1a1a',
        foreground: '#cccccc',
        cursor: '#ffffff',
        cursorAccent: '#1a1a1a',
        selectionBackground: '#444444',
        black: '#000000',
        red: '#f44747',
        green: '#4ec9b0',
        yellow: '#dcdcaa',
        blue: '#569cd6',
        magenta: '#c586c0',
        cyan: '#4fc1ff',
        white: '#d4d4d4',
        brightBlack: '#808080',
        brightRed: '#f44747',
        brightGreen: '#4ec9b0',
        brightYellow: '#dcdcaa',
        brightBlue: '#569cd6',
        brightMagenta: '#c586c0',
        brightCyan: '#4fc1ff',
        brightWhite: '#ffffff',
      },
    });

    const fitAddon = new FitAddon();
    const webLinksAddon = new WebLinksAddon();

    term.loadAddon(fitAddon);
    term.loadAddon(webLinksAddon);
    term.open(terminalRef.current);

    xtermRef.current = term;
    fitAddonRef.current = fitAddon;

    // Fit terminal to container
    setTimeout(() => {
      fitAddon.fit();
    }, 0);

    return () => {
      term.dispose();
      xtermRef.current = null;
      fitAddonRef.current = null;
    };
  }, []);

  // Handle resize
  useEffect(() => {
    if (!fitAddonRef.current || isCollapsed) return;

    const handleResize = () => {
      if (fitAddonRef.current && xtermRef.current) {
        fitAddonRef.current.fit();
        
        // Notify PTY of new size
        if (sessionId && window.electron) {
          const { cols, rows } = xtermRef.current;
          window.electron.ptyResize(sessionId, cols, rows);
        }
      }
    };

    window.addEventListener('resize', handleResize);
    
    // Fit when visibility changes
    if (isVisible && !isCollapsed) {
      setTimeout(handleResize, 0);
    }

    return () => window.removeEventListener('resize', handleResize);
  }, [isVisible, isCollapsed, sessionId]);

  // Spawn PTY session when project path is available
  const spawnTerminal = useCallback(async () => {
    if (!projectPath || !window.electron) {
      setError('Terminal requires Electron environment');
      return;
    }

    try {
      const cols = xtermRef.current?.cols || 80;
      const rows = xtermRef.current?.rows || 24;
      
      const result = await window.electron.ptySpawn(projectPath, { cols, rows });
      
      if ('error' in result) {
        setError(result.error);
        return;
      }

      setSessionId(result.sessionId);
      setIsConnected(true);
      setError(null);

      // Write user input to PTY
      xtermRef.current?.onData((data) => {
        if (window.electron && result.sessionId) {
          window.electron.ptyWrite(result.sessionId, data);
        }
      });

    } catch (err) {
      setError(String(err));
    }
  }, [projectPath]);

  // Listen for PTY data
  useEffect(() => {
    if (!window.electron || !sessionId) return;

    const cleanupData = window.electron.onPTYData((event) => {
      if (event.sessionId === sessionId && xtermRef.current) {
        xtermRef.current.write(event.data);
      }
    });

    const cleanupExit = window.electron.onPTYExit((event) => {
      if (event.sessionId === sessionId) {
        xtermRef.current?.writeln(`\r\n[Process exited with code ${event.exitCode}]`);
        setIsConnected(false);
        setSessionId(null);
      }
    });

    return () => {
      cleanupData();
      cleanupExit();
    };
  }, [sessionId]);

  // Kill PTY on unmount
  useEffect(() => {
    return () => {
      if (sessionId && window.electron) {
        window.electron.ptyKill(sessionId);
      }
    };
  }, [sessionId]);

  // Auto-spawn on first visibility
  useEffect(() => {
    if (isVisible && projectPath && !sessionId && !isConnected) {
      spawnTerminal();
    }
  }, [isVisible, projectPath, sessionId, isConnected, spawnTerminal]);

  if (!isVisible) return null;

  return (
    <div className={`xterminal-container ${isCollapsed ? 'xterminal-collapsed' : ''}`}>
      <div className="xterminal-header" onClick={onToggleCollapse}>
        <div className="xterminal-title">
          <FiTerminal size={14} />
          <span>Terminal</span>
          {isConnected && <span className="xterminal-status connected">●</span>}
          {error && <span className="xterminal-status error">●</span>}
        </div>
        <div className="xterminal-actions">
          {!isConnected && !isCollapsed && (
            <button onClick={(e) => { e.stopPropagation(); spawnTerminal(); }} title="New Terminal">
              <FiPlus size={14} />
            </button>
          )}
          {onToggleCollapse && (
            <button onClick={(e) => { e.stopPropagation(); onToggleCollapse(); }}>
              {isCollapsed ? <FiMaximize2 size={14} /> : <FiMinimize2 size={14} />}
            </button>
          )}
          <button onClick={(e) => { e.stopPropagation(); onClose(); }}>
            <FiX size={14} />
          </button>
        </div>
      </div>
      
      {!isCollapsed && (
        <div className="xterminal-content">
          {error && !isConnected && (
            <div className="xterminal-error">
              {error}
              <button onClick={spawnTerminal}>Retry</button>
            </div>
          )}
          <div ref={terminalRef} className="xterminal-xterm" />
        </div>
      )}
    </div>
  );
}
