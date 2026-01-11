/**
 * Git Checkpoint Service
 * 
 * Production-grade git-based checkpointing for ShipS* agent system.
 * Lives in Electron where files are managed directly.
 * 
 * Features:
 * - Step checkpointing (every file write = commit)
 * - Agent run branching (ships/run/{run_id})
 * - Rollback to any step
 * - Branch merging
 * - Metadata stored in .ships/checkpoints/
 * 
 * GitHub integration ready from day one.
 */

import { execSync } from 'child_process';
import * as fs from 'fs';
import * as path from 'path';

// ============================================================================
// Types
// ============================================================================

export interface Checkpoint {
  commitHash: string;
  stepNumber: number;
  message: string;
  agent: string;
  timestamp: string;
  metadata: Record<string, any>;
  filesChanged: string[];
}

export interface AgentRun {
  runId: string;
  branchName: string;
  parentRunId?: string;
  parentStep?: number;
  startedAt: string;
  status: 'running' | 'paused' | 'complete' | 'error';
  userRequest: string;
  currentStep: number;
  checkpoints: string[]; // Commit hashes
}

// ============================================================================
// Git Checkpoint Service
// ============================================================================

export class GitCheckpointService {
  private projectPath: string;
  private shipsDir: string;
  private checkpointsDir: string;
  private runsFile: string;
  private initialized: boolean = false;

  constructor(projectPath: string) {
    this.projectPath = projectPath;
    this.shipsDir = path.join(projectPath, '.ships');
    this.checkpointsDir = path.join(this.shipsDir, 'checkpoints');
    this.runsFile = path.join(this.shipsDir, 'agent_runs.json');
  }

  /**
   * Initialize git repo if needed and create checkpoint directories.
   */
  async initialize(): Promise<boolean> {
    try {
      // Edge case: Check if project path exists
      if (!fs.existsSync(this.projectPath)) {
        console.error(`[GIT_CHECKPOINT] Project path does not exist: ${this.projectPath}`);
        return false;
      }

      // Edge case: Check if git is available
      try {
        execSync('git --version', { encoding: 'utf-8', stdio: ['pipe', 'pipe', 'pipe'] });
      } catch {
        console.error('[GIT_CHECKPOINT] Git is not installed or not in PATH');
        return false;
      }

      // Ensure .ships directories exist
      fs.mkdirSync(this.checkpointsDir, { recursive: true });

      // Check if git is initialized
      const gitDir = path.join(this.projectPath, '.git');
      if (!fs.existsSync(gitDir)) {
        // Initialize git repo
        this.runGit(['init']);
        console.log(`[GIT_CHECKPOINT] Initialized git repo at ${this.projectPath}`);

        // Configure git user for this repo if not set globally
        try {
          this.runGit(['config', 'user.email', 'agent@ships.dev']);
          this.runGit(['config', 'user.name', 'ShipS*']);
        } catch {
          // Non-fatal - global config might be set
        }

        // Create initial commit
        this.runGit(['add', '-A']);
        this.runGit([
          'commit', '-m', 'Initial ShipS* project setup',
          '--allow-empty', '--author=ShipS* <agent@ships.dev>'
        ]);
      }

      // Ensure we're on a branch (create main if needed)
      try {
        this.runGit(['rev-parse', '--abbrev-ref', 'HEAD']);
      } catch {
        this.runGit(['checkout', '-b', 'main']);
      }

      // Initialize runs file if needed
      if (!fs.existsSync(this.runsFile)) {
        fs.writeFileSync(this.runsFile, JSON.stringify({ runs: [] }, null, 2));
      }

      this.initialized = true;
      console.log(`[GIT_CHECKPOINT] Service initialized for ${this.projectPath}`);
      return true;

    } catch (e) {
      console.error(`[GIT_CHECKPOINT] Initialization failed:`, e);
      return false;
    }
  }

