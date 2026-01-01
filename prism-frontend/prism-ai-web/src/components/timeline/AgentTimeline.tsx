/**
 * Agent Timeline Component
 * 
 * Main timeline view showing the history of agent actions and features built.
 * Displays a horizontal timeline with nodes representing different stages of development.
 */

import { useState, useEffect } from 'react';
import { TimelineContainer } from './TimelineContainer';
import type { TimelineNode, TimelineState } from '../../types/timeline';
import './AgentTimeline.css';

interface AgentTimelineProps {
  // Optional: Can receive nodes from parent or manage internally
  initialNodes?: TimelineNode[];
  onNodeAction?: (action: string, nodeId: string) => void;
}

export function AgentTimeline({ initialNodes = [], onNodeAction }: AgentTimelineProps) {
  const [timelineState, setTimelineState] = useState<TimelineState>({
    nodes: initialNodes,
    current_node_id: '',
    scroll_position: 0,
    filter: 'all',
    group_by: 'none'
  });

  // Update nodes when initialNodes change
  useEffect(() => {
    if (initialNodes.length > 0) {
      setTimelineState(prev => ({
        ...prev,
        nodes: initialNodes,
        current_node_id: initialNodes[initialNodes.length - 1]?.id || ''
      }));
    }
  }, [initialNodes]);

  const handleNodeClick = (nodeId: string) => {
    onNodeAction?.('click', nodeId);
  };

  const handleViewDiff = (nodeId: string) => {
    onNodeAction?.('view_diff', nodeId);
  };

  const handleUndo = (nodeId: string) => {
    onNodeAction?.('undo', nodeId);
  };

  const handleRestore = (nodeId: string) => {
    onNodeAction?.('restore', nodeId);
  };

  return (
    <section className="agent-timeline-wrapper">
      <TimelineContainer
        nodes={timelineState.nodes}
        currentNodeId={timelineState.current_node_id}
        activeNodeId={timelineState.active_node_id}
        onNodeClick={handleNodeClick}
        onViewDiff={handleViewDiff}
        onUndo={handleUndo}
        onRestore={handleRestore}
      />
    </section>
  );
}

export default AgentTimeline;