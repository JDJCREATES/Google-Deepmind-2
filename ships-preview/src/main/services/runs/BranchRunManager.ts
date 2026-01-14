/**
 * Branch Run Manager
 * 
 * Manages git branches for each agent run.
 * Creates, switches, and manages run-specific branches.
 * 
 * Security: Sanitizes all user inputs before passing to shell commands.
 * Edge Cases: Handles uncommitted changes, missing branches, concurrent access.
 */

import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

// Maximum concurrent git operations
const GIT_OPERATION_TIMEOUT = 30000; // 30 seconds

export interface RunBranch {
  id: string;
  name: string;
  baseBranch: string;
  createdAt: string;
  isActive: boolean;
}

export class BranchRunManager {
  private projectPath: string;
  private activeBranches: Map<string, RunBranch> = new Map();
  private operationLock: Promise<void> = Promise.resolve();

  constructor(projectPath: string) {
    this.projectPath = projectPath;
  }

  /**
   * Sanitize input to prevent command injection
   */
  private sanitize(input: string): string {
    // Remove any shell metacharacters
    return input.replace(/[;&|`$(){}[\]<>!#*?\\'"]/g, '');
  }

  /**
   * Validate branch name format
   */
  private isValidBranchName(name: string): boolean {
    // Git branch name rules: no spaces, no .., no control chars
    return /^[a-zA-Z0-9/_-]+$/.test(name) && 
           !name.includes('..') &&
           name.length > 0 && 
           name.length <= 100;
  }

  /**
   * Execute git command with proper error handling
   */
  private async execGit(command: string): Promise<string> {
    try {
      const { stdout, stderr } = await execAsync(command, { 
        cwd: this.projectPath,
        timeout: GIT_OPERATION_TIMEOUT,
        maxBuffer: 10 * 1024 * 1024, // 10MB buffer
      });
      
      if (stderr && !stderr.includes('Switched to')) {
        console.warn(`[BranchRunManager] Git warning: ${stderr}`);
      }
      
      return stdout.trim();
    } catch (error: any) {
      // Enhance error message
      const message = error.stderr || error.message || String(error);
      throw new Error(`Git operation failed: ${message}`);
    }
  }

  /**
   * Serialize git operations to prevent race conditions
   */
  private async withLock<T>(operation: () => Promise<T>): Promise<T> {
    const previousLock = this.operationLock;
    let resolve: () => void;
    
    this.operationLock = new Promise(r => { resolve = r; });
    
    try {
      await previousLock;
      return await operation();
    } finally {
      resolve!();
    }
  }

  /**
   * Check for uncommitted changes
   */
  async hasUncommittedChanges(): Promise<boolean> {
    try {
      const status = await this.execGit('git status --porcelain');
      return status.length > 0;
    } catch {
      return false;
    }
  }

  /**
   * Stash any uncommitted changes
   */
  async stashChanges(): Promise<boolean> {
    if (!await this.hasUncommittedChanges()) {
      return false;
    }
    
    try {
      await this.execGit('git stash push -m "Auto-stash before branch operation"');
      return true;
    } catch (error) {
      console.warn('[BranchRunManager] Failed to stash changes:', error);
      return false;
    }
  }

  /**
   * Pop stashed changes
   */
  async popStash(): Promise<void> {
    try {
      await this.execGit('git stash pop');
    } catch (error) {
      console.warn('[BranchRunManager] Failed to pop stash:', error);
    }
  }

  /**
   * Create a new branch for an agent run
   */
  async createRunBranch(runId: string, prompt: string): Promise<RunBranch> {
    return this.withLock(async () => {
      // Sanitize inputs
      const sanitizedId = this.sanitize(runId);
      const sanitizedPrompt = this.sanitize(prompt);
      
      // Generate branch name - industry standard feature branch naming
      const slug = sanitizedPrompt.toLowerCase()
        .replace(/[^a-z0-9]+/g, '-')
        .slice(0, 30)
        .replace(/-+$/, '')
        .replace(/^-+/, '');
      
      const timestamp = new Date().toISOString().slice(5, 10).replace('-', ''); // MMDD format
      const branchName = `feature/ships-${slug || 'run'}-${timestamp}`;
      
      // Validate branch name
      if (!this.isValidBranchName(branchName)) {
        throw new Error(`Invalid branch name generated: ${branchName}`);
      }
      
      // Check if branch already exists
      if (this.activeBranches.has(sanitizedId)) {
        throw new Error(`Branch already exists for run: ${sanitizedId}`);
      }
      
      // Stash uncommitted changes
      const hadChanges = await this.stashChanges();
      
      try {
        // Get current branch as base
        const baseBranch = await this.execGit('git rev-parse --abbrev-ref HEAD');
        
        // Create and checkout new branch
        await this.execGit(`git checkout -b "${branchName}"`);
        
        const branch: RunBranch = {
          id: sanitizedId,
          name: branchName,
          baseBranch,
          createdAt: new Date().toISOString(),
          isActive: true,
        };
        
        this.activeBranches.set(sanitizedId, branch);
        console.log(`[BranchRunManager] Created branch: ${branchName}`);
        
        // Restore stashed changes on new branch
        if (hadChanges) {
          await this.popStash();
        }
        
        return branch;
      } catch (error) {
        // Try to restore state on failure
        if (hadChanges) {
          await this.popStash();
        }
        console.error(`[BranchRunManager] Failed to create branch:`, error);
        throw error;
      }
    });
  }

  /**
   * Switch to a run's branch
   */
  async switchToBranch(runId: string): Promise<void> {
    return this.withLock(async () => {
      const sanitizedId = this.sanitize(runId);
      const branch = this.activeBranches.get(sanitizedId);
      
      if (!branch) {
        throw new Error(`No branch found for run: ${sanitizedId}`);
      }
      
      // Stash current changes before switching
      const hadChanges = await this.stashChanges();
      
      try {
        await this.execGit(`git checkout "${branch.name}"`);
        console.log(`[BranchRunManager] Switched to: ${branch.name}`);
        
        // Pop stash on new branch (may conflict, that's ok)
        if (hadChanges) {
          await this.popStash();
        }
      } catch (error) {
        console.error(`[BranchRunManager] Failed to switch branch:`, error);
        throw error;
      }
    });
  }

  /**
   * Get the current git commit hash
   */
  async getCurrentCommit(): Promise<string> {
    try {
      return await this.execGit('git rev-parse HEAD');
    } catch (error) {
      console.error(`[BranchRunManager] Failed to get commit:`, error);
      return '';
    }
  }

  /**
   * Get current branch name
   */
  async getCurrentBranch(): Promise<string> {
    try {
      return await this.execGit('git rev-parse --abbrev-ref HEAD');
    } catch (error) {
      console.error(`[BranchRunManager] Failed to get current branch:`, error);
      return '';
    }
  }

  /**
   * Create a commit for the current state
   */
  async createCheckpoint(message: string): Promise<string> {
    return this.withLock(async () => {
      const sanitizedMessage = this.sanitize(message).slice(0, 500); // Limit message length
      
      try {
        // Check if there are changes to commit
        if (!await this.hasUncommittedChanges()) {
          console.log('[BranchRunManager] No changes to commit');
          return await this.getCurrentCommit();
        }
        
        // Stage all changes
        await this.execGit('git add -A');
        
        // Create commit with sanitized message
        await this.execGit(`git commit -m "${sanitizedMessage || 'Checkpoint'}"`);
        
        return await this.getCurrentCommit();
      } catch (error) {
        console.log(`[BranchRunManager] Commit failed:`, error);
        return await this.getCurrentCommit();
      }
    });
  }

  /**
   * Rollback to a specific commit
   */
  async rollbackToCommit(commitHash: string): Promise<void> {
    return this.withLock(async () => {
      // Validate commit hash format (40 char hex or short hash)
      const sanitizedHash = this.sanitize(commitHash);
      if (!/^[a-f0-9]{7,40}$/i.test(sanitizedHash)) {
        throw new Error(`Invalid commit hash format: ${commitHash}`);
      }
      
      try {
        // Verify commit exists
        await this.execGit(`git cat-file -t ${sanitizedHash}`);
        
        // Hard reset to the commit
        await this.execGit(`git reset --hard ${sanitizedHash}`);
        console.log(`[BranchRunManager] Rolled back to: ${sanitizedHash}`);
      } catch (error) {
        console.error(`[BranchRunManager] Failed to rollback:`, error);
        throw error;
      }
    });
  }

  /**
   * Delete a run's branch
   */
  async deleteBranch(runId: string): Promise<void> {
    return this.withLock(async () => {
      const sanitizedId = this.sanitize(runId);
      const branch = this.activeBranches.get(sanitizedId);
      
      if (!branch) {
        console.log(`[BranchRunManager] No branch to delete for run: ${sanitizedId}`);
        return;
      }
      
      try {
        // Check if we're currently on this branch
        const currentBranch = await this.getCurrentBranch();
        
        if (currentBranch === branch.name) {
          // Switch back to base branch first
          await this.execGit(`git checkout "${branch.baseBranch}"`);
        }
        
        // Delete the run branch
        await this.execGit(`git branch -D "${branch.name}"`);
        
        this.activeBranches.delete(sanitizedId);
        console.log(`[BranchRunManager] Deleted branch: ${branch.name}`);
      } catch (error) {
        // Remove from tracking even if delete fails
        this.activeBranches.delete(sanitizedId);
        console.error(`[BranchRunManager] Failed to delete branch:`, error);
      }
    });
  }

  /**
   * Get all active branches
   */
  getActiveBranches(): RunBranch[] {
    return Array.from(this.activeBranches.values());
  }

  /**
   * Get branch for a specific run
   */
  getBranch(runId: string): RunBranch | undefined {
    return this.activeBranches.get(this.sanitize(runId));
  }

  /**
   * Clean up all branches (for shutdown)
   */
  async cleanup(): Promise<void> {
    for (const [runId] of this.activeBranches) {
      try {
        await this.deleteBranch(runId);
      } catch {
        // Ignore errors during cleanup
      }
    }
  }
}
