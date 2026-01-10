/**
 * Security Scanner - Production Grade
 *
 * Runs npm audit, depcheck, and secret detection.
 * Generates security_report.json for the project.
 */

import * as fs from 'fs';
import * as path from 'path';
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

export interface Vulnerability {
  id: string;
  package: string;
  severity: 'critical' | 'high' | 'moderate' | 'low' | 'info';
  title: string;
  recommendation?: string;
  path?: string;
  fixAvailable?: boolean;
}

export interface UnusedDependency {
  package: string;
  type: 'dependencies' | 'devDependencies';
  reason: string;
}

export interface HardcodedSecret {
  file: string;
  line: number;
  type: string;
  pattern: string;
  snippet: string;
}

export interface SecurityReport {
  version: string;
  generatedAt: string;
  projectPath: string;
  summary: {
    critical: number;
    high: number;
    moderate: number;
    low: number;
    unusedDeps: number;
    secrets: number;
  };
  vulnerabilities: Vulnerability[];
  unusedDependencies: UnusedDependency[];
  secrets: HardcodedSecret[];
  recommendations: string[];
}

// Secret patterns
const SECRET_PATTERNS = [
  { type: 'AWS Access Key', pattern: /AKIA[0-9A-Z]{16}/g },
  { type: 'AWS Secret Key', pattern: /[0-9a-zA-Z\/+]{40}/g, context: 'aws' },
  { type: 'GitHub Token', pattern: /ghp_[a-zA-Z0-9]{36}/g },
  { type: 'GitHub Token (old)', pattern: /github_pat_[a-zA-Z0-9_]{22,}/g },
  { type: 'Slack Token', pattern: /xox[baprs]-[0-9]{10,13}-[0-9]{10,13}[a-zA-Z0-9]*/g },
  { type: 'Google API Key', pattern: /AIza[0-9A-Za-z\-_]{35}/g },
  { type: 'Private Key', pattern: /-----BEGIN (?:RSA |EC |DSA )?PRIVATE KEY-----/g },
  { type: 'Generic API Key', pattern: /(?:api[_-]?key|apikey)\s*[:=]\s*['"][a-zA-Z0-9_\-]{20,}['"]/gi },
  { type: 'Generic Secret', pattern: /(?:secret|password|passwd|pwd)\s*[:=]\s*['"][^'"]{8,}['"]/gi },
  { type: 'JWT', pattern: /eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}/g },
];

const IGNORE_DIRS = new Set([
  'node_modules', '.git', '__pycache__', '.venv', 'dist', 'build', '.next'
]);

/**
 * Production security scanner
 */
export class SecurityScanner {
  private projectPath: string;

  constructor(projectPath: string) {
    this.projectPath = projectPath;
  }

  /**
   * Generate security_report.json
   */
  async generateSecurityReport(): Promise<SecurityReport> {
    const vulnerabilities = await this.runNpmAudit();
    const unusedDeps = await this.runDepcheck();
    const secrets = await this.scanForSecrets();

    const summary = {
      critical: vulnerabilities.filter(v => v.severity === 'critical').length,
      high: vulnerabilities.filter(v => v.severity === 'high').length,
      moderate: vulnerabilities.filter(v => v.severity === 'moderate').length,
      low: vulnerabilities.filter(v => v.severity === 'low').length,
      unusedDeps: unusedDeps.length,
      secrets: secrets.length,
    };

    const recommendations: string[] = [];
    if (summary.critical > 0) {
      recommendations.push(`⚠️ ${summary.critical} critical vulnerabilities require immediate attention`);
    }
    if (summary.high > 0) {
      recommendations.push(`🔴 ${summary.high} high severity vulnerabilities should be fixed soon`);
    }
    if (summary.secrets > 0) {
      recommendations.push(`🔑 ${summary.secrets} potential hardcoded secrets detected - review immediately`);
    }
    if (summary.unusedDeps > 0) {
      recommendations.push(`📦 ${summary.unusedDeps} unused dependencies can be removed`);
    }

    const report: SecurityReport = {
      version: '1.0.0',
      generatedAt: new Date().toISOString(),
      projectPath: this.projectPath,
      summary,
      vulnerabilities,
      unusedDependencies: unusedDeps,
      secrets,
      recommendations,
    };

    // Write to .ships/
    const shipsDir = path.join(this.projectPath, '.ships');
    if (!fs.existsSync(shipsDir)) {
      fs.mkdirSync(shipsDir, { recursive: true });
    }
    fs.writeFileSync(
      path.join(shipsDir, 'security_report.json'),
      JSON.stringify(report, null, 2)
    );

    return report;
  }

  /**
   * Run npm audit
   */
  private async runNpmAudit(): Promise<Vulnerability[]> {
    const vulnerabilities: Vulnerability[] = [];
    const packageJson = path.join(this.projectPath, 'package.json');

    if (!fs.existsSync(packageJson)) {
      return vulnerabilities;
    }

    try {
      const { stdout } = await execAsync('npm audit --json', {
        cwd: this.projectPath,
        timeout: 60000,
      });

      const data = JSON.parse(stdout);

      // npm audit format varies by version
      if (data.vulnerabilities) {
        // npm v7+
        for (const [name, vuln] of Object.entries(data.vulnerabilities) as any) {
          vulnerabilities.push({
            id: vuln.via?.[0]?.source || name,
            package: name,
            severity: vuln.severity,
            title: vuln.via?.[0]?.title || `Vulnerability in ${name}`,
            recommendation: vuln.fixAvailable ? 'Run npm audit fix' : 'Manual update required',
            fixAvailable: !!vuln.fixAvailable,
          });
        }
      } else if (data.advisories) {
        // npm v6
        for (const [id, advisory] of Object.entries(data.advisories) as any) {
          vulnerabilities.push({
            id,
            package: advisory.module_name,
            severity: advisory.severity,
            title: advisory.title,
            recommendation: advisory.recommendation,
          });
        }
      }
    } catch (error: any) {
      // npm audit exits with non-zero when vulnerabilities found
      if (error.stdout) {
        try {
          const data = JSON.parse(error.stdout);
          if (data.vulnerabilities) {
            for (const [name, vuln] of Object.entries(data.vulnerabilities) as any) {
              vulnerabilities.push({
                id: vuln.via?.[0]?.source || name,
                package: name,
                severity: vuln.severity,
                title: vuln.via?.[0]?.title || `Vulnerability in ${name}`,
                fixAvailable: !!vuln.fixAvailable,
              });
            }
          }
        } catch {
          console.warn('[SecurityScanner] Could not parse npm audit output');
        }
      }
    }

    return vulnerabilities;
  }

  /**
   * Run depcheck for unused dependencies
   */
  private async runDepcheck(): Promise<UnusedDependency[]> {
    const unused: UnusedDependency[] = [];
    const packageJson = path.join(this.projectPath, 'package.json');

    if (!fs.existsSync(packageJson)) {
      return unused;
    }

    try {
      const { stdout } = await execAsync('npx -y depcheck --json', {
        cwd: this.projectPath,
        timeout: 60000,
      });

      const data = JSON.parse(stdout);

      for (const pkg of data.dependencies || []) {
        unused.push({
          package: pkg,
          type: 'dependencies',
          reason: 'Not imported in code',
        });
      }

      for (const pkg of data.devDependencies || []) {
        unused.push({
          package: pkg,
          type: 'devDependencies',
          reason: 'Not imported in code',
        });
      }
    } catch (error) {
      console.warn('[SecurityScanner] depcheck failed:', error);
    }

    return unused;
  }

  /**
   * Scan for hardcoded secrets
   */
  private async scanForSecrets(): Promise<HardcodedSecret[]> {
    const secrets: HardcodedSecret[] = [];

    const scanDir = (dir: string): void => {
      const entries = fs.readdirSync(dir, { withFileTypes: true });

      for (const entry of entries) {
        if (IGNORE_DIRS.has(entry.name) || entry.name.startsWith('.')) continue;

        const fullPath = path.join(dir, entry.name);

        if (entry.isDirectory()) {
          scanDir(fullPath);
        } else if (entry.isFile()) {
          // Only scan code files
          if (!/\.(ts|tsx|js|jsx|py|json|yml|yaml|env)$/.test(entry.name)) continue;
          // Skip lock files and type defs
          if (entry.name.includes('lock') || entry.name.endsWith('.d.ts')) continue;

          try {
            const content = fs.readFileSync(fullPath, 'utf-8');
            const relativePath = path.relative(this.projectPath, fullPath).replace(/\\/g, '/');
            const lines = content.split('\n');

            for (const { type, pattern } of SECRET_PATTERNS) {
              let match;
              const regex = new RegExp(pattern.source, pattern.flags);

              while ((match = regex.exec(content)) !== null) {
                // Find line number
                const beforeMatch = content.slice(0, match.index);
                const lineNumber = (beforeMatch.match(/\n/g) || []).length + 1;
                const line = lines[lineNumber - 1] || '';

                // Skip if in comment
                if (line.trim().startsWith('//') || line.trim().startsWith('#')) continue;

                // Skip obvious false positives
                if (match[0].includes('example') || match[0].includes('placeholder')) continue;

                secrets.push({
                  file: relativePath,
                  line: lineNumber,
                  type,
                  pattern: pattern.source.slice(0, 30) + '...',
                  snippet: line.trim().slice(0, 50) + (line.length > 50 ? '...' : ''),
                });
              }
            }
          } catch {
            // Skip files we can't read
          }
        }
      }
    };

    scanDir(this.projectPath);

    return secrets.slice(0, 50); // Limit results
  }
}
