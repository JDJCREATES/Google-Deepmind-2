/**
 * Mermaid Viewer Component
 * 
 * Renders Mermaid diagrams from text definitions.
 * 
 * @module components/artifacts/viewers/MermaidViewer
 */

import { useEffect, useRef, useState } from 'react';
import mermaid from 'mermaid';
import './MermaidViewer.css';

mermaid.initialize({
  startOnLoad: true,
  theme: 'dark',
  securityLevel: 'loose',
});

interface MermaidViewerProps {
  definition: string;
}

export default function MermaidViewer({ definition }: MermaidViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [svg, setSvg] = useState<string>('');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const renderDiagram = async () => {
      if (!definition) return;
      
      try {
        setError(null);
        // Generate a unique ID for the diagram
        const id = `mermaid-${Math.random().toString(36).substr(2, 9)}`;
        const { svg } = await mermaid.render(id, definition);
        setSvg(svg);
      } catch (err) {
        console.error('Mermaid render error:', err);
        setError('Failed to render diagram. Syntax might be invalid.');
      }
    };

    renderDiagram();
  }, [definition]);

  return (
    <div className="mermaid-viewer" ref={containerRef}>
      {error ? (
        <div className="mermaid-error">
          <p>{error}</p>
          <pre>{definition}</pre>
        </div>
      ) : (
        <div 
          className="mermaid-svg-container"
          dangerouslySetInnerHTML={{ __html: svg }} 
        />
      )}
    </div>
  );
}
