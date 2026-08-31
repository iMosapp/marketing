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

const GOLD = '#C9A962';
const RED = '#FF3B30';

const tid = (id: string): any => ({ testID: id, dataSet: { testid: id } });

const CATEGORIES = [
  { key: 'all', label: 'All', icon: 'apps', color: GOLD },
  { key: 'urgent', label: 'Needs You', icon: 'alert-circle', color: RED },
  { key: 'leads', label: 'Leads', icon: 'person-add', color: GOLD },
  { key: 'replies', label: 'Replies', icon: 'chatbubble', color: GOLD },
  { key: 'appts', label: 'Appts', icon: 'calendar', color: GOLD },
];

const TYPE_META: Record<string, { icon: string; color: string }> = {
  you_are_needed: { icon: 'alert-circle', color: RED },
  slow_lead: { icon: 'time', color: RED },
  jump_ball: { icon: 'flash', color: '#FF9500' },
  new_lead: { icon: 'person-add', color: GOLD },
  lead_assigned: { icon: 'person-add', color: GOLD },
  new_demo_request: { icon: 'person-add', color: GOLD },
  engagement_signal: { icon: 'flame', color: '#FF9500' },
  keyword_alert: { icon: 'key', color: GOLD },
  customer_reply: { icon: 'chatbubble', color: GOLD },
  customer_reply_ai_handling: { icon: 'sparkles', color: GOLD },
  unread_message: { icon: 'chatbubble', color: GOLD },
  appointment_extracted: { icon: 'calendar', color: GOLD },
  task_reminder: { icon: 'alarm', color: GOLD },
  task_overdue: { icon: 'alert-circle', color: RED },
  task_due_soon: { icon: 'time', color: '#FF9500' },
  // activity types (muted)
  flagged: { icon: 'flag', color: '#FF9500' },
  link_click: { icon: 'open', color: '#8E8E93' },
  review_submitted: { icon: 'star', color: '#FFD60A' },
  new_review: { icon: 'star', color: '#FFD60A' },
  new_contact: { icon: 'person-add', color: '#8E8E93' },
  digital_card_sent: { icon: 'card', color: '#8E8E93' },
  review_request_sent: { icon: 'star-half', color: '#8E8E93' },
  congrats_card_sent: { icon: 'gift', color: '#8E8E93' },
  email_sent: { icon: 'mail', color: '#8E8E93' },
  sms_sent: { icon: 'chatbox', color: '#8E8E93' },
  campaign_send: { icon: 'megaphone', color: '#8E8E93' },
  date_trigger: { icon: 'calendar', color: '#8E8E93' },
  milestone: { icon: 'trophy', color: '#FFD60A' },
  ai_outreach: { icon: 'sparkles', color: '#8E8E93' },
  call_recorded: { icon: 'mic', color: '#8E8E93' },
  photo_reminder: { icon: 'image', color: '#8E8E93' },
};

const metaFor = (type: string) => TYPE_META[type] || { icon: 'notifications', color: '#8E8E93' };

function formatTime(isoString: string) {
  try {
    const d = new Date(isoString);
    const now = new Date();
    const diff = now.getTime() - d.getTime();
    if (diff < 60000) return 'Just now';
    if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
    return d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
  } catch { return ''; }
}

function dayLabel(isoString: string): string {
  try {
    const d = new Date(isoString);
    const today = new Date();
    const sameDay = (a: Date, b: Date) =>
      a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
    if (sameDay(d, today)) return 'TODAY';
    const yest = new Date(today); yest.setDate(today.getDate() - 1);
    if (sameDay(d, yest)) return 'YESTERDAY';
    return d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' }).toUpperCase().replace(',', ' ·');
  } catch { return ''; }
}

