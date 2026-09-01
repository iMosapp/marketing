import React, { useEffect, useState, useCallback } from 'react';
import { View, Text, StyleSheet, FlatList, TouchableOpacity, ActivityIndicator, RefreshControl } from 'react-native';
import { Image } from 'expo-image';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useThemeStore } from '../store/themeStore';
import { useAuthStore } from '../store/authStore';
import api from '../services/api';

const BLUE = '#0A84FF';

export default function AdvocatesScreen() {
  const { colors } = useThemeStore();
  const { user } = useAuthStore();
  const router = useRouter();
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    if (!user?._id) return;
    try { const r = await api.get(`/relationship-health/${user._id}/advocates`); setItems(r.data.items || []); }
    catch { setItems([]); }
    finally { setLoading(false); setRefreshing(false); }
  }, [user?._id]);

  useEffect(() => { load(); }, [load]);

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      <View style={[st.header, { borderBottomColor: colors.border }]}>
        <TouchableOpacity onPress={() => router.back()} hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }} testID="advocates-back">
          <Ionicons name="chevron-back" size={26} color={colors.text} />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={{ fontSize: 19, fontWeight: '800', color: colors.text }}>Your Advocates 💙</Text>
          <Text style={{ fontSize: 13, color: colors.textSecondary }}>{items.length} champions who review &amp; refer you</Text>
        </View>
      </View>

      {loading ? (
        <View style={{ paddingVertical: 60, alignItems: 'center' }}><ActivityIndicator size="large" color={BLUE} /></View>
      ) : (
        <FlatList
          data={items}
          keyExtractor={(item) => item.contact_id}
          contentContainerStyle={{ padding: 16, paddingBottom: 32 }}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} tintColor={BLUE} />}
          ListEmptyComponent={
            <View style={{ alignItems: 'center', padding: 40 }}>
              <Ionicons name="heart-outline" size={48} color={colors.borderLight} />
              <Text style={{ fontSize: 15, color: colors.textSecondary, textAlign: 'center', marginTop: 16 }}>No advocates yet. Ask a happy customer for a review or a referral to start your list.</Text>
            </View>
          }
          renderItem={({ item }) => (
            <View style={[st.card, { backgroundColor: colors.card, borderColor: `${BLUE}30` }]} testID={`advocate-item-${item.contact_id}`}>
              <TouchableOpacity style={st.rowTop} onPress={() => router.push(`/contact/${item.contact_id}` as any)} activeOpacity={0.7}>
                <View style={[st.avatar, { backgroundColor: `${BLUE}22` }]}>
                  {item.photo_thumbnail ? (
                    <Image source={{ uri: item.photo_thumbnail }} style={[StyleSheet.absoluteFillObject, { borderRadius: 24 }]} contentFit="cover" cachePolicy="memory-disk" transition={150} />
                  ) : (
                    <Text style={{ color: BLUE, fontWeight: '800', fontSize: 16 }}>{`${(item.name || '?')[0]}`.toUpperCase()}</Text>
                  )}
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={{ fontSize: 16, fontWeight: '700', color: colors.text }} numberOfLines={1}>{item.name}</Text>
                  <Text style={{ fontSize: 13, color: colors.textSecondary, marginTop: 2 }} numberOfLines={1}>
                    {item.days_since != null ? `Last touch ${item.days_since}d ago` : 'Loyal customer'}
                  </Text>
                </View>
                <View style={[st.pill, { backgroundColor: `${BLUE}18` }]}>
                  <Text style={{ fontSize: 11, fontWeight: '800', color: BLUE }}>ADVOCATE</Text>
                </View>
              </TouchableOpacity>
              <TouchableOpacity
                style={[st.cta, { backgroundColor: BLUE }]}
                onPress={() => router.push(`/contact/${item.contact_id}` as any)}
                testID={`advocate-thank-${item.contact_id}`}
              >
                <Ionicons name="heart" size={16} color="#fff" />
                <Text style={{ color: '#fff', fontWeight: '800', fontSize: 14 }}>Say Thanks</Text>
              </TouchableOpacity>
            </View>
          )}
        />
      )}
    </SafeAreaView>
  );
}

const st = StyleSheet.create({
  header: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 14, borderBottomWidth: 1, gap: 12 },
  card: { borderRadius: 16, padding: 14, marginBottom: 10, borderWidth: 1, gap: 12 },
  rowTop: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  avatar: { width: 48, height: 48, borderRadius: 24, alignItems: 'center', justifyContent: 'center', overflow: 'hidden' },
  pill: { borderRadius: 10, paddingHorizontal: 8, paddingVertical: 4 },
  cta: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, borderRadius: 12, paddingVertical: 11 },
});
