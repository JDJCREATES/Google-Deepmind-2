/**
 * Agent Dashboard Types
 * 
 * Core type definitions for the agent run management system.
 */

// Run status enum
export type RunStatus = 'pending' | 'planning' | 'running' | 'paused' | 'completed' | 'error';

// Agent types that can work on a run
export type AgentType = 'planner' | 'coder' | 'validator' | 'fixer' | null;

/**
 * Screenshot captured during an agent run
 */
export interface Screenshot {
  id: string;
  runId: string;
  timestamp: string;
  imagePath: string;
  thumbnailPath?: string;
  gitCommitHash: string;
  agentPhase: string;
  description: string;
}

// Structured UI Block (Cursor-like)
export interface StreamBlock {
  id: string;
  type: 'text' | 'code' | 'command' | 'plan' | 'thinking' | 'tool_use' | 'error' | 'preflight' | 'cmd_output';
  title?: string;
  content: string;
  final_content?: string;  // Final content when block completes
  isComplete: boolean;
  metadata?: any;
}

// Chat Message
export interface ChatMessage {
  id: string;
  content: string;
  sender: 'user' | 'ai' | 'system';
  timestamp: Date;
  centered?: boolean;
  // Blocks for structured streaming
  blocks?: StreamBlock[];
}

// Thinking Section Data
export interface ThinkingSectionData {
  id: string;
  title: string;
  node: string;
  content: string;
  isLive: boolean;
}

/**
 * A single agent run representing a feature/branch
 */
export interface AgentRun {
  id: string;  // Short 8-char ID for UI display
  fullId: string;  // Full UUID for backend operations and port calculations
  title: string;
  prompt: string;
  branch: string;
  baseBranch: string;  // Branch this was forked from (e.g., "main")
  projectPath: string;  // Filesystem path to the project
  port: number;
  status: RunStatus;
  currentAgent: AgentType;
  agentMessage: string;
  screenshots: Screenshot[];
  filesChanged: string[];
  // Chat History
  messages: ChatMessage[];
  thinkingSections: ThinkingSectionData[];
  commitCount: number;
  createdAt: string;
  startedAt: string;
  updatedAt: string;
  // Preview status
  previewStatus?: 'running' | 'failed' | 'unknown' | 'error' | 'stopped';
  previewUrl?: string;
  previewError?: string; // New field for error messages  // e.g., "http://localhost:5173"
}

/**
 * WebSocket event for run status updates
 */
export interface RunStatusEvent {
  type: 'run_status';
  runId: string;
  status: RunStatus;
  currentAgent: AgentType;
  agentMessage: string;
  filesChanged?: string[];
}

/**
 * WebSocket event for new screenshot
 */
export interface ScreenshotEvent {
  type: 'screenshot_captured';
  runId: string;
  screenshot: Screenshot;
}

/**
 * WebSocket event for requesting a screenshot
 */
export interface RequestScreenshotEvent {
  type: 'request_screenshot';
  runId: string;
  description: string;
}

/**
 * Create run request
 */
export interface CreateRunRequest {
  prompt: string;
  title?: string;
  projectPath?: string;  // Filesystem path to project
}

/**
 * Feedback request for a run
 */
export interface FeedbackRequest {
  runId: string;
  message: string;
}

/**
 * Run actions available to user
 */
export type RunAction = 'pause' | 'resume' | 'delete' | 'rollback' | 'merge';

export interface RollbackRequest {
  runId: string;
  screenshotId: string;
  commitHash: string;
}

/**
 * Preview Status for a run
 */
export interface PreviewStatus {
  run_id: string;
  status: 'running' | 'stopped' | 'starting' | 'error';
  port?: number;
  url?: string;
  error?: string;
  logs?: string[];
  is_alive?: boolean;
}
