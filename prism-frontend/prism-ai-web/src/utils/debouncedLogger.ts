/**
 * Debounced logging utility to prevent console spam.
 * Tracks recent log messages and only emits if sufficient time has passed.
 */

interface LogEntry {
  lastTime: number;
  count: number;
}

class DebouncedLogger {
  private debounceMs: number;
  private logCache: Map<string, LogEntry>;
  private flushInterval: number | null;

  constructor(debounceMs: number = 1000) {
    this.debounceMs = debounceMs;
    this.logCache = new Map();
    this.flushInterval = null;
    
    // Periodically flush suppressed logs
    this.startFlushInterval();
  }

  private startFlushInterval() {
    this.flushInterval = window.setInterval(() => {
      this.flushSuppressed();
    }, this.debounceMs * 2);
  }

  private flushSuppressed() {
    const now = Date.now();
    
    this.logCache.forEach((entry, key) => {
      const timeSinceLastLog = now - entry.lastTime;
      
      if (entry.count > 0 && timeSinceLastLog >= this.debounceMs) {
        console.log(`${key} (×${entry.count} suppressed)`);
        entry.count = 0;
      }
    });
  }

  private shouldLog(message: string): { should: boolean; count: number } {
    const now = Date.now();
    const cached = this.logCache.get(message);

    if (!cached) {
      this.logCache.set(message, { lastTime: now, count: 0 });
      return { should: true, count: 0 };
    }

    const timeSinceLastLog = now - cached.lastTime;

    if (timeSinceLastLog >= this.debounceMs) {
      const suppressedCount = cached.count;
      cached.lastTime = now;
      cached.count = 0;
      return { should: true, count: suppressedCount };
    }

    cached.count++;
    return { should: false, count: cached.count };
  }

  log(message: string, ...args: any[]) {
    const { should, count } = this.shouldLog(message);
    
    if (should) {
      if (count > 0) {
        console.log(`${message} (×${count} suppressed)`, ...args);
      } else {
        console.log(message, ...args);
      }
    }
  }

  info(message: string, ...args: any[]) {
    const { should, count } = this.shouldLog(message);
    
    if (should) {
      if (count > 0) {
        console.info(`${message} (×${count} suppressed)`, ...args);
      } else {
        console.info(message, ...args);
      }
    }
  }

  warn(message: string, ...args: any[]) {
    const { should, count } = this.shouldLog(message);
    
    if (should) {
      if (count > 0) {
        console.warn(`${message} (×${count} suppressed)`, ...args);
      } else {
        console.warn(message, ...args);
      }
    }
  }

  error(message: string, ...args: any[]) {
    // Never debounce errors - always show them
    console.error(message, ...args);
  }

  debug(message: string, ...args: any[]) {
    const { should, count } = this.shouldLog(message);
    
    if (should) {
      if (count > 0) {
        console.debug(`${message} (×${count} suppressed)`, ...args);
      } else {
        console.debug(message, ...args);
      }
    }
  }

  destroy() {
    if (this.flushInterval) {
      window.clearInterval(this.flushInterval);
      this.flushInterval = null;
    }
    this.flushSuppressed();
  }
}

// Export singleton instance
export const debouncedLogger = new DebouncedLogger(1000);

// Export class for custom instances
export { DebouncedLogger };
