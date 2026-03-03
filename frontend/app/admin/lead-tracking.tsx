import React, { useState, useEffect, useCallback } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  ActivityIndicator, Platform, useWindowDimensions,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useThemeStore } from '../../store/themeStore';
import api from '../../services/api';

const PERIODS = [
  { label: '7d', days: 7 },
  { label: '30d', days: 30 },
  { label: '90d', days: 90 },
  { label: 'All', days: 3650 },
];

const CHANNEL_LABELS: Record<string, { label: string; icon: string; color: string }> = {
  organic: { label: 'Organic (Website)', icon: 'globe', color: '#007AFF' },
  paid_social: { label: 'Paid Social', icon: 'logo-instagram', color: '#FF2D55' },
  paid_search: { label: 'Paid Search', icon: 'search', color: '#FF9500' },
  sales_presentation: { label: 'Sales Presentation', icon: 'easel', color: '#5856D6' },
  in_app: { label: 'In-App', icon: 'phone-portrait', color: '#34C759' },
  email: { label: 'Email', icon: 'mail', color: '#FF3B30' },
  referral: { label: 'Referral', icon: 'people', color: '#AF52DE' },
  direct: { label: 'Direct', icon: 'navigate', color: '#8E8E93' },
};

const STATUS_COLORS: Record<string, string> = {
  new: '#007AFF',
  contacted: '#FF9500',
  scheduled: '#34C759',
  closed: '#8E8E93',
  lost: '#FF3B30',
};

interface Analytics {
  summary: {
    total_all_time: number;
    total_period: number;
    total_previous_period: number;
    total_new: number;
    period_days: number;
  };
  by_channel: { channel: string; count: number }[];
  by_page: { page: string; count: number }[];
  by_position: { position: string; count: number }[];
  by_source: { source: string; count: number }[];
  by_campaign: { campaign: string; utm_source: string; utm_medium: string; count: number }[];
  daily_trend: { date: string; count: number }[];
  recent_requests: any[];
}

