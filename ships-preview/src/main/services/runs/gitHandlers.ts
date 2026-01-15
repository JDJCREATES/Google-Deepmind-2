import { ipcMain } from 'electron';
import { GitSyncManager } from './GitSyncManager';

let gitManager: GitSyncManager | null = null;

export function registerGitHandlers(getProjectPath: () => string | null) {
  const getManager = () => {
    const path = getProjectPath();
    if (!path) throw new Error('No project selected');
    if (!gitManager || (gitManager as any).projectPath !== path) {
        gitManager = new GitSyncManager(path);
    }
    return gitManager;
  };

  // Get remotes
  ipcMain.handle('git:getRemotes', async () => {
    try {
      return await getManager().getRemotes();
    } catch (error: any) {
      console.error('Failed to get remotes:', error);
      throw error;
    }
  });

  // Set remote
  ipcMain.handle('git:setRemote', async (_, args: { url: string; name?: string }) => {
    try {
      await getManager().setRemote(args.url, args.name);
    } catch (error: any) {
      console.error('Failed to set remote:', error);
      throw error;
    }
  });

  // Push branch
  ipcMain.handle('git:push', async (_, args: { branch: string; token?: string; username?: string }) => {
    try {
      const manager = getManager();
      if (args.token && args.username) {
        manager.setCredentials(args.username, args.token);
      }
      await manager.pushBranch(args.branch);
    } catch (error: any) {
      console.error('Failed to push branch:', error);
      throw error;
    }
  });

  // Pull branch
  ipcMain.handle('git:pull', async (_, args: { branch: string }) => {
    try {
      await getManager().pullBranch(args.branch);
    } catch (error: any) {
      console.error('Failed to pull branch:', error);
      throw error;
    }
  });
  
  // Check conflicts (stub for now, but wired)
  ipcMain.handle('git:checkConflicts', async (_, args: { source: string; target: string }) => {
      try {
          return await getManager().checkMergeConflicts(args.source, args.target);
      } catch (error: any) {
          console.error('Failed to check conflicts:', error);
          throw error;
      }
  });
}
