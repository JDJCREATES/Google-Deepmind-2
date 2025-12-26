/**
 * Artifact Type Definitions for ShipS*
 * 
 * Comprehensive TypeScript types for all artifact types used in the ShipS* system.
 * These types ensure type safety when working with backend artifacts and provide
 * IntelliSense support for developers.
 * 
 * @module types/artifacts
 */

/**
 * All possible artifact types in the ShipS* system
 */
export type ArtifactType =
  | 'plan_manifest'
  | 'task_list'
  | 'folder_map'
  | 'api_contracts'
  | 'dependency_plan'
  | 'validation_checklist'
  | 'risk_report'
  | 'validation_report'
  | 'fix_plan'
  | 'fix_patch'
  | 'fix_report'
  | 'image'
  | 'text_document'
  | 'generic_file';

/**
 * Status of an artifact
 */
export type ArtifactStatus = 'draft' | 'active' | 'archived' | 'superseded';

/**
 * Base interface for all artifacts
 */
export interface BaseArtifact {
  /** Unique identifier */
  id: string;
  /** Type of artifact */
  type: ArtifactType;
  /** Project this artifact belongs to */
  projectId: string;
  /** User who created this artifact */
  createdBy: string;
  /** Timestamp of creation */
  createdAt: string;
  /** Timestamp of last update */
  updatedAt: string;
  /** Current status */
  status: ArtifactStatus;
  /** Schema version for migration compatibility */
  schemaVersion: string;
}

// ============================================================================
// PLANNER ARTIFACTS
// ============================================================================

/**
 * Plan Manifest - Top-level plan descriptor
 */
export interface PlanManifest extends BaseArtifact {
  type: 'plan_manifest';
  data: {
    title: string;
    description: string;
    intentSpecId?: string;
    goals: string[];
    nonGoals: string[];
    estimatedHours: number;
    complexity: 'low' | 'medium' | 'high';
    tags: string[];
  };
}

/**
 * Individual task in a task list
 */
export interface Task {
  id: string;
  title: string;
  description: string;
  status: 'pending' | 'in_progress' | 'completed' | 'blocked';
  priority: 1 | 2 | 3 | 4 | 5;
  estimatedHours: number;
  actualHours?: number;
  acceptanceCriteria: Array<{
    description: string;
    isMet: boolean;
  }>;
  dependencies: string[];
  assignedTo?: string;
  expectedOutputs: string[];
}

/**
 * Task List artifact
 */
export interface TaskList extends BaseArtifact {
  type: 'task_list';
  data: {
    planId: string;
    tasks: Task[];
    totalEstimatedHours: number;
    completedTasks: number;
  };
}

/**
 * Folder map entry
 */
export interface FolderMapEntry {
  path: string;
  isDirectory: boolean;
  purpose: string;
  protected?: boolean;
}

/**
 * Folder Map artifact
 */
export interface FolderMap extends BaseArtifact {
  type: 'folder_map';
  data: {
    planId: string;
    rootPath: string;
    entries: FolderMapEntry[];
    totalDirectories: number;
    framework?: string;
  };
}

/**
 * Dependency Plan artifact
 */
export interface DependencyPlan extends BaseArtifact {
  type: 'dependency_plan';
  data: {
    planId: string;
    runtimeDependencies: Array<{
      name: string;
      version: string;
      reason: string;
      license?: string;
    }>;
    devDependencies: Array<{
      name: string;
      version: string;
      reason: string;
    }>;
    packageManager: 'npm' | 'pip' | 'yarn' | 'pnpm';
    totalPackages: number;
  };
}

// ============================================================================
// VALIDATOR ARTIFACTS
// ============================================================================

/**
 * Validation status
 */
export type ValidationStatus = 'pass' | 'fail';

/**
 * Validation layer that failed
 */
export type FailureLayer = 'none' | 'structural' | 'completeness' | 'dependency' | 'scope';

/**
 * Violation severity
 */
export type ViolationSeverity = 'minor' | 'major' | 'critical';

/**
 * Individual violation
 */
export interface Violation {
  id: string;
  layer: FailureLayer;
  rule: string;
  message: string;
  filePath?: string;
  lineNumber?: number;
  severity: ViolationSeverity;
  suggestedFix?: string;
}

/**
 * Validation Report artifact
 */
