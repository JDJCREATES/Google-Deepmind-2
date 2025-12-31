
export {};

declare global {
  interface Window {
    electronAPI?: {
      openPreview: (url: string) => void;
    };
    electron?: {
      getLastProject: () => Promise<{ path: string | null }>;
    };
  }
}
