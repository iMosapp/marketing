import React, { useState, useEffect, useCallback } from 'react';
import {
  View, Text, ScrollView, TouchableOpacity, StyleSheet, Image,
  ActivityIndicator, RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import * as Haptics from 'expo-haptics';
import { useAuthStore } from '../../store/authStore';
import { useThemeStore } from '../../store/themeStore';
import api from '../../services/api';

const FEED_EVENT_LABELS: Record<string, string> = {
  email_sent: 'Email Sent',
  personal_sms: 'Text Sent',
  digital_card_sent: 'Shared Contact Card',
  review_request_sent: 'Review Invite Sent',
  congrats_card_sent: 'Congrats Card Sent',
  vcard_sent: 'Shared vCard',
  call_placed: 'Call Placed',
  customer_reply: 'Customer Reply',
  congrats_card_viewed: 'Viewed Congrats Card',
  congrats_card_download: 'Downloaded Card',
  congrats_card_share: 'Shared Card',
  review_submitted: 'Left a Review',
  review_link_clicked: 'Clicked Review Link',
  link_page_shared: 'Link Page Shared',
};

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

const groupByDate = (items: any[]) => {
  const groups: Record<string, any[]> = {};
  const now = new Date();
  const nowDay = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  items.forEach(item => {
    if (!item.timestamp) return;
    const d = new Date(item.timestamp);
    const evtDay = new Date(d.getFullYear(), d.getMonth(), d.getDate());
    const days = Math.round((nowDay.getTime() - evtDay.getTime()) / 86400000);
    let label = days < 0 ? (days === -1 ? 'Tomorrow' : 'Upcoming') : days === 0 ? 'Today' : days === 1 ? 'Yesterday' : days < 7 ? `${days} days ago` : d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
    if (!groups[label]) groups[label] = [];
    groups[label].push(item);
  });
  return groups;
};

export default function ActivityTab() {
  const { user } = useAuthStore();
  const colors = useThemeStore((state) => state.colors);
  const router = useRouter();
  const userId = user?._id;

  const [feed, setFeed] = useState<any[]>([]);
  const [suggested, setSuggested] = useState<any[]>([]);
  const [upcoming, setUpcoming] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [collapsedGroups, setCollapsedGroups] = useState<Record<string, boolean>>({});

  const loadFeed = useCallback(async () => {
    if (!userId) return;
    try {
      const resp = await api.get(`/contacts/${userId}/master-feed?limit=100`);
      setFeed(resp.data.feed || []);
      setSuggested(resp.data.suggested || []);
      setUpcoming(resp.data.upcoming || []);
    } catch (e) {
      console.error('Failed to load activity feed:', e);
    } finally {
      setLoading(false);
    }
  }, [userId]);

  useEffect(() => { loadFeed(); }, [loadFeed]);

  const onRefresh = async () => {
    setRefreshing(true);
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    await loadFeed();
    setRefreshing(false);
  };

  const grouped = groupByDate(feed);

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
        <Text style={s.headerTitle}>Activity</Text>
        <Text style={s.headerSubtitle}>{feed.length} events across all contacts</Text>
      </View>

      <ScrollView
        contentContainerStyle={s.scroll}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#C9A962" />}
        showsVerticalScrollIndicator={false}
      >
        {/* Action Items */}
        {suggested.length > 0 && (
          <View style={s.section}>
            <View style={s.sectionHeader}>
              <Ionicons name="bulb" size={16} color="#FF9500" />
              <Text style={s.sectionTitle}>Action Items</Text>
              <View style={s.badge}><Text style={s.badgeText}>{suggested.length}</Text></View>
            </View>
            {suggested.map((item: any, idx: number) => (
              <TouchableOpacity
                key={`sug-${idx}`}
                style={s.actionCard}
                onPress={() => item.contact?.id && router.push(`/contact/${item.contact.id}`)}
                activeOpacity={0.7}
                data-testid={`activity-suggested-${idx}`}
              >
                <View style={[s.actionIcon, { backgroundColor: `${item.color}20` }]}>
                  <Ionicons name={(item.icon || 'flag') as any} size={20} color={item.color} />
                </View>
                <View style={{ flex: 1, marginLeft: 12 }}>
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                    {item.contact?.photo ? (
                      <Image source={{ uri: item.contact.photo }} style={s.miniAvatar} />
                    ) : (
                      <View style={s.miniAvatarPlaceholder}>
                        <Text style={s.miniAvatarText}>{item.contact?.name?.[0] || '?'}</Text>
                      </View>
                    )}
                    <Text style={s.actionName}>{item.contact?.name}</Text>
                  </View>
                  <Text style={s.actionTitle}>{item.title}</Text>
                  <Text style={s.actionDesc}>{item.description}</Text>
                  {item.suggested_message && (
                    <View style={s.msgPreview}>
                      <Text style={s.msgPreviewText} numberOfLines={2}>"{item.suggested_message}"</Text>
                    </View>
                  )}
                </View>
                <Ionicons name="chevron-forward" size={16} color="#3A3A3C" />
              </TouchableOpacity>
            ))}
          </View>
        )}

        {/* Upcoming Campaigns */}
        {upcoming.length > 0 && (
          <View style={s.section}>
            <View style={s.sectionHeader}>
              <Ionicons name="rocket" size={16} color="#AF52DE" />
              <Text style={s.sectionTitle}>Upcoming</Text>
            </View>
            {upcoming.map((item: any, idx: number) => (
              <TouchableOpacity
                key={`up-${idx}`}
                style={s.upcomingCard}
                onPress={() => item.contact?.id && router.push(`/contact/${item.contact.id}`)}
                activeOpacity={0.7}
              >
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                  {item.contact?.photo ? (
                    <Image source={{ uri: item.contact.photo }} style={s.miniAvatar} />
                  ) : (
                    <View style={s.miniAvatarPlaceholder}>
                      <Text style={s.miniAvatarText}>{item.contact?.name?.[0] || '?'}</Text>
                    </View>
                  )}
                  <View style={{ flex: 1 }}>
                    <Text style={s.upcomingName}>{item.contact?.name}</Text>
                    <Text style={s.upcomingDesc}>{item.description}</Text>
                  </View>
                  <View style={s.campaignBadge}>
                    <Text style={s.campaignBadgeText}>{item.campaign_name}</Text>
                  </View>
                </View>
              </TouchableOpacity>
            ))}
          </View>
        )}

        {/* Feed grouped by date */}
        {Object.keys(grouped).length === 0 ? (
          <View style={s.empty}>
            <Ionicons name="pulse-outline" size={48} color="#2C2C2E" />
            <Text style={s.emptyText}>No activity yet</Text>
            <Text style={s.emptySubtext}>Send a message or card to get started</Text>
          </View>
        ) : (
          Object.entries(grouped).map(([dateLabel, events]) => {
            const isCollapsed = collapsedGroups[dateLabel] === true;
            const eventCount = (events as any[]).length;
            return (
            <View key={dateLabel} style={s.dateGroup}>
              <TouchableOpacity
                style={s.dateLabelRow}
                onPress={() => setCollapsedGroups(prev => ({ ...prev, [dateLabel]: !prev[dateLabel] }))}
                activeOpacity={0.7}
                data-testid={`activity-date-toggle-${dateLabel}`}
              >
                <View style={s.dateLine} />
                <Text style={s.dateLabel}>{dateLabel}</Text>
                <View style={s.dateBadge}><Text style={s.dateBadgeText}>{eventCount}</Text></View>
                <Ionicons name={isCollapsed ? 'chevron-down' : 'chevron-up'} size={14} color="#636366" />
                <View style={s.dateLine} />
              </TouchableOpacity>
              {!isCollapsed && (events as any[]).map((item: any, idx: number) => {
                const isInbound = item.is_inbound;
                const evtLabel = FEED_EVENT_LABELS[item.event_type] || item.title || 'Activity';
                return (
                  <TouchableOpacity
                    key={`evt-${idx}`}
                    style={s.eventCard}
                    onPress={() => item.contact?.id && router.push(`/contact/${item.contact.id}`)}
                    activeOpacity={0.7}
                    data-testid={`activity-event-${dateLabel}-${idx}`}
                  >
                    <View style={s.avatarGroup}>
                      {item.contact?.photo ? (
                        <Image source={{ uri: item.contact.photo }} style={s.eventAvatar} />
                      ) : (
                        <View style={s.eventAvatarPlaceholder}>
                          <Text style={s.eventAvatarText}>{item.contact?.name?.[0] || '?'}</Text>
                        </View>
                      )}
                      <View style={[s.eventIconBadge, { backgroundColor: item.color || '#007AFF' }]}>
                        <Ionicons name={(item.icon || 'flag') as any} size={10} color="#FFF" />
                      </View>
                    </View>
                    <View style={s.eventContent}>
                      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                        <Text style={s.eventName} numberOfLines={1}>{item.contact?.name || 'Unknown'}</Text>
                        {isInbound && <View style={s.inboundBadge}><Text style={s.inboundText}>INBOUND</Text></View>}
                        {item.contact?.tags?.slice(0, 2).map((t: string, ti: number) => (
                          <View key={ti} style={s.miniTag}><Text style={s.miniTagText}>{t}</Text></View>
                        ))}
                      </View>
                      <Text style={[s.eventTitle, isInbound && { color: '#30D158' }]}>
                        {isInbound ? `"${item.description}"` : evtLabel}
                      </Text>
                      {!isInbound && item.description && item.description !== evtLabel && (
                        <Text style={s.eventDesc} numberOfLines={1}>{item.description}</Text>
                      )}
                    </View>
                    <Text style={s.eventTime}>{formatFeedTime(item.timestamp)}</Text>
                  </TouchableOpacity>
                );
              })}
            </View>
            );
          })
        )}
        <View style={{ height: 40 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#000' },
  header: { paddingHorizontal: 16, paddingTop: 8, paddingBottom: 12 },
  headerTitle: { fontSize: 28, fontWeight: '800', color: '#FFF' },
  headerSubtitle: { fontSize: 13, color: '#636366', marginTop: 2 },
  scroll: { paddingBottom: 20 },

  // Section
  section: { marginBottom: 12 },
  sectionHeader: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingHorizontal: 16, paddingVertical: 10 },
  sectionTitle: { fontSize: 15, fontWeight: '700', color: '#FFF', flex: 1 },
  badge: { backgroundColor: '#FF9500', borderRadius: 10, minWidth: 20, height: 20, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 6 },
  badgeText: { fontSize: 11, fontWeight: '800', color: '#000' },

  // Action cards
  actionCard: {
    flexDirection: 'row', alignItems: 'center', marginHorizontal: 12, marginBottom: 6,
    backgroundColor: '#1C1C1E', borderRadius: 14, padding: 14,
    borderWidth: 1, borderColor: '#2C2C2E',
  },
  actionIcon: { width: 44, height: 44, borderRadius: 22, alignItems: 'center', justifyContent: 'center' },
  actionName: { fontSize: 14, fontWeight: '700', color: '#FFF' },
  actionTitle: { fontSize: 13, fontWeight: '600', color: '#C9A962', marginTop: 4 },
  actionDesc: { fontSize: 12, color: '#8E8E93', marginTop: 2 },
  msgPreview: { marginTop: 6, backgroundColor: '#0D0D0D', borderRadius: 8, padding: 8, borderWidth: 1, borderColor: '#2C2C2E' },
  msgPreviewText: { fontSize: 11, color: '#FFFFFFAA', fontStyle: 'italic', lineHeight: 16 },

  // Mini avatar
  miniAvatar: { width: 24, height: 24, borderRadius: 7, borderWidth: 1, borderColor: '#2C2C2E' },
  miniAvatarPlaceholder: { width: 24, height: 24, borderRadius: 7, backgroundColor: '#2C2C2E', alignItems: 'center', justifyContent: 'center' },
  miniAvatarText: { fontSize: 11, fontWeight: '700', color: '#636366' },

  // Upcoming
  upcomingCard: {
    marginHorizontal: 12, marginBottom: 6, backgroundColor: '#1C1C1E',
    borderRadius: 14, padding: 12, borderWidth: 1, borderColor: '#AF52DE30',
  },
  upcomingName: { fontSize: 14, fontWeight: '600', color: '#FFF' },
  upcomingDesc: { fontSize: 12, color: '#8E8E93', marginTop: 1 },
  campaignBadge: { backgroundColor: '#AF52DE20', paddingHorizontal: 8, paddingVertical: 3, borderRadius: 6 },
  campaignBadgeText: { fontSize: 10, fontWeight: '600', color: '#AF52DE' },

  // Date groups
  dateGroup: { marginBottom: 4 },
  dateLabelRow: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 8, gap: 12 },
  dateLine: { flex: 1, height: 1, backgroundColor: '#1C1C1E' },
  dateLabel: { fontSize: 12, fontWeight: '700', color: '#636366', textTransform: 'uppercase', letterSpacing: 1 },
  dateBadge: { backgroundColor: '#1C1C1E', paddingHorizontal: 6, paddingVertical: 2, borderRadius: 8, borderWidth: 1, borderColor: '#2C2C2E' },
  dateBadgeText: { fontSize: 10, fontWeight: '700', color: '#636366' },

  // Event cards
  eventCard: {
    flexDirection: 'row', alignItems: 'center', marginHorizontal: 12, marginBottom: 4,
    backgroundColor: '#1C1C1E', borderRadius: 14, padding: 12,
  },
  avatarGroup: { position: 'relative', marginRight: 10 },
  eventAvatar: { width: 44, height: 44, borderRadius: 12, borderWidth: 1, borderColor: '#2C2C2E' },
  eventAvatarPlaceholder: { width: 44, height: 44, borderRadius: 12, backgroundColor: '#2C2C2E', alignItems: 'center', justifyContent: 'center' },
  eventAvatarText: { fontSize: 16, fontWeight: '700', color: '#636366' },
  eventIconBadge: {
    position: 'absolute', bottom: -3, right: -3,
    width: 20, height: 20, borderRadius: 10,
    alignItems: 'center', justifyContent: 'center',
    borderWidth: 2, borderColor: '#1C1C1E',
  },
  eventContent: { flex: 1 },
  eventName: { fontSize: 14, fontWeight: '700', color: '#FFF' },
  eventTitle: { fontSize: 13, color: '#8E8E93', marginTop: 1 },
  eventDesc: { fontSize: 12, color: '#636366', marginTop: 1 },
  eventTime: { fontSize: 11, color: '#3A3A3C', fontWeight: '500', marginLeft: 6 },
  inboundBadge: { backgroundColor: '#30D15820', paddingHorizontal: 5, paddingVertical: 1, borderRadius: 4 },
  inboundText: { fontSize: 8, fontWeight: '700', color: '#30D158' },
  miniTag: { backgroundColor: '#2C2C2E', paddingHorizontal: 5, paddingVertical: 1, borderRadius: 4 },
  miniTagText: { fontSize: 8, fontWeight: '600', color: '#636366' },

  // Empty
  empty: { alignItems: 'center', paddingVertical: 60 },
  emptyText: { fontSize: 18, color: '#8E8E93', marginTop: 10, fontWeight: '600' },
  emptySubtext: { fontSize: 13, color: '#636366', marginTop: 4 },
});
