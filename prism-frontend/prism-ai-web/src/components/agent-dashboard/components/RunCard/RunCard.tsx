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
import { MergeConflictModal } from '../MergeConflictModal/MergeConflictModal';
import './RunCard.css';

interface RunCardProps {
  run: AgentRun;
  isSelected?: boolean;
  onSelect?: () => void;
}

export const RunCard: React.FC<RunCardProps> = ({ run, isSelected = false, onSelect }) => {
  const { pauseRun, resumeRun, deleteRun, rollbackToScreenshot, pushRun, pullRun } = useAgentRuns();
  const [expanded, setExpanded] = useState(true);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [showMergeModal, setShowMergeModal] = useState(false);
  const [showOptions, setShowOptions] = useState(false);
  const [conflicts, setConflicts] = useState<any[]>([]);

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
    }  };

  // Handle push/pull
  const handlePush = async () => {
    try {
        await pushRun(run.id);
    } catch (e: any) {
        if (e.message.includes('conflict')) {
            // Mock conflict for now, in real flow we'd fetch diffs
            setConflicts([{
                path: 'src/App.tsx',
                original: 'const App = () => <div>Original</div>',
                modified: 'const App = () => <div>Modified</div>'
            }]);
            setShowMergeModal(true);
        }
    }
  };

  // Handle resolution
  const handleResolve = (strategy: string) => {
    console.log('Resolved with:', strategy);
    setShowMergeModal(false);
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
      className={`run-card ${isSelected ? 'run-card--selected' : ''} ${!expanded ? 'run-card--collapsed' : ''}`}
      onClick={(e) => { 
        // Only select if not clicking buttons or content area
        if (!(e.target as HTMLElement).closest('button') && !(e.target as HTMLElement).closest('.run-card__content')) {
           onSelect?.();
        }
      }}
    >
      {/* Header */}
      <header className="run-card__header" onClick={() => setExpanded(!expanded)}>
        <div 
          className={`run-card__status-indicator ${showOptions ? 'run-card__status-indicator--open' : ''}`}
          style={{ background: getStatusColor() }}
          onClick={(e) => {
            e.stopPropagation();
            setShowOptions(!showOptions);
          }}
          title="Click for options"
        >
          {showOptions && (
            <div className="run-card__options-menu" onClick={(e) => e.stopPropagation()}>
              <button 
                className="run-card__option-item" 
                onClick={(e) => { e.stopPropagation(); handlePush(); setShowOptions(false); }}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M12 19V5M5 12l7-7 7 7"/>
                </svg>
                Push to Remote
              </button>
              
              <button 
                className="run-card__option-item" 
                onClick={(e) => { e.stopPropagation(); handleTogglePause(); setShowOptions(false); }}
              >
                {run.status === 'paused' ? (
                  <>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>
                  Resume Run
                  </>
                ) : (
                  <>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/></svg>
                  Pause Run
                  </>
                )}
              </button>

              <button 
                className="run-card__option-item" 
                onClick={(e) => { 
                  e.stopPropagation(); 
                  navigator.clipboard.writeText(run.branch);
                  setShowOptions(false); 
                }}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                   <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                   <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                </svg>
                Copy Branch
              </button>

              <div style={{ height: 1, background: 'var(--border-color)', margin: '4px 0' }} />
              
              <button 
                className="run-card__option-item run-card__option-item--danger" 
                onClick={(e) => { e.stopPropagation(); handleDelete(); setShowOptions(false); }}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M3 6h18M8 6V4a2 2 0 012-2h4a2 2 0 012 2v2m3 0v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6h14z"/>
                </svg>
                Delete Run
              </button>
            </div>
          )}
        </div>
        
        <div className="run-card__title-section">
          <h3 className="run-card__title">{run.title}</h3>
          <span className="run-card__branch">
            {run.branch}
            {run.baseBranch && <span className="run-card__base-branch"> → from {run.baseBranch}</span>}
          </span>
        </div>

        <div className="run-card__meta">
          {run.port > 0 && (
            <span className="run-card__port">Port: {run.port}</span>
          )}
          <span className="run-card__status">{run.status}</span>
        </div>

          <div className="run-card__actions">
              <button 
                className="run-card__action-btn"
                onClick={(e) => { e.stopPropagation(); handlePush(); }}
                title="Push to Remote"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M12 19V5M5 12l7-7 7 7"/>
                </svg>
              </button>
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
      
      <MergeConflictModal 
        isOpen={showMergeModal}
        onClose={() => setShowMergeModal(false)}
        onResolve={handleResolve}
        files={conflicts}
      />
    </div>
  );
};
