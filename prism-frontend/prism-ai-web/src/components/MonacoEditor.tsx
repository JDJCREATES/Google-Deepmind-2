import { useEffect, useRef } from 'react';
import Editor, { type OnMount } from '@monaco-editor/react';
import { useFileSystem } from '../store/fileSystem';

interface MonacoEditorProps {
  theme?: 'vs-dark' | 'light';
  height?: string | number;
  width?: string | number;
}

export default function MonacoEditor({
  theme = 'vs-dark',
  height = '100%',
  width = '100%',
}: MonacoEditorProps) {
  const { activeFile, getFile, updateFileContent } = useFileSystem();
  const editorRef = useRef<any>(null);

  const file = activeFile ? getFile(activeFile) : null;

  const handleEditorDidMount: OnMount = (editor, monaco) => {
    editorRef.current = editor;
  };

  const handleEditorChange = (value: string | undefined) => {
    if (activeFile && value !== undefined) {
      updateFileContent(activeFile, value);
    }
  };

  // Determine language capabilities based on file extension
  // Monaco usually handles this automatically if 'path' is provided correctly
  
  if (!file) {
    return (
      <div className="empty-editor-state">
        <div className="empty-state-content">
          <p>Select a file to start editing</p>
        </div>
      </div>
    );
  }

  return (
    <Editor
      height={height}
      width={width}
      path={file.path} // THIS IS KEY for multi-file support & intellisense
      defaultLanguage={undefined} // Let Monaco infer from path
      value={file.content}
      theme={theme}
      onChange={handleEditorChange}
      onMount={handleEditorDidMount}
      options={{
        minimap: { enabled: true },
        fontSize: 14,
        lineNumbers: 'on',
        roundedSelection: true,
        scrollBeyondLastLine: false,
        automaticLayout: true,
        tabSize: 2,
        wordWrap: 'on',
        padding: { top: 16 }
      }}
    />
  );
}
