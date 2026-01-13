/**
 * Agent Runs Store
 * 
 * Zustand store for managing agent run state.
 * Uses Electron IPC when available, falls back to HTTP API.
 * Includes comprehensive error handling and retry logic.
 */

import { create } from 'zustand';
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
  sendFeedback: (runId: string, message: string) => Promise<void>;
  rollbackToScreenshot: (runId: string, screenshotId: string) => Promise<void>;
  
  // Electron-specific actions
  captureScreenshot: (runId: string, agentPhase: string, description?: string) => Promise<Screenshot | null>;
  
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
};

// ============================================================================
// Store
// ============================================================================

export const useAgentRuns = create<AgentRunsState>((set, get) => ({
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
        })
      );
      
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Failed to create run: ${response.status} ${errorText}`);
      }
      
      const newRun: AgentRun = await response.json();
      
      // If in Electron, also create git branch and preview
      if (isElectron) {
        try {
          await electronAPI.createBranch(newRun.id, request.prompt);
          await electronAPI.createPreview(newRun.id);
        } catch (electronError) {
          console.warn('[useAgentRuns] Electron integration failed, continuing with HTTP only:', electronError);
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
      const response = await withRetry(() => fetch(`${API_BASE}/api/runs`));
      
      if (!response.ok) {
        throw new Error(`Failed to fetch runs: ${response.status}`);
      }
      
      const runs: AgentRun[] = await response.json();
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
        fetch(`${API_BASE}/api/runs/${runId}/pause`, { method: 'POST' })
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
        fetch(`${API_BASE}/api/runs/${runId}/resume`, { method: 'POST' })
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
      // If in Electron, close preview and delete branch first
      if (isElectron) {
        try {
          await electronAPI.closePreview(runId);
          await electronAPI.deleteBranch(runId);
        } catch (electronError) {
          console.warn('[useAgentRuns] Electron cleanup failed:', electronError);
        }
      }
      
      const response = await withRetry(() => 
        fetch(`${API_BASE}/api/runs/${runId}`, { method: 'DELETE' })
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
  
  sendFeedback: async (runId, message) => {
    const { setError, updateRun } = get();
    
    try {
      const response = await withRetry(() => 
        fetch(`${API_BASE}/api/runs/${runId}/feedback`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message }),
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
  
  // Electron-only: Capture screenshot
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
}));

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
      // Other existing electron methods...
      [key: string]: any;
    };
  }
}
