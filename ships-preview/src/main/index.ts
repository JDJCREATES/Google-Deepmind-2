import { app, BrowserWindow, ipcMain, dialog } from 'electron';
import { join } from 'path';
import { existsSync, statSync } from 'fs';
import Store from 'electron-store';

let mainWindow: BrowserWindow | null = null;

// Persistent storage for project settings
const store = new Store({
  name: 'ships-preview-config',
  schema: {
    lastProjectPath: {
      type: 'string',
      default: ''
    }
  }
});

function createWindow() {
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
  const lastPath = store.get('lastProjectPath') as string;
  
  if (lastPath && isValidProjectPath(lastPath)) {
    return { path: lastPath, exists: true };
  }
  
  return { path: null, exists: false };
});

/**
 * Select a project folder
 */
ipcMain.handle('select-project-folder', async () => {
  const result = await dialog.showOpenDialog(mainWindow!, {
    properties: ['openDirectory'],
    title: 'Select Project Folder',
    buttonLabel: 'Select Folder'
  });
  
  if (result.canceled || !result.filePaths.length) {
    return { success: false, path: null };
  }
  
  const selectedPath = result.filePaths[0];
  
  // Validate the path
  if (!isValidProjectPath(selectedPath)) {
    return { 
      success: false, 
      path: null, 
      error: 'Invalid or inaccessible directory' 
    };
  }
  
  // Store it securely
  store.set('lastProjectPath', selectedPath);
  
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
