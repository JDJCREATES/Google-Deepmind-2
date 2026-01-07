import { FiLoader, FiEdit3, FiCpu, FiTerminal } from 'react-icons/fi';
import './ActivityIndicator.css';

export interface ActivityProps {
  activity: string; // e.g., "Thinking...", "Writing src/App.tsx..."
  type?: 'thinking' | 'writing' | 'command' | 'reading' | 'working';
}

export function ActivityIndicator({ activity, type = 'thinking' }: ActivityProps) {
  if (!activity) return null;

  const getIcon = () => {
    switch (type) {
      case 'writing': return <FiEdit3 className="activity-icon-pulse" />;
      case 'command': return <FiTerminal className="activity-icon-pulse" />;
      case 'reading': return <FiCpu className="activity-icon-pulse" />; // Or specific icon
      default: return <FiLoader className="activity-icon-spin" />;
    }
  };

  return (
    <div className="activity-indicator-container">
      <div className="activity-indicator-card">
        <div className="activity-icon-wrapper">
          {getIcon()}
        </div>
        <div className="activity-text">
          {activity}
        </div>
      </div>
    </div>
  );
}
