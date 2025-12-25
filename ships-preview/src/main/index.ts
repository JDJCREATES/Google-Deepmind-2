import { app, BrowserWindow, ipcMain } from 'electron';
import { join } from 'path';

let mainWindow: BrowserWindow | null = null;

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

// Build Logic Placeholder
ipcMain.handle('run-build', async (_event, projectPath) => {
    console.log('Building project at:', projectPath);
    // TODO: Implement build logic
    return { success: true, message: 'Build started' };
});
