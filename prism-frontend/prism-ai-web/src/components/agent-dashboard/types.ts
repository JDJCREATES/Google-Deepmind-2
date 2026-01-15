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

// Chat Message
export interface ChatMessage {
  id: string;
  content: string;
  sender: 'user' | 'ai' | 'system';
  timestamp: Date;
  centered?: boolean;
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
  id: string;
  title: string;
  prompt: string;
  branch: string;
  baseBranch: string;  // Branch this was forked from (e.g., "main")
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
  updatedAt: string;
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

/**
 * Rollback request to a specific screenshot/commit
 */
export interface RollbackRequest {
  runId: string;
  screenshotId: string;
  commitHash: string;
}
