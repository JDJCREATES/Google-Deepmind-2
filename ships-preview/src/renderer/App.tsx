import { useState, useEffect, useRef } from 'react';
import { PiFolderOpenBold } from "react-icons/pi";
import { RiShip2Fill } from "react-icons/ri";
import { VscRefresh } from "react-icons/vsc";

// Add types for exposed Electron API
declare global {
  interface Window {
    electron: {
      selectProjectFolder: () => Promise<{ success: boolean; path: string | null; error?: string }>;
      getLastProject: () => Promise<{ path: string | null; exists: boolean }>;
      clearProject: () => Promise<void>;
      runBuild: (path: string) => Promise<void>;
      focusWindow: () => Promise<boolean>;
    }
  }
}

function App() {
  const [projectUrl, setProjectUrl] = useState<string | null>(null);
  const [isConnecting, setIsConnecting] = useState(false);
  const [currentPath, setCurrentPath] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string>('');
  const [error, setError] = useState<string | null>(null);
  const [backendConnected, setBackendConnected] = useState(false);
  const connectionTimeoutRef = useRef<number | null>(null);

  // 1. On Mount: Check for last project and try to reconnect
  useEffect(() => {
    const initProject = async () => {
      try {
        const result = await window.electron.getLastProject();
        if (result.exists && result.path) {
          console.log("Restoring last project:", result.path);
          setCurrentPath(result.path);
          await setBackendPath(result.path);
        }
      } catch (e) {
        console.error("Failed to restore project:", e);
      }
    };
    initProject();
    
    // Listen for preview URL from ships:// protocol (triggered by web app)
    if ((window.electron as any)?.onOpenPreviewUrl) {
      const cleanup = (window.electron as any).onOpenPreviewUrl((url: string) => {
        console.log("[Preview] Received URL from protocol:", url);
        setProjectUrl(url);
        setIsConnecting(false);
        setStatusMessage('');
      });
      return cleanup;
    }
  }, []);

  // Helper: Set path on backend with timeout
  const setBackendPath = async (path: string) => {
    try {
      setStatusMessage(`Connecting to backend...`);
      setIsConnecting(true);
      
      // Set a timeout - don't wait forever
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 5000);
      
      const res = await fetch('http://localhost:8001/preview/set-path', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path }),
        signal: controller.signal
      });
      clearTimeout(timeout);
      
      const data = await res.json();
      
      if (data.status === 'success') {
        setCurrentPath(path);
        setBackendConnected(true);
        setIsConnecting(false);  // Re-enable button immediately
        setStatusMessage('✓ Project linked to backend');
        
        // Start polling for preview URL
        startPreviewPolling();
      } else {
        setStatusMessage(`Error: ${data.message}`);
        setIsConnecting(false);
      }
    } catch (e: any) {
      console.error("Backend error:", e);
      if (e.name === 'AbortError') {
        setStatusMessage('⚠ Backend not responding. Is it running?');
      } else {
        setStatusMessage('⚠ Could not connect to backend');
      }
      setBackendConnected(false);
      setIsConnecting(false);
    }
  };

  // Poll for preview URL
  const startPreviewPolling = () => {
    // Clear any existing timeout
    if (connectionTimeoutRef.current) {
      clearTimeout(connectionTimeoutRef.current);
    }
    
    // Set a 30-second timeout for polling
    connectionTimeoutRef.current = window.setTimeout(() => {
      if (isConnecting && !projectUrl) {
        setStatusMessage('⚠ Preview server not starting. You can still code!');
        setIsConnecting(false);
      }
    }, 30000);
  };

  // 2. Poll Backend for Preview Status - ALWAYS poll, not just when backendConnected
  // This allows picking up previews started by prism-ai-web
  useEffect(() => {
    // Helper to probe if a URL is reachable - improved version
    const probeUrl = async (url: string): Promise<boolean> => {
      try {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 2000);
        
        // Use regular fetch - will throw on connection refused
        // Note: CORS may block the response, but connection success means server is running
        const response = await fetch(url, { 
          method: 'HEAD',  // Just check if server responds
          signal: controller.signal 
        });
        clearTimeout(timeout);
        console.log(`[Preview] Probe ${url}: OK (${response.status})`);
        return true;
      } catch (e: any) {
        // Distinguish between CORS error (server running) vs connection refused (not running)
        // CORS errors mean the server IS running but denying our request
        if (e.name === 'TypeError' && e.message?.includes('CORS')) {
          console.log(`[Preview] Probe ${url}: CORS error (server is running)`);
          return true;
        }
        // AbortError means timeout - server probably not running
        if (e.name === 'AbortError') {
          console.log(`[Preview] Probe ${url}: Timeout`);
          return false;
        }
        console.log(`[Preview] Probe ${url}: Failed - ${e.message || e}`);
        return false;
      }
    };

    // Try common dev server ports
    const tryCommonPorts = async () => {
      const ports = ['5177', '5173', '3000', '3001', '8080'];
      console.log('[Preview] Auto-detecting dev server on ports:', ports);
      
      for (const port of ports) {
        const url = `http://localhost:${port}`;
        if (await probeUrl(url)) {
          console.log(`[Preview] ✓ Auto-detected dev server at ${url}`);
          setProjectUrl(url);
          setIsConnecting(false);
          setStatusMessage(`✓ Auto-detected: ${url}`);
          return true;
        }
      }
      console.log('[Preview] No dev server found on common ports');
      return false;
    };

    const checkStatus = async () => {
        try {
            const res = await fetch('http://localhost:8001/preview/status');
            const data = await res.json();
            console.log('[Preview] Backend status:', { 
              is_running: data.is_running, 
              url: data.url, 
              project_path: data.project_path,
              error: data.error 
            });
            
            // Set error if present
            if (data.error) {
                setError(data.error);
                setIsConnecting(false);
            } else {
                setError(null);
            }
            
            if (data.is_running && data.url) {
                console.log('[Preview] ✓ Backend has running server at:', data.url, 'Setting projectUrl...');
                setProjectUrl(data.url);
                setIsConnecting(false);
                setStatusMessage('');
                if (connectionTimeoutRef.current) {
                  clearTimeout(connectionTimeoutRef.current);
                }
                
                // Sync project path if backend has one but we don't
                if (data.project_path && !currentPath) {
                  setCurrentPath(data.project_path);
                  setBackendConnected(true);
                }
            } else if (!projectUrl) {
                // Backend doesn't have a running server - try to auto-detect
                console.log('[Preview] Backend has no server, trying auto-detect...');
                await tryCommonPorts();
            }

            // Check for focus request (Reverse Focus)
            if (data.focus_requested) {
                console.log("Backend requested focus!");
                if (window.electron && window.electron.focusWindow) {
                    await window.electron.focusWindow();
                    // Acknowledge to clear the flag
                    await fetch('http://localhost:8001/preview/ack-focus', { method: 'POST' });
                }
            }
        } catch (e) {
            console.log('[Preview] Backend not reachable, trying auto-detect...');
            // Backend not running - try to auto-detect dev servers directly
            if (!projectUrl) {
                await tryCommonPorts();
            }
        }
    };
    
    // Poll immediately on mount
    checkStatus();
    
    const interval = setInterval(checkStatus, 2000);
    return () => clearInterval(interval);
  }, [currentPath, projectUrl]); // Re-run if currentPath or projectUrl changes

  // 3. User selects folder
  const handleSelectProject = async () => {
      try {
          if (!window.electron) {
              alert("Error: Electron API not available.");
              return;
          }

          const result = await window.electron.selectProjectFolder();
          if (result.success && result.path) {
              await setBackendPath(result.path);
          } else if (result.error) {
              alert("Selection Error: " + result.error);
          }
      } catch (e: any) {
          console.error("Selection error:", e);
          alert("Failed to select project: " + e.message);
      }
  };

  // 4. Reconnect to backend with stored path
  const handleReconnect = async () => {
    if (currentPath) {
      await setBackendPath(currentPath);
    }
  };

  // 5. Auto-discover project from backend (if local is empty)
  useEffect(() => {
    if (backendConnected || currentPath) return; // Don't override if user selected something

    const checkForbackendPath = async () => {
       try {
          const res = await fetch('http://localhost:8001/preview/path');
          const data = await res.json();
          if (data.is_set && data.project_path) {
              console.log("Auto-discovered project from backend:", data.project_path);
              // Use setBackendPath to connect and store it
              await setBackendPath(data.project_path);
          }
       } catch (e) {
          // Backend might be down, ignore
       }
    };
    
    // Check every 5 seconds
    const interval = setInterval(checkForbackendPath, 5000);
    checkForbackendPath(); // Immediate check
    return () => clearInterval(interval);
  }, [backendConnected, currentPath]);

  if (error) {
      return (
        <div style={{
          width: '100vw', height: '100vh', display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center', backgroundColor: '#1e1e1e', color: '#ff6b6b'
        }}>
           <div style={{ fontSize: '48px', marginBottom: '20px' }}>❌</div>
           <h2 style={{ margin: 0 }}>Preview Error</h2>
           <p style={{ maxWidth: '80%', textAlign: 'center', marginTop: '10px', color: '#e0e0e0' }}>{error}</p>
           <button 
             onClick={() => window.location.reload()}
             style={{ marginTop: '20px', padding: '10px 20px', cursor: 'pointer', background: '#333', color: '#fff', border: 'none', borderRadius: '4px' }}
           >
             Retry
           </button>
        </div>
      );
  }

  if (projectUrl) {
      return (
          <div style={{ width: '100vw', height: '100vh', display: 'flex', flexDirection: 'column' }}>
             <webview 
                src={projectUrl} 
                style={{ width: '100%', height: '100%', border: 'none' }}
                // @ts-ignore
                allowpopups="true"
             />
          </div>
      )
  }

  return (
    <div className="landing-container" style={{ 
        height: '100vh', 
        display: 'flex', 
        flexDirection: 'column', 
        alignItems: 'center', 
        justifyContent: 'center', 
        backgroundColor: '#1E1E1E', 
        color: '#fff',
        fontFamily: 'Inter, system-ui, sans-serif'
    }}>
      {/* Draggable Area */}
      <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 40, WebkitAppRegion: 'drag' } as any} />

      <div className="brand-content" style={{ textAlign: 'center', animation: 'fadeIn 0.5s ease', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 10 }}>
            <RiShip2Fill 
                size={48} 
                color="#FF5E57" 
                style={{ filter: 'drop-shadow(0 0 20px rgba(255, 94, 87, 0.3))' }} 
            />
            <h1 style={{ 
                fontSize: '48px', 
                fontWeight: 800, 
                margin: 0, 
                background: 'linear-gradient(to right, #fff, #aaa)', 
                WebkitBackgroundClip: 'text', 
                WebkitTextFillColor: 'transparent',
                lineHeight: 1
            }}>
                ShipS*
            </h1>
        </div>
        <p style={{ color: '#888', fontSize: '16px', marginTop: 0, marginBottom: 30 }}>
            {currentPath ? `📂 ${currentPath}` : 'Select a project to start preview'}
        </p>

        {statusMessage && (
            <div style={{ 
                marginBottom: 20, 
                padding: '8px 12px', 
                borderRadius: 4, 
                background: statusMessage.includes('⚠') ? 'rgba(255, 94, 87, 0.2)' : 'rgba(255, 255, 255, 0.1)', 
                fontSize: '13px',
                color: statusMessage.includes('⚠') ? '#ff9999' : '#aaa'
            }}>
                {statusMessage}
            </div>
        )}

        <div style={{ display: 'flex', gap: 10 }}>
          <button 
              onClick={handleSelectProject}
              disabled={isConnecting}
              style={{
                  backgroundColor: '#FF5E57',
                  color: 'white',
                  border: 'none',
                  padding: '12px 24px',
                  borderRadius: '8px',
                  fontSize: '16px',
                  fontWeight: 600,
                  cursor: isConnecting ? 'wait' : 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  transition: 'transform 0.2s, box-shadow 0.2s',
                  opacity: isConnecting ? 0.8 : 1,
                  boxShadow: '0 4px 12px rgba(255, 94, 87, 0.3)'
              }}
          >
              <PiFolderOpenBold size={20} />
              {currentPath ? 'Change Project' : 'Open Project Folder'}
          </button>
          
          {/* Reconnect button - shown when we have a path but backend disconnected */}
          {currentPath && !backendConnected && !isConnecting && (
            <button 
                onClick={handleReconnect}
                style={{
                    backgroundColor: 'transparent',
                    color: '#FF5E57',
                    border: '2px solid #FF5E57',
                    padding: '12px 16px',
                    borderRadius: '8px',
                    fontSize: '16px',
                    fontWeight: 600,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    transition: 'all 0.2s',
                }}
            >
                <VscRefresh size={18} />
                Reconnect
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export default App;
