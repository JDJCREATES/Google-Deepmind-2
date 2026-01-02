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
    <Ons.Page renderToolbar={renderToolbar} renderModal={() => null} renderFixed={() => null} renderBottomToolbar={() => null}>
      <Ons.Tabbar
        swipeable={false}
        position="top"
        index={activeTab}
        onPreChange={(event: TabbarPreChangeEvent) => setActiveTab(event.index)}
        renderTabs={() => [
          {
            content: <AccountSettings key="account" />,
            tab: <Ons.Tab key="account-tab" label="Account" />,
          },
          {
            content: <MonacoSettings key="monaco" />,
            tab: <Ons.Tab key="monaco-tab" label="Editor" />,
          },
          {
            content: <UniversalSettings key="universal" />,
            tab: <Ons.Tab key="universal-tab" label="General" />,
          },
        ]}
      />
    </Ons.Page>
  );
};

export default Settings;
