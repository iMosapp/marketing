import { useState, useEffect, useCallback, useRef } from 'react';
import { Platform } from 'react-native';
import { useAuthStore } from '../../store/authStore';

const API_URL = process.env.EXPO_PUBLIC_BACKEND_URL;

interface LeadNotification {
  id: string;
  type: string;
  title: string;
  message: string;
  conversation_id: string;
  contact_id: string;
  contact_name: string;
  contact_phone: string;
  contact_email?: string;
  lead_source_name?: string;
  created_at: string;
}

interface UseNotificationsResult {
  pendingNotification: LeadNotification | null;
  unreadCount: number;
  loading: boolean;
  refreshNotifications: () => Promise<void>;
  clearPendingNotification: () => void;
}

export function useNotifications(pollInterval: number = 5000): UseNotificationsResult {
  const { user } = useAuthStore();
  const [pendingNotification, setPendingNotification] = useState<LeadNotification | null>(null);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchPendingNotification = useCallback(async () => {
    if (!user?._id) return;
    
    try {
      const response = await fetch(
        `${API_URL}/api/notifications/pending-action?user_id=${user._id}`
      );
      const data = await response.json();
      
      if (data.success && data.notification) {
        setPendingNotification(data.notification);
      }
    } catch (error) {
      console.error('Error fetching pending notification:', error);
    }
  }, [user?._id]);

  const fetchUnreadCount = useCallback(async () => {
    if (!user?._id) return;
    
    try {
      const response = await fetch(
        `${API_URL}/api/notifications/unread-count?user_id=${user._id}`
      );
      const data = await response.json();
      setUnreadCount(data.count || 0);
    } catch (error) {
      console.error('Error fetching unread count:', error);
    }
  }, [user?._id]);

  const refreshNotifications = useCallback(async () => {
    if (!user?._id) return;
    setLoading(true);
    
    try {
      await Promise.all([
        fetchPendingNotification(),
        fetchUnreadCount()
      ]);
    } finally {
      setLoading(false);
    }
  }, [user?._id, fetchPendingNotification, fetchUnreadCount]);

  const clearPendingNotification = useCallback(() => {
    setPendingNotification(null);
    fetchUnreadCount();
  }, [fetchUnreadCount]);

  // Start polling when user is logged in
  useEffect(() => {
    if (!user?._id) {
      setPendingNotification(null);
      setUnreadCount(0);
      return;
    }

    // Initial fetch
    refreshNotifications();

    // Start polling
    pollIntervalRef.current = setInterval(() => {
      fetchPendingNotification();
      fetchUnreadCount();
    }, pollInterval);

    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    };
  }, [user?._id, pollInterval, refreshNotifications, fetchPendingNotification, fetchUnreadCount]);

  return {
    pendingNotification,
    unreadCount,
    loading,
    refreshNotifications,
    clearPendingNotification,
  };
}

export default useNotifications;
