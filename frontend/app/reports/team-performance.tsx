import React, { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, ActivityIndicator, ScrollView } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useThemeStore } from '../../store/themeStore';
import { useAuthStore } from '../../store/authStore';
import { ScreenHeader } from '../../components/common/ScreenHeader';
import { FS } from '../../constants/typography';
import api from '../../services/api';

const tid = (id: string) => ({ testID: id, dataSet: { testid: id } as any });
// Sold is the brand gold; Referrals and Repeats keep the same category colors as the Home sales tiles.
const STAT_COLORS = { sold: '#C9A962', referrals: '#007AFF', repeats: '#AF52DE' };

export default function TeamPerformanceScreen() {
  const { colors } = useThemeStore();
  const { user } = useAuthStore();
  const router = useRouter();

  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const now = new Date();
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [year, setYear] = useState(now.getFullYear());

  useEffect(() => {
    if (!user?._id) return;
    setLoading(true);
    api.get(`/team/${user._id}/performance`, { params: { month, year } })
      .then(r => setData(r.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [user?._id, month, year]);

  const changeMonth = (delta: number) => {
    let m = month + delta;
    let y = year;
    if (m > 12) { m = 1; y++; }
    if (m < 1)  { m = 12; y--; }
    setMonth(m); setYear(y);
  };

  const monthLabel = data?.month_label || new Date(year, month - 1).toLocaleString('default', { month: 'long', year: 'numeric' });

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      <ScreenHeader title="Team Sales" testID="team-sales-header" />

      <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'center', paddingVertical: 12, gap: 20 }}>
        <TouchableOpacity onPress={() => changeMonth(-1)} hitSlop={10} style={{ width: 44, height: 44, alignItems: 'center', justifyContent: 'center' }} {...tid('team-sales-prev-month')}>
          <Ionicons name="chevron-back" size={22} color={colors.accent} />
        </TouchableOpacity>
        <Text style={{ fontSize: FS.nav, fontWeight: '700', color: colors.text, minWidth: 150, textAlign: 'center' }} maxFontSizeMultiplier={1.2} {...tid('team-sales-month-label')}>
          {monthLabel}
        </Text>
        <TouchableOpacity onPress={() => changeMonth(1)} hitSlop={10} style={{ width: 44, height: 44, alignItems: 'center', justifyContent: 'center' }} {...tid('team-sales-next-month')}>
          <Ionicons name="chevron-forward" size={22} color={colors.accent} />
        </TouchableOpacity>
      </View>

      {loading ? (
        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}>
          <ActivityIndicator size="large" color={colors.accent} />
        </View>
      ) : !data?.stores?.length ? (
        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', padding: 32 }} {...tid('team-sales-empty')}>
          <Ionicons name="people-outline" size={44} color={colors.textTertiary} />
          <Text style={{ fontSize: FS.heading, fontWeight: '700', color: colors.text, marginTop: 12, textAlign: 'center' }}>No team sales yet</Text>
          <Text style={{ fontSize: FS.body, color: colors.textSecondary, textAlign: 'center', marginTop: 6 }}>Reps need a store assigned before their sold units roll up here.</Text>
          <TouchableOpacity onPress={() => router.push('/admin/users' as any)} style={{ marginTop: 18, backgroundColor: colors.accent, borderRadius: 14, paddingHorizontal: 22, paddingVertical: 12 }} {...tid('team-sales-manage-team')}>
            <Text style={{ fontSize: FS.heading, fontWeight: '700', color: '#000' }}>Manage team</Text>
          </TouchableOpacity>
        </View>
      ) : (
        <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 40 }}>
          {data.stores.map((store: any) => (
            <View key={store.store_id} style={{ marginBottom: 20 }} {...tid(`team-sales-store-${store.store_id}`)}>
              <View style={{ flexDirection: 'row', alignItems: 'center', marginBottom: 10, gap: 8 }}>
                <Ionicons name="business" size={18} color={colors.accent} />
                <Text style={{ flex: 1, fontSize: FS.heading, fontWeight: '800', color: colors.text }} numberOfLines={1}>{store.store_name}</Text>
                <View style={{ flexDirection: 'row', gap: 12 }}>
                  {[
                    { label: 'Sold', value: store.totals.sold, color: STAT_COLORS.sold },
                    { label: 'Refs', value: store.totals.referrals, color: STAT_COLORS.referrals },
                    { label: 'Rpts', value: store.totals.repeats, color: STAT_COLORS.repeats },
                  ].map(s => (
                    <View key={s.label} style={{ alignItems: 'center' }}>
                      <Text style={{ fontSize: FS.heading, fontWeight: '800', color: s.color }}>{s.value}</Text>
                      <Text style={{ fontSize: FS.micro, color: colors.textSecondary }}>{s.label}</Text>
                    </View>
                  ))}
                </View>
              </View>

              {store.reps.map((rep: any, idx: number) => (
                <TouchableOpacity
                  key={rep.user_id}
                  onPress={() => router.push(`/sales-list?type=sold&month=${month}&year=${year}&rep_id=${rep.user_id}` as any)}
                  style={{
                    flexDirection: 'row', alignItems: 'center', backgroundColor: colors.card,
                    borderRadius: 16, padding: 12, marginBottom: 8, borderWidth: 1,
                    borderColor: colors.border, gap: 10,
                  }}
                  {...tid(`rep-row-${rep.user_id}`)}
                >
                  <View style={{ width: 26, height: 26, borderRadius: 13, backgroundColor: idx === 0 ? `${colors.accent}25` : colors.surface, alignItems: 'center', justifyContent: 'center' }}>
                    <Text style={{ fontSize: FS.secondary, fontWeight: '700', color: idx === 0 ? colors.accent : colors.textSecondary }}>{idx + 1}</Text>
                  </View>

                  <Text style={{ flex: 1, flexShrink: 1, fontSize: FS.heading, fontWeight: '700', color: colors.text }} numberOfLines={1}>{rep.name}</Text>

                  {[
                    { value: rep.sold, color: STAT_COLORS.sold },
                    { value: rep.referrals, color: STAT_COLORS.referrals },
                    { value: rep.repeats, color: STAT_COLORS.repeats },
                  ].map((s, i) => (
                    <View key={i} style={{ backgroundColor: `${s.color}15`, borderRadius: 8, paddingHorizontal: 10, paddingVertical: 5, minWidth: 36, alignItems: 'center' }}>
                      <Text style={{ fontSize: FS.body, fontWeight: '800', color: s.color }}>{s.value}</Text>
                    </View>
                  ))}

                  <Ionicons name="chevron-forward" size={16} color={colors.textTertiary} />
                </TouchableOpacity>
              ))}
            </View>
          ))}

          <View style={{ flexDirection: 'row', justifyContent: 'center', gap: 20, marginTop: 4 }}>
            {[[STAT_COLORS.sold, 'Sold'], [STAT_COLORS.referrals, 'Referrals'], [STAT_COLORS.repeats, 'Repeats']].map(([c, l]) => (
              <View key={l} style={{ flexDirection: 'row', alignItems: 'center', gap: 5 }}>
                <View style={{ width: 10, height: 10, borderRadius: 5, backgroundColor: c }} />
                <Text style={{ fontSize: FS.caption, color: colors.textSecondary }}>{l}</Text>
              </View>
            ))}
          </View>
        </ScrollView>
      )}
    </SafeAreaView>
  );
}
