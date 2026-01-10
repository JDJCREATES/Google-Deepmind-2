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
    
    // === PTY (Interactive Terminal) ===
    /**
     * Spawn a new PTY session in the project directory.
     */
    ptySpawn: (projectPath: string, options?: { cols?: number; rows?: number }) =>
        ipcRenderer.invoke('pty-spawn', projectPath, options),
    
    /**
     * Write data to a PTY session.
     */
    ptyWrite: (sessionId: string, data: string) =>
        ipcRenderer.invoke('pty-write', sessionId, data),
    
    /**
     * Resize a PTY session.
     */
    ptyResize: (sessionId: string, cols: number, rows: number) =>
        ipcRenderer.invoke('pty-resize', sessionId, cols, rows),
    
    /**
     * Kill a PTY session.
     */
    ptyKill: (sessionId: string) =>
        ipcRenderer.invoke('pty-kill', sessionId),
    
    /**
     * Listen for PTY data output.
     */
    onPTYData: (callback: (event: { sessionId: string; data: string }) => void) => {
        const listener = (_: any, event: { sessionId: string; data: string }) => callback(event);
        ipcRenderer.on('pty-data', listener);
        return () => ipcRenderer.removeListener('pty-data', listener);
    },
    
    /**
     * Listen for PTY exit events.
     */
    onPTYExit: (callback: (event: { sessionId: string; exitCode: number }) => void) => {
        const listener = (_: any, event: { sessionId: string; exitCode: number }) => callback(event);
        ipcRenderer.on('pty-exit', listener);
        return () => ipcRenderer.removeListener('pty-exit', listener);
    },
    
    // === Preview ===
    /**
     * Open a preview URL in the preview panel.
     */
    openPreview: (url: string) => ipcRenderer.invoke('open-preview', url),
    
    /**
     * Listen for preview URL events from main process.
     */
    onPreviewUrl: (callback: (url: string) => void) => {
        const listener = (_: any, url: string) => callback(url);
        ipcRenderer.on('preview-url', listener);
        return () => ipcRenderer.removeListener('preview-url', listener);
    },
    
    /**
     * Listen for preview URL events from ships:// protocol handler.
     */
    onOpenPreviewUrl: (callback: (url: string) => void) => {
        const listener = (_: any, url: string) => callback(url);
        ipcRenderer.on('open-preview-url', listener);
        return () => ipcRenderer.removeListener('open-preview-url', listener);
    },

    // Window Management
    focusWindow: () => ipcRenderer.invoke('focus-window'),
    
    // === Artifacts ===
    /**
     * Generate all project artifacts (file_tree, dependency_graph, etc.)
     */
    generateArtifacts: () => ipcRenderer.invoke('artifacts:generate'),
    
    /**
     * Get file tree artifact with symbols
     */
    getFileTree: () => ipcRenderer.invoke('artifacts:getFileTree'),
    
    /**
     * Get dependency graph artifact
     */
    getDependencyGraph: () => ipcRenderer.invoke('artifacts:getDependencyGraph'),
    
    /**
     * Build LLM context for specific files
     */
    buildArtifactContext: (scopeFiles: string[]) => 
        ipcRenderer.invoke('artifacts:buildContext', scopeFiles),
    
    /**
     * Get artifacts summary for API requests
     */
    getArtifactsSummary: () => ipcRenderer.invoke('artifacts:getSummary'),
});
