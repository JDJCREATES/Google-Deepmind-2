/**
 * Timeline Container Component
 * 
 * Main horizontal timeline display with scrolling
 */

import { useRef, useState, useEffect } from 'react';
import type { TimelineNode as TimelineNodeType, FilterType } from '../../types/timeline';
import { TimelineNode } from './TimelineNode';
import { TimelineConnector } from './TimelineConnector';
import { NodeDetailPanel } from './NodeDetailPanel';
import { TimelineControls } from './TimelineControls';
import { useTimelineKeyboard } from '../../hooks/useTimelineKeyboard';
import './TimelineContainer.css';

interface TimelineContainerProps {
  nodes: TimelineNodeType[];
  currentNodeId?: string;
  activeNodeId?: string;
  onNodeClick?: (nodeId: string) => void;
  onViewDiff?: (nodeId: string) => void;
  onUndo?: (nodeId: string) => void;
  onRestore?: (nodeId: string) => void;
}

export function TimelineContainer({
  nodes,
  currentNodeId,
  activeNodeId,
  onNodeClick,
  onViewDiff,
  onUndo,
  onRestore
}: TimelineContainerProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [selectedNode, setSelectedNode] = useState<TimelineNodeType | null>(null);
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);
  const [filter, setFilter] = useState<FilterType>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(false);

  // Filter nodes based on current filter and search
  const filteredNodes = nodes.filter(node => {
    // Apply filter
    if (filter !== 'all') {
      if (filter === 'features' && node.type !== 'feature') return false;
      if (filter === 'fixes' && node.type !== 'fix') return false;
      if (filter === 'refactors' && node.type !== 'refactor') return false;
      if (filter === 'deploys' && node.type !== 'deploy') return false;
    }
    
    // Apply search
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      return (
        node.title.toLowerCase().includes(query) ||
        node.description?.toLowerCase().includes(query) ||
        node.files_changed.some(file => file.toLowerCase().includes(query))
      );
    }
    
    return true;
  });

  // Check scroll position
  const updateScrollButtons = () => {
    if (scrollRef.current) {
      const { scrollLeft, scrollWidth, clientWidth } = scrollRef.current;
      setCanScrollLeft(scrollLeft > 0);
      setCanScrollRight(scrollLeft < scrollWidth - clientWidth - 10);
    }
  };

  useEffect(() => {
    updateScrollButtons();
    const scrollEl = scrollRef.current;
    if (scrollEl) {
      scrollEl.addEventListener('scroll', updateScrollButtons);
      return () => scrollEl.removeEventListener('scroll', updateScrollButtons);
    }
  }, [nodes]);

  // Auto-scroll to active node
  useEffect(() => {
    if (activeNodeId && scrollRef.current) {
      const activeElement = scrollRef.current.querySelector(`[data-node-id="${activeNodeId}"]`);
      if (activeElement) {
        activeElement.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
      }
    }
  }, [activeNodeId]);

  const handleScrollLeft = () => {
    if (scrollRef.current) {
      scrollRef.current.scrollBy({ left: -200, behavior: 'smooth' });
    }
  };

  const handleScrollRight = () => {
    if (scrollRef.current) {
      scrollRef.current.scrollBy({ left: 200, behavior: 'smooth' });
    }
  };

  const handleNodeClick = (node: TimelineNodeType) => {
    setSelectedNode(node);
    onNodeClick?.(node.id);
  };

  const handleCloseDetail = () => {
    setSelectedNode(null);
  };

  // Keyboard shortcuts
  useTimelineKeyboard({
    onNavigateLeft: handleScrollLeft,
    onNavigateRight: handleScrollRight,
    onClosePanel: handleCloseDetail,
    onViewDiff: () => {
      if (selectedNode) {
        onViewDiff?.(selectedNode.id);
      }
    },
    onUndo: () => {
      if (selectedNode) {
        onUndo?.(selectedNode.id);
      }
    },
    onSearch: () => {
      // Focus search input
      const searchInput = document.querySelector('.search-input') as HTMLInputElement;
      searchInput?.focus();
    }
  }, true);

  // Empty state
  if (nodes.length === 0) {
    return (
      <div className="timeline-container">
        <div className="timeline-empty">
          <div className="empty-icon">○</div>
          <div className="empty-title">No changes yet</div>
          <div className="empty-subtitle">
            Click here or type a request to start building your app
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="timeline-container" role="region" aria-label="Feature Timeline">
      <TimelineControls
        onScrollLeft={handleScrollLeft}
        onScrollRight={handleScrollRight}
        onSearch={setSearchQuery}
        onFilterChange={setFilter}
        currentFilter={filter}
        canScrollLeft={canScrollLeft}
        canScrollRight={canScrollRight}
      />

      <div className="timeline-track" ref={scrollRef} role="list" aria-label="Timeline events">
        <div className="timeline-nodes">
          {filteredNodes.map((node, index) => (
            <div key={node.id} className="timeline-item" data-node-id={node.id} role="listitem">
              <TimelineNode
                node={node}
                isActive={activeNodeId === node.id}
                isCurrent={currentNodeId === node.id}
                onClick={() => handleNodeClick(node)}
                onHover={(hovering) => setHoveredNodeId(hovering ? node.id : null)}
              />
              {index < filteredNodes.length - 1 && (
                <TimelineConnector
                  status={
                    node.status === 'success' ? 'completed' :
                    node.status === 'failed' ? 'failed' :
                    'normal'
                  }
                  animated={node.status === 'in-progress'}
                />
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Detail Panel */}
      {selectedNode && (
        <NodeDetailPanel
          node={selectedNode}
          onClose={handleCloseDetail}
          onViewDiff={() => {
            onViewDiff?.(selectedNode.id);
            handleCloseDetail();
          }}
          onUndo={() => {
            onUndo?.(selectedNode.id);
            handleCloseDetail();
          }}
          onRestore={() => {
            onRestore?.(selectedNode.id);
            handleCloseDetail();
          }}
        />
      )}
    </div>
  );
}
