"""
ShipS* Artifact Manager Service

Manages artifacts in the flat .ships/ directory structure.
All artifacts are JSON files stored directly in .ships/.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

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
    
    Provides atomic file operations and path management.
    """
    
    def __init__(self, project_root: str | Path):
        """
        Initialize the artifact manager.
        
        Args:
            project_root: Path to the target project root directory
        """
        self.project_root = Path(project_root)
        self.paths = ArtifactPaths(self.project_root)
        
        # Ensure .ships directory exists
        self.paths.ensure_directories()
    
    def load_json(self, artifact_name: str) -> Optional[dict]:
        """
        Load a JSON artifact by name.
        
        Args:
            artifact_name: Name of the artifact (e.g., 'folder_map', 'task_list')
            
        Returns:
            Parsed JSON dict or None if file doesn't exist
        """
        path = getattr(self.paths, artifact_name, None)
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
        path = getattr(self.paths, artifact_name, None)
        if not path:
            raise ValueError(f"Unknown artifact: {artifact_name}")
        
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
        path = getattr(self.paths, artifact_name, None)
        return path is not None and path.exists()
    
    def get_artifact_summary(self) -> dict[str, bool]:
        """Get existence status of all artifacts."""
        artifacts = [
            'folder_map', 'task_list', 'implementation_plan',
            'api_contracts', 'dependency_plan', 'risk_report',
            'validation_checklist', 'file_tree', 'planner_status'
        ]
        return {name: self.artifact_exists(name) for name in artifacts}


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
