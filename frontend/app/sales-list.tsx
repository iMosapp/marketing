import React, { useEffect, useMemo, useState } from 'react';
import { View, Text, StyleSheet, FlatList, TouchableOpacity, ActivityIndicator } from 'react-native';
import { Image } from 'expo-image';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useThemeStore } from '../store/themeStore';
import { useAuthStore } from '../store/authStore';
import api from '../services/api';

const GOLD = '#C9A962';
const LABEL: Record<string, string> = {
  sold: 'Sold Units',
  referrals: 'Referrals',
  repeats: 'Repeat Buyers',
};
const MANAGER_ROLES = ['super_admin', 'admin', 'manager', 'store_manager', 'org_admin'];

interface MonthRow { year: number; month: number; label: string; total: number }

export default function SalesListScreen() {
  const { colors } = useThemeStore();
  const { user } = useAuthStore();
  const router = useRouter();
  const params = useLocalSearchParams<{ type: string; month: string; year: string }>();
  const type = params.type || 'sold';

  const now = new Date();
  const [selYear, setSelYear] = useState(parseInt(params.year || '0') || now.getFullYear());
  const [selMonth, setSelMonth] = useState(parseInt(params.month || '0') || now.getMonth() + 1);
  const [scope, setScope] = useState<'me' | 'team'>('me');
  const [contacts, setContacts] = useState<any[]>([]);
  const [months, setMonths] = useState<MonthRow[]>([]);
  const [yearTotals, setYearTotals] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(true);

  const isManager = MANAGER_ROLES.includes(user?.role || '');

  useEffect(() => {
    if (!user?._id) return;
    api.get(`/users/${user._id}/sold-monthly-summary`, { params: { filter_type: type, scope, month: now.getMonth() + 1, year: now.getFullYear() } })
      .then(r => { setMonths(r.data.months || []); setYearTotals(r.data.year_totals || {}); })
      .catch(() => {});
  }, [user?._id, type, scope]);

  useEffect(() => {
    if (!user?._id) return;
    setLoading(true);
    api.get(`/users/${user._id}/sold-contacts`, {
      params: { filter_type: type, month: selMonth, year: selYear, scope }
    }).then(r => setContacts(r.data.contacts || []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [user?._id, type, selMonth, selYear, scope]);

  const monthLabel = new Date(selYear, selMonth - 1).toLocaleString('default', { month: 'long', year: 'numeric' });
  const isCurrentMonth = selYear === now.getFullYear() && selMonth === now.getMonth() + 1;

  const getTotal = (y: number, m: number) => months.find(r => r.year === y && r.month === m)?.total ?? null;

  const selTotal = getTotal(selYear, selMonth) ?? contacts.length;
  const prevM = selMonth === 1 ? 12 : selMonth - 1;
  const prevY = selMonth === 1 ? selYear - 1 : selYear;
  const prevTotal = getTotal(prevY, prevM);
  const lastYearTotal = getTotal(selYear - 1, selMonth);

  const momDiff = prevTotal === null ? null : selTotal - prevTotal;
  const yoyPct = lastYearTotal ? Math.round(((selTotal - lastYearTotal) / lastYearTotal) * 100) : null;

  const chartMonths = useMemo(() => months.slice(-12), [months]);
  const chartMax = Math.max(1, ...chartMonths.map(r => r.total));

  const shiftMonth = (dir: number) => {
    let m = selMonth + dir;
    let y = selYear;
    if (m === 0) { m = 12; y -= 1; }
    if (m === 13) { m = 1; y += 1; }
    if (y > now.getFullYear() || (y === now.getFullYear() && m > now.getMonth() + 1)) return;
    setSelMonth(m); setSelYear(y);
  };

  const yearSoFar = yearTotals[String(selYear)] ?? 0;

  const CompareChip = ({ icon, label, value, color }: any) => (
    <View style={[st.chip, { backgroundColor: colors.card, borderColor: colors.surface }]}>
      <Ionicons name={icon} size={13} color={color} />
      <Text style={{ fontSize: 12, color: colors.textSecondary }} numberOfLines={1}>{label}</Text>
      <Text style={{ fontSize: 13, fontWeight: '800', color }} numberOfLines={1}>{value}</Text>
    </View>
  );

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      {/* Header */}
      <View style={[st.header, { borderBottomColor: colors.border }]}>
        <TouchableOpacity onPress={() => router.back()} hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }} testID="sales-back-btn" dataSet={{ testid: 'sales-back-btn' }}>
          <Ionicons name="chevron-back" size={26} color={colors.text} />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={{ fontSize: 19, fontWeight: '700', color: colors.text }}>{LABEL[type] || 'Sales'}</Text>
          <Text style={{ fontSize: 13, color: colors.textSecondary }}>
            {scope === 'team' ? 'Team' : 'My'} history · tap a bar or use arrows
          </Text>
        </View>
        {isManager && (
          <View style={[st.segment, { backgroundColor: colors.surface }]}>
            {(['me', 'team'] as const).map(s => (
              <TouchableOpacity
                key={s}
                onPress={() => setScope(s)}
                style={[st.segmentBtn, scope === s && { backgroundColor: GOLD }]}
                testID={`sales-scope-${s}`} dataSet={{ testid: `sales-scope-${s}` }}
              >
                <Text style={{ fontSize: 12, fontWeight: '700', color: scope === s ? '#1C1C1E' : colors.textSecondary }}>
                  {s === 'me' ? 'Me' : 'Team'}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
        )}
      </View>

      <FlatList
        data={loading ? [] : contacts}
        keyExtractor={item => item._id}
        contentContainerStyle={{ paddingHorizontal: 16, paddingBottom: 32 }}
        ListHeaderComponent={
          <View>
            {/* Month navigator */}
            <View style={[st.monthNav, { backgroundColor: colors.card, borderColor: colors.surface }]}>
              <TouchableOpacity onPress={() => shiftMonth(-1)} style={st.navBtn} testID="sales-month-prev" dataSet={{ testid: 'sales-month-prev' }}>
                <Ionicons name="chevron-back" size={22} color={GOLD} />
              </TouchableOpacity>
              <View style={{ alignItems: 'center' }}>
                <Text style={{ fontSize: 17, fontWeight: '800', color: colors.text }} testID="sales-month-label" dataSet={{ testid: 'sales-month-label' }}>{monthLabel}</Text>
                <Text style={{ fontSize: 26, fontWeight: '900', color: GOLD }} testID="sales-month-total" dataSet={{ testid: 'sales-month-total' }}>{selTotal}</Text>
                <Text style={{ fontSize: 11, color: colors.textSecondary, textTransform: 'uppercase', letterSpacing: 1 }}>
                  {type === 'sold' ? 'units sold' : type}
                </Text>
              </View>
              <TouchableOpacity onPress={() => shiftMonth(1)} style={[st.navBtn, isCurrentMonth && { opacity: 0.25 }]} disabled={isCurrentMonth} testID="sales-month-next" dataSet={{ testid: 'sales-month-next' }}>
                <Ionicons name="chevron-forward" size={22} color={GOLD} />
              </TouchableOpacity>
            </View>

            {/* Comparisons */}
            <View style={{ flexDirection: 'row', gap: 8, marginTop: 10 }}>
              <CompareChip
                icon={momDiff !== null && momDiff < 0 ? 'trending-down' : 'trending-up'}
                label="vs last mo"
                value={momDiff === null ? '—' : `${momDiff > 0 ? '+' : ''}${momDiff}`}
                color={momDiff !== null && momDiff < 0 ? '#FF3B30' : '#34C759'}
              />
              <CompareChip
                icon="calendar"
                label={new Date(selYear - 1, selMonth - 1).toLocaleString('default', { month: 'short', year: '2-digit' })}
                value={lastYearTotal === null ? '—' : `${lastYearTotal} → ${selTotal}${yoyPct !== null ? ` (${yoyPct > 0 ? '+' : ''}${yoyPct}%)` : ''}`}
                color="#007AFF"
              />
              <CompareChip icon="trophy" label={`${selYear} total`} value={String(yearSoFar)} color={GOLD} />
            </View>

            {/* 12-month bar chart */}
            <View style={[st.chartCard, { backgroundColor: colors.card, borderColor: colors.surface }]}>
              <View style={st.chartRow}>
                {chartMonths.map((r, i) => {
                  const active = r.year === selYear && r.month === selMonth;
                  const h = Math.max(4, Math.round((r.total / chartMax) * 64));
                  return (
                    <TouchableOpacity
                      key={`${r.year}-${r.month}`}
                      style={st.barCol}
                      onPress={() => { setSelYear(r.year); setSelMonth(r.month); }}
                      testID={`sales-bar-${i}`} dataSet={{ testid: `sales-bar-${i}` }}
                    >
                      <Text style={{ fontSize: 9, fontWeight: '700', color: active ? GOLD : colors.textSecondary }}>
                        {r.total > 0 ? r.total : ''}
                      </Text>
                      <View style={[st.bar, { height: h, backgroundColor: active ? GOLD : GOLD + '45' }]} />
                      <Text style={{ fontSize: 9, color: active ? colors.text : colors.textSecondary, fontWeight: active ? '800' : '500' }}>
                        {r.label.slice(0, 1)}
                      </Text>
                    </TouchableOpacity>
                  );
                })}
              </View>
              <Text style={{ fontSize: 11, color: colors.textSecondary, textAlign: 'center', marginTop: 6 }}>
                Last 12 months · tap a bar to jump
              </Text>
            </View>

            {loading && (
              <View style={{ paddingVertical: 40, alignItems: 'center' }}>
                <ActivityIndicator size="large" color={GOLD} />
              </View>
            )}
            {!loading && contacts.length === 0 && (
              <View style={{ alignItems: 'center', padding: 32 }}>
                <Ionicons name="trophy-outline" size={48} color={colors.borderLight} />
                <Text style={{ fontSize: 18, fontWeight: '700', color: colors.text, marginTop: 16 }}>Nothing in {monthLabel}</Text>
                <Text style={{ fontSize: 14, color: colors.textSecondary, textAlign: 'center', marginTop: 8 }}>
                  {type === 'sold' ? 'Use the SOLD wizard to log deliveries' : `No ${type} recorded this month`}
                </Text>
              </View>
            )}
          </View>
        }
        renderItem={({ item }) => (
          <TouchableOpacity
            onPress={() => router.push(`/contact/${item._id}` as any)}
            style={[st.row, { backgroundColor: colors.card, borderColor: colors.surface }]}
            testID={`sales-list-contact-${item._id}`} dataSet={{ testid: `sales-list-contact-${item._id}` }}
          >
            <View style={st.avatar}>
              <Text style={{ fontSize: 18, fontWeight: '700', color: GOLD }}>
                {(item.name || '?')[0].toUpperCase()}
              </Text>
              {item.photo_thumbnail ? (
                <Image
                  source={{ uri: item.photo_thumbnail }}
                  style={[StyleSheet.absoluteFillObject, { borderRadius: 22 }]}
                  contentFit="cover"
                  cachePolicy="memory-disk"
                  transition={150}
                />
              ) : null}
            </View>
            <View style={{ flex: 1 }}>
              <Text style={{ fontSize: 16, fontWeight: '700', color: colors.text }}>{item.name}</Text>
              {item.vehicle ? (
                <Text style={{ fontSize: 13, color: colors.textSecondary, marginTop: 2 }}>{item.vehicle}</Text>
              ) : null}
              {scope === 'team' && item.rep_name ? (
                <Text style={{ fontSize: 12, color: GOLD, marginTop: 2 }}>
                  <Ionicons name="person-circle-outline" size={11} color={GOLD} /> {item.rep_name}
                </Text>
              ) : null}
              {item.referred_by_name && type === 'referrals' ? (
                <Text style={{ fontSize: 12, color: '#007AFF', marginTop: 2 }}>
                  <Ionicons name="person" size={11} color="#007AFF" /> Referred by {item.referred_by_name}
                </Text>
              ) : null}
              {type === 'repeats' && item.sold_count > 1 ? (
                <Text style={{ fontSize: 12, color: '#AF52DE', marginTop: 2 }}>{item.sold_count}x buyer</Text>
              ) : null}
            </View>
            <View style={{ alignItems: 'flex-end', gap: 4 }}>
              {item.date_sold ? (
                <Text style={{ fontSize: 12, color: colors.textSecondary }}>
                  {new Date(item.date_sold).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                </Text>
              ) : null}
              <Ionicons name="chevron-forward" size={16} color={colors.borderLight} />
            </View>
          </TouchableOpacity>
        )}
      />
    </SafeAreaView>
  );
}

const st = StyleSheet.create({
  header: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 14, borderBottomWidth: 1, gap: 12 },
  segment: { flexDirection: 'row', borderRadius: 10, padding: 2 },
  segmentBtn: { paddingHorizontal: 12, paddingVertical: 6, borderRadius: 8 },
  monthNav: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', borderRadius: 16, borderWidth: 1, paddingVertical: 14, paddingHorizontal: 8, marginTop: 12 },
  navBtn: { padding: 10 },
  chip: { flex: 1, flexDirection: 'row', alignItems: 'center', gap: 4, borderRadius: 12, borderWidth: 1, paddingHorizontal: 8, paddingVertical: 8, minWidth: 0 },
  chartCard: { borderRadius: 16, borderWidth: 1, padding: 12, marginTop: 10, marginBottom: 12 },
  chartRow: { flexDirection: 'row', alignItems: 'flex-end', justifyContent: 'space-between', height: 96 },
  barCol: { flex: 1, alignItems: 'center', justifyContent: 'flex-end', gap: 3 },
  bar: { width: 14, borderRadius: 4 },
  row: { flexDirection: 'row', alignItems: 'center', borderRadius: 14, padding: 14, marginBottom: 8, borderWidth: 1, gap: 12 },
  avatar: { width: 44, height: 44, borderRadius: 22, backgroundColor: '#C9A96220', alignItems: 'center', justifyContent: 'center', overflow: 'hidden' },
});
