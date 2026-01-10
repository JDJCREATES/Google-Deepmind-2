"""
Sync Engine - Event-Driven Artifact Updates

Orchestrates artifact regeneration when files change.
Uses watchdog for Python-based file watching with debouncing.
"""

import logging
import asyncio
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Set, Callable
from datetime import datetime, timezone
from threading import Thread, Event
from collections import defaultdict
import time

logger = logging.getLogger("ships.sync")

# Try to import watchdog
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileSystemEvent
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    logger.warning("[SYNC] watchdog not installed, file watching disabled")


class ArtifactSyncEngine:
    """
    Orchestrates artifact updates when project files change.
    
    Features:
    - Debounced file event processing (500ms)
    - Incremental updates for modified files
    - Full rescan on package.json/requirements.txt changes
    """
    
    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        self.ships_dir = self.project_path / ".ships"
        
        # Event queue for debouncing
        self.pending_events: Dict[str, float] = {}
        self.debounce_ms = 500
        
        # Observer for file watching
        self.observer: Optional["Observer"] = None
        self.stop_event = Event()
        
        # Callbacks
        self.on_artifact_updated: Optional[Callable[[str], None]] = None
        
        # Track last sync times
        self.last_sync: Dict[str, datetime] = {}
        
    def start(self):
        """Start watching project for file changes."""
        if not WATCHDOG_AVAILABLE:
            logger.error("[SYNC] Cannot start - watchdog not installed")
            return False
        
        if self.observer and self.observer.is_alive():
            logger.warning("[SYNC] Already running")
            return True
        
        # Ensure .ships directory exists
        self.ships_dir.mkdir(parents=True, exist_ok=True)
        
        # Create handler
        handler = _FileChangeHandler(self)
        
        # Create observer
        self.observer = Observer()
        self.observer.schedule(handler, str(self.project_path), recursive=True)
        
        # Start observer
        self.observer.start()
        
        # Start debounce processor in background thread
        self.stop_event.clear()
        processor_thread = Thread(target=self._process_events_loop, daemon=True)
        processor_thread.start()
        
        logger.info(f"[SYNC] Started watching {self.project_path}")
        return True
    
    def stop(self):
        """Stop file watching."""
        self.stop_event.set()
        
        if self.observer:
            self.observer.stop()
            self.observer.join(timeout=2)
            self.observer = None
        
        logger.info("[SYNC] Stopped")
    
    def _process_events_loop(self):
        """Background loop to process debounced events."""
        while not self.stop_event.is_set():
            time.sleep(0.1)  # Check every 100ms
            
            now = time.time()
            events_to_process = []
            
            # Find events ready for processing
            for path, timestamp in list(self.pending_events.items()):
                if now - timestamp >= self.debounce_ms / 1000:
                    events_to_process.append(path)
            
            # Remove processed events
            for path in events_to_process:
                del self.pending_events[path]
            
            # Process events
            if events_to_process:
                self._process_file_changes(events_to_process)
    
    def _process_file_changes(self, paths: List[str]):
        """Process batched file changes."""
        logger.info(f"[SYNC] Processing {len(paths)} file changes")
        
        # Categorize changes
        package_changed = False
        code_files_changed: List[str] = []
        
        for path in paths:
            file_name = Path(path).name
            
            if file_name in ("package.json", "requirements.txt", "pyproject.toml"):
                package_changed = True
            elif Path(path).suffix.lower() in (".py", ".ts", ".tsx", ".js", ".jsx"):
                code_files_changed.append(path)
        
        # Update artifacts based on changes
        try:
            if package_changed:
                # Full rescan for dependency changes
                self._update_dependency_artifacts()
                self._update_security_artifacts()
            
            if code_files_changed:
                # Incremental update for code changes
                self._update_code_artifacts(code_files_changed)
            
            # Update sync health
            self._update_sync_health(paths)
            
        except Exception as e:
            logger.error(f"[SYNC] Error processing changes: {e}")
    
    def _update_dependency_artifacts(self):
        """Update dependency-related artifacts."""
        logger.info("[SYNC] Updating dependency artifacts...")
        
        try:
            from app.services.intelligence import DependencyAnalyzer
            
            analyzer = DependencyAnalyzer()
            analyzer.save_artifact(str(self.project_path))
            
            self.last_sync["dependency_graph.json"] = datetime.now(timezone.utc)
            
            if self.on_artifact_updated:
                self.on_artifact_updated("dependency_graph.json")
                
        except Exception as e:
            logger.error(f"[SYNC] Dependency artifact update failed: {e}")
    
    def _update_security_artifacts(self):
        """Update security artifacts."""
        logger.info("[SYNC] Updating security artifacts...")
        
        try:
            from app.services.security import SecurityScanner
            
            scanner = SecurityScanner()
            scanner.save_artifact(str(self.project_path))
            
            self.last_sync["security_report.json"] = datetime.now(timezone.utc)
            
            if self.on_artifact_updated:
                self.on_artifact_updated("security_report.json")
                
        except Exception as e:
            logger.error(f"[SYNC] Security artifact update failed: {e}")
    
    def _update_code_artifacts(self, changed_files: List[str]):
        """Update code-related artifacts incrementally."""
        logger.info(f"[SYNC] Updating code artifacts for {len(changed_files)} files...")
        
        try:
            from app.services.intelligence import CodeAnalyzer
            from app.services.intelligence.call_graph import CallGraphMerger
            
            # Update file_tree.json
            code_analyzer = CodeAnalyzer()
            code_analyzer.save_artifact(str(self.project_path))
            
            self.last_sync["file_tree.json"] = datetime.now(timezone.utc)
            
            # Update function_call_graph.json
            merger = CallGraphMerger()
            merger.save_artifact(str(self.project_path))
            
            self.last_sync["function_call_graph.json"] = datetime.now(timezone.utc)
            
            if self.on_artifact_updated:
                self.on_artifact_updated("file_tree.json")
                self.on_artifact_updated("function_call_graph.json")
                
        except Exception as e:
            logger.error(f"[SYNC] Code artifact update failed: {e}")
    
    def _update_sync_health(self, paths: List[str]):
        """Update sync_health.json with sync status."""
        health = {
            "last_sync": datetime.now(timezone.utc).isoformat(),
            "files_processed": len(paths),
            "artifacts_updated": list(self.last_sync.keys()),
            "status": "healthy"
        }
        
        health_path = self.ships_dir / "sync_health.json"
        with open(health_path, "w", encoding="utf-8") as f:
            json.dump(health, f, indent=2)
    
    def force_full_sync(self):
        """Force a full resync of all artifacts."""
        logger.info("[SYNC] Starting full sync...")
        
        try:
            from app.services.intelligence import CodeAnalyzer, DependencyAnalyzer
            from app.services.intelligence.call_graph import CallGraphMerger
            from app.services.security import SecurityScanner
            
            # Code analysis
            code_analyzer = CodeAnalyzer()
            code_analyzer.save_artifact(str(self.project_path))
            
            # Dependency analysis
            dep_analyzer = DependencyAnalyzer()
            dep_analyzer.save_artifact(str(self.project_path))
            
            # Call graph
            merger = CallGraphMerger()
            merger.save_artifact(str(self.project_path))
            
            # Security scan
            scanner = SecurityScanner()
            scanner.save_artifact(str(self.project_path))
            
            # Update last sync times
            now = datetime.now(timezone.utc)
            self.last_sync = {
                "file_tree.json": now,
                "dependency_graph.json": now,
                "function_call_graph.json": now,
                "security_report.json": now
            }
            
            self._update_sync_health(["FULL_SYNC"])
            
            logger.info("[SYNC] Full sync complete")
            return True
            
        except Exception as e:
            logger.error(f"[SYNC] Full sync failed: {e}")
            return False


