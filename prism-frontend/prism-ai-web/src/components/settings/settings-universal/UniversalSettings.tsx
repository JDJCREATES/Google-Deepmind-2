import React from 'react';
import * as Ons from 'react-onsenui';
import { useSettingsStore } from '../../../store/settingsStore';
import '../Settings.css';

const UniversalSettings: React.FC = () => {
  const { app, updateAppSettings, resetToDefaults } = useSettingsStore();

  const handleReset = () => {
    if (window.confirm('Are you sure you want to reset all settings to their default values?')) {
      resetToDefaults();
    }
  };

  return (
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
            <div className="settings-label-desc">Delay in milliseconds before auto-saving</div>
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
              onChange={(e) => updateAppSettings({ autoSaveDelay: parseInt(e.target.value) })}
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
            <div className="settings-label-desc">Ask for confirmation when closing the app</div>
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

      {/* Reset Settings */}
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
  );
};

export default UniversalSettings;
