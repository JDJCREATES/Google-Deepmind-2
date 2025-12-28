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
  VscLayoutSidebarRightOff 
} from 'react-icons/vsc';
import { BiBox } from 'react-icons/bi';
import { agentService, type AgentChunk } from './services/agentService';
import './App.css';

type SidebarView = 'files' | 'artifacts' | 'search';

function App() {
  const [theme, setTheme] = useState<'vs-dark' | 'light'>('vs-dark');
  const [showExplorer, setShowExplorer] = useState(true);
  const [activeSidebarView, setActiveSidebarView] = useState<SidebarView>('files');
  const { currentProjectId } = useArtifactStore();
  
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

    // Create a placeholder AI message
    const aiMessageId = (Date.now() + 1).toString();
    const initialAiMessage: Message = {
      id: aiMessageId,
      content: '', // Start empty, will stream in
      sender: 'ai',
      timestamp: new Date(),
    };
    
    setMessages(prev => [...prev, initialAiMessage]);

    // Project path is handled securely on the backend via preview_manager
    // Frontend doesn't need to send it - backend falls back to current project
    await agentService.runAgent(
      userMessage.content,
      null, // Backend uses preview_manager.current_project_path as fallback
      (chunk: AgentChunk) => {
        if (chunk.type === 'message' && chunk.content) {
          setMessages(prev => prev.map(msg => {
            if (msg.id === aiMessageId) {
              return { 
                ...msg, 
                content: msg.content + (msg.content ? '\n' : '') + chunk.content // Check if we should append or replace? logic depends on backend
              };
            }
            return msg;
          }));
        } else if (chunk.type === 'phase') {
           // Optional: Show phase toast or status indicator
           console.log("Agent Phase:", chunk.phase);
        } else if (chunk.type === 'error') {
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
         setMessages(prev => prev.map(msg => {
            if (msg.id === aiMessageId) {
              return { ...msg, content: msg.content + `\n⚠️ Network Error: ${error.message}` };
            }
            return msg;
          }));
      }
    );
    
    setIsAgentRunning(false);
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
             <div className="activity-icon" onClick={toggleTheme}>
               {theme === 'vs-dark' ? <MdLightMode size={24} /> : <MdDarkMode size={24} />}
             </div>
             <div className="activity-icon">
               <VscSettingsGear size={24} />
             </div>
           </div>
        </div>

        {/* File Explorer Sidebar */}
        {showExplorer && (
          <div className="sidebar-pane">
            {activeSidebarView === 'files' && <FileExplorer />}
            {activeSidebarView === 'artifacts' && <ArtifactPanel projectId={currentProjectId || ''} />}
            {activeSidebarView === 'search' && <div className="p-4 text-center text-gray-500">Search not implemented</div>}
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
          {messages.map((message) => (
            <ChatMessage key={message.id} message={message} />
          ))}
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
