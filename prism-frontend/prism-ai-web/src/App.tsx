import { useState, useRef, useEffect } from 'react';
import ChatMessage, { type Message } from './components/ChatMessage';
import MonacoEditor from './components/MonacoEditor';
import FileExplorer from './components/FileExplorer';
import EditorTabs from './components/EditorTabs';
import LandingPage from './components/LandingPage';
import { useFileSystem } from './store/fileSystem';
import { IoSend } from 'react-icons/io5';
import { MdLightMode, MdDarkMode } from 'react-icons/md';
import { VscSettingsGear, VscLayoutSidebarLeft, VscLayoutSidebarRightOff } from 'react-icons/vsc';
import { BiCodeBlock } from 'react-icons/bi';
import './App.css';

function App() {
  const [theme, setTheme] = useState<'vs-dark' | 'light'>('vs-dark');
  const [showExplorer, setShowExplorer] = useState(true);
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      content: 'Hello! I\'m your AI coding assistant. Open a file in the explorer to get started!',
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

  const handleSendMessage = () => {
    if (!inputValue.trim()) return;

    const newMessage: Message = {
      id: Date.now().toString(),
      content: inputValue,
      sender: 'user',
      timestamp: new Date(),
    };

    setMessages([...messages, newMessage]);
    setInputValue('');

    // Simulate AI response
    setTimeout(() => {
      const aiResponse: Message = {
        id: (Date.now() + 1).toString(),
        content: 'I see you are working on the code. How can I assist you with this file?',
        sender: 'ai',
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, aiResponse]);
    }, 1000);
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
             <div className={`activity-icon ${showExplorer ? 'active' : ''}`} onClick={() => setShowExplorer(!showExplorer)}>
               <VscLayoutSidebarLeft size={24} />
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
            <FileExplorer />
          </div>
        )}

        {/* Editor Content Area */}
        <div className="editor-pane">
          <div className="editor-tabs-container">
            <EditorTabs />
          </div>
          <div className="monaco-container">
            <MonacoEditor theme={theme} />
          </div>
        </div>

      </div>

      {/* RIGHT PANEL (Chat) - 40% */}
      <div className="chat-panel">
        <div className="chat-header">
          <div className="chat-header-left">
             <BiCodeBlock size={20} style={{ marginRight: 8 }} />
             <span className="chat-title">AI Assistant</span>
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
            onClick={handleSendMessage}
            className="send-button"
            disabled={!inputValue.trim()}
          >
            <IoSend size={16} />
          </button>
        </div>
      </div>
    </div>
  );
}

export default App;
