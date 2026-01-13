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
    const request: CreateRunRequest = {
      prompt: newRunPrompt.trim(),
      title: newRunPrompt.trim().slice(0, 50),
    };
    
    const newRun = await createRun(request);
    
    if (newRun) {
      setNewRunPrompt('');
      setShowCreateModal(false);
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

  // Separate primary (first) run from others
  const primaryRun = runs.find(r => r.isPrimary);
  const otherRuns = runs.filter(r => !r.isPrimary);
  const activeRuns = otherRuns.filter(r => r.status !== 'paused' && r.status !== 'completed');
  const pausedRuns = otherRuns.filter(r => r.status === 'paused');
  const completedRuns = otherRuns.filter(r => r.status === 'completed');

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
        {/* Primary Run */}
        {primaryRun && (
          <section className="agent-dashboard__section">
            <h2 className="agent-dashboard__section-title">Main</h2>
            <RunCard 
              run={primaryRun} 
              isPrimary 
              isSelected={primaryRun.id === activeRunId}
              onSelect={() => setActiveRun(primaryRun.id)}
            />
          </section>
        )}

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
