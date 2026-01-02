import { useEffect, useRef } from 'react';
import Editor, { type OnMount, type BeforeMount } from '@monaco-editor/react';
import { useFileSystem } from '../store/fileSystem';
import { useSettingsStore } from '../store/settingsStore';

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
  const { monaco: monacoSettings } = useSettingsStore();
  const editorRef = useRef<any>(null);

  const file = activeFile ? getFile(activeFile) : null;

  const handleEditorWillMount: BeforeMount = (monaco) => {
    // Configure TypeScript compiler options
    monaco.languages.typescript.typescriptDefaults.setCompilerOptions({
      target: monaco.languages.typescript.ScriptTarget.ESNext,
      allowNonTsExtensions: true,
      moduleResolution: monaco.languages.typescript.ModuleResolutionKind.NodeJs,
      module: monaco.languages.typescript.ModuleKind.CommonJS,
      noEmit: true,
      esModuleInterop: true,
      jsx: monaco.languages.typescript.JsxEmit.React,
      reactNamespace: "React",
      allowJs: true,
      typeRoots: ["node_modules/@types"],
    });

    // Suppress module resolution errors (red squiggles for imports)
    monaco.languages.typescript.typescriptDefaults.setDiagnosticsOptions({
        noSemanticValidation: true,
        noSyntaxValidation: false,
    });
    
    // Configure JavaScript defaults similarly
    monaco.languages.typescript.javascriptDefaults.setCompilerOptions({
        target: monaco.languages.typescript.ScriptTarget.ESNext,
        allowNonTsExtensions: true,
        allowJs: true,
        checkJs: false
    });
  };

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
      beforeMount={handleEditorWillMount}
      options={{
        minimap: { enabled: monacoSettings.minimap, scale: 0.75, renderCharacters: false },
        fontSize: monacoSettings.fontSize,
        fontFamily: "'JetBrains Mono', 'Fira Code', Consolas, 'Courier New', monospace",
        fontLigatures: true,
        lineNumbers: monacoSettings.lineNumbers,
        roundedSelection: true,
        scrollBeyondLastLine: false,
        automaticLayout: true,
        tabSize: monacoSettings.tabSize,
        wordWrap: monacoSettings.wordWrap,
        padding: { top: 16, bottom: 16 },
        cursorBlinking: 'smooth',
        cursorSmoothCaretAnimation: 'on',
        smoothScrolling: true,
        mouseWheelZoom: true,
        bracketPairColorization: { enabled: true },
        guides: {
            bracketPairs: true,
            indentation: true,
            highlightActiveBracketPair: true
        },
        suggest: {
            preview: true,
            showStatusBar: true
        },
        renderLineHighlight: 'all',
        scrollbar: {
            verticalScrollbarSize: 10,
            horizontalScrollbarSize: 10
        }
      }}
    />
  );
}
