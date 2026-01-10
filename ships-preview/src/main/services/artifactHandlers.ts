/**
 * Artifact IPC Handlers
 *
 * Exposes artifact service to renderer via IPC.
 */

import { ipcMain } from 'electron';
import { ArtifactService } from './artifactService';

let artifactService: ArtifactService | null = null;

/**
 * Register artifact IPC handlers
 */
export function registerArtifactHandlers(projectPath: string): void {
  artifactService = new ArtifactService(projectPath);

  // Generate all artifacts
  ipcMain.handle('artifacts:generate', async () => {
    if (!artifactService) return { success: false, error: 'No project loaded' };
    try {
      await artifactService.generateAll();
      return { success: true };
    } catch (error) {
      return { success: false, error: String(error) };
    }
  });

  // Get file tree
  ipcMain.handle('artifacts:getFileTree', async () => {
    if (!artifactService) return null;
    return artifactService.getArtifact('file_tree.json');
  });

  // Get dependency graph
  ipcMain.handle('artifacts:getDependencyGraph', async () => {
    if (!artifactService) return null;
    return artifactService.getArtifact('dependency_graph.json');
  });

  // Build LLM context
  ipcMain.handle('artifacts:buildContext', async (_, scopeFiles: string[]) => {
    if (!artifactService) return '';
    return artifactService.buildContext(scopeFiles);
  });

  // Get all artifacts summary (for API requests)
  ipcMain.handle('artifacts:getSummary', async () => {
    if (!artifactService) return null;
    
    const fileTree = artifactService.getArtifact('file_tree.json');
    const depGraph = artifactService.getArtifact('dependency_graph.json');
    
    return {
      fileTree: fileTree ? {
        version: fileTree.version,
        fileCount: Object.keys(fileTree.files).length,
        generatedAt: fileTree.generatedAt,
      } : null,
      dependencyGraph: depGraph ? {
        version: depGraph.version,
        nodeCount: Object.keys(depGraph.nodes).length,
        generatedAt: depGraph.generatedAt,
      } : null,
    };
  });
}

/**
 * Update project path (when user selects new folder)
 */
export function updateProjectPath(projectPath: string): void {
  artifactService = new ArtifactService(projectPath);
}

/**
 * Cleanup handlers
 */
export function removeArtifactHandlers(): void {
  ipcMain.removeHandler('artifacts:generate');
  ipcMain.removeHandler('artifacts:getFileTree');
  ipcMain.removeHandler('artifacts:getDependencyGraph');
  ipcMain.removeHandler('artifacts:buildContext');
  ipcMain.removeHandler('artifacts:getSummary');
  artifactService = null;
}
