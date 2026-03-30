import React, { useState, useEffect, useCallback } from 'react';
import {
  View, Text, FlatList, TouchableOpacity, StyleSheet,
  ActivityIndicator, RefreshControl, Platform,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import * as Haptics from 'expo-haptics';
import { useAuthStore } from '../../store/authStore';
import { useThemeStore } from '../../store/themeStore';
import api from '../../services/api';
import { Avatar } from '../../components/Avatar';
import { resolveContactPhotoUrl } from '../../utils/photoUrl';

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
  if (days < 7) return d.toLocaleDateString(undefined, { weekday: 'long' });
  return d.toLocaleDateString(undefined, { month: 'long', day: 'numeric' });
};

const ENGAGEMENT_LABELS: Record<string, string> = {
  digital_card_viewed: 'viewed your digital card',
  showcase_viewed: 'viewed your showcase',
  link_page_viewed: 'visited your link page',
  link_clicked: 'clicked your link',
  review_link_clicked: 'clicked your review link',
  congrats_card_viewed: 'opened your congrats card',
  review_page_viewed: 'viewed your review page',
  training_video_clicked: 'watched a training video',
};

const MILESTONE_META: Record<string, { icon: string; color: string; label: string }> = {
  new_contact_added: { icon: 'person-add', color: '#007AFF', label: 'New Relationship Started' },
  campaign_enrolled: { icon: 'rocket', color: '#AF52DE', label: 'Campaign Launched' },
  review_submitted: { icon: 'star', color: '#FFD60A', label: 'Review Received' },
  referral_made: { icon: 'people', color: '#34C759', label: 'Referral Connection' },
};

const EVENT_ICON: Record<string, string> = {
  digital_card_viewed: 'card',
  showcase_viewed: 'eye',
  link_page_viewed: 'link',
  link_clicked: 'open',
  review_link_clicked: 'star-half',
  congrats_card_viewed: 'gift',
  review_page_viewed: 'star',
  training_video_clicked: 'play-circle',
  new_contact_added: 'person-add',
  campaign_enrolled: 'rocket',
  review_submitted: 'star',
  referral_made: 'people',
};

// Get a human-readable label for any event
const getEventLabel = (item: any) => {
  if (ENGAGEMENT_LABELS[item.event_type]) return ENGAGEMENT_LABELS[item.event_type];
  const meta = MILESTONE_META[item.event_type];
  if (meta) return meta.label;
  return item.title || item.event_type || 'Activity';
};

const getEventIcon = (item: any) => item.icon || EVENT_ICON[item.event_type] || 'ellipse';
const getEventColor = (item: any) => {
  const meta = MILESTONE_META[item.event_type];
  if (meta) return meta.color;
  return item.color || '#C9A962';
};

// ── Single event card (when contact has only 1 activity) ──
const SingleEventCard = ({ item, colors, router }: any) => {
  const c = item.contact || {};
  const label = getEventLabel(item);
  const isMilestone = !!MILESTONE_META[item.event_type];

  if (isMilestone) {
    const meta = MILESTONE_META[item.event_type] || { icon: 'flag', color: '#C9A962', label: item.title };
    return (
      <TouchableOpacity
        style={[s.mileCard, { borderColor: meta.color + '30', backgroundColor: meta.color + '08' }]}
        onPress={() => c.id && router.push(`/contact/${c.id}` as any)}
        activeOpacity={0.8}
        data-testid="feed-milestone-card"
      >
        <View style={[s.mileIcon, { backgroundColor: meta.color + '18' }]}>
          <Ionicons name={meta.icon as any} size={22} color={meta.color} />
        </View>
        <View style={{ flex: 1 }}>
          <Text style={[s.mileLabel, { color: meta.color }]}>{meta.label}</Text>
          <Text style={[s.mileName, { color: colors.text }]}>{c.name || 'New Contact'}</Text>
          {item.description ? (
            <Text style={{ fontSize: 13, color: colors.textTertiary, marginTop: 2 }} numberOfLines={1}>{item.description}</Text>
          ) : null}
        </View>
        <Text style={{ fontSize: 12, color: colors.textTertiary }}>{formatFeedTime(item.timestamp)}</Text>
      </TouchableOpacity>
    );
  }

  // Standard single event with photo
  return (
    <TouchableOpacity
      style={[s.singleCard, { backgroundColor: colors.card }]}
      onPress={() => c.id && router.push(`/contact/${c.id}` as any)}
      activeOpacity={0.85}
      data-testid="feed-single-card"
    >
      <View style={s.singleHeader}>
        <Avatar uri={c.photo} name={c.name} sizePx={44} borderRadius={22} color={item.color} />
        <View style={{ flex: 1, marginLeft: 12 }}>
          <Text style={[{ fontSize: 15, color: colors.text }]} numberOfLines={2}>
            <Text style={{ fontWeight: '700' }}>{c.name || 'Customer'}</Text>
            {' '}<Text style={{ color: colors.textSecondary }}>{label}</Text>
          </Text>
          <View style={{ flexDirection: 'row', alignItems: 'center', marginTop: 3 }}>
            <Ionicons name={getEventIcon(item) as any} size={13} color={getEventColor(item)} />
            <Text style={{ fontSize: 12, color: colors.textTertiary, marginLeft: 5 }}>{formatFeedTime(item.timestamp)}</Text>
          </View>
        </View>
        <Ionicons name="chevron-forward" size={16} color={colors.textTertiary} />
      </View>
    </TouchableOpacity>
  );
};

