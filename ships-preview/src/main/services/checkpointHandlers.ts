/**
 * Checkpoint IPC Handlers
 *
 * Exposes git checkpoint service to renderer and backend via IPC.
 * Follows same pattern as artifactHandlers.ts
 */

import { ipcMain } from 'electron';
import { GitCheckpointService, getCheckpointService } from './gitCheckpoint';

let checkpointService: GitCheckpointService | null = null;
let currentProjectPath: string | null = null;

/**
 * Register checkpoint IPC handlers
 */
export function registerCheckpointHandlers(projectPath: string): void {
  currentProjectPath = projectPath;

  // Initialize checkpoint service
  ipcMain.handle('checkpoint:initialize', async () => {
    try {
      checkpointService = await getCheckpointService(projectPath);
      return { success: true };
    } catch (error: any) {
      return { success: false, error: error.message };
    }
  });

  // Create a checkpoint
  ipcMain.handle('checkpoint:create', async (_, args: {
    message: string;
    stepNumber: number;
    agent: string;
    metadata?: Record<string, any>;
  }) => {
    try {
      if (!checkpointService) {
        checkpointService = await getCheckpointService(projectPath);
      }
      const commitHash = await checkpointService.checkpoint(
        args.message,
        args.stepNumber,
        args.agent,
        args.metadata || {}
      );
      return { success: true, commitHash };
    } catch (error: any) {
      return { success: false, error: error.message };
    }
  });

  // List all checkpoints
  ipcMain.handle('checkpoint:list', async () => {
    try {
      if (!checkpointService) {
        checkpointService = await getCheckpointService(projectPath);
      }
      const checkpoints = await checkpointService.listCheckpoints();
      return { success: true, checkpoints };
    } catch (error: any) {
      return { success: false, error: error.message };
    }
  });

  // List all agent runs
  ipcMain.handle('checkpoint:listRuns', async () => {
    try {
      if (!checkpointService) {
        checkpointService = await getCheckpointService(projectPath);
      }
      const runs = await checkpointService.listRuns();
      return { success: true, runs };
    } catch (error: any) {
      return { success: false, error: error.message };
    }
  });

  // Create a new agent run branch
  ipcMain.handle('checkpoint:createRun', async (_, args: {
    runId: string;
    userRequest?: string;
    parentCommit?: string;
  }) => {
    try {
      if (!checkpointService) {
        checkpointService = await getCheckpointService(projectPath);
      }
      const run = await checkpointService.createRunBranch(
        args.runId,
        args.userRequest || '',
        args.parentCommit
      );
      return { success: true, run };
    } catch (error: any) {
      return { success: false, error: error.message };
    }
  });

  // Rollback to a specific step
  ipcMain.handle('checkpoint:rollback', async (_, stepNumber: number) => {
    try {
      if (!checkpointService) {
        checkpointService = await getCheckpointService(projectPath);
      }
      const success = await checkpointService.rollbackToStep(stepNumber);
      return { success, rolledBackTo: stepNumber };
    } catch (error: any) {
      return { success: false, error: error.message };
    }
  });

  // Merge an agent run branch
  ipcMain.handle('checkpoint:merge', async (_, args: {
    runId: string;
    targetBranch?: string;
  }) => {
    try {
      if (!checkpointService) {
        checkpointService = await getCheckpointService(projectPath);
      }
      const success = await checkpointService.mergeRun(
        args.runId,
        args.targetBranch || 'main'
      );
      return { success, mergedInto: args.targetBranch || 'main' };
    } catch (error: any) {
      return { success: false, error: error.message };
    }
  });

  // Get current step number
  ipcMain.handle('checkpoint:getCurrentStep', async () => {
    try {
      if (!checkpointService) {
        checkpointService = await getCheckpointService(projectPath);
      }
      const step = await checkpointService.getCurrentStep();
      return { success: true, step };
    } catch (error: any) {
      return { success: false, error: error.message };
    }
  });

  console.log('[CheckpointHandlers] Registered for:', projectPath);
}

/**
 * Update project path for checkpoint service
 */
export function updateCheckpointProjectPath(projectPath: string): void {
  currentProjectPath = projectPath;
  checkpointService = null; // Will be re-initialized on next call
}

/**
 * Cleanup checkpoint handlers
 */
export function removeCheckpointHandlers(): void {
  ipcMain.removeHandler('checkpoint:initialize');
  ipcMain.removeHandler('checkpoint:create');
  ipcMain.removeHandler('checkpoint:list');
  ipcMain.removeHandler('checkpoint:listRuns');
  ipcMain.removeHandler('checkpoint:createRun');
  ipcMain.removeHandler('checkpoint:rollback');
  ipcMain.removeHandler('checkpoint:merge');
  ipcMain.removeHandler('checkpoint:getCurrentStep');
  
  checkpointService = null;
  currentProjectPath = null;
}
