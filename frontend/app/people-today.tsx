import React, { useEffect, useState, useCallback } from 'react';
import { View, Text, StyleSheet, FlatList, TouchableOpacity, ActivityIndicator, RefreshControl } from 'react-native';
import { Avatar } from '../components/Avatar';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useThemeStore } from '../store/themeStore';
import { useAuthStore } from '../store/authStore';
import api from '../services/api';

const GOLD = '#C9A962';

export default function PeopleTodayScreen() {
  const { colors } = useThemeStore();
  const { user } = useAuthStore();
  const router = useRouter();
  const [people, setPeople] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    if (!user?._id) return;
    try {
      const r = await api.get(`/home/people-to-engage/${user._id}`, { params: { limit: 30 } });
      setPeople(r.data.people || []);
    } catch { setPeople([]); }
    finally { setLoading(false); setRefreshing(false); }
  }, [user?._id]);

  useEffect(() => { load(); }, [load]);


  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      <View style={[st.header, { borderBottomColor: colors.border }]}>
        <TouchableOpacity onPress={() => router.back()} hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }} testID="people-today-back">
          <Ionicons name="chevron-back" size={26} color={colors.text} />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={{ fontSize: 19, fontWeight: '800', color: colors.text }}>People to Talk To Today</Text>
          <Text style={{ fontSize: 13, color: colors.textSecondary }}>{people.length} worth reaching out to, and why</Text>
        </View>
      </View>

      {loading ? (
        <View style={{ paddingVertical: 60, alignItems: 'center' }}><ActivityIndicator size="large" color={GOLD} /></View>
      ) : (
        <FlatList
          data={people}
          keyExtractor={(item) => item.contact_id}
          contentContainerStyle={{ padding: 16, paddingBottom: 32 }}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} tintColor={GOLD} />}
          ListEmptyComponent={
            <View style={{ alignItems: 'center', padding: 40 }}>
              <Ionicons name="sparkles-outline" size={48} color={colors.borderLight} />
              <Text style={{ fontSize: 15, color: colors.textSecondary, textAlign: 'center', marginTop: 16 }}>You're all caught up - no one needs a nudge right now.</Text>
            </View>
          }
          renderItem={({ item }) => (
            <View style={[st.card, { backgroundColor: colors.card, borderColor: colors.surface }]} testID={`people-today-item-${item.contact_id}`}>
              <TouchableOpacity style={st.rowTop} onPress={() => router.push(`/contact/${item.contact_id}` as any)} activeOpacity={0.7}>
                <Avatar
                  photo={item.photo_url}
                  name={`${item.first_name || ''} ${item.last_name || ''}`.trim()}
                  sizePx={48}
                  color={`${item.color || GOLD}22`}
                  textStyle={{ color: item.color || GOLD, fontWeight: '800', fontSize: 16 }}
                  style={st.avatar}
                />
                <View style={{ flex: 1 }}>
                  <Text style={{ fontSize: 16, fontWeight: '700', color: colors.text }} numberOfLines={1}>
                    {`${item.first_name || ''} ${item.last_name || ''}`.trim() || item.phone || 'Contact'}
                  </Text>
                  <View style={st.reasonRow}>
                    <Ionicons name={item.icon || 'flash'} size={13} color={item.color || GOLD} />
                    <Text style={{ fontSize: 13, color: item.color || GOLD, fontWeight: '600', flex: 1 }} numberOfLines={1}>{item.reason_label}</Text>
                  </View>
                  {item.hook ? (
                    <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 2 }} numberOfLines={1}>💬 {item.hook}</Text>
                  ) : null}
                </View>
              </TouchableOpacity>
              <TouchableOpacity
                style={[st.cta, { backgroundColor: GOLD }]}
                onPress={() => router.push(`/contact/${item.contact_id}` as any)}
                testID={`people-today-start-${item.contact_id}`}
              >
                <Ionicons name="chatbubble-ellipses" size={16} color="#1a1a1a" />
                <Text style={{ color: '#1a1a1a', fontWeight: '800', fontSize: 14 }}>{item.action_label || 'Start Conversation'}</Text>
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
  reasonRow: { flexDirection: 'row', alignItems: 'center', gap: 5, marginTop: 3 },
  cta: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, borderRadius: 12, paddingVertical: 11 },
});
