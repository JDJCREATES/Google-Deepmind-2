/**
 * Agent Service
 * 
 * Handles interaction with the backend Agent API, including streaming responses.
 * Includes artifact data from Electron for LLM context.
 * 
 * @module services/agentService
 */

export interface AgentChunk {
  // Legacy types (kept for backward compatibility if needed)
  type: 'message' | 'phase' | 'error' | 'tool_start' | 'tool_result' | 'files_created' | 'terminal_output' | 'complete' | 'plan_created' | 'plan_review' | 'thinking_start' | 'thinking' |
        // NEW STRUCTURED TYPES
        'block_start' | 'block_delta' | 'block_end' | 'activity';
  
  // Structured Block Fields
  id?: string;
  block_type?: 'text' | 'code' | 'command' | 'plan' | 'thinking' | 'tool_use' | 'error' | 'preflight' | 'cmd_output';
  title?: string;
  timestamp?: number;
  final_content?: string;
  duration_ms?: number;
  metadata?: Record<string, any>;
  
  // Legacy Helper Fields
  node?: string;
  content?: string;
  phase?: 'idle' | 'planning' | 'coding' | 'validating' | 'fixing' | 'done' | 'error';
  
  // Tool Events (for ToolProgress component)
  tool?: string;
  success?: boolean;
  file?: string;
  
  // Activity Events (for ActivityIndicator)
  agent?: string;
  message?: string;
  
  // Preview/Terminal Events
  preview?: string;
  preview_url?: string;
  files?: string[];
  command?: string;
  output?: string;
  stderr?: string;
  exit_code?: number;
  execution_mode?: string;
}

// Artifact context sent to backend
export interface ArtifactContext {
  fileTree?: {
    version: string;
    fileCount: number;
    files: Record<string, {
      language: string;
      symbols: {
        functions: Array<{ name: string; parameters: string[]; visibility: string }>;
        classes: Array<{ name: string }>;
        imports: Array<{ module: string; items: string[] }>;
        exports: string[];
      };
    }>;
  };
  dependencyGraph?: {
    version: string;
    circularDependencies: string[][];
    orphanedFiles: string[];
  };
}

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001';

/**
 * Fetch artifact context from Electron
 */
async function getArtifactContext(): Promise<ArtifactContext | null> {
  try {
    // Check if we're in Electron
    if (typeof window !== 'undefined' && (window as any).electron) {
      const electron = (window as any).electron;
      
      // Try to get artifacts
      const [fileTree, depGraph] = await Promise.all([
        electron.getFileTree?.(),
        electron.getDependencyGraph?.(),
      ]);
      
      if (fileTree || depGraph) {
        return {
          fileTree: fileTree ? {
            version: fileTree.version,
            fileCount: Object.keys(fileTree.files || {}).length,
            files: fileTree.files,
          } : undefined,
          dependencyGraph: depGraph ? {
            version: depGraph.version,
            circularDependencies: depGraph.circularDependencies || [],
            orphanedFiles: depGraph.orphanedFiles || [],
          } : undefined,
        };
      }
    }
  } catch (error) {
    console.warn('[AgentService] Failed to get artifact context:', error);
  }
  return null;
}

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
      // Fetch artifact context from Electron (if available)
      const artifactContext = await getArtifactContext();
      
      if (artifactContext) {
        console.log('[AgentService] Including artifact context with request');
      }

      const response = await fetch(`${API_BASE_URL}/agent/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          prompt,
          project_path: projectPath,
          // Include artifact context for LLM
          artifact_context: artifactContext,
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
            console.group(`[AgentService] 📥 Chunk: ${chunk.type || 'NO_TYPE'}`);
            console.log('Raw line:', line.substring(0, 200));
            console.log('Parsed object:', chunk);
            console.log('Has type:', !!chunk.type, 'Value:', chunk.type);
            console.log('Has block_type:', !!chunk.block_type, 'Value:', chunk.block_type);
            console.log('Has id:', !!chunk.id, 'Value:', chunk.id);
            console.log('Has content:', !!chunk.content, 'Length:', chunk.content?.length);
            console.groupEnd();
            onChunk(chunk);
          } catch (e) {
            console.group('[AgentService] ❌ Parse Error');
            console.error("Error:", e);
            console.error("Raw line:", line);
            console.error("Line length:", line.length);
            console.groupEnd();
          }
        }
      }
      
      console.log('[AgentService] Stream completed');
    } catch (error) {
      console.error("Agent run error:", error);
      onError(error);
    }
  },

  /**
   * Refresh artifacts in Electron before a run
   */
  async refreshArtifacts(): Promise<boolean> {
    try {
      if (typeof window !== 'undefined' && (window as any).electron) {
        const result = await (window as any).electron.generateArtifacts?.();
        return result?.success ?? false;
      }
    } catch (error) {
      console.warn('[AgentService] Failed to refresh artifacts:', error);
    }
    return false;
  },
};
