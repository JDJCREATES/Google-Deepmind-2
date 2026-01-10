/**
 * Code Analyzer - Production Grade
 *
 * Uses web-tree-sitter for accurate AST parsing.
 * Extracts functions, classes, imports, exports from source files.
 */

import * as fs from 'fs';
import * as path from 'path';
import * as crypto from 'crypto';

// Types
export interface FunctionSymbol {
  name: string;
  line: number;
  endLine: number;
  visibility: 'public' | 'private' | 'protected' | 'export';
  async: boolean;
  parameters: ParameterInfo[];
  returnType?: string;
}

export interface ParameterInfo {
  name: string;
  type?: string;
  optional?: boolean;
  defaultValue?: string;
}

export interface ClassSymbol {
  name: string;
  line: number;
  endLine: number;
  extends?: string;
  implements?: string[];
  methods: FunctionSymbol[];
  properties: PropertySymbol[];
}

export interface PropertySymbol {
  name: string;
  line: number;
  visibility: 'public' | 'private' | 'protected';
  type?: string;
  static?: boolean;
}

export interface ImportSymbol {
  module: string;
  items: string[];
  isDefault: boolean;
  isNamespace: boolean;
  line: number;
}

export interface ExportSymbol {
  name: string;
  kind: 'function' | 'class' | 'variable' | 'type' | 'default';
  line: number;
}

export interface FileAnalysis {
  path: string;
  relativePath: string;
  language: string;
  size: number;
  hash: string;
  lastModified: number;
  symbols: {
    functions: FunctionSymbol[];
    classes: ClassSymbol[];
    imports: ImportSymbol[];
    exports: ExportSymbol[];
  };
  errors: string[];
}

export interface FileTree {
  version: string;
  generatedAt: string;
  projectPath: string;
  totalFiles: number;
  files: Record<string, FileAnalysis>;
}

// Language detection
const LANG_MAP: Record<string, string> = {
  '.ts': 'typescript',
  '.tsx': 'typescript',
  '.js': 'javascript',
  '.jsx': 'javascript',
  '.py': 'python',
  '.mjs': 'javascript',
  '.cjs': 'javascript',
};

const IGNORE_DIRS = new Set([
  'node_modules', '.git', '__pycache__', '.venv', 'venv',
  'dist', 'build', '.next', '.ships', 'coverage', '.cache',
  '.turbo', '.vercel', '.netlify', 'out'
]);

const IGNORE_FILES = new Set([
  '.DS_Store', 'Thumbs.db', '.gitignore', '.npmrc',
  'package-lock.json', 'yarn.lock', 'pnpm-lock.yaml'
]);

/**
 * Production-grade code analyzer using tree-sitter
 */
export class CodeAnalyzer {
  private projectPath: string;
  private parserInitialized = false;
  private Parser: any;
  private parsers: Map<string, any> = new Map();

  constructor(projectPath: string) {
    this.projectPath = projectPath;
  }

  /**
   * Initialize tree-sitter parsers
   */
  private async initParsers(): Promise<void> {
    if (this.parserInitialized) return;

    try {
      const TreeSitter = require('web-tree-sitter');
      await TreeSitter.init();
      this.Parser = TreeSitter;

      // Load language parsers from node_modules
      const wasmPath = path.join(__dirname, '../../node_modules/web-tree-sitter');
      
      // TypeScript/JavaScript use same parser
      const tsWasm = path.join(wasmPath, 'tree-sitter-typescript.wasm');
      const jsWasm = path.join(wasmPath, 'tree-sitter-javascript.wasm');
      const pyWasm = path.join(wasmPath, 'tree-sitter-python.wasm');

      // Load if exists, otherwise fall back to regex
      if (fs.existsSync(tsWasm)) {
        const tsLang = await TreeSitter.Language.load(tsWasm);
        const tsParser = new TreeSitter();
        tsParser.setLanguage(tsLang);
        this.parsers.set('typescript', tsParser);
      }

      if (fs.existsSync(jsWasm)) {
        const jsLang = await TreeSitter.Language.load(jsWasm);
        const jsParser = new TreeSitter();
        jsParser.setLanguage(jsLang);
        this.parsers.set('javascript', jsParser);
      }

      if (fs.existsSync(pyWasm)) {
        const pyLang = await TreeSitter.Language.load(pyWasm);
        const pyParser = new TreeSitter();
        pyParser.setLanguage(pyLang);
        this.parsers.set('python', pyParser);
      }

      this.parserInitialized = true;
    } catch (error) {
      console.warn('[CodeAnalyzer] tree-sitter init failed, using regex fallback:', error);
      this.parserInitialized = true; // Mark as initialized to prevent retries
    }
  }

