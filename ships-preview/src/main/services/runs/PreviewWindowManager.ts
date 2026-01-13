/**
 * Preview Window Manager
 * 
 * Manages multiple Electron preview windows for different agent runs.
 * Each run gets its own preview window with a dedicated port.
 */

import { BrowserWindow } from 'electron';
import { ChildProcess, spawn } from 'child_process';

export interface PreviewWindow {
  runId: string;
  window: BrowserWindow;
  port: number;
  devServer: ChildProcess | null;
  url: string;
}

export class PreviewWindowManager {
  private windows: Map<string, PreviewWindow> = new Map();
  private basePort: number = 3001; // Start from 3001, leave 3000 for main
  private projectPath: string;

  constructor(projectPath: string) {
    this.projectPath = projectPath;
  }

  /**
   * Get the next available port
   */
  private getNextPort(): number {
    const usedPorts = Array.from(this.windows.values()).map(w => w.port);
    let port = this.basePort;
    
    while (usedPorts.includes(port)) {
      port++;
    }
    
    return port;
  }

  /**
   * Create a new preview window for a run
   */
  async createPreviewWindow(runId: string): Promise<PreviewWindow> {
    const port = this.getNextPort();
    
    // Create browser window
    const window = new BrowserWindow({
      width: 800,
      height: 600,
      title: `Preview - Run ${runId}`,
      webPreferences: {
        nodeIntegration: false,
        contextIsolation: true,
      },
      show: false, // Don't show until loaded
    });

    // Start dev server on the assigned port
    const devServer = await this.startDevServer(port);
    
    const url = `http://localhost:${port}`;
    
    const preview: PreviewWindow = {
      runId,
      window,
      port,
      devServer,
      url,
    };
    
    this.windows.set(runId, preview);
    
    // Load the URL once server is ready
    setTimeout(async () => {
      try {
        await window.loadURL(url);
        window.show();
      } catch (error) {
        console.error(`[PreviewWindowManager] Failed to load URL:`, error);
      }
    }, 3000); // Give dev server time to start
    
    console.log(`[PreviewWindowManager] Created preview for run ${runId} on port ${port}`);
    
    return preview;
  }

  /**
   * Start a dev server on the specified port
   */
  private async startDevServer(port: number): Promise<ChildProcess | null> {
    try {
      // Detect package manager and run command
      const npmCommand = process.platform === 'win32' ? 'npm.cmd' : 'npm';
      
      const devServer = spawn(npmCommand, ['run', 'dev', '--', '--port', String(port)], {
        cwd: this.projectPath,
        shell: true,
        env: { ...process.env, PORT: String(port) },
      });
      
      devServer.stdout?.on('data', (data) => {
        console.log(`[DevServer:${port}] ${data}`);
      });
      
      devServer.stderr?.on('data', (data) => {
        console.error(`[DevServer:${port}] ${data}`);
      });
      
      devServer.on('error', (error) => {
        console.error(`[DevServer:${port}] Error:`, error);
      });
      
      return devServer;
    } catch (error) {
      console.error(`[PreviewWindowManager] Failed to start dev server:`, error);
      return null;
    }
  }

  /**
   * Get a preview window by run ID
   */
  getPreview(runId: string): PreviewWindow | undefined {
    return this.windows.get(runId);
  }

  /**
   * Refresh a preview window
   */
  async refreshPreview(runId: string): Promise<void> {
    const preview = this.windows.get(runId);
    if (preview && preview.window && !preview.window.isDestroyed()) {
      preview.window.reload();
      console.log(`[PreviewWindowManager] Refreshed preview for run ${runId}`);
    }
  }

  /**
   * Close a preview window and stop its dev server
   */
  async closePreview(runId: string): Promise<void> {
    const preview = this.windows.get(runId);
    if (!preview) return;
    
    // Close browser window
    if (preview.window && !preview.window.isDestroyed()) {
      preview.window.close();
    }
    
    // Kill dev server
    if (preview.devServer) {
      preview.devServer.kill();
    }
    
    this.windows.delete(runId);
    console.log(`[PreviewWindowManager] Closed preview for run ${runId}`);
  }

  /**
   * Close all preview windows
   */
  async closeAllPreviews(): Promise<void> {
    for (const runId of this.windows.keys()) {
      await this.closePreview(runId);
    }
  }

  /**
   * Get all active preview windows
   */
  getActivePreviews(): PreviewWindow[] {
    return Array.from(this.windows.values());
  }
}
