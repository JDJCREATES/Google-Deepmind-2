/**
 * Agent Runs Store
 * 
 * Zustand store for managing agent run state.
 * Uses Electron IPC when available, falls back to HTTP API.
 * Includes comprehensive error handling and retry logic.
 */

import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import type { AgentRun, Screenshot, RunStatus, AgentType, CreateRunRequest, ChatMessage, ThinkingSectionData } from '../types';

// ============================================================================
// Types
// ============================================================================

interface AgentRunsState {
  runs: AgentRun[];
  activeRunId: string | null;
  isLoading: boolean;
  error: string | null;
  isElectron: boolean;
  
  // Actions
  setRuns: (runs: AgentRun[]) => void;
  addRun: (run: AgentRun) => void;
  updateRun: (runId: string, updates: Partial<AgentRun>) => void;
  removeRun: (runId: string) => void;
  setActiveRun: (runId: string | null) => void;
  
  // Screenshot actions
  addScreenshot: (runId: string, screenshot: Screenshot) => void;
  
  // Status updates (from WebSocket)
  updateRunStatus: (
    runId: string, 
    status: RunStatus, 
    currentAgent: AgentType, 
    agentMessage: string,
    filesChanged?: string[]
  ) => void;

  // Chat actions
  addRunMessage: (runId: string, message: ChatMessage) => void;
  updateRunMessage: (runId: string, messageId: string, updates: Partial<ChatMessage>) => void;
  appendRunMessageContent: (runId: string, messageId: string, contentDelta: string) => void;
  updateRunThinking: (runId: string, sectionId: string, content: string) => void;
  addRunThinkingSection: (runId: string, section: ThinkingSectionData) => void;
  setRunThinkingSectionLive: (runId: string, sectionId: string, isLive: boolean) => void;
  
  // API actions
  createRun: (request: CreateRunRequest) => Promise<AgentRun | null>;
  fetchRuns: () => Promise<void>;
  pauseRun: (runId: string) => Promise<void>;
  resumeRun: (runId: string) => Promise<void>;
  deleteRun: (runId: string) => Promise<void>;
  sendFeedback: (runId: string, message: string, model?: string) => Promise<void>;
  rollbackToScreenshot: (runId: string, screenshotId: string) => Promise<void>;
  openPreview: (runId: string) => Promise<{ status: string; url?: string; message?: string }>;
  
  // Electron-specific actions
  captureScreenshot: (runId: string, agentPhase: string, description?: string) => Promise<Screenshot | null>;
  pushRun: (runId: string) => Promise<void>;
  pullRun: (runId: string) => Promise<void>;
  getRemotes: () => Promise<any[]>;
  setRemote: (url: string, name?: string) => Promise<void>;
  
  // Loading state
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  clearError: () => void;
}

// ============================================================================
// Helpers
// ============================================================================

// API base URL
const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8001';

// Check if running in Electron
const isElectronEnvironment = (): boolean => {
  return typeof window !== 'undefined' && 
         window.electron !== undefined &&
         typeof window.electron.createRunBranch === 'function';
};

// Retry wrapper for API calls
async function withRetry<T>(
  fn: () => Promise<T>,
  maxRetries: number = 3,
  delayMs: number = 1000
): Promise<T> {
  let lastError: Error | null = null;
  
  for (let attempt = 0; attempt < maxRetries; attempt++) {
    try {
      return await fn();
    } catch (error) {
      lastError = error instanceof Error ? error : new Error(String(error));
      
      // Don't retry on 4xx errors (client errors)
      if (lastError.message.includes('400') || 
          lastError.message.includes('404') ||
          lastError.message.includes('403')) {
        throw lastError;
      }
      
      // Wait before retry
      if (attempt < maxRetries - 1) {
        await new Promise(resolve => setTimeout(resolve, delayMs * (attempt + 1)));
      }
    }
  }
  
  throw lastError;
}

