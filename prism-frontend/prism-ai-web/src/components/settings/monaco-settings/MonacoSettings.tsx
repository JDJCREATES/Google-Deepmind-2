import React from 'react';
import * as Ons from 'react-onsenui';
import { useSettingsStore } from '../../../store/settingsStore';
import '../Settings.css';

const MonacoSettings: React.FC = () => {
  const { monaco, updateMonacoSettings } = useSettingsStore();

  return (
    <div className="settings-page">
      {/* Appearance */}
      <div className="settings-section">
        <h3 className="settings-section-title">Appearance</h3>
        
        <div className="settings-row">
          <div className="settings-label">
            <div className="settings-label-text">Theme</div>
            <div className="settings-label-desc">Editor color theme</div>
          </div>
          <div className="settings-control">
            <select
              className="settings-select"
              value={monaco.theme}
              onChange={(e) => updateMonacoSettings({ theme: e.target.value as 'vs-dark' | 'light' })}
            >
              <option value="vs-dark">Dark</option>
              <option value="light">Light</option>
            </select>
          </div>
        </div>

        <div className="settings-row">
          <div className="settings-label">
            <div className="settings-label-text">Font Size</div>
            <div className="settings-label-desc">Editor font size in pixels</div>
          </div>
          <div className="settings-control">
            <input
              type="number"
              className="settings-input"
              value={monaco.fontSize}
              min={10}
              max={24}
              onChange={(e) => updateMonacoSettings({ fontSize: parseInt(e.target.value) })}
            />
          </div>
        </div>

        <div className="settings-row">
          <div className="settings-label">
            <div className="settings-label-text">Show Minimap</div>
            <div className="settings-label-desc">Display code minimap on the right</div>
          </div>
          <div className="settings-control">
            <Ons.Switch
              checked={monaco.minimap}
              onChange={(e: any) => updateMonacoSettings({ minimap: e.target.checked })}
            />
          </div>
        </div>

        <div className="settings-row">
          <div className="settings-label">
            <div className="settings-label-text">Line Numbers</div>
            <div className="settings-label-desc">How to display line numbers</div>
          </div>
          <div className="settings-control">
            <select
              className="settings-select"
              value={monaco.lineNumbers}
              onChange={(e) => updateMonacoSettings({ lineNumbers: e.target.value as 'on' | 'off' | 'relative' })}
            >
              <option value="on">On</option>
              <option value="off">Off</option>
              <option value="relative">Relative</option>
            </select>
          </div>
        </div>
      </div>

      {/* Formatting */}
      <div className="settings-section">
        <h3 className="settings-section-title">Formatting</h3>
        
        <div className="settings-row">
          <div className="settings-label">
            <div className="settings-label-text">Tab Size</div>
            <div className="settings-label-desc">Number of spaces per tab</div>
          </div>
          <div className="settings-control">
            <input
              type="number"
              className="settings-input"
              value={monaco.tabSize}
              min={1}
              max={8}
              onChange={(e) => updateMonacoSettings({ tabSize: parseInt(e.target.value) })}
            />
          </div>
        </div>

        <div className="settings-row">
          <div className="settings-label">
            <div className="settings-label-text">Word Wrap</div>
            <div className="settings-label-desc">How lines should wrap</div>
          </div>
          <div className="settings-control">
            <select
              className="settings-select"
              value={monaco.wordWrap}
              onChange={(e) => updateMonacoSettings({ wordWrap: e.target.value as 'off' | 'on' | 'wordWrapColumn' | 'bounded' })}
            >
              <option value="off">Off</option>
              <option value="on">On</option>
              <option value="wordWrapColumn">Word Wrap Column</option>
              <option value="bounded">Bounded</option>
            </select>
          </div>
        </div>

        <div className="settings-row">
          <div className="settings-label">
            <div className="settings-label-text">Format On Save</div>
            <div className="settings-label-desc">Automatically format code when saving</div>
          </div>
          <div className="settings-control">
            <Ons.Switch
              checked={monaco.formatOnSave}
              onChange={(e: any) => updateMonacoSettings({ formatOnSave: e.target.checked })}
            />
          </div>
        </div>
      </div>
    </div>
  );
};

export default MonacoSettings;
