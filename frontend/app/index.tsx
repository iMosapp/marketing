import { useEffect, useState } from 'react';
import { View, ActivityIndicator, StyleSheet, Platform } from 'react-native';
import { Redirect } from 'expo-router';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { useAuthStore } from '../store/authStore';
import { useThemeStore } from '../store/themeStore';
import api from '../services/api';

// Push notification registration — runs once after successful auth
async function registerPushOnce(userId: string) {
  if (Platform.OS !== 'web' || typeof window === 'undefined') return;
  if (!('serviceWorker' in navigator) || !('PushManager' in window)) return;
  try {
    const reg = await navigator.serviceWorker.register('/sw-push.js');
    const existing = await reg.pushManager.getSubscription();
    if (existing) return; // Already subscribed

    const vapidKey = process.env.EXPO_PUBLIC_VAPID_KEY;
    if (!vapidKey) return;

    const padding = '='.repeat((4 - (vapidKey.length % 4)) % 4);
    const base64 = (vapidKey + padding).replace(/-/g, '+').replace(/_/g, '/');
    const raw = Uint8Array.from(atob(base64), c => c.charCodeAt(0));

    const sub = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: raw,
    });
    await api.post(`/push/subscribe/${userId}`, { subscription: sub.toJSON() });
  } catch (e) {
    console.log('Push registration skipped:', e);
  }
}

// Helper to get the right landing page based on user role
const getDefaultRoute = (_role?: string): string => {
  return '/(tabs)/home';
};

export default function Index() {
  const { isAuthenticated, isLoading, user, isImpersonating } = useAuthStore();
  const colors = useThemeStore((s) => s.colors);
  const [mounted, setMounted] = useState(false);
  const [redirectPath, setRedirectPath] = useState<string | null>(null);
  
  // Track mount state — loadAuth is already called by _layout.tsx
  useEffect(() => {
    setMounted(true);
  }, []);
  
  // Determine redirect path once loading is complete
  useEffect(() => {
    if (!mounted || isLoading) return;
    
    if (!isAuthenticated) {
      // Check if this is a Calendar Systems branded PWA
      if (Platform.OS === 'web' && typeof localStorage !== 'undefined' && localStorage.getItem('pwa_brand') === 'calendar-systems') {
        setRedirectPath('/cs-login');
      } else {
        setRedirectPath('/auth/login');
      }
    } else if (!isImpersonating && (user?.needs_onboarding || user?.status === 'pending' || !user?.onboarding_complete)) {
      // Check local backup flag before showing onboarding again
      if (user?._id) {
        AsyncStorage.getItem(`onboarding_done_${user._id}`).then(done => {
          if (done === 'true') {
            setRedirectPath(getDefaultRoute(user?.role));
            if (user?._id) registerPushOnce(user._id);
          } else {
            setRedirectPath('/onboarding/index');
          }
        }).catch(() => setRedirectPath('/onboarding/index'));
      } else {
        setRedirectPath('/onboarding/index');
      }
    } else {
      setRedirectPath(getDefaultRoute(user?.role));
      if (user?._id) registerPushOnce(user._id);
    }
  }, [mounted, isLoading, isAuthenticated, user]);
  
  // Use Redirect component for cleaner navigation
  if (redirectPath) {
    return <Redirect href={redirectPath as any} />;
  }
  
  return (
    <View style={[styles.container, { backgroundColor: colors.bg }]}>
      <ActivityIndicator size="large" color="#007AFF" />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
});