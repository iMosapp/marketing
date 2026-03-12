import React, { useState, useEffect, useCallback } from 'react';
import { View, Text, TouchableOpacity, ScrollView, ActivityIndicator, Modal, FlatList } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useAuthStore } from '../../store/authStore';
import { useThemeStore } from '../../store/themeStore';
import api from '../../services/api';

const PERIODS = [
  { key: 'today', label: 'Today' },
  { key: 'week', label: 'This Week' },
  { key: 'month', label: 'This Month' },
  { key: 'all', label: 'All Time' },
];

const SCOPES = [
  { key: 'user', label: 'My Contacts' },
  { key: 'org', label: 'Organization' },
  { key: 'global', label: 'Global' },
];

// Human-readable labels for event types
const EVENT_LABELS: Record<string, string> = {
  digital_card_viewed: 'Viewed Card',
  congrats_card_viewed: 'Viewed Congrats Card',
  card_call_clicked: 'Clicked Call',
  card_text_clicked: 'Clicked Text',
  card_email_clicked: 'Clicked Email',
  card_social_clicked: 'Clicked Social Link',
  card_website_clicked: 'Clicked Website',
  vcard_saved: 'Saved Contact',
  card_share_clicked: 'Shared Card',
  review_submitted: 'Submitted Review',
  internal_review_submitted: 'Submitted Review',
  card_internal_review_submitted: 'Submitted Review',
  review_link_clicked: 'Clicked Review Link',
  card_review_clicked: 'Clicked Review',
  card_online_review_clicked: 'Clicked Online Review',
  card_refer_clicked: 'Referred a Friend',
  congrats_card_downloaded: 'Downloaded Card',
  congrats_card_shared: 'Shared Card',
  card_salesman_clicked: 'Viewed Salesman Card',
  link_page_link_clicked: 'Clicked Link',
  opt_in_clicked: 'Opted In',
  card_directions_clicked: 'Clicked Directions',
};

interface RankedContact {
  contact_id: string;
  name: string;
  phone: string;
  photo_url: string;
  tags: string[];
  score: number;
  event_count: number;
  last_activity: string;
  salesperson_id: string;
  breakdown: Record<string, number>;
}

