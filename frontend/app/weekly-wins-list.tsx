import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, FlatList, TouchableOpacity, ActivityIndicator } from 'react-native';
import { Image } from 'expo-image';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useThemeStore } from '../store/themeStore';
import { useAuthStore } from '../store/authStore';
import api from '../services/api';

const GOLD = '#C9A962';

const META: Record<string, { icon: string; color: string; empty: string }> = {
  sold:     { icon: 'trophy',      color: GOLD,      empty: 'No sales logged last week' },
  texts:    { icon: 'chatbubble',  color: '#34C759', empty: 'No texts sent last week' },
  scans:    { icon: 'qr-code',     color: '#AF52DE', empty: 'No QR/card scans last week' },
  contacts: { icon: 'person-add',  color: '#FF9500', empty: 'No new contacts last week' },
};

export default function WeeklyWinsListScreen() {
  const { colors } = useThemeStore();
  const { user } = useAuthStore();
  const router = useRouter();
  const params = useLocalSearchParams<{ type: string }>();
  const type = params.type || 'sold';
  const meta = META[type] || META.sold;

  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!user?._id) return;
    setLoading(true);
    api.get(`/home/weekly-wins/${user._id}/list`, { params: { type } })
      .then(r => setData(r.data))
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [user?._id, type]);

  const items = data?.items || [];
  const range = data
    ? `${new Date(data.week_start).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })} – ${new Date(new Date(data.week_end).getTime() - 86400000).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}`
    : 'Last week';

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      <View style={[st.header, { borderBottomColor: colors.border }]}>
        <TouchableOpacity onPress={() => router.back()} hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }} testID="wins-list-back" dataSet={{ testid: 'wins-list-back' }}>
          <Ionicons name="chevron-back" size={26} color={colors.text} />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={{ fontSize: 19, fontWeight: '700', color: colors.text }}>{data?.title || "Last Week's Wins"}</Text>
          <Text style={{ fontSize: 13, color: colors.textSecondary }}>{range}</Text>
        </View>
        <View style={[st.badge, { backgroundColor: `${meta.color}22` }]}>
          <Ionicons name={meta.icon as any} size={15} color={meta.color} />
          <Text style={{ fontSize: 15, fontWeight: '800', color: meta.color }}>{data?.count ?? 0}</Text>
        </View>
      </View>

      {loading ? (
        <View style={{ paddingVertical: 60, alignItems: 'center' }}>
          <ActivityIndicator size="large" color={GOLD} />
        </View>
      ) : (
        <FlatList
          data={items}
          keyExtractor={(item) => item.id}
          contentContainerStyle={{ padding: 16, paddingBottom: 32 }}
          ListEmptyComponent={
            <View style={{ alignItems: 'center', padding: 40 }}>
              <Ionicons name={meta.icon as any} size={48} color={colors.borderLight} />
              <Text style={{ fontSize: 15, color: colors.textSecondary, textAlign: 'center', marginTop: 16 }}>{meta.empty}</Text>
            </View>
          }
          renderItem={({ item }) => {
            const tappable = !!item.contact_id;
            return (
              <TouchableOpacity
                disabled={!tappable}
                onPress={() => tappable && router.push(`/contact/${item.contact_id}` as any)}
                style={[st.row, { backgroundColor: colors.card, borderColor: colors.surface, opacity: tappable ? 1 : 0.9 }]}
                testID={`wins-list-item-${item.id}`} dataSet={{ testid: `wins-list-item-${item.id}` }}
              >
                <View style={[st.avatar, { backgroundColor: `${meta.color}20` }]}>
                  {item.photo_thumbnail ? (
                    <Image source={{ uri: item.photo_thumbnail }} style={[StyleSheet.absoluteFillObject, { borderRadius: 22 }]} contentFit="cover" cachePolicy="memory-disk" transition={150} />
                  ) : (
                    <Ionicons name={meta.icon as any} size={18} color={meta.color} />
                  )}
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={{ fontSize: 16, fontWeight: '700', color: colors.text }} numberOfLines={1}>{item.name}</Text>
                  {item.subtitle ? (
                    <Text style={{ fontSize: 13, color: colors.textSecondary, marginTop: 2 }} numberOfLines={1}>{item.subtitle}</Text>
                  ) : null}
                </View>
                <View style={{ alignItems: 'flex-end', gap: 4 }}>
                  {item.date ? (
                    <Text style={{ fontSize: 12, color: colors.textSecondary }}>
                      {new Date(item.date).toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })}
                    </Text>
                  ) : null}
                  {tappable ? <Ionicons name="chevron-forward" size={16} color={colors.borderLight} /> : null}
                </View>
              </TouchableOpacity>
            );
          }}
        />
      )}
    </SafeAreaView>
  );
}

const st = StyleSheet.create({
  header: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 14, borderBottomWidth: 1, gap: 12 },
  badge: { flexDirection: 'row', alignItems: 'center', gap: 5, borderRadius: 14, paddingHorizontal: 12, paddingVertical: 6 },
  row: { flexDirection: 'row', alignItems: 'center', borderRadius: 14, padding: 14, marginBottom: 8, borderWidth: 1, gap: 12 },
  avatar: { width: 44, height: 44, borderRadius: 22, alignItems: 'center', justifyContent: 'center', overflow: 'hidden' },
});
