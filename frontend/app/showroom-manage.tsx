import React, { useState, useEffect, useCallback } from 'react';
import {
  View, Text, ScrollView, TouchableOpacity, Image, StyleSheet,
  SafeAreaView, ActivityIndicator, Switch,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import AsyncStorage from '@react-native-async-storage/async-storage';
import api from '../services/api';

import { useThemeStore } from '../store/themeStore';
interface ShowroomEntry {
  card_id: string;
  customer_name: string;
  customer_photo: string;
  hidden: boolean;
  views: number;
  created_at: string | null;
}

export default function ManageShowroom() {
  const { colors } = useThemeStore();
  const s = getS(colors);
  const router = useRouter();
  const [user, setUser] = useState<any>(null);
  const [entries, setEntries] = useState<ShowroomEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [toggling, setToggling] = useState<string | null>(null);

  useEffect(() => {
    AsyncStorage.getItem('user').then(u => u && setUser(JSON.parse(u)));
  }, []);

  const loadEntries = useCallback(async () => {
    if (!user) return;
    setLoading(true);
    try {
      const res = await api.get(`/showcase/manage/${user._id}`);
      setEntries(res.data || []);
    } catch (e) {
      console.error('Failed to load showroom entries', e);
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => { loadEntries(); }, [loadEntries]);

  const toggleVisibility = async (cardId: string, currentHidden: boolean) => {
    setToggling(cardId);
    try {
      await api.put(`/showcase/entry/${cardId}/${currentHidden ? 'show' : 'hide'}`);
      setEntries(prev => prev.map(e =>
        e.card_id === cardId ? { ...e, hidden: !currentHidden } : e
      ));
    } catch (e) {
      console.error('Failed to toggle visibility', e);
    } finally {
      setToggling(null);
    }
  };

  const visibleCount = entries.filter(e => !e.hidden).length;
  const hiddenCount = entries.filter(e => e.hidden).length;

  return (
    <SafeAreaView style={s.safe}>
      <View style={s.header}>
        <TouchableOpacity onPress={() => router.back()} style={s.backBtn} data-testid="manage-showroom-back">
          <Ionicons name="chevron-back" size={24} color={colors.bg} />
        </TouchableOpacity>
        <Text style={s.headerTitle}>Edit Showcase</Text>
        <View style={{ width: 32 }} />
      </View>

      <View style={s.statsRow}>
        <View style={s.stat}>
          <Text style={s.statNum}>{visibleCount}</Text>
          <Text style={s.statLabel}>Visible</Text>
        </View>
        <View style={[s.stat, { borderLeftWidth: 1, borderLeftColor: colors.surface }]}>
          <Text style={[s.statNum, { color: colors.textTertiary }]}>{hiddenCount}</Text>
          <Text style={s.statLabel}>Hidden</Text>
        </View>
        <View style={[s.stat, { borderLeftWidth: 1, borderLeftColor: colors.surface }]}>
          <Text style={s.statNum}>{entries.length}</Text>
          <Text style={s.statLabel}>Total</Text>
        </View>
      </View>

      <Text style={s.hint}>Toggle off entries you don't want on your public Showcase page.</Text>

      {loading ? (
        <View style={s.center}><ActivityIndicator size="large" color="#C9A962" /></View>
      ) : entries.length === 0 ? (
        <View style={s.center}>
          <Ionicons name="images-outline" size={48} color={colors.textTertiary} />
          <Text style={s.emptyText}>No Showcase entries yet</Text>
          <Text style={s.emptySubtext}>Create a Congrats Card to add your first entry</Text>
        </View>
      ) : (
        <ScrollView style={s.list} contentContainerStyle={s.listContent}>
          {entries.map((entry) => (
            <View key={entry.card_id} style={[s.card, entry.hidden && s.cardHidden]} data-testid={`showroom-entry-${entry.card_id}`}>
              <Image source={{ uri: entry.customer_photo }} style={s.thumb} resizeMode="cover" />
              <View style={s.info}>
                <Text style={[s.name, entry.hidden && s.nameHidden]}>{entry.customer_name || 'Customer'}</Text>
                <Text style={s.meta}>
                  {entry.views} view{entry.views !== 1 ? 's' : ''}
                  {entry.created_at ? ` · ${new Date(entry.created_at).toLocaleDateString()}` : ''}
                </Text>
              </View>
              <View style={s.toggleWrap}>
                {toggling === entry.card_id ? (
                  <ActivityIndicator size="small" color="#C9A962" />
                ) : (
                  <Switch
                    value={!entry.hidden}
                    onValueChange={() => toggleVisibility(entry.card_id, entry.hidden)}
                    trackColor={{ false: '#39393D', true: '#34C759' }}
                    thumbColor={colors.bg}
                    data-testid={`toggle-${entry.card_id}`}
                  />
                )}
              </View>
            </View>
          ))}
        </ScrollView>
      )}
    </SafeAreaView>
  );
}

const getS = (colors: any) => StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 12 },
  backBtn: { padding: 4 },
  headerTitle: { fontSize: 18, fontWeight: '800', color: colors.bg, letterSpacing: 0.5 },
  statsRow: { flexDirection: 'row', marginHorizontal: 16, backgroundColor: colors.card, borderRadius: 14, marginBottom: 12, overflow: 'hidden' },
  stat: { flex: 1, alignItems: 'center', paddingVertical: 14 },
  statNum: { fontSize: 22, fontWeight: '800', color: '#C9A962' },
  statLabel: { fontSize: 11, color: '#8E8E93', marginTop: 2, textTransform: 'uppercase', letterSpacing: 0.5 },
  hint: { fontSize: 13, color: '#636366', paddingHorizontal: 16, marginBottom: 12 },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', gap: 8 },
  emptyText: { fontSize: 16, fontWeight: '600', color: '#8E8E93' },
  emptySubtext: { fontSize: 13, color: '#636366' },
  list: { flex: 1 },
  listContent: { paddingHorizontal: 16, paddingBottom: 40, gap: 8 },
  card: { flexDirection: 'row', alignItems: 'center', backgroundColor: colors.card, borderRadius: 14, padding: 12, gap: 12 },
  cardHidden: { opacity: 0.5 },
  thumb: { width: 56, height: 56, borderRadius: 10, backgroundColor: colors.surface },
  info: { flex: 1 },
  name: { fontSize: 15, fontWeight: '600', color: colors.bg },
  nameHidden: { color: '#636366' },
  meta: { fontSize: 12, color: '#8E8E93', marginTop: 2 },
  toggleWrap: { width: 52, alignItems: 'center' },
});
