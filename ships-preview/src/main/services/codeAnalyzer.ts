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

// Call Graph Types - Function-to-Function relationships
export interface FunctionCall {
  callee: string;           // Name of the function being called
  line: number;             // Line where the call occurs
  column?: number;          // Column position
  isMethodCall: boolean;    // obj.method() vs function()
  receiver?: string;        // The object if method call (e.g., "this", "utils")
}

export interface CallGraphNode {
  file: string;             // File path
  name: string;             // Function/method name
  fullName: string;         // Fully qualified: "ClassName.methodName" or "functionName"
  line: number;
  calls: FunctionCall[];    // Functions this node calls
}

export interface CallGraph {
  version: string;
  generatedAt: string;
  projectPath: string;
  nodes: CallGraphNode[];
}

// Dependency Graph Types - File-to-File relationships
export interface DependencyEdge {
  from: string;             // Importing file (relative path)
  to: string;               // Imported module/file
  imports: string[];        // Specific items imported
  isExternal: boolean;      // true if node_modules/external
  line: number;
}

export interface DependencyGraph {
  version: string;
  generatedAt: string;
  projectPath: string;
  edges: DependencyEdge[];
  circular: string[][];     // Groups of files in circular dependencies
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
  private extractFunction(node: any, content: string, _language: string): FunctionSymbol {
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

  private extractClass(node: any, content: string, _language: string): ClassSymbol {
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

  /**
   * Generate dependency_graph.json from import relationships
   */
  async generateDependencyGraph(): Promise<DependencyGraph> {
    await this.initParsers();
    
    const fileTree = await this.generateFileTree();
    const edges: DependencyEdge[] = [];
    const fileSet = new Set(Object.keys(fileTree.files));
    
    for (const [filePath, analysis] of Object.entries(fileTree.files)) {
      for (const imp of analysis.symbols.imports) {
        // Determine if external (starts with @ or doesn't start with . or /)
        const isExternal = !imp.module.startsWith('.') && !imp.module.startsWith('/');
        
        // Resolve relative imports to actual file paths
        let resolvedPath = imp.module;
        if (!isExternal) {
          const baseDir = path.dirname(filePath);
          resolvedPath = path.posix.normalize(path.posix.join(baseDir, imp.module));
          
          // Try to resolve with extensions
          for (const ext of ['.ts', '.tsx', '.js', '.jsx', '/index.ts', '/index.tsx', '/index.js']) {
            if (fileSet.has(resolvedPath + ext)) {
              resolvedPath = resolvedPath + ext;
              break;
            }
          }
        }
        
        edges.push({
          from: filePath,
          to: resolvedPath,
          imports: imp.items,
          isExternal,
          line: imp.line,
        });
      }
    }
    
    // Detect circular dependencies using DFS
    const circular = this.detectCircularDependencies(edges);
    
    const depGraph: DependencyGraph = {
      version: '1.0.0',
      generatedAt: new Date().toISOString(),
      projectPath: this.projectPath,
      edges,
      circular,
    };
    
    // Write to .ships/
    const shipsDir = path.join(this.projectPath, '.ships');
    if (!fs.existsSync(shipsDir)) {
      fs.mkdirSync(shipsDir, { recursive: true });
    }
    fs.writeFileSync(
      path.join(shipsDir, 'dependency_graph.json'),
      JSON.stringify(depGraph, null, 2)
    );
    
    return depGraph;
  }
  
  /**
   * Detect circular dependencies
   */
  private detectCircularDependencies(edges: DependencyEdge[]): string[][] {
    const graph = new Map<string, string[]>();
    
    for (const edge of edges) {
      if (!edge.isExternal) {
        const deps = graph.get(edge.from) || [];
        deps.push(edge.to);
        graph.set(edge.from, deps);
      }
    }
    
    const visited = new Set<string>();
    const recursionStack = new Set<string>();
    const cycles: string[][] = [];
    
    const dfs = (node: string, path: string[]): void => {
      if (recursionStack.has(node)) {
        // Found cycle - extract it
        const cycleStart = path.indexOf(node);
        if (cycleStart !== -1) {
          cycles.push(path.slice(cycleStart));
        }
        return;
      }
      
      if (visited.has(node)) return;
      
      visited.add(node);
      recursionStack.add(node);
      
      for (const dep of graph.get(node) || []) {
        dfs(dep, [...path, node]);
      }
      
      recursionStack.delete(node);
    };
    
    for (const node of graph.keys()) {
      if (!visited.has(node)) {
        dfs(node, []);
      }
    }
    
    return cycles;
  }

  /**
   * Generate call_graph.json from function call analysis
   */
  async generateCallGraph(): Promise<CallGraph> {
    await this.initParsers();
    
    const fileTree = await this.generateFileTree();
    const nodes: CallGraphNode[] = [];
    
    for (const [filePath, analysis] of Object.entries(fileTree.files)) {
      // Read file content for call extraction
      const fullPath = path.join(this.projectPath, filePath);
      let content: string;
      try {
        content = fs.readFileSync(fullPath, 'utf-8');
      } catch {
        continue;
      }
      
      const parser = this.parsers.get(analysis.language);
      
      // Extract calls for each function
      for (const func of analysis.symbols.functions) {
        const calls = parser
          ? this.extractCallsWithTreeSitter(content, parser, func.line, func.endLine)
          : this.extractCallsWithRegex(content, func.line, func.endLine);
        
        nodes.push({
          file: filePath,
          name: func.name,
          fullName: func.name,
          line: func.line,
          calls,
        });
      }
      
      // Extract calls for class methods
      for (const cls of analysis.symbols.classes) {
        for (const method of cls.methods) {
          const calls = parser
            ? this.extractCallsWithTreeSitter(content, parser, method.line, method.endLine)
            : this.extractCallsWithRegex(content, method.line, method.endLine);
          
          nodes.push({
            file: filePath,
            name: method.name,
            fullName: `${cls.name}.${method.name}`,
            line: method.line,
            calls,
          });
        }
      }
    }
    
    const callGraph: CallGraph = {
      version: '1.0.0',
      generatedAt: new Date().toISOString(),
      projectPath: this.projectPath,
      nodes,
    };
    
    // Write to .ships/
    const shipsDir = path.join(this.projectPath, '.ships');
    if (!fs.existsSync(shipsDir)) {
      fs.mkdirSync(shipsDir, { recursive: true });
    }
    fs.writeFileSync(
      path.join(shipsDir, 'call_graph.json'),
      JSON.stringify(callGraph, null, 2)
    );
    
    return callGraph;
  }
  
  /**
   * Extract function calls using tree-sitter AST
   */
  private extractCallsWithTreeSitter(
    content: string,
    parser: any,
    startLine: number,
    endLine: number
  ): FunctionCall[] {
    const calls: FunctionCall[] = [];
    const tree = parser.parse(content);
    
    const walk = (node: any): void => {
      const nodeLine = node.startPosition.row + 1;
      
      // Skip nodes outside our function range
      if (nodeLine < startLine || nodeLine > endLine) {
        for (const child of node.children || []) {
          walk(child);
        }
        return;
      }
      
      if (node.type === 'call_expression') {
        const funcNode = node.childForFieldName('function') || node.children?.[0];
        
        if (funcNode) {
          let callee = '';
          let receiver: string | undefined;
          let isMethodCall = false;
          
          if (funcNode.type === 'member_expression') {
            // obj.method() or this.method()
            isMethodCall = true;
            const objNode = funcNode.childForFieldName('object');
            const propNode = funcNode.childForFieldName('property');
            
            receiver = objNode ? content.substring(objNode.startIndex, objNode.endIndex) : undefined;
            callee = propNode ? content.substring(propNode.startIndex, propNode.endIndex) : '';
          } else {
            // Direct function call
            callee = content.substring(funcNode.startIndex, funcNode.endIndex);
          }
          
          calls.push({
            callee,
            line: nodeLine,
            column: node.startPosition.column,
            isMethodCall,
            receiver,
          });
        }
      }
      
      for (const child of node.children || []) {
        walk(child);
      }
    };
    
    walk(tree.rootNode);
    return calls;
  }
  
  /**
   * Extract function calls using regex (fallback)
   */
  private extractCallsWithRegex(
    content: string,
    startLine: number,
    endLine: number
  ): FunctionCall[] {
    const calls: FunctionCall[] = [];
    const lines = content.split('\n');
    
    // Simple regex for function calls: identifier( or obj.method(
    const callPattern = /(?:(\w+)\.)?(\w+)\s*\(/g;
    
    for (let i = startLine - 1; i < Math.min(endLine, lines.length); i++) {
      const line = lines[i];
      let match;
      
      while ((match = callPattern.exec(line)) !== null) {
        const receiver = match[1];
        const callee = match[2];
        
        // Skip keywords
        if (['if', 'while', 'for', 'switch', 'catch', 'function', 'class'].includes(callee)) {
          continue;
        }
        
        calls.push({
          callee,
          line: i + 1,
          column: match.index,
          isMethodCall: !!receiver,
          receiver,
        });
      }
    }
    
    return calls;
  }
}