export default function AlertsPage() {
  const { colors } = useThemeStore();
  const styles = getStyles(colors);
  const router = useRouter();
  const { user } = useAuthStore();
  const [feed, setFeed] = useState<'for_you' | 'activity'>('for_you');
  const [notifications, setNotifications] = useState<any[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [categoryCounts, setCategoryCounts] = useState<Record<string, number>>({});
  const [activityCount, setActivityCount] = useState(0);
  const [activeCategory, setActiveCategory] = useState('all');
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchNotifications = useCallback(async (f: string, cat: string) => {
    if (!user?._id) return;
    try {
      const res = await api.get(`/notification-center/${user._id}?feed=${f}&category=${cat}&limit=100`);
      if (res.data.success) {
        setNotifications(res.data.notifications || []);
        setUnreadCount(res.data.unread_count ?? 0);
        setCategoryCounts(res.data.category_counts || {});
        setActivityCount(res.data.activity_count ?? 0);
      }
    } catch { /* silent */ }
  }, [user?._id]);

  useEffect(() => {
    if (!user?._id) return;
    setLoading(true);
    fetchNotifications(feed, activeCategory).finally(() => setLoading(false));
  }, [feed, activeCategory, user?._id, fetchNotifications]);

  const onRefresh = async () => {
    setRefreshing(true);
    await fetchNotifications(feed, activeCategory);
    setRefreshing(false);
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
    } else if (n.contact_id) {
      router.push(`/contact/${n.contact_id}` as any);
    }
  };

  const totalForYou = Object.values(categoryCounts).reduce((s: number, v: any) => s + v, 0);

  // group rows by day
  const grouped: { label: string; items: any[] }[] = [];
  notifications.forEach((n: any) => {
    const label = dayLabel(n.timestamp);
    const g = grouped.find(x => x.label === label);
    if (g) g.items.push(n);
    else grouped.push({ label, items: [n] });
  });

  return (
    <SafeAreaView style={styles.container} {...tid('notifications-page')}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backBtn} {...tid('notif-back-btn')}>
          <Ionicons name="chevron-back" size={24} color={GOLD} />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text maxFontSizeMultiplier={1.0} style={styles.headerTitle}>Alerts</Text>
          {unreadCount > 0 && (
            <Text maxFontSizeMultiplier={1.0} style={styles.headerSub}>{unreadCount} unread</Text>
          )}
        </View>
        {unreadCount > 0 && (
          <TouchableOpacity onPress={markAllRead} style={styles.markAllBtn} {...tid('notif-mark-all-read')}>
            <Ionicons name="checkmark-done" size={15} color="#000" />
            <Text maxFontSizeMultiplier={1.0} style={styles.markAllText}>Read All</Text>
          </TouchableOpacity>
        )}
      </View>

      {/* For You / Activity segmented control */}
      <View style={styles.segmentWrap}>
        <TouchableOpacity
          style={[styles.segment, feed === 'for_you' && styles.segmentActive]}
          onPress={() => setFeed('for_you')}
          {...tid('notif-feed-foryou')}
        >
          <Text maxFontSizeMultiplier={1.0} style={[styles.segmentText, feed === 'for_you' && styles.segmentTextActive]}>
            For You{totalForYou > 0 ? ` · ${totalForYou}` : ''}
          </Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.segment, feed === 'activity' && styles.segmentActive]}
          onPress={() => setFeed('activity')}
          {...tid('notif-feed-activity')}
        >
          <Text maxFontSizeMultiplier={1.0} style={[styles.segmentText, feed === 'activity' && styles.segmentTextActive]}>
            Activity{activityCount > 0 ? ` · ${activityCount}` : ''}
          </Text>
        </TouchableOpacity>
      </View>

      {/* Smart filter cards — For You only */}
      {feed === 'for_you' && (
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          style={{ flexGrow: 0, flexShrink: 0 }}
          contentContainerStyle={{ paddingHorizontal: 16, gap: 8, paddingVertical: 10 }}
        >
          {CATEGORIES.map(cat => {
            const isActive = activeCategory === cat.key;
            const count = cat.key === 'all' ? totalForYou : (categoryCounts[cat.key] || 0);
            return (
              <TouchableOpacity
                key={cat.key}
                style={[styles.smartCard, isActive && styles.smartCardActive]}
                onPress={() => setActiveCategory(cat.key)}
                {...tid(`notif-tab-${cat.key}`)}
              >
                <View style={[styles.smartIcon, { backgroundColor: cat.color + '22' }]}>
                  <Ionicons name={cat.icon as any} size={13} color={cat.color} />
                </View>
                <View>
                  <Text maxFontSizeMultiplier={1.0} style={styles.smartCount}>{count}</Text>
                  <Text maxFontSizeMultiplier={1.0} style={styles.smartLabel}>{cat.label}</Text>
                </View>
              </TouchableOpacity>
            );
          })}
        </ScrollView>
      )}

      {/* List */}
      {loading ? (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={GOLD} />
        </View>
      ) : (
        <ScrollView
          style={styles.list}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={GOLD} />}
        >
          {notifications.length === 0 ? (
            <View style={styles.emptyContainer} {...tid('notif-empty')}>
              <View style={styles.emptyIcon}>
                <Ionicons name="checkmark-circle" size={44} color={GOLD} />
              </View>
              <Text maxFontSizeMultiplier={1.0} style={styles.emptyTitle}>All caught up!</Text>
              <Text maxFontSizeMultiplier={1.0} style={styles.emptySubtitle}>
                {feed === 'activity'
                  ? 'No recent activity.'
                  : activeCategory === 'all'
                    ? 'Nothing needs you right now.'
                    : `No ${CATEGORIES.find(c => c.key === activeCategory)?.label.toLowerCase()} alerts.`}
              </Text>
            </View>
          ) : (
            grouped.map(group => (
              <View key={group.label}>
                <Text maxFontSizeMultiplier={1.0} style={styles.dayHeader}>{group.label}</Text>
                {group.items.map((n: any) => {
                  const meta = metaFor(n.type);
                  return (
                    <TouchableOpacity
                      key={n.id}
                      style={[styles.notifItem, !n.read && styles.notifItemUnread]}
                      onPress={() => handleNotifPress(n)}
                      activeOpacity={0.7}
                      {...tid(`notif-item-${n.id}`)}
                    >
                      <View style={[styles.notifIcon, { backgroundColor: meta.color + '20' }]}>
                        <Ionicons name={meta.icon as any} size={17} color={meta.color} />
                      </View>
                      <View style={{ flex: 1 }}>
                        <View style={styles.notifTopRow}>
                          {!n.read && <View style={styles.unreadDot} />}
                          <Text maxFontSizeMultiplier={1.0} style={styles.notifTitle} numberOfLines={1}>
                            {n.title}
                          </Text>
                          <Text maxFontSizeMultiplier={1.0} style={styles.notifTime}>{formatTime(n.timestamp)}</Text>
                        </View>
                        {(n.body || n.contact_name) ? (
                          <Text maxFontSizeMultiplier={1.0} style={styles.notifBody} numberOfLines={2}>
                            {n.body || n.contact_name}
                          </Text>
                        ) : null}
                      </View>
                    </TouchableOpacity>
                  );
                })}
              </View>
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
  },
  backBtn: {
    width: 36, height: 36, borderRadius: 12,
    backgroundColor: colors.card, alignItems: 'center', justifyContent: 'center',
  },
  headerTitle: { fontSize: 22, fontWeight: '800', color: colors.text },
  headerSub: { fontSize: 13, color: colors.textSecondary, marginTop: 1 },
  markAllBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    paddingHorizontal: 12, paddingVertical: 7, borderRadius: 16,
    backgroundColor: GOLD,
  },
  markAllText: { fontSize: 13, color: '#000', fontWeight: '700' },
  segmentWrap: {
    flexDirection: 'row', marginHorizontal: 16, backgroundColor: colors.card,
    borderRadius: 12, padding: 3, gap: 3,
  },
  segment: {
    flex: 1, paddingVertical: 8, borderRadius: 10, alignItems: 'center',
  },
  segmentActive: { backgroundColor: GOLD },
  segmentText: { fontSize: 13.5, fontWeight: '700', color: colors.textSecondary },
  segmentTextActive: { color: '#000' },
  smartCard: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    backgroundColor: colors.card, borderRadius: 14,
    paddingHorizontal: 10, paddingVertical: 7,
    borderWidth: 1, borderColor: 'transparent',
  },
  smartCardActive: { borderColor: GOLD, backgroundColor: GOLD + '14' },
  smartIcon: {
    width: 26, height: 26, borderRadius: 13,
    alignItems: 'center', justifyContent: 'center',
  },
  smartCount: { fontSize: 15, fontWeight: '800', color: colors.text, lineHeight: 17 },
  smartLabel: { fontSize: 10, fontWeight: '600', color: colors.textSecondary, lineHeight: 12 },
  list: { flex: 1 },
  loadingContainer: { flex: 1, justifyContent: 'center', alignItems: 'center', paddingTop: 80 },
  emptyContainer: { alignItems: 'center', paddingTop: 70, gap: 8 },
  emptyIcon: {
    width: 72, height: 72, borderRadius: 36,
    backgroundColor: GOLD + '15', alignItems: 'center', justifyContent: 'center',
    marginBottom: 8,
  },
  emptyTitle: { fontSize: 18, fontWeight: '700', color: colors.text },
  emptySubtitle: { fontSize: 14, color: colors.textSecondary, textAlign: 'center' },
  dayHeader: {
    fontSize: 12, fontWeight: '800', color: GOLD, letterSpacing: 0.8,
    paddingHorizontal: 20, marginTop: 16, marginBottom: 6,
  },
  notifItem: {
    flexDirection: 'row', alignItems: 'flex-start', gap: 10,
    backgroundColor: colors.card, borderRadius: 16,
    marginHorizontal: 16, marginBottom: 6,
    paddingHorizontal: 12, paddingVertical: 12,
  },
  notifItemUnread: {
    borderLeftWidth: 3, borderLeftColor: GOLD,
  },
  notifIcon: {
    width: 34, height: 34, borderRadius: 11,
    alignItems: 'center', justifyContent: 'center', marginTop: 1,
  },
  notifTopRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  unreadDot: { width: 7, height: 7, borderRadius: 4, backgroundColor: GOLD },
  notifTitle: { fontSize: 15, fontWeight: '700', color: colors.text, flex: 1 },
  notifTime: { fontSize: 11.5, color: colors.textTertiary },
  notifBody: { fontSize: 13, color: colors.textSecondary, lineHeight: 17, marginTop: 2 },
});
