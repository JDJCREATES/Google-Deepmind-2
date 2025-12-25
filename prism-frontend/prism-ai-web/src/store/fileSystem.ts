import { create } from 'zustand';

export interface FileNode {
  id: string;
  name: string;
  type: 'file' | 'folder';
  children?: FileNode[];
  content?: string;
  path: string;
}

interface FileSystemState {
  files: FileNode[];
  activeFile: string | null;
  openFiles: string[];
  setFiles: (files: FileNode[]) => void;
  setActiveFile: (id: string | null) => void;
  openFile: (id: string) => void;
  closeFile: (id: string) => void;
  updateFileContent: (id: string, content: string) => void;
  getFile: (id: string) => FileNode | null;
}

const initialFiles: FileNode[] = [
  {
    id: 'root',
    name: 'src',
    type: 'folder',
    path: '/src',
    children: [
      {
        id: '1',
        name: 'main.tsx',
        type: 'file',
        path: '/src/main.tsx',
        content: `import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './index.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);`
      },
      {
        id: '2',
        name: 'App.tsx',
        type: 'file',
        path: '/src/App.tsx',
        content: `import { useState } from 'react';
import './App.css';

function App() {
  const [count, setCount] = useState(0);

  return (
    <div className="App">
      <h1>Hello World</h1>
      <button onClick={() => setCount(count + 1)}>
        count is {count}
      </button>
    </div>
  );
}

export default App;`
      },
      {
        id: '3',
        name: 'components',
        type: 'folder',
        path: '/src/components',
        children: [
          {
            id: '4',
            name: 'Button.tsx',
            type: 'file',
            path: '/src/components/Button.tsx',
            content: `export const Button = ({ children, onClick }) => (
  <button onClick={onClick}>{children}</button>
);`
          }
        ]
      },
      {
        id: '5',
        name: 'styles.css',
        type: 'file',
        path: '/src/styles.css',
        content: `.App {
  text-align: center;
  padding: 20px;
}`
      }
    ]
  }
];

// Helper to find file by ID recursively
const findFileById = (nodes: FileNode[], id: string): FileNode | null => {
  for (const node of nodes) {
    if (node.id === id) return node;
    if (node.children) {
      const found = findFileById(node.children, id);
      if (found) return found;
    }
  }
  return null;
};

// Helper to update file content
const updateFileInTree = (nodes: FileNode[], id: string, newContent: string): FileNode[] => {
  return nodes.map(node => {
    if (node.id === id) return { ...node, content: newContent };
    if (node.children) return { ...node, children: updateFileInTree(node.children, id, newContent) };
    return node;
  });
};

export const useFileSystem = create<FileSystemState>((set, get) => ({
  files: initialFiles,
  activeFile: null,
  openFiles: [],

  setFiles: (files) => set({ files }),
  
  setActiveFile: (id) => set({ activeFile: id }),
  
  openFile: (id) => {
    const { openFiles } = get();
    if (!openFiles.includes(id)) {
      set({ openFiles: [...openFiles, id], activeFile: id });
    } else {
      set({ activeFile: id });
    }
  },
  
  closeFile: (id) => {
    const { openFiles, activeFile } = get();
    const newOpenFiles = openFiles.filter(fileId => fileId !== id);
    let newActiveFile = activeFile;
    
    if (activeFile === id) {
      // If we closed the active file, switch to the last opened file or null
      newActiveFile = newOpenFiles.length > 0 ? newOpenFiles[newOpenFiles.length - 1] : null;
    }
    
    set({ openFiles: newOpenFiles, activeFile: newActiveFile });
  },

  updateFileContent: (id, content) => {
    const { files } = get();
    const newFiles = updateFileInTree(files, id, content);
    set({ files: newFiles });
  },

  getFile: (id) => {
    const { files } = get();
    return findFileById(files, id);
  }
}));
