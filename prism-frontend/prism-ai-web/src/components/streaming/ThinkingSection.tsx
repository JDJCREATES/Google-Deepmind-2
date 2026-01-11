import React, { useState } from 'react';
import { FiCheck, FiLoader, FiArrowRight, FiZap, FiFileText, FiSettings } from 'react-icons/fi';
import './ThinkingSection.css';

interface ThinkingSectionProps {
  title: string;
  node: string;
  content: string;
  isLive?: boolean;
  defaultExpanded?: boolean;
}

// Get icon based on node type
const getNodeIcon = (node: string) => {
  switch (node.toLowerCase()) {
    case 'orchestrator': return <FiSettings size={14} />;
    case 'planner': return <FiFileText size={14} />;
    case 'coder': return <FiZap size={14} />;
    case 'validator': return <FiCheck size={14} />;
    case 'fixer': return <FiSettings size={14} />;
    default: return <FiArrowRight size={14} />;
  }
};

/**
 * Agent Activity Section - Shows agent reasoning in structured blocks
 * Inspired by GitHub Copilot and Antigravity agent displays
 */
export const ThinkingSection: React.FC<ThinkingSectionProps> = ({
  title,
  node,
  content,
  isLive = false,
  defaultExpanded = true
}) => {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);
  
  // Parse content into structured steps
  const parseSteps = (text: string) => {
    const lines = text.split('\n').filter(line => line.trim());
    return lines.map(line => {
      // Detect step type for styling
      const isDecision = /decision:|decided|routing to/i.test(line);
      const isAction = line.includes('→') || line.includes('->') || /calling|running|executing/i.test(line);
      const isResult = /✓|✔|success|complete|created|wrote/i.test(line);
      const isError = /✗|error|failed|exception/i.test(line);
      const isNote = line.startsWith('-') || line.startsWith('•') || line.startsWith('*');
      
      return { line, isDecision, isAction, isResult, isError, isNote };
    });
  };

  const steps = parseSteps(content);

  return (
    <div className={`agent-activity-section ${isLive ? 'live' : ''} ${node.toLowerCase()}`}>
      {/* Header - collapsible */}
      <div 
        className="agent-activity-header"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <span className="agent-activity-icon">
          {isLive ? <FiLoader className="spinning" size={14} /> : getNodeIcon(node)}
        </span>
        <span className="agent-activity-title">{title}</span>
        <span className="agent-activity-toggle">
          {isExpanded ? '−' : '+'}
        </span>
      </div>
      
      {/* Content - each step as a separate line */}
      {isExpanded && steps.length > 0 && (
        <div className="agent-activity-steps">
          {steps.map((step, i) => {
            let className = 'agent-activity-step';
            let icon = <FiArrowRight size={12} />;
            
            if (step.isResult) {
              className += ' success';
              icon = <FiCheck size={12} />;
            } else if (step.isError) {
              className += ' error';
            } else if (step.isDecision) {
              className += ' decision';
              icon = <FiZap size={12} />;
            } else if (step.isAction) {
              className += ' action';
            } else if (step.isNote) {
              className += ' note';
            }
            
            return (
              <div key={i} className={className}>
                <span className="step-icon">{icon}</span>
                <span className="step-text">{step.line}</span>
              </div>
            );
          })}
          {isLive && (
            <div className="agent-activity-step live">
              <span className="step-icon"><FiLoader className="spinning" size={12} /></span>
              <span className="step-text typing-cursor">_</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default ThinkingSection;


