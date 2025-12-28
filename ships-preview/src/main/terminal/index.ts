/**
 * Terminal Module
 * 
 * Safe terminal execution for ShipS* Electron app.
 * Provides whitelisted command execution with streaming output.
 * 
 * @example
 * ```typescript
 * import { executeCommand, ALLOWED_COMMANDS } from './terminal';
 * 
 * const result = await executeCommand({
 *   command: 'npm install',
 *   cwd: '/path/to/project'
 * });
 * ```
 */

// Re-export types
export type {
  CommandValidationResult,
  CommandRequest,
  CommandResult,
  CommandStreamEvent,
  AllowedCommand,
} from './types';

// Re-export security functions
export {
  ALLOWED_COMMANDS,
  validateCommand,
  isPathSafe,
  getAllowedCommandConfig,
} from './security';

// Re-export executor functions
export {
  executeCommand,
  executeCommandWithStream,
  killAllProcesses,
  getActiveProcessCount,
} from './executor';
