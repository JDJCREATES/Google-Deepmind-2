/**
 * File Watcher Service
 *
 * Watches project files and triggers artifact regeneration on changes.
 * Uses chokidar for efficient cross-platform file watching.
 */

import * as chokidar from 'chokidar';
import * as path from 'path';

// Interface for artifact generator (can be ArtifactService or ArtifactGenerator)
interface IArtifactGenerator {
  generateAll(): Promise<any>;
}

// Debounce timeout in ms
const DEBOUNCE_MS = 500;

// Ignore patterns
const IGNORE_PATTERNS = [
  '**/node_modules/**',
  '**/.git/**',
  '**/__pycache__/**',
  '**/.venv/**',
  '**/venv/**',
  '**/dist/**',
  '**/build/**',
  '**/.next/**',
  '**/.ships/**',
  '**/coverage/**',
  '**/*.pyc',
  '**/*.log',
];

export class FileWatcher {
  private watcher: chokidar.FSWatcher | null = null;
  private artifactGenerator: IArtifactGenerator;
  private pendingUpdate: NodeJS.Timeout | null = null;
  private onUpdateCallback: (() => void) | null = null;

  constructor(artifactGenerator: IArtifactGenerator) {
    this.artifactGenerator = artifactGenerator;
  }

  /**
   * Start watching the project directory
   */
  start(projectPath: string): void {
    if (this.watcher) {
      this.stop();
    }

    console.log(`[FILE_WATCHER] Starting watch on: ${projectPath}`);

    this.watcher = chokidar.watch(projectPath, {
      ignored: IGNORE_PATTERNS,
      persistent: true,
      ignoreInitial: true,
      awaitWriteFinish: {
        stabilityThreshold: 300,
        pollInterval: 100,
      },
    });

    // Watch for changes
    this.watcher.on('add', (filePath) => this.handleChange('add', filePath));
    this.watcher.on('change', (filePath) => this.handleChange('change', filePath));
    this.watcher.on('unlink', (filePath) => this.handleChange('unlink', filePath));

    this.watcher.on('error', (error) => {
      console.error(`[FILE_WATCHER] Error:`, error);
    });

    this.watcher.on('ready', () => {
      console.log(`[FILE_WATCHER] Ready and watching`);
    });
  }

  /**
   * Stop watching
   */
  stop(): void {
    if (this.watcher) {
      this.watcher.close();
      this.watcher = null;
      console.log(`[FILE_WATCHER] Stopped`);
    }

    if (this.pendingUpdate) {
      clearTimeout(this.pendingUpdate);
      this.pendingUpdate = null;
    }
  }

  /**
   * Set callback for when artifacts are updated
   */
  onUpdate(callback: () => void): void {
    this.onUpdateCallback = callback;
  }

  /**
   * Handle file change event (debounced)
   */
  private handleChange(type: string, filePath: string): void {
    const ext = path.extname(filePath).toLowerCase();
    
    // Only care about code files
    const codeExts = ['.py', '.ts', '.tsx', '.js', '.jsx', '.json'];
    if (!codeExts.includes(ext)) return;

    console.log(`[FILE_WATCHER] ${type}: ${filePath}`);

    // Debounce updates
    if (this.pendingUpdate) {
      clearTimeout(this.pendingUpdate);
    }

    this.pendingUpdate = setTimeout(async () => {
      this.pendingUpdate = null;
      
      try {
        console.log(`[FILE_WATCHER] Regenerating artifacts...`);
        await this.artifactGenerator.generateAll();
        
        if (this.onUpdateCallback) {
          this.onUpdateCallback();
        }
      } catch (error) {
        console.error(`[FILE_WATCHER] Artifact generation failed:`, error);
      }
    }, DEBOUNCE_MS);
  }
}
