// Types for File System Access API
// These are not always fully typed in standard TS lib yet
export interface FileSystemHandle {
  kind: 'file' | 'directory';
  name: string;
  isSameEntry: (other: FileSystemHandle) => Promise<boolean>;
}

export interface FileSystemFileHandle extends FileSystemHandle {
  kind: 'file';
  getFile: () => Promise<File>;
  createWritable: () => Promise<FileSystemWritableFileStream>;
}

export interface FileSystemDirectoryHandle extends FileSystemHandle {
  kind: 'directory';
  getDirectoryHandle: (name: string, options?: { create?: boolean }) => Promise<FileSystemDirectoryHandle>;
  getFileHandle: (name: string, options?: { create?: boolean }) => Promise<FileSystemFileHandle>;
  removeEntry: (name: string, options?: { recursive?: boolean }) => Promise<void>;
  resolve: (possibleDescendant: FileSystemHandle) => Promise<string[] | null>;
  values: () => AsyncIterableIterator<FileSystemHandle>;
}

interface FileSystemWritableFileStream extends WritableStream {
  write: (data: string | BufferSource | Blob) => Promise<void>;
  seek: (position: number) => Promise<void>;
  truncate: (size: number) => Promise<void>;
}

// Utility to pick a directory
export const openDirectory = async (): Promise<FileSystemDirectoryHandle> => {
  // @ts-ignore - showDirectoryPicker is experimental but supported in Chrome/Edge
  return await window.showDirectoryPicker();
};

export const readFileContent = async (handle: FileSystemFileHandle): Promise<string> => {
  const file = await handle.getFile();
  return await file.text();
};

export const writeFileContent = async (handle: FileSystemFileHandle, content: string): Promise<void> => {
  const writable = await handle.createWritable();
  await writable.write(content);
  await writable.close();
};
