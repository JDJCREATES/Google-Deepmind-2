import { useState } from 'react';
import { RiShip2Fill } from 'react-icons/ri';
import { IoArrowForward } from 'react-icons/io5';
import { useFileSystem } from '../store/fileSystem';

export default function LandingPage() {
  const { openProjectFolder } = useFileSystem();
  const [prompt, setPrompt] = useState('');

  const handleStart = () => {
    openProjectFolder(); 
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleStart();
    }
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
            <IoArrowForward size={20} />
          </button>
        </div>

        <div className="landing-actions">
           <button className="text-btn" onClick={openProjectFolder}>
             Open Existing Project
           </button>
        </div>
      </div>
    </div>
  );
}
