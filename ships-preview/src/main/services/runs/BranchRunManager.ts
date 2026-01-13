/**
 * Branch Run Manager
 * 
 * Manages git branches for each agent run.
 * Creates, switches, and manages run-specific branches.
 */

import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

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

  constructor(projectPath: string) {
    this.projectPath = projectPath;
  }

  /**
   * Create a new branch for an agent run
   */
  async createRunBranch(runId: string, prompt: string): Promise<RunBranch> {
    // Generate branch name from prompt
    const slug = prompt.toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .slice(0, 30)
      .replace(/-+$/, '');
    
    const branchName = `work/${slug}-${runId}`;
    
    try {
      // Get current branch as base
      const { stdout: currentBranch } = await execAsync(
        'git rev-parse --abbrev-ref HEAD',
        { cwd: this.projectPath }
      );
      
      const baseBranch = currentBranch.trim();
      
      // Create and checkout new branch
      await execAsync(
        `git checkout -b "${branchName}"`,
        { cwd: this.projectPath }
      );
      
      const branch: RunBranch = {
        id: runId,
        name: branchName,
        baseBranch,
        createdAt: new Date().toISOString(),
        isActive: true,
      };
      
      this.activeBranches.set(runId, branch);
      console.log(`[BranchRunManager] Created branch: ${branchName}`);
      
      return branch;
    } catch (error) {
      console.error(`[BranchRunManager] Failed to create branch:`, error);
      throw error;
    }
  }

  /**
   * Switch to a run's branch
   */
  async switchToBranch(runId: string): Promise<void> {
    const branch = this.activeBranches.get(runId);
    if (!branch) {
      throw new Error(`No branch found for run: ${runId}`);
    }
    
    try {
      await execAsync(
        `git checkout "${branch.name}"`,
        { cwd: this.projectPath }
      );
      console.log(`[BranchRunManager] Switched to: ${branch.name}`);
    } catch (error) {
      console.error(`[BranchRunManager] Failed to switch branch:`, error);
      throw error;
    }
  }

  /**
   * Get the current git commit hash
   */
  async getCurrentCommit(): Promise<string> {
    try {
      const { stdout } = await execAsync(
        'git rev-parse HEAD',
        { cwd: this.projectPath }
      );
      return stdout.trim();
    } catch (error) {
      console.error(`[BranchRunManager] Failed to get commit:`, error);
      return '';
    }
  }

  /**
   * Create a commit for the current state
   */
  async createCheckpoint(message: string): Promise<string> {
    try {
      // Stage all changes
      await execAsync('git add -A', { cwd: this.projectPath });
      
      // Create commit
      await execAsync(
        `git commit -m "${message.replace(/"/g, '\\"')}"`,
        { cwd: this.projectPath }
      );
      
      return await this.getCurrentCommit();
    } catch (error) {
      // Might fail if no changes
      console.log(`[BranchRunManager] No changes to commit or error:`, error);
      return await this.getCurrentCommit();
    }
  }

  /**
   * Rollback to a specific commit
   */
  async rollbackToCommit(commitHash: string): Promise<void> {
    try {
      // Hard reset to the commit
      await execAsync(
        `git reset --hard ${commitHash}`,
        { cwd: this.projectPath }
      );
      console.log(`[BranchRunManager] Rolled back to: ${commitHash}`);
    } catch (error) {
      console.error(`[BranchRunManager] Failed to rollback:`, error);
      throw error;
    }
  }

  /**
   * Delete a run's branch
   */
  async deleteBranch(runId: string): Promise<void> {
    const branch = this.activeBranches.get(runId);
    if (!branch) return;
    
    try {
      // Switch back to base branch first
      await execAsync(
        `git checkout "${branch.baseBranch}"`,
        { cwd: this.projectPath }
      );
      
      // Delete the run branch
      await execAsync(
        `git branch -D "${branch.name}"`,
        { cwd: this.projectPath }
      );
      
      this.activeBranches.delete(runId);
      console.log(`[BranchRunManager] Deleted branch: ${branch.name}`);
    } catch (error) {
      console.error(`[BranchRunManager] Failed to delete branch:`, error);
    }
  }

  /**
   * Get all active branches
   */
  getActiveBranches(): RunBranch[] {
    return Array.from(this.activeBranches.values());
  }
}
