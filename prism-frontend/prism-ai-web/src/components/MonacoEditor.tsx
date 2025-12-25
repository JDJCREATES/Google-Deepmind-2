import Editor, { type OnMount } from '@monaco-editor/react';
import { editor } from 'monaco-editor';

interface MonacoEditorProps {
  value?: string;
  defaultValue?: string;
  language?: string;
  theme?: 'vs-dark' | 'light' | 'vs';
  height?: string | number;
  width?: string | number;
  onChange?: (value: string | undefined) => void;
  onMount?: OnMount;
  options?: editor.IStandaloneEditorConstructionOptions;
  readOnly?: boolean;
}

export default function MonacoEditor({
  value,
  defaultValue = '// Start coding...',
  language = 'typescript',
  theme = 'vs-dark',
  height = '400px',
  width = '100%',
  onChange,
  onMount,
  options = {},
  readOnly = false,
}: MonacoEditorProps) {
  const handleEditorChange = (value: string | undefined) => {
    if (onChange) {
      onChange(value);
    }
  };

  const editorOptions: editor.IStandaloneEditorConstructionOptions = {
    minimap: { enabled: true },
    fontSize: 14,
    lineNumbers: 'on',
    roundedSelection: true,
    scrollBeyondLastLine: false,
    readOnly,
    automaticLayout: true,
    ...options,
  };

  return (
    <Editor
      height={height}
      width={width}
      language={language}
      theme={theme}
      value={value}
      defaultValue={defaultValue}
      onChange={handleEditorChange}
      onMount={onMount}
      options={editorOptions}
    />
  );
}
