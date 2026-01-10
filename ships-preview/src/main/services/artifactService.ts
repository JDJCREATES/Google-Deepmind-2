/**
 * Artifact Intelligence Service
 *
 * Scans project files and generates artifacts for LLM context.
 * Runs in Electron main process with full file system access.
 */

import * as fs from 'fs';
import * as path from 'path';
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

// Types
export interface FileEntry {
  path: string;
  size: number;
  language: string;
  symbols: {
    functions: FunctionSymbol[];
    classes: ClassSymbol[];
    imports: ImportSymbol[];
    exports: string[];
  };
}

export interface FunctionSymbol {
  name: string;
  line: number;
  visibility: 'public' | 'private' | 'export';
  parameters: string[];
}

export interface ClassSymbol {
  name: string;
  line: number;
}

export interface ImportSymbol {
  module: string;
  items: string[];
}

export interface FileTree {
  version: string;
  generatedAt: string;
  files: Record<string, FileEntry>;
}

export interface DependencyGraph {
  version: string;
  generatedAt: string;
  nodes: Record<string, {
    imports: string[];
    importedBy: string[];
    externalDeps: string[];
  }>;
  circularDependencies: string[][];
  orphanedFiles: string[];
}

// Extension to language mapping
const EXT_TO_LANG: Record<string, string> = {
  '.py': 'python',
  '.ts': 'typescript',
  '.tsx': 'typescript',
  '.js': 'javascript',
  '.jsx': 'javascript',
};

const IGNORE_DIRS = new Set([
  'node_modules', '.git', '__pycache__', '.venv', 'venv',
  'dist', 'build', '.next', '.ships', 'coverage'
]);

/**
 * Artifact Intelligence Service
 */
export class ArtifactService {
  private projectPath: string;
  private shipsDir: string;

  constructor(projectPath: string) {
    this.projectPath = projectPath;
    this.shipsDir = path.join(projectPath, '.ships');
  }

  /**
   * Initialize .ships directory
   */
  async init(): Promise<void> {
    if (!fs.existsSync(this.shipsDir)) {
      fs.mkdirSync(this.shipsDir, { recursive: true });
    }
  }

  /**
   * Generate all artifacts
   */
  async generateAll(): Promise<void> {
    await this.init();
    await Promise.all([
      this.generateFileTree(),
      this.generateDependencyGraph(),
    ]);
  }

  /**
   * Generate file_tree.json with symbols
   */
  async generateFileTree(): Promise<FileTree> {
    const files: Record<string, FileEntry> = {};

    const scanDir = async (dir: string): Promise<void> => {
      const entries = fs.readdirSync(dir, { withFileTypes: true });

      for (const entry of entries) {
        const fullPath = path.join(dir, entry.name);
        const relativePath = path.relative(this.projectPath, fullPath);

        if (entry.isDirectory()) {
          if (!IGNORE_DIRS.has(entry.name) && !entry.name.startsWith('.')) {
            await scanDir(fullPath);
          }
        } else if (entry.isFile()) {
          const ext = path.extname(entry.name).toLowerCase();
          const language = EXT_TO_LANG[ext];

          if (language) {
            const content = fs.readFileSync(fullPath, 'utf-8');
            const symbols = this.extractSymbols(content, language);

            files[relativePath] = {
              path: relativePath,
              size: content.length,
              language,
              symbols,
            };
          }
        }
      }
    };

    await scanDir(this.projectPath);

    const fileTree: FileTree = {
      version: '2.0',
      generatedAt: new Date().toISOString(),
      files,
    };

    // Save artifact
    fs.writeFileSync(
      path.join(this.shipsDir, 'file_tree.json'),
      JSON.stringify(fileTree, null, 2)
    );

    return fileTree;
  }

