/**
 * Agent Service
 * 
 * Handles interaction with the backend Agent API, including streaming responses.
 * 
 * @module services/agentService
 */

export interface AgentChunk {
  type: 'message' | 'phase' | 'error' | 'tool_start' | 'tool_result' | 'files_created' | 'terminal_output' | 'complete';
  node?: string;
  content?: string;
  phase?: 'idle' | 'planning' | 'coding' | 'validating' | 'fixing' | 'done' | 'error';
  // Tool fields
  tool?: string;
  success?: boolean;
  file?: string;
  preview?: string;
  preview_url?: string; // For auto-launch
  // Files created (for explorer refresh)
  files?: string[];
  // Terminal output fields
  command?: string;
  output?: string;
  stderr?: string;
  exit_code?: number;
  duration_ms?: number;
  execution_mode?: string;
}

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001';

export const agentService = {
  /**
   * Run the agent with a prompt and stream responses.
   * 
   * @param prompt - User prompt
   * @param projectPath - Optional path to the user's project directory
   * @param onChunk - Callback for each streaming chunk
   * @param onError - Callback for errors
   */
  async runAgent(
    prompt: string,
    projectPath: string | null,
    onChunk: (chunk: AgentChunk) => void,
    onError: (error: any) => void
  ): Promise<void> {
    try {
      const response = await fetch(`${API_BASE_URL}/agent/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          prompt,
          project_path: projectPath 
        }),
      });

      if (!response.ok) {
        throw new Error(`Agent API failed: ${response.statusText}`);
      }

      if (!response.body) {
        throw new Error("No response body");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        
        // Handle split chunks by splitting on newlines
        const lines = buffer.split("\n");
        // Keep the last part in buffer if it's incomplete
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.trim()) continue;
          try {
            const chunk = JSON.parse(line);
            onChunk(chunk);
          } catch (e) {
            console.error("Error parsing JSON chunk:", e, line);
          }
        }
      }
    } catch (error) {
      console.error("Agent run error:", error);
      onError(error);
    }
  }
};
