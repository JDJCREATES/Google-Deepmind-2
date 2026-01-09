import { useState, useEffect, useCallback } from 'react';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001';
const PROJECT_PATH_KEY = 'ships_project_path';

interface UseProjectPathResult {
  electronProjectPath: string | null;
  syncProjectPathWithBackend: (path: string) => Promise<void>;
  loading: boolean;
}

export function useProjectPath(): UseProjectPathResult {
  const [electronProjectPath, setElectronProjectPath] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const getProjectPath = useCallback(async (): Promise<string | null> => {
    // 1. Electron
    if ((window as any).electron?.getLastProject) {
      try {
        const result = await (window as any).electron.getLastProject();
        if (result.path) return result.path;
      } catch (e) {
        console.warn('[useProjectPath] Electron connection unavailable');
      }
    }
    
    // 2. LocalStorage
    const savedPath = localStorage.getItem(PROJECT_PATH_KEY);
    if (savedPath) return savedPath;
    
    // 3. Backend
    try {
      const response = await fetch(`${API_URL}/preview/path`);
      const data = await response.json();
      if (data.project_path) return data.project_path;
    } catch (e) {
      console.warn('[useProjectPath] Failed to fetch project path from backend');
    }
    
    return null;
  }, []);

  const syncProjectPathWithBackend = useCallback(async (path: string) => {
    try {
      await fetch(`${API_URL}/preview/set-path`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path })
      });
      console.log('[useProjectPath] Synced project path with backend:', path);
      localStorage.setItem(PROJECT_PATH_KEY, path);
    } catch (error) {
      console.warn('[useProjectPath] Failed to sync project path with backend:', error);
    }
  }, []);

  useEffect(() => {
    const fetchAndSync = async () => {
      setLoading(true);
      const path = await getProjectPath();
      if (path) {
        setElectronProjectPath(path);
        await syncProjectPathWithBackend(path);
      }
      setLoading(false);
    };
    fetchAndSync();
    
    // Periodic re-sync
    const syncInterval = setInterval(async () => {
      const path = await getProjectPath();
      if (path) {
        await syncProjectPathWithBackend(path);
      }
    }, 30000);
    
    return () => clearInterval(syncInterval);
  }, [getProjectPath, syncProjectPathWithBackend]);

  return { electronProjectPath, syncProjectPathWithBackend, loading };
}
