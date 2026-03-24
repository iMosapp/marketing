import React, { useState, useEffect, useCallback } from 'react';
import {
  View, Text, FlatList, ScrollView, TouchableOpacity, StyleSheet, Image,
  ActivityIndicator, RefreshControl, Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
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

const MILESTONE_ICONS: Record<string, { icon: string; color: string; label: string }> = {
  new_contact_added: { icon: 'person-add', color: '#007AFF', label: 'New relationship started' },
  campaign_enrolled: { icon: 'rocket', color: '#AF52DE', label: 'Campaign launched' },
  review_submitted: { icon: 'star', color: '#FFD60A', label: 'Review received' },
  referral_made: { icon: 'people', color: '#34C759', label: 'Referral connection' },
};

// ── Photo Moment Card (large, Instagram-style) ──
const PhotoMomentCard = ({ item, colors, router }: any) => {
  const contact = item.contact || {};
  const photoUri = contact.photo;
  const hasPhoto = !!photoUri;

  return (
    <TouchableOpacity
      style={[s.photoCard, { backgroundColor: colors.card }]}
      onPress={() => contact.id && router.push(`/contact/${contact.id}` as any)}
      activeOpacity={0.85}
      data-testid="feed-photo-card"
    >
      {/* Header: avatar + name + time */}
      <View style={s.photoHeader}>
        <View style={s.photoHeaderLeft}>
          {photoUri ? (
            Platform.OS === 'web' ? (
              <View style={s.smallAvatar}>
                <img src={photoUri} style={{ width: 36, height: 36, borderRadius: 18, objectFit: 'cover', display: 'block' }} loading="lazy" />
              </View>
            ) : (
              <Image source={{ uri: photoUri }} style={s.smallAvatar} />
            )
          ) : (
            <View style={[s.smallAvatarPlaceholder, { backgroundColor: (item.color || '#C9A962') + '18' }]}>
              <Text style={{ fontSize: 15, fontWeight: '700', color: item.color || '#C9A962' }}>{contact.name?.[0] || '?'}</Text>
            </View>
          )}
          <View>
            <Text style={[s.photoName, { color: colors.text }]} numberOfLines={1}>{contact.name || 'Customer'}</Text>
            <Text style={[s.photoTime, { color: colors.textTertiary }]}>{formatFeedTime(item.timestamp)}</Text>
          </View>
        </View>
        <View style={[s.eventBadge, { backgroundColor: (item.color || '#C9A962') + '15' }]}>
          <Ionicons name={(item.icon || 'camera') as any} size={14} color={item.color || '#C9A962'} />
        </View>
      </View>

      {/* Photo area */}
      {hasPhoto ? (
        <View style={s.photoImage}>
          {Platform.OS === 'web' ? (
            <img src={photoUri} style={{ width: '100%', height: 280, objectFit: 'cover', borderRadius: 12, display: 'block' }} loading="lazy" />
          ) : (
            <Image source={{ uri: photoUri }} style={{ width: '100%', height: 280, borderRadius: 12 }} resizeMode="cover" />
          )}
        </View>
      ) : (
        <View style={[s.photoPlaceholder, { backgroundColor: (item.color || '#C9A962') + '08' }]}>
          <Ionicons name={(item.icon || 'camera') as any} size={36} color={(item.color || '#C9A962') + '40'} />
        </View>
      )}

      {/* Caption */}
      <View style={s.photoCaption}>
        <Text style={[s.photoCaptionTitle, { color: colors.text }]}>{item.title}</Text>
        {item.description ? (
          <Text style={[s.photoCaptionDesc, { color: colors.textSecondary }]} numberOfLines={2}>{item.description}</Text>
        ) : null}
        {contact.vehicle ? (
          <View style={[s.vehicleTag, { backgroundColor: colors.surface }]}>
            <Ionicons name="car-sport" size={12} color={colors.textTertiary} />
            <Text style={[s.vehicleText, { color: colors.textTertiary }]}>{contact.vehicle}</Text>
          </View>
        ) : null}
      </View>
    </TouchableOpacity>
  );
};

// ── Engagement Card (what customers are clicking/viewing) ──
const EngagementCard = ({ item, colors, router }: any) => {
  const contact = item.contact || {};
  const photoUri = contact.photo;
  const engagementLabel = ENGAGEMENT_LABELS[item.event_type] || item.title;

  return (
    <TouchableOpacity
      style={[s.engagementCard, { backgroundColor: colors.card }]}
      onPress={() => contact.id && router.push(`/contact/${contact.id}` as any)}
      activeOpacity={0.8}
      data-testid="feed-engagement-card"
    >
      <View style={[s.engagementStripe, { backgroundColor: item.color || '#007AFF' }]} />
      <View style={s.engagementBody}>
        <View style={s.engagementLeft}>
          {photoUri ? (
            Platform.OS === 'web' ? (
              <View style={s.engagementAvatar}>
                <img src={photoUri} style={{ width: 44, height: 44, borderRadius: 22, objectFit: 'cover', display: 'block' }} loading="lazy" />
              </View>
            ) : (
              <Image source={{ uri: photoUri }} style={s.engagementAvatar} />
            )
          ) : (
            <View style={[s.engagementAvatarPlaceholder, { backgroundColor: (item.color || '#007AFF') + '15' }]}>
              <Text style={{ fontSize: 16, fontWeight: '700', color: item.color || '#007AFF' }}>{contact.name?.[0] || '?'}</Text>
            </View>
          )}
        </View>
        <View style={s.engagementContent}>
          <Text style={[s.engagementName, { color: colors.text }]} numberOfLines={1}>
            {contact.name || 'Someone'}{' '}
            <Text style={[s.engagementAction, { color: colors.textSecondary }]}>{engagementLabel}</Text>
          </Text>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 3 }}>
            <Ionicons name={(item.icon || 'eye') as any} size={13} color={item.color || '#007AFF'} />
            <Text style={[s.engagementTime, { color: colors.textTertiary }]}>{formatFeedTime(item.timestamp)}</Text>
          </View>
        </View>
        <Ionicons name="chevron-forward" size={16} color={colors.textTertiary} />
      </View>
    </TouchableOpacity>
  );
};

