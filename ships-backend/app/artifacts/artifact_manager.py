"""
ShipS* Artifact Manager Service

This module provides a centralized service for loading, saving, and managing
all artifacts used by the LangGraph agents. It handles:
- File I/O operations with proper error handling
- Artifact versioning and timestamps
- Typed accessors for each artifact type
- Directory structure management

The service follows the .ships/ directory convention:
  .ships/
    planning/     - Layer 1: Planning artifacts (user-provided)
    runtime/      - Layer 2: Runtime artifacts (agent-managed)
    audit/        - Layer 3: Audit artifacts (system-generated)
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, TypeVar, Type, Generic
from pydantic import BaseModel

from app.artifacts.models import (
    PatternRegistry,
    ContractDefinitions,
    QualityGateResults,
    AgentConversationLog,
    ContextMap,
    DependencyGraph,
    FixHistory,
    PitfallCoverageMatrix,
    AgentType,
    AgentLogEntry,
)


# Type variable for generic artifact operations
T = TypeVar('T', bound=BaseModel)


class ArtifactPaths:
    """
    Centralized path definitions for all artifact files.
    
    This ensures consistency across the codebase and makes it easy
    to change the directory structure in one place.
    """
    
    def __init__(self, project_root: Path):
        """
        Initialize artifact paths for a project.
        
        Args:
            project_root: Root directory of the target project
        """
        self.root = project_root
        self.ships_dir = project_root / ".ships"
        
        # Layer 1: Planning
        self.planning_dir = self.ships_dir / "planning"
        self.app_blueprint = self.planning_dir / "app_blueprint.yaml"
        self.folder_map = self.planning_dir / "folder_map.yaml"
        self.data_schema = self.planning_dir / "data_schema.ts"
        self.flows = self.planning_dir / "flows.yaml"
        self.ui_sketches_dir = self.planning_dir / "ui_sketches"
        
        # Layer 2: Runtime
        self.runtime_dir = self.ships_dir / "runtime"
        self.pattern_registry = self.runtime_dir / "pattern_registry.json"
        self.context_map = self.runtime_dir / "context_map.json"
        self.contracts = self.runtime_dir / "contracts.json"
        self.dependency_graph = self.runtime_dir / "dependency_graph.json"
        self.quality_gates = self.runtime_dir / "quality_gates.json"
        self.agent_log = self.runtime_dir / "agent_log.json"
        self.fix_history = self.runtime_dir / "fix_history.json"
        self.pitfall_matrix = self.runtime_dir / "pitfall_matrix.json"
        self.error_kb = self.runtime_dir / "error_kb.json"
        
        # Layer 3: Audit
        self.audit_dir = self.ships_dir / "audit"
        self.tasks_dir = self.audit_dir / "tasks"
        self.history_dir = self.audit_dir / "history"
    
    def ensure_directories(self) -> None:
        """Create all required directories if they don't exist."""
        dirs = [
            self.planning_dir,
            self.ui_sketches_dir,
            self.runtime_dir,
            self.tasks_dir,
            self.history_dir,
        ]
        for dir_path in dirs:
            dir_path.mkdir(parents=True, exist_ok=True)
    
    def get_task_dir(self, task_id: str) -> Path:
        """Get the directory for a specific task's audit artifacts."""
        task_dir = self.tasks_dir / task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        return task_dir