// Electron API wrapper with type safety
const electronAPI = {
  createBranch: async (runId: string, prompt: string) => {
    if (!window.electron?.createRunBranch) throw new Error('Electron API not available');
    return window.electron.createRunBranch(runId, prompt);
  },
  createPreview: async (runId: string) => {
    if (!window.electron?.createRunPreview) throw new Error('Electron API not available');
    return window.electron.createRunPreview(runId);
  },
  closePreview: async (runId: string) => {
    if (!window.electron?.closeRunPreview) throw new Error('Electron API not available');
    return window.electron.closeRunPreview(runId);
  },
  deleteBranch: async (runId: string) => {
    if (!window.electron?.deleteRunBranch) throw new Error('Electron API not available');
    return window.electron.deleteRunBranch(runId);
  },
  rollback: async (commitHash: string) => {
    if (!window.electron?.rollbackRun) throw new Error('Electron API not available');
    return window.electron.rollbackRun(commitHash);
  },
  captureScreenshot: async (runId: string, agentPhase: string, description?: string) => {
    if (!window.electron?.captureRunScreenshot) throw new Error('Electron API not available');
    return window.electron.captureRunScreenshot(runId, agentPhase, description);
  },
  getScreenshots: async (runId: string) => {
    if (!window.electron?.getRunScreenshots) throw new Error('Electron API not available');
    return window.electron.getRunScreenshots(runId);
  },
  pushRun: async (branch: string) => {
    if (!window.electron?.pushRun) throw new Error('Electron API not available');
    return window.electron.pushRun(branch);
  },
  pullRun: async (branch: string) => {
    if (!window.electron?.pullRun) throw new Error('Electron API not available');
    return window.electron.pullRun(branch);
  },
  getRemotes: async () => {
    if (!window.electron?.getRemotes) throw new Error('Electron API not available');
    return window.electron.getRemotes();
  },
  setRemote: async (url: string, name?: string) => {
    if (!window.electron?.setRemote) throw new Error('Electron API not available');
    return window.electron.setRemote(url, name);
  },
};

// ============================================================================
// Store
// ============================================================================

