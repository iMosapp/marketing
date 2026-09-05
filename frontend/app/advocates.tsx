import React, { useEffect, useState, useCallback } from 'react';
import { View, Text, StyleSheet, FlatList, TouchableOpacity, ActivityIndicator, RefreshControl } from 'react-native';
import { Avatar } from '../components/Avatar';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useThemeStore } from '../store/themeStore';
import { useAuthStore } from '../store/authStore';
import api from '../services/api';
import { ThankSheet } from '../components/advocates/ThankSheet';
import { useToast } from '../components/common/Toast';

const BLUE = '#0A84FF';

export default function AdvocatesScreen() {
  const { colors } = useThemeStore();
  const { user } = useAuthStore();
  const router = useRouter();
  const { showToast } = useToast();
  const [items, setItems] = useState<any[]>([]);
  const [thanked30, setThanked30] = useState(0);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [target, setTarget] = useState<any | null>(null);

  const load = useCallback(async () => {
    if (!user?._id) return;
    try { const r = await api.get(`/relationship-health/${user._id}/advocates`); setItems(r.data.items || []); setThanked30(r.data.thanked_30d || 0); }
    catch { setItems([]); }
    finally { setLoading(false); setRefreshing(false); }
  }, [user?._id]);

  useEffect(() => { load(); }, [load]);

  const onSent = (contactId: string, result: any) => {
    const was = items.find(i => i.contact_id === contactId);
    if (was && (was.thanked_days == null || was.thanked_days > 30)) setThanked30(n => n + 1);
    setItems(prev => prev.map(i => (i.contact_id === contactId ? { ...i, thanked_days: 0, days_since: 0 } : i)));
    const name = items.find(i => i.contact_id === contactId)?.first_name || 'them';
    showToast(result.mode === 'card' ? `Thank-you card sent to ${name}` : `Thank-you text sent to ${name}`, 'success');
  };

  const thankedLabel = (d: number | null | undefined) => (d == null ? null : d === 0 ? 'Thanked today' : d === 1 ? 'Thanked yesterday' : `Thanked ${d}d ago`);

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      <View style={[st.header, { borderBottomColor: colors.border }]}>
        <TouchableOpacity onPress={() => router.back()} hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }} testID="advocates-back">
          <Ionicons name="chevron-back" size={26} color={colors.text} />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={{ fontSize: 19, fontWeight: '800', color: colors.text }}>Your Advocates 💙</Text>
          <Text style={{ fontSize: 13, color: colors.textSecondary }}>
            {items.length} champions who review &amp; refer you{thanked30 > 0 ? ` · ${thanked30} thanked this month` : ''}
          </Text>
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
                <Avatar
                  photo={item.photo_thumbnail}
                  name={item.name || '?'}
                  sizePx={48}
                  color={`${BLUE}22`}
                  textStyle={{ color: BLUE, fontWeight: '800', fontSize: 16 }}
                  style={st.avatar}
                />
                <View style={{ flex: 1 }}>
                  <Text style={{ fontSize: 16, fontWeight: '700', color: colors.text }} numberOfLines={1}>{item.name}</Text>
                  <Text style={{ fontSize: 13, color: colors.textSecondary, marginTop: 2 }} numberOfLines={1}>
                    {item.thanked_days === 0 ? 'Thanked today' : `${item.days_since != null ? `Last touch ${item.days_since}d ago` : 'Loyal customer'}${thankedLabel(item.thanked_days) ? ` · ${thankedLabel(item.thanked_days)}` : ''}`}
                  </Text>
                </View>
                <View style={[st.pill, { backgroundColor: `${BLUE}18` }]}>
                  <Text style={{ fontSize: 11, fontWeight: '800', color: BLUE }}>ADVOCATE</Text>
                </View>
              </TouchableOpacity>
              <TouchableOpacity
                style={[st.cta, item.thanked_days === 0 ? { backgroundColor: `${BLUE}18`, borderWidth: 1, borderColor: `${BLUE}55` } : { backgroundColor: BLUE }]}
                onPress={() => setTarget(item)}
                testID={`advocate-thank-${item.contact_id}`}
              >
                <Ionicons name={item.thanked_days === 0 ? 'checkmark-circle' : 'heart'} size={16} color={item.thanked_days === 0 ? BLUE : '#fff'} />
                <Text style={{ color: item.thanked_days === 0 ? BLUE : '#fff', fontWeight: '800', fontSize: 14 }}>
                  {item.thanked_days === 0 ? 'Thanked today · send another' : item.thanked_days != null ? 'Thank again' : 'Say Thanks'}
                </Text>
              </TouchableOpacity>
            </View>
          )}
        />
      )}
      <ThankSheet visible={!!target} userId={user?._id || ''} advocate={target} colors={colors} onClose={() => setTarget(null)} onSent={onSent} />
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
