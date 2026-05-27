/**
 * usePushNotifications — manages web push permission and subscription state.
 * 
 * Usage:
 *   const { status, enable, isSupported } = usePushNotifications();
 *   status: 'default' | 'granted' | 'denied' | 'unsupported'
 *   enable(): requests permission + subscribes to push
 */
import { useState, useEffect, useCallback } from 'react';
import { Platform } from 'react-native';
import api from '../services/api';
import { useAuthStore } from '../store/authStore';

// Push permission states
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

  const isSupported =
    Platform.OS === 'web' &&
    typeof window !== 'undefined' &&
    'serviceWorker' in navigator &&
    'PushManager' in window &&
    'Notification' in window;

  // Read current permission on mount
  useEffect(() => {
    if (!isSupported) {
      setStatus('unsupported');
      return;
    }
    const perm = (window as any).Notification?.permission;
    if (perm === 'granted') setStatus('granted');
    else if (perm === 'denied') setStatus('denied');
    else setStatus('default');
  }, [isSupported]);

  const enable = useCallback(async (): Promise<boolean> => {
    if (!isSupported || !user?._id || !VAPID_KEY) return false;
    setSubscribing(true);
    try {
      // 1. Request browser permission
      const permission = await (window as any).Notification.requestPermission();
      if (permission !== 'granted') {
        setStatus('denied');
        return false;
      }
      setStatus('granted');

      // 2. Register push service worker
      const reg = await navigator.serviceWorker.register('/sw-push.js');
      await navigator.serviceWorker.ready;

      // 3. Check for existing subscription
      let sub = await reg.pushManager.getSubscription();
      if (!sub) {
        sub = await reg.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: urlBase64ToUint8Array(VAPID_KEY),
        });
      }

      // 4. Send to backend
      await api.post(`/push/subscribe/${user._id}`, { subscription: sub.toJSON() });
      return true;
    } catch (e) {
      console.warn('[Push] Enable failed:', e);
      return false;
    } finally {
      setSubscribing(false);
    }
  }, [isSupported, user?._id]);

  const disable = useCallback(async (): Promise<void> => {
    if (!isSupported || !user?._id) return;
    try {
      const reg = await navigator.serviceWorker.getRegistration('/sw-push.js');
      if (!reg) return;
      const sub = await reg.pushManager.getSubscription();
      if (sub) {
        await api.delete(`/push/unsubscribe/${user._id}`, { data: { endpoint: sub.endpoint } });
        await sub.unsubscribe();
      }
      setStatus('default');
    } catch (e) {
      console.warn('[Push] Disable failed:', e);
    }
  }, [isSupported, user?._id]);

  return { status, enable, disable, subscribing, isSupported };
}
