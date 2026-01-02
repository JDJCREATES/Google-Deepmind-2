import React, { useState } from 'react';
import { Page, Toolbar, ToolbarButton, Icon } from '../../lib/onsenui';
import AccountSettings from './account-settings/AccountSettings';
import MonacoSettings from './monaco-settings/MonacoSettings';
import UniversalSettings from './settings-universal/UniversalSettings';
import './Settings.css';

interface SettingsProps {
  onClose: () => void;
}

const Settings: React.FC<SettingsProps> = ({ onClose }) => {
  const [activeTab, setActiveTab] = useState(0);

  const tabs = [
    { label: 'Account', component: <AccountSettings /> },
    { label: 'Editor', component: <MonacoSettings /> },
    { label: 'General', component: <UniversalSettings /> },
  ];

  const renderToolbar = () => (
    <Toolbar>
      <div className="left">
        <ToolbarButton onClick={onClose}>
          <Icon icon="md-close" />
        </ToolbarButton>
      </div>
      <div className="center">Settings</div>
    </Toolbar>
  );

  return (
    <Page 
      renderToolbar={renderToolbar}
      renderModal={() => null}
      renderFixed={() => null}
      renderBottomToolbar={() => null}
    >
      {/* Custom Tab Bar - replaces broken Ons.Tabbar */}
      <div className="settings-tabbar">
        {tabs.map((tab, index) => (
          <button
            key={index}
            className={`settings-tabbar-item ${activeTab === index ? 'active' : ''}`}
            onClick={() => setActiveTab(index)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="settings-tab-content">
        {tabs[activeTab].component}
      </div>
    </Page>
  );
};

export default Settings;
