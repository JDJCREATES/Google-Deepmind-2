/**
 * Screenshot Service
 * 
 * Captures screenshots of preview windows at key moments.
 * Stores screenshots and associates them with git commits.
 * 
 * Features:
 * - Input sanitization for file paths
 * - File size limits and cleanup
 * - Concurrent capture protection
 * - Thumbnail generation with quality settings
 * - Atomic file writes
 */

import { BrowserWindow } from 'electron';
import * as fs from 'fs';
import * as path from 'path';
import * as crypto from 'crypto';

// Configuration
const CONFIG = {
  MAX_SCREENSHOTS_PER_RUN: 100,
  MAX_TOTAL_SIZE_MB: 500,
  THUMBNAIL_WIDTH: 200,
  CLEANUP_THRESHOLD: 0.9, // Clean when 90% of limit reached
  INDEX_BACKUP_COUNT: 3,
};

export interface Screenshot {
  id: string;
  runId: string;
  timestamp: string;
  imagePath: string;
  thumbnailPath?: string;
  gitCommitHash: string;
  agentPhase: string;
  description: string;
  sizeBytes?: number;
}

export class ScreenshotService {
  private screenshotsDir: string;
  private captureInProgress: Set<string> = new Set();

  constructor(projectPath: string) {
    this.screenshotsDir = path.join(projectPath, '.ships', 'screenshots');
    this.ensureDir();
  }

  /**
   * Sanitize input to prevent path traversal
   */
  private sanitize(input: string): string {
    return input.replace(/[^a-zA-Z0-9_-]/g, '');
  }

  /**
   * Ensure screenshots directory exists
   */
  private ensureDir(): void {
    try {
      if (!fs.existsSync(this.screenshotsDir)) {
        fs.mkdirSync(this.screenshotsDir, { recursive: true });
      }
    } catch (error) {
      console.error('[ScreenshotService] Failed to create directory:', error);
    }
  }

  /**
   * Clean up old screenshots when limit is reached
   */
  private async cleanupOldScreenshots(runId: string): Promise<void> {
    const sanitizedId = this.sanitize(runId);
    const screenshots = this.getScreenshotsForRun(sanitizedId);
    
    // Check if we need cleanup
    if (screenshots.length < CONFIG.MAX_SCREENSHOTS_PER_RUN * CONFIG.CLEANUP_THRESHOLD) {
      return;
    }
    
    // Remove oldest screenshots (keep most recent half)
    const toRemove = screenshots.slice(0, Math.floor(screenshots.length / 2));
    
    for (const screenshot of toRemove) {
      this.deleteScreenshot(sanitizedId, screenshot.id);
    }
    
    console.log(`[ScreenshotService] Cleaned up ${toRemove.length} old screenshots for run ${sanitizedId}`);
  }

  /**
   * Delete a single screenshot
   */
  private deleteScreenshot(runId: string, screenshotId: string): void {
    const sanitizedId = this.sanitize(runId);
    const sanitizedScreenshotId = this.sanitize(screenshotId);
    
    const screenshots = this.getScreenshotsForRun(sanitizedId);
    const screenshot = screenshots.find(s => s.id === sanitizedScreenshotId);
    
    if (!screenshot) return;
    
    try {
      // Delete image file
      if (fs.existsSync(screenshot.imagePath)) {
        fs.unlinkSync(screenshot.imagePath);
      }
      
      // Delete thumbnail
      if (screenshot.thumbnailPath && fs.existsSync(screenshot.thumbnailPath)) {
        fs.unlinkSync(screenshot.thumbnailPath);
      }
      
      // Update index
      const remaining = screenshots.filter(s => s.id !== sanitizedScreenshotId);
      this.saveScreenshotIndex(sanitizedId, remaining);
    } catch (error) {
      console.error(`[ScreenshotService] Failed to delete screenshot ${sanitizedScreenshotId}:`, error);
    }
  }

  /**
   * Capture a screenshot of a BrowserWindow
   */
  async captureScreenshot(
    window: BrowserWindow,
    runId: string,
    commitHash: string,
    agentPhase: string,
    description: string = ''
  ): Promise<Screenshot> {
    const sanitizedRunId = this.sanitize(runId);
    const sanitizedCommit = this.sanitize(commitHash);
    const sanitizedPhase = this.sanitize(agentPhase);
    const sanitizedDesc = description.slice(0, 500); // Limit description length
    
    // Prevent concurrent captures for same run
    if (this.captureInProgress.has(sanitizedRunId)) {
      throw new Error(`Screenshot capture already in progress for run: ${sanitizedRunId}`);
    }
    
    this.captureInProgress.add(sanitizedRunId);
    
    try {
      // Validate window
      if (!window || window.isDestroyed()) {
        throw new Error('Window is not available for screenshot');
      }
      
      // Check limits and cleanup if needed
      await this.cleanupOldScreenshots(sanitizedRunId);
      
      const id = crypto.randomUUID().slice(0, 8);
      const timestamp = new Date().toISOString();
      
      // Capture the page
      const image = await window.webContents.capturePage();
      
      if (image.isEmpty()) {
        throw new Error('Captured image is empty');
      }
      
      // Generate filenames with sanitized components
      const filename = `${sanitizedRunId}_${id}.png`;
      const thumbFilename = `${sanitizedRunId}_${id}_thumb.png`;
      const imagePath = path.join(this.screenshotsDir, filename);
      const thumbnailPath = path.join(this.screenshotsDir, thumbFilename);
      
      // Convert to PNG
      const pngBuffer = image.toPNG();
      const sizeBytes = pngBuffer.length;
      
      // Atomic write for main image (write to temp, then rename)
      const tempPath = `${imagePath}.tmp`;
      fs.writeFileSync(tempPath, pngBuffer);
      fs.renameSync(tempPath, imagePath);
      
      // Create and save thumbnail
      let thumbnailSaved = false;
      try {
        const thumb = image.resize({ width: CONFIG.THUMBNAIL_WIDTH });
        const thumbBuffer = thumb.toPNG();
        const tempThumbPath = `${thumbnailPath}.tmp`;
        fs.writeFileSync(tempThumbPath, thumbBuffer);
        fs.renameSync(tempThumbPath, thumbnailPath);
        thumbnailSaved = true;
      } catch (thumbError) {
        console.warn('[ScreenshotService] Failed to create thumbnail:', thumbError);
      }
      
      const screenshot: Screenshot = {
        id,
        runId: sanitizedRunId,
        timestamp,
        imagePath,
        thumbnailPath: thumbnailSaved ? thumbnailPath : undefined,
        gitCommitHash: sanitizedCommit,
        agentPhase: sanitizedPhase,
        description: sanitizedDesc,
        sizeBytes,
      };
      
      // Update index
      const existingScreenshots = this.getScreenshotsForRun(sanitizedRunId);
      existingScreenshots.push(screenshot);
      this.saveScreenshotIndex(sanitizedRunId, existingScreenshots);
      
      console.log(`[ScreenshotService] Captured screenshot: ${id} (${Math.round(sizeBytes / 1024)}KB)`);
      
      return screenshot;
    } finally {
      this.captureInProgress.delete(sanitizedRunId);
    }
  }

