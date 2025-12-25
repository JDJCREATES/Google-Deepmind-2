import { useState } from 'react';
import MonacoEditor from './components/MonacoEditor';
import { FiCode, FiSave, FiPlay, FiSettings } from 'react-icons/fi';
import { BiCodeBlock } from 'react-icons/bi';
import { MdLightMode, MdDarkMode } from 'react-icons/md';
import { AiOutlineFileText } from 'react-icons/ai';
import './App.css';

const defaultCode = `// Welcome to Monaco Editor!
function fibonacci(n: number): number {
  if (n <= 1) return n;
  return fibonacci(n - 1) + fibonacci(n - 2);
}

// Calculate the 10th Fibonacci number
const result = fibonacci(10);
console.log(\`Fibonacci(10) = \${result}\`);

// Try editing this code!
`;

const languages = [
  { id: 'typescript', name: 'TypeScript', icon: FiCode },
  { id: 'javascript', name: 'JavaScript', icon: FiCode },
  { id: 'json', name: 'JSON', icon: AiOutlineFileText },
  { id: 'html', name: 'HTML', icon: FiCode },
  { id: 'css', name: 'CSS', icon: FiCode },
];

function App() {
  const [code, setCode] = useState(defaultCode);
  const [language, setLanguage] = useState('typescript');
  const [theme, setTheme] = useState<'vs-dark' | 'light'>('vs-dark');

  const handleCodeChange = (value: string | undefined) => {
    setCode(value || '');
  };

  const toggleTheme = () => {
    setTheme(theme === 'vs-dark' ? 'light' : 'vs-dark');
  };

  return (
    <div className="app-container">
      <header className="app-header">
        <div className="header-left">
          <BiCodeBlock size={28} />
          <h1>Monaco Editor + Onsen UI</h1>
        </div>
        <div className="header-right">
          <button onClick={toggleTheme} className="theme-toggle">
            {theme === 'vs-dark' ? <MdLightMode size={24} /> : <MdDarkMode size={24} />}
          </button>
        </div>
      </header>

      <div className="main-content">
        <aside className="sidebar">
          <h3>Languages</h3>
          <ul className="language-list">
            {languages.map((lang) => {
              const Icon = lang.icon;
              return (
                <li
                  key={lang.id}
                  className={language === lang.id ? 'active' : ''}
                  onClick={() => setLanguage(lang.id)}
                >
                  <Icon size={18} />
                  <span>{lang.name}</span>
                </li>
              );
            })}
          </ul>
        </aside>

        <main className="editor-section">
          <div className="card">
            <div className="card-header">
              <h2>
                <BiCodeBlock size={24} />
                Code Editor
              </h2>
              <p className="language-info">
                Current Language: <strong>{language}</strong>
              </p>
            </div>

            <div className="editor-container">
              <MonacoEditor
                value={code}
                language={language}
                theme={theme}
                height="500px"
                onChange={handleCodeChange}
              />
            </div>

            <div className="action-buttons">
              <button className="btn btn-primary">
                <FiPlay />
                Run Code
              </button>
              <button className="btn btn-secondary">
                <FiSave />
                Save
              </button>
              <button className="btn btn-secondary">
                <FiSettings />
                Settings
              </button>
            </div>
          </div>

          <div className="card features-card">
            <h3>Features</h3>
            <ul className="features-list">
              <li>
                <div className="feature-title">Monaco Editor Integration</div>
                <div className="feature-subtitle">
                  Full-featured code editor with syntax highlighting
                </div>
              </li>
              <li>
                <div className="feature-title">Onsen UI Styling</div>
                <div className="feature-subtitle">
                  Mobile-first UI components with native feel
                </div>
              </li>
              <li>
                <div className="feature-title">React Icons</div>
                <div className="feature-subtitle">
                  Using FiCode, BiCodeBlock, MdLightMode, and more
                </div>
              </li>
            </ul>
          </div>
        </main>
      </div>
    </div>
  );
}

export default App;
