import { useState, useRef, useEffect } from 'react';
import * as Ons from 'react-onsenui';
import ChatMessage, { type Message } from './components/ChatMessage';
import MonacoEditor from './components/MonacoEditor';
import FileExplorer from './components/FileExplorer';
import EditorTabs from './components/EditorTabs';
import LandingPage from './pages/LandingPage';
import ArtifactPanel from './components/artifacts/ArtifactPanel';
import ArtifactViewer from './components/artifacts/ArtifactViewer';
import Settings from './components/settings/Settings';
import { useFileSystem } from './store/fileSystem';
import { useArtifactStore } from './store/artifactStore';
import { useSettingsStore } from './store/settingsStore';
import { useAuthStore } from './store/authStore';
import { MdLightMode, MdDarkMode } from 'react-icons/md';
import { PiShippingContainerFill } from "react-icons/pi";
import { RiShip2Fill } from 'react-icons/ri';
import { 
  VscFiles, 
  VscSearch, 
  VscSettingsGear, 
  VscLayoutSidebarRightOff,
  VscTerminal 
} from 'react-icons/vsc';
import { XTerminal } from './components/terminal/XTerminal';
import { BiBox } from 'react-icons/bi';
import { agentService, type AgentChunk } from './services/agentService';
import { ToolProgress, type ToolEvent, PhaseIndicator, type AgentPhase } from './components/streaming';
import { ActivityIndicator } from './components/streaming/ActivityIndicator';
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
  const { refreshFileTree } = useFileSystem();
  
  // Define API URL for component usage
  const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001';
  
  // Toggle sidebar or switch view
  const handleSidebarClick = (view: SidebarView) => {
    if (activeSidebarView === view) {
      // Toggle visibility if clicking same icon
      setShowExplorer(!showExplorer);
    } else {
      // Switch view and ensure visible
      setActiveSidebarView(view);
      setShowExplorer(true);
    }
  };

  const [isAgentRunning, setIsAgentRunning] = useState(false);
  
  // Terminal state
  const [showTerminal, setShowTerminal] = useState(false);
  const [terminalCollapsed, setTerminalCollapsed] = useState(false);
  
  // Streaming state
  const [agentPhase, setAgentPhase] = useState<AgentPhase>('idle');
  const [toolEvents, setToolEvents] = useState<ToolEvent[]>([]);
  const [currentActivity, setCurrentActivity] = useState<string>('');
  const [activityType, setActivityType] = useState<any>('thinking');
  
  // Terminal output from agent commands
  const [terminalOutput, setTerminalOutput] = useState<string>('');
  // Preview URL from completed agent (for auto-launching preview)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  // Preview server status: 'idle' | 'starting' | 'running' | 'error'
  const [previewStatus, setPreviewStatus] = useState<'idle' | 'starting' | 'running' | 'error'>('idle');
  // Get project path from Electron (if available)
  const [electronProjectPath, setElectronProjectPath] = useState<string | null>(null);
  
  // Monaco Diagnostics - reports TypeScript/syntax errors to backend for Fixer
  useMonacoDiagnostics({
    projectPath: electronProjectPath || undefined,
    apiUrl: API_URL,
    enabled: !!electronProjectPath, // Only enable when project is selected
  });
  
  // LocalStorage key for project path backup
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
      // Save to localStorage as backup
      localStorage.setItem(PROJECT_PATH_KEY, path);
    } catch (error) {
      console.warn('[App] Failed to sync project path with backend:', error);
    }
  };
  
  // Get project path from multiple sources with fallback chain
  const getProjectPath = async (): Promise<string | null> => {
    // 1. Try Electron first (most reliable when connected)
    if (window.electron?.getLastProject) {
      try {
        const result = await window.electron.getLastProject();
        if (result.path) {
          return result.path;
        }
      } catch (e) {
        console.warn('[App] Electron connection unavailable');
      }
    }
    
    // 2. Fallback to localStorage backup
    const savedPath = localStorage.getItem(PROJECT_PATH_KEY);
    if (savedPath) {
      console.log('[App] Using cached project path from localStorage:', savedPath);
      return savedPath;
    }
    
    // 3. Try fetching from backend (if backend remembers)
    try {
      const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001';
      const response = await fetch(`${API_URL}/preview/path`);
      const data = await response.json();
      if (data.project_path) {
        console.log('[App] Got project path from backend:', data.project_path);
        return data.project_path;
      }
    } catch (e) {
      console.warn('[App] Failed to fetch project path from backend');
    }
    
    return null;
  };
  
  // Fetch project path from multiple sources on mount and sync with backend
  useEffect(() => {
    const fetchAndSync = async () => {
      const path = await getProjectPath();
      if (path) {
        setElectronProjectPath(path);
        await syncProjectPathWithBackend(path);
      }
    };
    fetchAndSync();
    
    // Check authentication session
    const { checkSession } = useAuthStore.getState();
    checkSession();
    
    // Handle OAuth errors from redirect
    const params = new URLSearchParams(window.location.search);
    const authError = params.get('auth_error');
    const authErrorDescription = params.get('auth_error_description');
    
    if (authError) {
      console.error(`[Auth] OAuth Error: ${authError} - ${authErrorDescription}`);
      setMessages(prev => [...prev, {
        id: Date.now().toString(),
        sender: 'ai' as const,
        content: `⚠ Authentication failed: ${authErrorDescription || 'Unknown error'}`,
        timestamp: new Date(),
      }]);
      
      // Clean URL
      window.history.replaceState({}, document.title, window.location.pathname);
    }
    
    // Periodic re-sync every 30 seconds to handle disconnects/restarts
    const syncInterval = setInterval(async () => {
      const path = await getProjectPath();
      if (path) {
        await syncProjectPathWithBackend(path);
      }
    }, 30000);
    
    return () => clearInterval(syncInterval);
  }, []);

  // Sync with any EXISTING preview server on mount (important for refresh/reconnect)
  useEffect(() => {
    const syncExistingPreview = async () => {
      try {
        const response = await fetch(`${API_URL}/preview/status`);
        const status = await response.json();
        
        if (status.is_running) {
          console.log('[App] Found existing preview server:', status);
          
          // Populate terminal with existing logs
          if (status.logs && status.logs.length > 0) {
            const existingLogs = status.logs.join('\n');
            setTerminalOutput(prev => {
              if (prev.includes('[Previous Session Logs]')) return prev; // Don't double-add
              return `\x1b[36m[Previous Session Logs]\x1b[0m\n${existingLogs}\n${prev}`;
            });
          }
          
          // Set URL if known
          if (status.url) {
            setPreviewUrl(status.url);
            setPreviewStatus('running');
            setTerminalOutput(prev => prev + `\n\x1b[32m[System] ✓ Dev server running at: ${status.url}\x1b[0m\n`);
          } else {
            setPreviewStatus('starting'); // Still waiting for URL
          }
        }
      } catch (e) {
        console.warn('[App] Could not fetch preview status:', e);
      }
    };
    
    syncExistingPreview();
  }, []);

  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      content: 'Ready to Ship?',
      sender: 'ai',
      timestamp: new Date(),
    },
  ]);
  const [inputValue, setInputValue] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  // Sync theme with settings store
  useEffect(() => {
    setTheme(monaco.theme);
  }, [monaco.theme]);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const toggleTheme = () => {
    const newTheme = theme === 'vs-dark' ? 'light' : 'vs-dark';
    setTheme(newTheme);
    useSettingsStore.getState().updateMonacoSettings({ theme: newTheme });
  };

  const handleSendMessage = async () => {
    if (!inputValue.trim()) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      content: inputValue,
      sender: 'user',
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInputValue('');
    setIsAgentRunning(true);
    
    // Reset streaming state for new request
    setAgentPhase('planning');
    setToolEvents([]);
    setCurrentActivity('Initializing...');
    setActivityType('thinking');

    // Create a placeholder AI message
    const aiMessageId = (Date.now() + 1).toString();
    const initialAiMessage: Message = {
      id: aiMessageId,
      content: '', // Start empty, will stream in
      sender: 'ai',
      timestamp: new Date(),
    };
    
    setMessages(prev => [...prev, initialAiMessage]);

    // Track files created for explorer refresh
    let filesCreated = false;

    // Project path is handled securely on the backend via preview_manager
    await agentService.runAgent(
      userMessage.content,
      null, // Backend uses preview_manager.current_project_path as fallback
      (chunk: AgentChunk) => {
        // Handle phase changes
        if (chunk.type === 'phase' && chunk.phase) {
          setAgentPhase(chunk.phase);
          if (chunk.phase === 'planning') setCurrentActivity('Planning approach...');
          else if (chunk.phase === 'coding') setCurrentActivity('Writing code...');
          else if (chunk.phase === 'validating') setCurrentActivity('Verifying changes...');
          else if (chunk.phase === 'fixing') setCurrentActivity('Fixing issues...');
        }
        
        // Handle tool start (show spinner)
        else if (chunk.type === 'tool_start') {
          const toolName = chunk.tool || 'unknown';
          let activityText = `Running ${toolName}...`;
          let type: any = 'working';
          
          if (toolName === 'write_file_to_disk') {
             activityText = `Writing ${chunk.file || 'file'}...`;
             type = 'writing';
          } else if (toolName === 'run_terminal_command') {
             activityText = `Running command...`;
             type = 'command';
          } else if (toolName === 'read_file_from_disk') {
             activityText = `Reading ${chunk.file || 'file'}...`;
             type = 'reading';
          }
          
          setCurrentActivity(activityText);
          setActivityType(type);

          setToolEvents(prev => [...prev, {
            id: `${Date.now()}-${chunk.tool}`,
            type: 'tool_start',
            tool: chunk.tool || 'unknown',
            file: chunk.file,
            timestamp: Date.now()
          }]);
        }
        
        // Handle tool result (show checkmark/X)
        else if (chunk.type === 'tool_result') {
          // Reset activity to generic thinking after tool is done
          setCurrentActivity('Thinking...');
          setActivityType('thinking');

          setToolEvents(prev => [...prev, {
            id: `${Date.now()}-${chunk.tool}-result`,
            type: 'tool_result',
            tool: chunk.tool || 'unknown',
            file: chunk.file,
            success: chunk.success,
            timestamp: Date.now()
          }]);
          
          // Track if files were created for refresh
          if (chunk.tool === 'write_file_to_disk' || chunk.tool === 'edit_file_content') {
            filesCreated = true;
          }
          
          // Auto-show terminal when agent runs commands
          if (chunk.tool === 'run_terminal_command') {
            setShowTerminal(true);
          }
        }
        
        // Handle files created event (explorer refresh)
        else if (chunk.type === 'files_created') {
          filesCreated = true;
        }
        
        // Handle plan created event (display nicely instead of JSON dump)
        else if (chunk.type === 'plan_created') {
          const summary = (chunk as any).summary || 'Plan created';
          const taskCount = (chunk as any).task_count || 0;
          const folderCount = (chunk as any).folders || 0;
          
          setMessages(prev => prev.map(msg => {
            if (msg.id === aiMessageId) {
              const planText = `📋 **Plan Created:** ${summary}\n• ${taskCount} tasks defined\n• ${folderCount} folders structured`;
              return { 
                ...msg, 
                content: msg.content + (msg.content ? '\n\n' : '') + planText
              };
            }
            return msg;
          }));
        }
        
        // Handle terminal output from agent commands
        else if (chunk.type === 'terminal_output') {
          const output = chunk.output || '';
          const stderr = chunk.stderr || '';
          const command = chunk.command || '';
          const fullOutput = `\n\x1b[36m$ ${command}\x1b[0m\n${output}${stderr ? '\n\x1b[31mSTDERR:\x1b[0m ' + stderr : ''}`;
          setTerminalOutput(prev => prev + fullOutput); // APPEND, not replace
          setShowTerminal(true);
        }
        
        // Handle AI text messages (filter noise)
        else if (chunk.type === 'message' && chunk.content) {
          // Filter out internal control messages
          const content = chunk.content;
          const skipPatterns = [
            'ACTION REQUIRED',
            'MANDATORY FIRST STEP',
            'SCAFFOLDING CHECK',
            'list_directory',
            '{"type": "tool_result"',
          ];
          
          if (skipPatterns.some(p => content.includes(p))) {
            return; // Skip internal messages
          }
          
          setMessages(prev => prev.map(msg => {
            if (msg.id === aiMessageId) {
              return { 
                ...msg, 
                content: msg.content + (msg.content && !msg.content.endsWith('\n') ? ' ' : '') + content
              };
            }
            return msg;
          }));
        }
        
        // Handle pipeline completion with preview URL
        else if (chunk.type === 'complete') {
          setAgentPhase('done');
          
          // If we have a preview URL, store it and trigger Electron preview
          if (chunk.preview_url) {
            setPreviewUrl(chunk.preview_url);
            console.log('[App] Preview ready at:', chunk.preview_url);
            
            // Tell Electron to open the preview (if available)
            if (window.electron?.openPreview) {
              window.electron.openPreview(chunk.preview_url);
            } else {
              // Fallback for browser: Open in new tab
              // Note: Browsers might block this if not directly triggered by user interaction,
              // but it's the best we can do for auto-open.
              window.open(chunk.preview_url, '_blank');
              setTerminalOutput(prev => prev + `\n\n[System] Preview ready at: ${chunk.preview_url}\n(Popup might be blocked by browser)`);
            }
          }
        }
        
        // Handle errors
        else if (chunk.type === 'error') {
          setAgentPhase('error');
          setMessages(prev => prev.map(msg => {
            if (msg.id === aiMessageId) {
              return { ...msg, content: msg.content + `\n🛑 Error: ${chunk.content}` };
            }
            return msg;
          }));
        }
      },
      (error: any) => {
        setIsAgentRunning(false);
        setAgentPhase('error');
        setMessages(prev => prev.map(msg => {
          if (msg.id === aiMessageId) {
            return { ...msg, content: msg.content + `\n⚠️ Network Error: ${error.message}` };
          }
          return msg;
        }));
      }
    );
    
    setIsAgentRunning(false);
    setAgentPhase('done');
    setCurrentActivity(''); // Clear activity indicator when done
    
    // Refresh file explorer if files were created
    if (filesCreated) {
      refreshFileTree();
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const { saveFile, activeFile, rootHandle } = useFileSystem();
  
  // Kill backend process (preview server) which might be locking files
  const handleKillBackendProcess = async () => {
    try {
      if (confirm('Are you sure you want to kill the backend process (e.g. dev server)?')) {
        const response = await fetch(`${API_URL}/preview/stop`, { method: 'POST' });
        if (response.ok) {
          setTerminalOutput(prev => prev + '\n\n\x1b[31m[System] 🛑 Backend process (dev server) killed by user.\x1b[0m\n');
        } else {
          setTerminalOutput(prev => prev + '\n\n\x1b[33m[System] ⚠️ Failed to kill process.\x1b[0m\n');
        }
      }
    } catch (e) {
      console.error("Failed to kill backend process", e);
      setTerminalOutput(prev => prev + `\n\n\x1b[31m[System] ⚠️ Error killing process: ${e}\x1b[0m\n`);
    }
  };

  const handleKeyDown = (e: KeyboardEvent) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 's') {
      e.preventDefault();
      if (activeFile) {
        saveFile(activeFile);
      }
    }
  };

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [activeFile]);

  // Show Landing Page if no project is opened
  if (!rootHandle) {
    return <LandingPage />;
  }

  return (
    <div className={`app-container ${theme}`}>
      {/* LEFT PANEL SYSTEM (Explorer + Editor) - 60% */}
      <div className="main-editor-area">
        
        {/* Activity Bar (Optional, simplified for now just to hold settings/bottom) */}
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
             <div className="activity-icon" onClick={() => { console.log('Settings clicked!'); setShowSettings(true); }} title="Settings">
               <VscSettingsGear size={24} />
             </div>
           </div>
        </div>

        {/* File Explorer Sidebar */}
        {showExplorer && (
          <div className="sidebar-pane">
            <div className="sidebar-content">
              {activeSidebarView === 'files' && <FileExplorer />}
              {activeSidebarView === 'artifacts' && <ArtifactPanel projectId={currentProjectId || ''} />}
              {activeSidebarView === 'search' && <div className="p-4 text-center text-gray-500">Search not implemented</div>}
            </div>
          </div>
        )}

        {/* Editor Content Area - Swaps between Monaco and Artifact Viewer */}
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
              {/* Interactive Terminal at bottom of editor (IDE-style) */}
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

      {/* RIGHT PANEL (Chat) - 40% */}
      <div className="chat-panel">
        <div className="chat-header">
          <div className="chat-header-left">
             <RiShip2Fill size={20} style={{ marginRight: 8, color: 'var(--primary-color, #ff5e57)' }} />
             <span className="chat-title">ShipS*</span>
          </div>
          <div className="chat-header-center" style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            {/* Preview Status Indicator */}
            {previewStatus === 'running' && previewUrl && (
              <span style={{ color: '#4ec9b0', fontSize: '12px' }}>● Live: {previewUrl}</span>
            )}
            {previewStatus === 'starting' && (
              <span style={{ color: '#dcdcaa', fontSize: '12px' }}>○ Starting...</span>
            )}
            {previewStatus === 'error' && (
              <span style={{ color: '#f44747', fontSize: '12px' }}>✖ Error</span>
            )}
            
            <button 
              className="preview-btn"
              onClick={async () => {
                if (isAgentRunning) return;

                if (!electronProjectPath) {
                   console.error("No project path available");
                   setTerminalOutput(prev => prev + '\n\x1b[31m[Error] No project folder selected.\x1b[0m\n');
                   return;
                }

                try {
                  setPreviewStatus('starting');
                  setShowTerminal(true);
                  setTerminalOutput(prev => prev + '\n\n\x1b[36m[System] ▶ Starting development server...\x1b[0m\n');
                  
                  const response = await fetch(`${API_URL}/preview/start`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ path: electronProjectPath })
                  });
                  
                  const result = await response.json();
                  
                  if (result.status === 'error') {
                     setPreviewStatus('error');
                     setTerminalOutput(prev => prev + `\n\x1b[31m[Error] ${result.message}\x1b[0m\n`);
                     return;
                  }

                  // Poll for URL
                  let attempts = 0;
                  const maxAttempts = 30; // 15 seconds
                  let lastLogSeen = "";
                  
                  const pollInterval = setInterval(async () => {
                    attempts++;
                    try {
                        const statusRes = await fetch(`${API_URL}/preview/status`);
                        const status = await statusRes.json();
                        
                        // Stream ALL new logs
                        if (status.logs && status.logs.length > 0) {
                           const latest = status.logs[status.logs.length - 1];
                           if (latest && latest !== lastLogSeen) {
                               setTerminalOutput(prev => prev + `\n${latest}`);
                               lastLogSeen = latest;
                           }
                        }
                        
                        if (status.url) {
                            clearInterval(pollInterval);
                            setPreviewUrl(status.url);
                            setPreviewStatus('running');
                            setTerminalOutput(prev => prev + `\n\x1b[32m[System] ✓ Server ready at: ${status.url}\x1b[0m\n`);
                            
                            if (window.electron?.openPreview) {
                                // Running inside Electron - use IPC
                                window.electron.openPreview(status.url);
                            } else {
                                // Running in browser - try to launch Electron via custom protocol
                                // ships://preview?url=<encoded-url>&path=<encoded-path>
                                const shipsUrl = `ships://preview?url=${encodeURIComponent(status.url)}&path=${encodeURIComponent(electronProjectPath || '')}`;
                                
                                // Try launching via protocol (opens Electron if installed)
                                const protocolFrame = document.createElement('iframe');
                                protocolFrame.style.display = 'none';
                                protocolFrame.src = shipsUrl;
                                document.body.appendChild(protocolFrame);
                                
                                // After 1 second, also offer the browser fallback
                                setTimeout(() => {
                                    document.body.removeChild(protocolFrame);
                                    // Show notification that user can also view in browser
                                    setTerminalOutput(prev => prev + `\n\x1b[36m[System] Preview launched. If Electron doesn't open, visit: ${status.url}\x1b[0m\n`);
                                }, 1000);
                            }
                        } else if (attempts >= maxAttempts) {
                            clearInterval(pollInterval);
                            setPreviewStatus('error');
                            setTerminalOutput(prev => prev + '\n\x1b[33m[System] ⚠ Server timed out. Check terminal for errors.\x1b[0m\n');
                        }
                    } catch (err) {
                        console.error("Poll error", err);
                    }
                  }, 500);

                } catch (e) {
                   setPreviewStatus('error');
                   setTerminalOutput(prev => prev + `\n\x1b[31m[Error] Preview launch failed: ${e}\x1b[0m\n`);
                }
              }}
              style={{
                background: previewStatus === 'starting' ? '#555' : (isAgentRunning ? '#555' : 'var(--primary-color, #ff5e57)'),
                color: 'white',
                border: 'none',
                padding: '6px 16px',
                borderRadius: '4px',
                cursor: (isAgentRunning || previewStatus === 'starting') ? 'not-allowed' : 'pointer',
                fontSize: '13px',
                fontWeight: 500,
                opacity: (isAgentRunning || previewStatus === 'starting') ? 0.7 : 1
              }}
              disabled={isAgentRunning || previewStatus === 'starting'}
            >
              {previewStatus === 'starting' ? 'Starting...' : (isAgentRunning ? 'Busy...' : 'Preview')}
            </button>
          </div>
          <div className="chat-header-right">
            <VscLayoutSidebarRightOff size={16} />
          </div>
        </div>

        <div className="chat-messages">
          {/* Phase indicator when agent is running */}
          {isAgentRunning && agentPhase !== 'idle' && (
            <PhaseIndicator phase={agentPhase} />
          )}

          {messages.map((message) => (
            <ChatMessage key={message.id} message={message} />
          ))}

          {/* Real-time Activity Indicator */}
          <div className="activity-section">
             <ActivityIndicator 
                activity={currentActivity} 
                type={activityType} 
             />
          </div>
          
          {/* Tool progress card (History) */}
          {toolEvents.length > 0 && (
            <ToolProgress 
              events={toolEvents} 
              isCollapsed={agentPhase === 'done' || agentPhase === 'idle'}
            />
          )}
          
          <div ref={messagesEndRef} />
        </div>

        <div className="chat-input-container">
          <textarea
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Time to ShipS*?"
            className="chat-input"
            rows={1}
            style={{ minHeight: '40px' }}
          />
            <button
              className="send-button"
              onClick={handleSendMessage}
              disabled={!inputValue.trim() || isAgentRunning}
            >
              <PiShippingContainerFill size={24} />
            </button>
        </div>
      </div>

      {/* Settings Modal - Custom implementation to avoid OnsenUI React 19 issues */}
      {showSettings && (
        <div className="fullscreen-modal" style={{ 
          position: 'fixed', 
          top: 0, 
          left: 0, 
          right: 0, 
          bottom: 0, 
          display: 'flex', 
          alignItems: 'center', 
          justifyContent: 'center',
          animation: 'fadeIn 0.2s ease-out'
        }}>
          <div style={{ 
            width: '800px', 
            height: '600px', 
            maxWidth: '95vw', 
            maxHeight: '90vh',
            borderRadius: '12px',
            overflow: 'hidden',
            boxShadow: '0 12px 48px rgba(0, 0, 0, 0.6)',
            position: 'relative',
            backgroundColor: 'var(--bg-editor)'
          }}>
            <Settings onClose={() => setShowSettings(false)} />
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