// ── Grouped contact card (small avatar only + touchpoint list) ──
const GroupedContactCard = ({ group, colors, router }: any) => {
  const firstEvent = group.events[0];
  const c = firstEvent.contact || {};

  return (
    <TouchableOpacity
      style={[s.groupCard, { backgroundColor: colors.card }]}
      onPress={() => c.id && router.push(`/contact/${c.id}` as any)}
      activeOpacity={0.85}
      data-testid="feed-grouped-card"
    >
      {/* Contact header — small avatar only, no full-size photo */}
      <View style={s.groupHeader}>
        <Avatar uri={c.photo} name={c.name} sizePx={48} borderRadius={12} color={firstEvent.color} />
        <View style={{ flex: 1, marginLeft: 12 }}>
          <Text style={[s.groupName, { color: colors.text }]} numberOfLines={1}>{c.name || 'Customer'}</Text>
          <Text style={{ fontSize: 13, color: colors.textTertiary, marginTop: 1 }}>
            {group.events.length} touch{group.events.length === 1 ? '' : 'es'} · {formatFeedTime(firstEvent.timestamp)}
          </Text>
          {c.vehicle ? (
            <View style={[s.vehicleTag, { backgroundColor: colors.surface }]}>
              <Ionicons name="car-sport" size={11} color={colors.textTertiary} />
              <Text style={{ fontSize: 11, fontWeight: '600', color: colors.textTertiary, marginLeft: 3 }}>{c.vehicle}</Text>
            </View>
          ) : null}
        </View>
        <Ionicons name="chevron-forward" size={16} color={colors.textTertiary} />
      </View>

      {/* Touchpoint list — all events preserved, no photo tile */}
      <View style={[s.touchList, { borderTopColor: colors.border }]}>
        {group.events.map((evt: any, idx: number) => {
          const label = getEventLabel(evt);
          const icon = getEventIcon(evt);
          const color = getEventColor(evt);
          const isLast = idx === group.events.length - 1;

          return (
            <View key={`tp-${idx}`} style={[s.touchRow, !isLast && { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border }]}>
              <View style={[s.touchDot, { backgroundColor: color + '18' }]}>
                <Ionicons name={icon as any} size={14} color={color} />
              </View>
              <Text style={[s.touchLabel, { color: colors.textSecondary }]} numberOfLines={1}>{label}</Text>
              <Text style={[s.touchTime, { color: colors.textTertiary }]}>{formatFeedTime(evt.timestamp)}</Text>
            </View>
          );
        })}
      </View>
    </TouchableOpacity>
  );
};


