import React, { useState, useEffect, useCallback } from 'react';
import { View, Text, TouchableOpacity, ScrollView, ActivityIndicator, Modal, FlatList } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { useAuthStore } from '../../store/authStore';
import { useThemeStore } from '../../store/themeStore';
import api, { tasksAPI } from '../../services/api';

const PERIODS = [
  { key: 'today', label: 'Today' },
  { key: 'week', label: 'This Week' },
  { key: 'month', label: 'This Month' },
  { key: 'all', label: 'All Time' },
];

// Push notification helpers
const IS_WEB = typeof window !== 'undefined';

async function registerPushNotifications(userId: string) {
  if (!IS_WEB || !('serviceWorker' in navigator) || !('PushManager' in window)) return;
  try {
    const reg = await navigator.serviceWorker.register('/sw-push.js');
    const existing = await reg.pushManager.getSubscription();
    if (existing) return; // Already subscribed

    const vapidKey = process.env.EXPO_PUBLIC_VAPID_KEY;
    if (!vapidKey) return;

    // Convert VAPID key
    const padding = '='.repeat((4 - (vapidKey.length % 4)) % 4);
    const base64 = (vapidKey + padding).replace(/-/g, '+').replace(/_/g, '/');
    const raw = Uint8Array.from(atob(base64), c => c.charCodeAt(0));

    const sub = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: raw,
    });

    await api.post(`/push/subscribe/${userId}`, { subscription: sub.toJSON() });
  } catch (e) {
    console.log('Push registration skipped:', e);
  }
}

