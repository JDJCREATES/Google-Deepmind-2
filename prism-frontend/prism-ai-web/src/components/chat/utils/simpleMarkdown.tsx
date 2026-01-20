/**
 * Simple Markdown Formatter
 * Renders basic markdown syntax without external dependencies
 */

import React from 'react';

export function formatMarkdown(text: string | undefined | null): React.ReactNode {
  // Handle non-string inputs gracefully
  if (!text || typeof text !== 'string') return null;
  
  // Handle empty string
  if (text.trim() === '') return null;

  const lines = text.split('\n');
  const elements: React.ReactNode[] = [];
  
  lines.forEach((line, idx) => {
    // List item: - text or * text
    if (line.trim().startsWith('- ') || line.trim().startsWith('* ')) {
      const content = line.replace(/^[-*]\s+/, '');
      elements.push(
        <div key={idx} style={{ paddingLeft: '16px', marginBottom: '4px' }}>
          <span style={{ color: '#60A5FA', marginRight: '8px' }}>•</span>
          {renderInlineMarkdown(content)}
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
          {renderInlineMarkdown(numberedMatch[2])}
        </div>
      );
      return;
    }
    
    // Empty line (paragraph break)
    if (line.trim() === '') {
      elements.push(<div key={idx} style={{ height: '8px' }} />);
      return;
    }
    
    // Regular line with inline formatting
    elements.push(
      <div key={idx} style={{ marginBottom: '2px' }}>
        {renderInlineMarkdown(line)}
      </div>
    );
  });
  
  return <>{elements}</>;
}

// Helper function to render inline markdown (bold, etc.)
function renderInlineMarkdown(text: string | undefined | null): React.ReactNode {
  // Handle non-string inputs
  if (!text || typeof text !== 'string') return '';
  
  // Handle empty string
  if (text.trim() === '') return '';
  
  // Bold: **text**
  if (text.includes('**')) {
    const parts = text.split('**');
    return parts.map((part, i) => 
      i % 2 === 1 ? <strong key={i}>{part}</strong> : <React.Fragment key={i}>{part}</React.Fragment>
    );
  }
  
  return text;
}
