import { useSettingsStore } from '../store/settingsStore';

export function useTheme() {
    const theme = useSettingsStore(state => state.monaco.theme);
    const updateSettings = useSettingsStore(state => state.updateMonacoSettings);

    const toggleTheme = () => {
        const newTheme = theme === 'vs-dark' ? 'light' : 'vs-dark';
        updateSettings({ theme: newTheme });
    };

    return { theme, toggleTheme };
}
