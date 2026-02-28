import { useState, useEffect, useCallback } from 'react';
import { useAuthStore } from '../store/authStore';
import api from '../services/api';

export interface AppNotification {
  id: string;
  type: string;
  category: string;
  priority: number;
  title: string;
  body?: string;
  message?: string;
  link?: string;
  contact_name?: string;
  read: boolean;
  timestamp: string;
  source?: string;
  // Legacy fields for backward compat
  user_id?: string;
  conversation_id?: string;
  contact_id?: string;
  channel_id?: string;
  created_at?: string;
}

interface UseNotificationsResult {
  notifications: AppNotification[];
  unreadCount: number;
  loading: boolean;
  categoryFilter: string;
  setCategoryFilter: (cat: string) => void;
  categoryCounts: Record<string, number>;
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
  const [categoryFilter, setCategoryFilter] = useState('all');
  const [categoryCounts, setCategoryCounts] = useState<Record<string, number>>({});

  const fetchNotifications = useCallback(async () => {
    if (!user?._id) return;
    try {
      const res = await api.get(`/notification-center/${user._id}?category=${categoryFilter}`);
      const data = res.data;
      if (data.success) {
        setNotifications(data.notifications || []);
        setUnreadCount(data.unread_count ?? 0);
        setCategoryCounts(data.category_counts || {});
      }
    } catch {
      // Silent fail
    }
  }, [user?._id, categoryFilter]);

  const fetchUnreadCount = useCallback(async () => {
    if (!user?._id) return;
    try {
      const res = await api.get(`/notification-center/${user._id}/unread-count`);
      setUnreadCount(res.data.count || 0);
    } catch {
      // Silent fail
    }
  }, [user?._id]);

  const refreshNotifications = useCallback(async () => {
    setLoading(true);
    await fetchNotifications();
    setLoading(false);
  }, [fetchNotifications]);

  const markAsRead = useCallback(async (id: string) => {
    if (!user?._id) return;
    try {
      await api.post(`/notification-center/${user._id}/read`, { ids: [id] });
      setNotifications(prev => prev.map(n => n.id === id ? { ...n, read: true } : n));
      setUnreadCount(prev => Math.max(0, prev - 1));
    } catch { /* silent */ }
  }, [user?._id]);

  const markAllRead = useCallback(async () => {
    if (!user?._id) return;
    try {
      await api.post(`/notification-center/${user._id}/read-all`);
      setNotifications(prev => prev.map(n => ({ ...n, read: true })));
      setUnreadCount(0);
    } catch { /* silent */ }
  }, [user?._id]);

  const clearAll = useCallback(async () => {
    if (!user?._id) return;
    try {
      await api.delete(`/notifications/clear-all?user_id=${user._id}`);
      setNotifications([]);
      setUnreadCount(0);
    } catch { /* silent */ }
  }, [user?._id]);

  // Initial fetch + poll every 15 seconds
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

  return {
    notifications,
    unreadCount,
    loading,
    categoryFilter,
    setCategoryFilter,
    categoryCounts,
    refreshNotifications,
    markAsRead,
    markAllRead,
    clearAll,
  };
}

export default useNotifications;
