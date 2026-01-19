import { useState, useEffect } from 'react';
import { useAgentRuns } from './useAgentRuns';

export interface PreviewStatus {
    status: 'stopped' | 'starting' | 'running' | 'error';
    port: number | null;
    url: string | null;
    error: string | null;
    logs: string[];
}

export function usePreviewStatus(runId: string | null, fullId?: string) {
    const { runs } = useAgentRuns();
    const [previewStatus, setPreviewStatus] = useState<PreviewStatus>({
        status: 'stopped',
        port: null,
        url: null,
        error: null,
        logs: []
    });

    useEffect(() => {
        if (!runId && !fullId) return;

        const checkStatus = async () => {
            try {
                // Priority: Explicit fullId -> Resolved from Store -> Original runId
                let runIdForLookup = fullId;
                
                if (!runIdForLookup && runId) {
                    const run = runs.find(r => r.id === runId || r.fullId === runId);
                    runIdForLookup = run?.fullId || runId;
                }

                if (!runIdForLookup) return;

                const res = await fetch(`http://localhost:8001/preview/status?run_id=${encodeURIComponent(runIdForLookup)}`);
                if (res.ok) {
                    const data = await res.json();
                    setPreviewStatus({
                        status: (data.status || 'stopped').trim() as any,
                        port: data.port,
                        url: data.url,
                        error: data.error,
                        logs: data.logs || []
                    });
                }
            } catch (e) {
                // Silently fail on poll error (network glitch, etc)
                console.debug('[usePreviewStatus] Poll failed', e);
            }
        };

        // Initial check
        checkStatus();

        // Poll every 2s to match ProcessDashboard cadence
        const interval = setInterval(checkStatus, 2000);
        return () => clearInterval(interval);
    }, [runId, runs, fullId]); // Depend on fullId to re-poll if it resolves late

    return previewStatus;
}