export default function PerformanceScreen() {
  const { colors } = useThemeStore();
  const router = useRouter();
  const user = useAuthStore((s) => s.user);
  const { period: periodParam } = useLocalSearchParams<{ period?: string }>();
  const [period, setPeriod] = useState(periodParam === 'today' ? 'today' : periodParam === 'month' ? 'month' : 'week');
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [detailModal, setDetailModal] = useState<{ visible: boolean; title: string; category: string; events: any[] }>({ visible: false, title: '', category: '', events: [] });
  const [detailLoading, setDetailLoading] = useState(false);

  useEffect(() => { loadData(); }, [user?._id, period]);

  // Register push notifications on first load
  useEffect(() => {
    if (user?._id) registerPushNotifications(user._id);
  }, [user?._id]);

  const loadData = async () => {
    if (!user?._id) return;
    setLoading(true);
    try {
      const res = await tasksAPI.getPerformance(user._id, period);
      setData(res);
    } catch (e) { console.error(e); }
    setLoading(false);
  };

  const openDetail = useCallback(async (title: string, category: string) => {
    if (!user?._id) return;
    setDetailModal({ visible: true, title, category, events: [] });
    setDetailLoading(true);
    try {
      const res = await api.get(`/tasks/${user._id}/performance/detail`, { params: { category, period } });
      setDetailModal(prev => ({ ...prev, events: res.data.events || [] }));
    } catch (e) { console.error(e); }
    setDetailLoading(false);
  }, [user?._id, period]);

  const trendUp = data?.trend_pct >= 0;
  const sc = data?.scorecard;
  const scDiff = sc?.diff || 0;
  const scUp = scDiff >= 0;

  const formatTime = (iso: string) => {
    const d = new Date(iso);
    const now = new Date();
    const diff = (now.getTime() - d.getTime()) / 1000;
    if (diff < 60) return 'Just now';
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  };

  const eventLabel = (t: string) => {
    const labels: Record<string, string> = {
      sms_sent: 'Text sent', sms_personal: 'Personal text', personal_sms: 'Personal text', sms_failed: 'Text (failed)',
      email_sent: 'Email sent', email_failed: 'Email (failed)',
      call_placed: 'Call placed', call_received: 'Call received',
      digital_card_shared: 'Digital card shared', card_shared: 'Card shared', digital_card_sent: 'Digital card sent',
      review_invite_sent: 'Review invite sent', review_shared: 'Review shared', review_request_sent: 'Review request',
      congrats_card_sent: 'Congrats card', birthday_card_sent: 'Birthday card', holiday_card_sent: 'Holiday card',
      thank_you_card_sent: 'Thank you card', anniversary_card_sent: 'Anniversary card',
      showroom_shared: 'Showcase shared',
      link_clicked: 'Link clicked', card_viewed: 'Card viewed', digital_card_viewed: 'Business card viewed',
      congrats_card_viewed: 'Congrats card viewed', birthday_card_viewed: 'Birthday card viewed', holiday_card_viewed: 'Holiday card viewed',
      review_link_clicked: 'Review link clicked', showcase_viewed: 'Showcase viewed', showroom_viewed: 'Showcase viewed',
      link_page_viewed: 'Link page viewed', email_opened: 'Email opened',
      reply_received: 'Reply received', sms_received: 'Text received',
      new_lead: 'New contact',
    };
    return labels[t] || t?.replace(/_/g, ' ') || '';
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      <View style={{ flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: 0.5, borderBottomColor: colors.border }} data-testid="performance-header">
        <TouchableOpacity onPress={() => router.back()} style={{ padding: 4, marginRight: 8 }} data-testid="performance-back-btn">
          <Ionicons name="chevron-back" size={24} color={colors.accent} />
        </TouchableOpacity>
        <Text style={{ fontSize: 19, fontWeight: '700', color: colors.text, flex: 1 }}>My Performance</Text>
      </View>

      <ScrollView style={{ flex: 1 }} contentContainerStyle={{ paddingBottom: 40 }} showsVerticalScrollIndicator={false}>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8, paddingHorizontal: 16, paddingVertical: 14 }}>
          {PERIODS.map(p => (
            <TouchableOpacity key={p.key} onPress={() => setPeriod(p.key)}
              style={{ paddingHorizontal: 16, paddingVertical: 8, borderRadius: 10, alignItems: 'center', borderWidth: 1,
                backgroundColor: period === p.key ? colors.accent : colors.card,
                borderColor: period === p.key ? colors.accent : colors.border }}
              data-testid={`period-${p.key}`}>
              <Text style={{ fontSize: 15, fontWeight: '600', color: period === p.key ? '#000' : colors.textSecondary }}>{p.label}</Text>
            </TouchableOpacity>
          ))}
        </ScrollView>

        {loading ? (
          <ActivityIndicator size="large" color={colors.accent} style={{ marginTop: 40 }} />
        ) : data ? (
          <>
            {/* Daily Scorecard */}
            {sc && (
              <View style={{ marginHorizontal: 16, marginBottom: 14, borderRadius: 14, padding: 16, borderWidth: 1, borderColor: scUp ? 'rgba(52,199,89,0.3)' : 'rgba(255,59,48,0.3)', backgroundColor: scUp ? 'rgba(52,199,89,0.06)' : 'rgba(255,59,48,0.06)' }} data-testid="daily-scorecard">
                <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
                  <View style={{ flex: 1 }}>
                    <Text style={{ fontSize: 15, fontWeight: '600', color: colors.textSecondary, textTransform: 'uppercase', letterSpacing: 1 }}>Today's Scorecard</Text>
                    <View style={{ flexDirection: 'row', alignItems: 'baseline', gap: 8, marginTop: 4 }}>
                      <Text style={{ fontSize: 36, fontWeight: '800', color: colors.text }}>{sc.today}</Text>
                      <Text style={{ fontSize: 16, color: colors.textSecondary }}>touchpoints</Text>
                    </View>
                  </View>
                  <View style={{ alignItems: 'flex-end' }}>
                    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4, paddingVertical: 5, paddingHorizontal: 10, borderRadius: 12, backgroundColor: scUp ? 'rgba(52,199,89,0.15)' : 'rgba(255,59,48,0.15)' }}>
                      <Ionicons name={scUp ? 'arrow-up' : 'arrow-down'} size={14} color={scUp ? '#34C759' : '#FF3B30'} />
                      <Text style={{ fontSize: 16, fontWeight: '700', color: scUp ? '#34C759' : '#FF3B30' }}>{Math.abs(scDiff)}</Text>
                    </View>
                    <Text style={{ fontSize: 13, color: colors.textSecondary, marginTop: 4 }}>vs yesterday ({sc.yesterday})</Text>
                  </View>
                </View>
                {/* Streak Counter */}
                <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginTop: 12, paddingTop: 12, borderTopWidth: 0.5, borderTopColor: scUp ? 'rgba(52,199,89,0.2)' : 'rgba(255,59,48,0.2)' }}>
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                    <Ionicons name="flame" size={18} color={sc.streak > 0 ? '#FF9500' : colors.textTertiary} />
                    <Text style={{ fontSize: 15, fontWeight: '600', color: sc.streak > 0 ? '#FF9500' : colors.textTertiary }}>
                      {sc.streak > 0 ? `${sc.streak}-day streak` : 'No active streak'}
                    </Text>
                    {sc.streak >= 7 && <Text style={{ fontSize: 13, color: '#FF9500', fontWeight: '700', backgroundColor: 'rgba(255,150,0,0.12)', paddingHorizontal: 6, paddingVertical: 2, borderRadius: 6, overflow: 'hidden' }}>ON FIRE</Text>}
                  </View>
                  <Text style={{ fontSize: 13, color: colors.textTertiary }}>
                    {sc.streak > 0
                      ? sc.today >= (sc.streak_threshold || 5) ? "Today counts! Keep going!" : `Need ${(sc.streak_threshold || 5) - sc.today} more to keep it alive`
                      : `Get ${sc.streak_threshold || 5}+ touchpoints to start`}
                  </Text>
                </View>
                <Text style={{ fontSize: 14, color: scUp ? '#34C759' : '#FF9500', fontWeight: '500', marginTop: 8 }}>
                  {sc.today === 0 ? "No touchpoints yet today — let's get started!" : scDiff > 0 ? "Great work! You're ahead of yesterday. Keep it up!" : scDiff === 0 ? "On pace with yesterday. Push for more!" : "Behind yesterday's pace. Time to make some moves!"}
                </Text>
              </View>
            )}

            {/* Personal Bests */}
            {data.personal_bests && (data.personal_bests.best_day > 0 || data.personal_bests.best_week > 0) && (
              <View style={{ marginHorizontal: 16, marginBottom: 14, flexDirection: 'row', gap: 8 }} data-testid="personal-bests">
                <View style={{ flex: 1, backgroundColor: colors.card, borderRadius: 12, padding: 12, borderWidth: 1, borderColor: colors.border, alignItems: 'center' }}>
                  <Ionicons name="trophy" size={18} color="#FFD60A" />
                  <Text style={{ fontSize: 22, fontWeight: '800', color: '#FFD60A', marginTop: 4 }}>{data.personal_bests.best_day}</Text>
                  <Text style={{ fontSize: 12, color: colors.textSecondary, fontWeight: '600' }}>BEST DAY</Text>
                  {data.personal_bests.best_day_date && (
                    <Text style={{ fontSize: 9, color: colors.textTertiary, marginTop: 2 }}>
                      {new Date(data.personal_bests.best_day_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                    </Text>
                  )}
                </View>
                <View style={{ flex: 1, backgroundColor: colors.card, borderRadius: 12, padding: 12, borderWidth: 1, borderColor: colors.border, alignItems: 'center' }}>
                  <Ionicons name="ribbon" size={18} color="#AF52DE" />
                  <Text style={{ fontSize: 22, fontWeight: '800', color: '#AF52DE', marginTop: 4 }}>{data.personal_bests.best_week}</Text>
                  <Text style={{ fontSize: 12, color: colors.textSecondary, fontWeight: '600' }}>BEST WEEK</Text>
                </View>
                <View style={{ flex: 1, backgroundColor: colors.card, borderRadius: 12, padding: 12, borderWidth: 1, borderColor: colors.border, alignItems: 'center' }}>
                  <Ionicons name="flash" size={18} color={sc && sc.today > data.personal_bests.best_day ? '#34C759' : colors.textSecondary} />
                  <Text style={{ fontSize: 22, fontWeight: '800', color: sc && sc.today > data.personal_bests.best_day ? '#34C759' : colors.text, marginTop: 4 }}>{sc?.today || 0}</Text>
                  <Text style={{ fontSize: 12, color: colors.textSecondary, fontWeight: '600' }}>TODAY</Text>
                  {sc && sc.today > data.personal_bests.best_day && (
                    <Text style={{ fontSize: 9, color: '#34C759', fontWeight: '700', marginTop: 2 }}>NEW RECORD!</Text>
                  )}
                  {sc && sc.today <= data.personal_bests.best_day && data.personal_bests.best_day > 0 && (
                    <Text style={{ fontSize: 9, color: colors.textTertiary, marginTop: 2 }}>
                      {data.personal_bests.best_day - sc.today} to beat
                    </Text>
                  )}
                </View>
              </View>
            )}

            {/* Period Summary */}
            <View style={{ marginHorizontal: 16, marginBottom: 14, backgroundColor: colors.card, borderRadius: 14, padding: 16, borderWidth: 1, borderColor: colors.border, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
              <View>
                <Text style={{ fontSize: 32, fontWeight: '800', color: colors.text }}>{data.total_touchpoints}</Text>
                <Text style={{ fontSize: 15, color: colors.textSecondary, marginTop: 2 }}>Total Touchpoints</Text>
              </View>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4, paddingVertical: 5, paddingHorizontal: 10, borderRadius: 12, backgroundColor: trendUp ? 'rgba(52,199,89,0.12)' : 'rgba(255,59,48,0.12)' }}>
                <Ionicons name={trendUp ? 'trending-up' : 'trending-down'} size={16} color={trendUp ? '#34C759' : '#FF3B30'} />
                <Text style={{ fontSize: 15, fontWeight: '700', color: trendUp ? '#34C759' : '#FF3B30' }}>{trendUp ? '+' : ''}{data.trend_pct}%</Text>
              </View>
            </View>

            <Text style={{ fontSize: 13, fontWeight: '700', color: '#48484A', letterSpacing: 1.5, paddingHorizontal: 16, paddingTop: 8, paddingBottom: 8 }}>COMMUNICATION</Text>
            <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8, paddingHorizontal: 16, paddingBottom: 8 }}>
              <StatCard icon="chatbubble" iconColor="#007AFF" iconBg="rgba(0,122,255,0.12)" value={data.communication?.texts || 0} label="TEXTS SENT" onPress={() => openDetail('Texts Sent', 'texts')} colors={colors} />
              <StatCard icon="mail" iconColor="#5856D6" iconBg="rgba(88,86,214,0.12)" value={data.communication?.emails || 0} label="EMAILS" onPress={() => openDetail('Emails', 'emails')} colors={colors} />
              <StatCard icon="call" iconColor="#34C759" iconBg="rgba(52,199,89,0.12)" value={data.communication?.calls || 0} label="CALLS" onPress={() => openDetail('Calls', 'calls')} colors={colors} />
            </View>

            <Text style={{ fontSize: 13, fontWeight: '700', color: '#48484A', letterSpacing: 1.5, paddingHorizontal: 16, paddingTop: 8, paddingBottom: 8 }}>SHARING</Text>
            <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8, paddingHorizontal: 16, paddingBottom: 8 }}>
              <StatCard icon="person-circle" iconColor="#C9A962" iconBg="rgba(201,169,98,0.12)" value={data.sharing?.my_card || 0} label="MY CARD" onPress={() => openDetail('My Card Shares', 'my_card')} colors={colors} />
              <StatCard icon="star" iconColor="#FFD60A" iconBg="rgba(255,214,10,0.12)" value={data.sharing?.reviews || 0} label="REVIEWS" onPress={() => openDetail('Review Invites', 'reviews')} colors={colors} />
              <StatCard icon="gift" iconColor="#FF9500" iconBg="rgba(255,150,0,0.12)" value={data.sharing?.card_shares || 0} label="CARD SHARES" onPress={() => openDetail('Card Shares', 'card_shares')} colors={colors} />
              <StatCard icon="storefront" iconColor="#34C759" iconBg="rgba(52,199,89,0.12)" value={data.sharing?.showcase || 0} label="SHOWCASE" onPress={() => openDetail('Showcase Shares', 'showcase')} colors={colors} />
            </View>

            <Text style={{ fontSize: 13, fontWeight: '700', color: '#48484A', letterSpacing: 1.5, paddingHorizontal: 16, paddingTop: 8, paddingBottom: 8 }}>ENGAGEMENT & CLICK-THROUGHS</Text>
            <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8, paddingHorizontal: 16, paddingBottom: 8 }}>
              <EngCard icon="finger-print" iconColor="#FF375F" iconBg="rgba(255,55,95,0.12)" title="Link Clicks" value={data.engagement?.link_clicks || 0} sub="People viewing your content" onPress={() => openDetail('Link Clicks', 'link_clicks')} colors={colors} />
              <EngCard icon="mail-open" iconColor="#AF52DE" iconBg="rgba(175,82,222,0.12)" title="Email Opens" value={data.engagement?.email_opens || 0} sub="Open rate" onPress={() => openDetail('Email Opens', 'email_opens')} colors={colors} />
              <EngCard icon="chatbubble-ellipses" iconColor="#FF9500" iconBg="rgba(255,150,0,0.12)" title="Replies" value={data.engagement?.replies || 0} sub="Customers responding" onPress={() => openDetail('Replies', 'replies')} colors={colors} />
              <EngCard icon="person-add" iconColor="#32ADE6" iconBg="rgba(50,173,230,0.12)" title="New Leads" value={data.engagement?.new_leads || 0} sub="Contacts added" onPress={() => openDetail('New Leads', 'new_leads')} colors={colors} />
            </View>

            <Text style={{ fontSize: 13, fontWeight: '700', color: '#48484A', letterSpacing: 1.5, paddingHorizontal: 16, paddingTop: 8, paddingBottom: 8 }}>CLICK-THROUGH BREAKDOWN</Text>
            <View style={{ marginHorizontal: 16, backgroundColor: colors.card, borderRadius: 14, borderWidth: 1, borderColor: colors.border, overflow: 'hidden' }}>
              <CtrRow icon="person-circle" iconColor="#C9A962" iconBg="rgba(201,169,98,0.12)" label="My Card Views" sub="People who opened your business card" value={data.click_through?.my_card_views || 0} valueColor="#C9A962" onPress={() => openDetail('My Card Views', 'my_card_views')} colors={colors} />
              <CtrRow icon="camera" iconColor="#FF9500" iconBg="rgba(255,150,0,0.12)" label="Customer Card Views" sub="People who opened cards you created" value={data.click_through?.customer_card_views || 0} valueColor="#FF9500" onPress={() => openDetail('Customer Card Views', 'customer_card_views')} colors={colors} />
              <CtrRow icon="star" iconColor="#FFD60A" iconBg="rgba(255,214,10,0.12)" label="Review Link Clicks" sub="People who clicked your review link" value={data.click_through?.review_link_clicks || 0} valueColor="#FFD60A" onPress={() => openDetail('Review Link Clicks', 'review_link_clicks')} colors={colors} />
              <CtrRow icon="storefront" iconColor="#34C759" iconBg="rgba(52,199,89,0.12)" label="Showcase Views" sub="People browsing your showcase" value={data.click_through?.showcase_views || 0} valueColor="#34C759" onPress={() => openDetail('Showcase Views', 'showcase_views')} colors={colors} />
              <CtrRow icon="link" iconColor="#AF52DE" iconBg="rgba(175,82,222,0.12)" label="Link Page Visits" sub="Your personal link page views" value={data.click_through?.link_page_visits || 0} valueColor="#AF52DE" onPress={() => openDetail('Link Page Visits', 'link_page_visits')} colors={colors} last />
            </View>
          </>
        ) : null}
      </ScrollView>

      {/* Detail Modal */}
      <Modal visible={detailModal.visible} transparent animationType="slide" onRequestClose={() => setDetailModal(prev => ({ ...prev, visible: false }))}>
        <View style={{ flex: 1, backgroundColor: 'rgba(0,0,0,0.5)', justifyContent: 'flex-end' }}>
          <View style={{ backgroundColor: colors.card, borderTopLeftRadius: 20, borderTopRightRadius: 20, maxHeight: '70%', paddingBottom: 30 }}>
            <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', padding: 16, borderBottomWidth: 0.5, borderBottomColor: colors.border }}>
              <Text style={{ fontSize: 18, fontWeight: '700', color: colors.text }}>{detailModal.title}</Text>
              <TouchableOpacity onPress={() => setDetailModal(prev => ({ ...prev, visible: false }))} data-testid="close-detail-modal">
                <Ionicons name="close-circle" size={28} color={colors.textSecondary} />
              </TouchableOpacity>
            </View>
            {detailLoading ? (
              <ActivityIndicator size="large" color={colors.accent} style={{ marginTop: 40 }} />
            ) : detailModal.events.length === 0 ? (
              <Text style={{ padding: 20, textAlign: 'center', color: colors.textSecondary }}>No activity in this period</Text>
            ) : (
              <FlatList
                data={detailModal.events}
                keyExtractor={(_, i) => String(i)}
                renderItem={({ item }) => (
                  <TouchableOpacity
                    style={{ flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: 0.5, borderBottomColor: colors.border }}
                    onPress={() => {
                      if (item.contact_id) {
                        setDetailModal(prev => ({ ...prev, visible: false }));
                        router.push(`/contact/${item.contact_id}` as any);
                      }
                    }}
                  >
                    <View style={{ flex: 1 }}>
                      <Text style={{ fontSize: 17, fontWeight: '600', color: colors.text }}>{item.contact_name || 'Unknown Contact'}</Text>
                      <Text style={{ fontSize: 14, color: colors.textSecondary, marginTop: 2 }}>{eventLabel(item.event_type)}{item.content ? ` - ${item.content.substring(0, 50)}` : ''}</Text>
                    </View>
                    <Text style={{ fontSize: 14, color: colors.textTertiary }}>{item.timestamp ? formatTime(item.timestamp) : ''}</Text>
                    {item.contact_id && <Ionicons name="chevron-forward" size={16} color={colors.textTertiary} style={{ marginLeft: 4 }} />}
                  </TouchableOpacity>
                )}
              />
            )}
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

