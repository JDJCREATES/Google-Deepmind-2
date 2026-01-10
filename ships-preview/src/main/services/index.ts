/**
 * Intelligence Services
 *
 * Production-grade code analysis and artifact generation.
 */

export { CodeAnalyzer } from './codeAnalyzer';
export { DependencyAnalyzer } from './dependencyAnalyzer';
export { SecurityScanner } from './securityScanner';
export { ArtifactGenerator } from './artifactGenerator';
export { FileWatcher } from './fileWatcher';
export { ArtifactService } from './artifactService';
export { 
  registerArtifactHandlers, 
  updateProjectPath, 
  removeArtifactHandlers 
} from './artifactHandlers';

export type { FileTree, FileAnalysis, FunctionSymbol, ClassSymbol } from './codeAnalyzer';
export type { DependencyGraph, DependencyNode, CircularDependency } from './dependencyAnalyzer';
export type { SecurityReport, Vulnerability, HardcodedSecret } from './securityScanner';
export type { ArtifactStatus, GenerationResult } from './artifactGenerator';
