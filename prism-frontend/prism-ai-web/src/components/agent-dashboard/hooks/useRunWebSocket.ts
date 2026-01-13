/**
 * Run WebSocket Hook
 * 
 * Connects to the backend WebSocket for real-time run updates.
 * Automatically updates the Zustand store when events are received.
 */

import { useEffect, useRef, useCallback } from 'react';
import { useAgentRuns } from './useAgentRuns';
import type { RunStatusEvent, ScreenshotEvent } from '../types';

const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8001/ws/runs';

type RunEvent = RunStatusEvent | ScreenshotEvent;

export const useRunWebSocket = () => {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const { updateRunStatus, addScreenshot } = useAgentRuns();

  // Handle incoming messages
  const handleMessage = useCallback((event: MessageEvent) => {
    try {
      const data: RunEvent = JSON.parse(event.data);
      
      switch (data.type) {
        case 'run_status':
          updateRunStatus(
            data.runId,
            data.status,
            data.currentAgent,
            data.agentMessage,
            data.filesChanged
          );
          break;
          
        case 'screenshot_captured':
          addScreenshot(data.runId, data.screenshot);
          break;
          
        default:
          console.log('[useRunWebSocket] Unknown event type:', data);
      }
    } catch (error) {
      console.error('[useRunWebSocket] Failed to parse message:', error);
    }
  }, [updateRunStatus, addScreenshot]);

  // Connect to WebSocket
  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;
    
    console.log('[useRunWebSocket] Connecting to', WS_URL);
    
    const ws = new WebSocket(WS_URL);
    
    ws.onopen = () => {
      console.log('[useRunWebSocket] Connected');
    };
    
    ws.onmessage = handleMessage;
    
    ws.onclose = (event) => {
      console.log('[useRunWebSocket] Disconnected', event.code, event.reason);
      
      // Reconnect after 3 seconds
      reconnectTimeoutRef.current = window.setTimeout(() => {
        connect();
      }, 3000);
    };
    
    ws.onerror = (error) => {
      console.error('[useRunWebSocket] Error:', error);
    };
    
    wsRef.current = ws;
  }, [handleMessage]);

  // Disconnect
  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }
    
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
  }, []);

  // Connect on mount, disconnect on unmount
  useEffect(() => {
    connect();
    
    return () => {
      disconnect();
    };
  }, [connect, disconnect]);

  return {
    isConnected: wsRef.current?.readyState === WebSocket.OPEN,
    reconnect: connect,
    disconnect,
  };
};
