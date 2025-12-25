import { useState } from 'react';
import { PiShippingContainerFill } from "react-icons/pi";

function App() {
  const [logs, setLogs] = useState<string[]>([]);
  const [status, setStatus] = useState('Idle');

  const handleBuild = async () => {
    setStatus('Building...');
    setLogs(prev => [...prev, 'Starting build...']);
    // Mock call
    // @ts-ignore
    const result = await window.electron.runBuild('path/to/project');
    setLogs(prev => [...prev, result.message]);
    setStatus('Done');
  };

  return (
    <div style={{ padding: 20, backgroundColor: '#1e1e1e', color: '#ccc', height: '100vh', fontFamily: 'monospace' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 20 }}>
        <PiShippingContainerFill size={32} color="#FF5E57" />
        <h1 style={{ margin: 0, color: 'white' }}>ShipS* Builder</h1>
      </div>
      
      <div style={{ marginBottom: 20 }}>
        <button onClick={handleBuild} style={{ padding: '8px 16px', backgroundColor: '#FF5E57', border: 'none', color: 'white', cursor: 'pointer' }}>
            Run Build
        </button>
        <span style={{ marginLeft: 10 }}>Status: {status}</span>
      </div>

      <div style={{ backgroundColor: '#000', padding: 10, borderRadius: 4, height: 300, overflowY: 'auto' }}>
        {logs.map((log, i) => <div key={i}>{log}</div>)}
      </div>
    </div>
  );
}

export default App;
