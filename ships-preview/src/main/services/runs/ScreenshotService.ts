/**
 * Screenshot Service
 * 
 * Captures screenshots of preview windows at key moments.
 * Stores screenshots and associates them with git commits.
 */

import { BrowserWindow } from 'electron';
import * as fs from 'fs';
import * as path from 'path';
import * as crypto from 'crypto';

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

export class ScreenshotService {
  private screenshotsDir: string;

  constructor(projectPath: string) {
    this.screenshotsDir = path.join(projectPath, '.ships', 'screenshots');
    this.ensureDir();
  }

  /**
   * Ensure screenshots directory exists
   */
  private ensureDir(): void {
    if (!fs.existsSync(this.screenshotsDir)) {
      fs.mkdirSync(this.screenshotsDir, { recursive: true });
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
    const id = crypto.randomUUID().slice(0, 8);
    const timestamp = new Date().toISOString();
    
    try {
      // Capture the page
      const image = await window.webContents.capturePage();
      
      // Generate filenames
      const filename = `${runId}_${id}.png`;
      const thumbFilename = `${runId}_${id}_thumb.png`;
      const imagePath = path.join(this.screenshotsDir, filename);
      const thumbnailPath = path.join(this.screenshotsDir, thumbFilename);
      
      // Save full-size image
      fs.writeFileSync(imagePath, image.toPNG());
      
      // Create and save thumbnail (200px wide)
      const thumb = image.resize({ width: 200 });
      fs.writeFileSync(thumbnailPath, thumb.toPNG());
      
      const screenshot: Screenshot = {
        id,
        runId,
        timestamp,
        imagePath,
        thumbnailPath,
        gitCommitHash: commitHash,
        agentPhase,
        description,
      };
      
      console.log(`[ScreenshotService] Captured screenshot: ${id}`);
      
      return screenshot;
    } catch (error) {
      console.error(`[ScreenshotService] Failed to capture screenshot:`, error);
      throw error;
    }
  }

  /**
   * Get all screenshots for a run
   */
  getScreenshotsForRun(runId: string): Screenshot[] {
    // Read screenshots index file if exists
    const indexPath = path.join(this.screenshotsDir, `${runId}_index.json`);
    
    if (fs.existsSync(indexPath)) {
      try {
        return JSON.parse(fs.readFileSync(indexPath, 'utf-8'));
      } catch {
        return [];
      }
    }
    
    return [];
  }

  /**
   * Save screenshot index for a run
   */
  saveScreenshotIndex(runId: string, screenshots: Screenshot[]): void {
    const indexPath = path.join(this.screenshotsDir, `${runId}_index.json`);
    fs.writeFileSync(indexPath, JSON.stringify(screenshots, null, 2));
  }

  /**
   * Delete all screenshots for a run
   */
  deleteScreenshotsForRun(runId: string): void {
    try {
      const files = fs.readdirSync(this.screenshotsDir);
      
      for (const file of files) {
        if (file.startsWith(`${runId}_`)) {
          fs.unlinkSync(path.join(this.screenshotsDir, file));
        }
      }
      
      console.log(`[ScreenshotService] Deleted screenshots for run: ${runId}`);
    } catch (error) {
      console.error(`[ScreenshotService] Failed to delete screenshots:`, error);
    }
  }

  /**
   * Get screenshot by ID
   */
  getScreenshot(runId: string, screenshotId: string): Screenshot | undefined {
    const screenshots = this.getScreenshotsForRun(runId);
    return screenshots.find(s => s.id === screenshotId);
  }
}