export default function ActivityTab() {
  const { colors } = useThemeStore();
  const { user } = useAuthStore();
  const router = useRouter();
  const userId = user?._id;

  const [feed, setFeed] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const [page, setPage] = useState(0);
  const [, setTick] = useState(0);

  const PAGE_SIZE = 30;

  const loadFeed = useCallback(async (reset = true) => {
    if (!userId) return;
    const skip = reset ? 0 : page * PAGE_SIZE;
    try {
      const resp = await api.get(`/contacts/${userId}/master-feed?limit=${PAGE_SIZE}&skip=${skip}`);
      const newItems = resp.data.feed || [];
      const more = resp.data.has_more ?? (newItems.length === PAGE_SIZE);
      if (reset) {
        setFeed(newItems);
        setPage(1);
      } else {
        setFeed(prev => [...prev, ...newItems]);
        setPage(p => p + 1);
      }
      setHasMore(more);
    } catch (e) {
      console.error('Failed to load activity feed:', e);
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  }, [userId, page]);

  const loadMore = useCallback(async () => {
    if (loadingMore || !hasMore || loading) return;
    setLoadingMore(true);
    await loadFeed(false);
  }, [loadingMore, hasMore, loading, loadFeed]);

  useEffect(() => { loadFeed(true); }, [userId]);
  useEffect(() => {
    if (!userId) return;
    // Refresh first page every 30s — don't paginate on refresh
    const interval = setInterval(() => loadFeed(true), 30000);
    return () => clearInterval(interval);
  }, [userId]);
  useEffect(() => {
    const interval = setInterval(() => setTick(t => t + 1), 60000);
    return () => clearInterval(interval);
  }, []);

  const onRefresh = async () => {
    setRefreshing(true);
    try { Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light); } catch {}
    await loadFeed(true);
    setRefreshing(false);
  };

  // Group by date, then group consecutive same-contact events
  const groupedData = React.useMemo(() => {
    const items: any[] = [];
    let lastDateLabel = '';
    let currentGroup: { contactId: string; events: any[] } | null = null;

    const flushGroup = () => {
      if (!currentGroup) return;
      if (currentGroup.events.length === 1) {
        items.push({ _type: 'single', ...currentGroup.events[0] });
      } else {
        items.push({ _type: 'group', contactId: currentGroup.contactId, events: currentGroup.events, _key: `grp-${currentGroup.contactId}-${currentGroup.events[0].timestamp}` });
      }
      currentGroup = null;
    };

    for (const item of feed) {
      const dateLabel = getDateLabel(item.timestamp);

      // New date section
      if (dateLabel !== lastDateLabel) {
        flushGroup();
        items.push({ _type: 'date_header', label: dateLabel, _key: `dh-${dateLabel}` });
        lastDateLabel = dateLabel;
      }

      const contactId = item.contact?.id || '';

      // Same contact as current group? Add to group
      if (currentGroup && currentGroup.contactId === contactId && contactId) {
        currentGroup.events.push(item);
      } else {
        // Different contact — flush previous group, start new one
        flushGroup();
        currentGroup = { contactId, events: [item] };
      }
    }
    flushGroup(); // flush last group

    return items;
  }, [feed]);

  if (loading) {
    return (
      <View style={[s.root, { backgroundColor: colors.bg }]}>
        <ActivityIndicator size="large" color="#C9A962" style={{ marginTop: 60 }} />
      </View>
    );
  }

  return (
    <View style={[s.root, { backgroundColor: colors.bg }]}>
      <View style={s.header}>
        <Text style={[s.headerTitle, { color: colors.text }]} data-testid="activity-header">Activity</Text>
        <Text style={[s.headerSub, { color: colors.textTertiary }]}>Your relationship feed</Text>
      </View>

      <FlatList
        data={groupedData}
        keyExtractor={(item, idx) => item._key || `${item._type}-${item.event_type || ''}-${idx}`}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#C9A962" />}
        showsVerticalScrollIndicator={false}
        contentContainerStyle={{ paddingBottom: 40 }}
        style={{ flex: 1 }}
        ListEmptyComponent={
          <View style={s.empty}>
            <View style={[s.emptyIcon, { backgroundColor: colors.surface }]}>
              <Ionicons name="pulse-outline" size={32} color={colors.textTertiary} />
            </View>
            <Text style={[{ fontSize: 18, fontWeight: '700', color: colors.textSecondary }]}>No activity yet</Text>
            <Text style={[{ fontSize: 14, marginTop: 4, textAlign: 'center', paddingHorizontal: 40, color: colors.textTertiary }]}>
              Share your card or send a message to get started
            </Text>
          </View>
        }
        renderItem={({ item }) => {
          if (item._type === 'date_header') {
            return (
              <View style={s.dateRow}>
                <View style={[s.dateLine, { backgroundColor: colors.border }]} />
                <Text style={[s.dateText, { color: colors.textTertiary }]}>{item.label}</Text>
                <View style={[s.dateLine, { backgroundColor: colors.border }]} />
              </View>
            );
          }
          if (item._type === 'group') {
            return <GroupedContactCard group={item} colors={colors} router={router} />;
          }
          // Single event
          return <SingleEventCard item={item} colors={colors} router={router} />;
        }}
        onEndReached={loadMore}
        onEndReachedThreshold={0.3}
        ListFooterComponent={
          loadingMore ? (
            <View style={{ paddingVertical: 20, alignItems: 'center' }}>
              <ActivityIndicator color={colors.textSecondary} />
              <Text style={{ fontSize: 13, color: colors.textTertiary, marginTop: 6 }}>Loading more...</Text>
            </View>
          ) : hasMore ? (
            <TouchableOpacity
              style={{ paddingVertical: 16, alignItems: 'center' }}
              onPress={loadMore}
            >
              <Text style={{ fontSize: 15, fontWeight: '600', color: '#007AFF' }}>Load more activity</Text>
            </TouchableOpacity>
          ) : feed.length > 0 ? (
            <Text style={{ textAlign: 'center', color: colors.textTertiary, fontSize: 13, paddingVertical: 20 }}>
              You've reached the beginning
            </Text>
          ) : null
        }
      />
    </View>
  );
}

