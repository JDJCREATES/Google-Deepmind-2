/**
 * Terminal Executor Module
 * 
 * Executes validated commands using child_process.spawn.
 * Handles streaming output, timeouts, and cleanup.
 */

import { spawn, ChildProcess } from 'child_process';
import { platform } from 'os';
import type { CommandRequest, CommandResult, CommandStreamEvent } from './types';
import { validateCommand, getAllowedCommandConfig } from './security';

/** Active processes for cleanup */
const activeProcesses: Map<string, ChildProcess> = new Map();

/**
 * Generate a unique process ID.
 */
function generateProcessId(): string {
  return `proc_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

/**
 * Get the shell configuration for the current platform.
 */
function getShellConfig(): { shell: string; shellFlag: string } {
  if (platform() === 'win32') {
    return { shell: 'cmd.exe', shellFlag: '/c' };
  }
  return { shell: '/bin/sh', shellFlag: '-c' };
}

/**
 * Execute a command and return the result.
 * This is the main execution function.
 */
export async function executeCommand(request: CommandRequest): Promise<CommandResult> {
  const startTime = Date.now();
  const processId = generateProcessId();
  
  // Validate command first
  const validation = validateCommand(request.command, request.cwd);
  if (!validation.isValid) {
    return {
      success: false,
      exitCode: null,
      stdout: '',
      stderr: validation.error || 'Command validation failed',
      error: validation.error,
      durationMs: Date.now() - startTime,
    };
  }

  // Get timeout from allowed command config or request
  const cmdConfig = getAllowedCommandConfig(request.command);
  const timeout = request.timeout ?? cmdConfig?.maxTimeout ?? 60000;

  const { shell, shellFlag } = getShellConfig();
  
  return new Promise((resolve) => {
    let stdout = '';
    let stderr = '';
    let timedOut = false;
    let resolved = false;

    const finish = (exitCode: number | null, error?: string) => {
      if (resolved) return;
      resolved = true;
      
      // Cleanup
      activeProcesses.delete(processId);
      
      resolve({
        success: exitCode === 0,
        exitCode,
        stdout,
        stderr,
        error: error || (timedOut ? 'Command timed out' : undefined),
        timedOut,
        durationMs: Date.now() - startTime,
      });
    };

    try {
      const child = spawn(shell, [shellFlag, validation.sanitizedCommand!], {
        cwd: request.cwd,
        env: {
          ...process.env,
          // Ensure npm doesn't prompt for input
          npm_config_yes: 'true',
          CI: 'true',
        },
        windowsHide: true,
      });

      activeProcesses.set(processId, child);

      // Set timeout
      const timeoutHandle = setTimeout(() => {
        timedOut = true;
        child.kill('SIGTERM');
        
        // Force kill after 5 seconds if still running
        setTimeout(() => {
          if (!resolved) {
            child.kill('SIGKILL');
          }
        }, 5000);
      }, timeout);

      child.stdout?.on('data', (data: Buffer) => {
        stdout += data.toString();
      });

      child.stderr?.on('data', (data: Buffer) => {
        stderr += data.toString();
      });

      child.on('error', (error: Error) => {
        clearTimeout(timeoutHandle);
        finish(null, error.message);
      });

      child.on('close', (code: number | null) => {
        clearTimeout(timeoutHandle);
        finish(code);
      });

    } catch (error: any) {
      finish(null, error.message);
    }
  });
}

/**
 * Execute a command with streaming output.
 * Calls the callback for each output event.
 */
export async function executeCommandWithStream(
  request: CommandRequest,
  onEvent: (event: CommandStreamEvent) => void
): Promise<CommandResult> {
  const startTime = Date.now();
  const processId = generateProcessId();
  
  // Validate command first
  const validation = validateCommand(request.command, request.cwd);
  if (!validation.isValid) {
    const error = validation.error || 'Command validation failed';
    onEvent({ type: 'error', data: error, timestamp: Date.now() });
    return {
      success: false,
      exitCode: null,
      stdout: '',
      stderr: error,
      error,
      durationMs: Date.now() - startTime,
    };
  }

  // Get timeout from allowed command config or request
  const cmdConfig = getAllowedCommandConfig(request.command);
  const timeout = request.timeout ?? cmdConfig?.maxTimeout ?? 60000;

  const { shell, shellFlag } = getShellConfig();
  
  return new Promise((resolve) => {
    let stdout = '';
    let stderr = '';
    let timedOut = false;
    let resolved = false;

    const finish = (exitCode: number | null, error?: string) => {
      if (resolved) return;
      resolved = true;
      
      activeProcesses.delete(processId);
      
      onEvent({ 
        type: 'exit', 
        data: String(exitCode ?? 'null'), 
        timestamp: Date.now() 
      });
      
      resolve({
        success: exitCode === 0,
        exitCode,
        stdout,
        stderr,
        error: error || (timedOut ? 'Command timed out' : undefined),
        timedOut,
        durationMs: Date.now() - startTime,
      });
    };

    try {
      const child = spawn(shell, [shellFlag, validation.sanitizedCommand!], {
        cwd: request.cwd,
        env: {
          ...process.env,
          npm_config_yes: 'true',
          CI: 'true',
        },
        windowsHide: true,
      });

      activeProcesses.set(processId, child);

      const timeoutHandle = setTimeout(() => {
        timedOut = true;
        onEvent({ type: 'error', data: 'Command timed out', timestamp: Date.now() });
        child.kill('SIGTERM');
        setTimeout(() => {
          if (!resolved) child.kill('SIGKILL');
        }, 5000);
      }, timeout);

      child.stdout?.on('data', (data: Buffer) => {
        const text = data.toString();
        stdout += text;
        onEvent({ type: 'stdout', data: text, timestamp: Date.now() });
      });

      child.stderr?.on('data', (data: Buffer) => {
        const text = data.toString();
        stderr += text;
        onEvent({ type: 'stderr', data: text, timestamp: Date.now() });
      });

      child.on('error', (error: Error) => {
        clearTimeout(timeoutHandle);
        onEvent({ type: 'error', data: error.message, timestamp: Date.now() });
        finish(null, error.message);
      });

      child.on('close', (code: number | null) => {
        clearTimeout(timeoutHandle);
        finish(code);
      });

    } catch (error: any) {
      onEvent({ type: 'error', data: error.message, timestamp: Date.now() });
      finish(null, error.message);
    }
  });
}

/**
 * Kill all active processes.
 * Called during app shutdown.
 */
export function killAllProcesses(): void {
  for (const [_id, proc] of activeProcesses) {
    try {
      proc.kill('SIGTERM');
    } catch {
      // Process may already be dead
    }
  }
  activeProcesses.clear();
}

/**
 * Get count of active processes.
 */
export function getActiveProcessCount(): number {
  return activeProcesses.size;
}
