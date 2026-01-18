/**
 * Streaming Store - Persists tool events across component re-renders
 * 
 * Uses Zustand to maintain streaming state (tool events, phase) 
 * so it survives Hot Module Reload and component re-mounts.
 */

import { create } from 'zustand';
import { devtools } from 'zustand/middleware';

export interface ToolEvent {
  id: string;
  type: 'tool_start' | 'tool_result';
  tool: string;
  file?: string;
  success?: boolean;
  timestamp: number;
}

export type AgentPhase = 'idle' | 'planning' | 'coding' | 'validating' | 'fixing' | 'done' | 'error';

interface StreamingState {
  // Tool events from current run
  toolEvents: ToolEvent[];
  
  // Current agent phase
  agentPhase: AgentPhase;
  
  // Current activity text
  currentActivity: string;
  activityType: 'thinking' | 'writing' | 'reading' | 'command' | 'working';
  
  // Terminal state
  terminalOutput: string;
  showTerminal: boolean;
  
  // Human-in-the-Loop state
  awaitingConfirmation: boolean;
  planSummary: string;
  
  // Actions
  addToolEvent: (event: ToolEvent) => void;
  clearToolEvents: () => void;
  setPhase: (phase: AgentPhase) => void;
  setActivity: (activity: string, type?: StreamingState['activityType']) => void;
  
  // Terminal actions
  appendTerminalOutput: (output: string) => void;
  setTerminalOutput: (output: string) => void;
  setShowTerminal: (show: boolean) => void;
  
  // HITL actions
  setAwaitingConfirmation: (awaiting: boolean, summary?: string) => void;
  resetStreaming: () => void;
}

export const useStreamingStore = create<StreamingState>()(
  devtools(
    (set) => ({
      toolEvents: [],
      agentPhase: 'idle',
      currentActivity: '',
      activityType: 'thinking',
      
      // Terminal defaults
      terminalOutput: '',
      showTerminal: false,
      
      // HITL defaults
      awaitingConfirmation: false,
      planSummary: '',
      
      addToolEvent: (event) => 
        set((state) => {
          const newToolEvents = [...state.toolEvents, event];
          console.log('[streamingStore] addToolEvent called. New array length:', newToolEvents.length, 'Event:', event);
          return { toolEvents: newToolEvents };
        }),
      
      clearToolEvents: () => 
        set({ toolEvents: [] }),
      
      setPhase: (phase) => 
        set({ agentPhase: phase }),
      
      setActivity: (activity, type = 'thinking') => 
        set({ currentActivity: activity, activityType: type }),
        
      appendTerminalOutput: (output) =>
        set((state) => ({ terminalOutput: state.terminalOutput + output })),
        
      setTerminalOutput: (output) =>
        set({ terminalOutput: output }),
        
      setShowTerminal: (show) =>
        set({ showTerminal: show }),
      
      setAwaitingConfirmation: (awaiting, summary = '') =>
        set({ awaitingConfirmation: awaiting, planSummary: summary }),
      
      resetStreaming: () => 
        set({ 
          // Keep toolEvents - they should persist for the run
          agentPhase: 'idle', 
          currentActivity: '',
          activityType: 'thinking',
          awaitingConfirmation: false,
          planSummary: '',
        }),
    }),
    { name: 'streaming-store' }
  )
);