function StatCard({ icon, iconColor, iconBg, value, label, colors, onPress }: any) {
  return (
    <TouchableOpacity
      style={{ flex: 1, flexBasis: '28%', maxWidth: '32%', backgroundColor: colors.card, borderRadius: 12, padding: 12, alignItems: 'center', borderWidth: 1, borderColor: colors.border }}
      onPress={onPress}
      activeOpacity={onPress ? 0.7 : 1}
      data-testid={`stat-${label.toLowerCase().replace(/\s/g, '-')}`}
    >
      <View style={{ width: 36, height: 36, borderRadius: 10, backgroundColor: iconBg, alignItems: 'center', justifyContent: 'center', marginBottom: 8 }}>
        <Ionicons name={icon} size={18} color={iconColor} />
      </View>
      <Text style={{ fontSize: 22, fontWeight: '700', color: colors.text }}>{value}</Text>
      <Text style={{ fontSize: 12, color: '#636366', fontWeight: '600', marginTop: 2 }}>{label}</Text>
    </TouchableOpacity>
  );
}

function EngCard({ icon, iconColor, iconBg, title, value, sub, colors, onPress }: any) {
  return (
    <TouchableOpacity
      style={{ flex: 1, minWidth: '45%', backgroundColor: colors.card, borderRadius: 12, padding: 14, borderWidth: 1, borderColor: colors.border }}
      onPress={onPress}
      activeOpacity={onPress ? 0.7 : 1}
      data-testid={`eng-${title.toLowerCase().replace(/\s/g, '-')}`}
    >
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 8 }}>
        <View style={{ width: 32, height: 32, borderRadius: 8, backgroundColor: iconBg, alignItems: 'center', justifyContent: 'center' }}>
          <Ionicons name={icon} size={16} color={iconColor} />
        </View>
        <Text style={{ fontSize: 14, color: colors.textSecondary, fontWeight: '600' }}>{title}</Text>
      </View>
      <Text style={{ fontSize: 26, fontWeight: '700', color: iconColor }}>{value}</Text>
      <Text style={{ fontSize: 13, color: '#636366', marginTop: 2 }}>{sub}</Text>
    </TouchableOpacity>
  );
}