export default function LeadTrackingDashboard() {
  const { colors } = useThemeStore();
  const router = useRouter();
  const { width } = useWindowDimensions();
  const isWide = width > 768;
  const [period, setPeriod] = useState(30);
  const [data, setData] = useState<Analytics | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get(`/demo-requests/analytics?days=${period}`);
      setData(res.data);
    } catch (e) {
      console.error('Failed to fetch analytics', e);
    }
    setLoading(false);
  }, [period]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const pctChange = data ? (
    data.summary.total_previous_period > 0
      ? Math.round(((data.summary.total_period - data.summary.total_previous_period) / data.summary.total_previous_period) * 100)
      : data.summary.total_period > 0 ? 100 : 0
  ) : 0;

  const topPage = data?.by_page?.[0];
  const topChannel = data?.by_channel?.[0];

  const formatPage = (p: string) => (p || 'unknown').replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
  const formatSource = (s: string) => (s || 'direct').replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());

  const maxBarVal = data?.by_page?.length ? Math.max(...data.by_page.map(p => p.count)) : 1;

  return (
    <View style={[s.container, { backgroundColor: colors.bg }]}>
      {/* Header */}
      <View style={s.header}>
        <TouchableOpacity onPress={() => router.back()} style={s.backBtn} data-testid="lead-tracking-back">
          <Ionicons name="arrow-back" size={22} color={colors.text} />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={[s.title, { color: colors.text }]}>Lead Tracking</Text>
          <Text style={[s.subtitle, { color: colors.textSecondary }]}>Demo requests & attribution</Text>
        </View>
        <TouchableOpacity onPress={fetchData} style={s.refreshBtn} data-testid="lead-tracking-refresh">
          <Ionicons name="refresh" size={18} color="#007AFF" />
        </TouchableOpacity>
      </View>

      {/* Period Tabs */}
      <View style={s.periodRow}>
        {PERIODS.map(p => (
          <TouchableOpacity
            key={p.days}
            style={[s.periodTab, period === p.days && s.periodTabActive]}
            onPress={() => setPeriod(p.days)}
            data-testid={`period-${p.label}`}
          >
            <Text style={[s.periodText, period === p.days && s.periodTextActive]}>{p.label}</Text>
          </TouchableOpacity>
        ))}
      </View>

      {loading ? (
        <View style={s.loadingWrap}><ActivityIndicator size="large" color="#007AFF" /></View>
      ) : !data ? (
        <View style={s.loadingWrap}><Text style={{ color: colors.textSecondary }}>No data available</Text></View>
      ) : (
        <ScrollView contentContainerStyle={s.scroll} showsVerticalScrollIndicator={false}>
          {/* Summary Cards */}
          <View style={[s.cardRow, isWide && { flexDirection: 'row' }]}>
            <View style={[s.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
              <Text style={[s.cardLabel, { color: colors.textSecondary }]}>Total Requests</Text>
              <Text style={[s.cardValue, { color: colors.text }]}>{data.summary.total_period}</Text>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4, marginTop: 4 }}>
                <Ionicons name={pctChange >= 0 ? 'trending-up' : 'trending-down'} size={14} color={pctChange >= 0 ? '#34C759' : '#FF3B30'} />
                <Text style={{ fontSize: 12, color: pctChange >= 0 ? '#34C759' : '#FF3B30', fontWeight: '600' }}>
                  {pctChange >= 0 ? '+' : ''}{pctChange}% vs prev
                </Text>
              </View>
            </View>
            <View style={[s.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
              <Text style={[s.cardLabel, { color: colors.textSecondary }]}>All Time</Text>
              <Text style={[s.cardValue, { color: colors.text }]}>{data.summary.total_all_time}</Text>
              <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 4 }}>{data.summary.total_new} awaiting response</Text>
            </View>
            <View style={[s.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
              <Text style={[s.cardLabel, { color: colors.textSecondary }]}>Top Page</Text>
              <Text style={[s.cardValue, { color: colors.text, fontSize: 18 }]}>{topPage ? formatPage(topPage.page) : '-'}</Text>
              <Text style={{ fontSize: 12, color: '#007AFF', fontWeight: '600', marginTop: 4 }}>{topPage?.count || 0} requests</Text>
            </View>
            <View style={[s.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
              <Text style={[s.cardLabel, { color: colors.textSecondary }]}>Top Channel</Text>
              <Text style={[s.cardValue, { color: colors.text, fontSize: 18 }]}>
                {topChannel ? (CHANNEL_LABELS[topChannel.channel]?.label || topChannel.channel) : '-'}
              </Text>
              <Text style={{ fontSize: 12, color: '#007AFF', fontWeight: '600', marginTop: 4 }}>{topChannel?.count || 0} requests</Text>
            </View>
          </View>

          {/* Channel Breakdown */}
          <View style={[s.section, { backgroundColor: colors.card, borderColor: colors.border }]}>
            <Text style={[s.sectionTitle, { color: colors.text }]}>By Channel</Text>
            <Text style={[s.sectionSub, { color: colors.textSecondary }]}>Where your leads are coming from</Text>
            {data.by_channel.length === 0 ? (
              <Text style={{ color: colors.textSecondary, fontSize: 14, textAlign: 'center', paddingVertical: 20 }}>No data yet. Leads will appear here as demo requests come in.</Text>
            ) : data.by_channel.map((ch, i) => {
              const info = CHANNEL_LABELS[ch.channel] || { label: ch.channel, icon: 'ellipse', color: '#8E8E93' };
              const pct = data.summary.total_period > 0 ? Math.round((ch.count / data.summary.total_period) * 100) : 0;
              return (
                <View key={i} style={s.channelRow}>
                  <View style={[s.channelIcon, { backgroundColor: info.color + '14' }]}>
                    <Ionicons name={info.icon as any} size={16} color={info.color} />
                  </View>
                  <Text style={[s.channelLabel, { color: colors.text }]}>{info.label}</Text>
                  <View style={s.channelBar}>
                    <View style={[s.channelBarFill, { width: `${pct}%`, backgroundColor: info.color }]} />
                  </View>
                  <Text style={[s.channelCount, { color: colors.text }]}>{ch.count}</Text>
                  <Text style={{ fontSize: 12, color: colors.textSecondary, width: 40, textAlign: 'right' }}>{pct}%</Text>
                </View>
              );
            })}
          </View>

          {/* Source Pages Breakdown */}
          <View style={[s.section, { backgroundColor: colors.card, borderColor: colors.border }]}>
            <Text style={[s.sectionTitle, { color: colors.text }]}>By Page</Text>
            <Text style={[s.sectionSub, { color: colors.textSecondary }]}>Which pages drive demo requests</Text>
            {data.by_page.length === 0 ? (
              <Text style={{ color: colors.textSecondary, fontSize: 14, textAlign: 'center', paddingVertical: 20 }}>No data yet.</Text>
            ) : data.by_page.slice(0, 12).map((pg, i) => (
              <View key={i} style={s.pageRow}>
                <Text style={[s.pageRank, { color: colors.textSecondary }]}>{i + 1}</Text>
                <View style={{ flex: 1 }}>
                  <Text style={[s.pageLabel, { color: colors.text }]}>{formatPage(pg.page)}</Text>
                  <View style={s.pageBarTrack}>
                    <View style={[s.pageBarFill, { width: `${(pg.count / maxBarVal) * 100}%` }]} />
                  </View>
                </View>
                <Text style={[s.pageCount, { color: colors.text }]}>{pg.count}</Text>
              </View>
            ))}
          </View>

          {/* CTA Position Breakdown */}
          <View style={[s.section, { backgroundColor: colors.card, borderColor: colors.border }]}>
            <Text style={[s.sectionTitle, { color: colors.text }]}>By CTA Position</Text>
            <Text style={[s.sectionSub, { color: colors.textSecondary }]}>Where on the page they click</Text>
            {data.by_position.length === 0 ? (
              <Text style={{ color: colors.textSecondary, fontSize: 14, textAlign: 'center', paddingVertical: 20 }}>No data yet.</Text>
            ) : (
              <View style={[s.posGrid, isWide && { flexDirection: 'row' }]}>
                {data.by_position.map((pos, i) => {
                  const icons: Record<string, string> = { nav: 'menu', hero: 'flag', cta: 'megaphone', footer: 'reorder-four', direct: 'link' };
                  const posColors: Record<string, string> = { nav: '#007AFF', hero: '#FF9500', cta: '#34C759', footer: '#AF52DE', direct: '#8E8E93' };
                  return (
                    <View key={i} style={[s.posCard, { backgroundColor: colors.surface, borderColor: colors.border }]}>
                      <Ionicons name={(icons[pos.position] || 'ellipse') as any} size={20} color={posColors[pos.position] || '#8E8E93'} />
                      <Text style={[s.posLabel, { color: colors.text }]}>{(pos.position || 'unknown').toUpperCase()}</Text>
                      <Text style={[s.posCount, { color: posColors[pos.position] || '#8E8E93' }]}>{pos.count}</Text>
                    </View>
                  );
                })}
              </View>
            )}
          </View>

          {/* Paid Campaigns (future-proofed) */}
          <View style={[s.section, { backgroundColor: colors.card, borderColor: colors.border }]}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
              <Text style={[s.sectionTitle, { color: colors.text }]}>Ad Campaigns</Text>
              {data.by_campaign.length === 0 && (
                <View style={{ backgroundColor: '#FF950020', paddingHorizontal: 8, paddingVertical: 2, borderRadius: 6 }}>
                  <Text style={{ fontSize: 10, fontWeight: '700', color: '#FF9500' }}>READY</Text>
                </View>
              )}
            </View>
            <Text style={[s.sectionSub, { color: colors.textSecondary }]}>
              {data.by_campaign.length === 0
                ? 'When you run ads, add UTM parameters to your links and campaigns will appear here automatically.'
                : 'Performance by UTM campaign'}
            </Text>
            {data.by_campaign.length === 0 ? (
              <View style={{ backgroundColor: colors.surface, borderRadius: 12, padding: 16, marginTop: 12, borderWidth: 1, borderColor: colors.border }}>
                <Text style={{ fontSize: 13, color: colors.textSecondary, lineHeight: 20 }}>
                  Example ad link:{'\n'}
                  <Text style={{ fontFamily: Platform.OS === 'web' ? 'monospace' : undefined, color: '#007AFF', fontSize: 12 }}>
                    imonsocial.com/demo/?utm_source=facebook&utm_medium=paid_social&utm_campaign=spring_launch
                  </Text>
                </Text>
              </View>
            ) : data.by_campaign.map((c, i) => (
              <View key={i} style={s.campaignRow}>
                <View style={{ flex: 1 }}>
                  <Text style={[s.campaignName, { color: colors.text }]}>{c.campaign}</Text>
                  <Text style={{ fontSize: 12, color: colors.textSecondary }}>{c.utm_source} / {c.utm_medium}</Text>
                </View>
                <Text style={[s.campaignCount, { color: '#007AFF' }]}>{c.count}</Text>
              </View>
            ))}
          </View>

          {/* Recent Requests */}
          <View style={[s.section, { backgroundColor: colors.card, borderColor: colors.border }]}>
            <Text style={[s.sectionTitle, { color: colors.text }]}>Recent Requests</Text>
            {data.recent_requests.length === 0 ? (
              <Text style={{ color: colors.textSecondary, fontSize: 14, textAlign: 'center', paddingVertical: 20 }}>No requests yet.</Text>
            ) : data.recent_requests.map((req, i) => (
              <View key={i} style={[s.requestRow, { borderBottomColor: colors.border }]}>
                <View style={{ flex: 1 }}>
                  <Text style={[s.requestName, { color: colors.text }]}>{req.name}</Text>
                  <Text style={{ fontSize: 12, color: colors.textSecondary }}>{req.email}{req.company ? ` - ${req.company}` : ''}</Text>
                  <Text style={{ fontSize: 11, color: colors.textTertiary, marginTop: 2 }}>{formatSource(req.source)}</Text>
                </View>
                <View style={{ alignItems: 'flex-end' }}>
                  <View style={[s.statusBadge, { backgroundColor: (STATUS_COLORS[req.status] || '#8E8E93') + '18' }]}>
                    <Text style={{ fontSize: 11, fontWeight: '700', color: STATUS_COLORS[req.status] || '#8E8E93' }}>
                      {(req.status || 'new').toUpperCase()}
                    </Text>
                  </View>
                  <Text style={{ fontSize: 11, color: colors.textTertiary, marginTop: 4 }}>
                    {req.created_at ? new Date(req.created_at).toLocaleDateString() : ''}
                  </Text>
                </View>
              </View>
            ))}
          </View>

          <View style={{ height: 40 }} />
        </ScrollView>
      )}
    </View>
  );
}

const s = StyleSheet.create({
  container: { flex: 1 },
  header: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingHorizontal: 16, paddingTop: Platform.OS === 'web' ? 20 : 56, paddingBottom: 12 },
  backBtn: { width: 36, height: 36, borderRadius: 18, backgroundColor: '#F5F5F7', alignItems: 'center', justifyContent: 'center' },
  title: { fontSize: 22, fontWeight: '800' },
  subtitle: { fontSize: 13, marginTop: 2 },
  refreshBtn: { width: 36, height: 36, borderRadius: 18, backgroundColor: '#007AFF12', alignItems: 'center', justifyContent: 'center' },
  periodRow: { flexDirection: 'row', paddingHorizontal: 16, gap: 8, marginBottom: 16 },
  periodTab: { paddingHorizontal: 16, paddingVertical: 8, borderRadius: 20, backgroundColor: '#F5F5F7' },
  periodTabActive: { backgroundColor: '#007AFF' },
  periodText: { fontSize: 13, fontWeight: '600', color: '#6E6E73' },
  periodTextActive: { color: '#FFF' },
  loadingWrap: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  scroll: { paddingHorizontal: 16, paddingBottom: 40 },
  cardRow: { gap: 12, marginBottom: 20 },
  card: { flex: 1, borderRadius: 16, padding: 16, borderWidth: 1, minWidth: 140 },
  cardLabel: { fontSize: 12, fontWeight: '600', textTransform: 'uppercase', letterSpacing: 0.5 },
  cardValue: { fontSize: 32, fontWeight: '900', marginTop: 4 },
  section: { borderRadius: 16, padding: 20, borderWidth: 1, marginBottom: 16 },
  sectionTitle: { fontSize: 17, fontWeight: '700' },
  sectionSub: { fontSize: 13, marginTop: 2, marginBottom: 16 },
  channelRow: { flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 12 },
  channelIcon: { width: 32, height: 32, borderRadius: 10, alignItems: 'center', justifyContent: 'center' },
  channelLabel: { fontSize: 14, fontWeight: '500', width: 140 },
  channelBar: { flex: 1, height: 6, borderRadius: 3, backgroundColor: '#F0F0F5', overflow: 'hidden' },
  channelBarFill: { height: '100%', borderRadius: 3 },
  channelCount: { fontSize: 15, fontWeight: '700', width: 36, textAlign: 'right' },
  pageRow: { flexDirection: 'row', alignItems: 'center', gap: 12, marginBottom: 14 },
  pageRank: { fontSize: 14, fontWeight: '700', width: 20, textAlign: 'center' },
  pageLabel: { fontSize: 14, fontWeight: '500', marginBottom: 4 },
  pageBarTrack: { height: 4, borderRadius: 2, backgroundColor: '#F0F0F5', overflow: 'hidden' },
  pageBarFill: { height: '100%', borderRadius: 2, backgroundColor: '#007AFF' },
  pageCount: { fontSize: 15, fontWeight: '700', width: 36, textAlign: 'right' },
  posGrid: { gap: 10, flexWrap: 'wrap' },
  posCard: { flex: 1, minWidth: 100, alignItems: 'center', padding: 16, borderRadius: 14, borderWidth: 1, gap: 6 },
  posLabel: { fontSize: 12, fontWeight: '700', letterSpacing: 0.5 },
  posCount: { fontSize: 24, fontWeight: '900' },
  campaignRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: '#F0F0F5' },
  campaignName: { fontSize: 14, fontWeight: '600' },
  campaignCount: { fontSize: 18, fontWeight: '800' },
  requestRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: 12, borderBottomWidth: 1 },
  requestName: { fontSize: 14, fontWeight: '600' },
  statusBadge: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 6 },
});
