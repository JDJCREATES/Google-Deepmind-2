/**
 * Dependency Analyzer - Production Grade
 *
 * Uses dependency-cruiser to analyze module dependencies.
 * Detects circular dependencies and orphaned files.
 */

import * as fs from 'fs';
import * as path from 'path';
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

export interface DependencyNode {
  source: string;
  imports: string[];
  importedBy: string[];
  externalDeps: string[];
  coreNodeModules: string[];
}

export interface CircularDependency {
  cycle: string[];
  length: number;
}

export interface DependencyGraph {
  version: string;
  generatedAt: string;
  projectPath: string;
  totalModules: number;
  nodes: Record<string, DependencyNode>;
  circularDependencies: CircularDependency[];
  orphanedFiles: string[];
  externalPackages: string[];
}

/**
 * Production dependency analyzer using dependency-cruiser
 */
export class DependencyAnalyzer {
  private projectPath: string;

  constructor(projectPath: string) {
    this.projectPath = projectPath;
  }

  /**
   * Generate dependency_graph.json
   */
  async generateDependencyGraph(): Promise<DependencyGraph> {
    let nodes: Record<string, DependencyNode> = {};
    let circularDependencies: CircularDependency[] = [];
    const externalPackages = new Set<string>();

    // Try dependency-cruiser first
    try {
      const result = await this.runDependencyCruiser();
      nodes = result.nodes;
      circularDependencies = result.circular;
      result.external.forEach(pkg => externalPackages.add(pkg));
    } catch (error) {
      console.warn('[DependencyAnalyzer] dependency-cruiser failed, using fallback:', error);
      nodes = await this.analyzeFallback();
    }

    // Detect orphaned files
    const orphanedFiles = Object.entries(nodes)
      .filter(([_, node]) => node.importedBy.length === 0 && !node.source.includes('index'))
      .map(([source]) => source)
      .slice(0, 20);

    const graph: DependencyGraph = {
      version: '1.0.0',
      generatedAt: new Date().toISOString(),
      projectPath: this.projectPath,
      totalModules: Object.keys(nodes).length,
      nodes,
      circularDependencies,
      orphanedFiles,
      externalPackages: Array.from(externalPackages),
    };

    // Write to .ships/
    const shipsDir = path.join(this.projectPath, '.ships');
    if (!fs.existsSync(shipsDir)) {
      fs.mkdirSync(shipsDir, { recursive: true });
    }
    fs.writeFileSync(
      path.join(shipsDir, 'dependency_graph.json'),
      JSON.stringify(graph, null, 2)
    );

    return graph;
  }

  /**
   * Run dependency-cruiser via npx
   */
  private async runDependencyCruiser(): Promise<{
    nodes: Record<string, DependencyNode>;
    circular: CircularDependency[];
    external: string[];
  }> {
    const nodes: Record<string, DependencyNode> = {};
    const circular: CircularDependency[] = [];
    const external: string[] = [];

    // Find source directories
    const srcDir = fs.existsSync(path.join(this.projectPath, 'src')) ? 'src' : '.';
    
    const { stdout } = await execAsync(
      `npx -y dependency-cruiser --output-type json ${srcDir}`,
      { 
        cwd: this.projectPath, 
        timeout: 120000,
        maxBuffer: 10 * 1024 * 1024 // 10MB
      }
    );

    const data = JSON.parse(stdout);

    // Process modules
    for (const module of data.modules || []) {
      const source = module.source;
      
      nodes[source] = {
        source,
        imports: [],
        importedBy: [],
        externalDeps: [],
        coreNodeModules: [],
      };

      for (const dep of module.dependencies || []) {
        const resolved = dep.resolved || dep.module;
        
        if (dep.dependencyTypes?.includes('npm')) {
          nodes[source].externalDeps.push(dep.module);
          external.push(dep.module.split('/')[0]);
        } else if (dep.dependencyTypes?.includes('core')) {
          nodes[source].coreNodeModules.push(dep.module);
        } else if (resolved) {
          nodes[source].imports.push(resolved);
        }

        // Check for circular
        if (dep.circular) {
          circular.push({
            cycle: dep.cycle || [source, resolved],
            length: dep.cycle?.length || 2,
          });
        }
      }
    }

    // Populate importedBy
    for (const [source, node] of Object.entries(nodes)) {
      for (const imp of node.imports) {
        if (nodes[imp]) {
          nodes[imp].importedBy.push(source);
        }
      }
    }

    return { nodes, circular, external };
  }

  /**
   * Fallback: Basic import parsing
   */
  private async analyzeFallback(): Promise<Record<string, DependencyNode>> {
    const nodes: Record<string, DependencyNode> = {};

    const scanDir = async (dir: string): Promise<void> => {
      const entries = fs.readdirSync(dir, { withFileTypes: true });

      for (const entry of entries) {
        if (entry.name === 'node_modules' || entry.name.startsWith('.')) continue;

        const fullPath = path.join(dir, entry.name);

        if (entry.isDirectory()) {
          await scanDir(fullPath);
        } else if (entry.isFile() && /\.(ts|tsx|js|jsx|py)$/.test(entry.name)) {
          const relativePath = path.relative(this.projectPath, fullPath).replace(/\\/g, '/');
          const content = fs.readFileSync(fullPath, 'utf-8');
          const imports = this.extractImports(content, entry.name);

          nodes[relativePath] = {
            source: relativePath,
            imports: imports.internal,
            importedBy: [],
            externalDeps: imports.external,
            coreNodeModules: imports.core,
          };
        }
      }
    };

    await scanDir(this.projectPath);

    // Populate importedBy
    for (const [source, node] of Object.entries(nodes)) {
      for (const imp of node.imports) {
        if (nodes[imp]) {
          nodes[imp].importedBy.push(source);
        }
      }
    }

    return nodes;
  }

  /**
   * Extract imports from file content
   */
  private extractImports(content: string, filename: string): {
    internal: string[];
    external: string[];
    core: string[];
  } {
    const internal: string[] = [];
    const external: string[] = [];
    const core: string[] = [];

    const coreModules = new Set([
      'fs', 'path', 'http', 'https', 'crypto', 'os', 'child_process',
      'util', 'events', 'stream', 'buffer', 'url', 'querystring'
    ]);

    if (filename.endsWith('.py')) {
      // Python imports
      const regex = /^(?:from\s+(\S+)|import\s+(\S+))/gm;
      let match;
      while ((match = regex.exec(content)) !== null) {
        const module = match[1] || match[2];
        if (module.startsWith('.')) {
          internal.push(module);
        } else {
          external.push(module.split('.')[0]);
        }
      }
    } else {
      // JS/TS imports
      const regex = /import\s+(?:{[^}]+}|\w+|\*\s+as\s+\w+)\s+from\s+['"]([^'"]+)['"]/g;
      let match;
      while ((match = regex.exec(content)) !== null) {
        const module = match[1];
        if (module.startsWith('.')) {
          internal.push(module);
        } else if (coreModules.has(module)) {
          core.push(module);
        } else {
          external.push(module.split('/')[0]);
        }
      }

      // require() calls
      const reqRegex = /require\(['"]([^'"]+)['"]\)/g;
      while ((match = reqRegex.exec(content)) !== null) {
        const module = match[1];
        if (module.startsWith('.')) {
          internal.push(module);
        } else if (coreModules.has(module)) {
          core.push(module);
        } else {
          external.push(module.split('/')[0]);
        }
      }
    }

    return { internal, external: [...new Set(external)], core: [...new Set(core)] };
  }
}