class ArtifactManager:
    """
    Production-grade service for managing ShipS* artifacts.
    
    This class provides:
    - Type-safe loading and saving of all artifact types
    - Automatic directory structure creation
    - Error handling with descriptive messages
    - Caching for frequently accessed artifacts
    - Atomic write operations to prevent corruption
    
    Usage:
        manager = ArtifactManager("/path/to/project")
        patterns = manager.get_pattern_registry()
        patterns.naming_conventions.variables = "snake_case"
        manager.save_pattern_registry(patterns)
    """
    
    def __init__(self, project_root: str | Path):
        """
        Initialize the artifact manager.
        
        Args:
            project_root: Path to the target project root directory
        """
        self.project_root = Path(project_root)
        self.paths = ArtifactPaths(self.project_root)
        
        # Ensure directories exist
        self.paths.ensure_directories()
        
        # Cache for frequently accessed artifacts
        self._cache: dict[str, tuple[BaseModel, datetime]] = {}
        self._cache_ttl_seconds = 60  # Cache TTL in seconds
    
    # =========================================================================
    # GENERIC OPERATIONS
    # =========================================================================
    
    def _load_artifact(self, path: Path, model_class: Type[T]) -> Optional[T]:
        """
        Load an artifact from disk.
        
        Args:
            path: Path to the artifact file
            model_class: Pydantic model class to deserialize into
            
        Returns:
            Deserialized artifact or None if file doesn't exist
            
        Raises:
            ValueError: If the file exists but contains invalid data
        """
        if not path.exists():
            return None
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return model_class.model_validate(data)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in {path}: {e}")
        except Exception as e:
            raise ValueError(f"Failed to load artifact from {path}: {e}")
    
    def _save_artifact(self, path: Path, artifact: BaseModel) -> None:
        """
        Save an artifact to disk atomically.
        
        Uses a write-then-rename approach to prevent corruption
        if the process is interrupted during write.
        
        Args:
            path: Path to save the artifact
            artifact: Pydantic model instance to serialize
        """
        # Ensure parent directory exists
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write to temporary file first
        temp_path = path.with_suffix('.tmp')
        try:
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(
                    artifact.model_dump(mode='json'),
                    f,
                    indent=2,
                    default=str  # Handle datetime serialization
                )
            
            # Atomic rename (works on most filesystems)
            temp_path.replace(path)
            
            # Invalidate cache
            cache_key = str(path)
            if cache_key in self._cache:
                del self._cache[cache_key]
                
        except Exception as e:
            # Clean up temp file if it exists
            if temp_path.exists():
                temp_path.unlink()
            raise IOError(f"Failed to save artifact to {path}: {e}")
    
    def _get_cached_or_load(self, path: Path, model_class: Type[T]) -> Optional[T]:
        """Load artifact with caching support."""
        cache_key = str(path)
        now = datetime.utcnow()
        
        # Check cache
        if cache_key in self._cache:
            artifact, cached_at = self._cache[cache_key]
            age = (now - cached_at).total_seconds()
            if age < self._cache_ttl_seconds:
                return artifact  # type: ignore
        
        # Load from disk
        artifact = self._load_artifact(path, model_class)
        if artifact:
            self._cache[cache_key] = (artifact, now)
        
        return artifact
    
    # =========================================================================
    # LAYER 2: RUNTIME ARTIFACTS
    # =========================================================================
    
    def get_pattern_registry(self) -> PatternRegistry:
        """
        Load the pattern registry, creating a new one if it doesn't exist.
        
        Returns:
            PatternRegistry instance
        """
        registry = self._get_cached_or_load(
            self.paths.pattern_registry, 
            PatternRegistry
        )
        return registry or PatternRegistry()
    
    def save_pattern_registry(self, registry: PatternRegistry) -> None:
        """Save the pattern registry."""
        registry.last_updated = datetime.utcnow()
        self._save_artifact(self.paths.pattern_registry, registry)
    
    def get_contract_definitions(self) -> ContractDefinitions:
        """Load contract definitions, creating a new one if needed."""
        contracts = self._get_cached_or_load(
            self.paths.contracts,
            ContractDefinitions
        )
        return contracts or ContractDefinitions()
    
    def save_contract_definitions(self, contracts: ContractDefinitions) -> None:
        """Save contract definitions."""
        contracts.last_updated = datetime.utcnow()
        self._save_artifact(self.paths.contracts, contracts)
    
    def get_quality_gate_results(self, task_id: Optional[str] = None) -> QualityGateResults:
        """
        Load quality gate results.
        
        Args:
            task_id: Optional task ID to filter by
            
        Returns:
            QualityGateResults instance
        """
        results = self._get_cached_or_load(
            self.paths.quality_gates,
            QualityGateResults
        )
        if results and task_id and results.task_id != task_id:
            # Create new results for different task
            return QualityGateResults(task_id=task_id)
        return results or QualityGateResults()
    
    def save_quality_gate_results(self, results: QualityGateResults) -> None:
        """Save quality gate results."""
        results.last_updated = datetime.utcnow()
        self._save_artifact(self.paths.quality_gates, results)
    
    def get_agent_log(self, task_id: Optional[str] = None) -> AgentConversationLog:
        """Load agent conversation log."""
        log = self._get_cached_or_load(
            self.paths.agent_log,
            AgentConversationLog
        )
        if log and task_id and log.task_id != task_id:
            return AgentConversationLog(task_id=task_id)
        return log or AgentConversationLog()
    
    def save_agent_log(self, log: AgentConversationLog) -> None:
        """Save agent conversation log."""
        self._save_artifact(self.paths.agent_log, log)
    
    def log_agent_action(
        self,
        agent: AgentType,
        action: str,
        input_summary: Optional[str] = None,
        output_summary: Optional[str] = None,
        reasoning: Optional[str] = None,
        task_id: Optional[str] = None
    ) -> AgentLogEntry:
        """
        Convenience method to log an agent action.
        
        Loads the current log, appends the entry, and saves.
        
        Args:
            agent: Agent that performed the action
            action: Action type
            input_summary: Optional summary of input
            output_summary: Optional summary of output
            reasoning: Optional reasoning
            task_id: Optional task ID
            
        Returns:
            The created log entry
        """
        log = self.get_agent_log(task_id)
        entry = log.log(
            agent=agent,
            action=action,
            input_summary=input_summary,
            output_summary=output_summary,
            reasoning=reasoning
        )
        self.save_agent_log(log)
        return entry
    
    def get_context_map(self) -> Optional[ContextMap]:
        """Load context map if it exists."""
        return self._get_cached_or_load(
            self.paths.context_map,
            ContextMap
        )
    
    def save_context_map(self, context_map: ContextMap) -> None:
        """Save context map."""
        self._save_artifact(self.paths.context_map, context_map)
    
    def get_dependency_graph(self) -> DependencyGraph:
        """Load dependency graph."""
        graph = self._get_cached_or_load(
            self.paths.dependency_graph,
            DependencyGraph
        )
        return graph or DependencyGraph()
    
    def save_dependency_graph(self, graph: DependencyGraph) -> None:
        """Save dependency graph."""
        graph.last_updated = datetime.utcnow()
        self._save_artifact(self.paths.dependency_graph, graph)
    
    def get_fix_history(self) -> FixHistory:
        """Load fix history."""
        history = self._get_cached_or_load(
            self.paths.fix_history,
            FixHistory
        )
        return history or FixHistory()
    
    def save_fix_history(self, history: FixHistory) -> None:
        """Save fix history."""
        self._save_artifact(self.paths.fix_history, history)
    
    def get_pitfall_matrix(self) -> PitfallCoverageMatrix:
        """Load pitfall coverage matrix."""
        matrix = self._get_cached_or_load(
            self.paths.pitfall_matrix,
            PitfallCoverageMatrix
        )
        return matrix or PitfallCoverageMatrix()
    
    def save_pitfall_matrix(self, matrix: PitfallCoverageMatrix) -> None:
        """Save pitfall coverage matrix."""
        self._save_artifact(self.paths.pitfall_matrix, matrix)
    
    # =========================================================================
    # UTILITY METHODS
    # =========================================================================
    
    def clear_cache(self) -> None:
        """Clear all cached artifacts."""
        self._cache.clear()
    
    def artifact_exists(self, artifact_name: str) -> bool:
        """
        Check if an artifact file exists.
        
        Args:
            artifact_name: Name of the artifact (e.g., 'pattern_registry')
            
        Returns:
            True if the artifact file exists
        """
        path_attr = getattr(self.paths, artifact_name, None)
        if path_attr and isinstance(path_attr, Path):
            return path_attr.exists()
        return False
    
    def get_artifact_summary(self) -> dict[str, bool]:
        """
        Get a summary of which artifacts exist.
        
        Returns:
            Dict mapping artifact names to existence status
        """
        artifacts = [
            'pattern_registry',
            'context_map',
            'contracts',
            'dependency_graph',
            'quality_gates',
            'agent_log',
            'fix_history',
            'pitfall_matrix',
        ]
        return {name: self.artifact_exists(name) for name in artifacts}
    
    def initialize_for_task(self, task_id: str, task_description: str) -> None:
        """
        Initialize artifacts for a new task.
        
        Creates fresh instances of per-task artifacts.
        
        Args:
            task_id: Unique task identifier
            task_description: Human-readable task description
        """
        # Create fresh quality gates
        gates = QualityGateResults(
            task_id=task_id,
            task_description=task_description
        )
        self.save_quality_gate_results(gates)
        
        # Create fresh agent log
        log = AgentConversationLog(
            task_id=task_id,
            task_description=task_description
        )
        self.save_agent_log(log)
        
        # Create fresh pitfall matrix
        matrix = PitfallCoverageMatrix(task_id=task_id)
        self.save_pitfall_matrix(matrix)
        
        # Create task-specific audit directory
        self.paths.get_task_dir(task_id)


# Singleton instance for convenience (can be overridden)
_default_manager: Optional[ArtifactManager] = None


def get_artifact_manager(project_root: Optional[str | Path] = None) -> ArtifactManager:
    """
    Get the default artifact manager instance.
    
    Args:
        project_root: Optional project root path. If not provided and no 
                      default manager exists, raises ValueError.
                      
    Returns:
        ArtifactManager instance
    """
    global _default_manager
    
    if project_root:
        _default_manager = ArtifactManager(project_root)
    
    if _default_manager is None:
        raise ValueError("No project root provided and no default manager exists")
    
    return _default_manager
