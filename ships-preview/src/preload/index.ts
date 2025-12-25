import { contextBridge, ipcRenderer } from 'electron';

contextBridge.exposeInMainWorld('electron', {
    runBuild: (projectPath: string) => ipcRenderer.invoke('run-build', projectPath),
    onLog: (callback: (log: string) => void) => ipcRenderer.on('build-log', (_event, log) => callback(log))
});