  /**
   * Generate file_tree.json for the entire project
   */
  async generateFileTree(): Promise<FileTree> {
    await this.initParsers();

    const files: Record<string, FileAnalysis> = {};
    await this.scanDirectory(this.projectPath, files);

    const fileTree: FileTree = {
      version: '2.0.0',
      generatedAt: new Date().toISOString(),
      projectPath: this.projectPath,
      totalFiles: Object.keys(files).length,
      files,
    };

    // Write to .ships/
    const shipsDir = path.join(this.projectPath, '.ships');
    if (!fs.existsSync(shipsDir)) {
      fs.mkdirSync(shipsDir, { recursive: true });
    }
    fs.writeFileSync(
      path.join(shipsDir, 'file_tree.json'),
      JSON.stringify(fileTree, null, 2)
    );

    return fileTree;
  }

  /**
   * Recursively scan directory
   */
  private async scanDirectory(
    dir: string,
    files: Record<string, FileAnalysis>
  ): Promise<void> {
    const entries = fs.readdirSync(dir, { withFileTypes: true });

    for (const entry of entries) {
      const fullPath = path.join(dir, entry.name);
      const relativePath = path.relative(this.projectPath, fullPath).replace(/\\/g, '/');

      if (entry.isDirectory()) {
        if (!IGNORE_DIRS.has(entry.name) && !entry.name.startsWith('.')) {
          await this.scanDirectory(fullPath, files);
        }
      } else if (entry.isFile()) {
        if (IGNORE_FILES.has(entry.name)) continue;

        const ext = path.extname(entry.name).toLowerCase();
        const language = LANG_MAP[ext];

        if (language) {
          try {
            const analysis = await this.analyzeFile(fullPath, relativePath, language);
            files[relativePath] = analysis;
          } catch (error) {
            console.error(`[CodeAnalyzer] Failed to analyze ${relativePath}:`, error);
          }
        }
      }
    }
  }

  /**
   * Analyze a single file
   */
  private async analyzeFile(
    fullPath: string,
    relativePath: string,
    language: string
  ): Promise<FileAnalysis> {
    const content = fs.readFileSync(fullPath, 'utf-8');
    const stats = fs.statSync(fullPath);
    const hash = crypto.createHash('md5').update(content).digest('hex');

    // Try tree-sitter first, fall back to regex
    const parser = this.parsers.get(language);
    let symbols: FileAnalysis['symbols'];

    if (parser) {
      symbols = this.parseWithTreeSitter(content, parser, language);
    } else {
      symbols = this.parseWithRegex(content, language);
    }

    return {
      path: fullPath,
      relativePath,
      language,
      size: content.length,
      hash,
      lastModified: stats.mtimeMs,
      symbols,
      errors: [],
    };
  }

  /**
   * Parse with tree-sitter (accurate AST)
   */
  private parseWithTreeSitter(
    content: string,
    parser: any,
    language: string
  ): FileAnalysis['symbols'] {
    const tree = parser.parse(content);
    const root = tree.rootNode;

    const functions: FunctionSymbol[] = [];
    const classes: ClassSymbol[] = [];
    const imports: ImportSymbol[] = [];
    const exports: ExportSymbol[] = [];

    // Walk the AST
    const walk = (node: any) => {
      switch (node.type) {
        // TypeScript/JavaScript
        case 'function_declaration':
        case 'method_definition':
        case 'arrow_function':
          functions.push(this.extractFunction(node, content, language));
          break;
        case 'class_declaration':
          classes.push(this.extractClass(node, content, language));
          break;
        case 'import_statement':
          imports.push(this.extractImport(node, content));
          break;
        case 'export_statement':
          exports.push(...this.extractExports(node, content));
          break;
        // Python
        case 'function_definition':
          functions.push(this.extractPythonFunction(node, content));
          break;
        case 'class_definition':
          classes.push(this.extractPythonClass(node, content));
          break;
        case 'import_statement':
        case 'import_from_statement':
          imports.push(this.extractPythonImport(node, content));
          break;
      }

      for (let i = 0; i < node.childCount; i++) {
        walk(node.child(i));
      }
    };

    walk(root);

    return { functions, classes, imports, exports };
  }

