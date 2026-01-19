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
    MAX_INSTANCES = 50  # Increased range for hashing
    
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
    def _get_deterministic_port(self, run_id: str) -> int:
        """Calculate a consistent port based on run_id."""
        import zlib
        # Use CRC32 to map string to integer range
        # Use utf-8 encoding for consistency
        offset = zlib.crc32(run_id.encode('utf-8')) % self.MAX_INSTANCES
        return self.BASE_PORT + offset
    
    def _is_port_listening(self, port: int, timeout: float = 0.5) -> bool:
        """Check if a port is actually listening/accepting connections (IPv4/IPv6)."""
        # Try 127.0.0.1 first (most common)
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(timeout)
                if s.connect_ex(('127.0.0.1', port)) == 0:
                    return True
        except: pass

        # Try localhost (might be IPv6 ::1)
        try:
            # socket.create_connection handles DNS resolution and IPv4/IPv6 automatically
            # It tries all addresses returned by getaddrinfo
            with socket.create_connection(("localhost", port), timeout=timeout):
                return True
        except: pass
        
        return False

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
        
        # Allocate port (Try Deterministic First)
        det_port = self._get_deterministic_port(run_id)
        final_port = None
        
        # Check if deterministic port is available
        if det_port not in self.port_map:
            if self._is_port_listening(det_port):
                # ZOMBIE DETECTED - Kill it!
                logger.warning(f"[PREVIEW] 🧟 Zombie process detected on port {det_port}. Killing it...")
                self._kill_process_by_port(det_port)
                # Brief wait for OS release
                import time
                time.sleep(0.5)
                
            try:
                import socket
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(('127.0.0.1', det_port))
                    final_port = det_port
            except OSError:
                logger.warning(f"[PREVIEW] ⚠️ Deterministic port {det_port} is still busy after kill attempt. Falling back.")
        
        # Fallback to search if needed
        if final_port is None:
            # First, clean zombies in the search range too
            final_port = self._find_available_port()
            
        if final_port is None:
            return {"status": "error", "message": f"No available ports (max {self.MAX_INSTANCES} previews)"}
        
        # Create instance
        instance = PreviewInstance(
            run_id=run_id,
            project_path=project_path,
            port=final_port,
            status="starting"
        )
        
        try:
            # Detect command based on project type
            cmd, use_shell = self._detect_command(project_path, final_port)
            
            creation_flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            
            logger.info(f"[PREVIEW] 🚀 Starting dev server: port={final_port}, path={project_path}, cmd={cmd}")
            
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
            self.port_map[final_port] = run_id
            
            # Start log consumer thread
            threading.Thread(
                target=self._consume_logs,
                args=(instance,),
                daemon=True
            ).start()
            
            # Wait briefly for the port to actually start listening
            # Give it up to 10 seconds to bind to the port
            import time
            max_wait = 10
            wait_interval = 0.5
            elapsed = 0
            
            logger.info(f"[PREVIEW] ⏳ Waiting for port {final_port} to start listening...")
            
            while elapsed < max_wait:
                if not instance.is_alive():
                    # Process died immediately - check logs for error
                    error_msg = "Process crashed on startup"
                    if instance.logs:
                        # Get all logs, not just the last one
                        full_logs = "\n".join(instance.logs[-10:]) if len(instance.logs) > 10 else "\n".join(instance.logs)
                        error_msg = f"Dev server crashed:\n{full_logs}"
                    instance.status = "error"
                    instance.error_message = error_msg
                    logger.error(f"[PREVIEW] ❌ Process died: {error_msg}")
                    return {
                        "status": "error",
                        "message": error_msg,
                        "logs": instance.logs
                    }
                
                if self._is_port_listening(final_port):
                    instance.status = "running"
                    instance.url = f"http://localhost:{final_port}"
                    self._update_current(instance)
                    logger.info(f"[PREVIEW] ✅ Port {final_port} is now listening!")
                    self.focus_requested = True
                    return {
                        "status": "running",
                        "url": instance.url,
                        "port": final_port,
                        "run_id": run_id
                    }
                
                time.sleep(wait_interval)
                elapsed += wait_interval
            
            # Timeout - port never started listening
            instance.status = "error"
            recent_logs = "\n".join(instance.logs[-5:]) if instance.logs else "No logs"
            instance.error_message = f"Port {final_port} not listening after {max_wait}s. Logs:\n{recent_logs}"
            logger.error(f"[PREVIEW] ⏰ Timeout waiting for port {final_port}")
            
            return {
                "status": "error",
                "message": f"Dev server did not start listening on port {final_port}",
                "port": final_port,
                "logs": instance.logs[-10:]
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
                    port=final_port or 0,
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
                
                # Detect errors in logs
                line_clean = self.ANSI_ESCAPE.sub('', line_stripped).lower()
                if any(err in line_clean for err in ['failed to compile', 'error:', 'fatal', 'cannot find module', 'syntaxerror']):
                    instance.status = "error"
                    instance.error_message = line_stripped[:200]  # Keep first 200 chars
                    logger.error(f"[PREVIEW] Dev server error detected: {line_stripped}")
                
                # Try to detect URL
                if not instance.url:
                    line_clean_url = self.ANSI_ESCAPE.sub('', line_stripped)
                    if "localhost" in line_clean_url.lower() or "127.0.0.1" in line_clean_url:
                        match = self._url_pattern.search(line_clean_url)
                        if match:
                            instance.url = match.group(0)
                            if instance.status != "error":  # Don't override error status
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

    def kill_zombies(self) -> Dict[str, Any]:
        """
        Force kill all processes on preview ports (5200-5210).
        Useful when backend restarts and loses track of child processes.
        """
        killed_count = 0
        logger.info("[PREVIEW] 🧟 Killing zombie processes on ports...")
        
        # 1. Stop known instances first
        self.stop_all()
        
        # 2. Sweep the port range
        for port in range(self.BASE_PORT, self.BASE_PORT + self.MAX_INSTANCES):
            # Check if port is in use
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(0.1)
                    if s.connect_ex(('127.0.0.1', port)) == 0:
                        # Port is open (in use)
                        logger.info(f"[PREVIEW] Found zombie on port {port}")
                        self._kill_process_by_port(port)
                        killed_count += 1
            except Exception:
                pass
                
        return {"status": "success", "killed_count": killed_count}

    def kill_run_process(self, run_id: str, project_path: str = None) -> Dict[str, Any]:
        """
        Kill the SPECIFIC process for a run.
        Strategy:
        1. Stop known instance (graceful).
        2. Kill by CWD (Nuclear - releases file locks).
        3. Kill by Port (Cleanup).
        """
        # 1. Diagnose first
        self.diagnose_ports()
        
        results = []
        
        # 2. Stop if known
        self._stop_instance(run_id)
        
        # 3. Kill anyone in that folder (Fixes file lock issues)
        target_path = project_path
        if not target_path and run_id in self.instances:
            target_path = self.instances[run_id].project_path
            
        if target_path:
            if self._kill_by_cwd(target_path):
                results.append(f"Killed by CWD ({target_path})")
        else:
             results.append("No path known - skipping CWD kill")

        # 4. Force kill port (Zombie Killer)
        det_port = self._get_deterministic_port(run_id)
        self._kill_process_by_port(det_port)
        results.append(f"Cleaned port {det_port}")
        
        logger.info(f"[PREVIEW] 🎯 Targeted kill for run {run_id}: {', '.join(results)}")
        return {"status": "success", "killed_port": det_port, "details": results}

    def diagnose_ports(self):
        """Log all processes running on preview ports."""
        try:
            import psutil
            logger.info("="*50)
            logger.info("[PREVIEW DIAGNOSTIC] Scanning ports 5200-5250...")
            found = False
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    for conn in proc.connections(kind='inet'):
                        if self.BASE_PORT <= conn.laddr.port < (self.BASE_PORT + self.MAX_INSTANCES):
                            logger.info(f"  ❌ PORT {conn.laddr.port}: {proc.info['name']} (PID: {proc.pid})")
                            found = True
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                     continue
            if not found:
                logger.info("  ✓ No active processes on preview ports.")
            logger.info("="*50)
        except ImportError:
            logger.error("psutil not installed, cannot diagnose ports.")
        except Exception as e:
            logger.error(f"Diagnostic failed: {e}")
    
    def _kill_by_cwd(self, project_path: str) -> int:
        """Kill any process running in the project directory."""
        if not project_path: return 0
        killed = 0
        try:
            import psutil
            norm_path = os.path.normpath(project_path).lower()
            
            for proc in psutil.process_iter(['pid', 'name', 'cwd']):
                try:
                    p_cwd = proc.info.get('cwd')
                    if p_cwd:
                        p_norm = os.path.normpath(p_cwd).lower()
                        # Check if process is INSIDE the project path
                        if norm_path in p_norm:
                            logger.info(f"[PREVIEW] 🔪 Killing process in CWD: {proc.info['name']} ({proc.pid})")
                            proc.kill()
                            killed += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except ImportError:
            logger.error("psutil not installed")
        except Exception as e:
            logger.error(f"Error killing by CWD: {e}")
        return killed

    def _kill_process_by_port(self, port: int):
        """Kill any process listening on the port using robust methods."""
        # Method 1: Windows Taskkill (Most Robust for Windows)
        if os.name == 'nt':
            try:
                # Find PID using netstat (more reliable than psutil sometimes for zombies)
                cmd = f'netstat -ano | findstr :{port}'
                # We use shell=True to pipe
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                
                killed_any = False
                for line in result.stdout.splitlines():
                    parts = line.strip().split()
                    # Proto Local Address Foreign Address State PID
                    # TCP    0.0.0.0:5200   0.0.0.0:0       LISTENING   1234
                    if len(parts) >= 5:
                        pid = parts[-1]
                        if pid.isdigit() and pid != "0":
                            logger.info(f"[PREVIEW] 🔪 TaskKilling PID {pid} on port {port}")
                            subprocess.run(f"taskkill /F /T /PID {pid}", shell=True, capture_output=True)
                            killed_any = True
                
                if killed_any:
                    return
            except Exception as e:
                logger.error(f"[PREVIEW] Taskkill failed: {e}")

        # Method 2: Cross-platform psutil (Fallback)
        try:
            import psutil
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    for conn in proc.connections(kind='inet'):
                        if conn.laddr.port == port:
                            logger.info(f"[PREVIEW] 🔪 PSUtil Killing zombie on port {port}: {proc.info['name']} ({proc.pid})")
                            proc.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except ImportError:
            pass
        except Exception as e:
            logger.error(f"Error killing by port (psutil): {e}")

    def _kill_process_by_port_legacy(self, port: int):
        """Kill any process listening on the port (Windows Netstat fallback)."""
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

    def get_status(self, run_id: str = None) -> Dict[str, Any]:
        """Get status of a specific instance or all."""
        if run_id:
            if run_id in self.instances:
                instance = self.instances[run_id]
                return {
                    "run_id": run_id,
                    "status": instance.status,
                    "url": instance.url,
                    "port": instance.port,
                    "is_alive": instance.is_alive(),
                    "error": instance.error_message,
                    "logs": instance.logs[-20:]
                }
            
            # Not running, but return deterministic info
            det_port = self._get_deterministic_port(run_id)
            return {
                "run_id": run_id,
                "status": "stopped",
                "url": f"http://localhost:{det_port}",
                "port": det_port,
                "is_alive": False,
                "error": None,
                "logs": []
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
