import { useEffect } from 'react';
import { Platform } from 'react-native';
import { Stack } from 'expo-router';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { useAuthStore } from '../store/authStore';
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
    ensureMeta('apple-mobile-web-app-title', 'iMOs');
    ensureMeta('mobile-web-app-capable', 'yes');
    ensureMeta('theme-color', '#000000');
    ensureLink('manifest', '/manifest.json');
    ensureLink('apple-touch-icon', '/apple-touch-icon.png');

    // Set title
    document.title = "i'M On Social";
  }, []);
}

export default function RootLayout() {
  const loadAuth = useAuthStore((state) => state.loadAuth);
  
  usePWAMetaTags();
  
  useEffect(() => {
    loadAuth();
  }, []);
  
  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <SafeAreaProvider>
        <ToastProvider>
          <Stack screenOptions={{ headerShown: false }}>
            <Stack.Screen name="index" />
            <Stack.Screen name="auth/login" />
            <Stack.Screen name="auth/signup" />
            <Stack.Screen name="auth/forgot-password" />
            <Stack.Screen name="onboarding/index" />
            <Stack.Screen name="(tabs)" />
            <Stack.Screen name="settings" />
            <Stack.Screen name="card/[userId]" />
            <Stack.Screen name="thread/[id]" />
            <Stack.Screen name="contact/[id]" />
            <Stack.Screen name="review/[storeSlug]" />
          </Stack>
        </ToastProvider>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}