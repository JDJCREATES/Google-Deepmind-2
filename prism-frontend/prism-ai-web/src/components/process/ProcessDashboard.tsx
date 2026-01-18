import React, { useEffect, useState } from 'react';
import { useAgentRuns } from '../agent-dashboard/hooks/useAgentRuns';
import { useTheme } from '../../hooks/useTheme';
import { VscDebugDisconnect, VscPlay, VscGlobe } from 'react-icons/vsc';
import './ProcessDashboard.css';

interface ProcessStatus {
  run_id: string;
  status: 'running' | 'stopped' | 'starting' | 'error';
  port?: number;
  url?: string;
  error?: string;
  logs?: string[];
}

export const ProcessDashboard: React.FC = () => {
  const { activeRunId, runs, openPreview } = useAgentRuns();
  const { theme } = useTheme();
  const [processStatus, setProcessStatus] = useState<ProcessStatus | null>(null);
  const [loading, setLoading] = useState(false);

  // Poll for status
  useEffect(() => {
    if (!activeRunId) return;

    const checkStatus = async () => {
      try {
        // Get the full ID from the active run to use for status lookup
        const activeRun = runs.find(r => r.id === activeRunId);
        const runIdForLookup = activeRun?.fullId || activeRunId;
        
        const res = await fetch(`http://localhost:8001/preview/status?run_id=${runIdForLookup}`);
        if (res.ok) {
          const data = await res.json();
          setProcessStatus({
            run_id: activeRunId,
            status: data.status || 'stopped',
            port: data.port,
            url: data.url,
            error: data.error,
            logs: data.logs || []
          });
        }
      } catch (e) {
        // Silently fail on poll error
      }
    };

    // Initial check
    checkStatus();

    // Poll every 2s
    const interval = setInterval(checkStatus, 2000);
    return () => clearInterval(interval);
  }, [activeRunId, runs]);

  if (!activeRunId) return null;

  const activeRun = runs.find(r => r.id === activeRunId);
  const title = activeRun?.title || 'Unknown Run';

  const handleKill = async () => {
    if (!confirm('Stop the dev server?')) return;
    setLoading(true);
    try {
      const activeRun = runs.find(r => r.id === activeRunId);
      const runIdForStop = activeRun?.fullId || activeRunId;
      await fetch(`http://localhost:8001/preview/stop/${runIdForStop}`, { method: 'POST' });
      // Quick optimistic update
      setProcessStatus(prev => prev ? { ...prev, status: 'stopped' } : null);
    } catch (e) {
      console.error('Failed to stop process', e);
    } finally {
      setLoading(false);
    }
  };

  const handleStart = async () => {
    setLoading(true);
    try {
      await openPreview(activeRunId);
    } finally {
      setLoading(false);
    }
  };

  const handleOpenUrl = () => {
    if (processStatus?.url) {
      window.open(processStatus.url, '_blank');
    }
  };

  const isRunning = processStatus?.status === 'running' || processStatus?.status === 'starting';

  return (
    <div className={`process-dashboard ${theme}`}>
      <div className="process-header">
        <span className="process-title" title={title}>
          PROCESS: {title.length > 20 ? title.substring(0, 20) + '...' : title}
        </span>
        <span className={`status-dot ${processStatus?.status || 'stopped'}`} />
      </div>

      <div className="process-controls">
        <div className="process-info">
          <span className="port-badge" title="Localhost Port">{processStatus?.port || 'N/A'}</span>
          {processStatus?.status === 'starting' && <span className="starting-badge">Booting</span>}
          {processStatus?.status === 'stopped' && <span className="stopped-badge">OFF</span>}
        </div>
        <div className="process-actions">
          {!isRunning ? (
             <button 
                className="icon-btn" 
                onClick={handleStart} 
                disabled={loading}
                title="Start Dev Server"
              >
                <VscPlay size={18} />
              </button>
          ) : (
             <button 
                className="icon-btn danger" 
                onClick={handleKill} 
                disabled={loading}
                title="Stop Process"
              >
                <VscDebugDisconnect size={18} />
              </button>
          )}
          
          <button
            className="icon-btn"
            onClick={async () => {
              if(!confirm(`Force kill process for run? (Port ${processStatus?.port || '?'})\nThis releases file locks.`)) return;
              setLoading(true);
              try {
                const activeRun = runs.find(r => r.id === activeRunId);
                const runIdForCleanup = activeRun?.fullId || activeRunId;
                await fetch(`http://localhost:8001/preview/cleanup?run_id=${runIdForCleanup}`, { method: 'POST' });
                // Refresh status immediately
                setProcessStatus(null);
              } finally {
                setLoading(false);
              }
            }}
            disabled={loading}
            title="Force Reset (Zombie Kill)"
          >
            <VscDebugDisconnect size={18} style={{ opacity: 0.5 }} />
          </button>
          
          <button 
            className="icon-btn" 
            onClick={handleOpenUrl} 
            title="Open Browser"
            disabled={!processStatus?.url || !isRunning}
          >
            <VscGlobe size={18} />
          </button>
        </div>
      </div>
      
      {/* Show error with logs for debugging */}
      {processStatus?.error && (
        <div className="process-error" style={{
          backgroundColor: 'rgba(255, 94, 87, 0.1)',
          border: '1px solid rgba(255, 94, 87, 0.3)',
          borderRadius: '4px',
          padding: '8px',
          marginTop: '8px',
          fontSize: '11px',
          color: '#ff9999'
        }}>
          <div style={{ fontWeight: 'bold', marginBottom: '4px' }}>⚠️ Dev Server Error:</div>
          <div style={{ fontFamily: 'monospace', fontSize: '10px', opacity: 0.9 }}>
            {processStatus.error}
          </div>
          {processStatus.logs && processStatus.logs.length > 0 && (
            <details style={{ marginTop: '8px' }}>
              <summary style={{ cursor: 'pointer', opacity: 0.7 }}>View Logs</summary>
              <div style={{ 
                maxHeight: '100px', 
                overflow: 'auto', 
                marginTop: '4px', 
                fontSize: '9px',
                fontFamily: 'monospace',
                backgroundColor: 'rgba(0,0,0,0.3)',
                padding: '4px',
                borderRadius: '2px'
              }}>
                {processStatus.logs.map((log, i) => (
                  <div key={i}>{log}</div>
                ))}
              </div>
            </details>
          )}
        </div>
      )}
    </div>
  );
};
