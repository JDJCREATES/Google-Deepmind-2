/**
 * Node Detail Panel Component
 * 
 * Shows expanded details when a timeline node is clicked
 */

import type { TimelineNode } from '../../types/timeline';
import { FiX, FiClock, FiFileText, FiGitCommit, FiAlertTriangle } from 'react-icons/fi';
import './NodeDetailPanel.css';

interface NodeDetailPanelProps {
  node: TimelineNode | null;
  onClose: () => void;
  onViewDiff?: () => void;
  onUndo?: () => void;
  onRestore?: () => void;
}

// Format duration
const formatDuration = (ms: number): string => {
  const seconds = Math.floor(ms / 1000);
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  
  if (minutes > 0) {
    return `${minutes}m ${remainingSeconds}s`;
  }
  return `${seconds}s`;
};

// Get status display
const getStatusDisplay = (status: string): { emoji: string; text: string; color: string } => {
  switch (status) {
    case 'success':
      return { emoji: '✅', text: 'Completed', color: '#4ec9b0' };
    case 'failed':
      return { emoji: '❌', text: 'Failed', color: '#f44747' };
    case 'warning':
      return { emoji: '⚠️', text: 'Success with warnings', color: '#ffc107' };
    case 'in-progress':
      return { emoji: '🔄', text: 'In Progress', color: '#57a8ff' };
    default:
      return { emoji: '○', text: 'Pending', color: '#666' };
  }
};

export function NodeDetailPanel({ 
  node, 
  onClose,
  onViewDiff,
  onUndo,
  onRestore 
}: NodeDetailPanelProps) {
  if (!node) return null;
  
  const statusInfo = getStatusDisplay(node.status);

  return (
    <div className="node-detail-overlay" onClick={onClose}>
      <div className="node-detail-panel" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="detail-panel-header">
          <div className="detail-title-section">
            <span className="detail-type-icon">🎯</span>
            <h3 className="detail-title">{node.title}</h3>
          </div>
          <button className="detail-close-btn" onClick={onClose}>
            <FiX size={20} />
          </button>
        </div>

        {/* Status Section */}
        <div className="detail-section">
          <div className="detail-status-row">
            <span className="status-label">Status:</span>
            <span className="status-value" style={{ color: statusInfo.color }}>
              {statusInfo.emoji} {statusInfo.text}
            </span>
            {node.duration_ms > 0 && (
              <>
                <span className="detail-separator">•</span>
                <span className="duration-value">
                  <FiClock size={12} style={{ marginRight: 4 }} />
                  {formatDuration(node.duration_ms)}
                </span>
              </>
            )}
          </div>
        </div>

        {/* Files Changed */}
        {node.files_changed.length > 0 && (
          <div className="detail-section">
            <div className="section-label">
              <FiFileText size={14} style={{ marginRight: 6 }} />
              Changes:
            </div>
            <div className="files-stats">
              {node.files_changed.length} files changed, 
              <span className="stat-added"> {node.lines_added} lines added</span>
              {node.lines_removed > 0 && (
                <span className="stat-removed">, {node.lines_removed} lines removed</span>
              )}
            </div>
            <ul className="file-list">
              {node.files_changed.slice(0, 10).map((file, idx) => (
                <li key={idx} className="file-item">
                  <span className="file-icon">📄</span>
                  <span className="file-path">{file}</span>
                </li>
              ))}
              {node.files_changed.length > 10 && (
                <li className="file-item-more">
                  +{node.files_changed.length - 10} more files...
                </li>
              )}
            </ul>
          </div>
        )}

        {/* Issues Fixed */}
        {node.issues_fixed.length > 0 && (
          <div className="detail-section">
            <div className="section-label">
              <FiAlertTriangle size={14} style={{ marginRight: 6 }} />
              Issues Fixed:
            </div>
            <ul className="issues-list">
              {node.issues_fixed.map((issue, idx) => (
                <li key={idx} className="issue-item">
                  <span className="issue-status">
                    {issue.auto_fixed ? '🔧 Auto-fixed' : '✏️ Manual fix'}:
                  </span>
                  <span className="issue-description">
                    {issue.description || issue.pitfall_id}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Phases */}
        {node.phases.length > 0 && (
          <div className="detail-section">
            <div className="section-label">Pipeline Phases:</div>
            <div className="phases-grid">
              {node.phases.map((phase, idx) => (
                <div key={idx} className={`phase-card ${phase.status}`}>
                  <div className="phase-name">{phase.name}</div>
                  <div className="phase-duration">{formatDuration(phase.duration_ms)}</div>
                  <div className="phase-status-icon">
                    {phase.status === 'success' ? '✅' : 
                     phase.status === 'failed' ? '❌' : 
                     phase.status === 'in-progress' ? '🔄' : '⏳'}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Git Info */}
        {node.commit_hash && (
          <div className="detail-section">
            <div className="section-label">
              <FiGitCommit size={14} style={{ marginRight: 6 }} />
              Git:
            </div>
            <div className="git-info">
              <code className="commit-hash">{node.commit_hash.substring(0, 8)}</code>
            </div>
          </div>
        )}

        {/* Actions */}
        <div className="detail-actions">
          {onViewDiff && (
            <button className="action-btn primary" onClick={onViewDiff}>
              View Diff
            </button>
          )}
          {onUndo && node.status === 'success' && (
            <button className="action-btn warning" onClick={onUndo}>
              Undo to Here
            </button>
          )}
          {onRestore && (
            <button className="action-btn" onClick={onRestore}>
              Restore
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
