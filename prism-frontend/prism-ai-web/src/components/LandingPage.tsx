import { useState, useEffect } from 'react';
import { RiShip2Fill } from 'react-icons/ri';
import { PiShippingContainerFill } from "react-icons/pi";
import { useFileSystem } from '../store/fileSystem';
import { useAuthStore } from '../store/authStore';
import AuthModal from './AuthModal';
import phrases from '../data/phrases.json';

export default function LandingPage() {
  const { openProjectFolder } = useFileSystem();
  const { isAuthenticated } = useAuthStore();
  const [prompt, setPrompt] = useState('');
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [dailyPhrase, setDailyPhrase] = useState('');

  useEffect(() => {
    // Daily Phrase Logic
    const today = new Date().toISOString().split('T')[0];
    const stored = localStorage.getItem('ships_daily_phrase');
    
    if (stored) {
      const parsed = JSON.parse(stored);
      if (parsed.date === today) {
        setDailyPhrase(parsed.phrase);
        return;
      }
    }

    // Pick new random phrase
    const randomPhrase = phrases[Math.floor(Math.random() * phrases.length)];
    setDailyPhrase(randomPhrase);
    localStorage.setItem('ships_daily_phrase', JSON.stringify({
      date: today,
      phrase: randomPhrase
    }));
  }, []);

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
        {dailyPhrase && <p className="landing-phrase">{dailyPhrase}</p>}
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
