/**
 * Run Card Component
 * 
 * Displays a single agent run with status, screenshot timeline,
 * files changed, and feedback input.
 */

import React, { useState } from 'react';
import type { AgentRun } from '../../types';
import { useAgentRuns } from '../../hooks/useAgentRuns';
import { ScreenshotTimeline } from '../ScreenshotTimeline/ScreenshotTimeline';
import { FeedbackInput } from '../FeedbackInput/FeedbackInput';
import './RunCard.css';

interface RunCardProps {
  run: AgentRun;
  isPrimary?: boolean;
  isSelected?: boolean;
  onSelect?: () => void;
}

export const RunCard: React.FC<RunCardProps> = ({ run, isPrimary = false, isSelected = false, onSelect }) => {
  const { pauseRun, resumeRun, deleteRun, rollbackToScreenshot } = useAgentRuns();
  const [expanded, setExpanded] = useState(true);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  // Status indicator color
  const getStatusColor = () => {
    switch (run.status) {
      case 'running':
      case 'planning':
        return 'var(--success-color, #4ade80)';
      case 'paused':
        return 'var(--warning-color, #fbbf24)';
      case 'error':
        return 'var(--error-color, #ff5e57)';
      case 'completed':
        return 'var(--info-color, #60a5fa)';
      default:
        return 'var(--text-secondary)';
    }
  };

  // Agent display name
  const getAgentDisplay = () => {
    if (!run.currentAgent) return null;
    
    const agentNames: Record<string, string> = {
      planner: 'Planner',
      coder: 'Coder',
      validator: 'Validator',
      fixer: 'Fixer',
    };
    
    return agentNames[run.currentAgent] || run.currentAgent;
  };

  // Handle pause/resume
  const handleTogglePause = () => {
    if (run.status === 'paused') {
      resumeRun(run.id);
    } else {
      pauseRun(run.id);
    }
  };

  // Handle delete
  const handleDelete = () => {
    if (showDeleteConfirm) {
      deleteRun(run.id);
    } else {
      setShowDeleteConfirm(true);
      // Auto-dismiss after 3 seconds
      setTimeout(() => setShowDeleteConfirm(false), 3000);
    }
  };

  // Handle rollback
  const handleRollback = (screenshotId: string) => {
    rollbackToScreenshot(run.id, screenshotId);
  };

  const isActive = run.status === 'running' || run.status === 'planning';

  return (
    <div 
      className={`run-card ${isPrimary ? 'run-card--primary' : ''} ${isSelected ? 'run-card--selected' : ''} ${!expanded ? 'run-card--collapsed' : ''}`}
      onClick={(e) => { 
        // Only select if not clicking buttons or content area
        if (!(e.target as HTMLElement).closest('button') && !(e.target as HTMLElement).closest('.run-card__content')) {
           onSelect?.();
        }
      }}
    >
      {/* Header */}
      <header className="run-card__header" onClick={() => setExpanded(!expanded)}>
        <div className="run-card__status-indicator" style={{ background: getStatusColor() }} />
        
        <div className="run-card__title-section">
          <h3 className="run-card__title">{run.title}</h3>
          <span className="run-card__branch">{run.branch}</span>
        </div>

        <div className="run-card__meta">
          {run.port > 0 && (
            <span className="run-card__port">Port: {run.port}</span>
          )}
          <span className="run-card__status">{run.status}</span>
        </div>

        <div className="run-card__actions">
          {!isPrimary && (
            <>
              <button 
                className="run-card__action-btn"
                onClick={(e) => { e.stopPropagation(); handleTogglePause(); }}
                title={run.status === 'paused' ? 'Resume' : 'Pause'}
              >
                {run.status === 'paused' ? (
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M8 5v14l11-7z"/>
                  </svg>
                ) : (
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/>
                  </svg>
                )}
              </button>
              <button 
                className={`run-card__action-btn ${showDeleteConfirm ? 'run-card__action-btn--danger' : ''}`}
                onClick={(e) => { e.stopPropagation(); handleDelete(); }}
                title={showDeleteConfirm ? 'Click again to confirm' : 'Delete'}
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M3 6h18M8 6V4a2 2 0 012-2h4a2 2 0 012 2v2m3 0v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6h14z"/>
                </svg>
              </button>
            </>
          )}
          <button 
            className="run-card__expand-btn"
            onClick={(e) => { e.stopPropagation(); setExpanded(!expanded); }}
          >
            <svg 
              width="16" 
              height="16" 
              viewBox="0 0 24 24" 
              fill="none" 
              stroke="currentColor" 
              strokeWidth="2"
              style={{ transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)', transition: 'transform 0.2s ease' }}
            >
              <path d="M6 9l6 6 6-6"/>
            </svg>
          </button>
        </div>
      </header>

      {/* Agent Status */}
      {isActive && run.currentAgent && (
        <div className="run-card__agent-status">
          <div className="run-card__agent-indicator" />
          <span className="run-card__agent-name">{getAgentDisplay()} Agent</span>
          <span className="run-card__agent-message">{run.agentMessage || 'Working...'}</span>
        </div>
      )}

      {/* Expanded Content */}
      {expanded && (
        <div className="run-card__content">
          {/* Screenshot Timeline */}
          <ScreenshotTimeline 
            screenshots={run.screenshots} 
            onRollback={handleRollback}
          />

          {/* Files Changed */}
          {run.filesChanged.length > 0 && (
            <div className="run-card__files">
              <span className="run-card__files-label">Files changed:</span>
              <span className="run-card__files-list">
                {run.filesChanged.slice(0, 3).join(', ')}
                {run.filesChanged.length > 3 && ` (+${run.filesChanged.length - 3} more)`}
              </span>
            </div>
          )}

          {/* Feedback Input */}
          <FeedbackInput runId={run.id} disabled={!isActive && run.status !== 'paused'} />
        </div>
      )}
    </div>
  );
};