const s = StyleSheet.create({
  root: { flex: 1 },
  header: { paddingHorizontal: 16, paddingTop: 48, paddingBottom: 6 },
  headerTitle: { fontSize: 28, fontWeight: '800' },
  headerSub: { fontSize: 14, marginTop: 2 },

  // Date dividers
  dateRow: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 12, gap: 12 },
  dateLine: { flex: 1, height: 1 },
  dateText: { fontSize: 12, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 1.2 },

  // Single event card (compact)
  singleCard: { marginHorizontal: 12, marginBottom: 6, borderRadius: 14, overflow: 'hidden' },
  singleHeader: { flexDirection: 'row', alignItems: 'center', padding: 12 },

  // Grouped contact card
  groupCard: { marginHorizontal: 12, marginBottom: 14, borderRadius: 18, overflow: 'hidden' },
  groupHeader: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 14, paddingTop: 14, paddingBottom: 10 },
  groupName: { fontSize: 17, fontWeight: '700' },
  groupPhotoWrap: { paddingHorizontal: 12, marginBottom: 4 },
  vehicleTag: { flexDirection: 'row', alignItems: 'center', marginTop: 4, paddingHorizontal: 6, paddingVertical: 2, borderRadius: 6, alignSelf: 'flex-start' },

  // Touchpoint list inside group
  touchList: { marginHorizontal: 14, marginBottom: 10, borderTopWidth: StyleSheet.hairlineWidth, paddingTop: 4 },
  touchRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: 8 },
  touchDot: { width: 28, height: 28, borderRadius: 14, alignItems: 'center', justifyContent: 'center' },
  touchLabel: { flex: 1, fontSize: 14, marginLeft: 10 },
  touchTime: { fontSize: 12, marginLeft: 8 },

  // Milestone Card (standalone)
  mileCard: { marginHorizontal: 12, marginBottom: 10, borderRadius: 16, borderWidth: 1, flexDirection: 'row', alignItems: 'center', padding: 14, borderStyle: 'dashed' },
  mileIcon: { width: 48, height: 48, borderRadius: 24, alignItems: 'center', justifyContent: 'center', marginRight: 12 },
  mileLabel: { fontSize: 11, fontWeight: '800', textTransform: 'uppercase', letterSpacing: 0.5 },
  mileName: { fontSize: 16, fontWeight: '700', marginTop: 2 },

  // Empty
  empty: { alignItems: 'center', paddingVertical: 80 },
  emptyIcon: { width: 64, height: 64, borderRadius: 32, alignItems: 'center', justifyContent: 'center', marginBottom: 12 },
});