export default function CustomerPerformanceScreen() {
  const { colors } = useThemeStore();
  const router = useRouter();
  const user = useAuthStore((s) => s.user);
  const [period, setPeriod] = useState('month');
  const [scope, setScope] = useState('user');
  const [rankings, setRankings] = useState<RankedContact[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedContact, setSelectedContact] = useState<RankedContact | null>(null);

  const loadRankings = useCallback(async () => {
    if (!user?._id) return;
    setLoading(true);
    try {
      const res = await api.get(`/tracking/customer-rankings/${user._id}?period=${period}&scope=${scope}`);
      setRankings(res.data.rankings || []);
    } catch (e) {
      console.error('Failed to load rankings:', e);
    } finally {
      setLoading(false);
    }
  }, [user?._id, period, scope]);

  useEffect(() => { loadRankings(); }, [loadRankings]);

  const getHeatColor = (score: number, maxScore: number) => {
    if (maxScore === 0) return '#48484A';
    const ratio = score / maxScore;
    if (ratio >= 0.7) return '#FF3B30';
    if (ratio >= 0.4) return '#FF9500';
    if (ratio >= 0.15) return '#FBBC04';
    return '#48484A';
  };

  const getHeatLabel = (score: number, maxScore: number) => {
    if (maxScore === 0) return 'No Activity';
    const ratio = score / maxScore;
    if (ratio >= 0.7) return 'Very Engaged';
    if (ratio >= 0.4) return 'Engaged';
    if (ratio >= 0.15) return 'Warm';
    return 'Cool';
  };

  const formatTimeAgo = (ts: string) => {
    if (!ts) return '';
    const diff = Date.now() - new Date(ts).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    const days = Math.floor(hrs / 24);
    return `${days}d ago`;
  };

  const maxScore = rankings.length > 0 ? rankings[0].score : 0;

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      {/* Header — matches My Performance */}
      <View style={{ flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: 0.5, borderBottomColor: colors.border }}>
        <TouchableOpacity onPress={() => router.back()} style={{ padding: 4, marginRight: 8 }} data-testid="back-btn">
          <Ionicons name="chevron-back" size={24} color={colors.accent} />
        </TouchableOpacity>
        <Text style={{ fontSize: 18, fontWeight: '700', color: colors.text, flex: 1 }}>Customer Performance</Text>
      </View>

      <ScrollView style={{ flex: 1 }} contentContainerStyle={{ paddingBottom: 40 }} showsVerticalScrollIndicator={false}>
        {/* Period Filters — horizontal scroll, compact pills */}
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8, paddingHorizontal: 16, paddingTop: 14, paddingBottom: 8 }}>
          {PERIODS.map(p => (
            <TouchableOpacity
              key={p.key}
              onPress={() => setPeriod(p.key)}
              style={{
                paddingHorizontal: 16, paddingVertical: 8, borderRadius: 10, alignItems: 'center', borderWidth: 1,
                backgroundColor: period === p.key ? colors.accent : colors.card,
                borderColor: period === p.key ? colors.accent : colors.border,
              }}
              data-testid={`period-${p.key}`}
            >
              <Text style={{ fontSize: 13, fontWeight: '600', color: period === p.key ? '#000' : colors.textSecondary }}>{p.label}</Text>
            </TouchableOpacity>
          ))}
        </ScrollView>

        {/* Scope Filters — horizontal scroll, compact pills, green accent */}
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8, paddingHorizontal: 16, paddingBottom: 14 }}>
          {SCOPES.map(s => (
            <TouchableOpacity
              key={s.key}
              onPress={() => setScope(s.key)}
              style={{
                paddingHorizontal: 16, paddingVertical: 8, borderRadius: 10, alignItems: 'center', borderWidth: 1,
                backgroundColor: scope === s.key ? '#34C759' : colors.card,
                borderColor: scope === s.key ? '#34C759' : colors.border,
              }}
              data-testid={`scope-${s.key}`}
            >
              <Text style={{ fontSize: 13, fontWeight: '600', color: scope === s.key ? '#000' : colors.textSecondary }}>{s.label}</Text>
            </TouchableOpacity>
          ))}
        </ScrollView>

        {/* Summary Stats */}
        {!loading && rankings.length > 0 && (
          <View style={{ flexDirection: 'row', justifyContent: 'space-between', marginHorizontal: 16, marginBottom: 12, paddingHorizontal: 4 }}>
            <Text style={{ fontSize: 12, color: colors.textSecondary }}>{rankings.length} active customers</Text>
            <Text style={{ fontSize: 12, color: colors.textSecondary }}>Top score: {maxScore}</Text>
          </View>
        )}

        {/* Rankings List */}
        {loading ? (
          <ActivityIndicator size="large" color={colors.accent} style={{ marginTop: 40 }} />
        ) : rankings.length === 0 ? (
          <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center', paddingHorizontal: 40, paddingTop: 60 }}>
            <Ionicons name="people-outline" size={48} color="#48484A" />
            <Text style={{ fontSize: 16, fontWeight: '600', color: colors.text, marginTop: 12, textAlign: 'center' }}>No Customer Activity</Text>
            <Text style={{ fontSize: 13, color: colors.textSecondary, marginTop: 6, textAlign: 'center' }}>
              When customers interact with your shared cards and links, their engagement will show up here.
            </Text>
          </View>
        ) : (
          <View style={{ paddingHorizontal: 16 }}>
            {rankings.map((contact, idx) => {
              const heatColor = getHeatColor(contact.score, maxScore);
              const heatLabel = getHeatLabel(contact.score, maxScore);
              const barWidth = maxScore > 0 ? Math.max(8, (contact.score / maxScore) * 100) : 0;
              
              return (
                <TouchableOpacity
                  key={contact.contact_id}
                  onPress={() => setSelectedContact(contact)}
                  activeOpacity={0.7}
                  style={{
                    flexDirection: 'row', alignItems: 'center', gap: 12,
                    backgroundColor: colors.card, borderRadius: 12, padding: 14,
                    borderWidth: 1, borderColor: colors.border, marginBottom: 8,
                  }}
                  data-testid={`customer-rank-${idx}`}
                >
                  {/* Rank Badge */}
                  <View style={{
                    width: 32, height: 32, borderRadius: 16,
                    backgroundColor: idx < 3 ? heatColor : '#2C2C2E',
                    alignItems: 'center', justifyContent: 'center',
                  }}>
                    <Text style={{ fontSize: 13, fontWeight: '700', color: idx < 3 ? '#FFF' : colors.textSecondary }}>
                      {idx + 1}
                    </Text>
                  </View>

                  {/* Contact Info */}
                  <View style={{ flex: 1 }}>
                    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                      <Text style={{ fontSize: 15, fontWeight: '600', color: colors.text, flexShrink: 1 }} numberOfLines={1}>{contact.name}</Text>
                      <Text style={{ fontSize: 10, fontWeight: '700', color: heatColor, backgroundColor: `${heatColor}18`, paddingHorizontal: 8, paddingVertical: 2, borderRadius: 8, overflow: 'hidden' }}>
                        {heatLabel}
                      </Text>
                    </View>
                    {/* Score bar */}
                    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                      <View style={{ flex: 1, height: 4, backgroundColor: colors.border, borderRadius: 2, overflow: 'hidden' }}>
                        <View style={{ height: '100%', width: `${barWidth}%`, backgroundColor: heatColor, borderRadius: 2 }} />
                      </View>
                    </View>
                    <Text style={{ fontSize: 11, color: colors.textSecondary, marginTop: 4 }}>
                      {contact.event_count} interactions{contact.last_activity ? `  -  ${formatTimeAgo(contact.last_activity)}` : ''}
                    </Text>
                  </View>

                  {/* Score */}
                  <Text style={{ fontSize: 18, fontWeight: '700', color: heatColor, minWidth: 36, textAlign: 'right' }}>{contact.score}</Text>
                  <Ionicons name="chevron-forward" size={16} color="#48484A" />
                </TouchableOpacity>
              );
            })}
          </View>
        )}
      </ScrollView>

      {/* Detail Modal */}
      <Modal visible={!!selectedContact} animationType="slide" transparent>
        <View style={{ flex: 1, backgroundColor: 'rgba(0,0,0,0.5)', justifyContent: 'flex-end' }}>
          <View style={{ backgroundColor: colors.bg, borderTopLeftRadius: 20, borderTopRightRadius: 20, maxHeight: '75%', paddingBottom: 30 }}>
            {/* Handle */}
            <View style={{ alignItems: 'center', paddingVertical: 10 }}>
              <View style={{ width: 36, height: 4, borderRadius: 2, backgroundColor: colors.border }} />
            </View>

            {selectedContact && (
              <>
                {/* Header */}
                <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 20, paddingBottom: 14, borderBottomWidth: 1, borderBottomColor: colors.border }}>
                  <View>
                    <Text style={{ fontSize: 18, fontWeight: '700', color: colors.text }}>{selectedContact.name}</Text>
                    <Text style={{ fontSize: 13, color: colors.textSecondary, marginTop: 2 }}>
                      Score: {selectedContact.score} - {selectedContact.event_count} interactions
                    </Text>
                  </View>
                  <TouchableOpacity onPress={() => setSelectedContact(null)} data-testid="close-detail-modal">
                    <Ionicons name="close-circle" size={28} color="#48484A" />
                  </TouchableOpacity>
                </View>

                {/* Breakdown */}
                <ScrollView contentContainerStyle={{ padding: 20 }}>
                  <Text style={{ fontSize: 14, fontWeight: '600', color: colors.text, marginBottom: 12 }}>Activity Breakdown</Text>
                  {Object.entries(selectedContact.breakdown)
                    .sort((a, b) => b[1] - a[1])
                    .map(([eventType, count]) => (
                      <View key={eventType} style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: colors.border }}>
                        <Text style={{ fontSize: 13, color: colors.text, flex: 1 }}>
                          {EVENT_LABELS[eventType] || eventType.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
                        </Text>
                        <View style={{ backgroundColor: 'rgba(201,169,98,0.12)', paddingHorizontal: 10, paddingVertical: 3, borderRadius: 10 }}>
                          <Text style={{ fontSize: 12, fontWeight: '700', color: colors.accent }}>{count}</Text>
                        </View>
                      </View>
                    ))
                  }
                  
                  {/* View Contact Button */}
                  <TouchableOpacity
                    onPress={() => {
                      setSelectedContact(null);
                      router.push(`/contact/${selectedContact.contact_id}` as any);
                    }}
                    style={{
                      marginTop: 20, backgroundColor: colors.accent, borderRadius: 12,
                      padding: 14, alignItems: 'center',
                    }}
                    data-testid="view-contact-btn"
                  >
                    <Text style={{ fontSize: 15, fontWeight: '600', color: '#000' }}>View Contact</Text>
                  </TouchableOpacity>
                </ScrollView>
              </>
            )}
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}
