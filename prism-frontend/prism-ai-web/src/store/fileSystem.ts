import { create } from 'zustand';
import { 
  openDirectory, 
  readFileContent, 
  writeFileContent,
  type FileSystemDirectoryHandle, 
  type FileSystemFileHandle 
} from '../utils/fileSystemAccess';

export interface FileNode {
  id: string;
  name: string;
  type: 'file' | 'folder';
  children?: FileNode[];
  content?: string; // Loaded lazily or kept in memory for editor
  path: string;
  handle?: FileSystemFileHandle | FileSystemDirectoryHandle;
  isLoaded?: boolean; // For folders
}

interface FileSystemState {
  rootHandle: FileSystemDirectoryHandle | null;
  files: FileNode[];
  activeFile: string | null;
  openFiles: string[];
  
  // Actions
  openProjectFolder: () => Promise<void>;
  setActiveFile: (id: string | null) => void;
  openFile: (id: string) => Promise<void>;
  closeFile: (id: string) => void;
  saveFile: (id: string) => Promise<void>;
  updateFileContent: (id: string, content: string) => void;
  getFile: (id: string) => FileNode | null;
}

// Recursive helper to build tree from directory handle
const buildFileTree = async (
  dirHandle: FileSystemDirectoryHandle, 
  path: string
): Promise<FileNode[]> => {
  const nodes: FileNode[] = [];
  
  // iterate over the handle
  // @ts-ignore - native iteration
  for await (const entry of dirHandle.values()) {
    const entryPath = `${path}/${entry.name}`;
    const node: FileNode = {
      id: entryPath, // Use path as unique ID
      name: entry.name,
      type: entry.kind === 'directory' ? 'folder' : 'file',
      path: entryPath,
      handle: entry as FileSystemFileHandle | FileSystemDirectoryHandle
    };

    if (entry.kind === 'directory') {
      node.children = await buildFileTree(entry as FileSystemDirectoryHandle, entryPath);
    }

    nodes.push(node);
  }

  // Sort: folders first, then files
  return nodes.sort((a, b) => {
    if (a.type === b.type) return a.name.localeCompare(b.name);
    return a.type === 'folder' ? -1 : 1;
  });
};

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

// Helper to update file content in tree (immutable)
const updateFileInTree = (nodes: FileNode[], id: string, newContent: string): FileNode[] => {
  return nodes.map(node => {
    if (node.id === id) return { ...node, content: newContent };
    if (node.children) return { ...node, children: updateFileInTree(node.children, id, newContent) };
    return node;
  });
};

export const useFileSystem = create<FileSystemState>((set, get) => ({
  rootHandle: null,
  files: [], // Start empty
  activeFile: null,
  openFiles: [],

  openProjectFolder: async () => {
    try {
      const handle = await openDirectory();
      const files = await buildFileTree(handle, handle.name);
      
      set({ 
        rootHandle: handle,
        files: [{
          id: handle.name,
          name: handle.name,
          type: 'folder',
          path: handle.name,
          handle: handle,
          children: files
        }]
      });
    } catch (error) {
      console.error('Failed to open directory:', error);
      // User likely cancelled
    }
  },
  
  setActiveFile: (id) => set({ activeFile: id }),
  
  openFile: async (id) => {
    const { openFiles, files, updateFileContent } = get();
    
    // Check if content is loaded
    const fileNode = findFileById(files, id);
    if (fileNode?.type === 'file' && fileNode.handle && fileNode.content === undefined) {
      // Load content from disk
      try {
        const content = await readFileContent(fileNode.handle as FileSystemFileHandle);
        updateFileContent(id, content);
      } catch (err) {
        console.error("Failed to read file", err);
      }
    }

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
      newActiveFile = newOpenFiles.length > 0 ? newOpenFiles[newOpenFiles.length - 1] : null;
    }
    
    set({ openFiles: newOpenFiles, activeFile: newActiveFile });
  },

  updateFileContent: (id, content) => {
    const { files } = get();
    const newFiles = updateFileInTree(files, id, content);
    set({ files: newFiles });
  },
  
  saveFile: async (id) => {
    const { getFile } = get();
    const file = getFile(id);
    if (file && file.handle && file.content !== undefined) {
      try {
        await writeFileContent(file.handle as FileSystemFileHandle, file.content);
        console.log(`File ${id} saved successfully`);
      } catch (err) {
        console.error("Failed to save file", err);
      }
    }
  },

  getFile: (id) => {
    const { files } = get();
    return findFileById(files, id);
  }
}));
