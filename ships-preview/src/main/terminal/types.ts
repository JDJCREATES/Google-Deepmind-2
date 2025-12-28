/**
 * Terminal Module Types
 * 
 * TypeScript interfaces for the terminal execution system.
 */

/** Result of command validation */
export interface CommandValidationResult {
  isValid: boolean;
  error?: string;
  sanitizedCommand?: string;
}

/** Command execution request */
export interface CommandRequest {
  command: string;
  cwd: string;
  timeout?: number;  // ms, default 60000
}

/** Command execution result */
export interface CommandResult {
  success: boolean;
  exitCode: number | null;
  stdout: string;
  stderr: string;
  error?: string;
  timedOut?: boolean;
  durationMs: number;
}

/** Stream event during command execution */
export interface CommandStreamEvent {
  type: 'stdout' | 'stderr' | 'exit' | 'error';
  data: string;
  timestamp: number;
}

/** Whitelisted command configuration */
export interface AllowedCommand {
  prefix: string;
  description: string;
  maxTimeout: number;  // ms
  requiresApproval: boolean;
}
