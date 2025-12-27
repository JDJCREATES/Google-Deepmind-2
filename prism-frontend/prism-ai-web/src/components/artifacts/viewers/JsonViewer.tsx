/**
 * JSON Viewer Component
 * 
 * Generic fallback viewer for artifacts that don't have a specific visualization.
 * Uses Monaco Editor in read-only mode to show the raw JSON data.
 * 
 * @module components/artifacts/viewers/JsonViewer
 */

import { useState } from 'react';
import Editor from '@monaco-editor/react';
import './JsonViewer.css';

interface JsonViewerProps {
  data: any;
  onSave?: (newData: any) => Promise<void>;
  isEditable?: boolean;
}

export default function JsonViewer({ data, onSave, isEditable = false }: JsonViewerProps) {
  const [value, setValue] = useState(JSON.stringify(data, null, 2));
  const [isDirty, setIsDirty] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleEditorChange = (newValue: string | undefined) => {
    if (newValue !== undefined) {
      setValue(newValue);
      setIsDirty(newValue !== JSON.stringify(data, null, 2));
      
      try {
        JSON.parse(newValue);
        setError(null);
      } catch (e) {
         // @ts-ignore
        setError(e.message);
      }
    }
  };

  const handleSave = async () => {
    if (error || !isDirty || !onSave) return;
    
    try {
      const parsed = JSON.parse(value);
      await onSave(parsed);
      setIsDirty(false);
    } catch (e) {
      console.error("Save failed", e);
    }
  };
  return (
    <div className="json-viewer">
      <div className="json-viewer-header">
        <span>Raw Data Preview</span>
        {isEditable && onSave && (
          <button 
            className="save-json-btn" 
            disabled={!isDirty || !!error}
            onClick={handleSave}
          >
            {isDirty ? 'Save Changes' : 'Saved'}
          </button>
        )}
      </div>
      {error && <div className="json-error">{error}</div>}
      <div className="json-editor-container">
        <Editor
          height="100%"
          defaultLanguage="json"
          value={value}
          theme="vs-dark"
          onChange={handleEditorChange}
          options={{
            readOnly: !isEditable,
            minimap: { enabled: false },
            scrollBeyondLastLine: false,
            fontSize: 13,
            lineNumbers: 'off',
            folding: true,
          }}
        />
      </div>
    </div>
  );
}
