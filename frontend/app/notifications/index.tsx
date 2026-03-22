import React, { useState, useCallback, useEffect } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  ScrollView,
  StyleSheet,
  ActivityIndicator,
  RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useAuthStore } from '../../store/authStore';
import api from '../../services/api';

import { useThemeStore } from '../../store/themeStore';
const CATEGORIES = [
  { key: 'all', label: 'All', icon: 'apps' },
  { key: 'engagement', label: 'Engagement', icon: 'flame' },
  { key: 'leads', label: 'Leads', icon: 'person-add' },
  { key: 'tasks', label: 'Tasks', icon: 'checkbox' },
  { key: 'messages', label: 'Messages', icon: 'chatbubble' },
  { key: 'campaigns', label: 'Campaigns', icon: 'megaphone' },
  { key: 'flags', label: 'Flagged', icon: 'flag' },
  { key: 'activity', label: 'Activity', icon: 'pulse' },
];

function getNotifIcon(type: string): string {
  const map: Record<string, string> = {
    new_lead: 'person-add', lead_assigned: 'person-add', jump_ball: 'flash',
    task_overdue: 'alert-circle', task_due_soon: 'time',
    unread_message: 'chatbubble', flagged: 'flag',
    link_click: 'open', review_submitted: 'star', new_contact: 'person-add',
    digital_card_sent: 'card', review_request_sent: 'star-half',
    congrats_card_sent: 'gift', email_sent: 'mail', sms_sent: 'chatbox',
    badge_earned: 'trophy',
    campaign_send: 'megaphone',
    engagement_signal: 'flame',
  };
  return map[type] || 'notifications';
}

function getNotifColor(type: string): string {
  const map: Record<string, string> = {
    new_lead: '#007AFF', lead_assigned: '#007AFF', jump_ball: '#FF9500',
    task_overdue: '#FF3B30', task_due_soon: '#FF9500',
    unread_message: '#007AFF', flagged: '#FF9500',
    link_click: '#5856D6', review_submitted: '#FFD60A',
    email_sent: '#30D158', sms_sent: '#34C759', badge_earned: '#FFD60A',
    digital_card_sent: '#5856D6', review_request_sent: '#FFD60A',
    congrats_card_sent: '#FF2D55',
    engagement_signal: '#FF3B30',
    campaign_send: '#FF9500',
  };
  return map[type] || '#8E8E93';
}

function formatTime(isoString: string) {
  try {
    const d = new Date(isoString);
    const now = new Date();
    const diff = now.getTime() - d.getTime();
    if (diff < 60000) return 'Just now';
    if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
    if (diff < 172800000) return 'Yesterday';
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
  } catch { return ''; }
}

