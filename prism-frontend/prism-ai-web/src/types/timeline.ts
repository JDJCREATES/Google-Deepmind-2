/**
 * Feature Timeline Type Definitions
 * 
 * Data structures for the ShipS Feature Timeline system.
 */

export type NodeType = 'feature' | 'fix' | 'refactor' | 'deploy' | 'milestone';
export type NodeStatus = 'success' | 'failed' | 'in-progress' | 'pending' | 'warning';
export type FilterType = 'all' | 'features' | 'fixes' | 'refactors' | 'deploys';
export type GroupByType = 'none' | 'feature' | 'day' | 'smart';

export interface TimelinePhase {
  name: string;
  status: 'success' | 'failed' | 'in-progress' | 'pending';
  duration_ms: number;
}

export interface IssueFix {
  pitfall_id: string;
  auto_fixed: boolean;
  description?: string;
}

export interface TimelineNode {
  id: string;
  type: NodeType;
  status: NodeStatus;
  
  // Core info
  title: string;
  description?: string;
  timestamp: Date;
  duration_ms: number;
  
  // Changes
  files_changed: string[];
  lines_added: number;
  lines_removed: number;
  
  // Agent info
  agents_used: string[];
  phases: TimelinePhase[];
  
  // Learning
  issues_fixed: IssueFix[];
  
  // Git
  commit_hash?: string;
  parent_hash?: string;
  
  // Relationships
  parent_node?: string;
  grouped_with?: string[];
}

export interface TimelineState {
  nodes: TimelineNode[];
  current_node_id: string;
  active_node_id?: string;
  
  // View state
  scroll_position: number;
  selected_node?: string;
  filter: FilterType;
  group_by: GroupByType;
}

export interface TimelineControls {
  onNodeClick?: (nodeId: string) => void;
  onNodeHover?: (nodeId: string | null) => void;
  onUndo?: (nodeId: string) => void;
  onRestore?: (nodeId: string) => void;
  onViewDiff?: (nodeId: string) => void;
  onSearch?: (query: string) => void;
  onFilterChange?: (filter: FilterType) => void;
}