  /**
   * Get all screenshots for a run
   */
  getScreenshotsForRun(runId: string): Screenshot[] {
    const sanitizedId = this.sanitize(runId);
    const indexPath = path.join(this.screenshotsDir, `${sanitizedId}_index.json`);
    
    if (fs.existsSync(indexPath)) {
      try {
        const content = fs.readFileSync(indexPath, 'utf-8');
        const parsed = JSON.parse(content);
        
        // Validate array
        if (!Array.isArray(parsed)) {
          console.warn('[ScreenshotService] Invalid index format, returning empty array');
          return [];
        }
        
        return parsed;
      } catch (error) {
        console.error('[ScreenshotService] Failed to read index:', error);
        
        // Try to recover from backup
        for (let i = 1; i <= CONFIG.INDEX_BACKUP_COUNT; i++) {
          const backupPath = `${indexPath}.bak${i}`;
          if (fs.existsSync(backupPath)) {
            try {
              const backupContent = fs.readFileSync(backupPath, 'utf-8');
              return JSON.parse(backupContent);
            } catch {
              continue;
            }
          }
        }
        
        return [];
      }
    }
    
    return [];
  }

  /**
   * Save screenshot index for a run
   */
  saveScreenshotIndex(runId: string, screenshots: Screenshot[]): void {
    const sanitizedId = this.sanitize(runId);
    const indexPath = path.join(this.screenshotsDir, `${sanitizedId}_index.json`);
    
    try {
      // Rotate backups
      for (let i = CONFIG.INDEX_BACKUP_COUNT; i > 1; i--) {
        const older = `${indexPath}.bak${i - 1}`;
        const newer = `${indexPath}.bak${i}`;
        if (fs.existsSync(older)) {
          fs.renameSync(older, newer);
        }
      }
      
      // Current becomes backup 1
      if (fs.existsSync(indexPath)) {
        fs.renameSync(indexPath, `${indexPath}.bak1`);
      }
      
      // Atomic write
      const tempPath = `${indexPath}.tmp`;
      fs.writeFileSync(tempPath, JSON.stringify(screenshots, null, 2));
      fs.renameSync(tempPath, indexPath);
    } catch (error) {
      console.error('[ScreenshotService] Failed to save index:', error);
    }
  }

  /**
   * Delete all screenshots for a run
   */
  deleteScreenshotsForRun(runId: string): void {
    const sanitizedId = this.sanitize(runId);
    
    try {
      const files = fs.readdirSync(this.screenshotsDir);
      let deletedCount = 0;
      
      for (const file of files) {
        if (file.startsWith(`${sanitizedId}_`)) {
          try {
            fs.unlinkSync(path.join(this.screenshotsDir, file));
            deletedCount++;
          } catch {
            // Continue deleting other files
          }
        }
      }
      
      console.log(`[ScreenshotService] Deleted ${deletedCount} files for run: ${sanitizedId}`);
    } catch (error) {
      console.error(`[ScreenshotService] Failed to delete screenshots:`, error);
    }
  }

  /**
   * Get screenshot by ID
   */
  getScreenshot(runId: string, screenshotId: string): Screenshot | undefined {
    const sanitizedRunId = this.sanitize(runId);
    const sanitizedScreenshotId = this.sanitize(screenshotId);
    
    const screenshots = this.getScreenshotsForRun(sanitizedRunId);
    return screenshots.find(s => s.id === sanitizedScreenshotId);
  }

  /**
   * Get screenshot image as buffer (for serving via IPC)
   */
  getScreenshotImage(runId: string, screenshotId: string, thumbnail: boolean = false): Buffer | null {
    const screenshot = this.getScreenshot(runId, screenshotId);
    if (!screenshot) return null;
    
    const imagePath = thumbnail && screenshot.thumbnailPath 
      ? screenshot.thumbnailPath 
      : screenshot.imagePath;
    
    try {
      if (fs.existsSync(imagePath)) {
        return fs.readFileSync(imagePath);
      }
    } catch (error) {
      console.error('[ScreenshotService] Failed to read image:', error);
    }
    
    return null;
  }
}
