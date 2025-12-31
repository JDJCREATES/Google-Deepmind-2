import { useEffect, useRef, useCallback } from 'react';
import * as monaco from 'monaco-editor';

/**
 * Monaco Diagnostics Hook
 * 
 * Listens to Monaco editor markers (errors, warnings) and reports them
 * to the backend for the Fixer agent to consume.
 * 
 * Features:
 * - Debounced reporting (500ms after last change)
 * - Only reports errors (not warnings/hints)
 * - Secure: Uses localhost backend endpoint
 */

interface DiagnosticError {
  file: string;
  line: number;
  column: number;
  message: string;
  severity: string;
  code?: string;
  source?: string;
}

interface UseMonacoDiagnosticsOptions {
  projectPath?: string;
  apiUrl?: string;
  debounceMs?: number;
  enabled?: boolean;
}

export function useMonacoDiagnostics({
  projectPath,
  apiUrl = 'http://localhost:8001',
  debounceMs = 500,
  enabled = true,
}: UseMonacoDiagnosticsOptions = {}) {
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastErrorCountRef = useRef<number>(0);

  const reportDiagnostics = useCallback(async (errors: DiagnosticError[]) => {
    if (!projectPath || !enabled) return;
    
    try {
      await fetch(`${apiUrl}/diagnostics/report`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project_path: projectPath,
          errors,
        }),
      });
    } catch (error) {
      console.error('[Monaco Diagnostics] Failed to report:', error);
    }
  }, [projectPath, apiUrl, enabled]);

  const handleMarkersChange = useCallback(() => {
    if (!enabled) return;
    
    // Clear pending report
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }

    // Debounce the report
    timeoutRef.current = setTimeout(() => {
      // Get all markers from Monaco
      const allMarkers = monaco.editor.getModelMarkers({});
      
      // Filter to only errors
      const errors = allMarkers
        .filter(marker => marker.severity === monaco.MarkerSeverity.Error)
        .map(marker => ({
          file: marker.resource.path,
          line: marker.startLineNumber,
          column: marker.startColumn,
          message: marker.message,
          severity: 'error',
          code: marker.code?.toString() || undefined,
          source: marker.source || undefined,
        }));

      // Only report if error count changed (avoid spamming)
      if (errors.length !== lastErrorCountRef.current) {
        lastErrorCountRef.current = errors.length;
        reportDiagnostics(errors);
        
        if (errors.length > 0) {
          console.log(`[Monaco Diagnostics] Reporting ${errors.length} errors`);
        }
      }
    }, debounceMs);
  }, [enabled, debounceMs, reportDiagnostics]);

  useEffect(() => {
    if (!enabled) return;

    // Subscribe to marker changes
    const disposable = monaco.editor.onDidChangeMarkers(handleMarkersChange);

    return () => {
      disposable.dispose();
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, [enabled, handleMarkersChange]);

  // Clear diagnostics when component unmounts
  useEffect(() => {
    return () => {
      if (projectPath) {
        fetch(`${apiUrl}/diagnostics/clear?project_path=${encodeURIComponent(projectPath)}`, {
          method: 'POST',
        }).catch(() => {});
      }
    };
  }, [projectPath, apiUrl]);

  return {
    clearDiagnostics: useCallback(() => {
      if (projectPath) {
        fetch(`${apiUrl}/diagnostics/clear?project_path=${encodeURIComponent(projectPath)}`, {
          method: 'POST',
        }).catch(() => {});
      }
    }, [projectPath, apiUrl]),
  };
}

export default useMonacoDiagnostics;
