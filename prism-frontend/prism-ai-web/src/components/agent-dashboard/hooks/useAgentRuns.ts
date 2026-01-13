/**
 * Agent Runs Store
 * 
 * Zustand store for managing agent run state.
 * Handles CRUD operations and real-time updates from WebSocket.
 */

import { create } from 'zustand';
import { AgentRun, Screenshot, RunStatus, AgentType, CreateRunRequest } from '../types';

interface AgentRunsState {
  runs: AgentRun[];
  activeRunId: string | null;
  isLoading: boolean;
  error: string | null;
  
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
  
  // API actions
  createRun: (request: CreateRunRequest) => Promise<AgentRun | null>;
  fetchRuns: () => Promise<void>;
  pauseRun: (runId: string) => Promise<void>;
  resumeRun: (runId: string) => Promise<void>;
  deleteRun: (runId: string) => Promise<void>;
  sendFeedback: (runId: string, message: string) => Promise<void>;
  rollbackToScreenshot: (runId: string, screenshotId: string) => Promise<void>;
  
  // Loading state
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
}

// API base URL
const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8001';

export const useAgentRuns = create<AgentRunsState>((set, get) => ({
  runs: [],
  activeRunId: null,
  isLoading: false,
  error: null,
  
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
  
  setLoading: (isLoading) => set({ isLoading }),
  setError: (error) => set({ error }),
  
  // API Actions
  createRun: async (request) => {
    const { setLoading, setError, addRun } = get();
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch(`${API_BASE}/api/runs`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
      });
      
      if (!response.ok) {
        throw new Error(`Failed to create run: ${response.statusText}`);
      }
      
      const newRun: AgentRun = await response.json();
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
      const response = await fetch(`${API_BASE}/api/runs`);
      
      if (!response.ok) {
        throw new Error(`Failed to fetch runs: ${response.statusText}`);
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
      const response = await fetch(`${API_BASE}/api/runs/${runId}/pause`, {
        method: 'POST',
      });
      
      if (!response.ok) {
        throw new Error(`Failed to pause run: ${response.statusText}`);
      }
      
      updateRun(runId, { status: 'paused', currentAgent: null });
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to pause run';
      setError(message);
      console.error('[useAgentRuns] Pause run error:', error);
    }
  },
  
  resumeRun: async (runId) => {
    const { updateRun, setError } = get();
    
    try {
      const response = await fetch(`${API_BASE}/api/runs/${runId}/resume`, {
        method: 'POST',
      });
      
      if (!response.ok) {
        throw new Error(`Failed to resume run: ${response.statusText}`);
      }
      
      updateRun(runId, { status: 'running' });
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to resume run';
      setError(message);
      console.error('[useAgentRuns] Resume run error:', error);
    }
  },
  
  deleteRun: async (runId) => {
    const { removeRun, setError } = get();
    
    try {
      const response = await fetch(`${API_BASE}/api/runs/${runId}`, {
        method: 'DELETE',
      });
      
      if (!response.ok) {
        throw new Error(`Failed to delete run: ${response.statusText}`);
      }
      
      removeRun(runId);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to delete run';
      setError(message);
      console.error('[useAgentRuns] Delete run error:', error);
    }
  },
  
  sendFeedback: async (runId, message) => {
    const { setError } = get();
    
    try {
      const response = await fetch(`${API_BASE}/api/runs/${runId}/feedback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message }),
      });
      
      if (!response.ok) {
        throw new Error(`Failed to send feedback: ${response.statusText}`);
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to send feedback';
      setError(message);
      console.error('[useAgentRuns] Send feedback error:', error);
    }
  },
  
  rollbackToScreenshot: async (runId, screenshotId) => {
    const { setError, runs } = get();
    
    const run = runs.find(r => r.id === runId);
    const screenshot = run?.screenshots.find(s => s.id === screenshotId);
    
    if (!screenshot) {
      setError('Screenshot not found');
      return;
    }
    
    try {
      const response = await fetch(`${API_BASE}/api/runs/${runId}/rollback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          screenshotId,
          commitHash: screenshot.gitCommitHash 
        }),
      });
      
      if (!response.ok) {
        throw new Error(`Failed to rollback: ${response.statusText}`);
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to rollback';
      setError(message);
      console.error('[useAgentRuns] Rollback error:', error);
    }
  },
}));
