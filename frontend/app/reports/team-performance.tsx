import React, { useEffect, useState } from 'react';
import { View, Text, FlatList, TouchableOpacity, ActivityIndicator, ScrollView } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useThemeStore } from '../../store/themeStore';
import { useAuthStore } from '../../store/authStore';
import api from '../../services/api';

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

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      {/* Header */}
      <View style={{ flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 14, borderBottomWidth: 1, borderBottomColor: colors.border, gap: 12 }}>
        <TouchableOpacity onPress={() => router.back()} hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}>
          <Ionicons name="chevron-back" size={26} color={colors.text} />
        </TouchableOpacity>
        <Text style={{ flex: 1, fontSize: 19, fontWeight: '700', color: colors.text }}>Team Performance</Text>
      </View>

      {/* Month picker */}
      <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'center', paddingVertical: 12, gap: 20 }}>
        <TouchableOpacity onPress={() => changeMonth(-1)} hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}>
          <Ionicons name="chevron-back" size={22} color={colors.text} />
        </TouchableOpacity>
        <Text style={{ fontSize: 17, fontWeight: '700', color: colors.text, minWidth: 140, textAlign: 'center' }}>
          {data?.month_label || `${new Date(year, month - 1).toLocaleString('default', { month: 'long', year: 'numeric' })}`}
        </Text>
        <TouchableOpacity onPress={() => changeMonth(1)} hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}>
          <Ionicons name="chevron-forward" size={22} color={colors.text} />
        </TouchableOpacity>
      </View>

      {loading ? (
        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}>
          <ActivityIndicator size="large" color="#C9A962" />
        </View>
      ) : !data?.stores?.length ? (
        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', padding: 32 }}>
          <Text style={{ fontSize: 16, color: colors.textSecondary, textAlign: 'center' }}>No team data available. Reps need a store assigned.</Text>
        </View>
      ) : (
        <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 40 }}>
          {data.stores.map((store: any) => (
            <View key={store.store_id} style={{ marginBottom: 24 }}>
              {/* Store header */}
              <View style={{ flexDirection: 'row', alignItems: 'center', marginBottom: 10, gap: 8 }}>
                <Ionicons name="business" size={18} color="#C9A962" />
                <Text style={{ fontSize: 17, fontWeight: '800', color: colors.text }}>{store.store_name}</Text>
                <View style={{ flex: 1 }} />
                {/* Store totals */}
                <View style={{ flexDirection: 'row', gap: 12 }}>
                  {[
                    { label: 'Sold', value: store.totals.sold, color: '#C9A962' },
                    { label: 'Refs', value: store.totals.referrals, color: '#007AFF' },
                    { label: 'Rpts', value: store.totals.repeats, color: '#AF52DE' },
                  ].map(s => (
                    <View key={s.label} style={{ alignItems: 'center' }}>
                      <Text style={{ fontSize: 16, fontWeight: '800', color: s.color }}>{s.value}</Text>
                      <Text style={{ fontSize: 10, color: colors.textSecondary }}>{s.label}</Text>
                    </View>
                  ))}
                </View>
              </View>

              {/* Rep rows */}
              {store.reps.map((rep: any, idx: number) => (
                <TouchableOpacity
                  key={rep.user_id}
                  onPress={() => router.push(`/sales-list?type=sold&month=${month}&year=${year}&rep_id=${rep.user_id}` as any)}
                  style={{
                    flexDirection: 'row', alignItems: 'center', backgroundColor: colors.card,
                    borderRadius: 12, padding: 12, marginBottom: 6, borderWidth: 1,
                    borderColor: colors.surface, gap: 10,
                  }}
                  data-testid={`rep-row-${rep.user_id}`}
                >
                  {/* Rank */}
                  <View style={{ width: 26, height: 26, borderRadius: 13, backgroundColor: idx === 0 ? '#C9A96225' : colors.surface, alignItems: 'center', justifyContent: 'center' }}>
                    <Text style={{ fontSize: 13, fontWeight: '700', color: idx === 0 ? '#C9A962' : colors.textSecondary }}>{idx + 1}</Text>
                  </View>

                  {/* Name */}
                  <Text style={{ flex: 1, fontSize: 15, fontWeight: '600', color: colors.text }} numberOfLines={1}>{rep.name}</Text>

                  {/* Stats */}
                  {[
                    { value: rep.sold, color: '#C9A962', bg: '#C9A96215' },
                    { value: rep.referrals, color: '#007AFF', bg: '#007AFF15' },
                    { value: rep.repeats, color: '#AF52DE', bg: '#AF52DE15' },
                  ].map((s, i) => (
                    <View key={i} style={{ backgroundColor: s.bg, borderRadius: 8, paddingHorizontal: 10, paddingVertical: 5, minWidth: 36, alignItems: 'center' }}>
                      <Text style={{ fontSize: 15, fontWeight: '800', color: s.color }}>{s.value}</Text>
                    </View>
                  ))}

                  <Ionicons name="chevron-forward" size={14} color={colors.borderLight} />
                </TouchableOpacity>
              ))}
            </View>
          ))}

          {/* Legend */}
          <View style={{ flexDirection: 'row', justifyContent: 'center', gap: 20, marginTop: 8 }}>
            {[['#C9A962', 'Sold'], ['#007AFF', 'Referrals'], ['#AF52DE', 'Repeats']].map(([c, l]) => (
              <View key={l} style={{ flexDirection: 'row', alignItems: 'center', gap: 5 }}>
                <View style={{ width: 10, height: 10, borderRadius: 5, backgroundColor: c }} />
                <Text style={{ fontSize: 12, color: colors.textSecondary }}>{l}</Text>
              </View>
            ))}
          </View>
        </ScrollView>
      )}
    </SafeAreaView>
  );
}
