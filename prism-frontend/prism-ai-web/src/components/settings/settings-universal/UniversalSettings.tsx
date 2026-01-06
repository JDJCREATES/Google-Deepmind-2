import React from 'react';
import * as Ons from 'react-onsenui';
import type { SwitchChangeEvent } from 'react-onsenui';
import { useSettingsStore } from '../../../store/settingsStore';
import { SettingsCarousel, CarouselSlide } from '../../ui/SettingsCarousel';
import '../Settings.css';

const UniversalSettings: React.FC = () => {
  const { 
    app, 
    artifacts, 
    updateAppSettings, 
    updateArtifactSettings, 
    resetToDefaults 
  } = useSettingsStore();

  const handleReset = () => {
    if (window.confirm('Are you sure you want to reset all settings to their default values?')) {
      resetToDefaults();
    }
  };

  if (!app) return <div className="p-4">Loading settings...</div>;

  return (
    <SettingsCarousel>
        {/* Slide 1: General Settings */}
        <CarouselSlide>
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
                  onChange={(e: SwitchChangeEvent) => {
                    const target = e.target as HTMLInputElement | null;
                    if (target) updateAppSettings({ autoSave: target.checked });
                  }}
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
                  onChange={(e: SwitchChangeEvent) => {
                    const target = e.target as HTMLInputElement | null;
                    if (target) updateAppSettings({ confirmBeforeExit: target.checked });
                  }}
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
                  onChange={(e: SwitchChangeEvent) => {
                    const target = e.target as HTMLInputElement | null;
                    if (target) updateAppSettings({ showWelcomeScreen: target.checked });
                  }}
                />
              </div>
            </div>
          </div>

          {/* Artifacts Settings */}
          <div className="settings-section">
            <h3 className="settings-section-title">Artifacts</h3>
            
            <div className="settings-row">
              <div className="settings-label">
                <div className="settings-label-text">File Tree Scan Depth</div>
                <div className="settings-label-desc">Maximum folder depth scanning planning</div>
              </div>
              <div className="settings-control">
                <input
                  type="number"
                  className="settings-input"
                  value={artifacts?.fileTreeDepth ?? 3}
                  min={1}
                  max={10}
                  step={1}
                  onChange={(e) => {
                    const val = parseInt(e.target.value);
                    if (!isNaN(val) && val >= 1 && val <= 10) {
                      updateArtifactSettings({ fileTreeDepth: val });
                    }
                  }}
                />
              </div>
            </div>
          </div>
        </div>
      </CarouselSlide>

      {/* Slide 2: Advanced / Reset */}
      <CarouselSlide>
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
      </CarouselSlide>
    </SettingsCarousel>
  );
};

export default UniversalSettings;
