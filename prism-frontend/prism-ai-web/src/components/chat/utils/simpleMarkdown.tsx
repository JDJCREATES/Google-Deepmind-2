/**
 * Simple Markdown Formatter
 * Renders basic markdown syntax without external dependencies
 */

import React from 'react';

export function formatMarkdown(text: string): React.ReactNode {
  if (!text) return null;

  const lines = text.split('\n');
  const elements: React.ReactNode[] = [];
  
  lines.forEach((line, idx) => {
    let processedLine: React.ReactNode = line;
    
    // Bold: **text**
    if (line.includes('**')) {
      const parts = line.split('**');
      processedLine = parts.map((part, i) => 
        i % 2 === 1 ? <strong key={i}>{part}</strong> : part
      );
    }
    
    // List item: - text or * text
    if (line.trim().startsWith('- ') || line.trim().startsWith('* ')) {
      elements.push(
        <div key={idx} style={{ paddingLeft: '16px', marginBottom: '4px' }}>
          <span style={{ color: '#60A5FA', marginRight: '8px' }}>•</span>
          {processedLine.toString().replace(/^[-*]\s+/, '')}
        </div>
      );
      return;
    }
    
    // Numbered list: 1. text
    const numberedMatch = line.match(/^(\d+)\.\s+(.+)/);
    if (numberedMatch) {
      elements.push(
        <div key={idx} style={{ paddingLeft: '16px', marginBottom: '4px' }}>
          <span style={{ color: '#60A5FA', marginRight: '8px', fontWeight: 'bold' }}>
            {numberedMatch[1]}.
          </span>
          {numberedMatch[2]}
        </div>
      );
      return;
    }
    
    // Empty line (paragraph break)
    if (line.trim() === '') {
      elements.push(<div key={idx} style={{ height: '8px' }} />);
      return;
    }
    
    // Regular line
    elements.push(
      <div key={idx} style={{ marginBottom: '2px' }}>
        {processedLine}
      </div>
    );
  });
  
  return <>{elements}</>;
}
