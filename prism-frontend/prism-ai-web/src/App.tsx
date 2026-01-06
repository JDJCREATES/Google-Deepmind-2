import { useState, useEffect } from 'react';
import { MdLightMode, MdDarkMode } from 'react-icons/md';
import { 
  VscFiles, 
  VscSearch, 
  VscSettingsGear, 
  VscTerminal 
} from 'react-icons/vsc';
import { BiBox } from 'react-icons/bi';

import MonacoEditor from './components/MonacoEditor';
import FileExplorer from './components/FileExplorer';
import EditorTabs from './components/EditorTabs';
import LandingPage from './pages/LandingPage';
import ArtifactPanel from './components/artifacts/ArtifactPanel';
import ArtifactViewer from './components/artifacts/ArtifactViewer';
import Settings from './components/settings/Settings';
import { ChatInterface } from './components/chat/ChatInterface';
import { XTerminal } from './components/terminal/XTerminal';

import { useFileSystem } from './store/fileSystem';
import { useArtifactStore } from './store/artifactStore';
import { useSettingsStore } from './store/settingsStore';
import { useAuthStore } from './store/authStore';
import { useStreamingStore } from './store/streamingStore';
import { useMonacoDiagnostics } from './hooks/useMonacoDiagnostics';

import './App.css';

type SidebarView = 'files' | 'artifacts' | 'search';

