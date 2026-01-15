/**
 * Git Sync Manager
 * 
 * Handles synchronization between local git repository and remote providers.
 * Supports generic git remotes with secure credential handling.
 */

import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

export interface GitRemote {
  name: string;
  url: string;
}

export interface DiffResult {
  filePath: string;
  diff: string;
  status: 'modified' | 'conflict' | 'clean';
}

export class GitSyncManager {
  private projectPath: string;
  private token: string | null = null;
  private username: string | null = null;

  constructor(projectPath: string) {
    this.projectPath = projectPath;
  }

  /**
   * Set credentials for git operations
   */
  setCredentials(username: string, token: string) {
    this.username = username;
    this.token = token;
  }

  /**
   * Get configured remotes
   */
  async getRemotes(): Promise<GitRemote[]> {
    try {
      const { stdout } = await this.execGit('git remote -v');
      const lines = stdout.trim().split('\n');
      const remotes = new Map<string, string>();
      
      lines.forEach(line => {
        const [name, url] = line.split('\t');
        if (name && url) {
          remotes.set(name, url.split(' ')[0]);
        }
      });
      
      return Array.from(remotes.entries()).map(([name, url]) => ({ name, url }));
    } catch (e) {
      return [];
    }
  }

  /**
   * Check if remote exists
   */
  async hasRemote(name: string = 'origin'): Promise<boolean> {
    try {
      await this.execGit(`git remote get-url ${name}`);
      return true;
    } catch {
      return false;
    }
  }

  /**
   * Add or update remote
   */
  async setRemote(url: string, name: string = 'origin'): Promise<void> {
    const exists = await this.hasRemote(name);
    if (exists) {
      await this.execGit(`git remote set-url ${name} ${url}`);
    } else {
      await this.execGit(`git remote add ${name} ${url}`);
    }
  }

  /**
   * Push branch to remote
   */
  async pushBranch(branch: string, remote: string = 'origin'): Promise<void> {
    // Format URL with credentials if available
    // WARNING: Using credentials in URL is not secure for logging/history
    // In production, use git credential helper
    
    if (this.token && this.username) {
        // Retrieve generic URL
        const { stdout } = await this.execGit(`git remote get-url ${remote}`);
        let url = stdout.trim();
        
        if (url.startsWith('https://')) {
            // Inject auth
            const authUrl = url.replace('https://', `https://${this.username}:${this.token}@`);
            // Push using auth URL (but don't save it to remote config)
            try {
                await this.execGit(`git push ${remote} ${branch} --set-upstream`, { 
                    env: { ...process.env, GIT_ASKPASS: 'echo' } // disabling prompt
                });
                return; 
            } catch (e) {
                // Try direct push with embedded credentials
                await this.execGit(`git push "${authUrl}" ${branch}:${branch}`);
                return;
            }
        }
    }
    
    await this.execGit(`git push ${remote} ${branch} --set-upstream`);
  }

  /**
   * Pull changes from remote
   */
  async pullBranch(branch: string, remote: string = 'origin'): Promise<void> {
    await this.execGit(`git pull ${remote} ${branch}`);
  }

  /**
   * Check for merge conflicts between two branches
   */
  async checkMergeConflicts(source: string, target: string): Promise<string[]> {
    try {
        // Dry run merge to see conflicts
        // git merge-tree write-tree source target
        // (Newer git versions)
        await this.execGit(`git merge-tree ${target} ${source}`);
        // Parse output for conflict markers if generic
        // Or simpler: git format-patch ... check? No.
        
        // Simpler approach:
        // git merge --no-commit --no-ff target
        // if fails, conflicts exist
        return []; // TODO: Implement robust conflict detection
    } catch (e) {
        return [];
    }
  }
  
  /**
   * Get file content on specific branch
   */
  async getFileContent(path: string, branch: string): Promise<string> {
    const { stdout } = await this.execGit(`git show ${branch}:${path}`);
    return stdout;
  }

  private async execGit(command: string, options: any = {}): Promise<{stdout: string, stderr: string}> {
     const result = await execAsync(command, { 
        cwd: this.projectPath, 
        ...options 
     });
     // Ensure stdout/stderr are strings (execAsync can return Buffers depending on opts)
     return {
        stdout: result.stdout.toString(),
        stderr: result.stderr.toString()
     };
  }
}