// ── Milestone Card (special marker) ──
const MilestoneCard = ({ item, colors, router }: any) => {
  const contact = item.contact || {};
  const info = MILESTONE_ICONS[item.event_type] || { icon: 'flag', color: '#C9A962', label: item.title };

  return (
    <TouchableOpacity
      style={[s.milestoneCard, { borderColor: info.color + '25' }]}
      onPress={() => contact.id && router.push(`/contact/${contact.id}` as any)}
      activeOpacity={0.8}
      data-testid="feed-milestone-card"
    >
      <View style={[s.milestoneIcon, { backgroundColor: info.color + '12' }]}>
        <Ionicons name={info.icon as any} size={20} color={info.color} />
      </View>
      <View style={s.milestoneContent}>
        <Text style={[s.milestoneLabel, { color: info.color }]}>{info.label}</Text>
        <Text style={[s.milestoneName, { color: colors.text }]}>{contact.name || 'New Contact'}</Text>
        {item.description ? (
          <Text style={[s.milestoneDesc, { color: colors.textTertiary }]} numberOfLines={1}>{item.description}</Text>
        ) : null}
      </View>
      <Text style={[s.milestoneTime, { color: colors.textTertiary }]}>{formatFeedTime(item.timestamp)}</Text>
    </TouchableOpacity>
  );
};

