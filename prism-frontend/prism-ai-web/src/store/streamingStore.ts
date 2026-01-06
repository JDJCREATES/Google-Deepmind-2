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
  
  // Actions
  addToolEvent: (event: ToolEvent) => void;
  clearToolEvents: () => void;
  setPhase: (phase: AgentPhase) => void;
  setActivity: (activity: string, type?: StreamingState['activityType']) => void;
  
  // Terminal actions
  appendTerminalOutput: (output: string) => void;
  setTerminalOutput: (output: string) => void;
  setShowTerminal: (show: boolean) => void;
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
      
      addToolEvent: (event) => 
        set((state) => ({ 
          toolEvents: [...state.toolEvents, event] 
        })),
      
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
      
      resetStreaming: () => 
        set({ 
          toolEvents: [], 
          agentPhase: 'idle', 
          currentActivity: '',
          activityType: 'thinking',
          // Don't reset terminal output on new run, usually we want to keep history
          // But ensure visibility is managed if needed
        }),
    }),
    { name: 'streaming-store' }
  )
);
