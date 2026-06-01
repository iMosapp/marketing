/**
 * usePushNotifications — manages push notification permission for both web and native iOS.
 *
 * Web:    Uses browser Notification API + VAPID service worker
 * Native: Uses expo-notifications to request iOS permission + register Expo push token
 */
import { useState, useEffect, useCallback } from 'react';
import { Platform, Linking } from 'react-native';
import api from '../services/api';
import { useAuthStore } from '../store/authStore';

type PushPermissionStatus = 'default' | 'granted' | 'denied' | 'unsupported';

const VAPID_KEY = process.env.EXPO_PUBLIC_VAPID_KEY || '';

function urlBase64ToUint8Array(base64String: string): Uint8Array {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
  const rawData = atob(base64);
  return Uint8Array.from([...rawData].map(c => c.charCodeAt(0)));
}

export function usePushNotifications() {
  const user = useAuthStore(s => s.user);
  const [status, setStatus] = useState<PushPermissionStatus>('default');
  const [subscribing, setSubscribing] = useState(false);

  const isNative = Platform.OS === 'ios' || Platform.OS === 'android';
  const isSupported = isNative || (
    typeof window !== 'undefined' &&
    'serviceWorker' in navigator &&
    'PushManager' in window &&
    'Notification' in window
  );

  // Read current permission on mount
  useEffect(() => {
    if (!isSupported) { setStatus('unsupported'); return; }

    if (isNative) {
      // Check expo-notifications permission
      (async () => {
        try {
          const Notifications = await import('expo-notifications');
          const { status: perm } = await Notifications.getPermissionsAsync();
          if (perm === 'granted') setStatus('granted');
          else if (perm === 'denied') setStatus('denied');
          else setStatus('default');
        } catch { setStatus('default'); }
      })();
    } else {
      const perm = (window as any).Notification?.permission;
      if (perm === 'granted') setStatus('granted');
      else if (perm === 'denied') setStatus('denied');
      else setStatus('default');
    }
  }, [isNative, isSupported]);

  const enable = useCallback(async (): Promise<boolean> => {
    if (!isSupported || !user?._id) return false;
    setSubscribing(true);
    try {
      if (isNative) {
        // ── Native iOS/Android ──────────────────────────────────────────────
        const Notifications = await import('expo-notifications');
        const { status: existing } = await Notifications.getPermissionsAsync();
        let finalStatus = existing;

        if (existing !== 'granted') {
          const { status: asked } = await Notifications.requestPermissionsAsync();
          finalStatus = asked;
        }

        if (finalStatus === 'denied') {
          setStatus('denied');
          // User previously denied — direct them to Settings
          Linking.openSettings?.();
          return false;
        }

        if (finalStatus !== 'granted') {
          setStatus('default');
          return false;
        }

        setStatus('granted');
        // Register Expo push token
        try {
          const tokenData = await Notifications.getExpoPushTokenAsync();
          if (tokenData?.data) {
            await api.post(`/push/subscribe-native/${user._id}`, {
              expo_push_token: tokenData.data,
              platform: Platform.OS,
            });
          }
        } catch (tokenErr) {
          console.warn('[Push] Token registration failed:', tokenErr);
        }
        return true;

      } else {
        // ── Web ─────────────────────────────────────────────────────────────
        if (!VAPID_KEY) return false;
        const permission = await (window as any).Notification.requestPermission();
        if (permission !== 'granted') { setStatus('denied'); return false; }
        setStatus('granted');

        const reg = await navigator.serviceWorker.register('/sw-push.js');
        await navigator.serviceWorker.ready;
        let sub = await reg.pushManager.getSubscription();
        if (!sub) {
          sub = await reg.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: urlBase64ToUint8Array(VAPID_KEY),
          });
        }
        await api.post(`/push/subscribe/${user._id}`, { subscription: sub.toJSON() });
        return true;
      }
    } catch (e) {
      console.warn('[Push] Enable failed:', e);
      return false;
    } finally {
      setSubscribing(false);
    }
  }, [isNative, isSupported, user?._id]);

  const disable = useCallback(async (): Promise<void> => {
    if (!user?._id) return;
    try {
      if (isNative) {
        // Can't revoke iOS permission programmatically — open Settings
        setStatus('default');
        Linking.openSettings?.();
      } else {
        const reg = await navigator.serviceWorker.getRegistration('/sw-push.js');
        if (!reg) return;
        const sub = await reg.pushManager.getSubscription();
        if (sub) {
          await api.delete(`/push/unsubscribe/${user._id}`, { data: { endpoint: sub.endpoint } });
          await sub.unsubscribe();
        }
        setStatus('default');
      }
    } catch (e) {
      console.warn('[Push] Disable failed:', e);
    }
  }, [isNative, user?._id]);

  return { status, enable, disable, subscribing, isSupported };
}