// ── Text Event Card (compact, for messages/tasks) ──
const TextEventCard = ({ item, colors, router }: any) => {
  const contact = item.contact || {};
  const photoUri = contact.photo;
  const isInbound = item.is_inbound;

  return (
    <TouchableOpacity
      style={[s.textCard, { backgroundColor: colors.card }]}
      onPress={() => contact.id && router.push(`/contact/${contact.id}` as any)}
      activeOpacity={0.8}
      data-testid="feed-text-card"
    >
      <View style={s.textAvatarWrap}>
        {photoUri ? (
          Platform.OS === 'web' ? (
            <View style={s.textAvatar}>
              <img src={photoUri} style={{ width: 44, height: 44, borderRadius: 12, objectFit: 'cover', display: 'block' }} loading="lazy" />
            </View>
          ) : (
            <Image source={{ uri: photoUri }} style={s.textAvatar} />
          )
        ) : (
          <View style={[s.textAvatarPlaceholder, { backgroundColor: colors.surface }]}>
            <Text style={{ fontSize: 16, fontWeight: '700', color: colors.textTertiary }}>{contact.name?.[0] || '?'}</Text>
          </View>
        )}
        <View style={[s.textIconBadge, { backgroundColor: item.color || '#8E8E93', borderColor: colors.card }]}>
          <Ionicons name={(item.icon || 'flag') as any} size={10} color="#FFF" />
        </View>
      </View>
      <View style={s.textContent}>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
          <Text style={[s.textName, { color: colors.text }]} numberOfLines={1}>{contact.name || 'Unknown'}</Text>
          {isInbound && (
            <View style={s.inboundBadge}><Text style={s.inboundText}>INBOUND</Text></View>
          )}
        </View>
        <Text style={[s.textTitle, { color: colors.textSecondary }, isInbound && { color: '#30D158' }]} numberOfLines={1}>
          {isInbound ? `"${item.description}"` : item.title}
        </Text>
        {!isInbound && item.description && item.description !== item.title ? (
          <Text style={[s.textDesc, { color: colors.textTertiary }]} numberOfLines={1}>{item.description}</Text>
        ) : null}
      </View>
      <Text style={[s.textTime, { color: colors.textTertiary }]}>{formatFeedTime(item.timestamp)}</Text>
    </TouchableOpacity>
  );
};

// ── Filter Chips ──
const FILTERS = [
  { key: 'all', label: 'All', icon: 'pulse' },
  { key: 'engagement', label: 'Engagement', icon: 'eye' },
  { key: 'photo_moment', label: 'Photos', icon: 'camera' },
  { key: 'milestone', label: 'Milestones', icon: 'flag' },
  { key: 'text_event', label: 'Messages', icon: 'chatbubble' },
];

