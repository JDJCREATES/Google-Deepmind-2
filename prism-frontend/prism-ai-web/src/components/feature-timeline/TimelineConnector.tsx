/**
 * Timeline Connector Component
 * 
 * Draws connection lines between timeline nodes
 */

import './TimelineConnector.css';

interface TimelineConnectorProps {
  status?: 'normal' | 'completed' | 'failed' | 'revert';
  animated?: boolean;
}

export function TimelineConnector({ 
  status = 'normal',
  animated = false 
}: TimelineConnectorProps) {
  return (
    <div className={`timeline-connector ${status} ${animated ? 'animated' : ''}`}>
      <div className="connector-line" />
    </div>
  );
}
