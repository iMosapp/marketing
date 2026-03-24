import React, { useState, useEffect, useCallback } from 'react';
import {
  View, Text, FlatList, TouchableOpacity, StyleSheet, Image,
  ActivityIndicator, RefreshControl, Platform,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import * as Haptics from 'expo-haptics';
import { useAuthStore } from '../../store/authStore';
import { useThemeStore } from '../../store/themeStore';
import api from '../../services/api';

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

const MILESTONE_META: Record<string, { icon: string; color: string; label: string; emoji: string }> = {
  new_contact_added: { icon: 'person-add', color: '#007AFF', label: 'New Relationship Started', emoji: '' },
  campaign_enrolled: { icon: 'rocket', color: '#AF52DE', label: 'Campaign Launched', emoji: '' },
  review_submitted: { icon: 'star', color: '#FFD60A', label: 'Review Received', emoji: '' },
  referral_made: { icon: 'people', color: '#34C759', label: 'Referral Connection', emoji: '' },
};

// Avatar component that handles web/native + fallback
const Avatar = ({ uri, name, size, borderRadius, color }: { uri?: string | null; name?: string; size: number; borderRadius: number; color?: string }) => {
  const accent = color || '#C9A962';
  if (uri) {
    if (Platform.OS === 'web') {
      return (
        <View style={{ width: size, height: size, borderRadius }}>
          <img src={uri} style={{ width: size, height: size, borderRadius, objectFit: 'cover', display: 'block' }} loading="lazy" />
        </View>
      );
    }
    return <Image source={{ uri }} style={{ width: size, height: size, borderRadius }} />;
  }
  return (
    <View style={{ width: size, height: size, borderRadius, backgroundColor: accent + '18', alignItems: 'center', justifyContent: 'center' }}>
      <Text style={{ fontSize: size * 0.4, fontWeight: '700', color: accent }}>{name?.[0] || '?'}</Text>
    </View>
  );
};

// ── Photo Moment Card — Facebook/Instagram-style large card ──
const PhotoCard = ({ item, colors, router }: any) => {
  const c = item.contact || {};
  const label = ENGAGEMENT_LABELS[item.event_type] || item.title;

  return (
    <TouchableOpacity
      style={[s.card, { backgroundColor: colors.card }]}
      onPress={() => c.id && router.push(`/contact/${c.id}` as any)}
      activeOpacity={0.85}
      data-testid="feed-photo-card"
    >
      {/* Post header: avatar + name + time */}
      <View style={s.cardHeader}>
        <Avatar uri={c.photo} name={c.name} size={40} borderRadius={20} color={item.color} />
        <View style={{ flex: 1, marginLeft: 10 }}>
          <Text style={[s.cardName, { color: colors.text }]} numberOfLines={1}>{c.name || 'Customer'}</Text>
          <Text style={[s.cardTime, { color: colors.textTertiary }]}>{formatFeedTime(item.timestamp)}</Text>
        </View>
        <View style={[s.typeBadge, { backgroundColor: (item.color || '#C9A962') + '15' }]}>
          <Ionicons name={(item.icon || 'eye') as any} size={14} color={item.color || '#C9A962'} />
        </View>
      </View>

      {/* Big photo */}
      {c.photo ? (
        <View style={s.photoWrap}>
          {Platform.OS === 'web' ? (
            <img src={c.photo} style={{ width: '100%', height: 260, objectFit: 'cover', borderRadius: 14, display: 'block' }} loading="lazy" />
          ) : (
            <Image source={{ uri: c.photo }} style={{ width: '100%', height: 260, borderRadius: 14 }} resizeMode="cover" />
          )}
        </View>
      ) : (
        <View style={[s.photoPlaceholder, { backgroundColor: (item.color || '#C9A962') + '08' }]}>
          <Ionicons name={(item.icon || 'camera') as any} size={40} color={(item.color || '#C9A962') + '50'} />
        </View>
      )}

      {/* Caption / action */}
      <View style={s.cardCaption}>
        <Text style={[s.captionText, { color: colors.text }]}>
          <Text style={{ fontWeight: '700' }}>{c.name || 'Customer'}</Text>
          {' '}{label}
        </Text>
        {c.vehicle ? (
          <View style={[s.vehicleTag, { backgroundColor: colors.surface }]}>
            <Ionicons name="car-sport" size={12} color={colors.textTertiary} />
            <Text style={{ fontSize: 12, fontWeight: '600', color: colors.textTertiary, marginLeft: 4 }}>{c.vehicle}</Text>
          </View>
        ) : null}
      </View>
    </TouchableOpacity>
  );
};

// ── Engagement Card — compact notification-style ──
const EngagementCard = ({ item, colors, router }: any) => {
  const c = item.contact || {};
  const label = ENGAGEMENT_LABELS[item.event_type] || item.title;

  return (
    <TouchableOpacity
      style={[s.engCard, { backgroundColor: colors.card }]}
      onPress={() => c.id && router.push(`/contact/${c.id}` as any)}
      activeOpacity={0.8}
      data-testid="feed-engagement-card"
    >
      <View style={[s.engStripe, { backgroundColor: item.color || '#007AFF' }]} />
      <View style={s.engBody}>
        <Avatar uri={c.photo} name={c.name} size={44} borderRadius={22} color={item.color} />
        <View style={{ flex: 1, marginLeft: 12 }}>
          <Text style={[{ fontSize: 15, color: colors.text }]} numberOfLines={2}>
            <Text style={{ fontWeight: '700' }}>{c.name || 'Someone'}</Text>
            {' '}<Text style={{ color: colors.textSecondary }}>{label}</Text>
          </Text>
          <View style={{ flexDirection: 'row', alignItems: 'center', marginTop: 3 }}>
            <Ionicons name={(item.icon || 'eye') as any} size={13} color={item.color || '#007AFF'} />
            <Text style={{ fontSize: 12, color: colors.textTertiary, marginLeft: 5 }}>{formatFeedTime(item.timestamp)}</Text>
          </View>
        </View>
        <Ionicons name="chevron-forward" size={16} color={colors.textTertiary} />
      </View>
    </TouchableOpacity>
  );
};

// ── Milestone Card — celebration-style ──
const MilestoneCard = ({ item, colors, router }: any) => {
  const c = item.contact || {};
  const meta = MILESTONE_META[item.event_type] || { icon: 'flag', color: '#C9A962', label: item.title, emoji: '' };

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
};

// ── Text Event Card — message/task-style ──
const TextCard = ({ item, colors, router }: any) => {
  const c = item.contact || {};
  const isInbound = item.is_inbound;

  return (
    <TouchableOpacity
      style={[s.txtCard, { backgroundColor: colors.card }]}
      onPress={() => c.id && router.push(`/contact/${c.id}` as any)}
      activeOpacity={0.8}
      data-testid="feed-text-card"
    >
      <View style={{ position: 'relative' }}>
        <Avatar uri={c.photo} name={c.name} size={44} borderRadius={12} color="#8E8E93" />
        <View style={[s.txtBadge, { backgroundColor: item.color || '#8E8E93', borderColor: colors.card }]}>
          <Ionicons name={(item.icon || 'flag') as any} size={10} color="#FFF" />
        </View>
      </View>
      <View style={{ flex: 1, marginLeft: 12 }}>
        <View style={{ flexDirection: 'row', alignItems: 'center' }}>
          <Text style={[{ fontSize: 15, fontWeight: '700', color: colors.text }]} numberOfLines={1}>{c.name || 'Unknown'}</Text>
          {isInbound && (
            <View style={s.inbound}><Text style={s.inboundTxt}>INBOUND</Text></View>
          )}
        </View>
        <Text style={[{ fontSize: 14, marginTop: 1, color: isInbound ? '#30D158' : colors.textSecondary }]} numberOfLines={1}>
          {isInbound ? `"${item.description}"` : item.title}
        </Text>
      </View>
      <Text style={{ fontSize: 12, color: colors.textTertiary }}>{formatFeedTime(item.timestamp)}</Text>
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
  const [, setTick] = useState(0);

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
  useEffect(() => {
    if (!userId) return;
    const interval = setInterval(loadFeed, 30000);
    return () => clearInterval(interval);
  }, [userId, loadFeed]);
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

  // Group by date
  const groupedData = React.useMemo(() => {
    const items: any[] = [];
    let lastLabel = '';
    for (const item of feed) {
      const label = getDateLabel(item.timestamp);
      if (label !== lastLabel) {
        items.push({ _type: 'date_header', label, _key: `dh-${label}` });
        lastLabel = label;
      }
      items.push({ _type: 'event', ...item });
    }
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
          const vt = item.visual_type || 'text_event';
          if (vt === 'photo_moment') return <PhotoCard item={item} colors={colors} router={router} />;
          if (vt === 'engagement') return <EngagementCard item={item} colors={colors} router={router} />;
          if (vt === 'milestone') return <MilestoneCard item={item} colors={colors} router={router} />;
          return <TextCard item={item} colors={colors} router={router} />;
        }}
      />
    </View>
  );
}

const s = StyleSheet.create({
  root: { flex: 1 },
  header: { paddingHorizontal: 16, paddingTop: 8, paddingBottom: 6 },
  headerTitle: { fontSize: 28, fontWeight: '800' },
  headerSub: { fontSize: 14, marginTop: 2 },

  // Date dividers
  dateRow: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 12, gap: 12 },
  dateLine: { flex: 1, height: 1 },
  dateText: { fontSize: 12, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 1.2 },

  // Photo Card (large social-style)
  card: { marginHorizontal: 12, marginBottom: 14, borderRadius: 20, overflow: 'hidden' },
  cardHeader: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 14, paddingTop: 14, paddingBottom: 10 },
  cardName: { fontSize: 15, fontWeight: '700' },
  cardTime: { fontSize: 12, marginTop: 1 },
  typeBadge: { width: 32, height: 32, borderRadius: 16, alignItems: 'center', justifyContent: 'center' },
  photoWrap: { paddingHorizontal: 12 },
  photoPlaceholder: { marginHorizontal: 12, height: 140, borderRadius: 14, alignItems: 'center', justifyContent: 'center' },
  cardCaption: { paddingHorizontal: 14, paddingTop: 10, paddingBottom: 14 },
  captionText: { fontSize: 15, lineHeight: 20 },
  vehicleTag: { flexDirection: 'row', alignItems: 'center', marginTop: 8, paddingHorizontal: 8, paddingVertical: 4, borderRadius: 8, alignSelf: 'flex-start' },

  // Engagement Card
  engCard: { marginHorizontal: 12, marginBottom: 6, borderRadius: 14, overflow: 'hidden', flexDirection: 'row' },
  engStripe: { width: 3 },
  engBody: { flex: 1, flexDirection: 'row', alignItems: 'center', padding: 12 },

  // Milestone Card
  mileCard: { marginHorizontal: 12, marginBottom: 10, borderRadius: 16, borderWidth: 1, flexDirection: 'row', alignItems: 'center', padding: 14, borderStyle: 'dashed' },
  mileIcon: { width: 48, height: 48, borderRadius: 24, alignItems: 'center', justifyContent: 'center', marginRight: 12 },
  mileLabel: { fontSize: 11, fontWeight: '800', textTransform: 'uppercase', letterSpacing: 0.5 },
  mileName: { fontSize: 16, fontWeight: '700', marginTop: 2 },

  // Text Card
  txtCard: { flexDirection: 'row', alignItems: 'center', marginHorizontal: 12, marginBottom: 4, borderRadius: 14, padding: 12 },
  txtBadge: { position: 'absolute', bottom: -2, right: -2, width: 18, height: 18, borderRadius: 9, alignItems: 'center', justifyContent: 'center', borderWidth: 2 },
  inbound: { backgroundColor: '#30D15820', paddingHorizontal: 5, paddingVertical: 1, borderRadius: 4, marginLeft: 6 },
  inboundTxt: { fontSize: 9, fontWeight: '700', color: '#30D158' },

  // Empty
  empty: { alignItems: 'center', paddingVertical: 80 },
  emptyIcon: { width: 64, height: 64, borderRadius: 32, alignItems: 'center', justifyContent: 'center', marginBottom: 12 },
});