export default function ActivityTab() {
  const { colors } = useThemeStore();
  const { user } = useAuthStore();
  const router = useRouter();
  const userId = user?._id;

  const [feed, setFeed] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [activeFilter, setActiveFilter] = useState('all');
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
    const interval = setInterval(() => { loadFeed(); }, 30000);
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

  // Filter feed
  const filteredFeed = activeFilter === 'all'
    ? feed
    : feed.filter(item => item.visual_type === activeFilter);

  // Group by date
  const groupedData = React.useMemo(() => {
    const items: any[] = [];
    let lastLabel = '';
    for (const item of filteredFeed) {
      const label = getDateLabel(item.timestamp);
      if (label !== lastLabel) {
        items.push({ _type: 'date_header', label });
        lastLabel = label;
      }
      items.push({ _type: 'event', ...item });
    }
    return items;
  }, [filteredFeed]);

  const photoCount = feed.filter(f => f.visual_type === 'photo_moment').length;

  if (loading) {
    return (
      <View style={[s.container, { backgroundColor: colors.bg }]}>
        <ActivityIndicator size="large" color="#C9A962" style={{ marginTop: 60 }} />
      </View>
    );
  }

  return (
    <View style={[s.container, { backgroundColor: colors.bg }]}>
      {/* Header */}
      <View style={s.header}>
        <View>
          <Text style={[s.headerTitle, { color: colors.text }]} data-testid="activity-header">Activity</Text>
          <Text style={[s.headerSubtitle, { color: colors.textTertiary }]}>Your relationship feed</Text>
        </View>
        {engagementCount > 0 && (
          <View style={[s.headerStat, { backgroundColor: '#34C75915' }]}>
            <Ionicons name="eye" size={14} color="#34C759" />
            <Text style={{ fontSize: 13, fontWeight: '700', color: '#34C759' }}>{engagementCount}</Text>
          </View>
        )}
      </View>

      {/* Feed */}
      <FlatList
        data={[{ _type: 'filters' }, ...groupedData]}
        keyExtractor={(item, idx) => `${item._type}-${(item as any).event_type || (item as any).label || 'f'}-${idx}`}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#C9A962" />}
        showsVerticalScrollIndicator={false}
        contentContainerStyle={{ paddingBottom: 40 }}
        style={{ flex: 1 }}
        ListEmptyComponent={
          <View style={s.empty}>
            <View style={[s.emptyIcon, { backgroundColor: colors.surface }]}>
              <Ionicons name="pulse-outline" size={32} color={colors.textTertiary} />
            </View>
            <Text style={[s.emptyText, { color: colors.textSecondary }]}>No activity yet</Text>
            <Text style={[s.emptySubtext, { color: colors.textTertiary }]}>Share your card or send a message to get started</Text>
          </View>
        }
        renderItem={({ item }) => {
          if (item._type === 'filters') {
            return (
              <View style={{ height: 40, marginBottom: 4 }}>
                <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ flexDirection: 'row', paddingHorizontal: 12, alignItems: 'center' }}>
                  {FILTERS.map((f, i) => {
                  const isActive = activeFilter === f.key;
                  return (
                    <TouchableOpacity
                      key={f.key}
                      onPress={() => setActiveFilter(f.key)}
                      style={{
                        flexDirection: 'row', alignItems: 'center',
                        paddingHorizontal: 14, paddingVertical: 7, borderRadius: 20, borderWidth: 1,
                        marginRight: i < FILTERS.length - 1 ? 8 : 0,
                        backgroundColor: isActive ? '#C9A962' : colors.card,
                        borderColor: isActive ? '#C9A962' : colors.border,
                      }}
                    >
                      <Ionicons name={f.icon as any} size={14} color={isActive ? '#000' : colors.textSecondary} style={{ marginRight: 5 }} />
                      <Text style={{ fontSize: 13, fontWeight: '600', color: isActive ? '#000' : colors.textSecondary }}>{f.label}</Text>
                    </TouchableOpacity>
                  );
                })}
              </ScrollView>
            );
          }
          if (item._type === 'date_header') {
            return (
              <View style={s.dateLabelRow}>
                <View style={[s.dateLine, { backgroundColor: colors.border }]} />
                <Text style={[s.dateLabel, { color: colors.textTertiary }]}>{item.label}</Text>
                <View style={[s.dateLine, { backgroundColor: colors.border }]} />
              </View>
            );
          }
          const vt = item.visual_type || 'text_event';
          if (vt === 'photo_moment') return <PhotoMomentCard item={item} colors={colors} router={router} />;
          if (vt === 'engagement') return <EngagementCard item={item} colors={colors} router={router} />;
          if (vt === 'milestone') return <MilestoneCard item={item} colors={colors} router={router} />;
          return <TextEventCard item={item} colors={colors} router={router} />;
        }}
      />

    </View>
  );
}

