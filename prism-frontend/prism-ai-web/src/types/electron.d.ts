
export {};

declare global {
  interface Window {
    electronAPI?: {
      openPreview: (url: string) => void;
    };
    electron?: {
      // Project Management
      getLastProject: () => Promise<{ path: string | null; exists: boolean }>;
      selectProjectFolder: () => Promise<{ success: boolean; path: string | null; error?: string }>;
      openPreview: (url: string) => Promise<{ success: boolean; error?: string }>;

      // PTY / Terminal
      ptySpawn: (projectPath: string, options?: { cols?: number; rows?: number }) => Promise<{ sessionId: string } | { error: string }>;
      ptyWrite: (sessionId: string, data: string) => Promise<boolean>;
      ptyResize: (sessionId: string, cols: number, rows: number) => Promise<boolean>;
      ptyKill: (sessionId: string) => Promise<boolean>;
      onPTYData: (callback: (event: { sessionId: string; data: string }) => void) => () => void;
      onPTYExit: (callback: (event: { sessionId: string; exitCode: number }) => void) => () => void;

      // Agent Runs - Branch Management
      createRunBranch: (runId: string, prompt: string) => Promise<{ success: boolean; branch?: any; error?: string }>;
      switchRunBranch: (runId: string) => Promise<{ success: boolean; error?: string }>;
      getRunBranch: (runId: string) => Promise<{ success: boolean; branch?: any; error?: string }>;
      deleteRunBranch: (runId: string) => Promise<{ success: boolean; error?: string }>;
      createRunCheckpoint: (message: string) => Promise<{ success: boolean; commitHash?: string; error?: string }>;
      rollbackRunBranch: (commitHash: string) => Promise<{ success: boolean; error?: string }>;

      // Agent Runs - Preview Management
      createRunPreview: (runId: string, projectPath?: string) => Promise<{ success: boolean; preview?: any; error?: string }>;
      getActiveRunPreviews: () => Promise<{ success: boolean; previews?: any[]; error?: string }>;
      refreshRunPreview: (runId: string) => Promise<{ success: boolean; error?: string }>;
      closeRunPreview: (runId: string) => Promise<{ success: boolean; error?: string }>;

      // Agent Runs - Screenshots
      captureRunScreenshot: (runId: string, commitHash: string, agentPhase: string, description?: string) => Promise<{ success: boolean; screenshot?: any; error?: string }>;
      getRunScreenshots: (runId: string) => Promise<{ success: boolean; screenshots?: any[]; error?: string }>;
      deleteRunScreenshots: (runId: string) => Promise<{ success: boolean; error?: string }>;
    };
  }
}