export default function NotificationsPage() {
  const { colors } = useThemeStore();
  const styles = getStyles(colors);
  const router = useRouter();
  const { user } = useAuthStore();
  const [notifications, setNotifications] = useState<any[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [categoryCounts, setCategoryCounts] = useState<Record<string, number>>({});
  const [activeCategory, setActiveCategory] = useState('all');
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchNotifications = useCallback(async (cat: string = 'all') => {
    if (!user?._id) return;
    try {
      const res = await api.get(`/notification-center/${user._id}?category=${cat}&limit=100`);
      if (res.data.success) {
        setNotifications(res.data.notifications || []);
        setUnreadCount(res.data.unread_count ?? 0);
        setCategoryCounts(res.data.category_counts || {});
      }
    } catch (e) {
      console.error('Failed to fetch notifications:', e);
    }
  }, [user?._id]);

  useEffect(() => {
    if (!user?._id) return;
    setLoading(true);
    fetchNotifications(activeCategory).finally(() => setLoading(false));
  }, [activeCategory, user?._id]);

  const onRefresh = async () => {
    setRefreshing(true);
    await fetchNotifications();
    setRefreshing(false);
  };

  const handleCategoryChange = (cat: string) => {
    setActiveCategory(cat);
    fetchNotifications(cat);
  };

  const markAsRead = async (id: string) => {
    if (!user?._id) return;
    try {
      await api.post(`/notification-center/${user._id}/read`, { ids: [id] });
      setNotifications(prev => prev.map(n => n.id === id ? { ...n, read: true } : n));
      setUnreadCount(prev => Math.max(0, prev - 1));
    } catch { /* silent */ }
  };

  const markAllRead = async () => {
    if (!user?._id) return;
    try {
      await api.post(`/notification-center/${user._id}/read-all`);
      setNotifications(prev => prev.map(n => ({ ...n, read: true })));
      setUnreadCount(0);
    } catch { /* silent */ }
  };

  const handleNotifPress = (n: any) => {
    markAsRead(n.id);
    if (n.link) {
      router.push(n.link as any);
    }
  };

  const totalCount = Object.values(categoryCounts).reduce((s: number, v: any) => s + v, 0);

  return (
    <SafeAreaView style={styles.container} data-testid="notifications-page">
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backBtn} data-testid="notif-back-btn">
          <Ionicons name="chevron-back" size={24} color={colors.text} />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={styles.headerTitle}>Notifications</Text>
          {unreadCount > 0 && (
            <Text style={styles.headerSub}>{unreadCount} unread</Text>
          )}
        </View>
        {unreadCount > 0 && (
          <TouchableOpacity onPress={markAllRead} style={styles.markAllBtn} data-testid="notif-mark-all-read">
            <Ionicons name="checkmark-done" size={18} color="#007AFF" />
            <Text style={styles.markAllText}>Read All</Text>
          </TouchableOpacity>
        )}
      </View>

      {/* Category Tabs */}
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.tabBar}>
        {CATEGORIES.map(cat => {
          const isActive = activeCategory === cat.key;
          const count = cat.key === 'all' ? totalCount : (categoryCounts[cat.key] || 0);
          return (
            <TouchableOpacity
              key={cat.key}
              style={[styles.tab, isActive && styles.tabActive]}
              onPress={() => handleCategoryChange(cat.key)}
              data-testid={`notif-tab-${cat.key}`}
            >
              <Ionicons name={cat.icon as any} size={15} color={isActive ? '#FFF' : colors.textSecondary} />
              <Text style={[styles.tabText, isActive && styles.tabTextActive]}>
                {cat.label}
              </Text>
              {count > 0 && (
                <View style={[styles.tabBadge, isActive && styles.tabBadgeActive]}>
                  <Text style={[styles.tabBadgeText, isActive && { color: '#007AFF' }]}>{count}</Text>
                </View>
              )}
            </TouchableOpacity>
          );
        })}
      </ScrollView>

      {/* Notification List */}
      {loading ? (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#007AFF" />
        </View>
      ) : (
        <ScrollView
          style={styles.list}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#007AFF" />}
        >
          {notifications.length === 0 ? (
            <View style={styles.emptyContainer}>
              <View style={styles.emptyIcon}>
                <Ionicons name="checkmark-circle" size={48} color={colors.borderLight} />
              </View>
              <Text style={styles.emptyTitle}>All caught up!</Text>
              <Text style={styles.emptySubtitle}>
                {activeCategory === 'all'
                  ? "You have no notifications right now."
                  : `No ${activeCategory} notifications.`}
              </Text>
            </View>
          ) : (
            notifications.map((n: any) => (
              <TouchableOpacity
                key={n.id}
                style={[styles.notifItem, !n.read && styles.notifItemUnread]}
                onPress={() => handleNotifPress(n)}
                data-testid={`notif-item-${n.id}`}
              >
                <View style={[styles.notifIcon, { backgroundColor: getNotifColor(n.type) + '18' }]}>
                  <Ionicons name={getNotifIcon(n.type) as any} size={18} color={getNotifColor(n.type)} />
                </View>
                <View style={styles.notifContent}>
                  <View style={styles.notifTopRow}>
                    <Text style={[styles.notifTitle, !n.read && { color: colors.text }]} numberOfLines={1}>
                      {n.title}
                    </Text>
                    {!n.read && <View style={styles.unreadDot} />}
                  </View>
                  {(n.body || n.contact_name) && (
                    <Text style={styles.notifBody} numberOfLines={2}>
                      {n.body || n.contact_name}
                    </Text>
                  )}
                  <View style={styles.notifMeta}>
                    <Text style={styles.notifTime}>{formatTime(n.timestamp)}</Text>
                    <View style={[styles.notifCatBadge, { backgroundColor: getNotifColor(n.type) + '15' }]}>
                      <Text style={[styles.notifCatBadgeText, { color: getNotifColor(n.type) }]}>
                        {(n.category || '').charAt(0).toUpperCase() + (n.category || '').slice(1)}
                      </Text>
                    </View>
                  </View>
                </View>
                <Ionicons name="chevron-forward" size={16} color={colors.borderLight} style={{ marginTop: 4 }} />
              </TouchableOpacity>
            ))
          )}
          <View style={{ height: 40 }} />
        </ScrollView>
      )}
    </SafeAreaView>
  );
}

