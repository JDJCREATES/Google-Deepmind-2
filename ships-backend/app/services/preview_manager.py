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

    def __init__(self):
        self.process: Optional[subprocess.Popen] = None
        self.logs: List[str] = []
        self.current_url: Optional[str] = None
        self.is_running: bool = False
        self.current_project_path: Optional[str] = None  # Track the current project path
        self._url_pattern = re.compile(r'http://localhost:\d+')

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
            # Determine command based on OS
            cmd = ["npm.cmd", "run", "dev"] if os.name == 'nt' else ["npm", "run", "dev"]
            
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

        Returns:
            Dict[str, str]: Status of the stop operation.
        """
        if self.process:
            try:
                # terminate() is usually sufficient for dev servers
                self.process.terminate()
                # On Windows, we might need taskkill if node spawns children
                if os.name == 'nt':
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(self.process.pid)],
                        stdout=subprocess.DEVNULL, 
                        stderr=subprocess.DEVNULL
                    )
            except Exception as e:
                print(f"Error stopping process: {e}")
            finally:
                self.process = None
                self.is_running = False
                self.current_url = None

            return {"status": "stopped"}
        
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
                if not self.current_url and "localhost:" in line_stripped:
                    match = self._url_pattern.search(line_stripped)
                    if match:
                        self.current_url = match.group(0)
                        
        except Exception as e:
            self.logs.append(f"[System Error] Log consumption failed: {e}")
        finally:
            self.is_running = False
            # Ensure process is marked logs finished if it dies
            if self.process and self.process.poll() is not None:
                self.logs.append("[System] Process exited.")

preview_manager = PreviewManager()
