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

interface SettingsState {
  monaco: MonacoSettings;
  app: AppSettings;
  updateMonacoSettings: (settings: Partial<MonacoSettings>) => void;
  updateAppSettings: (settings: Partial<AppSettings>) => void;
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

export const useSettingsStore = create<SettingsState>()(
  persist(
    (set) => ({
      monaco: defaultMonacoSettings,
      app: defaultAppSettings,

      updateMonacoSettings: (settings) =>
        set((state) => ({
          monaco: { ...state.monaco, ...settings },
        })),

      updateAppSettings: (settings) =>
        set((state) => ({
          app: { ...state.app, ...settings },
        })),

      resetToDefaults: () =>
        set({
          monaco: defaultMonacoSettings,
          app: defaultAppSettings,
        }),
    }),
    {
      name: 'ships-settings-storage',
    }
  )
);
