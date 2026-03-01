import { create } from 'zustand';
import AsyncStorage from '@react-native-async-storage/async-storage';

export type ThemeMode = 'dark' | 'light';

const COLORS = {
  dark: {
    bg: '#000000',
    card: '#1C1C1E',
    cardAlt: '#1A1A1E',
    surface: '#2C2C2E',
    border: '#2C2C2E',
    borderLight: '#3A3A3C',
    text: '#FFFFFF',
    textSecondary: '#8E8E93',
    textTertiary: '#636366',
    tabBar: '#000000',
    tabBarBorder: '#2C2C2E',
    header: '#000000',
    inputBg: '#1C1C1E',
    modalBg: '#1C1C1E',
    overlay: 'rgba(0,0,0,0.6)',
    statusBar: 'light',
    accent: '#C9A962',
    accentText: '#000000',
    searchBg: '#1C1C1E',
    badge: '#FF3B30',
    success: '#34C759',
    warning: '#FF9500',
    danger: '#FF3B30',
    info: '#007AFF',
    skeleton: '#2C2C2E',
  },
  light: {
    bg: '#F2F2F7',
    card: '#FFFFFF',
    cardAlt: '#FFFFFF',
    surface: '#E5E5EA',
    border: '#D1D1D6',
    borderLight: '#E5E5EA',
    text: '#000000',
    textSecondary: '#6C6C70',
    textTertiary: '#8E8E93',
    tabBar: '#FFFFFF',
    tabBarBorder: '#D1D1D6',
    header: '#FFFFFF',
    inputBg: '#FFFFFF',
    modalBg: '#FFFFFF',
    overlay: 'rgba(0,0,0,0.3)',
    statusBar: 'dark',
    accent: '#C9A962',
    accentText: '#000000',
    searchBg: '#E5E5EA',
    badge: '#FF3B30',
    success: '#34C759',
    warning: '#FF9500',
    danger: '#FF3B30',
    info: '#007AFF',
    skeleton: '#E5E5EA',
  },
} as const;

export type ThemeColors = typeof COLORS.dark;

interface ThemeState {
  mode: ThemeMode;
  colors: ThemeColors;
  setMode: (mode: ThemeMode) => void;
  toggle: () => void;
  loadTheme: () => Promise<void>;
}

export const useThemeStore = create<ThemeState>((set, get) => ({
  mode: 'dark',
  colors: COLORS.dark,
  setMode: (mode: ThemeMode) => {
    set({ mode, colors: COLORS[mode] });
    AsyncStorage.setItem('theme_mode', mode);
  },
  toggle: () => {
    const next = get().mode === 'dark' ? 'light' : 'dark';
    set({ mode: next, colors: COLORS[next] });
    AsyncStorage.setItem('theme_mode', next);
  },
  loadTheme: async () => {
    const saved = await AsyncStorage.getItem('theme_mode');
    if (saved === 'light' || saved === 'dark') {
      set({ mode: saved, colors: COLORS[saved] });
    }
  },
}));
