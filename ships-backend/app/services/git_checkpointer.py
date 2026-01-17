"""
ShipS* Git Checkpointer Service

Manages git commits at key milestones during agent execution.
This enables rollback capability and provides audit trail.
"""

import subprocess
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List

from pydantic import BaseModel, Field

logger = logging.getLogger("ships.git")


class CheckpointRecord(BaseModel):
    """Record of a single checkpoint."""
    
    milestone: str
    commit_hash: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    message: str = ""
    files_changed: int = 0
    success: bool = True
    error: Optional[str] = None


class CheckpointHistory(BaseModel):
    """History of all checkpoints in a run."""
    
    run_id: Optional[str] = None
    project_path: str
    checkpoints: List[CheckpointRecord] = Field(default_factory=list)
    
    def add(self, record: CheckpointRecord) -> None:
        """Add a checkpoint record."""
        self.checkpoints.append(record)
    
    def get_last_successful(self) -> Optional[CheckpointRecord]:
        """Get the last successful checkpoint."""
        for cp in reversed(self.checkpoints):
            if cp.success and cp.commit_hash:
                return cp
        return None


class GitCheckpointer:
    """
    Manages git commits at key milestones.
    
    Milestones:
    - plan_ready: After planner generates implementation plan
    - scaffolding_complete: After project is scaffolded
    - implementation_complete: After coder finishes all files
    - validation_passed: After validator passes
    - fix_applied: After fixer applies a fix
    """
    
    MILESTONES = {
        "plan_ready": "🎯 Plan generated",
        "scaffolding_complete": "🏗️ Project scaffolded", 
        "implementation_complete": "💻 Implementation complete",
        "validation_passed": "✅ Validation passed",
        "fix_applied": "🔧 Fix applied",
        "run_complete": "🚀 Run complete",
    }
    
    def __init__(self, project_path: str, run_id: Optional[str] = None):
        """
        Initialize the git checkpointer.
        
        Args:
            project_path: Path to the project directory
            run_id: Optional run ID for tracking
        """
        self.project_path = Path(project_path)
        self.run_id = run_id
        self.is_git_repo = (self.project_path / ".git").exists()
        self.history = CheckpointHistory(
            run_id=run_id,
            project_path=str(project_path)
        )
    
    def _run_git(self, args: List[str], check: bool = False) -> subprocess.CompletedProcess:
        """Run a git command in the project directory."""
        try:
            return subprocess.run(
                ["git"] + args,
                cwd=self.project_path,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',  # Replace invalid UTF-8 sequences
                check=check,
                timeout=30  # Prevent hanging
            )
        except subprocess.TimeoutExpired:
            logger.error(f"[GIT] Command timed out: git {' '.join(args)}")
            raise
    
    def init_repo_if_needed(self) -> bool:
        """
        Initialize git repo if it doesn't exist.
        
        Returns:
            True if repo exists/was created, False on error
        """
        if self.is_git_repo:
            return True
        
        try:
            result = self._run_git(["init"])
            if result.returncode == 0:
                self.is_git_repo = True
                logger.info(f"[GIT] Initialized repo at {self.project_path}")
                
                # Create initial gitignore
                gitignore_path = self.project_path / ".gitignore"
                if not gitignore_path.exists():
                    gitignore_content = """# Dependencies
node_modules/
.venv/
venv/
__pycache__/

# Build
dist/
build/
.next/
.nuxt/

# IDE
.idea/
.vscode/

# OS
.DS_Store
Thumbs.db

# Environment
.env
.env.local
"""
                    gitignore_path.write_text(gitignore_content)
                    logger.info("[GIT] Created .gitignore")
                
                return True
            else:
                logger.error(f"[GIT] Failed to init: {result.stderr}")
                return False
        except Exception as e:
            logger.error(f"[GIT] Init failed: {e}")
            return False
    
    def checkpoint(
        self, 
        milestone: str, 
        details: str = "",
        force: bool = False
    ) -> Optional[str]:
        """
        Create a checkpoint commit.
        
        Args:
            milestone: Milestone name (key in MILESTONES dict)
            details: Additional details for commit message
            force: If True, commit even if nothing changed
            
        Returns:
            Commit hash if successful, None otherwise
        """
        if not self.is_git_repo:
            if not self.init_repo_if_needed():
                return None
        
        record = CheckpointRecord(milestone=milestone)
        
        try:
            # Stage all changes
            self._run_git(["add", "-A"])
            
            # Check if there are changes to commit
            status = self._run_git(["status", "--porcelain"])
            if not status.stdout.strip() and not force:
                logger.info(f"[GIT] No changes to commit for {milestone}")
                record.message = "No changes"
                record.files_changed = 0
                self.history.add(record)
                return None
            
            # Build commit message
            milestone_msg = self.MILESTONES.get(milestone, milestone)
            message = f"[ShipS] {milestone_msg}"
            if details:
                message += f"\n\n{details}"
            if self.run_id:
                message += f"\n\nRun: {self.run_id}"
            
            # Commit
            commit_args = ["commit", "-m", message]
            if force:
                commit_args.append("--allow-empty")
            
            result = self._run_git(commit_args)
            
            if result.returncode == 0:
                # Get commit hash
                hash_result = self._run_git(["rev-parse", "HEAD"])
                commit_hash = hash_result.stdout.strip()
                
                # Count files changed
                diff_result = self._run_git(["diff", "--stat", "HEAD~1", "HEAD"])
                files_changed = len([l for l in diff_result.stdout.split("\n") if l.strip() and "|" in l])
                
                record.commit_hash = commit_hash
                record.message = message.split("\n")[0]
                record.files_changed = files_changed
                record.success = True
                
                logger.info(f"[GIT] ✅ Checkpoint: {milestone} -> {commit_hash[:8]} ({files_changed} files)")
            else:
                record.success = False
                record.error = result.stderr
                logger.warning(f"[GIT] ⚠️ Commit failed for {milestone}: {result.stderr}")
        
        except Exception as e:
            record.success = False
            record.error = str(e)
            logger.error(f"[GIT] ❌ Checkpoint error: {e}")
        
        self.history.add(record)
        return record.commit_hash
    
    def rollback(self, commit_hash: str) -> bool:
        """
        Rollback to a specific checkpoint.
        
        Args:
            commit_hash: Commit hash to rollback to
            
        Returns:
            True if successful, False otherwise
        """
        if not self.is_git_repo:
            logger.error("[GIT] Cannot rollback: not a git repo")
            return False
        
        try:
            result = self._run_git(["reset", "--hard", commit_hash])
            if result.returncode == 0:
                logger.info(f"[GIT] ✅ Rolled back to {commit_hash[:8]}")
                return True
            else:
                logger.error(f"[GIT] ❌ Rollback failed: {result.stderr}")
                return False
        except Exception as e:
            logger.error(f"[GIT] ❌ Rollback error: {e}")
            return False
    
    def rollback_to_last_success(self) -> bool:
        """
        Rollback to the last successful checkpoint.
        
        Returns:
            True if successful, False otherwise
        """
        last_success = self.history.get_last_successful()
        if last_success and last_success.commit_hash:
            return self.rollback(last_success.commit_hash)
        
        logger.warning("[GIT] No successful checkpoint to rollback to")
        return False
    
    def get_history(self) -> CheckpointHistory:
        """Get checkpoint history."""
        return self.history
    
    def save_history(self) -> None:
        """Save checkpoint history to .ships/checkpoint_history.json"""
        ships_dir = self.project_path / ".ships"
        ships_dir.mkdir(parents=True, exist_ok=True)
        
        history_path = ships_dir / "checkpoint_history.json"
        history_path.write_text(self.history.model_dump_json(indent=2))
        logger.debug(f"[GIT] Saved checkpoint history to {history_path}")


# Singleton instance per project
_checkpointers: Dict[str, GitCheckpointer] = {}


def get_checkpointer(project_path: str, run_id: Optional[str] = None) -> GitCheckpointer:
    """
    Get or create a GitCheckpointer for a project.
    
    Args:
        project_path: Path to the project
        run_id: Optional run ID
        
    Returns:
        GitCheckpointer instance
    """
    global _checkpointers
    
    key = str(Path(project_path).resolve())
    
    if key not in _checkpointers or run_id:
        _checkpointers[key] = GitCheckpointer(project_path, run_id)
    
    return _checkpointers[key]