const s = StyleSheet.create({
  container: { flex: 1 },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', paddingHorizontal: 16, paddingTop: 8, paddingBottom: 8 },
  headerTitle: { fontSize: 28, fontWeight: '800' },
  headerSubtitle: { fontSize: 14, marginTop: 2 },
  headerStat: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 10, paddingVertical: 5, borderRadius: 20, marginTop: 4 },

  // Filter chips
  filterRow: { flexDirection: 'row', flexWrap: 'wrap', paddingHorizontal: 12, paddingBottom: 10, gap: 8, alignItems: 'flex-start' },
  filterChip: { flexDirection: 'row', alignItems: 'center', gap: 5, paddingHorizontal: 14, paddingVertical: 7, borderRadius: 20, borderWidth: 1, alignSelf: 'flex-start' },
  filterText: { fontSize: 13, fontWeight: '600' },

  scrollContainer: { flex: 1 },
  scroll: { paddingBottom: 0 },

  // Date headers
  dateLabelRow: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 12, gap: 12 },
  dateLine: { flex: 1, height: 1 },
  dateLabel: { fontSize: 12, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 1.2 },

  // ── Photo Moment Card ──
  photoCard: { marginHorizontal: 12, marginBottom: 12, borderRadius: 20, overflow: 'hidden' },
  photoHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 14, paddingTop: 14, paddingBottom: 10 },
  photoHeaderLeft: { flexDirection: 'row', alignItems: 'center', gap: 10, flex: 1 },
  smallAvatar: { width: 36, height: 36, borderRadius: 18 },
  smallAvatarPlaceholder: { width: 36, height: 36, borderRadius: 18, alignItems: 'center', justifyContent: 'center' },
  photoName: { fontSize: 15, fontWeight: '700' },
  photoTime: { fontSize: 12 },
  eventBadge: { width: 32, height: 32, borderRadius: 16, alignItems: 'center', justifyContent: 'center' },
  photoImage: { paddingHorizontal: 12 },
  photoPlaceholder: { marginHorizontal: 12, height: 160, borderRadius: 12, alignItems: 'center', justifyContent: 'center' },
  photoCaption: { paddingHorizontal: 14, paddingTop: 10, paddingBottom: 14 },
  photoCaptionTitle: { fontSize: 15, fontWeight: '700' },
  photoCaptionDesc: { fontSize: 14, marginTop: 3, lineHeight: 19 },
  vehicleTag: { flexDirection: 'row', alignItems: 'center', gap: 5, marginTop: 8, paddingHorizontal: 8, paddingVertical: 4, borderRadius: 8, alignSelf: 'flex-start' },
  vehicleText: { fontSize: 12, fontWeight: '600' },

  // ── Engagement Card ──
  engagementCard: { marginHorizontal: 12, marginBottom: 6, borderRadius: 14, overflow: 'hidden', flexDirection: 'row' },
  engagementStripe: { width: 3 },
  engagementBody: { flex: 1, flexDirection: 'row', alignItems: 'center', padding: 12, gap: 12 },
  engagementLeft: {},
  engagementAvatar: { width: 44, height: 44, borderRadius: 22 },
  engagementAvatarPlaceholder: { width: 44, height: 44, borderRadius: 22, alignItems: 'center', justifyContent: 'center' },
  engagementContent: { flex: 1 },
  engagementName: { fontSize: 15, fontWeight: '700' },
  engagementAction: { fontWeight: '400', fontSize: 14 },
  engagementTime: { fontSize: 12 },

  // ── Milestone Card ──
  milestoneCard: { marginHorizontal: 12, marginBottom: 8, borderRadius: 14, borderWidth: 1, flexDirection: 'row', alignItems: 'center', padding: 14, gap: 12, borderStyle: 'dashed' },
  milestoneIcon: { width: 44, height: 44, borderRadius: 22, alignItems: 'center', justifyContent: 'center' },
  milestoneContent: { flex: 1 },
  milestoneLabel: { fontSize: 11, fontWeight: '800', textTransform: 'uppercase', letterSpacing: 0.5 },
  milestoneName: { fontSize: 16, fontWeight: '700', marginTop: 2 },
  milestoneDesc: { fontSize: 13, marginTop: 2 },
  milestoneTime: { fontSize: 12 },

  // ── Text Event Card ──
  textCard: { flexDirection: 'row', alignItems: 'center', marginHorizontal: 12, marginBottom: 4, borderRadius: 14, padding: 12, gap: 12 },
  textAvatarWrap: { position: 'relative' },
  textAvatar: { width: 44, height: 44, borderRadius: 12 },
  textAvatarPlaceholder: { width: 44, height: 44, borderRadius: 12, alignItems: 'center', justifyContent: 'center' },
  textIconBadge: { position: 'absolute', bottom: -2, right: -2, width: 18, height: 18, borderRadius: 9, alignItems: 'center', justifyContent: 'center', borderWidth: 2 },
  textContent: { flex: 1 },
  textName: { fontSize: 15, fontWeight: '700' },
  textTitle: { fontSize: 14, marginTop: 1 },
  textDesc: { fontSize: 13, marginTop: 1 },
  textTime: { fontSize: 12 },
  inboundBadge: { backgroundColor: '#30D15820', paddingHorizontal: 5, paddingVertical: 1, borderRadius: 4 },
  inboundText: { fontSize: 9, fontWeight: '700', color: '#30D158' },

  // Empty
  empty: { alignItems: 'center', paddingVertical: 80 },
  emptyIcon: { width: 64, height: 64, borderRadius: 32, alignItems: 'center', justifyContent: 'center', marginBottom: 12 },
  emptyText: { fontSize: 18, fontWeight: '700' },
  emptySubtext: { fontSize: 14, marginTop: 4, textAlign: 'center', paddingHorizontal: 40 },
});