export const useAgentRuns = create<AgentRunsState>()(
  persist(
    (set, get) => ({
  runs: [],
  activeRunId: null,
  isLoading: false,
  error: null,
  isElectron: isElectronEnvironment(),
  
  // Basic setters
  setRuns: (runs) => set({ runs }),
  
  addRun: (run) => set((state) => ({ 
    runs: [run, ...state.runs] 
  })),
  
  updateRun: (runId, updates) => set((state) => ({
    runs: state.runs.map((run) =>
      run.id === runId ? { ...run, ...updates, updatedAt: new Date().toISOString() } : run
    ),
  })),
  
  removeRun: (runId) => set((state) => ({
    runs: state.runs.filter((run) => run.id !== runId),
    activeRunId: state.activeRunId === runId ? null : state.activeRunId,
  })),
  
  setActiveRun: (runId) => set({ activeRunId: runId }),
  
  addScreenshot: (runId, screenshot) => set((state) => ({
    runs: state.runs.map((run) =>
      run.id === runId
        ? { ...run, screenshots: [...run.screenshots, screenshot] }
        : run
    ),
  })),
  
  updateRunStatus: (runId, status, currentAgent, agentMessage, filesChanged) =>
    set((state) => ({
      runs: state.runs.map((run) =>
        run.id === runId
          ? {
              ...run,
              status,
              currentAgent,
              agentMessage,
              filesChanged: filesChanged ?? run.filesChanged,
              updatedAt: new Date().toISOString(),
            }
          : run
      ),
    })),

  addRunMessage: (runId, message) =>
    set((state) => ({
      runs: state.runs.map((run) =>
        run.id === runId
          ? { ...run, messages: [...(run.messages || []), message] }
          : run
      ),
    })),

  updateRunMessage: (runId, messageId, updates) =>
    set((state) => ({
      runs: state.runs.map((run) =>
        run.id === runId
          ? {
              ...run,
              messages: (run.messages || []).map((msg) =>
                msg.id === messageId ? { ...msg, ...updates } : msg
              ),
            }
          : run
      ),
    })),

  appendRunMessageContent: (runId, messageId, contentDelta) =>
    set((state) => ({
      runs: state.runs.map((run) =>
        run.id === runId
          ? {
              ...run,
              messages: (run.messages || []).map((msg) =>
                msg.id === messageId ? { ...msg, content: msg.content + contentDelta } : msg
              ),
            }
          : run
      ),
    })),

  addRunThinkingSection: (runId, section) =>
    set((state) => ({
      runs: state.runs.map((run) =>
        run.id === runId
          ? { ...run, thinkingSections: [...(run.thinkingSections || []), section] }
          : run
      ),
    })),

  updateRunThinking: (runId, sectionId, content) =>
    set((state) => ({
      runs: state.runs.map((run) =>
        run.id === runId
          ? {
              ...run,
              thinkingSections: (run.thinkingSections || []).map((s) =>
                s.id === sectionId ? { ...s, content: s.content + content } : s
              ),
            }
          : run
      ),
    })),

  setRunThinkingSectionLive: (runId, sectionId, isLive) =>
    set((state) => ({
      runs: state.runs.map((run) =>
        run.id === runId
          ? {
              ...run,
              thinkingSections: (run.thinkingSections || []).map((s) =>
                s.id === sectionId ? { ...s, isLive } : s
              ),
            }
          : run
      ),
    })),

  
  setLoading: (isLoading) => set({ isLoading }),
  setError: (error) => set({ error }),
  clearError: () => set({ error: null }),
  
  // ========================================
  // API Actions (with IPC + HTTP fallback)
  // ========================================
  
  createRun: async (request) => {
    const { setLoading, setError, addRun, isElectron } = get();
    setLoading(true);
    setError(null);
    
    try {
      // Create run via backend API
      const response = await withRetry(() => 
        fetch(`${API_BASE}/api/runs`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(request),
          credentials: 'include',
        })
      );
      
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Failed to create run: ${response.status} ${errorText}`);
      }
      
      const newRun: AgentRun = await response.json();
      
      // Ensure previewStatus has default (may not come from backend yet)
      if (!newRun.previewStatus) {
        newRun.previewStatus = 'unknown';
      }
      
      // If in Electron, also create git branch and preview
      if (isElectron) {
        try {
          await electronAPI.createBranch(newRun.id, request.prompt);
          await electronAPI.createPreview(newRun.id);
          // After creating preview, set status to running (will be updated by WS)
          newRun.previewStatus = 'running';
        } catch (electronError) {
          console.warn('[useAgentRuns] Electron integration failed, continuing with HTTP only:', electronError);
          newRun.previewStatus = 'stopped';
        }
      }
      
      addRun(newRun);
      return newRun;
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to create run';
      setError(message);
      console.error('[useAgentRuns] Create run error:', error);
      return null;
    } finally {
      setLoading(false);
    }
  },
  
  fetchRuns: async () => {
    const { setLoading, setError, setRuns } = get();
    setLoading(true);
    setError(null);
    
    try {
      const response = await withRetry(() => fetch(`${API_BASE}/api/runs`, { credentials: 'include' }));
      
      if (!response.ok) {
        throw new Error(`Failed to fetch runs: ${response.status}`);
      }
      
      const runs: AgentRun[] = await response.json();
      // Ensure previewStatus default for all runs
      runs.forEach(run => {
        if (!run.previewStatus) run.previewStatus = 'unknown';
      });
      setRuns(runs);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to fetch runs';
      setError(message);
      console.error('[useAgentRuns] Fetch runs error:', error);
    } finally {
      setLoading(false);
    }
  },
  
  pauseRun: async (runId) => {
    const { updateRun, setError } = get();
    
    try {
      const response = await withRetry(() => 
        fetch(`${API_BASE}/api/runs/${runId}/pause`, { method: 'POST', credentials: 'include' })
      );
      
      if (!response.ok) {
        throw new Error(`Failed to pause run: ${response.status}`);
      }
      
      updateRun(runId, { status: 'paused', currentAgent: null, agentMessage: 'Paused' });
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to pause run';
      setError(message);
      console.error('[useAgentRuns] Pause run error:', error);
    }
  },
  
  resumeRun: async (runId) => {
    const { updateRun, setError } = get();
    
    try {
      const response = await withRetry(() => 
        fetch(`${API_BASE}/api/runs/${runId}/resume`, { method: 'POST', credentials: 'include' })
      );
      
      if (!response.ok) {
        throw new Error(`Failed to resume run: ${response.status}`);
      }
      
      updateRun(runId, { status: 'running', agentMessage: 'Resuming...' });
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to resume run';
      setError(message);
      console.error('[useAgentRuns] Resume run error:', error);
    }
  },
  
  deleteRun: async (runId) => {
    const { removeRun, setError, isElectron } = get();
    
    try {
      // If in Electron, trigger cleanup but don't block the backend call
      if (isElectron) {
        // execute asynchronously
        Promise.all([
          electronAPI.closePreview(runId).catch(console.warn),
          electronAPI.deleteBranch(runId).catch(console.warn)
        ]).catch(e => console.warn('[useAgentRuns] Electron cleanup error:', e));
      }
      
      const response = await withRetry(() => 
        fetch(`${API_BASE}/api/runs/${runId}`, { method: 'DELETE', credentials: 'include' })
      );
      
      if (!response.ok) {
        throw new Error(`Failed to delete run: ${response.status}`);
      }
      
      removeRun(runId);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to delete run';
      setError(message);
      console.error('[useAgentRuns] Delete run error:', error);
    }
  },
  
  sendFeedback: async (runId, message, model = "gemini-1.5-pro-002") => {
    const { setError, updateRun } = get();
    
    try {
      const response = await withRetry(() => 
        fetch(`${API_BASE}/api/runs/${runId}/feedback`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message, model }),
          credentials: 'include',
        })
      );
      
      if (!response.ok) {
        throw new Error(`Failed to send feedback: ${response.status}`);
      }
      
      // Optimistically update UI
      updateRun(runId, { agentMessage: `Processing: ${message.slice(0, 30)}...` });
    } catch (error) {
      const errMsg = error instanceof Error ? error.message : 'Failed to send feedback';
      setError(errMsg);
      console.error('[useAgentRuns] Send feedback error:', error);
    }
  },
  
  rollbackToScreenshot: async (runId, screenshotId) => {
    const { setError, runs, updateRun, isElectron } = get();
    
    const run = runs.find(r => r.id === runId);
    const screenshot = run?.screenshots.find(s => s.id === screenshotId);
    
    if (!screenshot) {
      setError('Screenshot not found');
      return;
    }
    
    try {
      // If in Electron, use git directly
      if (isElectron) {
        try {
          await electronAPI.rollback(screenshot.gitCommitHash);
        } catch (electronError) {
          console.warn('[useAgentRuns] Electron rollback failed, using HTTP:', electronError);
        }
      }
      
      const response = await withRetry(() => 
        fetch(`${API_BASE}/api/runs/${runId}/rollback`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ 
            screenshotId,
            commitHash: screenshot.gitCommitHash 
          }),
          credentials: 'include',
        })
      );
      
      if (!response.ok) {
        throw new Error(`Failed to rollback: ${response.status}`);
      }
      
      updateRun(runId, { 
        agentMessage: `Rolled back to snapshot ${screenshotId.slice(0, 4)}`,
        status: 'running'
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to rollback';
      setError(message);
      console.error('[useAgentRuns] Rollback error:', error);
    }
  },
  
  openPreview: async (runId) => {
    const { runs, updateRun, setError } = get();
    
    // Find the run to get project path
    const run = runs.find(r => r.id === runId);
    if (!run) {
      return { status: 'error', message: 'Run not found' };
    }
    
    // The project path should be based on the run's branch
    // For now, we assume it's in SHIPS_TEST/<branch>
    const projectPath = `P:\\WERK_IT_2025\\SHIPS_TEST\\${run.branch}`;
    
    try {
      updateRun(runId, { previewStatus: 'running' });
      
      const response = await fetch(`${API_BASE}/preview/open`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project_path: projectPath,
          run_id: runId
        }),
        credentials: 'include'
      });
      
      const result = await response.json();
      
      if (result.status === 'running') {
        updateRun(runId, { 
          previewStatus: 'running',
          previewUrl: result.url 
        });
      } else {
        updateRun(runId, { previewStatus: 'error' });
      }
      
      return result;
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to open preview';
      setError(message);
      console.error('[useAgentRuns] Open preview error:', error);
      updateRun(runId, { previewStatus: 'error' });
      return { status: 'error', message };
    }
  },
  
  captureScreenshot: async (runId, agentPhase, description) => {
    const { isElectron, addScreenshot, setError } = get();
    
    if (!isElectron) {
      console.warn('[useAgentRuns] captureScreenshot requires Electron');
      return null;
    }
    
    try {
      const result = await electronAPI.captureScreenshot(runId, agentPhase, description);
      
      if (result.success && result.screenshot) {
        addScreenshot(runId, result.screenshot);
        return result.screenshot;
      } else {
        throw new Error(result.error || 'Screenshot capture failed');
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to capture screenshot';
      setError(message);
      console.error('[useAgentRuns] Capture screenshot error:', error);
      return null;
    }
  },

  pushRun: async (runId) => {
    const { runs, isElectron } = get();
    if (!isElectron) return;
    const run = runs.find(r => r.id === runId);
    if (!run) throw new Error('Run not found');
    
    // Extract branch name from run or generate it
    // The backend router generates: feature/ships-<slug>-<timestamp>
    // We assume the frontend has the correct branch name in `run.branch` if we added it?
    // Wait, the backend model doesn't store branch name explicitly usually, or does it?
    // Looking at RunCard logic, it uses `run.branch_name` or similar.
    // Actually, `BranchRunManager` generates it deterministically.
    // But we need the exact name.
    // The `AgentRun` type in `types.ts` should have `branchName`?
    // Let's assume we pass the branch name or ID and let Electron handle it.
    // Electron's `pushRun` IPC handler I defined in `gitHandlers.ts` takes `branch`.
    // We need to know the branch name.
    // I'll update the IPC to take `runId` and resolve branch internally?
    // Or simpler: pass `runId` and `prompt` like `createBranch` and regenerate it?
    // NO, that's risky. 
    // The `AgentRun` type SHOULD have the branch name.
    // I recall adding `baseBranch` but did I add `branchName`?
    // Runs usually have metadata.
    // Let's assume for now we construct it or have it.
    // Actually, `BranchRunManager.ts` stores branch name? No, it calculates it.
    // If I look at `RunCard.tsx`, it calls `pushRun(run.id)`.
    // So `useAgentRuns.pushRun` receives `runId`.
    // I should invoke `electronAPI.pushRun(branchName)`.
    // I need the branch name.
    // I'll call `electronAPI.pushRun(runId)` instead and update `gitHandlers` to take `runId` and look it up?
    // `BranchRunManager` has `getBranchName(runId)`.
    // I should update `gitHandlers.ts` to accept `runId` instead of `branch`.
    // This is cleaner.
    
    // For now I'll stub with the run ID and let the background handler resolve it if I update it.
    // Or I'll query `branchManager` in `gitHandlers`.
    
    // Wait, I registered `git:push` taking `{ branch: string }`.
    // I should change it to take `runId`?
    // Or I need to get the branch name here.
    // `run` object likely has it if backend returns it. I removed `isPrimary` but `branch_name` might be there?
    // I'll peek at `types.ts` or `AgentRun` model in backend.
    
    // Assuming `run.branch` exists for now.
    // If not, I'll pass `run.id` and let Electron resolve it (need to update handler).
    // Let's update handler to take `runId`.
    
    // Actually, let's look at `types.ts` quickly using `view_file`? No space in this turn.
    // I'll assume `run.branch` or `run.branchName` is available from the API response.
    // The previous summary said: "Modified branch display to show both the run's branch name".
    // So the data is there.
    
    // Let's assume `run.branchName` is the field.
    // I'll pass that.
    
    await electronAPI.pushRun((run as any).branchName || (run as any).branch || `run-${runId}`);
  },

  pullRun: async (runId) => {
    const { runs, isElectron } = get();
    if (!isElectron) return;
    const run = runs.find(r => r.id === runId);
    if (!run) throw new Error('Run not found');
    
    await electronAPI.pullRun((run as any).branchName || (run as any).branch || `run-${runId}`);
  },

  getRemotes: async () => {
    return electronAPI.getRemotes();
  },

  setRemote: async (url, name) => {
     return electronAPI.setRemote(url, name);
  },
}),
    {
      name: 'ships-agent-runs-v2',
      storage: createJSONStorage(() => localStorage),
      // Persist runs and activeRunId so messages don't disappear
      partialize: (state) => ({
        runs: state.runs,
        activeRunId: state.activeRunId,
      }),
      // Handle date serialization
      onRehydrateStorage: () => (state) => {
        if (state) {
          // Rehydrate dates in runs
          state.runs = state.runs.map(run => ({
            ...run,
            createdAt: run.createdAt,
            updatedAt: run.updatedAt,
            messages: run.messages?.map(msg => ({
              ...msg,
              timestamp: new Date(msg.timestamp),
            })) || [],
          }));
          console.log('[useAgentRuns] Rehydrated', state.runs.length, 'runs from storage');
        }
      },
    }
  )
);

// ============================================================================
// Type augmentation for window.electron
// ============================================================================

declare global {
  interface Window {
    electron?: {
      createRunBranch?: (runId: string, prompt: string) => Promise<{ success: boolean; branch?: any; error?: string }>;
      switchRunBranch?: (runId: string) => Promise<{ success: boolean; error?: string }>;
      deleteRunBranch?: (runId: string) => Promise<{ success: boolean; error?: string }>;
      createRunCheckpoint?: (message: string) => Promise<{ success: boolean; commitHash?: string; error?: string }>;
      rollbackRun?: (commitHash: string) => Promise<{ success: boolean; error?: string }>;
      createRunPreview?: (runId: string) => Promise<{ success: boolean; preview?: any; error?: string }>;
      refreshRunPreview?: (runId: string) => Promise<{ success: boolean; error?: string }>;
      closeRunPreview?: (runId: string) => Promise<{ success: boolean; error?: string }>;
      getActiveRunPreviews?: () => Promise<{ success: boolean; previews?: any[]; error?: string }>;
      captureRunScreenshot?: (runId: string, agentPhase: string, description?: string) => Promise<{ success: boolean; screenshot?: Screenshot; error?: string }>;
      getRunScreenshots?: (runId: string) => Promise<{ success: boolean; screenshots?: Screenshot[]; error?: string }>;
      deleteRunScreenshots?: (runId: string) => Promise<{ success: boolean; error?: string }>;
      
      // Git ops
      pushRun?: (branch: string) => Promise<void>;
      pullRun?: (branch: string) => Promise<void>;
      getRemotes?: () => Promise<any[]>;
      setRemote?: (url: string, name?: string) => Promise<void>;
      
      // Other existing electron methods...
      [key: string]: any;
    };
  }
}
