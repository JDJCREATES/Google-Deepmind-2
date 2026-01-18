"""
Multi-Preview Manager for ShipS.

Manages multiple preview dev servers - one per project/run.
Each project gets its own port, and startup is robust with npm install checks.
"""

import subprocess
import threading
import os
import socket
import re
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger("ships.preview")


@dataclass
class PreviewInstance:
    """Represents a single running preview server."""
    run_id: str
    project_path: str
    port: int
    process: Optional[subprocess.Popen] = None
    url: Optional[str] = None
    status: str = "stopped"  # stopped, starting, running, error
    logs: List[str] = field(default_factory=list)
    error_message: Optional[str] = None
    
    def is_alive(self) -> bool:
        """Check if the process is actually running."""
        return self.process is not None and self.process.poll() is None


class MultiPreviewManager:
    """
    Manages multiple preview dev servers.
    
    Each run/project gets its own PreviewInstance on a unique port.
    Provides robust startup with npm install checks and proper error handling.
    """
    
    # Port range for preview servers
    BASE_PORT = 5200
    MAX_INSTANCES = 10  # Maximum concurrent previews
    
    # ANSI escape codes (for log parsing)
    ANSI_ESCAPE = re.compile(r'\x1b\[[0-9;]*m')
    
    def __init__(self):
        self.instances: Dict[str, PreviewInstance] = {}  # run_id -> PreviewInstance
        self.port_map: Dict[int, str] = {}  # port -> run_id
        self._url_pattern = re.compile(r'https?://(?:localhost|127\.0\.0\.1):\d+')
        self.focus_requested: bool = False
        
        # For backward compatibility
        self.current_project_path: Optional[str] = None
        self.current_url: Optional[str] = None
        self.logs: List[str] = []
        self.process: Optional[subprocess.Popen] = None
    
    def _find_available_port(self) -> Optional[int]:
        """Find an available port starting from BASE_PORT."""
        for port in range(self.BASE_PORT, self.BASE_PORT + self.MAX_INSTANCES):
            if port in self.port_map:
                continue
            # Check if port is actually free
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(('127.0.0.1', port))
                    return port
            except OSError:
                continue
        return None
    
    def _detect_command(self, project_path: str, port: int) -> tuple[str | list[str], bool]:
        """
        Detect the correct start command based on project files.
        Returns (command, is_shell_needed).
        """
        import shutil
        
        # 1. NodeJS
        pkg_json = Path(project_path) / "package.json"
        if pkg_json.exists():
            npm_path = shutil.which('npm') or 'npm'
            
            if os.name == 'nt':
                return f'"{npm_path}" run dev -- --port {port}', True
            else:
                return [npm_path, "run", "dev", "--", "--port", str(port)], False
                
        # 2. Python (FastAPI/Flask)
        if (Path(project_path) / "requirements.txt").exists() or (Path(project_path) / "pyproject.toml").exists():
            has_main = (Path(project_path) / "main.py").exists()
            has_app = (Path(project_path) / "app.py").exists()
            python_path = shutil.which('python') or 'python'
            
            if has_main:
                # FastAPI/Uvicorn
                if os.name == 'nt':
                    return f'"{python_path}" -m uvicorn main:app --reload --port {port}', True
                else:
                    return [python_path, "-m", "uvicorn", "main:app", "--reload", "--port", str(port)], False
            
            if has_app:
                # Flask
                if os.name == 'nt':
                    return f'"{python_path}" -m flask run --port {port}', True
                else:
                    return [python_path, "-m", "flask", "run", "--port", str(port)], False

        # 3. Go
        if (Path(project_path) / "go.mod").exists():
            go_path = shutil.which('go') or 'go'
            if os.name == 'nt':
                 return f'"{go_path}" run . --port {port}', True
            else:
                 return [go_path, "run", ".", "--port", str(port)], False

        # Fallback to NPM
        npm_path = shutil.which('npm') or 'npm'
        if os.name == 'nt':
            return f'"{npm_path}" run dev -- --port {port}', True
        else:
            return [npm_path, "run", "dev", "--", "--port", str(port)], False

    def _check_npm_installed(self, project_path: str) -> bool:
        """Check if node_modules exists, run npm install if not."""
        node_modules = Path(project_path) / "node_modules"
        package_json = Path(project_path) / "package.json"
        
        if not package_json.exists():
            # Allow if Python or Go project
            if (Path(project_path) / "requirements.txt").exists() or \
               (Path(project_path) / "pyproject.toml").exists() or \
               (Path(project_path) / "go.mod").exists():
               return True
               
            logger.warning(f"[PREVIEW] No package.json/requirements.txt in {project_path}")
            return False
        
        if not node_modules.exists():
            logger.info(f"[PREVIEW] 📦 Running npm install in {project_path}...")
            try:
                import shutil
                npm_path = shutil.which('npm')
                if not npm_path:
                    return False
                
                result = subprocess.run(
                    [npm_path, "install"],
                    cwd=project_path,
                    capture_output=True,
                    text=True,
                    timeout=120  # 2 minutes timeout
                )
                
                if result.returncode != 0:
                    logger.error(f"[PREVIEW] npm install failed: {result.stderr[:500]}")
                    return False
                
                logger.info(f"[PREVIEW] ✅ npm install completed")
            except Exception as e:
                logger.error(f"[PREVIEW] npm install error: {e}")
                return False
        
        return True
    
    def get_or_start(self, run_id: str, project_path: str) -> Dict[str, Any]:
        """
        Get existing preview or start a new one.
        This is the main entry point - ensures the preview is running.
        
        Returns:
            Dict with status, url, port, etc.
        """
        logger.info(f"[PREVIEW] get_or_start for run={run_id}, path={project_path}")
        
        # 1. OPTIONAL: Time Travel / Branch Switching (Production Hardening)
        # If run_id is specific, try to checkout its branch to match state
        if run_id and run_id != "default":
            try:
                # Import here to avoid circular dependencies
                from app.services.git_checkpointer import get_checkpointer
                git_service = get_checkpointer(project_path)
                
                # Derive branch name logic (matches pipeline.py)
                branch_short = run_id[:8] if "-" in run_id else run_id
                target_branch = f"ships/run/{branch_short}"
                
                current = git_service.get_current_branch()
                if current != target_branch:
                   # Only switch if branch exists
                   # use underlying git command to check existence without overhead
                   if git_service._run_git(["rev-parse", "--verify", target_branch]).returncode == 0:
                        logger.info(f"[PREVIEW] 🔄 Switching to run branch: {target_branch}")
                        git_service.stash_changes(f"Auto-stash before previewing {run_id}")
                        git_service._run_git(["checkout", target_branch])
            except Exception as e:
                logger.warning(f"[PREVIEW] ⚠️ Could not switch branch for run {run_id}: {e}")

        # 2. Check for existing instance
        if run_id in self.instances:
            instance = self.instances[run_id]
            
            # If same project and still alive, just return it
            if instance.project_path == project_path and instance.is_alive():
                logger.info(f"[PREVIEW] ✓ Using existing preview on port {instance.port}")
                self._update_current(instance)
                return {
                    "status": "running",
                    "url": instance.url,
                    "port": instance.port,
                    "run_id": run_id
                }
            
            # Different project or dead - clean up first
            self._stop_instance(run_id)
        
        # Start new preview
        return self._start_instance(run_id, project_path)
    
    def _start_instance(self, run_id: str, project_path: str) -> Dict[str, Any]:
        """Start a new preview instance."""
        
        # Validate path
        if not os.path.exists(project_path):
            return {"status": "error", "message": f"Path not found: {project_path}"}
        
        # Check package.json and npm install
        if not self._check_npm_installed(project_path):
            return {"status": "error", "message": "Failed to install dependencies. Check package.json."}
        
        # Allocate port
        port = self._find_available_port()
        if port is None:
            return {"status": "error", "message": f"No available ports (max {self.MAX_INSTANCES} previews)"}
        
        # Create instance
        instance = PreviewInstance(
            run_id=run_id,
            project_path=project_path,
            port=port,
            status="starting"
        )
        
        try:
            # Detect command based on project type
            cmd, use_shell = self._detect_command(project_path, port)
            
            creation_flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            
            logger.info(f"[PREVIEW] 🚀 Starting dev server: port={port}, path={project_path}, cmd={cmd}")
            
            instance.process = subprocess.Popen(
                cmd,
                cwd=project_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                creationflags=creation_flags,
                shell=use_shell
            )
            
            # Register instance
            self.instances[run_id] = instance
            self.port_map[port] = run_id
            
            # Start log consumer thread
            threading.Thread(
                target=self._consume_logs,
                args=(instance,),
                daemon=True
            ).start()
            
            # DON'T BLOCK - return immediately and let polling detect URL
            # The log consumer thread will set instance.url when detected
            instance.status = "starting"
            self._update_current(instance)
            
            # Set default URL immediately so ships-preview has something to load
            instance.url = f"http://localhost:{port}"
            self.current_url = instance.url  # Ensure backward compat
            
            logger.info(f"[PREVIEW] 📡 Process started, URL will be: {instance.url}")
            
            # Request focus so ships-preview comes to front
            self.focus_requested = True
            
            return {
                "status": "starting",
                "url": instance.url,
                "port": port,
                "run_id": run_id,
                "message": "Dev server starting, poll /preview/status for updates"
            }
            
        except Exception as e:
            logger.error(f"[PREVIEW] Failed to start: {e}")
            # Don't cleanup - keep instance to report error
            if run_id in self.instances:
                self.instances[run_id].status = "error"
                self.instances[run_id].error_message = str(e)
            else:
                # Create a placeholder instance for the error
                self.instances[run_id] = PreviewInstance(
                    run_id=run_id,
                    project_path=project_path,
                    port=port or 0,
                    status="error",
                    error_message=str(e)
                )
            
            return {"status": "error", "message": str(e)}
    
    def _consume_logs(self, instance: PreviewInstance):
        """Background thread to consume process stdout."""
        if not instance.process or not instance.process.stdout:
            return
        
        try:
            for line in instance.process.stdout:
                line_stripped = line.strip()
                instance.logs.append(line_stripped)
                
                # Keep log size manageable
                if len(instance.logs) > 500:
                    instance.logs.pop(0)
                
                # Try to detect URL
                if not instance.url:
                    line_clean = self.ANSI_ESCAPE.sub('', line_stripped)
                    if "localhost" in line_clean.lower() or "127.0.0.1" in line_clean:
                        match = self._url_pattern.search(line_clean)
                        if match:
                            instance.url = match.group(0)
                            instance.status = "running"
                            self.focus_requested = True
                            logger.info(f"[PREVIEW] Detected URL: {instance.url}")
                            
        except Exception as e:
            instance.logs.append(f"[Error] {e}")
        finally:
            if not instance.is_alive():
                instance.status = "stopped"
    
    def _update_current(self, instance: PreviewInstance):
        """Update backward-compatible current_* fields."""
        self.current_project_path = instance.project_path
        self.current_url = instance.url
        self.logs = instance.logs
        self.process = instance.process
    
    def _stop_instance(self, run_id: str):
        """Stop and remove a preview instance."""
        if run_id not in self.instances:
            return
        
        instance = self.instances[run_id]
        logger.info(f"[PREVIEW] Stopping instance for run={run_id}")
        
        # Terminate process
        # Terminate process tree
        if instance.process:
            try:
                # On Windows with shell=True, we must kill the tree
                if os.name == 'nt':
                    subprocess.run(f"taskkill /F /T /PID {instance.process.pid}", shell=True, capture_output=True)
                else:
                    instance.process.terminate()
            except Exception:
                pass
        
        # Kill any remaining processes on that port
        self._kill_process_by_port(instance.port)
        
        self._cleanup_instance(run_id)
    
    def _cleanup_instance(self, run_id: str):
        """Clean up instance from tracking."""
        if run_id in self.instances:
            instance = self.instances[run_id]
            if instance.port in self.port_map:
                del self.port_map[instance.port]
            del self.instances[run_id]
    
    def _kill_process_by_port(self, port: int):
        """Kill any process listening on the port (Windows)."""
        if os.name != 'nt':
            return
        
        try:
            cmd = f'netstat -ano | findstr :{port}'
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            
            pids = set()
            for line in result.stdout.splitlines():
                parts = line.split()
                if len(parts) >= 5:
                    pid = parts[-1]
                    if pid.isdigit() and pid != "0":
                        pids.add(pid)
            
            for pid in pids:
                subprocess.run(f"taskkill /F /T /PID {pid}", shell=True, capture_output=True)
        except Exception as e:
            logger.debug(f"Kill by port failed: {e}")
    
    def stop_all(self):
        """Stop all preview instances."""
        for run_id in list(self.instances.keys()):
            self._stop_instance(run_id)
    
    def get_status(self, run_id: str = None) -> Dict[str, Any]:
        """Get status of a specific instance or all."""
        if run_id and run_id in self.instances:
            instance = self.instances[run_id]
            return {
                "run_id": run_id,
                "status": instance.status,
                "url": instance.url,
                "port": instance.port,
                "is_alive": instance.is_alive(),
                "logs": instance.logs[-20:]
            }
        
        # Return summary of all
        return {
            "active_count": len(self.instances),
            "instances": {
                rid: {
                    "status": inst.status,
                    "url": inst.url,
                    "port": inst.port,
                    "is_alive": inst.is_alive()
                }
                for rid, inst in self.instances.items()
            }
        }
    
    # Backward compatibility methods
    def start_dev_server(self, project_path: str) -> Dict[str, Any]:
        """Backward compatible - uses 'default' run_id."""
        return self.get_or_start("default", project_path)
    
    def stop_dev_server(self) -> Dict[str, str]:
        """Backward compatible - stops 'default' run."""
        self._stop_instance("default")
        return {"status": "stopped"}
    
    def request_focus(self):
        self.focus_requested = True
    
    def clear_focus_request(self):
        self.focus_requested = False
    
    def open_system_terminal(self, project_path: str) -> Dict[str, str]:
        """Open a native terminal in the project path."""
        if not os.path.exists(project_path):
            return {"status": "error", "message": f"Path not found: {project_path}"}
        
        try:
            if os.name == 'nt':
                subprocess.Popen(
                    f'start powershell -NoExit -Command "cd \'{project_path}\'"',
                    shell=True
                )
            else:
                subprocess.Popen(["open", "-a", "Terminal", project_path])
            return {"status": "success"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


# Singleton instance (replaces old preview_manager)
preview_manager = MultiPreviewManager()
