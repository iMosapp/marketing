import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  View, Text, ScrollView, TouchableOpacity, StyleSheet, Image,
  ActivityIndicator, RefreshControl, Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import * as Haptics from 'expo-haptics';
import { useAuthStore } from '../../store/authStore';
import { useThemeStore } from '../../store/themeStore';
import api from '../../services/api';
import { EVENT_TYPE_LABELS, getEventLabel } from '../../utils/eventTypes';

const formatFeedTime = (ts: string) => {
  if (!ts) return '';
  const d = new Date(ts);
  const now = new Date();
  const diff = now.getTime() - d.getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'Just now';
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
};

const getDateLabel = (ts: string) => {
  if (!ts) return 'Unknown';
  const d = new Date(ts);
  const now = new Date();
  const nowDay = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const evtDay = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  const days = Math.round((nowDay.getTime() - evtDay.getTime()) / 86400000);
  if (days === 0) return 'Today';
  if (days === 1) return 'Yesterday';
  if (days < 7) return `${days} days ago`;
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
};

export default function ActivityTab() {
  const { colors } = useThemeStore();
  const { user } = useAuthStore();
  const router = useRouter();
  const userId = user?._id;

  const [feed, setFeed] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [, setTick] = useState(0); // Force re-render for timestamps

  const loadFeed = useCallback(async () => {
    if (!userId) return;
    try {
      const resp = await api.get(`/contacts/${userId}/master-feed?limit=100`);
      setFeed(resp.data.feed || []);
    } catch (e) {
      console.error('Failed to load activity feed:', e);
    } finally {
      setLoading(false);
    }
  }, [userId]);

  useEffect(() => { loadFeed(); }, [loadFeed]);

  // Auto-refresh every 30 seconds
  useEffect(() => {
    if (!userId) return;
    const interval = setInterval(() => { loadFeed(); }, 30000);
    return () => clearInterval(interval);
  }, [userId, loadFeed]);

  // Refresh timestamps every 60 seconds
  useEffect(() => {
    const interval = setInterval(() => setTick(t => t + 1), 60000);
    return () => clearInterval(interval);
  }, []);

  const onRefresh = async () => {
    setRefreshing(true);
    try { Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light); } catch {}
    await loadFeed();
    setRefreshing(false);
  };

  // Build flat list data with section headers
  const listData = React.useMemo(() => {
    const items: any[] = [];
    let lastLabel = '';
    for (const item of feed) {
      const label = getDateLabel(item.timestamp);
      if (label !== lastLabel) {
        items.push({ _type: 'header', label, count: feed.filter(f => getDateLabel(f.timestamp) === label).length });
        lastLabel = label;
      }
      items.push({ _type: 'event', ...item });
    }
    return items;
  }, [feed]);

  const renderItem = useCallback(({ item }: { item: any }) => {
    if (item._type === 'header') {
      return (
        <View style={s.dateLabelRow}>
          <View style={[s.dateLine, { backgroundColor: colors.border }]} />
          <Text style={[s.dateLabel, { color: colors.textTertiary }]}>{item.label}</Text>
          <View style={[s.dateBadge, { backgroundColor: colors.card, borderColor: colors.border }]}>
            <Text style={[s.dateBadgeText, { color: colors.textTertiary }]}>{item.count}</Text>
          </View>
          <View style={[s.dateLine, { backgroundColor: colors.border }]} />
        </View>
      );
    }

    const isInbound = item.is_inbound;
    const evtLabel = getEventLabel(item.event_type) || item.title || 'Activity';
    const photoUri = item.contact?.photo;

    return (
      <TouchableOpacity
        style={[s.eventCard, { backgroundColor: colors.card }]}
        onPress={() => item.contact?.id && router.push(`/contact/${item.contact.id}` as any)}
        activeOpacity={0.7}
        data-testid={`activity-event-item`}
      >
        <View style={s.avatarGroup}>
          {photoUri ? (
            Platform.OS === 'web' ? (
              <View style={s.eventAvatar}>
                <img
                  src={photoUri}
                  style={{ width: 52, height: 52, borderRadius: 14, objectFit: 'cover', display: 'block' }}
                  loading="lazy"
                />
              </View>
            ) : (
              <Image source={{ uri: photoUri }} style={s.eventAvatar} />
            )
          ) : (
            <View style={[s.eventAvatarPlaceholder, { backgroundColor: colors.border }]}>
              <Text style={[s.eventAvatarText, { color: colors.textTertiary }]}>{item.contact?.name?.[0] || '?'}</Text>
            </View>
          )}
          <View style={[s.eventIconBadge, { backgroundColor: item.color || '#007AFF', borderColor: colors.card }]}>
            <Ionicons name={(item.icon || 'flag') as any} size={12} color="#FFF" />
          </View>
        </View>
        <View style={s.eventContent}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
            <Text style={[s.eventName, { color: colors.text }]} numberOfLines={1}>{item.contact?.name || 'Unknown'}</Text>
            {isInbound && <View style={s.inboundBadge}><Text style={s.inboundText}>INBOUND</Text></View>}
            {item.contact?.tags?.slice(0, 2).map((t: string, ti: number) => (
              <View key={ti} style={[s.miniTag, { backgroundColor: colors.border }]}><Text style={[s.miniTagText, { color: colors.textTertiary }]}>{t}</Text></View>
            ))}
          </View>
          <Text style={[s.eventTitle, { color: colors.textSecondary }, isInbound && { color: '#30D158' }]}>
            {isInbound ? `"${item.description}"` : evtLabel}
          </Text>
          {!isInbound && item.description && item.description !== evtLabel && (
            <Text style={[s.eventDesc, { color: colors.textTertiary }]} numberOfLines={2}>{item.description}</Text>
          )}
        </View>
        <View style={{ alignItems: 'flex-end' }}>
          <Text style={[s.eventTime, { color: colors.textTertiary }]}>{formatFeedTime(item.timestamp)}</Text>
          <Ionicons name="chevron-forward" size={14} color={colors.textTertiary} style={{ marginTop: 4 }} />
        </View>
      </TouchableOpacity>
    );
  }, [colors, router]);

  if (loading) {
    return (
      <SafeAreaView style={[s.container, { backgroundColor: colors.bg }]}>
        <ActivityIndicator size="large" color="#C9A962" style={{ marginTop: 60 }} />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={[s.container, { backgroundColor: colors.bg }]} edges={['top']}>
      <View style={s.header}>
        <Text style={[s.headerTitle, { color: colors.text }]}>Activity</Text>
        <Text style={[s.headerSubtitle, { color: colors.textTertiary }]}>{feed.length} event{feed.length !== 1 ? 's' : ''} across all contacts</Text>
      </View>

      <ScrollView
        style={s.scrollContainer}
        contentContainerStyle={s.scroll}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#C9A962" />}
        showsVerticalScrollIndicator={false}
      >
        {listData.length === 0 ? (
          <View style={s.empty}>
            <Ionicons name="pulse-outline" size={48} color={colors.surface} />
            <Text style={[s.emptyText, { color: colors.textSecondary }]}>No activity yet</Text>
            <Text style={[s.emptySubtext, { color: colors.textTertiary }]}>Send a message or card to get started</Text>
          </View>
        ) : (
          listData.map((item, idx) => (
            <React.Fragment key={item._type === 'header' ? `hdr-${item.label}` : `evt-${idx}`}>
              {renderItem({ item })}
            </React.Fragment>
          ))
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1 },
  header: { paddingHorizontal: 16, paddingTop: 8, paddingBottom: 12 },
  headerTitle: { fontSize: 28, fontWeight: '800' },
  headerSubtitle: { fontSize: 13, marginTop: 2 },
  scrollContainer: { flex: 1 },
  scroll: { paddingBottom: 40 },

  // Date groups
  dateLabelRow: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 10, gap: 12 },
  dateLine: { flex: 1, height: 1 },
  dateLabel: { fontSize: 12, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 1 },
  dateBadge: { paddingHorizontal: 6, paddingVertical: 2, borderRadius: 8, borderWidth: 1 },
  dateBadgeText: { fontSize: 10, fontWeight: '700' },

  // Event cards — LARGER tiles
  eventCard: {
    flexDirection: 'row', alignItems: 'center', marginHorizontal: 12, marginBottom: 6,
    borderRadius: 16, padding: 16,
  },
  avatarGroup: { position: 'relative', marginRight: 14 },
  eventAvatar: { width: 52, height: 52, borderRadius: 14, borderWidth: 1 },
  eventAvatarPlaceholder: { width: 52, height: 52, borderRadius: 14, alignItems: 'center', justifyContent: 'center' },
  eventAvatarText: { fontSize: 18, fontWeight: '700' },
  eventIconBadge: {
    position: 'absolute', bottom: -3, right: -3,
    width: 22, height: 22, borderRadius: 11,
    alignItems: 'center', justifyContent: 'center', borderWidth: 2,
  },
  eventContent: { flex: 1 },
  eventName: { fontSize: 16, fontWeight: '700' },
  eventTitle: { fontSize: 14, marginTop: 2, fontWeight: '500' },
  eventDesc: { fontSize: 13, marginTop: 2, lineHeight: 18 },
  eventTime: { fontSize: 12, fontWeight: '500' },
  inboundBadge: { backgroundColor: '#30D15820', paddingHorizontal: 5, paddingVertical: 1, borderRadius: 4 },
  inboundText: { fontSize: 9, fontWeight: '700', color: '#30D158' },
  miniTag: { paddingHorizontal: 5, paddingVertical: 1, borderRadius: 4 },
  miniTagText: { fontSize: 9, fontWeight: '600' },

  // Empty
  empty: { alignItems: 'center', paddingVertical: 60 },
  emptyText: { fontSize: 18, marginTop: 10, fontWeight: '600' },
  emptySubtext: { fontSize: 13, marginTop: 4 },
});
