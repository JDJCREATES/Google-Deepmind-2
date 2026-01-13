/**
 * Screenshot Timeline Component
 * 
 * Horizontal scrubber showing captured screenshots as dots.
 * Hover to preview, click to rollback to that git commit.
 */

import React, { useState, useRef } from 'react';
import { Screenshot } from '../../types';
import './ScreenshotTimeline.css';

interface ScreenshotTimelineProps {
  screenshots: Screenshot[];
  onRollback: (screenshotId: string) => void;
}

export const ScreenshotTimeline: React.FC<ScreenshotTimelineProps> = ({
  screenshots,
  onRollback,
}) => {
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
  const [previewPosition, setPreviewPosition] = useState({ x: 0, y: 0 });
  const containerRef = useRef<HTMLDivElement>(null);

  // Handle mouse enter on a dot
  const handleMouseEnter = (index: number, event: React.MouseEvent) => {
    setHoveredIndex(index);
    
    // Calculate preview position
    const rect = event.currentTarget.getBoundingClientRect();
    const containerRect = containerRef.current?.getBoundingClientRect();
    
    if (containerRect) {
      setPreviewPosition({
        x: rect.left - containerRect.left + rect.width / 2,
        y: rect.top - containerRect.top,
      });
    }
  };

  // Format timestamp
  const formatTime = (timestamp: string) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    
    if (diff < 60000) return 'Just now';
    if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
    return date.toLocaleDateString();
  };

  // If no screenshots, show empty state
  if (screenshots.length === 0) {
    return (
      <div className="screenshot-timeline screenshot-timeline--empty">
        <span className="screenshot-timeline__empty-text">
          No snapshots yet. Screenshots will appear as the agent works.
        </span>
      </div>
    );
  }

  const hoveredScreenshot = hoveredIndex !== null ? screenshots[hoveredIndex] : null;

  return (
    <div className="screenshot-timeline" ref={containerRef}>
      <div className="screenshot-timeline__label">Snapshots</div>
      
      {/* Timeline Track */}
      <div className="screenshot-timeline__track">
        <div className="screenshot-timeline__line" />
        
        {screenshots.map((screenshot, index) => {
          const isLast = index === screenshots.length - 1;
          const isHovered = hoveredIndex === index;
          
          return (
            <button
              key={screenshot.id}
              className={`screenshot-timeline__dot ${isLast ? 'screenshot-timeline__dot--current' : ''} ${isHovered ? 'screenshot-timeline__dot--hovered' : ''}`}
              onMouseEnter={(e) => handleMouseEnter(index, e)}
              onMouseLeave={() => setHoveredIndex(null)}
              onClick={() => !isLast && onRollback(screenshot.id)}
              title={isLast ? 'Current state' : 'Click to rollback'}
            >
              <span className="screenshot-timeline__dot-inner" />
            </button>
          );
        })}
      </div>

      {/* Hover Preview */}
      {hoveredScreenshot && hoveredIndex !== null && (
        <div 
          className="screenshot-timeline__preview"
          style={{
            left: previewPosition.x,
            top: previewPosition.y,
          }}
        >
          {/* Thumbnail Image */}
          {hoveredScreenshot.imagePath ? (
            <img 
              src={hoveredScreenshot.imagePath} 
              alt={`Snapshot ${hoveredIndex + 1}`}
              className="screenshot-timeline__preview-image"
            />
          ) : (
            <div className="screenshot-timeline__preview-placeholder">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <rect x="3" y="3" width="18" height="18" rx="2"/>
                <circle cx="8.5" cy="8.5" r="1.5"/>
                <path d="M21 15l-5-5L5 21"/>
              </svg>
            </div>
          )}
          
          {/* Preview Info */}
          <div className="screenshot-timeline__preview-info">
            <span className="screenshot-timeline__preview-number">
              Snapshot {hoveredIndex + 1}
            </span>
            <span className="screenshot-timeline__preview-time">
              {formatTime(hoveredScreenshot.timestamp)}
            </span>
            <span className="screenshot-timeline__preview-phase">
              {hoveredScreenshot.agentPhase}
            </span>
          </div>
          
          {/* Rollback hint */}
          {hoveredIndex !== screenshots.length - 1 && (
            <div className="screenshot-timeline__preview-hint">
              Click to rollback
            </div>
          )}
        </div>
      )}

      {/* Current indicator */}
      <div className="screenshot-timeline__current-label">
        {screenshots.length} snapshot{screenshots.length !== 1 ? 's' : ''}
      </div>
    </div>
  );
};
