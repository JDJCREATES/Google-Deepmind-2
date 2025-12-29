import { useState, useRef, useEffect } from 'react';
import ChatMessage, { type Message } from './components/ChatMessage';
import MonacoEditor from './components/MonacoEditor';
import FileExplorer from './components/FileExplorer';
import EditorTabs from './components/EditorTabs';
import LandingPage from './components/LandingPage';
import ArtifactPanel from './components/artifacts/ArtifactPanel';
import ArtifactViewer from './components/artifacts/ArtifactViewer';
import { useFileSystem } from './store/fileSystem';
import { useArtifactStore } from './store/artifactStore';
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
import './App.css';

type SidebarView = 'files' | 'artifacts' | 'search';

function App() {
  const [theme, setTheme] = useState<'vs-dark' | 'light'>('vs-dark');
  const [showExplorer, setShowExplorer] = useState(true);
  const [activeSidebarView, setActiveSidebarView] = useState<SidebarView>('files');
  const { currentProjectId } = useArtifactStore();
  const { refreshFileTree } = useFileSystem();
  
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
  // Get project path from Electron (if available)
  const [electronProjectPath, setElectronProjectPath] = useState<string | null>(null);
  
  // Fetch project path from Electron on mount
  useEffect(() => {
    const fetchProjectPath = async () => {
      if (window.electron?.getLastProject) {
        const result = await window.electron.getLastProject();
        if (result.path) {
          setElectronProjectPath(result.path);
        }
      }
    };
    fetchProjectPath();
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

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const toggleTheme = () => {
    setTheme(theme === 'vs-dark' ? 'light' : 'vs-dark');
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
        }
        
        // Handle tool start (show spinner)
        else if (chunk.type === 'tool_start') {
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
             <div className="activity-icon" title="Settings">
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
          <div className="chat-header-center">
            <button 
              className="preview-btn"
              onClick={() => {
                // Try to open the Electron app via custom protocol
                window.location.href = 'ships://preview';
              }}
              style={{
                background: 'var(--primary-color, #ff5e57)',
                color: 'white',
                border: 'none',
                padding: '6px 16px',
                borderRadius: '4px',
                cursor: 'pointer',
                fontSize: '13px',
                fontWeight: 500
              }}
            >
              Preview
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
          
          {/* Tool progress card when there are tool events */}
          {toolEvents.length > 0 && (
            <ToolProgress events={toolEvents} />
          )}
          
          <div ref={messagesEndRef} />
        </div>

        <div className="chat-input-container">
          <textarea
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Ask me anything..."
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
    </div>
  );
}

export default App;
