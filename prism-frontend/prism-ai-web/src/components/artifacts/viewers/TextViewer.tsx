/**
 * Text Viewer Component
 * 
 * Displays text artifacts using Monaco Editor in read-only mode.
 * 
 * @module components/artifacts/viewers/TextViewer
 */

import Editor from '@monaco-editor/react';
import type { TextDocumentArtifact } from '../../../types/artifacts';
import './TextViewer.css';

interface TextViewerProps {
  artifact: TextDocumentArtifact;
}

export default function TextViewer({ artifact }: TextViewerProps) {
  const { content, language } = artifact.data;

  return (
    <div className="text-viewer">
      <Editor
        height="100%"
        defaultLanguage={language || 'plaintext'}
        value={content}
        theme="vs-dark"
        options={{
          readOnly: true,
          minimap: { enabled: false },
          scrollBeyondLastLine: false,
          fontSize: 13,
          fontFamily: "'JetBrains Mono', 'Fira Code', Consolas, monospace",
        }}
      />
    </div>
  );
}
