import { app, BrowserWindow, ipcMain, dialog } from 'electron';
import { join } from 'path';
import { existsSync, statSync } from 'fs';

console.log("-----------------------------------------");
console.log(" MAIN PROCESS STARTING");
console.log("-----------------------------------------");

// Use require for CJS compatibility
const Store = require('electron-store');

// Register ships:// as a custom protocol for deep linking
if (process.defaultApp) {
  if (process.argv.length >= 2) {
    app.setAsDefaultProtocolClient('ships', process.execPath, [process.argv[1]]);
  }
} else {
  app.setAsDefaultProtocolClient('ships');
}

// Persistent storage for project settings
let store: any;
try {
    store = new Store({
      name: 'ships-preview-config',
      schema: {
        lastProjectPath: {
          type: 'string',
          default: ''
        }
      }
    });
    console.log("✅ Store initialized successfully");
} catch (e) {
    console.error("❌ Failed to initialize Store:", e);
}

let mainWindow: BrowserWindow | null = null;

function createWindow() {
  console.log("Creating window...");
  mainWindow = new BrowserWindow({
    width: 1000,
    height: 800,
    webPreferences: {
      preload: join(__dirname, '../preload/index.js'),
      nodeIntegration: false,
      contextIsolation: true,
    },
    titleBarStyle: 'hidden',
    titleBarOverlay: {
        color: '#252526',
        symbolColor: '#cccccc',
        height: 35
    }
  });

  if (process.env.NODE_ENV === 'development') {
    mainWindow.loadURL('http://localhost:5177');
    mainWindow.webContents.openDevTools();
  } else {
    mainWindow.loadFile(join(__dirname, '../renderer/index.html'));
  }
}

app.whenReady().then(() => {
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

// Handle protocol on Windows/Linux (second-instance)
const gotTheLock = app.requestSingleInstanceLock();
if (!gotTheLock) {
  app.quit();
} else {
  app.on('second-instance', (_event, commandLine) => {
    // Someone tried to run a second instance, focus our window
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.focus();
    }
    // Handle the protocol URL (last arg is the deep link)
    const url = commandLine.find(arg => arg.startsWith('ships://'));
    if (url) {
      console.log('Deep link received:', url);
      // Could parse url and take action here
    }
  });
}

// Handle protocol on macOS
app.on('open-url', (_event, url) => {
  console.log('Open URL received (macOS):', url);
  if (mainWindow) {
    mainWindow.focus();
  }
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

// ============================================================================
// PROJECT MANAGEMENT
// ============================================================================

/**
 * Validate that a path is safe and accessible
 */
function isValidProjectPath(path: string): boolean {
  if (!path || typeof path !== 'string') return false;
  
  try {
    // Check path exists
    if (!existsSync(path)) return false;
    
    // Check it's a directory
    const stats = statSync(path);
    if (!stats.isDirectory()) return false;
    
    // Security: Don't allow system directories
    const normalizedPath = path.toLowerCase();
    const forbidden = [
      'c:\\windows',
      'c:\\program files',
      'c:\\programdata',
      '/system',
      '/usr/bin',
      '/bin'
    ];
    
    if (forbidden.some(f => normalizedPath.startsWith(f))) {
      return false;
    }
    
    return true;
  } catch (error) {
    console.error('Path validation error:', error);
    return false;
  }
}

/**
 * Get the last used project path (if valid)
 */
ipcMain.handle('get-last-project', async () => {
  console.log("IPC: get-last-project called");
  if (!store) {
      console.error("Store not initialized");
      return { path: null, exists: false };
  }
  const lastPath = store.get('lastProjectPath') as string;
  console.log("Last path in store:", lastPath);
  
  if (lastPath && isValidProjectPath(lastPath)) {
    return { path: lastPath, exists: true };
  }
  
  return { path: null, exists: false };
});

/**
 * Select a project folder
 */
ipcMain.handle('select-project-folder', async () => {
  console.log("IPC: select-project-folder called");
  const result = await dialog.showOpenDialog(mainWindow!, {
    properties: ['openDirectory'],
    title: 'Select Project Folder',
    buttonLabel: 'Select Folder'
  });
  
  if (result.canceled || !result.filePaths.length) {
    console.log("Selection canceled");
    return { success: false, path: null };
  }
  
  const selectedPath = result.filePaths[0];
  console.log("Selected path:", selectedPath);
  
  // Validate the path
  if (!isValidProjectPath(selectedPath)) {
    console.error("Invalid path selected");
    return { 
      success: false, 
      path: null, 
      error: 'Invalid or inaccessible directory' 
    };
  }
  
  // Store it securely
  if (store) {
      store.set('lastProjectPath', selectedPath);
      console.log("Path stored");
  }
  
  return { success: true, path: selectedPath };
});

/**
 * Clear the stored project (logout)
 */
ipcMain.handle('clear-project', async () => {
  store.delete('lastProjectPath');
  return { success: true };
});

// Build Logic Placeholder
ipcMain.handle('run-build', async (_event, projectPath) => {
  console.log('Building project at:', projectPath);
  // TODO: Implement build logic
  return { success: true, message: 'Build started' };
});

// ============================================================================
// TERMINAL EXECUTION
// ============================================================================

import { 
  executeCommand, 
  executeCommandWithStream,
  validateCommand,
  ALLOWED_COMMANDS,
  killAllProcesses 
} from './terminal';

/**
 * Get list of allowed commands for the frontend.
 */
ipcMain.handle('get-allowed-commands', async () => {
  return ALLOWED_COMMANDS.map(c => ({
    prefix: c.prefix,
    description: c.description,
    requiresApproval: c.requiresApproval,
  }));
});

/**
 * Validate a command without executing it.
 */
ipcMain.handle('validate-command', async (_event, command: string, cwd: string) => {
  return validateCommand(command, cwd);
});

/**
 * Execute a terminal command in the project directory.
 * Returns the full result after completion.
 */
ipcMain.handle('run-command', async (_event, command: string, cwd: string, timeout?: number) => {
  console.log(`[TERMINAL] Running command: ${command}`);
  console.log(`[TERMINAL] CWD: ${cwd}`);
  
  const result = await executeCommand({ command, cwd, timeout });
  
  console.log(`[TERMINAL] Exit code: ${result.exitCode}`);
  if (!result.success) {
    console.log(`[TERMINAL] Error: ${result.error || result.stderr}`);
  }
  
  return result;
});

/**
 * Execute a terminal command with streaming output.
 * Sends events to the renderer as they happen.
 */
ipcMain.handle('run-command-stream', async (_event, command: string, cwd: string, timeout?: number) => {
  console.log(`[TERMINAL] Streaming command: ${command}`);
  
  const result = await executeCommandWithStream(
    { command, cwd, timeout },
    (event) => {
      // Send streaming events to renderer
      if (mainWindow) {
        mainWindow.webContents.send('terminal-output', event);
      }
    }
  );
  
  return result;
});

// Cleanup on app quit
app.on('before-quit', () => {
  console.log('[TERMINAL] Killing all processes...');
  killAllProcesses();
});
