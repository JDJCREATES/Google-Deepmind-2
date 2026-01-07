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

export interface ArtifactSettings {
  fileTreeDepth: number;
}

interface SettingsState {
  monaco: MonacoSettings;
  app: AppSettings;
  security: SecuritySettings;
  artifacts: ArtifactSettings;
  updateMonacoSettings: (settings: Partial<MonacoSettings>) => void;
  updateAppSettings: (settings: Partial<AppSettings>) => void;
  updateSecuritySettings: (settings: Partial<SecuritySettings>) => void;
  updateArtifactSettings: (settings: Partial<ArtifactSettings>) => void;
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

const defaultArtifactSettings: ArtifactSettings = {
  fileTreeDepth: 3,
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
      artifacts: defaultArtifactSettings,

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

      updateArtifactSettings: (settings) =>
        set((state) => ({
          artifacts: { ...state.artifacts, ...settings },
        })),

      resetToDefaults: () =>
        set({
          monaco: defaultMonacoSettings,
          app: defaultAppSettings,
          security: defaultSecuritySettings,
          artifacts: defaultArtifactSettings,
        }),
    }),
    {
      name: 'prism-settings-storage',
    }
  )
);
