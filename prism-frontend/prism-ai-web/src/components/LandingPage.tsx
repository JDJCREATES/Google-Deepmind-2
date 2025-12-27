import { useState, useEffect } from 'react';
import { RiShip2Fill } from 'react-icons/ri';
import { PiShippingContainerFill } from "react-icons/pi";
import { useFileSystem } from '../store/fileSystem';
import { useAuthStore } from '../store/authStore';
import AuthModal from './AuthModal';
import phrases from '../data/phrases.json';

export default function LandingPage() {
  const { openProjectFolder, restoreLastProject, isRestoringProject } = useFileSystem();
  const [prompt, setPrompt] = useState('');
  // Use global store for modal
  const { isAuthenticated, openAuthModal, isAuthModalOpen, closeAuthModal } = useAuthStore();
  
  const [dailyPhrase, setDailyPhrase] = useState('');
  const [attemptedRestore, setAttemptedRestore] = useState(false);

  // Auto-restore last project on mount
  useEffect(() => {
    if (!attemptedRestore) {
      setAttemptedRestore(true);
      restoreLastProject().catch(err => {
        console.log('Could not restore project:', err);
      });
    }
  }, [attemptedRestore, restoreLastProject]);

  useEffect(() => {
    if (phrases && phrases.length > 0) {
      const randomIndex = Math.floor(Math.random() * phrases.length);
      setDailyPhrase(phrases[randomIndex]);
    }
  }, []);

  const handleStart = () => {
    // Freemium: Allow start even if not authenticated.
    // The backend limits usage to 1 prompt per IP.
    openProjectFolder(); 
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleStart();
    }
  };

  const handleAuthSuccess = () => {
    closeAuthModal();
    // Optional: openProjectFolder() if we want auto-start upon login
  };

  return (
    <div className="landing-container">
      <div className="landing-content">
        {dailyPhrase && <p className="landing-phrase">{dailyPhrase}</p>}
        {/* ... */}
        
      <AuthModal 
        isOpen={isAuthModalOpen} 
        onClose={closeAuthModal}
        onSuccess={handleAuthSuccess}
      />
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
            disabled={isRestoringProject}
          />
          <button 
            className="landing-submit-btn" 
            onClick={handleStart}
            disabled={isRestoringProject}
          >
            {isRestoringProject ? (
              <span style={{ fontSize: '14px' }}>⏳</span>
            ) : (
              <PiShippingContainerFill size={24} color="white" />
            )}
          </button>
        </div>

        <div className="landing-actions">
           <button className="text-btn" onClick={handleStart}>
             Open Existing Project
           </button>
        </div>
      </div>

      {/* Auth Modal via Global Store */}
      <AuthModal 
        isOpen={isAuthModalOpen} 
        onClose={closeAuthModal}
        onSuccess={handleAuthSuccess}
      />
    </div>
  );
}
