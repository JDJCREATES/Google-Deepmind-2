import { useState } from 'react';
import { PiShippingContainerFill, PiLinkBold } from "react-icons/pi";

function App() {
  const [projectUrl, setProjectUrl] = useState<string | null>(null);
  const [isConnecting, setIsConnecting] = useState(false);

  // TODO: integrate with backend or main process to get active project
  const handleConnect = async () => {
      setIsConnecting(true);
      // Mock connection for now
      setTimeout(() => {
          // In real implementation, this would be the localhost url of the user's app
          setIsConnecting(false);
          // setProjectUrl('http://localhost:3000'); 
      }, 2000);
  };

  if (projectUrl) {
      return (
          <div style={{ width: '100vw', height: '100vh', display: 'flex', flexDirection: 'column' }}>
             {/* Preview Header / Controls could go here */}
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
        <div style={{ display: 'flex', alignItems: 'center', gap: 15, marginBottom: 10 }}>
            <PiShippingContainerFill 
                size={56} 
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
        <p style={{ color: '#888', fontSize: '16px', marginTop: 0, marginBottom: 40 }}>
            Preview Environment
        </p>

        <button 
            onClick={handleConnect}
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
                opacity: isConnecting ? 0.8 : 1
            }}
            onMouseOver={(e) => e.currentTarget.style.transform = 'translateY(-2px)'}
            onMouseOut={(e) => e.currentTarget.style.transform = 'translateY(0)'}
        >
            <PiLinkBold size={20} />
            {isConnecting ? 'Connecting...' : 'Connect to Project'}
        </button>
      </div>
    </div>
  );
}

export default App;


