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
  isRestoringProject: boolean;
  
  // Actions
  openProjectFolder: () => Promise<void>;
  restoreLastProject: () => Promise<boolean>;
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

// ============================================================================
// SECURE PERSISTENCE USING INDEXEDDB
// ============================================================================

const DB_NAME = 'ships-project-storage';
const STORE_NAME = 'directory-handles';
const HANDLE_KEY = 'last-project-handle';

/**
 * Store directory handle in IndexedDB (secure, persists across sessions)
 */
const storeDirectoryHandle = async (handle: FileSystemDirectoryHandle): Promise<void> => {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, 1);
    
    request.onerror = () => reject(request.error);
    request.onsuccess = () => {
      const db = request.result;
      const tx = db.transaction(STORE_NAME, 'readwrite');
      const store = tx.objectStore(STORE_NAME);
      
      store.put(handle, HANDLE_KEY);
      
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    };
    
    request.onupgradeneeded = (event) => {
      const db = (event.target as IDBOpenDBRequest).result;
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME);
      }
    };
  });
};

/**
 * Retrieve directory handle from IndexedDB
 */
const getStoredDirectoryHandle = async (): Promise<FileSystemDirectoryHandle | null> => {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, 1);
    
    request.onerror = () => reject(request.error);
    request.onsuccess = () => {
      const db = request.result;
      
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        resolve(null);
        return;
      }
      
      const tx = db.transaction(STORE_NAME, 'readonly');
      const store = tx.objectStore(STORE_NAME);
      const getRequest = store.get(HANDLE_KEY);
      
      getRequest.onsuccess = () => resolve(getRequest.result || null);
      getRequest.onerror = () => reject(getRequest.error);
    };
    
    request.onupgradeneeded = (event) => {
      const db = (event.target as IDBOpenDBRequest).result;
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME);
      }
    };
  });
};

/**
 * Verify we still have permission to access a stored handle
 */
const verifyHandlePermission = async (handle: FileSystemDirectoryHandle): Promise<boolean> => {
  try {
    // @ts-ignore - queryPermission is available but not in all type definitions
    const permission = await handle.queryPermission({ mode: 'readwrite' });
    
    if (permission === 'granted') {
      return true;
    }
    
    // Try to request permission
    // @ts-ignore - requestPermission is available but not in all type definitions
    const requestResult = await handle.requestPermission({ mode: 'readwrite' });
    return requestResult === 'granted';
  } catch (error) {
    // If permissions API not available, try to access directly
    try {
      // @ts-ignore
      for await (const _ of handle.values()) {
        break; // Just test access
      }
      return true;
    } catch {
      return false;
    }
  }
};

export const useFileSystem = create<FileSystemState>((set, get) => ({
  rootHandle: null,
  files: [], // Start empty
  activeFile: null,
  openFiles: [],
  isRestoringProject: false,

  openProjectFolder: async () => {
    try {
      const handle = await openDirectory();
      const files = await buildFileTree(handle, handle.name);
      
      // Store for next time
      await storeDirectoryHandle(handle);
      
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
  
  restoreLastProject: async () => {
    try {
      set({ isRestoringProject: true });
      
      const storedHandle = await getStoredDirectoryHandle();
      
      if (!storedHandle) {
        set({ isRestoringProject: false });
        return false;
      }
      
      // Verify we still have permission
      const hasPermission = await verifyHandlePermission(storedHandle);
      
      if (!hasPermission) {
        console.log('No permission for stored directory');
        set({ isRestoringProject: false });
        return false;
      }
      
      // Rebuild the file tree
      const files = await buildFileTree(storedHandle, storedHandle.name);
      
      set({ 
        rootHandle: storedHandle,
        files: [{
          id: storedHandle.name,
          name: storedHandle.name,
          type: 'folder',
          path: storedHandle.name,
          handle: storedHandle,
          children: files
        }],
        isRestoringProject: false
      });
      
      console.log('✅ Restored last project:', storedHandle.name);
      return true;
    } catch (error) {
      console.error('Failed to restore last project:', error);
      set({ isRestoringProject: false });
      return false;
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