export interface ValidationReport extends BaseArtifact {
  type: 'validation_report';
  data: {
    taskId: string;
    status: ValidationStatus;
    failureLayer: FailureLayer;
    violations: Violation[];
    totalViolations: number;
    checksRun: number;
    checkedFiles: number;
    recommendedAction: 'proceed' | 'fix' | 'replan';
    validatedAt: string;
  };
}

// ============================================================================
// FIXER ARTIFACTS
// ============================================================================

/**
 * Fix approach strategy
 */
export type FixApproach = 'local' | 'escalate_planner' | 'escalate_security';

/**
 * Fix result status
 */
export type FixResult = 'applied' | 'rejected' | 'failed' | 'needs_approval';

/**
 * Fix Plan artifact
 */
export interface FixPlan extends BaseArtifact {
  type: 'fix_plan';
  data: {
    validationReportId: string;
    summary: string;
    approach: FixApproach;
    violationsFixes: Array<{
      violationId: string;
      strategy: string;
      confidence: number;
    }>;
    estimatedRisk: 'low' | 'medium' | 'high';
    autoApplyAllowed: boolean;
    requiresReplan: boolean;
  };
}

/**
 * Fix Patch artifact
 */
export interface FixPatch extends BaseArtifact {
  type: 'fix_patch';
  data: {
    fixPlanId: string;
    changes: Array<{
      path: string;
      operation: 'add' | 'modify' | 'delete';
      originalContent?: string;
      newContent?: string;
      unifiedDiff?: string;
      linesAdded: number;
      linesRemoved: number;
      reason: string;
    }>;
    commitMessage: string;
    preflightPassed: boolean;
    totalFiles: number;
  };
}

/**
 * Fix Report artifact
 */
export interface FixReport extends BaseArtifact {
  type: 'fix_report';
  data: {
    fixPlanId: string;
    fixPatchId?: string;
    result: FixResult;
    violationsFixed: number;
    filesModified: number;
    revalidationRequired: boolean;
    notes: string;
    appliedAt?: string;
  };
}

// ============================================================================
// MEDIA & FILE ARTIFACTS
// ============================================================================

/**
 * Image artifact
 */
export interface ImageArtifact extends BaseArtifact {
  type: 'image';
  data: {
    url: string;
    filename: string;
    mimeType: string;
    size: number;
    dimensions?: { width: number; height: number };
    altText?: string;
  };
}

/**
 * Text Document artifact (logs, notes, etc.)
 */
export interface TextDocumentArtifact extends BaseArtifact {
  type: 'text_document';
  data: {
    content: string;
    filename: string;
    language: string; // e.g., 'markdown', 'python', 'plaintext'
  };
}

/**
 * Generic File artifact (zip, pdf, etc.)
 */
export interface GenericFileArtifact extends BaseArtifact {
  type: 'generic_file';
  data: {
    url: string;
    filename: string;
    mimeType: string;
    size: number;
  };
}

// ============================================================================
// UTILITY TYPES
// ============================================================================

/**
 * Union type of all possible artifacts
 */
export type Artifact =
  | PlanManifest
  | TaskList
  | FolderMap
  | DependencyPlan
  | ValidationReport
  | FixPlan
  | FixPatch
  | FixReport
  | ImageArtifact
  | TextDocumentArtifact
  | GenericFileArtifact;

/**
 * Artifact metadata for lists and trees
 */
export interface ArtifactMetadata {
  id: string;
  type: ArtifactType;
  title: string;
  createdAt: string;
  updatedAt: string;
  status: ArtifactStatus;
}

/**
 * Grouped artifacts by type
 */
export interface ArtifactGroup {
  type: ArtifactType;
  label: string;
  icon: string;
  artifacts: ArtifactMetadata[];
  count: number;
}

/**
 * API response for artifact list
 */
export interface ArtifactListResponse {
  projectId: string;
  artifacts: ArtifactMetadata[];
  total: number;
  groups: ArtifactGroup[];
}

/**
 * API response for single artifact
 */
export interface ArtifactResponse<T extends Artifact = Artifact> {
  artifact: T;
  relatedArtifacts?: ArtifactMetadata[];
}

/**
 * API request for creating artifact
 */
export interface CreateArtifactRequest {
  type: ArtifactType;
  projectId: string;
  data: any;
}

/**
 * API request for updating artifact
 */
export interface UpdateArtifactRequest {
  data: any;
  updatedBy: string;
}