function App() {
  const { monaco } = useSettingsStore();
  const [theme, setTheme] = useState<'vs-dark' | 'light'>(monaco.theme);
  const [showExplorer, setShowExplorer] = useState(true);
  const [activeSidebarView, setActiveSidebarView] = useState<SidebarView>('files');
  const [showSettings, setShowSettings] = useState(false);
  const { currentProjectId } = useArtifactStore();
  const { rootHandle } = useFileSystem();
  
  // Terminal state from store
  const { 
    terminalOutput, 
    showTerminal, 
    setShowTerminal 
  } = useStreamingStore();

  const [terminalCollapsed, setTerminalCollapsed] = useState(false);
  
  // Project path handling
  const [electronProjectPath, setElectronProjectPath] = useState<string | null>(null);
  const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001';
  
  // Monaco Diagnostics
  useMonacoDiagnostics({
    projectPath: electronProjectPath || undefined,
    apiUrl: API_URL,
    enabled: !!electronProjectPath, 
  });
  
  const PROJECT_PATH_KEY = 'ships_project_path';
  
  // Sync project path with backend
  const syncProjectPathWithBackend = async (path: string) => {
    try {
      await fetch(`${API_URL}/preview/set-path`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path })
      });
      console.log('[App] Synced project path with backend:', path);
      localStorage.setItem(PROJECT_PATH_KEY, path);
    } catch (error) {
      console.warn('[App] Failed to sync project path with backend:', error);
    }
  };
  
  const getProjectPath = async (): Promise<string | null> => {
    // 1. Electron
    if (window.electron?.getLastProject) {
      try {
        const result = await window.electron.getLastProject();
        if (result.path) return result.path;
      } catch (e) {
        console.warn('[App] Electron connection unavailable');
      }
    }
    
    // 2. LocalStorage
    const savedPath = localStorage.getItem(PROJECT_PATH_KEY);
    if (savedPath) return savedPath;
    
    // 3. Backend
    try {
      const response = await fetch(`${API_URL}/preview/path`);
      const data = await response.json();
      if (data.project_path) return data.project_path;
    } catch (e) {
      console.warn('[App] Failed to fetch project path from backend');
    }
    
    return null;
  };
  
  useEffect(() => {
    const fetchAndSync = async () => {
      const path = await getProjectPath();
      if (path) {
        setElectronProjectPath(path);
        await syncProjectPathWithBackend(path);
      }
    };
    fetchAndSync();
    
    const { checkSession } = useAuthStore.getState();
    checkSession();
    
    // Periodic re-sync
    const syncInterval = setInterval(async () => {
      const path = await getProjectPath();
      if (path) {
        await syncProjectPathWithBackend(path);
      }
    }, 30000);
    
    return () => clearInterval(syncInterval);
  }, []);

  // Theme Sync
  useEffect(() => {
    setTheme(monaco.theme);
  }, [monaco.theme]);

  const toggleTheme = () => {
    const newTheme = theme === 'vs-dark' ? 'light' : 'vs-dark';
    setTheme(newTheme);
    useSettingsStore.getState().updateMonacoSettings({ theme: newTheme });
  };
  
  const handleSidebarClick = (view: SidebarView) => {
    if (activeSidebarView === view) {
      setShowExplorer(!showExplorer);
    } else {
      setActiveSidebarView(view);
      setShowExplorer(true);
    }
  };

  const handleKillBackendProcess = async () => {
    try {
      if (confirm('Are you sure you want to kill the backend process (e.g. dev server)?')) {
        const response = await fetch(`${API_URL}/preview/stop`, { method: 'POST' });
        // Output handled usually by appending to terminal via chat, but here we might lack the setter
        // Ideally XTerminal or Store should handle this logging, but for now console log is fine
        // or we could use useStreamingStore().appendTerminalOutput if we wanted.
        if (response.ok) console.log('Backend killed');
      }
    } catch (e) {
      console.error("Failed to kill backend process", e);
    }
  };

  if (!rootHandle) {
    return <LandingPage />;
  }

  return (
    <div className={`app-container ${theme}`}>
      {/* LEFT PANEL SYSTEM (Explorer + Editor) - 60% */}
      <div className="main-editor-area">
        
        <div className="activity-bar">
           <div className="activity-top">
             <div 
               className={`activity-icon ${activeSidebarView === 'files' && showExplorer ? 'active' : ''}`} 
               onClick={() => handleSidebarClick('files')}
               title="File Explorer"
             >
               <VscFiles size={24} />
             </div>
             <div 
               className={`activity-icon ${activeSidebarView === 'artifacts' && showExplorer ? 'active' : ''}`} 
               onClick={() => handleSidebarClick('artifacts')}
               title="Artifacts"
             >
               <BiBox size={24} />
             </div>
             <div 
               className={`activity-icon ${activeSidebarView === 'search' && showExplorer ? 'active' : ''}`} 
               onClick={() => handleSidebarClick('search')}
               title="Search"
             >
               <VscSearch size={24} />
             </div>
           </div>
           <div className="activity-bottom">
             <div 
               className={`activity-icon ${showTerminal ? 'active' : ''}`} 
               onClick={() => setShowTerminal(!showTerminal)}
               title="Terminal"
             >
               <VscTerminal size={24} />
             </div>
             <div className="activity-icon" onClick={toggleTheme} title="Toggle Theme">
               {theme === 'vs-dark' ? <MdLightMode size={24} /> : <MdDarkMode size={24} />}
             </div>
             <div className="activity-icon" onClick={() => setShowSettings(true)} title="Settings">
               <VscSettingsGear size={24} />
             </div>
           </div>
        </div>

        {showExplorer && (
          <div className="sidebar-pane">
            <div className="sidebar-content">
              {activeSidebarView === 'files' && <FileExplorer />}
              {activeSidebarView === 'artifacts' && <ArtifactPanel projectId={currentProjectId || ''} />}
              {activeSidebarView === 'search' && <div className="p-4 text-center text-gray-500">Search not implemented</div>}
            </div>
          </div>
        )}

        <div className="editor-pane">
          {activeSidebarView === 'artifacts' ? (
            <ArtifactViewer />
          ) : (
            <>
              <div className="editor-tabs-container">
                <EditorTabs />
              </div>
              <div className="monaco-container">
                <MonacoEditor theme={theme} />
              </div>
              <XTerminal
                projectPath={electronProjectPath}
                isVisible={showTerminal}
                isCollapsed={terminalCollapsed}
                onClose={() => setShowTerminal(false)}
                onToggleCollapse={() => setTerminalCollapsed(!terminalCollapsed)}
                externalOutput={terminalOutput}
                onKillBackendProcess={handleKillBackendProcess}
              />
            </>
          )}
        </div>

      </div>

      {/* RIGHT PANEL (Chat Interface) - 40% */}
      <ChatInterface electronProjectPath={electronProjectPath} />

      {showSettings && (
        <div className="fullscreen-modal" style={{ 
          position: 'fixed', 
          top: 0, 
          left: 0, 
          right: 0, 
          bottom: 0, 
          display: 'flex', 
          justifyContent: 'center', 
          alignItems: 'center',
          backgroundColor: 'rgba(0,0,0,0.5)',
          zIndex: 9999
        }}>
          <div className="modal-content" style={{
            width: '80%',
            height: '80%',
            backgroundColor: 'var(--bg-primary, #1e1e1e)',
            borderRadius: '8px',
            overflow: 'hidden',
            boxShadow: '0 4px 20px rgba(0,0,0,0.5)',
            position: 'relative'
          }}>
             <Settings onClose={() => setShowSettings(false)} />
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
