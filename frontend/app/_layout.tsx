import { useEffect, useState } from 'react';
import { Platform } from 'react-native';
import { Stack } from 'expo-router';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { useAuthStore } from '../store/authStore';
import { useThemeStore } from '../store/themeStore';
import { ToastProvider } from '../components/common/Toast';

function usePWAMetaTags() {
  useEffect(() => {
    if (Platform.OS !== 'web') return;
    const head = document.head;
    
    const ensureMeta = (name: string, content: string, attr = 'name') => {
      if (!head.querySelector(`meta[${attr}="${name}"]`)) {
        const meta = document.createElement('meta');
        meta.setAttribute(attr, name);
        meta.content = content;
        head.appendChild(meta);
      }
    };

    const ensureLink = (rel: string, href: string) => {
      if (!head.querySelector(`link[rel="${rel}"]`)) {
        const link = document.createElement('link');
        link.rel = rel;
        link.href = href;
        head.appendChild(link);
      }
    };

    ensureMeta('apple-mobile-web-app-capable', 'yes');
    ensureMeta('apple-mobile-web-app-status-bar-style', 'black-translucent');
    ensureMeta('apple-mobile-web-app-title', 'On Social');
    ensureMeta('mobile-web-app-capable', 'yes');
    ensureMeta('theme-color', '#000000');
    ensureLink('manifest', '/manifest.json');
    ensureLink('apple-touch-icon', '/apple-touch-icon.png');

    // Set title
    document.title = "i'M On Social";

    // Suppress browser focus outlines and autofill background on inputs
    const styleId = 'imos-global-input-styles';
    if (!head.querySelector(`#${styleId}`)) {
      const style = document.createElement('style');
      style.id = styleId;
      style.textContent = `
        input:focus, textarea:focus { outline: none !important; box-shadow: none !important; }
        textarea { min-height: 0 !important; }
        input:-webkit-autofill, input:-webkit-autofill:hover, input:-webkit-autofill:focus,
        textarea:-webkit-autofill, textarea:-webkit-autofill:hover, textarea:-webkit-autofill:focus {
          -webkit-box-shadow: 0 0 0px 1000px #1C1C1E inset !important;
          -webkit-text-fill-color: #FFFFFF !important;
          caret-color: #FFFFFF !important;
          transition: background-color 5000s ease-in-out 0s;
        }
      `;
      head.appendChild(style);
    }
  }, []);
}

export default function RootLayout() {
  const loadAuth = useAuthStore((state) => state.loadAuth);
  const loadTheme = useThemeStore((state) => state.loadTheme);
  const colors = useThemeStore((state) => state.colors);
  const [mounted, setMounted] = useState(false);
  
  usePWAMetaTags();
  
  useEffect(() => {
    loadAuth();
    loadTheme();
    setMounted(true);
  }, []);
  
  // Use SSR-safe default (#000000) until client hydration is complete
  const bgColor = mounted ? colors.bg : '#000000';
  
  return (
    <GestureHandlerRootView style={{ flex: 1, backgroundColor: bgColor }}>
      <SafeAreaProvider>
        <ToastProvider>
          <Stack screenOptions={{ headerShown: false, animation: 'none' }}>
            <Stack.Screen name="index" options={{ animation: 'none' }} />
            <Stack.Screen name="auth/login" options={{ animation: 'none' }} />
            <Stack.Screen name="auth/signup" />
            <Stack.Screen name="auth/forgot-password" />
            <Stack.Screen name="onboarding/index" />
            <Stack.Screen name="(tabs)" />
            <Stack.Screen name="settings" />
            <Stack.Screen name="card/[userId]" />
            <Stack.Screen name="thread/[id]" />
            <Stack.Screen name="contact/[id]" />
            <Stack.Screen name="review/[storeSlug]" />
            <Stack.Screen name="l/[username]" />
          </Stack>
        </ToastProvider>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}