/**
 * Run IPC Handlers
 *
 * Exposes agent run services to renderer via IPC.
 * Manages preview windows, screenshots, and git branches for each run.
 */

import { ipcMain } from 'electron';
import { BranchRunManager } from './BranchRunManager';
import { PreviewWindowManager } from './PreviewWindowManager';
import { ScreenshotService, type Screenshot } from './ScreenshotService';

let branchManager: BranchRunManager | null = null;
let previewManager: PreviewWindowManager | null = null;
let screenshotService: ScreenshotService | null = null;
let currentProjectPath: string | null = null;

// Track screenshots for each run
const runScreenshots: Map<string, Screenshot[]> = new Map();

/**
 * Initialize run services for a project
 */
function initializeServices(projectPath: string): void {
  if (currentProjectPath === projectPath && branchManager) {
    return; // Already initialized for this project
  }
  
  currentProjectPath = projectPath;
  branchManager = new BranchRunManager(projectPath);
  previewManager = new PreviewWindowManager(projectPath);
  screenshotService = new ScreenshotService(projectPath);
  
  console.log('[RunHandlers] Initialized services for:', projectPath);
}

/**
 * Register run IPC handlers
 */
export function registerRunHandlers(projectPath: string): void {
  initializeServices(projectPath);

  // ========================================
  // Branch Management
  // ========================================

  ipcMain.handle('runs:createBranch', async (_, args: { runId: string; prompt: string }) => {
    try {
      if (!branchManager) throw new Error('Branch manager not initialized');
      const branch = await branchManager.createRunBranch(args.runId, args.prompt);
      return { success: true, branch };
    } catch (error: any) {
      console.error('[RunHandlers] createBranch error:', error);
      return { success: false, error: error.message };
    }
  });

  ipcMain.handle('runs:switchBranch', async (_, args: { runId: string }) => {
    try {
      if (!branchManager) throw new Error('Branch manager not initialized');
      await branchManager.switchToBranch(args.runId);
      return { success: true };
    } catch (error: any) {
      console.error('[RunHandlers] switchBranch error:', error);
      return { success: false, error: error.message };
    }
  });

  ipcMain.handle('runs:deleteBranch', async (_, args: { runId: string }) => {
    try {
      if (!branchManager) throw new Error('Branch manager not initialized');
      await branchManager.deleteBranch(args.runId);
      return { success: true };
    } catch (error: any) {
      console.error('[RunHandlers] deleteBranch error:', error);
      return { success: false, error: error.message };
    }
  });

  ipcMain.handle('runs:createCheckpoint', async (_, args: { message: string }) => {
    try {
      if (!branchManager) throw new Error('Branch manager not initialized');
      const commitHash = await branchManager.createCheckpoint(args.message);
      return { success: true, commitHash };
    } catch (error: any) {
      console.error('[RunHandlers] createCheckpoint error:', error);
      return { success: false, error: error.message };
    }
  });

  ipcMain.handle('runs:rollback', async (_, args: { commitHash: string }) => {
    try {
      if (!branchManager) throw new Error('Branch manager not initialized');
      await branchManager.rollbackToCommit(args.commitHash);
      return { success: true };
    } catch (error: any) {
      console.error('[RunHandlers] rollback error:', error);
      return { success: false, error: error.message };
    }
  });

  // ========================================
  // Preview Window Management
  // ========================================

  ipcMain.handle('runs:createPreview', async (_, args: { runId: string }) => {
    try {
      if (!previewManager) throw new Error('Preview manager not initialized');
      const preview = await previewManager.createPreviewWindow(args.runId);
      return { 
        success: true, 
        preview: {
          runId: preview.runId,
          port: preview.port,
          url: preview.url,
        }
      };
    } catch (error: any) {
      console.error('[RunHandlers] createPreview error:', error);
      return { success: false, error: error.message };
    }
  });

  ipcMain.handle('runs:refreshPreview', async (_, args: { runId: string }) => {
    try {
      if (!previewManager) throw new Error('Preview manager not initialized');
      await previewManager.refreshPreview(args.runId);
      return { success: true };
    } catch (error: any) {
      console.error('[RunHandlers] refreshPreview error:', error);
      return { success: false, error: error.message };
    }
  });

  ipcMain.handle('runs:closePreview', async (_, args: { runId: string }) => {
    try {
      if (!previewManager) throw new Error('Preview manager not initialized');
      await previewManager.closePreview(args.runId);
      return { success: true };
    } catch (error: any) {
      console.error('[RunHandlers] closePreview error:', error);
      return { success: false, error: error.message };
    }
  });

  ipcMain.handle('runs:getActivePreviews', async () => {
    try {
      if (!previewManager) throw new Error('Preview manager not initialized');
      const previews = previewManager.getActivePreviews().map(p => ({
        runId: p.runId,
        port: p.port,
        url: p.url,
      }));
      return { success: true, previews };
    } catch (error: any) {
      console.error('[RunHandlers] getActivePreviews error:', error);
      return { success: false, error: error.message };
    }
  });

  // ========================================
  // Screenshot Management
  // ========================================

  ipcMain.handle('runs:captureScreenshot', async (_, args: { 
    runId: string; 
    agentPhase: string;
    description?: string;
  }) => {
    try {
      if (!screenshotService || !previewManager || !branchManager) {
        throw new Error('Services not initialized');
      }
      
      const preview = previewManager.getPreview(args.runId);
      if (!preview || !preview.window || preview.window.isDestroyed()) {
        throw new Error('Preview window not found or destroyed');
      }
      
      const commitHash = await branchManager.getCurrentCommit();
      
      const screenshot = await screenshotService.captureScreenshot(
        preview.window,
        args.runId,
        commitHash,
        args.agentPhase,
        args.description || ''
      );
      
      // Store screenshot in memory
      const existing = runScreenshots.get(args.runId) || [];
      existing.push(screenshot);
      runScreenshots.set(args.runId, existing);
      
      // Persist to disk
      screenshotService.saveScreenshotIndex(args.runId, existing);
      
      return { success: true, screenshot };
    } catch (error: any) {
      console.error('[RunHandlers] captureScreenshot error:', error);
      return { success: false, error: error.message };
    }
  });

  ipcMain.handle('runs:getScreenshots', async (_, args: { runId: string }) => {
    try {
      if (!screenshotService) throw new Error('Screenshot service not initialized');
      
      // Check memory first
      let screenshots = runScreenshots.get(args.runId);
      
      // Fall back to disk
      if (!screenshots) {
        screenshots = screenshotService.getScreenshotsForRun(args.runId);
        runScreenshots.set(args.runId, screenshots);
      }
      
      return { success: true, screenshots };
    } catch (error: any) {
      console.error('[RunHandlers] getScreenshots error:', error);
      return { success: false, error: error.message };
    }
  });

  ipcMain.handle('runs:deleteScreenshots', async (_, args: { runId: string }) => {
    try {
      if (!screenshotService) throw new Error('Screenshot service not initialized');
      screenshotService.deleteScreenshotsForRun(args.runId);
      runScreenshots.delete(args.runId);
      return { success: true };
    } catch (error: any) {
      console.error('[RunHandlers] deleteScreenshots error:', error);
      return { success: false, error: error.message };
    }
  });

  console.log('[RunHandlers] Registered all IPC handlers');
}

/**
 * Update project path for run services
 */
export function updateRunProjectPath(projectPath: string): void {
  initializeServices(projectPath);
}

/**
 * Cleanup run handlers
 */
export function removeRunHandlers(): void {
  // Close all previews
  if (previewManager) {
    previewManager.closeAllPreviews();
  }
  
  // Remove IPC handlers
  const handlers = [
    'runs:createBranch',
    'runs:switchBranch',
    'runs:deleteBranch',
    'runs:createCheckpoint',
    'runs:rollback',
    'runs:createPreview',
    'runs:refreshPreview',
    'runs:closePreview',
    'runs:getActivePreviews',
    'runs:captureScreenshot',
    'runs:getScreenshots',
    'runs:deleteScreenshots',
  ];
  
  handlers.forEach(channel => {
    ipcMain.removeHandler(channel);
  });
  
  // Clear state
  branchManager = null;
  previewManager = null;
  screenshotService = null;
  currentProjectPath = null;
  runScreenshots.clear();
  
  console.log('[RunHandlers] Removed all IPC handlers');
}
