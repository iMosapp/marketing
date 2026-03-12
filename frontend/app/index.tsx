import { useEffect, useState } from 'react';
import { View, ActivityIndicator, StyleSheet, Platform } from 'react-native';
import { useRouter, useRootNavigationState, Redirect } from 'expo-router';
import { useAuthStore } from '../store/authStore';
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
const getDefaultRoute = (role?: string): string => {
  switch (role) {
    case 'super_admin':
    case 'org_admin':
    case 'store_manager':
      return '/(tabs)/more';
    default:
      return '/(tabs)/inbox';
  }
};

export default function Index() {
  const router = useRouter();
  const { isAuthenticated, isLoading, user, loadAuth, isImpersonating } = useAuthStore();
  const [mounted, setMounted] = useState(false);
  const [redirectPath, setRedirectPath] = useState<string | null>(null);
  
  // Track mount state and load auth
  useEffect(() => {
    setMounted(true);
    loadAuth();
  }, []);
  
  // Determine redirect path once loading is complete
  // CRITICAL: If loadAuth fails once, retry before sending to login screen.
  // iOS PWA can have slow AsyncStorage reads on cold boot after process kill.
  useEffect(() => {
    if (!mounted || isLoading) return;
    
    if (!isAuthenticated) {
      // Don't redirect to login immediately — retry once after a short delay
      // This handles iOS cold-boot race conditions where AsyncStorage is slow
      const retryTimer = setTimeout(async () => {
        await loadAuth();
        const state = useAuthStore.getState();
        if (!state.isAuthenticated) {
          setRedirectPath('/auth/login');
        }
      }, 1000);
      return () => clearTimeout(retryTimer);
    } else if (!isImpersonating && (user?.needs_onboarding || user?.status === 'pending' || !user?.onboarding_complete)) {
      setRedirectPath('/onboarding/index');
    } else {
      setRedirectPath(getDefaultRoute(user?.role));
      // Register for push notifications after successful auth
      if (user?._id) registerPushOnce(user._id);
    }
  }, [mounted, isLoading, isAuthenticated, user]);
  
  // Fallback timeout — if loadAuth hasn't resolved in 30s, something is truly wrong.
  // Try one more loadAuth and then redirect to login if still not authenticated.
  useEffect(() => {
    if (!mounted || redirectPath) return;
    
    const timer = setTimeout(() => {
      if (!redirectPath && isLoading) {
        console.warn('[Auth] loadAuth still loading after 30s, retrying once');
        loadAuth().finally(() => {
          const { isAuthenticated: authNow } = useAuthStore.getState();
          if (!authNow) {
            setRedirectPath('/auth/login');
          }
        });
      }
    }, 30000);
    
    return () => clearTimeout(timer);
  }, [mounted, redirectPath]);
  
  // Use Redirect component for cleaner navigation
  if (redirectPath) {
    return <Redirect href={redirectPath as any} />;
  }
  
  return (
    <View style={styles.container}>
      <ActivityIndicator size="large" color="#007AFF" />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#000',
    alignItems: 'center',
    justifyContent: 'center',
  },
});