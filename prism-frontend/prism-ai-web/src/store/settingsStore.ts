import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export interface MonacoSettings {
  theme: 'vs-dark' | 'light';
  fontSize: number;
  tabSize: number;
  wordWrap: 'off' | 'on' | 'wordWrapColumn' | 'bounded';
  minimap: boolean;
  lineNumbers: 'on' | 'off' | 'relative';
  formatOnSave: boolean;
}

export interface AppSettings {
  autoSave: boolean;
  autoSaveDelay: number; // in milliseconds
  confirmBeforeExit: boolean;
  showWelcomeScreen: boolean;
}

export interface SecuritySettings {
  enableInputSanitization: boolean;
  enableOutputFiltering: boolean;
  redactSensitiveData: boolean;
  logSecurityEvents: boolean;
  strictCommandWhitelist: boolean;
  allowNetworkRequests: boolean;
  riskThreshold: 'low' | 'medium' | 'high';
}

interface SettingsState {
  monaco: MonacoSettings;
  app: AppSettings;
  security: SecuritySettings;
  updateMonacoSettings: (settings: Partial<MonacoSettings>) => void;
  updateAppSettings: (settings: Partial<AppSettings>) => void;
  updateSecuritySettings: (settings: Partial<SecuritySettings>) => void;
  resetToDefaults: () => void;
}

const defaultMonacoSettings: MonacoSettings = {
  theme: 'vs-dark',
  fontSize: 14,
  tabSize: 2,
  wordWrap: 'off',
  minimap: true,
  lineNumbers: 'on',
  formatOnSave: false,
};

const defaultAppSettings: AppSettings = {
  autoSave: false,
  autoSaveDelay: 1000,
  confirmBeforeExit: true,
  showWelcomeScreen: true,
};

const defaultSecuritySettings: SecuritySettings = {
  enableInputSanitization: true,
  enableOutputFiltering: true,
  redactSensitiveData: true,
  logSecurityEvents: true,
  strictCommandWhitelist: true,
  allowNetworkRequests: false,
  riskThreshold: 'medium',
};

export const useSettingsStore = create<SettingsState>()(
  persist(
    (set) => ({
      monaco: defaultMonacoSettings,
      app: defaultAppSettings,
      security: defaultSecuritySettings,

      updateMonacoSettings: (settings) =>
        set((state) => ({
          monaco: { ...state.monaco, ...settings },
        })),

      updateAppSettings: (settings) =>
        set((state) => ({
          app: { ...state.app, ...settings },
        })),

      updateSecuritySettings: (settings) =>
        set((state) => ({
          security: { ...state.security, ...settings },
        })),

      resetToDefaults: () =>
        set({
          monaco: defaultMonacoSettings,
          app: defaultAppSettings,
          security: defaultSecuritySettings,
        }),
    }),
    {
      name: 'prism-settings-storage',
    }
  )
);
