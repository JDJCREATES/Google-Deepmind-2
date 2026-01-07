import subprocess
import threading
import os
import signal
import re
from typing import Optional, List, Dict, Any

class PreviewManager:
    """
    Manages the lifecycle of the user's project development server.
    
    Responsible for spawning the `npm run dev` process, capturing its output,
    extracting the local server URL, and handling graceful shutdowns.
    """
    
    # Default port for ShipS preview servers (avoid 5173 conflict)
    SHIPS_DEV_PORT = "5177"
    
    # Pattern to strip ANSI escape codes (colors) from terminal output
    # Vite outputs: \x1b[36mhttp://localhost:5177/\x1b[0m
    ANSI_ESCAPE = re.compile(r'\x1b\[[0-9;]*m')

    def __init__(self):
        self.process: Optional[subprocess.Popen] = None
        self.logs: List[str] = []
        self.current_url: Optional[str] = None
        self.is_running: bool = False
        self.current_project_path: Optional[str] = None  # Track the current project path
        # Enhanced URL pattern to catch various formats:
        # - Vite: "Local:   http://localhost:5177/"
        # - Next.js: "- Local: http://localhost:3000"
        # - Plain: "http://localhost:5177"
        self._url_pattern = re.compile(r'https?://(?:localhost|127\.0\.0\.1):\d+')
        self.focus_requested: bool = False  # Flag for frontend to request electron focus
    
    @classmethod
    def strip_ansi(cls, text: str) -> str:
        """Remove ANSI escape codes from text for reliable pattern matching."""
        return cls.ANSI_ESCAPE.sub('', text)

    def start_dev_server(self, project_path: str) -> Dict[str, Any]:
        """
        Starts the development server for the specified project.

        Args:
            project_path (str): The absolute path to the project directory.

        Returns:
            Dict[str, Any]: A dictionary containing the status of the operation and process ID.
        
        Raises:
            FileNotFoundError: If the project path does not exist.
        """
        if not os.path.exists(project_path):
            return {"status": "error", "message": f"Project path not found: {project_path}"}

        if self.is_running and self.process:
            self.stop_dev_server()

        self.logs = []
        self.current_url = None
        
        try:
            # Determine command based on OS, using class-level port constant
            if os.name == 'nt':
                cmd = ["npm.cmd", "run", "dev", "--", "--port", self.SHIPS_DEV_PORT]
            else:
                cmd = ["npm", "run", "dev", "--", "--port", self.SHIPS_DEV_PORT]
            
            print(f"[PreviewManager] Starting dev server on port {self.SHIPS_DEV_PORT}")
            print(f"[PreviewManager] Command: {' '.join(cmd)}")
            print(f"[PreviewManager] CWD: {project_path}")
            
            # Spawn process without opening a new window (Windows specific)
            creation_flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0

            self.process = subprocess.Popen(
                cmd,
                cwd=project_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                creationflags=creation_flags
            )
            self.is_running = True
            self.current_project_path = project_path  # Store the project path
            
            # Start a background thread to consume logs and detect URL
            threading.Thread(target=self._consume_logs, daemon=True).start()
            
            return {
                "status": "starting", 
                "pid": self.process.pid, 
                "message": "Development server starting..."
            }

        except Exception as e:
            self.is_running = False
            return {"status": "error", "message": f"Failed to start server: {str(e)}"}

    def stop_dev_server(self) -> Dict[str, str]:
        """
        Stops the currently running development server.
        """
        if self.process:
            try:
                # 1. Standard Termination
                self.process.terminate()
            except Exception as e:
                print(f"Error terminating process: {e}")

        # 2. Aggressive Cleanup (Windows)
        # Even if self.process is None, we might have zombie node processes.
        # We search for any node.exe running in this project path.
        if os.name == 'nt' and self.current_project_path:
            self._kill_processes_by_path(self.current_project_path)

        self.process = None
        self.is_running = False
        self.current_url = None

        return {"status": "stopped"}

    def _kill_processes_by_path(self, project_path: str):
        """
        Aggressively kills all node.exe and npm.exe processes running from the given project path
        using PowerShell and WMI. This is required because npm often spawns detached 
        child processes (vite, node) that survive simple termination.
        """
        try:
            # Normalize path for WMI comparison (double backslashes are safer for WQL but we use PowerShell filtering)
            # We want to match command lines containing this path.
            normalized_path = project_path.replace("\\", "\\\\")
            
            # PowerShell command - kill both node.exe AND npm.exe
            # Also kill any process on the dev server port
            for process_name in ['node.exe', 'npm.exe', 'npx.exe']:
                ps_command = (
                    f"Get-CimInstance Win32_Process -Filter \"Name = '{process_name}'\" | "
                    f"Where-Object {{ $_.CommandLine -like '*{normalized_path}*' }} | "
                    f"ForEach-Object {{ Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }}"
                )
                
                subprocess.run(
                    ["powershell", "-NoProfile", "-Command", ps_command],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=5
                )
        except Exception as e:
            print(f"Failed to execute aggressive process kill: {e}")
        
        return {"status": "not_running"}

    def _consume_logs(self):
        """
        Internal method to consume stdout from the subprocess.
        Runs in a separate thread to prevent blocking.
        Populates self.logs and attempts to extract the server URL.
        """
        if not self.process or not self.process.stdout:
            return

        try:
            for line in self.process.stdout:
                line_stripped = line.strip()
                self.logs.append(line_stripped)
                
                # Keep log size manageable
                if len(self.logs) > 1000:
                    self.logs.pop(0)

                # Attempt to find URL if not yet found
                # CRITICAL: Strip ANSI escape codes first - Vite outputs colored text!
                # Without this, the pattern sees \x1b[36mhttp://localhost:5177/\x1b[0m
                line_clean = self.strip_ansi(line_stripped)
                
                if not self.current_url and ("localhost" in line_clean.lower() or "127.0.0.1" in line_clean):
                    match = self._url_pattern.search(line_clean)
                    if match:
                        self.current_url = match.group(0)
                        print(f"[PreviewManager] ✓ Detected URL: {self.current_url}")
                        # Request focus so ships-preview window comes to front
                        self.focus_requested = True
                    else:
                        # Debug: log lines that contain localhost but don't match pattern
                        print(f"[PreviewManager] URL pattern miss (clean): {line_clean[:100]}")
                        
        except Exception as e:
            self.logs.append(f"[System Error] Log consumption failed: {e}")
        finally:
            self.is_running = False
            # Ensure process is marked logs finished if it dies
            if self.process and self.process.poll() is not None:
                self.logs.append("[System] Process exited.")

    def request_focus(self):
        """Set the focus request flag."""
        self.focus_requested = True

    def clear_focus_request(self):
        """Clear the focus request flag."""
        self.focus_requested = False

    def open_system_terminal(self, project_path: str):
        """
        Opens a native system terminal (PowerShell) in the specified project path.
        This allows the user to manually control processes or delete files that might be locked.
        """
        if not os.path.exists(project_path):
            return {"status": "error", "message": f"Project path not found: {project_path}"}
        
        try:
            if os.name == 'nt':
                # 'start' is a shell command in cmd, so we use shell=True.
                # 'powershell -NoExit' keeps the window open.
                subprocess.Popen(
                    f'start powershell -NoExit -Command "cd \'{project_path}\'"', 
                    shell=True
                )
            else:
                # Fallback for non-Windows (though user is on Windows)
                # Try to key common terminals
                subprocess.Popen(["open", "-a", "Terminal", project_path]) # MacOS
                
            return {"status": "success", "message": "Terminal opened"}
        except Exception as e:
            print(f"Failed to open system terminal: {e}")
            return {"status": "error", "message": str(e)}

preview_manager = PreviewManager()
