import { useState } from 'react';
import { RiShip2Fill } from 'react-icons/ri';
import { PiShippingContainerFill } from "react-icons/pi";
import { useFileSystem } from '../store/fileSystem';
import { useAuthStore } from '../store/authStore';
import AuthModal from './AuthModal';

export default function LandingPage() {
  const { openProjectFolder } = useFileSystem();
  const { isAuthenticated } = useAuthStore();
  const [prompt, setPrompt] = useState('');
  const [showAuthModal, setShowAuthModal] = useState(false);

  const handleStart = () => {
    if (!isAuthenticated) {
      setShowAuthModal(true);
      return;
    }
    openProjectFolder(); 
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleStart();
    }
  };

  const handleAuthSuccess = () => {
    setShowAuthModal(false);
    openProjectFolder();
  };

  return (
    <div className="landing-container">
      <div className="landing-content">
        <div className="brand-header">
          <RiShip2Fill className="brand-icon" size={48} color="var(--primary-color)" />
          <h1 className="brand-title">ShipS*</h1>
        </div>
        
        <p className="landing-subtitle">
          What would you like to build today?
        </p>

        <div className="landing-input-wrapper">
          <input 
            type="text" 
            className="landing-input"
            placeholder="Build a CRM for a cat cafe..."
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            onKeyPress={handleKeyPress}
          />
          <button className="landing-submit-btn" onClick={handleStart}>
            <PiShippingContainerFill size={24} color="white" />
          </button>
        </div>

        <div className="landing-actions">
           <button className="text-btn" onClick={handleStart}>
             Open Existing Project
           </button>
        </div>
      </div>

      <AuthModal 
        isOpen={showAuthModal} 
        onClose={() => setShowAuthModal(false)}
        onSuccess={handleAuthSuccess}
      />
    </div>
  );
}