  /**
   * Extract symbols from source code using regex patterns
   */
  private extractSymbols(content: string, language: string): FileEntry['symbols'] {
    const functions: FunctionSymbol[] = [];
    const classes: ClassSymbol[] = [];
    const imports: ImportSymbol[] = [];
    const exports: string[] = [];

    const lines = content.split('\n');

    if (language === 'python') {
      // Python patterns
      lines.forEach((line, i) => {
        // Functions
        const funcMatch = line.match(/^(\s*)def\s+(\w+)\s*\(([^)]*)\)/);
        if (funcMatch) {
          const name = funcMatch[2];
          const params = funcMatch[3].split(',').map(p => p.trim()).filter(Boolean);
          functions.push({
            name,
            line: i + 1,
            visibility: name.startsWith('_') ? 'private' : 'public',
            parameters: params,
          });
        }

        // Classes
        const classMatch = line.match(/^class\s+(\w+)/);
        if (classMatch) {
          classes.push({ name: classMatch[1], line: i + 1 });
        }

        // Imports
        const importMatch = line.match(/^from\s+(\S+)\s+import\s+(.+)$/);
        if (importMatch) {
          imports.push({
            module: importMatch[1],
            items: importMatch[2].split(',').map(s => s.trim()),
          });
        }
      });
    } else {
      // TypeScript/JavaScript patterns
      lines.forEach((line, i) => {
        // Functions
        const funcMatch = line.match(/(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)/);
        if (funcMatch) {
          functions.push({
            name: funcMatch[1],
            line: i + 1,
            visibility: line.includes('export') ? 'export' : 'public',
            parameters: funcMatch[2].split(',').map(p => p.trim()).filter(Boolean),
          });
        }

        // Arrow functions (const name = ...)
        const arrowMatch = line.match(/(?:export\s+)?const\s+(\w+)\s*=\s*(?:async\s*)?\([^)]*\)\s*(?::\s*\w+)?\s*=>/);
        if (arrowMatch) {
          functions.push({
            name: arrowMatch[1],
            line: i + 1,
            visibility: line.includes('export') ? 'export' : 'public',
            parameters: [],
          });
        }

        // Classes
        const classMatch = line.match(/(?:export\s+)?class\s+(\w+)/);
        if (classMatch) {
          classes.push({ name: classMatch[1], line: i + 1 });
        }

        // Imports
        const importMatch = line.match(/import\s+(?:{([^}]+)}|(\w+))\s+from\s+['"]([^'"]+)['"]/);
        if (importMatch) {
          const items = importMatch[1] 
            ? importMatch[1].split(',').map(s => s.trim())
            : [importMatch[2]];
          imports.push({ module: importMatch[3], items });
        }

        // Exports
        const exportMatch = line.match(/export\s+(?:const|function|class|interface|type)\s+(\w+)/);
        if (exportMatch) {
          exports.push(exportMatch[1]);
        }
      });
    }

    return { functions, classes, imports, exports };
  }

  /**
   * Generate dependency_graph.json using dependency-cruiser if available
   */
  async generateDependencyGraph(): Promise<DependencyGraph> {
    const nodes: DependencyGraph['nodes'] = {};

    try {
      // Try using dependency-cruiser
      const { stdout } = await execAsync(
        'npx -y dependency-cruiser --output-type json src',
        { cwd: this.projectPath, timeout: 60000 }
      );

      const data = JSON.parse(stdout);
      
      for (const module of data.modules || []) {
        const source = module.source;
        nodes[source] = {
          imports: module.dependencies?.map((d: any) => d.resolved || d.module) || [],
          importedBy: [],
          externalDeps: module.dependencies
            ?.filter((d: any) => d.externalPackage)
            .map((d: any) => d.module) || [],
        };
      }

      // Populate importedBy
      for (const [source, data] of Object.entries(nodes)) {
        for (const imp of data.imports) {
          if (nodes[imp]) {
            nodes[imp].importedBy.push(source);
          }
        }
      }

    } catch {
      // Fallback: Basic import parsing
      const fileTree = await this.generateFileTree();
      
      for (const [filePath, file] of Object.entries(fileTree.files)) {
        nodes[filePath] = {
          imports: file.symbols.imports.map(i => i.module),
          importedBy: [],
          externalDeps: file.symbols.imports
            .filter(i => !i.module.startsWith('.'))
            .map(i => i.module),
        };
      }
    }

    const depGraph: DependencyGraph = {
      version: '1.0',
      generatedAt: new Date().toISOString(),
      nodes,
      circularDependencies: [],
      orphanedFiles: Object.entries(nodes)
        .filter(([_, n]) => n.importedBy.length === 0)
        .map(([p]) => p)
        .slice(0, 10),
    };

    // Save artifact
    fs.writeFileSync(
      path.join(this.shipsDir, 'dependency_graph.json'),
      JSON.stringify(depGraph, null, 2)
    );

    return depGraph;
  }

  /**
   * Get artifact for LLM context
   */
  getArtifact(name: string): any | null {
    const artifactPath = path.join(this.shipsDir, name);
    if (fs.existsSync(artifactPath)) {
      return JSON.parse(fs.readFileSync(artifactPath, 'utf-8'));
    }
    return null;
  }

  /**
   * Build context for LLM prompts
   */
  buildContext(scopeFiles: string[]): string {
    const fileTree = this.getArtifact('file_tree.json') as FileTree | null;
    if (!fileTree) return '';

    const parts: string[] = [];

    // Valid functions
    const functions: string[] = [];
    for (const filePath of scopeFiles) {
      const file = fileTree.files[filePath];
      if (file) {
        for (const func of file.symbols.functions) {
          const params = func.parameters.join(', ');
          functions.push(`  ${func.visibility === 'export' ? '[export] ' : ''}${func.name}(${params})`);
        }
      }
    }
    if (functions.length) {
      parts.push('### Valid Functions\n' + functions.join('\n'));
    }

    // Valid imports
    const imports: string[] = [];
    for (const filePath of scopeFiles) {
      const file = fileTree.files[filePath];
      if (file) {
        for (const imp of file.symbols.imports) {
          imports.push(`  from '${imp.module}': ${imp.items.join(', ')}`);
        }
      }
    }
    if (imports.length) {
      parts.push('### Valid Imports\n' + imports.join('\n'));
    }

    return parts.join('\n\n');
  }
}
