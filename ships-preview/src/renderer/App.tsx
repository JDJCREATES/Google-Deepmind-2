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
      openExternal: (url: string) => Promise<void>;
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
        setIsConnecting(false); 
        setStatusMessage('✓ Project linked to backend');
        startPreviewPolling();
      } else {
        setStatusMessage(`Error: ${data.message}`);
        setIsConnecting(false);
      }
    } catch (e: any) {
      console.error("Backend error:", e);
      setStatusMessage(e.name === 'AbortError' ? '⚠ Backend not responding. Is it running?' : '⚠ Could not connect to backend');
      setBackendConnected(false);
      setIsConnecting(false);
    }
  };

  const startPreviewPolling = () => {
    if (connectionTimeoutRef.current) clearTimeout(connectionTimeoutRef.current);
    connectionTimeoutRef.current = window.setTimeout(() => {
      if (isConnecting && !projectUrl) {
        setStatusMessage('⚠ Preview server not starting. You can still code!');
        setIsConnecting(false);
      }
    }, 30000);
  };

  // Helper to probe if a URL is reachable
  const probeUrl = async (url: string): Promise<boolean> => {
    try {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 2000);
      
      const response = await fetch(url, { 
        method: 'HEAD',
        signal: controller.signal 
      });
      clearTimeout(timeout);
      console.log(`[Preview] Probe ${url}: OK (${response.status})`);
      return true;
    } catch (e: any) {
      if (e.name === 'TypeError' && e.message?.includes('CORS')) {
        console.log(`[Preview] Probe ${url}: CORS error (server is running)`);
        return true;
      }
      if (e.name === 'AbortError') {
        return false;
      }
      return false;
    }
  };

  // Try backend ports ONLY (5200-5250) - PARALLEL SCAN
  const tryBackendPorts = async () => {
    const currentPort = window.location.port;
    const backendPorts = Array.from({length: 51}, (_, i) => String(5200 + i)); 
    const ports = backendPorts.filter(p => p !== currentPort);
    
    console.log(`[Preview] Scanning ShipS backend ports (${ports.length}) in parallel...`);
    setStatusMessage(`Scanning ${ports.length} ports (5200-5250)...`);

    // Scan in chunks of 10 to avoid flooding but speed up checks
    const chunkSize = 10;
    for (let i = 0; i < ports.length; i += chunkSize) {
        const chunk = ports.slice(i, i + chunkSize);
        
        // Create checking promises
        const promises = chunk.map(async (port) => {
            const url = `http://localhost:${port}`;
            // Skip self and forbidden
            if (url === window.location.origin) return null;
            
            const alive = await probeUrl(url);
            return alive ? url : null;
        });

        // Wait for this chunk
        const results = await Promise.all(promises);
        const foundUrl = results.find(url => url !== null);
        
        if (foundUrl) {
            console.log(`[Preview] ✓ Auto-detected dev server at ${foundUrl}`);
            setProjectUrl(foundUrl);
            setIsConnecting(false);
            setStatusMessage(`✓ Auto-detected: ${foundUrl}`);
            return true;
        }
    }
    
    return false;
  };

  // 2. Poll Backend for Preview Status
  useEffect(() => {
    const checkStatus = async () => {
        try {
            const res = await fetch('http://localhost:8001/preview/status');
            const data = await res.json();
            
            // Set error if present
            if (data.error) setError(data.error);

            if (data.is_running && data.url) {
                if (projectUrl !== data.url) {
                   console.log('[Preview] ✓ Backend has running server at:', data.url);
                   setProjectUrl(data.url);
                   setStatusMessage('');
                   setBackendConnected(true);
                }
                setIsConnecting(false);
            } else if (!projectUrl && !isConnecting) {
                // If backend says nothing running and we aren't scanning/connecting, show idle
                setStatusMessage('');
            }

            // Check for focus request
            if (data.focus_requested) {
                if (window.electron?.focusWindow) {
                    await window.electron.focusWindow();
                    await fetch('http://localhost:8001/preview/ack-focus', { method: 'POST' });
                }
            }
        } catch (e) {
            // Backend down - say nothing, let manual scan handle it
        }
    };
    
    checkStatus();
    const interval = setInterval(checkStatus, 2000);
    return () => clearInterval(interval);
  }, [projectUrl, isConnecting]); // Removed currentPath dependency to prevent loops

  // Manual Scan Trigger
  const handleManualScan = async () => {
    if (isConnecting) return;
    setIsConnecting(true);
    setError(null);
    
    // 1. Try backend list first (fastest source of truth)
    try {
        setStatusMessage("Checking backend...");
        const res = await fetch('http://localhost:8001/preview/status');
        const data = await res.json();
        if (data.is_running && data.url) {
            setProjectUrl(data.url);
            setIsConnecting(false);
            return;
        }
    } catch(e) {}

    // 2. Fallback to physical port scan
    const found = await tryBackendPorts();
    if (!found) {
        setStatusMessage("No running servers found.");
        setIsConnecting(false);
    }
  };

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

  // Ref for the webview to validly modify it
  const webviewRef = useRef<any>(null);

  // Auto-reload webview when backend re-confirms (even if URL is same)
  useEffect(() => {
    if (webviewRef.current && projectUrl && backendConnected) {
       try {
         // If we are connected and URL is set, ensure we are not on an error page
         // We can force a reload to be safe if the backend just came back up
         console.log("Backend confirmed - reloading webview to ensure freshness");
         webviewRef.current.reload(); 
       } catch (e) {
         // Webview might not be ready
       }
    }
  }, [backendConnected]); // Trigger when backend connection status flips to true

  // Add event listeners to webview (Moved to top level)
  useEffect(() => {
    const webview = webviewRef.current;
    if (webview && projectUrl) {
        const handleFailLoad = (e: any) => {
            console.log('Webview failed to load:', e);
            setStatusMessage(`⚠ Preview failed to load: ${e.errorDescription || 'Unknown error'}`);
        };
        
        webview.addEventListener('did-fail-load', handleFailLoad);
        
        return () => {
            webview.removeEventListener('did-fail-load', handleFailLoad);
        };
    }
  }, [projectUrl, backendConnected]); // Re-bind if URL changes or backend reconnects

  if (projectUrl) {
      return (
          <div style={{ width: '100vw', height: '100vh', display: 'flex', flexDirection: 'column' }}>
             {/* Show URL bar for debugging */}
             <div style={{ 
                height: '32px', 
                backgroundColor: '#2d2d2d', 
                color: '#aaa', 
                display: 'flex', 
                alignItems: 'center', 
                padding: '0 12px', 
                fontSize: '12px',
                borderBottom: '1px solid #444'
             }}>
                <span style={{ marginRight: '8px' }}>📡</span>
                {projectUrl}
                <div style={{ marginLeft: 'auto', display: 'flex', gap: '8px' }}>
                    <button 
                      onClick={() => {
                        if (webviewRef.current) {
                            webviewRef.current.reload();
                        }
                      }}
                      style={{
                        background: 'transparent',
                        border: '1px solid #555',
                        color: '#aaa',
                        padding: '4px 8px',
                        borderRadius: '4px',
                        cursor: 'pointer',
                        fontSize: '11px',
                        display: 'flex', 
                        alignItems: 'center',
                        gap: '4px'
                      }}
                    >
                      <VscRefresh /> Reload
                    </button>
                    <button 
                      onClick={async () => {
                        // Open in external browser for debugging
                        if (window.electron?.openExternal) {
                          await window.electron.openExternal(projectUrl);
                        }
                      }}
                      style={{
                        background: 'transparent',
                        border: '1px solid #555',
                        color: '#aaa',
                        padding: '4px 8px',
                        borderRadius: '4px',
                        cursor: 'pointer',
                        fontSize: '11px'
                      }}
                    >
                      Open in Browser
                    </button>
                </div>
             </div>
             <webview 
                ref={webviewRef}
                src={projectUrl} 
                style={{ width: '100%', flex: 1, border: 'none' }}
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

          {/* Manual Scan Button */}
          {!isConnecting && !projectUrl && (
             <button
                onClick={handleManualScan}
                style={{
                    backgroundColor: 'rgba(255, 255, 255, 0.1)',
                    color: '#aaa',
                    border: '1px solid #444',
                    padding: '12px 16px',
                    borderRadius: '8px',
                    fontSize: '14px',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    transition: 'all 0.2s',
                }}
             >
                <VscRefresh size={16} />
                Scan for Servers
             </button>
          )}

        </div>
      </div>
    </div>
  );
}

export default App;
