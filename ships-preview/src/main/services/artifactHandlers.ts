/**
 * Artifact IPC Handlers
 *
 * Exposes artifact generation to renderer via IPC.
 * Uses production ArtifactGenerator with tree-sitter, dependency-cruiser, etc.
 */

import { ipcMain, BrowserWindow } from 'electron';
import { ArtifactGenerator } from './artifactGenerator';
import { FileWatcher } from './fileWatcher';

let artifactGenerator: ArtifactGenerator | null = null;
let fileWatcher: FileWatcher | null = null;
let mainWindow: BrowserWindow | null = null;

/**
 * Register artifact IPC handlers
 */
export function registerArtifactHandlers(projectPath: string, window?: BrowserWindow): void {
  artifactGenerator = new ArtifactGenerator(projectPath);
  mainWindow = window || null;

  // Set up file watcher
  if (fileWatcher) {
    fileWatcher.stop();
  }
  fileWatcher = new FileWatcher(artifactGenerator as any);
  fileWatcher.onUpdate(() => {
    if (mainWindow) {
      mainWindow.webContents.send('artifacts:updated');
    }
  });
  fileWatcher.start(projectPath);

  // Generate all artifacts on project load
  ipcMain.handle('artifacts:generate', async () => {
    if (!artifactGenerator) return { success: false, error: 'No project loaded' };
    try {
      const result = await artifactGenerator.generateAll();
      return result;
    } catch (error: any) {
      return { success: false, error: error.message };
    }
  });

  // Get artifact status
  ipcMain.handle('artifacts:status', async () => {
    if (!artifactGenerator) return null;
    return artifactGenerator.getStatus();
  });

  // Get file tree
  ipcMain.handle('artifacts:getFileTree', async () => {
    if (!artifactGenerator) return null;
    return artifactGenerator.getArtifact('file_tree.json');
  });

  // Get dependency graph
  ipcMain.handle('artifacts:getDependencyGraph', async () => {
    if (!artifactGenerator) return null;
    return artifactGenerator.getArtifact('dependency_graph.json');
  });

  // Get security report
  ipcMain.handle('artifacts:getSecurityReport', async () => {
    if (!artifactGenerator) return null;
    return artifactGenerator.getArtifact('security_report.json');
  });

  // Build LLM context
  ipcMain.handle('artifacts:buildContext', async (_, scopeFiles: string[]) => {
    if (!artifactGenerator) return '';
    return artifactGenerator.buildLLMContext(scopeFiles);
  });

  // Get summary for API requests
  ipcMain.handle('artifacts:getSummary', async () => {
    if (!artifactGenerator) return null;
    
    const fileTree = artifactGenerator.getArtifact('file_tree.json');
    const depGraph = artifactGenerator.getArtifact('dependency_graph.json');
    const security = artifactGenerator.getArtifact('security_report.json');
    
    return {
      fileTree: fileTree ? {
        version: fileTree.version,
        fileCount: fileTree.totalFiles,
        generatedAt: fileTree.generatedAt,
      } : null,
      dependencyGraph: depGraph ? {
        version: depGraph.version,
        moduleCount: depGraph.totalModules,
        circularDeps: depGraph.circularDependencies?.length || 0,
        generatedAt: depGraph.generatedAt,
      } : null,
      security: security ? {
        critical: security.summary?.critical || 0,
        high: security.summary?.high || 0,
        secrets: security.summary?.secrets || 0,
        generatedAt: security.generatedAt,
      } : null,
    };
  });

  console.log('[ArtifactHandlers] Registered for:', projectPath);
}

/**
 * Update project path
 */
export function updateProjectPath(projectPath: string): void {
  if (fileWatcher) {
    fileWatcher.stop();
  }
  artifactGenerator = new ArtifactGenerator(projectPath);
  fileWatcher = new FileWatcher(artifactGenerator as any);
  fileWatcher.start(projectPath);
}

/**
 * Cleanup handlers
 */
export function removeArtifactHandlers(): void {
  ipcMain.removeHandler('artifacts:generate');
  ipcMain.removeHandler('artifacts:status');
  ipcMain.removeHandler('artifacts:getFileTree');
  ipcMain.removeHandler('artifacts:getDependencyGraph');
  ipcMain.removeHandler('artifacts:getSecurityReport');
  ipcMain.removeHandler('artifacts:buildContext');
  ipcMain.removeHandler('artifacts:getSummary');
  
  if (fileWatcher) {
    fileWatcher.stop();
    fileWatcher = null;
  }
  artifactGenerator = null;
  mainWindow = null;
}
