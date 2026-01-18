/**
 * Preview Window Manager
 * 
 * Manages multiple Electron preview windows for different agent runs.
 * Each run gets its own preview window with a dedicated port.
 * 
 * Features:
 * - Port range validation and conflict detection
 * - Server health checks before loading
 * - Graceful shutdown with timeout
 * - Window lifecycle event handling
 * - Memory-efficient window management
 */

import { BrowserWindow, app } from 'electron';
import { ChildProcess, spawn, exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

// Configuration
const CONFIG = {
  BASE_PORT: 3001,
  MAX_PORT: 3999,
  MAX_WINDOWS: 10,
  SERVER_STARTUP_TIMEOUT: 30000, // 30 seconds
  SERVER_HEALTH_CHECK_INTERVAL: 500, // ms
  SHUTDOWN_TIMEOUT: 5000, // 5 seconds
};

export interface PreviewWindow {
  runId: string;
  window: BrowserWindow;
  port: number;
  devServer: ChildProcess | null;
  url: string;
  status: 'starting' | 'ready' | 'error' | 'closed';
  error?: string;
}

export class PreviewWindowManager {
  private windows: Map<string, PreviewWindow> = new Map();
  private projectPath: string;
  private isShuttingDown: boolean = false;

  constructor(projectPath: string) {
    this.projectPath = projectPath;
    
    // Register cleanup on app quit
    app.on('before-quit', () => {
      this.isShuttingDown = true;
      this.closeAllPreviews();
    });
  }

  /**
   * Sanitize runId to prevent path traversal
   */
  private sanitizeRunId(runId: string): string {
    return runId.replace(/[^a-zA-Z0-9_-]/g, '');
  }

  /**
   * Get the next available port
   */
  private getNextPort(): number {
    const usedPorts = Array.from(this.windows.values()).map(w => w.port);
    let port = CONFIG.BASE_PORT;
    
    while (usedPorts.includes(port) && port <= CONFIG.MAX_PORT) {
      port++;
    }
    
    if (port > CONFIG.MAX_PORT) {
      throw new Error(`No available ports in range ${CONFIG.BASE_PORT}-${CONFIG.MAX_PORT}`);
    }
    
    return port;
  }

  /**
   * Check if a port is in use
   */
  private async isPortInUse(port: number): Promise<boolean> {
    try {
      const command = process.platform === 'win32'
        ? `netstat -ano | findstr :${port}`
        : `lsof -i :${port}`;
      
      await execAsync(command);
      return true;
    } catch {
      return false;
    }
  }

  /**
   * Wait for server to be ready
   */
  private async waitForServer(url: string, timeout: number): Promise<boolean> {
    const startTime = Date.now();
    
    while (Date.now() - startTime < timeout) {
      try {
        const response = await fetch(url, { 
          method: 'HEAD',
          signal: AbortSignal.timeout(2000)
        });
        
        if (response.ok || response.status === 304) {
          return true;
        }
      } catch {
        // Server not ready yet
      }
      
      await new Promise(resolve => setTimeout(resolve, CONFIG.SERVER_HEALTH_CHECK_INTERVAL));
    }
    
    return false;
  }

  /**
   * Create a new preview window for a run
   */
  async createPreviewWindow(runId: string, projectPath?: string): Promise<PreviewWindow> {
    const sanitizedId = this.sanitizeRunId(runId);
    const targetPath = projectPath || this.projectPath;
    
    // Check limits
    if (this.windows.size >= CONFIG.MAX_WINDOWS) {
      throw new Error(`Maximum number of preview windows (${CONFIG.MAX_WINDOWS}) reached`);
    }
    
    // Check if already exists
    if (this.windows.has(sanitizedId)) {
      const existing = this.windows.get(sanitizedId)!;
      if (existing.status !== 'closed' && existing.status !== 'error') {
        // Focus the existing window
        if (!existing.window.isDestroyed()) {
          if (existing.window.isMinimized()) {
            existing.window.restore();
          }
          existing.window.show();
          existing.window.focus();
        }
        return existing;
      }
      // Clean up old entry
      await this.closePreview(sanitizedId);
    }
    
    const port = this.getNextPort();
    
    // Verify port is actually available
    if (await this.isPortInUse(port)) {
      throw new Error(`Port ${port} is already in use`);
    }
    
    // Create browser window
    const window = new BrowserWindow({
      width: 1024,
      height: 768,
      title: `Preview - Run ${sanitizedId}`,
      webPreferences: {
        nodeIntegration: false,
        contextIsolation: true,
        sandbox: true,
      },
      show: false,
      backgroundColor: '#1e1e1e',
    });
    
    const url = `http://localhost:${port}`;
    
    const preview: PreviewWindow = {
      runId: sanitizedId,
      window,
      port,
      devServer: null,
      url,
      status: 'starting',
    };
    
    this.windows.set(sanitizedId, preview);
    
    // Handle window close
    window.on('closed', () => {
      const currentPreview = this.windows.get(sanitizedId);
      if (currentPreview) {
        currentPreview.status = 'closed';
        // Kill dev server when window is closed
        if (currentPreview.devServer) {
          this.killProcess(currentPreview.devServer);
        }
      }
    });
    
    try {
      // Start dev server with specific CWD
      console.log(`[PreviewWindowManager] Starting dev server for run ${sanitizedId} from: ${targetPath}`);
      preview.devServer = await this.startDevServer(port, targetPath);
      
      // Wait for server to be ready
      const isReady = await this.waitForServer(url, CONFIG.SERVER_STARTUP_TIMEOUT);
      
      if (!isReady) {
        throw new Error(`Dev server failed to start within ${CONFIG.SERVER_STARTUP_TIMEOUT}ms`);
      }
      
      // Load URL and show window
      await window.loadURL(url);
      window.show();
      
      preview.status = 'ready';
      console.log(`[PreviewWindowManager] Created preview for run ${sanitizedId} on port ${port}`);
      
      return preview;
    } catch (error: any) {
      preview.status = 'error';
      preview.error = error.message;
      console.error(`[PreviewWindowManager] Failed to create preview:`, error);
      
      // Cleanup on failure
      if (preview.devServer) {
        this.killProcess(preview.devServer);
      }
      if (!window.isDestroyed()) {
        window.close();
      }
      
      throw error;
    }
  }

  /**
   * Detect the correct start command based on project files
   */
  private detectStartCommand(cwd: string, port: number): { command: string, args: string[] } {
    const { existsSync, readFileSync } = require('fs');
    const { join } = require('path');
    
    // 1. NodeJS (package.json)
    if (existsSync(join(cwd, 'package.json'))) {
      try {
        const pkg = JSON.parse(readFileSync(join(cwd, 'package.json'), 'utf-8'));
        const scripts = pkg.scripts || {};
        
        const npmCmd = process.platform === 'win32' ? 'npm.cmd' : 'npm';
        
        // Priority: dev -> start -> serve
        if (scripts.dev) {
            // Vite/Next/etc usually accept --port
            // Note: "--" is needed for npm to pass args to script
            return { command: npmCmd, args: ['run', 'dev', '--', '--port', String(port)] };
        }
        if (scripts.start) {
            return { command: npmCmd, args: ['run', 'start', '--', '--port', String(port)] };
        }
        return { command: npmCmd, args: ['run', 'dev'] }; // Fallback
      } catch (e) {
        console.warn('Failed to parse package.json:', e);
      }
    }
    
    // 2. Python (FastAPI/Flask)
    if (existsSync(join(cwd, 'requirements.txt')) || existsSync(join(cwd, 'pyproject.toml'))) {
       const hasMain = existsSync(join(cwd, 'main.py'));
       const hasApp = existsSync(join(cwd, 'app.py'));
       
       // Try Uvicorn (Standard for FastAPI)
       // We use 'python -m' to use the active environment python
       if (hasMain) {
           return { command: 'python', args: ['-m', 'uvicorn', 'main:app', '--reload', '--port', String(port)] };
       }
       // Try Flask
       if (hasApp) {
           return { command: 'python', args: ['-m', 'flask', 'run', '--port', String(port)] };
       }
    }
    
    // 3. Go
    if (existsSync(join(cwd, 'go.mod'))) {
        return { command: 'go', args: ['run', '.', '--port', String(port)] };
    }
    
    // Default fallback
    const defaultNpm = process.platform === 'win32' ? 'npm.cmd' : 'npm';
    return { command: defaultNpm, args: ['run', 'dev', '--', '--port', String(port)] };
  }

  /**
   * Start a dev server on the specified port
   */
  private async startDevServer(port: number, cwd: string): Promise<ChildProcess> {
    return new Promise((resolve, reject) => {
      try {
        const { command, args } = this.detectStartCommand(cwd, port);
        console.log(`[PreviewWindowManager] Detected command: ${command} ${args.join(' ')}`);

        const devServer = spawn(command, args, {
          cwd: cwd,
          shell: true,
          env: { 
            ...process.env, 
            PORT: String(port),
            BROWSER: 'none', // Prevent auto-opening browser
          },
          detached: false,
        });
        
        let hasOutput = false;
        
        devServer.stdout?.on('data', (data: Buffer) => {
          const output = data.toString();
          console.log(`[DevServer:${port}] ${output}`);
          
          // Resolve once we see the server is listening
          if (!hasOutput && (output.includes('ready') || output.includes('localhost'))) {
            hasOutput = true;
            resolve(devServer);
          }
        });
        
        devServer.stderr?.on('data', (data: Buffer) => {
          const output = data.toString();
          // Some dev servers output to stderr, don't treat as error
          if (!output.includes('error') && !output.includes('Error')) {
            console.log(`[DevServer:${port}] ${output}`);
          } else {
            console.error(`[DevServer:${port}] ${output}`);
          }
        });
        
        devServer.on('error', (error) => {
          console.error(`[DevServer:${port}] Process error:`, error);
          reject(error);
        });
        
        devServer.on('exit', (code) => {
          if (code !== 0 && !this.isShuttingDown) {
            console.error(`[DevServer:${port}] Exited with code ${code}`);
          }
        });
        
        // Timeout fallback - resolve anyway after a delay
        setTimeout(() => {
          if (!hasOutput) {
            resolve(devServer);
          }
        }, 3000);
        
      } catch (error) {
        reject(error);
      }
    });
  }

  /**
   * Kill a process gracefully
   */
  private killProcess(process: ChildProcess): void {
    if (!process.killed) {
      try {
        // Try graceful shutdown first
        if (globalThis.process?.platform === 'win32') {
          spawn('taskkill', ['/pid', String(process.pid), '/f', '/t']);
        } else {
          process.kill('SIGTERM');
          
          // Force kill after timeout
          setTimeout(() => {
            if (!process.killed) {
              process.kill('SIGKILL');
            }
          }, CONFIG.SHUTDOWN_TIMEOUT);
        }
      } catch (error) {
        console.warn('[PreviewWindowManager] Failed to kill process:', error);
      }
    }
  }

  /**
   * Get a preview window by run ID
   */
  getPreview(runId: string): PreviewWindow | undefined {
    return this.windows.get(this.sanitizeRunId(runId));
  }

  /**
   * Refresh a preview window
   */
  async refreshPreview(runId: string): Promise<void> {
    const sanitizedId = this.sanitizeRunId(runId);
    const preview = this.windows.get(sanitizedId);
    
    if (preview && preview.window && !preview.window.isDestroyed()) {
      preview.window.reload();
      console.log(`[PreviewWindowManager] Refreshed preview for run ${sanitizedId}`);
    } else {
      throw new Error(`No active preview window for run: ${sanitizedId}`);
    }
  }

  /**
   * Close a preview window and stop its dev server
   */
  async closePreview(runId: string): Promise<void> {
    const sanitizedId = this.sanitizeRunId(runId);
    const preview = this.windows.get(sanitizedId);
    
    if (!preview) return;
    
    preview.status = 'closed';
    
    // Kill dev server first
    if (preview.devServer) {
      this.killProcess(preview.devServer);
      preview.devServer = null;
    }
    
    // Close browser window
    if (preview.window && !preview.window.isDestroyed()) {
      preview.window.close();
    }
    
    this.windows.delete(sanitizedId);
    console.log(`[PreviewWindowManager] Closed preview for run ${sanitizedId}`);
  }

  /**
   * Close all preview windows
   */
  async closeAllPreviews(): Promise<void> {
    const runIds = Array.from(this.windows.keys());
    
    await Promise.all(runIds.map(runId => this.closePreview(runId)));
  }

  /**
   * Get all active preview windows
   */
  getActivePreviews(): PreviewWindow[] {
    return Array.from(this.windows.values()).filter(p => 
      p.status === 'ready' || p.status === 'starting'
    );
  }

  /**
   * Get preview count
   */
  getPreviewCount(): number {
    return this.windows.size;
  }
}
