import React, { useState } from 'react';
import * as Ons from 'react-onsenui';
import { useSettingsStore } from '../../../store/settingsStore';
import '../Settings.css';

const UniversalSettings: React.FC = () => {
  const { app, updateAppSettings, resetToDefaults } = useSettingsStore();
  const [index, setIndex] = useState(0);

  const handleReset = () => {
    if (window.confirm('Are you sure you want to reset all settings to their default values?')) {
      resetToDefaults();
    }
  };

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <Ons.Carousel 
        swipeable 
        autoScroll 
        overscrollable 
        index={index} 
        onPostChange={(e: any) => setIndex(e.activeIndex)}
        style={{ flex: 1 }}
      >
        {/* Slide 1: General Settings */}
        <Ons.CarouselItem>
          <div className="settings-page">
            {/* File Management */}
            <div className="settings-section">
              <h3 className="settings-section-title">File Management</h3>
              
              <div className="settings-row">
                <div className="settings-label">
                  <div className="settings-label-text">Auto Save</div>
                  <div className="settings-label-desc">Automatically save files after editing</div>
                </div>
                <div className="settings-control">
                  <Ons.Switch
                    checked={app.autoSave}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) => updateAppSettings({ autoSave: e.target.checked })}
                  />
                </div>
              </div>

              <div className="settings-row">
                <div className="settings-label">
                  <div className="settings-label-text">Auto Save Delay</div>
                  <div className="settings-label-desc">Delay in milliseconds</div>
                </div>
                <div className="settings-control">
                  <input
                    type="number"
                    className="settings-input"
                    value={app.autoSaveDelay}
                    min={500}
                    max={5000}
                    step={100}
                    disabled={!app.autoSave}
                    onChange={(e) => {
                      const value = parseInt(e.target.value);
                      if (!isNaN(value) && value >= 500 && value <= 5000) {
                        updateAppSettings({ autoSaveDelay: value });
                      }
                    }}
                  />
                </div>
              </div>
            </div>

            {/* Application Behavior */}
            <div className="settings-section">
              <h3 className="settings-section-title">Application Behavior</h3>
              
              <div className="settings-row">
                <div className="settings-label">
                  <div className="settings-label-text">Confirm Before Exit</div>
                  <div className="settings-label-desc">Ask for confirmation when closing</div>
                </div>
                <div className="settings-control">
                  <Ons.Switch
                    checked={app.confirmBeforeExit}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) => updateAppSettings({ confirmBeforeExit: e.target.checked })}
                  />
                </div>
              </div>

              <div className="settings-row">
                <div className="settings-label">
                  <div className="settings-label-text">Show Welcome Screen</div>
                  <div className="settings-label-desc">Display welcome screen on startup</div>
                </div>
                <div className="settings-control">
                  <Ons.Switch
                    checked={app.showWelcomeScreen}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) => updateAppSettings({ showWelcomeScreen: e.target.checked })}
                  />
                </div>
              </div>
            </div>
          </div>
        </Ons.CarouselItem>

        {/* Slide 2: Advanced / Reset */}
        <Ons.CarouselItem>
          <div className="settings-page">
            <div className="settings-section">
              <h3 className="settings-section-title">Reset</h3>
              
              <div className="settings-row">
                <div className="settings-label">
                  <div className="settings-label-text">Reset to Defaults</div>
                  <div className="settings-label-desc">Restore all settings to default values</div>
                </div>
                <div className="settings-control">
                  <button 
                    className="settings-button settings-button-secondary"
                    onClick={handleReset}
                  >
                    Reset All Settings
                  </button>
                </div>
              </div>
            </div>
          </div>
        </Ons.CarouselItem>
      </Ons.Carousel>

      <div style={{ 
        display: 'flex', 
        justifyContent: 'center', 
        padding: '10px 0', 
        gap: '8px', 
        borderTop: '1px solid var(--border-color)' 
      }}>
        {[0, 1].map((i) => (
          <div 
            key={i}
            onClick={() => setIndex(i)}
            style={{ 
              width: '8px', 
              height: '8px', 
              borderRadius: '50%', 
              background: index === i ? 'var(--primary-color)' : 'var(--text-secondary)',
              opacity: index === i ? 1 : 0.3,
              cursor: 'pointer',
              transition: 'all 0.2s ease'
            }}
          />
        ))}
      </div>
    </div>
  );
};

export default UniversalSettings;