  /**
   * Extract function from AST node
   */
  private extractFunction(node: any, content: string, language: string): FunctionSymbol {
    const nameNode = node.childForFieldName('name');
    const name = nameNode ? content.slice(nameNode.startIndex, nameNode.endIndex) : 'anonymous';
    
    const params: ParameterInfo[] = [];
    const paramsNode = node.childForFieldName('parameters');
    if (paramsNode) {
      for (let i = 0; i < paramsNode.childCount; i++) {
        const param = paramsNode.child(i);
        if (param.type === 'identifier' || param.type === 'required_parameter') {
          params.push({ name: content.slice(param.startIndex, param.endIndex) });
        }
      }
    }

    return {
      name,
      line: node.startPosition.row + 1,
      endLine: node.endPosition.row + 1,
      visibility: this.detectVisibility(node, content),
      async: content.slice(node.startIndex, node.startIndex + 5) === 'async',
      parameters: params,
    };
  }

  private extractClass(node: any, content: string, language: string): ClassSymbol {
    const nameNode = node.childForFieldName('name');
    const name = nameNode ? content.slice(nameNode.startIndex, nameNode.endIndex) : 'Anonymous';

    return {
      name,
      line: node.startPosition.row + 1,
      endLine: node.endPosition.row + 1,
      methods: [],
      properties: [],
    };
  }

  private extractImport(node: any, content: string): ImportSymbol {
    const text = content.slice(node.startIndex, node.endIndex);
    const match = text.match(/from\s+['"]([^'"]+)['"]/);
    const module = match ? match[1] : '';

    const items: string[] = [];
    const namedMatch = text.match(/\{([^}]+)\}/);
    if (namedMatch) {
      items.push(...namedMatch[1].split(',').map(s => s.trim().split(' ')[0]));
    }

