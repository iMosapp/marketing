import { useEffect, useState } from 'react';
import { Platform, View } from 'react-native';
import { Stack, useSegments } from 'expo-router';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { useAuthStore } from '../store/authStore';
import { useThemeStore } from '../store/themeStore';
import { ToastProvider } from '../components/common/Toast';
import JessieFloatingChat, { JESSI_BAR_HEIGHT } from '../components/JessieFloatingChat';
import { ErrorBoundary } from '../components/ErrorBoundary';
import { initGlobalErrorHandlers } from '../services/errorReporter';

function usePWAMetaTags() {
  useEffect(() => {
    if (Platform.OS !== 'web') return;
    if (typeof window === 'undefined') return;
    
    const path = window.location.pathname;
    const isCS = path.includes('cs-login') || path.includes('/cs/');
    const head = document.head;

    // Calendar Systems PWA branding override
    if (isCS) {
      localStorage.setItem('pwa_brand', 'calendar-systems');
      const metaTitle = head.querySelector('meta[name="apple-mobile-web-app-title"]');
      if (metaTitle) metaTitle.setAttribute('content', 'Calendar Systems');
      const metaTheme = head.querySelector('meta[name="theme-color"]');
      if (metaTheme) metaTheme.setAttribute('content', '#FFFFFF');
      const linkManifest = head.querySelector('link[rel="manifest"]');
      if (linkManifest) linkManifest.setAttribute('href', '/cs-manifest.json');
      const linkIcon = head.querySelector('link[rel="apple-touch-icon"]');
      if (linkIcon) linkIcon.setAttribute('href', '/cs-apple-touch-icon.png');
      document.title = 'Calendar Systems';
      return; // Skip default branding
    }

    localStorage.removeItem('pwa_brand');
    
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
          -webkit-text-fill-color: currentColor !important;
          caret-color: currentColor !important;
          transition: background-color 9999s ease-in-out 0s, -webkit-box-shadow 9999s ease-in-out 0s;
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
  const mode = useThemeStore((state) => state.mode);
  const user = useAuthStore((state) => state.user);
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const segments = useSegments();
  const [mounted, setMounted] = useState(false);

  // Sync theme mode to data-theme on <html> so CSS can target dark/light autofill colors
  // Also re-applies whenever segments change (e.g. after returning from login page which forced 'light')
  useEffect(() => {
    if (Platform.OS === 'web' && typeof document !== 'undefined') {
      document.documentElement.setAttribute('data-theme', mode);
    }
  }, [mode, segments]);
  
  // Hide Jessi on auth/public/customer-facing screens
  // These are ALL routes where a customer/public visitor could land
  const publicRoutes = ['auth', 'index', 'onboarding', 'p', 'card', 'congrats', 'opt-in', 'review', 'showcase', 'l', 'birthday', 'timeline', 'imos', 'import-guide', 'cs-login'];
  const isPublicScreen = !segments.length || publicRoutes.includes(segments[0]);
  // Double-check with pathname for routes that sometimes resolve differently
  const pathname = segments.join('/');
  const isPublicPath = pathname.startsWith('p/') || pathname.startsWith('congrats/') || pathname.startsWith('card/') || pathname === 'import-guide';
  const showJessi = isAuthenticated && !!user?._id && !isPublicScreen && !isPublicPath;
  
  usePWAMetaTags();
  
  useEffect(() => {
    loadAuth();
    loadTheme();
    setMounted(true);
    initGlobalErrorHandlers();
    
    // Re-check auth when PWA comes back from background (iOS aggressively kills JS context)
    if (Platform.OS === 'web') {
      const handleVisibilityChange = () => {
        if (document.visibilityState === 'visible') {
          // Only run loadAuth if we're NOT already authenticated in-memory.
          // If we are authenticated, iOS may have cleared storage but the JS context
          // survived — loadAuth handles this by re-persisting from in-memory state.
          // This avoids a flash of "loading" that can trigger the login redirect.
          const { isAuthenticated: alreadyAuth } = useAuthStore.getState();
          if (!alreadyAuth) {
            loadAuth();
          } else {
            // Already authenticated in memory — silently re-persist storage in background
            loadAuth();
          }
        }
      };
      document.addEventListener('visibilitychange', handleVisibilityChange);
      return () => document.removeEventListener('visibilitychange', handleVisibilityChange);
    }
  }, []);
  
  // Use theme background color once mounted, SSR-safe default that matches light theme
  const bgColor = mounted ? colors.bg : '#F2F2F7';
  
  // Don't render app content until client-side mounted — prevents #418 hydration errors
  // SSR output is just a blank shell; client renders everything fresh after mount
  if (!mounted) {
    return (
      <View style={{ flex: 1, backgroundColor: '#F2F2F7' }} />
    );
  }
  
  return (
    <ErrorBoundary>
      <GestureHandlerRootView style={{ flex: 1, backgroundColor: bgColor }}>
        <SafeAreaProvider>
          <ToastProvider>
            <View style={{ flex: 1, paddingTop: showJessi ? JESSI_BAR_HEIGHT : 0 }}>
              <Stack screenOptions={{ headerShown: false, animation: 'none' }}>
                <Stack.Screen name="index" options={{ animation: 'none' }} />
                <Stack.Screen name="auth/login" options={{ animation: 'none' }} />
                <Stack.Screen name="cs-login" options={{ animation: 'none' }} />
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
            </View>
            {showJessi && <JessieFloatingChat />}
          </ToastProvider>
        </SafeAreaProvider>
      </GestureHandlerRootView>
    </ErrorBoundary>
  );
}