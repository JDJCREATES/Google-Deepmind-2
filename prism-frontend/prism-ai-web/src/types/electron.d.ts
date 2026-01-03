
export {};

declare global {
  interface Window {
    electronAPI?: {
      openPreview: (url: string) => void;
    };
    electron?: {
      getLastProject: () => Promise<{ path: string | null }>;
      openPreview: (url: string) => Promise<{ success: boolean; error?: string }>;
      selectProjectFolder: () => Promise<{ success: boolean; path: string | null; error?: string }>;
      // ... add others if needed, but openPreview is critical now
    };
    };
  }
}