    return {
      module,
      items,
      isDefault: text.includes('import ') && !text.includes('{'),
      isNamespace: text.includes('* as'),
      line: node.startPosition.row + 1,
    };
  }

  private extractExports(node: any, content: string): ExportSymbol[] {
    const text = content.slice(node.startIndex, node.endIndex);
    const exports: ExportSymbol[] = [];

    if (text.includes('export default')) {
      exports.push({ name: 'default', kind: 'default', line: node.startPosition.row + 1 });
    }

    const match = text.match(/export\s+(?:const|let|var|function|class|interface|type)\s+(\w+)/);
    if (match) {
      exports.push({ name: match[1], kind: 'variable', line: node.startPosition.row + 1 });
    }

    return exports;
  }

  private extractPythonFunction(node: any, content: string): FunctionSymbol {
    const nameNode = node.childForFieldName('name');
    const name = nameNode ? content.slice(nameNode.startIndex, nameNode.endIndex) : 'anonymous';

    return {
      name,
      line: node.startPosition.row + 1,
      endLine: node.endPosition.row + 1,
      visibility: name.startsWith('_') ? 'private' : 'public',
      async: content.slice(node.startIndex, node.startIndex + 5) === 'async',
      parameters: [],
    };
  }

  private extractPythonClass(node: any, content: string): ClassSymbol {
    const nameNode = node.childForFieldName('name');
    const name = nameNode ? content.slice(nameNode.startIndex, nameNode.endIndex) : 'Anonymous';

    return {
      name,
      line: node.startPosition.row + 1,
      endLine: node.endPosition.row + 1,
      methods: [],
      properties: [],
    };
  }

  private extractPythonImport(node: any, content: string): ImportSymbol {
    const text = content.slice(node.startIndex, node.endIndex);
    
    const fromMatch = text.match(/from\s+(\S+)\s+import\s+(.+)/);
    if (fromMatch) {
      return {
        module: fromMatch[1],
        items: fromMatch[2].split(',').map(s => s.trim()),
        isDefault: false,
        isNamespace: false,
        line: node.startPosition.row + 1,
      };
    }

    const importMatch = text.match(/import\s+(\S+)/);
    return {
      module: importMatch ? importMatch[1] : '',
      items: [],
      isDefault: true,
      isNamespace: false,
      line: node.startPosition.row + 1,
    };
  }

  private detectVisibility(node: any, content: string): 'public' | 'private' | 'protected' | 'export' {
    const text = content.slice(Math.max(0, node.startIndex - 20), node.startIndex);
    if (text.includes('export')) return 'export';
    if (text.includes('private')) return 'private';
    if (text.includes('protected')) return 'protected';
    return 'public';
  }

  /**
   * Fallback regex parsing when tree-sitter unavailable
   */
  private parseWithRegex(content: string, language: string): FileAnalysis['symbols'] {
    const functions: FunctionSymbol[] = [];
    const classes: ClassSymbol[] = [];
    const imports: ImportSymbol[] = [];
    const exports: ExportSymbol[] = [];

    const lines = content.split('\n');

    if (language === 'python') {
      lines.forEach((line, i) => {
        const funcMatch = line.match(/^(\s*)(?:async\s+)?def\s+(\w+)\s*\(([^)]*)\)/);
        if (funcMatch) {
          const name = funcMatch[2];
          const params = funcMatch[3].split(',').map(p => ({ name: p.trim().split(':')[0].split('=')[0].trim() })).filter(p => p.name);
          functions.push({
            name,
            line: i + 1,
            endLine: i + 1,
            visibility: name.startsWith('_') ? 'private' : 'public',
            async: line.includes('async'),
            parameters: params,
          });
        }

        const classMatch = line.match(/^class\s+(\w+)/);
        if (classMatch) {
          classes.push({ name: classMatch[1], line: i + 1, endLine: i + 1, methods: [], properties: [] });
        }

        const importMatch = line.match(/^from\s+(\S+)\s+import\s+(.+)/);
        if (importMatch) {
          imports.push({
            module: importMatch[1],
            items: importMatch[2].split(',').map(s => s.trim()),
            isDefault: false,
            isNamespace: false,
            line: i + 1,
          });
        }
      });
    } else {
      // TypeScript/JavaScript
      lines.forEach((line, i) => {
        const funcMatch = line.match(/(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)/);
        if (funcMatch) {
          functions.push({
            name: funcMatch[1],
            line: i + 1,
            endLine: i + 1,
            visibility: line.includes('export') ? 'export' : 'public',
            async: line.includes('async'),
            parameters: funcMatch[2].split(',').map(p => ({ name: p.trim().split(':')[0].split('=')[0].trim() })).filter(p => p.name),
          });
        }

        const arrowMatch = line.match(/(?:export\s+)?const\s+(\w+)\s*=\s*(?:async\s*)?\([^)]*\)\s*(?::\s*\w+)?\s*=>/);
        if (arrowMatch) {
          functions.push({
            name: arrowMatch[1],
            line: i + 1,
            endLine: i + 1,
            visibility: line.includes('export') ? 'export' : 'public',
            async: line.includes('async'),
            parameters: [],
          });
        }

        const classMatch = line.match(/(?:export\s+)?class\s+(\w+)/);
        if (classMatch) {
          classes.push({ name: classMatch[1], line: i + 1, endLine: i + 1, methods: [], properties: [] });
        }

        const importMatch = line.match(/import\s+(?:{([^}]+)}|(\w+))\s+from\s+['"]([^'"]+)['"]/);
        if (importMatch) {
          const items = importMatch[1] ? importMatch[1].split(',').map(s => s.trim().split(' ')[0]) : [importMatch[2]];
          imports.push({
            module: importMatch[3],
            items,
            isDefault: !importMatch[1],
            isNamespace: false,
            line: i + 1,
          });
        }

        const exportMatch = line.match(/export\s+(?:const|let|var|function|class|interface|type)\s+(\w+)/);
        if (exportMatch) {
          exports.push({ name: exportMatch[1], kind: 'variable', line: i + 1 });
        }
      });
    }

    return { functions, classes, imports, exports };
  }
}
