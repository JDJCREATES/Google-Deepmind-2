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
    openExternal: (url: string) => ipcRenderer.invoke('open-external', url),
    
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
     * Generate all project artifacts (file_tree, dependency_graph, security)
     */
    generateArtifacts: () => ipcRenderer.invoke('artifacts:generate'),
    
    /**
     * Get artifact generation status
     */
    getArtifactStatus: () => ipcRenderer.invoke('artifacts:status'),
    
    /**
     * Get file tree artifact with symbols
     */
    getFileTree: () => ipcRenderer.invoke('artifacts:getFileTree'),
    
    /**
     * Get dependency graph artifact
     */
    getDependencyGraph: () => ipcRenderer.invoke('artifacts:getDependencyGraph'),
    
    /**
     * Get security report artifact
     */
    getSecurityReport: () => ipcRenderer.invoke('artifacts:getSecurityReport'),
    
    /**
     * Build LLM context for specific files
     */
    buildArtifactContext: (scopeFiles: string[]) => 
        ipcRenderer.invoke('artifacts:buildContext', scopeFiles),
    
    /**
     * Get artifacts summary for API requests
     */
    getArtifactsSummary: () => ipcRenderer.invoke('artifacts:getSummary'),
    
    /**
     * Listen for artifact update events
     */
    onArtifactsUpdated: (callback: () => void) => {
        const listener = () => callback();
        ipcRenderer.on('artifacts:updated', listener);
        return () => ipcRenderer.removeListener('artifacts:updated', listener);
    },
    
    // === Agent Runs ===
    /**
     * Create a new git branch for a run
     */
    createRunBranch: (runId: string, prompt: string) =>
        ipcRenderer.invoke('runs:createBranch', { runId, prompt }),
    
    /**
     * Switch to a run's git branch
     */
    switchRunBranch: (runId: string) =>
        ipcRenderer.invoke('runs:switchBranch', { runId }),
    
    /**
     * Delete a run's git branch
     */
    deleteRunBranch: (runId: string) =>
        ipcRenderer.invoke('runs:deleteBranch', { runId }),
    
    /**
     * Create a checkpoint (commit) on current branch
     */
    createRunCheckpoint: (message: string) =>
        ipcRenderer.invoke('runs:createCheckpoint', { message }),
    
    /**
     * Rollback to a specific commit
     */
    rollbackRun: (commitHash: string) =>
        ipcRenderer.invoke('runs:rollback', { commitHash }),
    
    /**
     * Create a preview window for a run
     */
    createRunPreview: (runId: string, projectPath?: string) =>
        ipcRenderer.invoke('runs:createPreview', { runId, projectPath }),
    
    /**
     * Refresh a run's preview window
     */
    refreshRunPreview: (runId: string) =>
        ipcRenderer.invoke('runs:refreshPreview', { runId }),
    
    /**
     * Close a run's preview window
     */
    closeRunPreview: (runId: string) =>
        ipcRenderer.invoke('runs:closePreview', { runId }),
    
    /**
     * Get all active preview windows
     */
    getActiveRunPreviews: () =>
        ipcRenderer.invoke('runs:getActivePreviews'),
    
    /**
     * Capture a screenshot of a run's preview
     */
    captureRunScreenshot: (runId: string, agentPhase: string, description?: string) =>
        ipcRenderer.invoke('runs:captureScreenshot', { runId, agentPhase, description }),
    
    /**
     * Get all screenshots for a run
     */
    getRunScreenshots: (runId: string) =>
        ipcRenderer.invoke('runs:getScreenshots', { runId }),
    
    /**
     * Delete all screenshots for a run
     */
    deleteRunScreenshots: (runId: string) =>
        ipcRenderer.invoke('runs:deleteScreenshots', { runId }),
});