function CtrRow({ icon, iconColor, iconBg, label, sub, value, valueColor, colors, last, onPress }: any) {
  return (
    <TouchableOpacity
      style={{ flexDirection: 'row', alignItems: 'center', padding: 12, paddingHorizontal: 16, gap: 12, borderBottomWidth: last ? 0 : 1, borderBottomColor: colors.border }}
      onPress={onPress}
      activeOpacity={onPress ? 0.7 : 1}
      data-testid={`ctr-${label.toLowerCase().replace(/\s/g, '-')}`}
    >
      <View style={{ width: 32, height: 32, borderRadius: 8, backgroundColor: iconBg, alignItems: 'center', justifyContent: 'center' }}>
        <Ionicons name={icon} size={16} color={iconColor} />
      </View>
      <View style={{ flex: 1 }}>
        <Text style={{ fontSize: 16, fontWeight: '600', color: colors.text }}>{label}</Text>
        <Text style={{ fontSize: 13, color: '#636366', marginTop: 1 }}>{sub}</Text>
      </View>
      <Text style={{ fontSize: 19, fontWeight: '700', color: valueColor }}>{value}</Text>
      {onPress && <Ionicons name="chevron-forward" size={16} color={colors.textTertiary} style={{ marginLeft: 4 }} />}
    </TouchableOpacity>
  );
}
