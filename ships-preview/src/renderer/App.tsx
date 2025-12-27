import { useState, useEffect } from 'react';
import { PiFolderOpenBold } from "react-icons/pi";
import { RiShip2Fill } from "react-icons/ri";

// Add types for exposed Electron API
declare global {
  interface Window {
    electron: {
      selectProjectFolder: () => Promise<{ success: boolean; path: string | null; error?: string }>;
      getLastProject: () => Promise<{ path: string | null; exists: boolean }>;
      clearProject: () => Promise<void>;
      runBuild: (path: string) => Promise<void>;
    }
  }
}

function App() {
  const [projectUrl, setProjectUrl] = useState<string | null>(null);
  const [isConnecting, setIsConnecting] = useState(false);
  const [currentPath, setCurrentPath] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string>('');

  // 1. On Mount: Check for last project
  useEffect(() => {
    const initProject = async () => {
      try {
        const result = await window.electron.getLastProject();
        if (result.exists && result.path) {
          console.log("Restoring last project:", result.path);
          await setBackendPath(result.path);
        }
      } catch (e) {
        console.error("Failed to restore project:", e);
      }
    };
    initProject();
  }, []);

  // Helper: Set path on backend
  const setBackendPath = async (path: string) => {
    try {
      setStatusMessage(`Setting project: ${path}`);
      const res = await fetch('http://localhost:8001/preview/set-path', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path })
      });
      const data = await res.json();
      
      if (data.status === 'success') {
        setCurrentPath(path);
        setStatusMessage('Project linked. Waiting for preview...');
        setIsConnecting(true); // Start polling
      } else {
        setStatusMessage(`Error: ${data.message}`);
      }
    } catch (e) {
      console.error("Backend error:", e);
      setStatusMessage('Error: Could not connect to backend API');
    }
  };

  // 2. Poll Backend for Preview Status
  useEffect(() => {
    if (!isConnecting && !projectUrl) return;

    const checkStatus = async () => {
        try {
            const res = await fetch('http://localhost:8001/preview/status');
            const data = await res.json();
            
            // Should also check if data.project_path matches currentPath if we wanted to be strict
            if (data.is_running && data.url) {
                setProjectUrl(data.url);
                setIsConnecting(false);
                setStatusMessage('');
            }
        } catch (e) {
            // Backend might be down or not started
            console.log("Polling error:", e);
        }
    };

    const interval = setInterval(checkStatus, 2000);
    return () => clearInterval(interval);
  }, [isConnecting, projectUrl]);


  // 3. User selects folder
  const handleSelectProject = async () => {
      try {
          // Check if electron is available
          if (!window.electron) {
              alert("Error: Electron API not available. Preload script might have failed.");
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
            {currentPath ? `Current Project: ${currentPath}` : 'Select a project to start preview'}
        </p>

        {statusMessage && (
            <div style={{ 
                marginBottom: 20, 
                padding: '8px 12px', 
                borderRadius: 4, 
                background: 'rgba(255, 255, 255, 0.1)', 
                fontSize: '13px',
                color: '#aaa'
            }}>
                {statusMessage}
            </div>
        )}

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
                margin: '0 auto',
                transition: 'transform 0.2s, box-shadow 0.2s',
                opacity: isConnecting ? 0.8 : 1,
                boxShadow: '0 4px 12px rgba(255, 94, 87, 0.3)'
            }}
            onMouseOver={(e) => e.currentTarget.style.transform = 'translateY(-2px)'}
            onMouseOut={(e) => e.currentTarget.style.transform = 'translateY(0)'}
        >
            <PiFolderOpenBold size={20} />
            {currentPath ? 'Change Project' : 'Open Project Folder'}
        </button>
      </div>
    </div>
  );
}

export default App;


