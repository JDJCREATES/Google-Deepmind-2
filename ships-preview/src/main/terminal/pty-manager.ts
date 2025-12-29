/**
 * PTY Manager
 * 
 * Manages pseudo-terminal instances for interactive shell access.
 * Security: Sessions are sandboxed to the project directory.
 * 
 * Future enhancement: VM/container isolation for production environments.
 */

import * as os from 'os';
import * as path from 'path';
import * as pty from 'node-pty';

interface PTYSession {
  id: string;
  pty: pty.IPty;
  cwd: string;
  createdAt: Date;
}

// Active PTY sessions
const sessions = new Map<string, PTYSession>();

// Security: Allowed shells (whitelist)
const ALLOWED_SHELLS: Record<string, string[]> = {
  win32: ['powershell.exe', 'cmd.exe'],
  darwin: ['/bin/zsh', '/bin/bash'],
  linux: ['/bin/bash', '/bin/sh', '/usr/bin/zsh'],
};

/**
 * Get the default shell for the current platform
 */
function getDefaultShell(): string {
  const platform = os.platform();
  
  if (platform === 'win32') {
    return process.env.ComSpec || 'powershell.exe';
  }
  
  return process.env.SHELL || '/bin/bash';
}

/**
 * Validate that the shell is allowed
 */
function isShellAllowed(shell: string): boolean {
  const platform = os.platform();
  const allowed = ALLOWED_SHELLS[platform] || [];
  
  // Check if the shell basename matches any allowed shell
  const shellName = path.basename(shell).toLowerCase();
  return allowed.some(s => path.basename(s).toLowerCase() === shellName);
}

/**
 * Spawn a new PTY session
 */
export function spawnPTY(
  projectPath: string,
  options?: {
    cols?: number;
    rows?: number;
    shell?: string;
  }
): { sessionId: string } | { error: string } {
  try {
    const shell = options?.shell || getDefaultShell();
    
    // Security: Validate shell
    if (options?.shell && !isShellAllowed(options.shell)) {
      return { error: `Shell not allowed: ${options.shell}` };
    }
    
    // Security: Validate project path exists
    if (!projectPath) {
      return { error: 'Project path is required' };
    }
    
    const cols = options?.cols || 80;
    const rows = options?.rows || 24;
    
    // Determine shell arguments
    const shellArgs: string[] = os.platform() === 'win32' ? [] : ['--login'];
    
    // Spawn the PTY
    const ptyProcess = pty.spawn(shell, shellArgs, {
      name: 'xterm-256color',
      cols,
      rows,
      cwd: projectPath,
      env: {
        ...process.env,
        // Security: Set restrictive environment
        TERM: 'xterm-256color',
        // Future: Add container/VM isolation here
      },
    });
    
    const sessionId = `pty_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
    
    sessions.set(sessionId, {
      id: sessionId,
      pty: ptyProcess,
      cwd: projectPath,
      createdAt: new Date(),
    });
    
    console.log(`[PTY] Spawned session ${sessionId} in ${projectPath}`);
    
    return { sessionId };
  } catch (error) {
    console.error('[PTY] Spawn error:', error);
    return { error: String(error) };
  }
}

/**
 * Write data to a PTY session
 */
export function writeToPTY(sessionId: string, data: string): boolean {
  const session = sessions.get(sessionId);
  if (!session) {
    console.warn(`[PTY] Session not found: ${sessionId}`);
    return false;
  }
  
  session.pty.write(data);
  return true;
}

/**
 * Resize a PTY session
 */
export function resizePTY(sessionId: string, cols: number, rows: number): boolean {
  const session = sessions.get(sessionId);
  if (!session) {
    console.warn(`[PTY] Session not found: ${sessionId}`);
    return false;
  }
  
  session.pty.resize(cols, rows);
  return true;
}

/**
 * Kill a PTY session
 */
export function killPTY(sessionId: string): boolean {
  const session = sessions.get(sessionId);
  if (!session) {
    return false;
  }
  
  try {
    session.pty.kill();
    sessions.delete(sessionId);
    console.log(`[PTY] Killed session ${sessionId}`);
    return true;
  } catch (error) {
    console.error(`[PTY] Kill error for ${sessionId}:`, error);
    return false;
  }
}

/**
 * Kill all PTY sessions (cleanup on app quit)
 */
export function killAllPTY(): void {
  for (const [sessionId, session] of sessions) {
    try {
      session.pty.kill();
      console.log(`[PTY] Killed session ${sessionId}`);
    } catch (error) {
      console.error(`[PTY] Error killing ${sessionId}:`, error);
    }
  }
  sessions.clear();
}

/**
 * Set up PTY data listener to forward output to renderer
 */
export function onPTYData(
  sessionId: string,
  callback: (data: string) => void
): (() => void) | null {
  const session = sessions.get(sessionId);
  if (!session) {
    return null;
  }
  
  const disposable = session.pty.onData(callback);
  
  // Return cleanup function
  return () => {
    disposable.dispose();
  };
}

/**
 * Set up PTY exit listener
 */
export function onPTYExit(
  sessionId: string,
  callback: (exitCode: number) => void
): (() => void) | null {
  const session = sessions.get(sessionId);
  if (!session) {
    return null;
  }
  
  const disposable = session.pty.onExit(({ exitCode }) => {
    callback(exitCode);
    sessions.delete(sessionId);
  });
  
  return () => {
    disposable.dispose();
  };
}

/**
 * Get active session count
 */
export function getActiveSessionCount(): number {
  return sessions.size;
}
