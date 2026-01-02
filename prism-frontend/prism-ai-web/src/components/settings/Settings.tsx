import React, { useState } from 'react';
import * as Ons from 'react-onsenui';
import AccountSettings from './account-settings/AccountSettings';
import MonacoSettings from './monaco-settings/MonacoSettings';
import UniversalSettings from './settings-universal/UniversalSettings';
import './Settings.css';

interface SettingsProps {
  onClose: () => void;
}

interface TabbarPreChangeEvent {
  index: number;
  activeIndex: number;
}

const Settings: React.FC<SettingsProps> = ({ onClose }) => {
  const [activeTab, setActiveTab] = useState(0);

  const renderToolbar = () => {
    return (
      <Ons.Toolbar>
        <div className="left">
          <Ons.ToolbarButton onClick={onClose}>
            <Ons.Icon icon="md-close" />
          </Ons.ToolbarButton>
        </div>
        <div className="center">Settings</div>
      </Ons.Toolbar>
    );
  };

  return (
    <Ons.Page renderToolbar={renderToolbar}>
      <Ons.Tabbar
        swipeable={false}
        position="top"
        index={activeTab}
        onPreChange={(event: TabbarPreChangeEvent) => setActiveTab(event.index)}
        renderTabs={() => [
          {
            content: <AccountSettings />,
            tab: <Ons.Tab label="Account" />,
          },
          {
            content: <MonacoSettings />,
            tab: <Ons.Tab label="Editor" />,
          },
          {
            content: <UniversalSettings />,
            tab: <Ons.Tab label="General" />,
          },
        ]}
      />
    </Ons.Page>
  );
};

export default Settings;
