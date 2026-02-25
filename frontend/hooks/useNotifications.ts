import { useState, useEffect, useCallback, useRef } from 'react';
import { useAuthStore } from '../store/authStore';
import api from '../services/api';

export interface AppNotification {
  id: string;
  type: string;
  title: string;
  message?: string;
  body?: string;
  user_id?: string;
  conversation_id?: string;
  contact_id?: string;
  contact_name?: string;
  contact_phone?: string;
  contact_email?: string;
  lead_source_name?: string;
  channel_id?: string;
  read: boolean;
  created_at: string;
}

interface UseNotificationsResult {
  notifications: AppNotification[];
  unreadCount: number;
  loading: boolean;
  refreshNotifications: () => Promise<void>;
  markAsRead: (id: string) => Promise<void>;
  markAllRead: () => Promise<void>;
  clearAll: () => Promise<void>;
}

export function useNotifications(): UseNotificationsResult {
  const { user } = useAuthStore();
  const [notifications, setNotifications] = useState<AppNotification[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading] = useState(false);

  const fetchNotifications = useCallback(async () => {
    if (!user?._id) return;
    try {
      const res = await api.get(`/notifications/?user_id=${user._id}&limit=50`);
      const data = res.data;
      if (data.success) {
        setNotifications(data.notifications || []);
        setUnreadCount(data.unread_count ?? (data.notifications || []).filter((n: any) => !n.read).length);
      }
    } catch (e) {
      // Silent fail
    }
  }, [user?._id]);

  const fetchUnreadCount = useCallback(async () => {
    if (!user?._id) return;
    try {
      const res = await api.get(`/notifications/unread-count?user_id=${user._id}`);
      setUnreadCount(res.data.count || 0);
    } catch (e) {
      // Silent fail
    }
  }, [user?._id]);

  const refreshNotifications = useCallback(async () => {
    setLoading(true);
    await fetchNotifications();
    setLoading(false);
  }, [fetchNotifications]);

  const markAsRead = useCallback(async (id: string) => {
    try {
      await api.post(`/notifications/${id}/read`);
      setNotifications(prev => prev.map(n => n.id === id ? { ...n, read: true } : n));
      setUnreadCount(prev => Math.max(0, prev - 1));
    } catch (e) { /* silent */ }
  }, []);

  const markAllRead = useCallback(async () => {
    if (!user?._id) return;
    try {
      await api.post(`/notifications/mark-all-read?user_id=${user._id}`);
      setNotifications(prev => prev.map(n => ({ ...n, read: true })));
      setUnreadCount(0);
    } catch (e) { /* silent */ }
  }, [user?._id]);

  const clearAll = useCallback(async () => {
    if (!user?._id) return;
    try {
      await api.delete(`/notifications/clear-all?user_id=${user._id}`);
      setNotifications([]);
      setUnreadCount(0);
    } catch (e) { /* silent */ }
  }, [user?._id]);

  // Initial fetch + poll every 15 seconds as fallback
  useEffect(() => {
    if (!user?._id) {
      setNotifications([]);
      setUnreadCount(0);
      return;
    }
    refreshNotifications();
    const interval = setInterval(fetchUnreadCount, 15000);
    return () => clearInterval(interval);
  }, [user?._id, refreshNotifications, fetchUnreadCount]);

  // Listen for WebSocket notification_update events to refresh
  const bumpUnread = useCallback(() => {
    fetchUnreadCount();
    fetchNotifications();
  }, [fetchUnreadCount, fetchNotifications]);

  return {
    notifications,
    unreadCount,
    loading,
    refreshNotifications,
    markAsRead,
    markAllRead,
    clearAll,
    // expose bumpUnread for websocket integration
    ...(({ bumpUnread } as any)),
  };
}

export default useNotifications;