  /**
   * Create a checkpoint commit.
   */
  async checkpoint(
    message: string,
    stepNumber: number,
    agent: string,
    metadata: Record<string, any> = {}
  ): Promise<string | null> {
    try {
      if (!this.initialized) await this.initialize();

      // Stage all changes
      this.runGit(['add', '-A']);

      // Check if there are changes to commit
      const status = this.runGit(['status', '--porcelain']);
      if (!status.trim()) {
        console.log('[GIT_CHECKPOINT] No changes to checkpoint');
        return null;
      }

      // Create commit with structured message
      const commitMsg = `[Step ${stepNumber}] ${message}`;
      this.runGit([
        'commit', '-m', commitMsg,
        `--author=ShipS* ${agent} <${agent}@ships.dev>`
      ]);

      // Get commit hash
      const commitHash = this.runGit(['rev-parse', 'HEAD']).trim();

      // Get list of changed files
      let filesChanged: string[] = [];
      try {
        const diffOutput = this.runGit(['diff', '--name-only', 'HEAD~1', 'HEAD']);
        filesChanged = diffOutput.trim().split('\n').filter(Boolean);
      } catch {
        // First commit or other issue
      }

      // Store checkpoint metadata
      const checkpoint: Checkpoint = {
        commitHash,
        stepNumber,
        message,
        agent,
        timestamp: new Date().toISOString(),
        metadata,
        filesChanged,
      };

      const checkpointFile = path.join(this.checkpointsDir, `${commitHash.slice(0, 8)}.json`);
      fs.writeFileSync(checkpointFile, JSON.stringify(checkpoint, null, 2));

      console.log(`[GIT_CHECKPOINT] ✓ Step ${stepNumber}: ${message} (${commitHash.slice(0, 8)})`);
      return commitHash;

    } catch (e) {
      console.error(`[GIT_CHECKPOINT] Checkpoint failed:`, e);
      return null;
    }
  }

  /**
   * Create a new branch for an agent run.
   */
  async createRunBranch(
    runId: string,
    userRequest: string = '',
    parentCommit?: string
  ): Promise<AgentRun | null> {
    try {
      if (!this.initialized) await this.initialize();

      const branchName = `ships/run/${runId}`;

      if (parentCommit) {
        // Branch from specific commit
        this.runGit(['checkout', '-b', branchName, parentCommit]);
      } else {
        // Branch from current HEAD
        this.runGit(['checkout', '-b', branchName]);
      }

      // Create run record
      const run: AgentRun = {
        runId,
        branchName,
        startedAt: new Date().toISOString(),
        status: 'running',
        userRequest,
        currentStep: 0,
        checkpoints: [],
        parentStep: parentCommit ? await this.getStepFromCommit(parentCommit) : undefined,
      };

      // Save to runs file
      await this.saveRun(run);

      console.log(`[GIT_CHECKPOINT] ✓ Created branch ${branchName}`);
      return run;

    } catch (e) {
      console.error(`[GIT_CHECKPOINT] Failed to create run branch:`, e);
      return null;
    }
  }

  /**
   * Rollback to a specific step.
   */
  async rollbackToStep(stepNumber: number): Promise<boolean> {
    try {
      if (!this.initialized) await this.initialize();

      // Find commit for this step
      const commitHash = await this.findCommitForStep(stepNumber);
      if (!commitHash) {
        console.error(`[GIT_CHECKPOINT] No commit found for step ${stepNumber}`);
        return false;
      }

      // Hard reset to that commit
      this.runGit(['reset', '--hard', commitHash]);

      console.log(`[GIT_CHECKPOINT] ✓ Rolled back to step ${stepNumber} (${commitHash.slice(0, 8)})`);
      return true;

    } catch (e) {
      console.error(`[GIT_CHECKPOINT] Rollback failed:`, e);
      return false;
    }
  }

  /**
   * Merge an agent run branch into target.
   */
  async mergeRun(runId: string, targetBranch: string = 'main'): Promise<boolean> {
    try {
      if (!this.initialized) await this.initialize();

      const branchName = `ships/run/${runId}`;

      // Checkout target branch
      this.runGit(['checkout', targetBranch]);

      // Merge the run branch
      this.runGit(['merge', branchName, '--no-ff', '-m', `Merge agent run ${runId}`]);

      console.log(`[GIT_CHECKPOINT] ✓ Merged ${branchName} into ${targetBranch}`);
      return true;

    } catch (e) {
      console.error(`[GIT_CHECKPOINT] Merge failed:`, e);
      return false;
    }
  }

