import React, { useState, useCallback, useEffect, useMemo } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  ScrollView,
  StyleSheet,
  ActivityIndicator,
  RefreshControl,
  Dimensions,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import api from '../../services/api';
import { useAuthStore } from '../../store/authStore';

import { useThemeStore } from '../../store/themeStore';
const PERIODS = [
  { key: 7, label: '7D' },
  { key: 14, label: '14D' },
  { key: 30, label: '30D' },
  { key: 90, label: '90D' },
  { key: 365, label: '1Y' },
];

const KPI_CONFIG = [
  { key: 'total_touchpoints', label: 'Total Touchpoints', icon: 'pulse', color: '#34C759' },
  { key: 'sms_sent', label: 'SMS Sent', icon: 'chatbubble', color: '#007AFF' },
  { key: 'emails_sent', label: 'Emails', icon: 'mail', color: '#AF52DE' },
  { key: 'digital_cards', label: 'Digital Cards', icon: 'card', color: '#5856D6' },
  { key: 'review_invites', label: 'Review Invites', icon: 'star', color: '#FFD60A' },
  { key: 'congrats_cards', label: 'Congrats Cards', icon: 'gift', color: '#FF2D55' },
  { key: 'calls', label: 'Calls Made', icon: 'call', color: '#30D158' },
  { key: 'voice_notes', label: 'Voice Notes', icon: 'mic', color: '#FF9500' },
  { key: 'link_clicks', label: 'Link Clicks', icon: 'open', color: '#32ADE6' },
  { key: 'new_contacts', label: 'New Contacts', icon: 'person-add', color: '#007AFF' },
  { key: 'total_contacts', label: 'Total Contacts', icon: 'people', color: '#8E8E93' },
];

const CHANNEL_CONFIG: Record<string, { label: string; color: string; icon: string }> = {
  sms: { label: 'SMS', color: '#007AFF', icon: 'chatbubble' },
  email: { label: 'Email', color: '#AF52DE', icon: 'mail' },
  calls: { label: 'Calls', color: '#30D158', icon: 'call' },
  digital_cards: { label: 'Digital Cards', color: '#5856D6', icon: 'card' },
  reviews: { label: 'Reviews', color: '#FFD60A', icon: 'star' },
  congrats: { label: 'Congrats', color: '#FF2D55', icon: 'gift' },
  voice_notes: { label: 'Voice Notes', color: '#FF9500', icon: 'mic' },
};

