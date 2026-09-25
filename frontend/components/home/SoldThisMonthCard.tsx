import React, { useCallback, useState } from 'react';
import { View, Text, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import { useThemeStore } from '../../store/themeStore';
import api from '../../services/api';
import { GOLD, GREEN, RED, RADIUS, SPACE, TYPE, tid, tint } from '../ui/tokens';

/** This month's Sold / Referrals / Repeats with month-over-month change. On Home (bottom) and My Numbers. */
export function SoldThisMonthCard({ userId }: { userId: string }) {
  const router = useRouter();
  const { colors } = useThemeStore();
  const [perf, setPerf] = useState<any>(null);

  useFocusEffect(useCallback(() => {
    if (!userId) return;
    api.get(`/users/${userId}/sold-performance`, { params: { month: new Date().getMonth() + 1, year: new Date().getFullYear() } })
      .then(r => setPerf(r.data)).catch(() => {});
  }, [userId]));

  if (!perf) return null;
  const up = (perf.mom_change || 0) > 0;
  const stats = [
    { label: 'Sold', value: perf.current_month?.total || 0, color: GOLD, icon: 'trophy', hero: true, route: '/sales-list?type=sold' },
    { label: 'Referrals', value: perf.current_month?.referrals || 0, color: colors.text, icon: 'people', route: '/sales-list?type=referrals' },
    { label: 'Repeats', value: perf.current_month?.repeats || 0, color: colors.text, icon: 'repeat', route: '/sales-list?type=repeats' },
  ];
  return (
    <View style={{ marginHorizontal: SPACE.lg, marginBottom: SPACE.lg, backgroundColor: colors.card, borderRadius: RADIUS.lg, padding: SPACE.lg, borderWidth: 1, borderColor: tint(GOLD, 0.3) }} {...tid('sold-this-month-card')}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: SPACE.md }}>
        <Ionicons name="trophy" size={17} color={GOLD} />
        <Text style={{ fontSize: TYPE.body, fontWeight: '700', color: colors.text, flex: 1 }}>{new Date().toLocaleString('default', { month: 'long' })} Sales</Text>
        {perf.mom_change !== 0 && (
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: tint(up ? GREEN : RED, 0.12), paddingHorizontal: 8, paddingVertical: 3, borderRadius: 8 }}>
            <Ionicons name={up ? 'trending-up' : 'trending-down'} size={12} color={up ? GREEN : RED} />
            <Text style={{ fontSize: TYPE.caption, fontWeight: '700', color: up ? GREEN : RED }}>{up ? '+' : ''}{perf.mom_change} vs prev</Text>
          </View>
        )}
      </View>
      <View style={{ flexDirection: 'row', gap: SPACE.sm }}>
        {stats.map(s => (
          <TouchableOpacity key={s.label} onPress={() => router.push(s.route as any)} activeOpacity={0.8}
            style={{ flex: s.hero ? 1.5 : 1, backgroundColor: s.hero ? tint(GOLD, 0.14) : colors.bg, borderWidth: 1, borderColor: s.hero ? tint(GOLD, 0.4) : colors.border, borderRadius: RADIUS.md, padding: SPACE.md, alignItems: 'center', gap: 4 }}
            {...tid(`sold-stat-${s.label.toLowerCase()}`)}>
            <Ionicons name={s.icon as any} size={s.hero ? 22 : 18} color={s.hero ? GOLD : colors.textSecondary} />
            <Text style={{ fontSize: s.hero ? 28 : 20, fontWeight: '800', color: s.color }}>{s.value}</Text>
            <Text style={{ fontSize: TYPE.label, fontWeight: '600', color: colors.textSecondary }} numberOfLines={1}>{s.label}</Text>
          </TouchableOpacity>
        ))}
      </View>
      {perf.all_time_sold > 0 && (
        <Text style={{ fontSize: TYPE.caption, color: colors.textTertiary, textAlign: 'center', marginTop: SPACE.sm }}>
          {perf.all_time_sold} total sold · {perf.all_time_referrals} referrals all-time
        </Text>
      )}
    </View>
  );
}
