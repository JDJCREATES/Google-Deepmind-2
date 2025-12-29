/**
 * Phase Indicator Component
 * 
 * Shows the current pipeline phase with visual progress.
 * Planning → Coding → Validating → Done
 */

import { FiCheck } from 'react-icons/fi';
import './PhaseIndicator.css';

export type AgentPhase = 'idle' | 'planning' | 'coding' | 'validating' | 'done' | 'error';

interface PhaseIndicatorProps {
  phase: AgentPhase;
}

const phases: { key: AgentPhase; label: string }[] = [
  { key: 'planning', label: 'Planning' },
  { key: 'coding', label: 'Coding' },
  { key: 'validating', label: 'Validating' },
];

export function PhaseIndicator({ phase }: PhaseIndicatorProps) {
  if (phase === 'idle') return null;
  
  const currentIndex = phases.findIndex(p => p.key === phase);
  const isDone = phase === 'done';
  const isError = phase === 'error';

  return (
    <div className={`phase-indicator ${isError ? 'error' : ''}`}>
      {phases.map((p, idx) => {
        const isActive = p.key === phase;
        const isCompleted = isDone || (currentIndex >= 0 && idx < currentIndex);
        
        return (
          <div key={p.key} className="phase-step-wrapper">
            <div 
              className={`phase-step ${isActive ? 'active' : ''} ${isCompleted ? 'completed' : ''}`}
            >
              <div className="phase-dot">
                {isCompleted ? <FiCheck size={10} /> : (idx + 1)}
              </div>
              <span className="phase-label">{p.label}</span>
            </div>
            {idx < phases.length - 1 && (
              <div className={`phase-connector ${isCompleted ? 'completed' : ''}`} />
            )}
          </div>
        );
      })}
      
      {isDone && (
        <div className="phase-done">
          <FiCheck size={14} />
          <span>Done</span>
        </div>
      )}
      
      {isError && (
        <div className="phase-error">
          <span>⚠️ Error</span>
        </div>
      )}
    </div>
  );
}