const getStyles = (colors: any) => StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 12,
    gap: 12,
    borderBottomWidth: 1,
    borderBottomColor: colors.card,
  },
  backBtn: {
    width: 36, height: 36, borderRadius: 10,
    backgroundColor: colors.card, alignItems: 'center', justifyContent: 'center',
  },
  headerTitle: { fontSize: 21, fontWeight: '700', color: colors.text },
  headerSub: { fontSize: 14, color: colors.textSecondary, marginTop: 1 },
  markAllBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    paddingHorizontal: 12, paddingVertical: 6, borderRadius: 16,
    backgroundColor: '#007AFF15',
  },
  markAllText: { fontSize: 15, color: '#007AFF', fontWeight: '600' },
  tabBar: {
    paddingHorizontal: 12, paddingVertical: 10,
    borderBottomWidth: 1, borderBottomColor: colors.card,
    maxHeight: 52,
  },
  tab: {
    flexDirection: 'row', alignItems: 'center', gap: 5,
    paddingHorizontal: 14, paddingVertical: 7,
    borderRadius: 20, backgroundColor: colors.card,
    marginRight: 8,
  },
  tabActive: { backgroundColor: '#007AFF' },
  tabText: { fontSize: 15, color: colors.textSecondary, fontWeight: '500' },
  tabTextActive: { color: colors.text },
  tabBadge: {
    minWidth: 18, height: 18, borderRadius: 9,
    backgroundColor: colors.surface, alignItems: 'center', justifyContent: 'center',
    paddingHorizontal: 4, marginLeft: 2,
  },
  tabBadgeActive: { backgroundColor: '#FFFFFF30' },
  tabBadgeText: { fontSize: 12, fontWeight: '700', color: colors.textSecondary },
  list: { flex: 1 },
  loadingContainer: { flex: 1, justifyContent: 'center', alignItems: 'center', paddingTop: 80 },
  emptyContainer: { alignItems: 'center', paddingTop: 80, gap: 8 },
  emptyIcon: {
    width: 72, height: 72, borderRadius: 36,
    backgroundColor: colors.card, alignItems: 'center', justifyContent: 'center',
    marginBottom: 8,
  },
  emptyTitle: { fontSize: 19, fontWeight: '600', color: colors.text },
  emptySubtitle: { fontSize: 16, color: '#6E6E73', textAlign: 'center' },
  notifItem: {
    flexDirection: 'row', alignItems: 'flex-start', gap: 12,
    paddingHorizontal: 16, paddingVertical: 14,
    borderBottomWidth: 1, borderBottomColor: colors.card,
  },
  notifItemUnread: { backgroundColor: '#007AFF06' },
  notifIcon: {
    width: 38, height: 38, borderRadius: 12,
    alignItems: 'center', justifyContent: 'center', marginTop: 2,
  },
  notifContent: { flex: 1 },
  notifTopRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  notifTitle: { fontSize: 16, fontWeight: '600', color: colors.border, flex: 1 },
  unreadDot: {
    width: 8, height: 8, borderRadius: 4, backgroundColor: '#007AFF',
  },
  notifBody: { fontSize: 15, color: colors.textSecondary, lineHeight: 18, marginTop: 2 },
  notifMeta: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 4 },
  notifTime: { fontSize: 13, color: '#6E6E73' },
  notifCatBadge: {
    paddingHorizontal: 6, paddingVertical: 2, borderRadius: 4,
  },
  notifCatBadgeText: { fontSize: 12, fontWeight: '600' },
});