export default function AnalyticsDashboard() {
  const { colors } = useThemeStore();
  const styles = getStyles(colors);
  const router = useRouter();
  const { user } = useAuthStore();
  const [period, setPeriod] = useState(30);
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const isManager = ['super_admin', 'org_admin', 'store_manager'].includes(user?.role || '');

  const fetchData = useCallback(async (days: number) => {
    if (!user?._id) return;
    try {
      const res = await api.get(`/reports/dashboard/${user._id}?days=${days}`);
      setData(res.data);
    } catch (e) {
      console.error('Dashboard fetch failed:', e);
    }
  }, [user?._id]);

  useEffect(() => {
    if (!user?._id) return;
    setLoading(true);
    fetchData(period).finally(() => setLoading(false));
  }, [period, user?._id]);

  const onRefresh = async () => {
    setRefreshing(true);
    await fetchData(period);
    setRefreshing(false);
  };

  const changePeriod = (days: number) => {
    setPeriod(days);
  };

  // Compute chart max for daily trend
  const chartMax = useMemo(() => {
    if (!data?.daily_trend) return 1;
    const m = Math.max(...data.daily_trend.map((d: any) => d.total));
    return m || 1;
  }, [data?.daily_trend]);

  // Compute channel max for horizontal bar
  const channelMax = useMemo(() => {
    if (!data?.channel_breakdown) return 1;
    const m = Math.max(...Object.values(data.channel_breakdown).map((v: any) => v as number));
    return m || 1;
  }, [data?.channel_breakdown]);

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.loadingWrap}>
          <ActivityIndicator size="large" color="#007AFF" />
          <Text style={styles.loadingText}>Loading analytics...</Text>
        </View>
      </SafeAreaView>
    );
  }

  const kpis = data?.kpis || {};
  const trendPct = kpis.trend_pct || 0;
  const trendUp = trendPct >= 0;

  return (
    <SafeAreaView style={styles.container} data-testid="analytics-dashboard">
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backBtn} data-testid="analytics-back-btn">
          <Ionicons name="chevron-back" size={24} color={colors.text} />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={styles.headerTitle}>Analytics</Text>
          <Text style={styles.headerSub}>
            {data?.scope === 'organization' ? 'Organization' : data?.scope === 'store' ? 'Store' : 'Personal'} &middot; Last {period} days
          </Text>
        </View>
      </View>

      {/* Period Selector */}
      <View style={styles.periodBar}>
        {PERIODS.map(p => (
          <TouchableOpacity
            key={p.key}
            style={[styles.periodChip, period === p.key && styles.periodChipActive]}
            onPress={() => changePeriod(p.key)}
            data-testid={`period-${p.key}`}
          >
            <Text style={[styles.periodText, period === p.key && styles.periodTextActive]}>{p.label}</Text>
          </TouchableOpacity>
        ))}
      </View>

      <ScrollView
        style={styles.content}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#007AFF" />}
      >
        {/* === KPI Hero Card === */}
        <View style={styles.heroCard} data-testid="kpi-hero-card">
          <View style={styles.heroTop}>
            <Text style={styles.heroLabel}>Total Touchpoints</Text>
            <View style={[styles.trendBadge, { backgroundColor: trendUp ? '#34C75920' : '#FF3B3020' }]}>
              <Ionicons name={trendUp ? 'trending-up' : 'trending-down'} size={14} color={trendUp ? '#34C759' : '#FF3B30'} />
              <Text style={[styles.trendText, { color: trendUp ? '#34C759' : '#FF3B30' }]}>
                {trendPct > 0 ? '+' : ''}{trendPct}%
              </Text>
            </View>
          </View>
          <Text style={styles.heroValue}>{kpis.total_touchpoints?.toLocaleString() || 0}</Text>
          <Text style={styles.heroSub}>vs previous {period} days</Text>
        </View>

        {/* === KPI Grid === */}
        <View style={styles.kpiGrid} data-testid="kpi-grid">
          {KPI_CONFIG.filter(k => k.key !== 'total_touchpoints').map(kpi => (
            <View key={kpi.key} style={styles.kpiCard}>
              <View style={[styles.kpiIconWrap, { backgroundColor: kpi.color + '18' }]}>
                <Ionicons name={kpi.icon as any} size={18} color={kpi.color} />
              </View>
              <Text style={styles.kpiValue}>{(kpis[kpi.key] || 0).toLocaleString()}</Text>
              <Text style={styles.kpiLabel}>{kpi.label}</Text>
            </View>
          ))}
        </View>

        {/* === Daily Activity Trend === */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Activity Trend</Text>
          <View style={styles.chartCard} data-testid="activity-trend-chart">
            <ScrollView horizontal showsHorizontalScrollIndicator={false}>
              <View style={styles.barChart}>
                {(data?.daily_trend || []).map((day: any, i: number) => {
                  const barH = Math.max((day.total / chartMax) * 120, 2);
                  const smsH = day.sms ? (day.sms / chartMax) * 120 : 0;
                  const emailH = day.email ? (day.email / chartMax) * 120 : 0;
                  const shareH = day.shares ? (day.shares / chartMax) * 120 : 0;
                  const label = day.date.slice(5); // MM-DD
                  const showLabel = period <= 14 || i % Math.ceil(period / 15) === 0;
                  return (
                    <View key={day.date} style={styles.barGroup}>
                      <View style={styles.barStack}>
                        {shareH > 0 && <View style={[styles.barSegment, { height: shareH, backgroundColor: '#5856D6' }]} />}
                        {emailH > 0 && <View style={[styles.barSegment, { height: emailH, backgroundColor: '#AF52DE' }]} />}
                        {smsH > 0 && <View style={[styles.barSegment, { height: smsH, backgroundColor: '#007AFF' }]} />}
                        {day.total === 0 && <View style={[styles.barSegment, { height: 2, backgroundColor: colors.surface }]} />}
                      </View>
                      {showLabel && <Text style={styles.barLabel}>{label}</Text>}
                    </View>
                  );
                })}
              </View>
            </ScrollView>
            <View style={styles.chartLegend}>
              <View style={styles.legendItem}><View style={[styles.legendDot, { backgroundColor: '#007AFF' }]} /><Text style={styles.legendText}>SMS</Text></View>
              <View style={styles.legendItem}><View style={[styles.legendDot, { backgroundColor: '#AF52DE' }]} /><Text style={styles.legendText}>Email</Text></View>
              <View style={styles.legendItem}><View style={[styles.legendDot, { backgroundColor: '#5856D6' }]} /><Text style={styles.legendText}>Shares</Text></View>
            </View>
          </View>
        </View>

        {/* === Channel Breakdown === */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Channel Breakdown</Text>
          <View style={styles.channelCard} data-testid="channel-breakdown">
            {Object.entries(data?.channel_breakdown || {}).map(([key, value]) => {
              const cfg = CHANNEL_CONFIG[key];
              if (!cfg || !(value as number)) return null;
              const pct = ((value as number) / channelMax) * 100;
              return (
                <View key={key} style={styles.channelRow}>
                  <View style={styles.channelLeft}>
                    <View style={[styles.channelIcon, { backgroundColor: cfg.color + '18' }]}>
                      <Ionicons name={cfg.icon as any} size={14} color={cfg.color} />
                    </View>
                    <Text style={styles.channelLabel}>{cfg.label}</Text>
                  </View>
                  <View style={styles.channelBarWrap}>
                    <View style={[styles.channelBar, { width: `${Math.max(pct, 3)}%`, backgroundColor: cfg.color }]} />
                  </View>
                  <Text style={styles.channelValue}>{(value as number).toLocaleString()}</Text>
                </View>
              );
            })}
          </View>
        </View>

        {/* === Per-User Performance Table === */}
        {isManager && (data?.per_user || []).length > 0 && (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Team Performance</Text>
            <View style={styles.tableCard} data-testid="team-performance-table">
              {/* Table Header */}
              <View style={styles.tableHeader}>
                <Text style={[styles.tableHeaderCell, { flex: 2 }]}>Name</Text>
                <Text style={styles.tableHeaderCell}>Total</Text>
                <Text style={styles.tableHeaderCell}>SMS</Text>
                <Text style={styles.tableHeaderCell}>Email</Text>
                <Text style={styles.tableHeaderCell}>Cards</Text>
                <Text style={styles.tableHeaderCell}>Reviews</Text>
                <Text style={styles.tableHeaderCell}>Contacts</Text>
              </View>
              {/* Table Rows */}
              {(data.per_user || []).map((u: any, i: number) => {
                const isTop3 = i < 3;
                const medals = ['#FFD700', '#C0C0C0', '#CD7F32'];
                return (
                  <View key={u.user_id} style={[styles.tableRow, i % 2 === 0 && styles.tableRowAlt]}>
                    <View style={[styles.tableCell, { flex: 2, flexDirection: 'row', alignItems: 'center', gap: 6 }]}>
                      {isTop3 && (
                        <View style={[styles.rankBadge, { backgroundColor: medals[i] + '30' }]}>
                          <Text style={[styles.rankText, { color: medals[i] }]}>{i + 1}</Text>
                        </View>
                      )}
                      <Text style={styles.tableCellText} numberOfLines={1}>{u.name}</Text>
                    </View>
                    <Text style={[styles.tableCellText, styles.tableCell, { fontWeight: '700', color: '#34C759' }]}>{u.touchpoints}</Text>
                    <Text style={[styles.tableCellText, styles.tableCell]}>{u.sms}</Text>
                    <Text style={[styles.tableCellText, styles.tableCell]}>{u.email}</Text>
                    <Text style={[styles.tableCellText, styles.tableCell]}>{u.cards}</Text>
                    <Text style={[styles.tableCellText, styles.tableCell]}>{u.reviews}</Text>
                    <Text style={[styles.tableCellText, styles.tableCell]}>{u.contacts}</Text>
                  </View>
                );
              })}
            </View>
          </View>
        )}

        {/* === Store Comparison === */}
        {(data?.store_comparison || []).length > 0 && (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Store Comparison</Text>
            <View style={styles.tableCard} data-testid="store-comparison">
              <View style={styles.tableHeader}>
                <Text style={[styles.tableHeaderCell, { flex: 2 }]}>Store</Text>
                <Text style={styles.tableHeaderCell}>Users</Text>
                <Text style={styles.tableHeaderCell}>Touchpoints</Text>
                <Text style={styles.tableHeaderCell}>Avg/User</Text>
                <Text style={styles.tableHeaderCell}>Contacts</Text>
              </View>
              {(data.store_comparison || []).map((s: any, i: number) => (
                <View key={s.store_id} style={[styles.tableRow, i % 2 === 0 && styles.tableRowAlt]}>
                  <Text style={[styles.tableCellText, styles.tableCell, { flex: 2 }]} numberOfLines={1}>{s.store_name}</Text>
                  <Text style={[styles.tableCellText, styles.tableCell]}>{s.users}</Text>
                  <Text style={[styles.tableCellText, styles.tableCell, { fontWeight: '700', color: '#34C759' }]}>{s.touchpoints}</Text>
                  <Text style={[styles.tableCellText, styles.tableCell]}>{s.avg_per_user}</Text>
                  <Text style={[styles.tableCellText, styles.tableCell]}>{s.new_contacts}</Text>
                </View>
              ))}
            </View>
          </View>
        )}

        {/* === Quick Links === */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Detailed Reports</Text>
          <View style={styles.linkGrid}>
            {[
              { title: 'Card Analytics', icon: 'gift', color: '#C9A962', route: '/analytics/cards' },
              { title: 'Activity Report', icon: 'pulse', color: '#34C759', route: '/reports/activity' },
              { title: 'Messaging', icon: 'chatbubbles', color: '#007AFF', route: '/reports/messaging' },
              { title: 'Campaigns', icon: 'megaphone', color: '#FF9500', route: '/reports/campaigns' },
              { title: 'Team Report', icon: 'people', color: '#5856D6', route: '/reports/team' },
            ].map(link => (
              <TouchableOpacity
                key={link.route}
                style={styles.linkCard}
                onPress={() => router.push(link.route as any)}
                data-testid={`report-link-${link.title.toLowerCase().replace(' ', '-')}`}
              >
                <View style={[styles.linkIcon, { backgroundColor: link.color + '18' }]}>
                  <Ionicons name={link.icon as any} size={22} color={link.color} />
                </View>
                <Text style={styles.linkTitle}>{link.title}</Text>
                <Ionicons name="chevron-forward" size={16} color={colors.borderLight} />
              </TouchableOpacity>
            ))}
          </View>
        </View>

        <View style={{ height: 40 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

const getStyles = (colors: any) => StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  loadingWrap: { flex: 1, justifyContent: 'center', alignItems: 'center', gap: 12 },
  loadingText: { color: colors.textSecondary, fontSize: 14 },
  header: {
    flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16,
    paddingVertical: 12, gap: 12,
  },
  backBtn: {
    width: 36, height: 36, borderRadius: 10, backgroundColor: colors.card,
    alignItems: 'center', justifyContent: 'center',
  },
  headerTitle: { fontSize: 20, fontWeight: '700', color: colors.text },
  headerSub: { fontSize: 12, color: colors.textSecondary, marginTop: 1 },
  periodBar: {
    flexDirection: 'row', paddingHorizontal: 16, paddingBottom: 12, gap: 8,
  },
  periodChip: {
    paddingHorizontal: 16, paddingVertical: 7, borderRadius: 18,
    backgroundColor: colors.card,
  },
  periodChipActive: { backgroundColor: '#007AFF' },
  periodText: { fontSize: 13, color: colors.textSecondary, fontWeight: '600' },
  periodTextActive: { color: colors.text },
  content: { flex: 1 },

  // Hero Card
  heroCard: {
    marginHorizontal: 16, marginBottom: 16, padding: 20, borderRadius: 16,
    backgroundColor: colors.card, borderWidth: 1, borderColor: colors.surface,
  },
  heroTop: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  heroLabel: { fontSize: 14, color: colors.textSecondary, fontWeight: '500' },
  trendBadge: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    paddingHorizontal: 8, paddingVertical: 3, borderRadius: 12,
  },
  trendText: { fontSize: 12, fontWeight: '700' },
  heroValue: { fontSize: 42, fontWeight: '800', color: colors.text, marginTop: 4 },
  heroSub: { fontSize: 12, color: '#6E6E73', marginTop: 2 },

  // KPI Grid
  kpiGrid: {
    flexDirection: 'row', flexWrap: 'wrap', paddingHorizontal: 12,
    marginBottom: 8, gap: 8,
  },
  kpiCard: {
    width: '18%', minWidth: 100, backgroundColor: colors.card, borderRadius: 12,
    padding: 12, alignItems: 'center', borderWidth: 1, borderColor: colors.surface,
    flexGrow: 1,
  },
  kpiIconWrap: {
    width: 32, height: 32, borderRadius: 10, alignItems: 'center', justifyContent: 'center',
    marginBottom: 6,
  },
  kpiValue: { fontSize: 18, fontWeight: '700', color: colors.text },
  kpiLabel: { fontSize: 10, color: colors.textSecondary, marginTop: 2, textAlign: 'center' },

  // Section
  section: { marginTop: 16, paddingHorizontal: 16 },
  sectionTitle: { fontSize: 16, fontWeight: '700', color: colors.text, marginBottom: 10 },

  // Chart
  chartCard: {
    backgroundColor: colors.card, borderRadius: 14, padding: 16,
    borderWidth: 1, borderColor: colors.surface,
  },
  barChart: { flexDirection: 'row', alignItems: 'flex-end', height: 140, gap: 2, paddingBottom: 20 },
  barGroup: { alignItems: 'center', width: 18 },
  barStack: { alignItems: 'center', justifyContent: 'flex-end' },
  barSegment: { width: 10, borderRadius: 3, marginTop: 1 },
  barLabel: { fontSize: 8, color: '#6E6E73', marginTop: 4, transform: [{ rotate: '-45deg' }] },
  chartLegend: { flexDirection: 'row', gap: 16, marginTop: 12, justifyContent: 'center' },
  legendItem: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  legendDot: { width: 8, height: 8, borderRadius: 4 },
  legendText: { fontSize: 11, color: colors.textSecondary },

  // Channel Breakdown
  channelCard: {
    backgroundColor: colors.card, borderRadius: 14, padding: 14,
    borderWidth: 1, borderColor: colors.surface, gap: 10,
  },
  channelRow: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  channelLeft: { flexDirection: 'row', alignItems: 'center', gap: 6, width: 120 },
  channelIcon: { width: 26, height: 26, borderRadius: 8, alignItems: 'center', justifyContent: 'center' },
  channelLabel: { fontSize: 12, color: colors.border, fontWeight: '500' },
  channelBarWrap: { flex: 1, height: 18, backgroundColor: colors.surface, borderRadius: 9, overflow: 'hidden' },
  channelBar: { height: '100%', borderRadius: 9 },
  channelValue: { fontSize: 13, fontWeight: '700', color: colors.text, width: 40, textAlign: 'right' },

  // Tables
  tableCard: {
    backgroundColor: colors.card, borderRadius: 14, overflow: 'hidden',
    borderWidth: 1, borderColor: colors.surface,
  },
  tableHeader: {
    flexDirection: 'row', backgroundColor: colors.surface, paddingHorizontal: 12,
    paddingVertical: 10,
  },
  tableHeaderCell: { flex: 1, fontSize: 10, fontWeight: '700', color: colors.textSecondary, textAlign: 'center' },
  tableRow: { flexDirection: 'row', paddingHorizontal: 12, paddingVertical: 10 },
  tableRowAlt: { backgroundColor: '#1A1A1C' },
  tableCell: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  tableCellText: { fontSize: 12, color: colors.border, textAlign: 'center' },
  rankBadge: {
    width: 20, height: 20, borderRadius: 10, alignItems: 'center', justifyContent: 'center',
  },
  rankText: { fontSize: 10, fontWeight: '800' },

  // Link Grid
  linkGrid: { gap: 8 },
  linkCard: {
    flexDirection: 'row', alignItems: 'center', gap: 12,
    backgroundColor: colors.card, borderRadius: 12, padding: 14,
    borderWidth: 1, borderColor: colors.surface,
  },
  linkIcon: { width: 40, height: 40, borderRadius: 12, alignItems: 'center', justifyContent: 'center' },
  linkTitle: { flex: 1, fontSize: 14, fontWeight: '600', color: colors.text },
});
