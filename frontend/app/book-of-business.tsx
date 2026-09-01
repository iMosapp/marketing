import React, { useEffect, useState, useCallback } from 'react';
import { View, Text, StyleSheet, FlatList, TouchableOpacity, ActivityIndicator, ScrollView, RefreshControl } from 'react-native';
import { Image } from 'expo-image';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useThemeStore } from '../store/themeStore';
import { useAuthStore } from '../store/authStore';
import api from '../services/api';

const GOLD = '#C9A962';

export default function BookOfBusinessScreen() {
  const { colors } = useThemeStore();
  const { user } = useAuthStore();
  const router = useRouter();

  const [summary, setSummary] = useState<any>(null);
  const [active, setActive] = useState<string>('at_risk');
  const [items, setItems] = useState<any[]>([]);
  const [loadingSummary, setLoadingSummary] = useState(true);
  const [loadingList, setLoadingList] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const loadSummary = useCallback(async () => {
    if (!user?._id) return;
    try { const r = await api.get(`/relationship-health/${user._id}/summary`); setSummary(r.data); }
    catch { setSummary(null); }
    finally { setLoadingSummary(false); setRefreshing(false); }
  }, [user?._id]);

  const loadList = useCallback(async (bucket: string) => {
    if (!user?._id) return;
    setLoadingList(true);
    try { const r = await api.get(`/relationship-health/${user._id}/contacts`, { params: { bucket } }); setItems(r.data.items || []); }
    catch { setItems([]); }
    finally { setLoadingList(false); }
  }, [user?._id]);

  useEffect(() => { loadSummary(); }, [loadSummary]);
  useEffect(() => { loadList(active); }, [active, loadList]);

  const activeMeta = summary?.buckets?.find((b: any) => b.key === active);

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      <View style={[st.header, { borderBottomColor: colors.border }]}>
        <TouchableOpacity onPress={() => router.back()} hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }} testID="bob-back">
          <Ionicons name="chevron-back" size={26} color={colors.text} />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={{ fontSize: 19, fontWeight: '800', color: colors.text }}>Book of Business</Text>
          <Text style={{ fontSize: 13, color: colors.textSecondary }}>
            {summary ? `${summary.total} relationships · ${summary.needs_attention} need attention` : 'Loading…'}
          </Text>
        </View>
      </View>

      {loadingSummary ? (
        <View style={{ paddingVertical: 60, alignItems: 'center' }}><ActivityIndicator size="large" color={GOLD} /></View>
      ) : (
        <>
          {/* Bucket tiles */}
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={st.tilesRow} style={{ maxHeight: 108 }}>
            {(summary?.buckets || []).map((b: any) => {
              const isActive = b.key === active;
              return (
                <TouchableOpacity
                  key={b.key}
                  onPress={() => setActive(b.key)}
                  style={[st.tile, { backgroundColor: isActive ? b.color : colors.card, borderColor: isActive ? b.color : colors.surface }]}
                  testID={`bob-tile-${b.key}`}
                >
                  <Text style={{ fontSize: 20 }}>{b.emoji}</Text>
                  <Text style={{ fontSize: 24, fontWeight: '900', color: isActive ? '#fff' : colors.text }}>{b.count}</Text>
                  <Text style={{ fontSize: 11, fontWeight: '700', color: isActive ? '#fff' : colors.textSecondary }} numberOfLines={1}>{b.label}</Text>
                </TouchableOpacity>
              );
            })}
          </ScrollView>

          {activeMeta ? (
            <View style={st.listHeader}>
              <Ionicons name={activeMeta.icon} size={16} color={activeMeta.color} />
              <Text style={{ fontSize: 14, fontWeight: '700', color: colors.text }}>{activeMeta.label} · {activeMeta.count}</Text>
            </View>
          ) : null}

          {loadingList ? (
            <View style={{ paddingVertical: 40, alignItems: 'center' }}><ActivityIndicator color={GOLD} /></View>
          ) : (
            <FlatList
              data={items}
              keyExtractor={(item) => item.contact_id}
              contentContainerStyle={{ paddingHorizontal: 16, paddingBottom: 32 }}
              refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); loadSummary(); loadList(active); }} tintColor={GOLD} />}
              ListEmptyComponent={
                <View style={{ alignItems: 'center', padding: 40 }}>
                  <Text style={{ fontSize: 15, color: colors.textSecondary, textAlign: 'center' }}>No one in this group right now.</Text>
                </View>
              }
              renderItem={({ item }) => (
                <TouchableOpacity
                  style={[st.row, { backgroundColor: colors.card, borderColor: colors.surface }]}
                  onPress={() => router.push(`/contact/${item.contact_id}` as any)}
                  testID={`bob-item-${item.contact_id}`}
                >
                  <View style={[st.avatar, { backgroundColor: `${activeMeta?.color || GOLD}22` }]}>
                    {item.photo_thumbnail ? (
                      <Image source={{ uri: item.photo_thumbnail }} style={[StyleSheet.absoluteFillObject, { borderRadius: 22 }]} contentFit="cover" cachePolicy="memory-disk" transition={150} />
                    ) : (
                      <Text style={{ color: activeMeta?.color || GOLD, fontWeight: '800' }}>
                        {`${(item.name || '?')[0]}`.toUpperCase()}
                      </Text>
                    )}
                  </View>
                  <View style={{ flex: 1 }}>
                    <Text style={{ fontSize: 16, fontWeight: '700', color: colors.text }} numberOfLines={1}>{item.name}</Text>
                    <Text style={{ fontSize: 13, color: colors.textSecondary, marginTop: 2 }} numberOfLines={1}>{item.reason}</Text>
                  </View>
                  <Ionicons name="chevron-forward" size={16} color={colors.borderLight} />
                </TouchableOpacity>
              )}
            />
          )}
        </>
      )}
    </SafeAreaView>
  );
}

const st = StyleSheet.create({
  header: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 14, borderBottomWidth: 1, gap: 12 },
  tilesRow: { paddingHorizontal: 16, paddingVertical: 12, gap: 10 },
  tile: { width: 84, borderRadius: 14, borderWidth: 1, alignItems: 'center', justifyContent: 'center', paddingVertical: 10, gap: 2 },
  listHeader: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingHorizontal: 16, paddingBottom: 8 },
  row: { flexDirection: 'row', alignItems: 'center', borderRadius: 14, padding: 12, marginBottom: 8, borderWidth: 1, gap: 12 },
  avatar: { width: 44, height: 44, borderRadius: 22, alignItems: 'center', justifyContent: 'center', overflow: 'hidden' },
});