  /**
   * List all checkpoints.
   */
  async listCheckpoints(): Promise<Checkpoint[]> {
    const checkpoints: Checkpoint[] = [];

    if (!fs.existsSync(this.checkpointsDir)) {
      return checkpoints;
    }

    const files = fs.readdirSync(this.checkpointsDir).filter(f => f.endsWith('.json'));
    for (const file of files) {
      try {
        const content = fs.readFileSync(path.join(this.checkpointsDir, file), 'utf-8');
        checkpoints.push(JSON.parse(content));
      } catch (e) {
        console.warn(`[GIT_CHECKPOINT] Failed to read checkpoint ${file}:`, e);
      }
    }

    // Sort by step number
    checkpoints.sort((a, b) => a.stepNumber - b.stepNumber);
    return checkpoints;
  }

  /**
   * List all agent runs.
   */
  async listRuns(): Promise<AgentRun[]> {
    try {
      if (!fs.existsSync(this.runsFile)) {
        return [];
      }
      const data = JSON.parse(fs.readFileSync(this.runsFile, 'utf-8'));
      return data.runs || [];
    } catch (e) {
      console.error(`[GIT_CHECKPOINT] Failed to list runs:`, e);
      return [];
    }
  }

  /**
   * Get a specific agent run.
   */
  async getRun(runId: string): Promise<AgentRun | null> {
    const runs = await this.listRuns();
    return runs.find(r => r.runId === runId) || null;
  }

  /**
   * Update the status of an agent run.
   */
  async updateRunStatus(runId: string, status: AgentRun['status']): Promise<boolean> {
    try {
      const runs = await this.listRuns();
      const run = runs.find(r => r.runId === runId);
      if (run) {
        run.status = status;
        await this.saveRuns(runs);
        return true;
      }
      return false;
    } catch {
      return false;
    }
  }

  /**
   * Get current step number.
   */
  async getCurrentStep(): Promise<number> {
    const checkpoints = await this.listCheckpoints();
    if (checkpoints.length === 0) return 0;
    return Math.max(...checkpoints.map(c => c.stepNumber));
  }

  // =========================================================================
  // Private helpers
  // =========================================================================

  private runGit(args: string[]): string {
    try {
      return execSync(`git ${args.join(' ')}`, {
        cwd: this.projectPath,
        encoding: 'utf-8',
        stdio: ['pipe', 'pipe', 'pipe'],
      });
    } catch (e: any) {
      throw new Error(`Git command failed: ${args.join(' ')} - ${e.stderr || e.message}`);
    }
  }

  private async findCommitForStep(stepNumber: number): Promise<string | null> {
    if (!fs.existsSync(this.checkpointsDir)) return null;

    const files = fs.readdirSync(this.checkpointsDir).filter(f => f.endsWith('.json'));
    for (const file of files) {
      try {
        const content = fs.readFileSync(path.join(this.checkpointsDir, file), 'utf-8');
        const data = JSON.parse(content);
        if (data.stepNumber === stepNumber) {
          return data.commitHash;
        }
      } catch {
        // Skip invalid files
      }
    }
    return null;
  }

  private async getStepFromCommit(commitHash: string): Promise<number | undefined> {
    const shortHash = commitHash.slice(0, 8);
    const checkpointFile = path.join(this.checkpointsDir, `${shortHash}.json`);

    if (fs.existsSync(checkpointFile)) {
      try {
        const content = fs.readFileSync(checkpointFile, 'utf-8');
        return JSON.parse(content).stepNumber;
      } catch {
        return undefined;
      }
    }
    return undefined;
  }

  private async saveRun(run: AgentRun): Promise<void> {
    const runs = await this.listRuns();
    runs.push(run);
    await this.saveRuns(runs);
  }

  private async saveRuns(runs: AgentRun[]): Promise<void> {
    fs.writeFileSync(this.runsFile, JSON.stringify({ runs }, null, 2));
  }
}

// =============================================================================
// Service Cache - One instance per project
// =============================================================================

const serviceCache: Map<string, GitCheckpointService> = new Map();

export async function getCheckpointService(projectPath: string): Promise<GitCheckpointService> {
  if (!serviceCache.has(projectPath)) {
    const service = new GitCheckpointService(projectPath);
    await service.initialize();
    serviceCache.set(projectPath, service);
  }
  return serviceCache.get(projectPath)!;
}
