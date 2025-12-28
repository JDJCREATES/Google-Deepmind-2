/**
 * Terminal Security Module
 * 
 * Command validation and sanitization for safe terminal execution.
 * This is the security gate - all commands must pass through here.
 */

import { existsSync, statSync } from 'fs';
import type { CommandValidationResult, AllowedCommand } from './types';

/**
 * Whitelisted command prefixes with their configurations.
 * Only these commands can be executed.
 */
export const ALLOWED_COMMANDS: AllowedCommand[] = [
  { prefix: 'npm', description: 'Node package manager', maxTimeout: 300000, requiresApproval: false },
  { prefix: 'npx', description: 'NPM package runner', maxTimeout: 300000, requiresApproval: false },
  { prefix: 'yarn', description: 'Yarn package manager', maxTimeout: 300000, requiresApproval: false },
  { prefix: 'pnpm', description: 'PNPM package manager', maxTimeout: 300000, requiresApproval: false },
  { prefix: 'git', description: 'Git version control', maxTimeout: 60000, requiresApproval: false },
  { prefix: 'python', description: 'Python interpreter', maxTimeout: 60000, requiresApproval: true },
  { prefix: 'py', description: 'Python interpreter (Windows)', maxTimeout: 60000, requiresApproval: true },
  { prefix: 'pip', description: 'Python package manager', maxTimeout: 300000, requiresApproval: true },
  { prefix: 'node', description: 'Node.js runtime', maxTimeout: 60000, requiresApproval: true },
];

/**
 * Blocked patterns that indicate dangerous operations.
 * Commands containing these will be rejected.
 */
const BLOCKED_PATTERNS: RegExp[] = [
  /rm\s+-rf/i,           // Recursive delete
  /rm\s+--force/i,       // Force delete
  /del\s+\/[fqs]/i,      // Windows force delete
  /rmdir\s+\/s/i,        // Windows recursive delete
  /format\s+/i,          // Disk format
  /mkfs\s+/i,            // Make filesystem
  /\|\s*sh/i,            // Pipe to shell
  /\|\s*bash/i,          // Pipe to bash
  /\|\s*cmd/i,           // Pipe to cmd
  /;\s*rm/i,             // Command chain to rm
  /&&\s*rm/i,            // Command chain to rm
  /sudo\s+/i,            // Privilege escalation
  /chmod\s+/i,           // Permission changes
  /chown\s+/i,           // Ownership changes
  /curl.*\|\s*sh/i,      // Curl pipe to shell
  /wget.*\|\s*sh/i,      // Wget pipe to shell
  /eval\s+/i,            // Eval execution
  /exec\s+/i,            // Exec execution
  /`.*`/,                // Backtick execution
  /\$\(/,                // Subshell execution
  />.*\/etc\//i,         // Write to /etc
  />.*\.bashrc/i,        // Write to bashrc
  />.*\.profile/i,       // Write to profile
];

/**
 * Blocked subcommands for specific tools.
 */
const BLOCKED_SUBCOMMANDS: Record<string, string[]> = {
  npm: ['exec', 'x'],  // npm exec can run arbitrary code
  git: ['filter-branch', 'gc', 'prune'],  // Destructive git commands
};

/**
 * Validate that a path is safe for command execution.
 */
export function isPathSafe(projectPath: string): boolean {
  if (!projectPath || !existsSync(projectPath)) {
    return false;
  }

  try {
    const stats = statSync(projectPath);
    if (!stats.isDirectory()) {
      return false;
    }

    // Block system directories
    const normalizedPath = projectPath.toLowerCase().replace(/\\/g, '/');
    const forbidden = [
      'c:/windows',
      'c:/program files',
      'c:/programdata',
      '/system',
      '/usr/bin',
      '/bin',
      '/etc',
      '/var',
    ];

    return !forbidden.some(f => normalizedPath.startsWith(f));
  } catch {
    return false;
  }
}

/**
 * Get the allowed command config for a command prefix.
 */
export function getAllowedCommandConfig(command: string): AllowedCommand | undefined {
  const cmdBase = command.trim().split(/\s+/)[0].toLowerCase();
  return ALLOWED_COMMANDS.find(ac => ac.prefix === cmdBase);
}

/**
 * Validate a command for safe execution.
 * This is the main security gate.
 */
export function validateCommand(command: string, cwd: string): CommandValidationResult {
  // Trim and normalize
  const trimmedCommand = command.trim();
  
  if (!trimmedCommand) {
    return { isValid: false, error: 'Empty command' };
  }

  // Check CWD is safe
  if (!isPathSafe(cwd)) {
    return { isValid: false, error: 'Invalid or unsafe working directory' };
  }

  // Get command base
  const parts = trimmedCommand.split(/\s+/);
  const cmdBase = parts[0].toLowerCase();
  const subCommand = parts[1]?.toLowerCase();

  // Check if command prefix is allowed
  const allowedConfig = ALLOWED_COMMANDS.find(ac => ac.prefix === cmdBase);
  if (!allowedConfig) {
    return { 
      isValid: false, 
      error: `Command '${cmdBase}' is not in the whitelist. Allowed: ${ALLOWED_COMMANDS.map(c => c.prefix).join(', ')}` 
    };
  }

  // Check for blocked subcommands
  const blockedSubs = BLOCKED_SUBCOMMANDS[cmdBase];
  if (blockedSubs && subCommand && blockedSubs.includes(subCommand)) {
    return { isValid: false, error: `Subcommand '${cmdBase} ${subCommand}' is blocked for security` };
  }

  // Check for blocked patterns
  for (const pattern of BLOCKED_PATTERNS) {
    if (pattern.test(trimmedCommand)) {
      return { isValid: false, error: 'Command contains blocked pattern' };
    }
  }

  // Check for path traversal attempts
  if (trimmedCommand.includes('..')) {
    return { isValid: false, error: 'Path traversal (..) is not allowed' };
  }

  // Check for environment variable manipulation in npm scripts
  if (cmdBase === 'npm' && subCommand === 'run') {
    // npm run is allowed, but we trust the project's package.json
    // This is a calculated risk - user controls their own project
  }

  return { 
    isValid: true, 
    sanitizedCommand: trimmedCommand 
  };
}