class _FileChangeHandler(FileSystemEventHandler if WATCHDOG_AVAILABLE else object):
    """Watchdog event handler that queues events for debouncing."""
    
    def __init__(self, sync_engine: ArtifactSyncEngine):
        if WATCHDOG_AVAILABLE:
            super().__init__()
        self.sync_engine = sync_engine
        
        # Ignore patterns
        self.ignore_dirs = {
            ".git", "node_modules", "__pycache__", ".venv", "venv",
            "dist", "build", ".next", ".ships", "coverage"
        }
        self.ignore_extensions = {".pyc", ".pyo", ".log", ".lock"}
    
    def _should_ignore(self, path: str) -> bool:
        """Check if path should be ignored."""
        path_obj = Path(path)
        
        # Check directory components
        for part in path_obj.parts:
            if part in self.ignore_dirs or part.startswith("."):
                return True
        
        # Check extension
        if path_obj.suffix.lower() in self.ignore_extensions:
            return True
        
        return False
    
    def on_any_event(self, event: "FileSystemEvent"):
        """Handle any file system event."""
        if event.is_directory:
            return
        
        if self._should_ignore(event.src_path):
            return
        
        # Queue for debounced processing
        self.sync_engine.pending_events[event.src_path] = time.time()


# Singleton instance for the active project
_active_sync_engine: Optional[ArtifactSyncEngine] = None


def start_sync(project_path: str) -> ArtifactSyncEngine:
    """Start sync engine for a project."""
    global _active_sync_engine
    
    if _active_sync_engine:
        _active_sync_engine.stop()
    
    _active_sync_engine = ArtifactSyncEngine(project_path)
    _active_sync_engine.start()
    
    return _active_sync_engine


def stop_sync():
    """Stop the active sync engine."""
    global _active_sync_engine
    
    if _active_sync_engine:
        _active_sync_engine.stop()
        _active_sync_engine = None


def get_sync_engine() -> Optional[ArtifactSyncEngine]:
    """Get the active sync engine."""
    return _active_sync_engine
