import React, { useState, useCallback, useEffect, useMemo } from 'react';
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

const CARD_TYPE_CONFIG: Record<string, { label: string; icon: string; color: string }> = {
  congrats: { label: 'Congrats', icon: 'trophy', color: '#C9A962' },
  birthday: { label: 'Birthday', icon: 'gift', color: '#FF2D55' },
  anniversary: { label: 'Anniversary', icon: 'heart', color: '#AF52DE' },
  thankyou: { label: 'Thank You', icon: 'thumbs-up', color: '#34C759' },
  welcome: { label: 'Welcome', icon: 'hand-left', color: '#007AFF' },
  holiday: { label: 'Holiday', icon: 'snow', color: '#5AC8FA' },
};

export default function CardAnalytics() {
  const { colors } = useThemeStore();
  const s = getStyles(colors);
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
      const res = await api.get(`/reports/card-analytics/${user._id}?days=${days}`);
      setData(res.data);
    } catch (e) {
      console.error('Card analytics fetch failed:', e);
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

  // Chart max for daily trend
  const chartMax = useMemo(() => {
    if (!data?.daily_trend) return 1;
    const m = Math.max(...data.daily_trend.map((d: any) => d.cards));
    return m || 1;
  }, [data?.daily_trend]);

  // Max for type breakdown bar
  const typeMax = useMemo(() => {
    if (!data?.card_type_breakdown) return 1;
    return Math.max(...data.card_type_breakdown.map((t: any) => t.count), 1);
  }, [data?.card_type_breakdown]);

  if (loading) {
    return (
      <SafeAreaView style={s.container}>
        <View style={s.loadingWrap}>
          <ActivityIndicator size="large" color="#C9A962" />
          <Text style={s.loadingText}>Loading card analytics...</Text>
        </View>
      </SafeAreaView>
    );
  }

  const summary = data?.summary || {};

  return (
    <SafeAreaView style={s.container} data-testid="card-analytics-page">
      {/* Header */}
      <View style={s.header}>
        <TouchableOpacity onPress={() => router.back()} style={s.backBtn} data-testid="card-analytics-back-btn">
          <Ionicons name="chevron-back" size={24} color={colors.text} />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={s.headerTitle}>Card Analytics</Text>
          <Text style={s.headerSub}>
            {data?.scope === 'organization' ? 'Organization' : data?.scope === 'store' ? 'Store' : 'Personal'} &middot; Last {period} days
          </Text>
        </View>
      </View>

      {/* Period Selector */}
      <View style={s.periodBar}>
        {PERIODS.map(p => (
          <TouchableOpacity
            key={p.key}
            style={[s.periodChip, period === p.key && s.periodChipActive]}
            onPress={() => setPeriod(p.key)}
            data-testid={`card-period-${p.key}`}
          >
            <Text style={[s.periodText, period === p.key && s.periodTextActive]}>{p.label}</Text>
          </TouchableOpacity>
        ))}
      </View>

      <ScrollView
        style={s.content}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#C9A962" />}
      >
        {/* === Hero KPI Row === */}
        <View style={s.heroRow} data-testid="card-hero-kpis">
          <HeroKPI
            colors={colors}
            label="Cards Created"
            value={summary.total_cards}
            trend={summary.cards_trend_pct}
            icon="layers"
            color="#C9A962"
          />
          <HeroKPI
            colors={colors}
            label="Total Views"
            value={summary.total_views}
            trend={summary.views_trend_pct}
            icon="eye"
            color="#007AFF"
          />
          <HeroKPI
            colors={colors}
            label="Downloads"
            value={summary.total_downloads}
            icon="download"
            color="#34C759"
          />
          <HeroKPI
            colors={colors}
            label="Shares"
            value={summary.total_shares}
            icon="share-social"
            color="#5856D6"
          />
        </View>

        {/* === Averages Row === */}
        <View style={s.avgRow}>
          <View style={[s.avgCard, { borderLeftColor: '#007AFF' }]}>
            <Text style={s.avgValue}>{summary.avg_views_per_card || 0}</Text>
            <Text style={s.avgLabel}>Avg Views / Card</Text>
          </View>
          <View style={[s.avgCard, { borderLeftColor: '#34C759' }]}>
            <Text style={s.avgValue}>{summary.avg_downloads_per_card || 0}</Text>
            <Text style={s.avgLabel}>Avg Downloads / Card</Text>
          </View>
        </View>

        {/* === Card Type Breakdown === */}
        {(data?.card_type_breakdown || []).length > 0 && (
          <View style={s.section}>
            <Text style={s.sectionTitle}>Performance by Card Type</Text>
            <View style={s.breakdownCard} data-testid="card-type-breakdown">
              {data.card_type_breakdown.map((t: any) => {
                const cfg = CARD_TYPE_CONFIG[t.card_type] || { label: t.card_type, icon: 'document', color: '#8E8E93' };
                const pct = (t.count / typeMax) * 100;
                return (
                  <View key={t.card_type} style={s.typeRow}>
                    <View style={s.typeLeft}>
                      <View style={[s.typeIcon, { backgroundColor: cfg.color + '18' }]}>
                        <Ionicons name={cfg.icon as any} size={16} color={cfg.color} />
                      </View>
                      <View>
                        <Text style={s.typeLabel}>{cfg.label}</Text>
                        <Text style={s.typeCount}>{t.count} card{t.count !== 1 ? 's' : ''}</Text>
                      </View>
                    </View>
                    <View style={s.typeRight}>
                      <View style={s.typeBarWrap}>
                        <View style={[s.typeBar, { width: `${Math.max(pct, 5)}%`, backgroundColor: cfg.color }]} />
                      </View>
                      <View style={s.typeStats}>
                        <StatBadge icon="eye" value={t.views} color="#007AFF" colors={colors} />
                        <StatBadge icon="download" value={t.downloads} color="#34C759" colors={colors} />
                        <StatBadge icon="share-social" value={t.shares} color="#5856D6" colors={colors} />
                      </View>
                    </View>
                  </View>
                );
              })}
            </View>
          </View>
        )}

        {/* === Daily Trend Chart === */}
        {(data?.daily_trend || []).length > 0 && (
          <View style={s.section}>
            <Text style={s.sectionTitle}>Daily Card Activity</Text>
            <View style={s.chartCard} data-testid="card-daily-trend">
              <ScrollView horizontal showsHorizontalScrollIndicator={false}>
                <View style={s.barChart}>
                  {data.daily_trend.map((day: any, i: number) => {
                    const barH = Math.max((day.cards / chartMax) * 120, 2);
                    const label = day.date.slice(5);
                    const showLabel = period <= 14 || i % Math.ceil(period / 15) === 0;
                    return (
                      <View key={day.date} style={s.barGroup}>
                        <Text style={s.barValue}>{day.cards || ''}</Text>
                        <View style={[s.barFill, { height: barH, backgroundColor: '#C9A962' }]} />
                        {showLabel && <Text style={s.barLabel}>{label}</Text>}
                      </View>
                    );
                  })}
                </View>
              </ScrollView>
              <View style={s.chartLegend}>
                <View style={s.legendItem}><View style={[s.legendDot, { backgroundColor: '#C9A962' }]} /><Text style={s.legendText}>Cards Created</Text></View>
              </View>
            </View>
          </View>
        )}

        {/* === Top Performing Cards === */}
        {(data?.top_cards || []).length > 0 && (
          <View style={s.section}>
            <Text style={s.sectionTitle}>Top Performing Cards</Text>
            <View style={s.tableCard} data-testid="top-cards-table">
              <View style={s.tableHeader}>
                <Text style={[s.tableHeaderCell, { flex: 1, textAlign: 'left', paddingLeft: 4 }]}>#</Text>
                <Text style={[s.tableHeaderCell, { flex: 3, textAlign: 'left' }]}>Customer</Text>
                <Text style={[s.tableHeaderCell, { flex: 2 }]}>Type</Text>
                {isManager && <Text style={[s.tableHeaderCell, { flex: 2 }]}>Rep</Text>}
                <Text style={s.tableHeaderCell}>Views</Text>
                <Text style={s.tableHeaderCell}>DL</Text>
                <Text style={s.tableHeaderCell}>Shares</Text>
                <Text style={s.tableHeaderCell}>Score</Text>
              </View>
              {data.top_cards.map((card: any, i: number) => {
                const cfg = CARD_TYPE_CONFIG[card.card_type] || { label: card.card_type, icon: 'document', color: '#8E8E93' };
                const medals = ['#FFD700', '#C0C0C0', '#CD7F32'];
                return (
                  <View key={card.card_id} style={[s.tableRow, i % 2 === 0 && s.tableRowAlt]}>
                    <View style={[s.tableCell, { flex: 1 }]}>
                      {i < 3 ? (
                        <View style={[s.rankBadge, { backgroundColor: medals[i] + '30' }]}>
                          <Text style={[s.rankText, { color: medals[i] }]}>{i + 1}</Text>
                        </View>
                      ) : (
                        <Text style={s.tableCellText}>{i + 1}</Text>
                      )}
                    </View>
                    <Text style={[s.tableCellText, s.tableCell, { flex: 3, textAlign: 'left' }]} numberOfLines={1}>
                      {card.customer_name}
                    </Text>
                    <View style={[s.tableCell, { flex: 2, flexDirection: 'row', gap: 4, justifyContent: 'center' }]}>
                      <Ionicons name={cfg.icon as any} size={12} color={cfg.color} />
                      <Text style={[s.tableCellText, { color: cfg.color }]}>{cfg.label}</Text>
                    </View>
                    {isManager && (
                      <Text style={[s.tableCellText, s.tableCell, { flex: 2 }]} numberOfLines={1}>
                        {card.salesman_name}
                      </Text>
                    )}
                    <Text style={[s.tableCellText, s.tableCell]}>{card.views}</Text>
                    <Text style={[s.tableCellText, s.tableCell]}>{card.downloads}</Text>
                    <Text style={[s.tableCellText, s.tableCell]}>{card.shares}</Text>
                    <Text style={[s.tableCellText, s.tableCell, { fontWeight: '700', color: '#C9A962' }]}>
                      {card.engagement}
                    </Text>
                  </View>
                );
              })}
            </View>
          </View>
        )}

        {/* === Per-User Breakdown (Managers) === */}
        {isManager && (data?.per_user || []).length > 1 && (
          <View style={s.section}>
            <Text style={s.sectionTitle}>Team Card Performance</Text>
            <View style={s.tableCard} data-testid="team-card-performance">
              <View style={s.tableHeader}>
                <Text style={[s.tableHeaderCell, { flex: 3, textAlign: 'left', paddingLeft: 12 }]}>Name</Text>
                <Text style={s.tableHeaderCell}>Cards</Text>
                <Text style={s.tableHeaderCell}>Views</Text>
                <Text style={s.tableHeaderCell}>DL</Text>
                <Text style={s.tableHeaderCell}>Shares</Text>
                <Text style={s.tableHeaderCell}>Score</Text>
                <Text style={[s.tableHeaderCell, { flex: 1.3 }]}>vs Avg</Text>
              </View>
              {data.per_user.map((u: any, i: number) => {
                const medals = ['#FFD700', '#C0C0C0', '#CD7F32'];
                const vsAvg = u.vs_avg_cards;
                const vsColor = vsAvg > 0 ? '#34C759' : vsAvg < 0 ? '#FF3B30' : colors.textSecondary;
                return (
                  <View key={u.user_id} style={[s.tableRow, i % 2 === 0 && s.tableRowAlt]}>
                    <View style={[s.tableCell, { flex: 3, flexDirection: 'row', alignItems: 'center', gap: 6, paddingLeft: 4 }]}>
                      {i < 3 && (
                        <View style={[s.rankBadge, { backgroundColor: medals[i] + '30' }]}>
                          <Text style={[s.rankText, { color: medals[i] }]}>{i + 1}</Text>
                        </View>
                      )}
                      <Text style={s.tableCellText} numberOfLines={1}>{u.name}</Text>
                    </View>
                    <Text style={[s.tableCellText, s.tableCell, { fontWeight: '700' }]}>{u.cards}</Text>
                    <Text style={[s.tableCellText, s.tableCell]}>{u.views}</Text>
                    <Text style={[s.tableCellText, s.tableCell]}>{u.downloads}</Text>
                    <Text style={[s.tableCellText, s.tableCell]}>{u.shares}</Text>
                    <Text style={[s.tableCellText, s.tableCell, { fontWeight: '700', color: '#C9A962' }]}>{u.engagement}</Text>
                    <View style={[s.tableCell, { flex: 1.3 }]}>
                      <View style={[s.vsAvgBadge, { backgroundColor: vsColor + '18' }]}>
                        <Ionicons
                          name={vsAvg > 0 ? 'arrow-up' : vsAvg < 0 ? 'arrow-down' : 'remove'}
                          size={10}
                          color={vsColor}
                        />
                        <Text style={[s.vsAvgText, { color: vsColor }]}>
                          {vsAvg > 0 ? '+' : ''}{vsAvg}
                        </Text>
                      </View>
                    </View>
                  </View>
                );
              })}
            </View>
          </View>
        )}

        {/* === Card Type Pie / Distribution for personal users === */}
        {!isManager && (data?.per_user || []).length === 1 && (
          <View style={s.section}>
            <Text style={s.sectionTitle}>Your Card Mix</Text>
            <View style={s.mixCard} data-testid="personal-card-mix">
              {Object.entries(data.per_user[0]?.card_types || {}).map(([type, count]) => {
                const cfg = CARD_TYPE_CONFIG[type] || { label: type, icon: 'document', color: '#8E8E93' };
                const pct = summary.total_cards ? Math.round((count as number) / summary.total_cards * 100) : 0;
                return (
                  <View key={type} style={s.mixRow}>
                    <View style={[s.mixDot, { backgroundColor: cfg.color }]} />
                    <Ionicons name={cfg.icon as any} size={14} color={cfg.color} />
                    <Text style={s.mixLabel}>{cfg.label}</Text>
                    <View style={{ flex: 1 }} />
                    <Text style={s.mixCount}>{count as number}</Text>
                    <Text style={[s.mixPct, { color: cfg.color }]}>{pct}%</Text>
                  </View>
                );
              })}
            </View>
          </View>
        )}

        <View style={{ height: 40 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

/* ── Small helper components ── */
function HeroKPI({ colors, label, value, trend, icon, color }: any) {
  const s = getStyles(colors);
  const trendUp = (trend || 0) >= 0;
  return (
    <View style={s.heroKPI}>
      <View style={[s.heroKPIIcon, { backgroundColor: color + '18' }]}>
        <Ionicons name={icon} size={18} color={color} />
      </View>
      <Text style={s.heroKPIValue}>{(value || 0).toLocaleString()}</Text>
      <Text style={s.heroKPILabel}>{label}</Text>
      {trend !== undefined && (
        <View style={[s.heroTrendBadge, { backgroundColor: trendUp ? '#34C75920' : '#FF3B3020' }]}>
          <Ionicons name={trendUp ? 'trending-up' : 'trending-down'} size={10} color={trendUp ? '#34C759' : '#FF3B30'} />
          <Text style={{ fontSize: 10, fontWeight: '700', color: trendUp ? '#34C759' : '#FF3B30' }}>
            {trend > 0 ? '+' : ''}{trend}%
          </Text>
        </View>
      )}
    </View>
  );
}

function StatBadge({ icon, value, color, colors }: any) {
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 3 }}>
      <Ionicons name={icon} size={11} color={color} />
      <Text style={{ fontSize: 11, color: colors.textSecondary, fontWeight: '600' }}>{value}</Text>
    </View>
  );
}

/* ── Styles ── */
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
  periodBar: { flexDirection: 'row', paddingHorizontal: 16, paddingBottom: 12, gap: 8 },
  periodChip: {
    paddingHorizontal: 16, paddingVertical: 7, borderRadius: 18,
    backgroundColor: colors.card,
  },
  periodChipActive: { backgroundColor: '#C9A962' },
  periodText: { fontSize: 13, color: colors.textSecondary, fontWeight: '600' },
  periodTextActive: { color: '#000' },
  content: { flex: 1 },

  // Hero KPI Row
  heroRow: {
    flexDirection: 'row', paddingHorizontal: 12, marginBottom: 8, gap: 8,
    flexWrap: 'wrap',
  },
  heroKPI: {
    flex: 1, minWidth: 140, backgroundColor: colors.card, borderRadius: 14,
    padding: 14, alignItems: 'center', borderWidth: 1, borderColor: colors.surface,
  },
  heroKPIIcon: {
    width: 36, height: 36, borderRadius: 12, alignItems: 'center', justifyContent: 'center',
    marginBottom: 8,
  },
  heroKPIValue: { fontSize: 26, fontWeight: '800', color: colors.text },
  heroKPILabel: { fontSize: 11, color: colors.textSecondary, marginTop: 2, textAlign: 'center' },
  heroTrendBadge: {
    flexDirection: 'row', alignItems: 'center', gap: 3, marginTop: 6,
    paddingHorizontal: 8, paddingVertical: 2, borderRadius: 10,
  },

  // Averages
  avgRow: { flexDirection: 'row', paddingHorizontal: 16, gap: 8, marginTop: 8, marginBottom: 4 },
  avgCard: {
    flex: 1, backgroundColor: colors.card, borderRadius: 12, padding: 14,
    borderWidth: 1, borderColor: colors.surface, borderLeftWidth: 3,
  },
  avgValue: { fontSize: 22, fontWeight: '700', color: colors.text },
  avgLabel: { fontSize: 11, color: colors.textSecondary, marginTop: 2 },

  // Sections
  section: { marginTop: 20, paddingHorizontal: 16 },
  sectionTitle: { fontSize: 16, fontWeight: '700', color: colors.text, marginBottom: 10 },

  // Type Breakdown
  breakdownCard: {
    backgroundColor: colors.card, borderRadius: 14, padding: 14,
    borderWidth: 1, borderColor: colors.surface, gap: 14,
  },
  typeRow: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  typeLeft: { flexDirection: 'row', alignItems: 'center', gap: 10, width: 130 },
  typeIcon: { width: 32, height: 32, borderRadius: 10, alignItems: 'center', justifyContent: 'center' },
  typeLabel: { fontSize: 13, fontWeight: '600', color: colors.text },
  typeCount: { fontSize: 10, color: colors.textSecondary },
  typeRight: { flex: 1, gap: 6 },
  typeBarWrap: { height: 10, backgroundColor: colors.surface, borderRadius: 5, overflow: 'hidden' },
  typeBar: { height: '100%', borderRadius: 5 },
  typeStats: { flexDirection: 'row', gap: 12 },

  // Chart
  chartCard: {
    backgroundColor: colors.card, borderRadius: 14, padding: 16,
    borderWidth: 1, borderColor: colors.surface,
  },
  barChart: { flexDirection: 'row', alignItems: 'flex-end', height: 150, gap: 3, paddingBottom: 20 },
  barGroup: { alignItems: 'center', width: 24 },
  barFill: { width: 14, borderRadius: 4 },
  barValue: { fontSize: 8, color: colors.textSecondary, marginBottom: 2 },
  barLabel: { fontSize: 8, color: '#6E6E73', marginTop: 4, transform: [{ rotate: '-45deg' }] },
  chartLegend: { flexDirection: 'row', gap: 16, marginTop: 12, justifyContent: 'center' },
  legendItem: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  legendDot: { width: 8, height: 8, borderRadius: 4 },
  legendText: { fontSize: 11, color: colors.textSecondary },

  // Tables
  tableCard: {
    backgroundColor: colors.card, borderRadius: 14, overflow: 'hidden',
    borderWidth: 1, borderColor: colors.surface,
  },
  tableHeader: {
    flexDirection: 'row', backgroundColor: colors.surface, paddingHorizontal: 8,
    paddingVertical: 10,
  },
  tableHeaderCell: { flex: 1, fontSize: 10, fontWeight: '700', color: colors.textSecondary, textAlign: 'center' },
  tableRow: { flexDirection: 'row', paddingHorizontal: 8, paddingVertical: 10 },
  tableRowAlt: { backgroundColor: colors.surface + '40' },
  tableCell: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  tableCellText: { fontSize: 12, color: colors.border, textAlign: 'center' },
  rankBadge: {
    width: 20, height: 20, borderRadius: 10, alignItems: 'center', justifyContent: 'center',
  },
  rankText: { fontSize: 10, fontWeight: '800' },

  // vs Average badge
  vsAvgBadge: {
    flexDirection: 'row', alignItems: 'center', gap: 2,
    paddingHorizontal: 6, paddingVertical: 2, borderRadius: 8,
  },
  vsAvgText: { fontSize: 10, fontWeight: '700' },

  // Personal Card Mix
  mixCard: {
    backgroundColor: colors.card, borderRadius: 14, padding: 14,
    borderWidth: 1, borderColor: colors.surface, gap: 10,
  },
  mixRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  mixDot: { width: 8, height: 8, borderRadius: 4 },
  mixLabel: { fontSize: 13, fontWeight: '500', color: colors.text },
  mixCount: { fontSize: 14, fontWeight: '700', color: colors.text, minWidth: 30, textAlign: 'right' },
  mixPct: { fontSize: 12, fontWeight: '600', minWidth: 36, textAlign: 'right' },
});
