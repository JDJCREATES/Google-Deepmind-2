"""
ShipS* Artifact Manager Service

Manages artifacts in the flat .ships/ directory structure.
All artifacts are JSON files stored directly in .ships/.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict

from pydantic import BaseModel


class ArtifactPaths:
    """
    Centralized path definitions for all artifact files.
    
    All artifacts are stored flat in .ships/ directory.
    """
    
    def __init__(self, project_root: Path):
        """
        Initialize artifact paths for a project.
        
        Args:
            project_root: Root directory of the target project
        """
        self.root = project_root
        self.ships_dir = project_root / ".ships"
        
        # Planning artifacts (Planner-generated)
        self.folder_map = self.ships_dir / "folder_map_plan.json"
        self.task_list = self.ships_dir / "task_list.json"
        self.implementation_plan = self.ships_dir / "implementation_plan.md"
        self.api_contracts = self.ships_dir / "api_contracts.json"
        self.dependency_plan = self.ships_dir / "dependency_plan.json"
        self.risk_report = self.ships_dir / "risk_report.json"
        self.validation_checklist = self.ships_dir / "validation_checklist.json"
        
        # Runtime artifacts (Agent-managed)
        self.file_tree = self.ships_dir / "file_tree.json"
        self.planner_status = self.ships_dir / "planner_status.json"
    
    def ensure_directories(self) -> None:
        """Create .ships directory if it doesn't exist."""
        self.ships_dir.mkdir(parents=True, exist_ok=True)


class ArtifactManager:
    """
    Service for managing ShipS* artifacts in .ships/ directory.
    
    Provides atomic file operations, path management, and state↔disk sync.
    This is the SINGLE SOURCE OF TRUTH for artifacts.
    """
    
    # All managed artifact names
    ARTIFACT_NAMES = [
        'folder_map', 'task_list', 'api_contracts', 
        'dependency_plan', 'risk_report', 'validation_checklist',
        'file_tree', 'planner_status', 'fix_request',
        'checkpoint_history'
    ]
    
    def __init__(self, project_root: str | Path):
        """
        Initialize the artifact manager.
        
        Args:
            project_root: Path to the target project root directory
        """
        self.project_root = Path(project_root)
        self.paths = ArtifactPaths(self.project_root)
        
        # Dynamic artifact paths not in ArtifactPaths
        self._dynamic_paths = {
            'fix_request': self.paths.ships_dir / 'fix_request.json',
            'checkpoint_history': self.paths.ships_dir / 'checkpoint_history.json',
        }
        
        # Ensure .ships directory exists
        self.paths.ensure_directories()
    
    def _get_path(self, artifact_name: str) -> Optional[Path]:
        """Get path for an artifact, checking both static and dynamic paths."""
        # Check static paths first
        path = getattr(self.paths, artifact_name, None)
        if path:
            return path
        # Check dynamic paths
        return self._dynamic_paths.get(artifact_name)
    
    def load_json(self, artifact_name: str) -> Optional[dict]:
        """
        Load a JSON artifact by name.
        
        Args:
            artifact_name: Name of the artifact (e.g., 'folder_map', 'task_list')
            
        Returns:
            Parsed JSON dict or None if file doesn't exist
        """
        path = self._get_path(artifact_name)
        if not path or not path.exists():
            return None
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return None
    
    def save_json(self, artifact_name: str, data: dict) -> None:
        """
        Save a JSON artifact atomically.
        
        Args:
            artifact_name: Name of the artifact
            data: Dict to serialize
        """
        path = self._get_path(artifact_name)
        if not path:
            # Create dynamic path for unknown artifacts
            path = self.paths.ships_dir / f"{artifact_name}.json"
            self._dynamic_paths[artifact_name] = path
        
        # Atomic write
        temp_path = path.with_suffix('.tmp')
        try:
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, default=str)
            temp_path.replace(path)
        except Exception as e:
            if temp_path.exists():
                temp_path.unlink()
            raise IOError(f"Failed to save {artifact_name}: {e}")
    
    def artifact_exists(self, artifact_name: str) -> bool:
        """Check if an artifact file exists."""
        path = self._get_path(artifact_name)
        return path is not None and path.exists()
    
    def get_artifact_summary(self) -> dict[str, bool]:
        """Get existence status of all artifacts."""
        return {name: self.artifact_exists(name) for name in self.ARTIFACT_NAMES}
    
    # =========================================================================
    # SYNC METHODS: State ↔ Disk synchronization
    # =========================================================================
    
    def sync_from_disk(self) -> Dict[str, dict]:
        """
        Load all artifacts from disk into a dict.
        
        Use at pipeline START to initialize state.artifacts.
        
        Returns:
            Dict of all artifacts that exist on disk
        """
        artifacts = {}
        for name in self.ARTIFACT_NAMES:
            data = self.load_json(name)
            if data is not None:
                artifacts[name] = data
        return artifacts
    
    def sync_to_disk(self, state_artifacts: Dict[str, dict]) -> int:
        """
        Write state artifacts to disk.
        
        Use after each node to persist changes.
        
        Args:
            state_artifacts: Dict from state.artifacts
            
        Returns:
            Number of artifacts written
        """
        count = 0
        for name, data in state_artifacts.items():
            if name in self.ARTIFACT_NAMES and isinstance(data, dict):
                try:
                    self.save_json(name, data)
                    count += 1
                except Exception:
                    pass  # Don't fail pipeline on artifact write error
        return count
    
    def save_batch(self, artifacts: Dict[str, dict]) -> tuple[int, list[str]]:
        """
        Save multiple artifacts atomically.
        
        Args:
            artifacts: Dict of artifact_name -> data
            
        Returns:
            Tuple of (success_count, failed_names)
        """
        success = 0
        failed = []
        
        for name, data in artifacts.items():
            try:
                self.save_json(name, data)
                success += 1
            except Exception as e:
                failed.append(f"{name}: {e}")
        
        return success, failed




# Singleton instance
_default_manager: Optional[ArtifactManager] = None


def get_artifact_manager(project_root: Optional[str | Path] = None) -> ArtifactManager:
    """
    Get the artifact manager instance.
    
    Args:
        project_root: Optional project root path
        
    Returns:
        ArtifactManager instance
    """
    global _default_manager
    
    if project_root:
        _default_manager = ArtifactManager(project_root)
    
    if _default_manager is None:
        raise ValueError("No project root provided and no default manager exists")
    
    return _default_manager
