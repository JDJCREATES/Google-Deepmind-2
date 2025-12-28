import { contextBridge, ipcRenderer } from 'electron';

// Terminal stream event type
export interface TerminalOutputEvent {
    type: 'stdout' | 'stderr' | 'exit' | 'error';
    data: string;
    timestamp: number;
}

contextBridge.exposeInMainWorld('electron', {
    // === Project Management ===
    selectProjectFolder: () => ipcRenderer.invoke('select-project-folder'),
    getLastProject: () => ipcRenderer.invoke('get-last-project'),
    clearProject: () => ipcRenderer.invoke('clear-project'),
    
    // === Build (Legacy) ===
    runBuild: (projectPath: string) => ipcRenderer.invoke('run-build', projectPath),
    onLog: (callback: (log: string) => void) => ipcRenderer.on('build-log', (_event, log) => callback(log)),
    
    // === Terminal Execution ===
    /**
     * Get list of allowed command prefixes.
     */
    getAllowedCommands: () => ipcRenderer.invoke('get-allowed-commands'),
    
    /**
     * Validate a command without executing it.
     */
    validateCommand: (command: string, cwd: string) => 
        ipcRenderer.invoke('validate-command', command, cwd),
    
    /**
     * Run a command and get the full result.
     */
    runCommand: (command: string, cwd: string, timeout?: number) => 
        ipcRenderer.invoke('run-command', command, cwd, timeout),
    
    /**
     * Run a command with streaming output.
     * Use onTerminalOutput to receive stream events.
     */
    runCommandStream: (command: string, cwd: string, timeout?: number) => 
        ipcRenderer.invoke('run-command-stream', command, cwd, timeout),
    
    /**
     * Listen for terminal output events during streaming.
     */
    onTerminalOutput: (callback: (event: TerminalOutputEvent) => void) => {
        const listener = (_: any, event: TerminalOutputEvent) => callback(event);
        ipcRenderer.on('terminal-output', listener);
        // Return cleanup function
        return () => ipcRenderer.removeListener('terminal-output', listener);
    },
});
