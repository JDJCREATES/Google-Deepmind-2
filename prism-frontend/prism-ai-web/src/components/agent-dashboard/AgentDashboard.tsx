/**
 * Agent Dashboard
 * 
 * Main container component for managing multiple agent runs.
 * Displays as a custom tab in the Monaco editor area.
 */

import React, { useEffect, useState } from 'react';
import { useAgentRuns } from './hooks/useAgentRuns';
import { RunCard } from './components/RunCard/RunCard';
import type { CreateRunRequest } from './types';
import { agentService } from '../../services/agentService';
import './AgentDashboard.css';

export const AgentDashboard: React.FC = () => {
  const { 
    runs, 
    isLoading, 
    error, 
    fetchRuns, 
    createRun,
    setError,
    activeRunId,
    setActiveRun
  } = useAgentRuns();
  
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newRunPrompt, setNewRunPrompt] = useState('');
  const [isCreating, setIsCreating] = useState(false);

  // Fetch runs on mount
  useEffect(() => {
    fetchRuns();
  }, [fetchRuns]);

  // Handle new run creation
  const handleCreateRun = async () => {
    if (!newRunPrompt.trim()) return;
    
    setIsCreating(true);
    const prompt = newRunPrompt.trim();
    
    // Get project path from Electron BEFORE creating run
    const projectPath = (window as any).electron?.getProjectPath 
      ? await (window as any).electron.getProjectPath() 
      : null;
    
    // If no Electron, try to get from preview API (backend knows the current project)
    let finalProjectPath = projectPath;
    if (!finalProjectPath) {
      try {
        const statusRes = await fetch('http://localhost:8001/preview/path');
        if (statusRes.ok) {
          const data = await statusRes.json();
          finalProjectPath = data.project_path;
        }
      } catch (e) {
        console.warn('[AgentDashboard] Could not fetch project path from backend');
      }
    }
    
    const request: CreateRunRequest = {
      prompt,
      title: prompt.slice(0, 50),
      projectPath: finalProjectPath || undefined,
    };
    
    const newRun = await createRun(request);
    
    if (newRun) {
      // IMPORTANT: Set this run as active so the chat UI binds to it
      setActiveRun(newRun.id);
      setNewRunPrompt('');
      setShowCreateModal(false);
      
      // Auto-trigger the agent with the prompt
      // This provides immediate feedback - the user doesn't need to re-type
      console.log('[AgentDashboard] Auto-triggering agent for new run:', newRun.id);
      
      // Use the project path from the created run (now stored in backend)
      
      // Start the agent (async, don't await)
      agentService.runAgent(
        prompt,
        newRun.projectPath,
        (chunk) => {
          // Chunk handling happens in ChatInterface via useChatLogic
          // The streaming store is shared, so updates will flow there
          console.log('[AgentDashboard] Agent chunk:', chunk.type);
        },
        (error) => {
          console.error('[AgentDashboard] Agent error:', error);
          setError(`Agent failed: ${error.message}`);
        }
      );
    }
    
    setIsCreating(false);
  };

  // Handle keyboard shortcut for create
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      handleCreateRun();
    }
    if (e.key === 'Escape') {
      setShowCreateModal(false);
      setNewRunPrompt('');
    }
  };

  // Dismiss error
  const dismissError = () => setError(null);

  // Categorize runs by status
  const activeRuns = runs.filter(r => r.status !== 'paused' && r.status !== 'completed');
  const pausedRuns = runs.filter(r => r.status === 'paused');
  const completedRuns = runs.filter(r => r.status === 'completed');

  return (
    <div className="agent-dashboard">
      {/* Header */}
      <header className="agent-dashboard__header">
        <h1 className="agent-dashboard__title">Agent Runs</h1>
        <button 
          className="agent-dashboard__new-btn"
          onClick={() => setShowCreateModal(true)}
        >
          + New Run
        </button>
      </header>

      {/* Error Banner */}
      {error && (
        <div className="agent-dashboard__error">
          <span>{error}</span>
          <button onClick={dismissError} className="agent-dashboard__error-dismiss">
            Dismiss
          </button>
        </div>
      )}

      {/* Loading State */}
      {isLoading && runs.length === 0 && (
        <div className="agent-dashboard__loading">
          <div className="agent-dashboard__spinner" />
          <span>Loading runs...</span>
        </div>
      )}

      {/* Empty State */}
      {!isLoading && runs.length === 0 && (
        <div className="agent-dashboard__empty">
          <div className="agent-dashboard__empty-icon">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path d="M12 5v14M5 12h14" />
            </svg>
          </div>
          <h2>No runs yet</h2>
          <p>Create your first run to start building with AI agents</p>
          <button 
            className="agent-dashboard__new-btn agent-dashboard__new-btn--large"
            onClick={() => setShowCreateModal(true)}
          >
            + Create First Run
          </button>
        </div>
      )}

      {/* Runs List */}
      <div className="agent-dashboard__runs">

        {/* Active Runs */}
        {activeRuns.length > 0 && (
          <section className="agent-dashboard__section">
            <h2 className="agent-dashboard__section-title">
              Active ({activeRuns.length})
            </h2>
            {activeRuns.map((run) => (
              <RunCard 
                key={run.id} 
                run={run} 
                isSelected={run.id === activeRunId}
                onSelect={() => setActiveRun(run.id)}
              />
            ))}
          </section>
        )}

        {/* Paused Runs */}
        {pausedRuns.length > 0 && (
          <section className="agent-dashboard__section agent-dashboard__section--collapsed">
            <h2 className="agent-dashboard__section-title">
              Paused ({pausedRuns.length})
            </h2>
            {pausedRuns.map((run) => (
              <RunCard 
                key={run.id} 
                run={run} 
                isSelected={run.id === activeRunId}
                onSelect={() => setActiveRun(run.id)}
              />
            ))}
          </section>
        )}

        {/* Completed Runs */}
        {completedRuns.length > 0 && (
          <section className="agent-dashboard__section agent-dashboard__section--collapsed">
            <h2 className="agent-dashboard__section-title">
              Completed ({completedRuns.length})
            </h2>
            {completedRuns.map((run) => (
              <RunCard 
                key={run.id} 
                run={run} 
                isSelected={run.id === activeRunId}
                onSelect={() => setActiveRun(run.id)}
              />
            ))}
          </section>
        )}
      </div>

      {/* Create Run Modal */}
      {showCreateModal && (
        <div className="agent-dashboard__modal-overlay" onClick={() => setShowCreateModal(false)}>
          <div className="agent-dashboard__modal" onClick={(e) => e.stopPropagation()}>
            <h2 className="agent-dashboard__modal-title">New Run</h2>
            <p className="agent-dashboard__modal-description">
              Describe what you want to build. A new git branch will be created for this run.
            </p>
            <textarea
              className="agent-dashboard__modal-input"
              placeholder="e.g., Add a dark mode toggle to the settings page"
              value={newRunPrompt}
              onChange={(e) => setNewRunPrompt(e.target.value)}
              onKeyDown={handleKeyDown}
              autoFocus
              rows={4}
            />
            <div className="agent-dashboard__modal-actions">
              <button 
                className="agent-dashboard__modal-cancel"
                onClick={() => {
                  setShowCreateModal(false);
                  setNewRunPrompt('');
                }}
              >
                Cancel
              </button>
              <button 
                className="agent-dashboard__modal-submit"
                onClick={handleCreateRun}
                disabled={!newRunPrompt.trim() || isCreating}
              >
                {isCreating ? 'Creating...' : 'Create Run'}
              </button>
            </div>
            <span className="agent-dashboard__modal-hint">
              Ctrl+Enter to create
            </span>
          </div>
        </div>
      )}
    </div>
  );
};
