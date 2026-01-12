/**
 * Artifact Generator - Production Orchestrator
 *
 * Orchestrates all analyzers to generate project artifacts.
 * Writes artifacts to .ships/ directory.
 */

import * as fs from 'fs';
import * as path from 'path';
import { CodeAnalyzer, FileTree } from './codeAnalyzer';
import { DependencyAnalyzer } from './dependencyAnalyzer';
import { SecurityScanner, SecurityReport } from './securityScanner';

export interface ArtifactStatus {
  fileTree: { generated: boolean; lastUpdated?: string; totalFiles?: number };
  dependencyGraph: { generated: boolean; lastUpdated?: string; totalModules?: number };
  securityReport: { generated: boolean; lastUpdated?: string; criticalCount?: number };
  callGraph: { generated: boolean; lastUpdated?: string; totalNodes?: number };
}

export interface GenerationResult {
  success: boolean;
  duration: number;
  artifacts: string[];
  errors: string[];
}

/**
 * Main artifact generator - orchestrates all analyzers
 */
export class ArtifactGenerator {
  private projectPath: string;
  private codeAnalyzer: CodeAnalyzer;
  private dependencyAnalyzer: DependencyAnalyzer;
  private securityScanner: SecurityScanner;

  constructor(projectPath: string) {
    this.projectPath = projectPath;
    this.codeAnalyzer = new CodeAnalyzer(projectPath);
    this.dependencyAnalyzer = new DependencyAnalyzer(projectPath);
    this.securityScanner = new SecurityScanner(projectPath);
  }

  /**
   * Generate all artifacts
   */
  async generateAll(): Promise<GenerationResult> {
    const startTime = Date.now();
    const artifacts: string[] = [];
    const errors: string[] = [];

    console.log(`[ArtifactGenerator] Starting generation for: ${this.projectPath}`);

    // Ensure .ships/ exists
    const shipsDir = path.join(this.projectPath, '.ships');
    if (!fs.existsSync(shipsDir)) {
      fs.mkdirSync(shipsDir, { recursive: true });
    }

    // Generate file_tree.json
    try {
      console.log('[ArtifactGenerator] Generating file_tree.json...');
      await this.codeAnalyzer.generateFileTree();
      artifacts.push('file_tree.json');
      console.log('[ArtifactGenerator] ✓ file_tree.json generated');
    } catch (error: any) {
      console.error('[ArtifactGenerator] ✗ file_tree.json failed:', error);
      errors.push(`file_tree: ${error.message}`);
    }

    // Generate dependency_graph.json
    try {
      console.log('[ArtifactGenerator] Generating dependency_graph.json...');
      await this.dependencyAnalyzer.generateDependencyGraph();
      artifacts.push('dependency_graph.json');
      console.log('[ArtifactGenerator] ✓ dependency_graph.json generated');
    } catch (error: any) {
      console.error('[ArtifactGenerator] ✗ dependency_graph.json failed:', error);
      errors.push(`dependency_graph: ${error.message}`);
    }

    // Generate security_report.json
    try {
      console.log('[ArtifactGenerator] Generating security_report.json...');
      await this.securityScanner.generateSecurityReport();
      artifacts.push('security_report.json');
      console.log('[ArtifactGenerator] ✓ security_report.json generated');
    } catch (error: any) {
      console.error('[ArtifactGenerator] ✗ security_report.json failed:', error);
      errors.push(`security_report: ${error.message}`);
    }

    // Generate call_graph.json (function-level relationships)
    try {
      console.log('[ArtifactGenerator] Generating call_graph.json...');
      await this.codeAnalyzer.generateCallGraph();
      artifacts.push('call_graph.json');
      console.log('[ArtifactGenerator] ✓ call_graph.json generated');
    } catch (error: any) {
      console.error('[ArtifactGenerator] ✗ call_graph.json failed:', error);
      errors.push(`call_graph: ${error.message}`);
    }

    const duration = Date.now() - startTime;
    console.log(`[ArtifactGenerator] Generation complete in ${duration}ms`);

    return {
      success: errors.length === 0,
      duration,
      artifacts,
      errors,
    };
  }

  /**
   * Get current artifact status
   */
  getStatus(): ArtifactStatus {
    const shipsDir = path.join(this.projectPath, '.ships');

    const getArtifactInfo = (filename: string) => {
      const filePath = path.join(shipsDir, filename);
      if (!fs.existsSync(filePath)) {
        return { generated: false };
      }

      try {
        const content = JSON.parse(fs.readFileSync(filePath, 'utf-8'));
        return {
          generated: true,
          lastUpdated: content.generatedAt,
          ...content.summary || {},
          totalFiles: content.totalFiles,
          totalModules: content.totalModules,
        };
      } catch {
        return { generated: false };
      }
    };

    return {
      fileTree: getArtifactInfo('file_tree.json'),
      dependencyGraph: getArtifactInfo('dependency_graph.json'),
      securityReport: getArtifactInfo('security_report.json'),
      callGraph: getArtifactInfo('call_graph.json'),
    };
  }

  /**
   * Read a specific artifact
   */
  getArtifact(name: string): any | null {
    const filePath = path.join(this.projectPath, '.ships', name);
    if (!fs.existsSync(filePath)) {
      return null;
    }

    try {
      return JSON.parse(fs.readFileSync(filePath, 'utf-8'));
    } catch {
      return null;
    }
  }

  /**
   * Build LLM context from artifacts
   */
  buildLLMContext(scopeFiles: string[]): string {
    const fileTree = this.getArtifact('file_tree.json') as FileTree | null;
    if (!fileTree) return '';

    const parts: string[] = [];
    const functions: string[] = [];
    const imports: string[] = [];

    // Get symbols for scope files
    for (const relativePath of scopeFiles) {
      const file = fileTree.files[relativePath];
      if (!file) continue;

      // Functions
      for (const func of file.symbols.functions) {
        const params = func.parameters.map(p => p.name).join(', ');
        const prefix = func.visibility === 'export' ? '[export] ' : '';
        const asyncPrefix = func.async ? 'async ' : '';
        functions.push(`  ${prefix}${asyncPrefix}${func.name}(${params})`);
      }

      // Imports
      for (const imp of file.symbols.imports) {
        if (imp.items.length > 0) {
          imports.push(`  from '${imp.module}': ${imp.items.join(', ')}`);
        } else {
          imports.push(`  import '${imp.module}'`);
        }
      }
    }

    if (functions.length > 0) {
      parts.push('### Valid Functions (Do NOT invent)');
      parts.push(...functions.slice(0, 20));
    }

    if (imports.length > 0) {
      parts.push('\n### Valid Imports (Use ONLY these)');
      parts.push(...imports.slice(0, 15));
    }

    // Add security warnings if critical
    const security = this.getArtifact('security_report.json') as SecurityReport | null;
    if (security && security.summary.critical > 0) {
      parts.push(`\n### ⚠️ Security Warning`);
      parts.push(`${security.summary.critical} critical vulnerabilities in dependencies`);
    }

    return parts.join('\n');
  }
}
