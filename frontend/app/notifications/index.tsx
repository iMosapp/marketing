import React, { useState, useCallback, useEffect, useRef } from 'react';
import { View, Text, TouchableOpacity, ScrollView, StyleSheet, ActivityIndicator, RefreshControl } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useAuthStore } from '../../store/authStore';
import api from '../../services/api';
import { useThemeStore } from '../../store/themeStore';
import { showConfirm } from '../../services/alert';
import { AlertRow, AlertItem } from '../../components/notifications/AlertRow';

const GOLD = '#C9A962';
const RED = '#FF3B30';

const tid = (id: string): any => ({ testID: id, dataSet: { testid: id } });

const BUCKETS: { key: AlertItem['bucket']; label: string; color: string }[] = [
  { key: 'now', label: 'NOW', color: RED },
  { key: 'today', label: 'TODAY', color: GOLD },
  { key: 'later', label: 'LATER', color: '#8E8E93' },
];

export default function AlertsPage() {
  const { colors } = useThemeStore();
  const styles = getStyles(colors);
  const router = useRouter();
  const { user } = useAuthStore();
  const [items, setItems] = useState<AlertItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [undo, setUndo] = useState<{ ids: string[]; items: AlertItem[]; label: string } | null>(null);
  const undoTimer = useRef<any>(null);

  const fetchAlerts = useCallback(async () => {
    if (!user?._id) return;
    try {
      const res = await api.get(`/notification-center/${user._id}?limit=100`);
      if (res.data.success) setItems(res.data.notifications || []);
    } catch { /* silent */ }
  }, [user?._id]);

  useEffect(() => {
    if (!user?._id) return;
    setLoading(true);
    fetchAlerts().finally(() => setLoading(false));
  }, [user?._id, fetchAlerts]);

  const onRefresh = async () => {
    setRefreshing(true);
    await fetchAlerts();
    setRefreshing(false);
  };

  const showUndo = (ids: string[], removed: AlertItem[], label: string) => {
    if (undoTimer.current) clearTimeout(undoTimer.current);
    setUndo({ ids, items: removed, label });
    undoTimer.current = setTimeout(() => setUndo(null), 6000);
  };

  const handleUndo = async () => {
    if (!undo || !user?._id) return;
    if (undoTimer.current) clearTimeout(undoTimer.current);
    const { ids, items: restored } = undo;
    setUndo(null);
    setItems(prev => {
      const have = new Set(prev.map(i => i.id));
      return [...prev, ...restored.filter(i => !have.has(i.id))];
    });
    try { await api.post(`/notification-center/${user._id}/undismiss`, { ids }); } catch { /* silent */ }
    fetchAlerts();
  };

  const open = async (n: AlertItem) => {
    if (user?._id && !n.read) {
      setItems(prev => prev.map(i => i.id === n.id ? { ...i, read: true } : i));
      api.post(`/notification-center/${user._id}/read`, { ids: [n.id] }).catch(() => {});
    }
    // Website demo-form leads: claim on tap, then land on the contact with the intro prefilled
    if (n.type === 'new_lead' && n.demo_request_id && user?._id) {
      try {
        const res = await api.post(`/demo-requests/${n.demo_request_id}/claim`, { user_id: user._id });
        if (res.data?.contact_id) {
          router.push({ pathname: `/contact/${res.data.contact_id}`, params: { prefill: res.data.prefill_message || '' } } as any);
          return;
        }
      } catch { /* fall through to the link */ }
    }
    const link = n.action?.link || n.link || (n.contact_id ? `/contact/${n.contact_id}` : null);
    if (link) router.push(link as any);
  };

  const dismiss = async (n: AlertItem) => {
    if (!user?._id) return;
    setItems(prev => prev.filter(i => i.id !== n.id));
    showUndo([n.id], [n], `Dismissed · ${n.title}`);
    try { await api.post(`/notification-center/${user._id}/dismiss`, { ids: [n.id] }); } catch { /* silent */ }
  };

  const clearAll = () => {
    if (!user?._id || items.length === 0) return;
    const count = items.length;
    showConfirm('Clear all alerts?', `${count} alert${count === 1 ? '' : 's'} will be cleared. Tasks and threads stay where they are.`, async () => {
      const snapshot = items;
      setItems([]);
      try {
        const res = await api.post(`/notification-center/${user._id}/clear-all`);
        showUndo(res.data.ids || snapshot.map(i => i.id), snapshot, `${count} alert${count === 1 ? '' : 's'} cleared`);
      } catch { setItems(snapshot); }
    }, undefined, 'Clear all');
  };

  const unread = items.filter(i => !i.read).length;
  const subtitle = items.length === 0
    ? 'All clear'
    : unread > 0
      ? `${unread} thing${unread === 1 ? '' : 's'} need${unread === 1 ? 's' : ''} you`
      : `${items.length} open`;

  return (
    <SafeAreaView style={styles.container} {...tid('notifications-page')}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backBtn} {...tid('notif-back-btn')}>
          <Ionicons name="chevron-back" size={24} color={GOLD} />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text maxFontSizeMultiplier={1} style={styles.headerTitle}>Alerts</Text>
          <Text maxFontSizeMultiplier={1} style={styles.headerSub} {...tid('alerts-subtitle')}>{subtitle}</Text>
        </View>
        {items.length > 0 && (
          <TouchableOpacity onPress={clearAll} style={styles.clearBtn} {...tid('alerts-clear-all')}>
            <Ionicons name="checkmark-done" size={15} color="#000" />
            <Text maxFontSizeMultiplier={1} style={styles.clearText}>Clear all</Text>
          </TouchableOpacity>
        )}
      </View>

      {loading ? (
        <View style={styles.loadingContainer}><ActivityIndicator size="large" color={GOLD} /></View>
      ) : (
        <ScrollView
          style={{ flex: 1 }}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={GOLD} />}
        >
          {items.length === 0 ? (
            <View style={styles.emptyContainer} {...tid('notif-empty')}>
              <View style={styles.emptyIcon}><Ionicons name="checkmark-circle" size={44} color={GOLD} /></View>
              <Text maxFontSizeMultiplier={1} style={styles.emptyTitle}>All clear</Text>
              <Text maxFontSizeMultiplier={1} style={styles.emptySubtitle}>Nothing needs you right now.</Text>
            </View>
          ) : (
            BUCKETS.map(b => {
              const group = items.filter(i => i.bucket === b.key);
              if (group.length === 0) return null;
              return (
                <View key={b.key} {...tid(`alerts-bucket-${b.key}`)}>
                  <View style={styles.bucketRow}>
                    <View style={[styles.bucketDot, { backgroundColor: b.color }]} />
                    <Text maxFontSizeMultiplier={1} style={[styles.bucketLabel, { color: b.color }]}>{b.label}</Text>
                    <Text maxFontSizeMultiplier={1} style={styles.bucketCount}>{group.length}</Text>
                  </View>
                  {group.map(n => <AlertRow key={n.id} item={n} onOpen={open} onDismiss={dismiss} />)}
                </View>
              );
            })
          )}
          {items.length > 0 && (
            <Text maxFontSizeMultiplier={1} style={styles.hint}>Swipe left to dismiss · Tap to jump in</Text>
          )}
          <View style={{ height: 80 }} />
        </ScrollView>
      )}

      {undo && (
        <View style={styles.undoBar} {...tid('alerts-undo-bar')}>
          <Ionicons name="close-circle" size={20} color={GOLD} />
          <Text maxFontSizeMultiplier={1} style={styles.undoText} numberOfLines={1}>{undo.label}</Text>
          <TouchableOpacity onPress={handleUndo} style={styles.undoBtn} {...tid('alerts-undo-btn')}>
            <Text maxFontSizeMultiplier={1} style={styles.undoBtnText}>UNDO</Text>
          </TouchableOpacity>
        </View>
      )}
    </SafeAreaView>
  );
}

const getStyles = (colors: any) => StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  header: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 12, gap: 12 },
  backBtn: { width: 36, height: 36, borderRadius: 12, backgroundColor: colors.card, alignItems: 'center', justifyContent: 'center' },
  headerTitle: { fontSize: 22, fontWeight: '800', color: colors.text },
  headerSub: { fontSize: 13, color: colors.textSecondary, marginTop: 1 },
  clearBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 12, paddingVertical: 7, borderRadius: 16, backgroundColor: GOLD },
  clearText: { fontSize: 13, color: '#000', fontWeight: '700' },
  loadingContainer: { flex: 1, justifyContent: 'center', alignItems: 'center', paddingTop: 80 },
  emptyContainer: { alignItems: 'center', paddingTop: 90, gap: 8 },
  emptyIcon: { width: 72, height: 72, borderRadius: 36, backgroundColor: GOLD + '15', alignItems: 'center', justifyContent: 'center', marginBottom: 8 },
  emptyTitle: { fontSize: 18, fontWeight: '700', color: colors.text },
  emptySubtitle: { fontSize: 14, color: colors.textSecondary, textAlign: 'center' },
  bucketRow: { flexDirection: 'row', alignItems: 'center', gap: 7, paddingHorizontal: 20, marginTop: 16, marginBottom: 8 },
  bucketDot: { width: 7, height: 7, borderRadius: 4 },
  bucketLabel: { fontSize: 12, fontWeight: '800', letterSpacing: 1 },
  bucketCount: { fontSize: 12, fontWeight: '700', color: colors.textTertiary },
  hint: { textAlign: 'center', fontSize: 12, color: colors.textTertiary, marginTop: 14 },
  undoBar: {
    position: 'absolute', left: 16, right: 16, bottom: 28,
    backgroundColor: '#1C1C1E', borderRadius: 14, borderWidth: 1, borderColor: 'rgba(255,255,255,0.14)',
    flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 14,
    shadowColor: '#000', shadowOffset: { width: 0, height: 4 }, shadowOpacity: 0.45, shadowRadius: 12, elevation: 10,
  },
  undoText: { flex: 1, marginLeft: 10, color: '#FFF', fontSize: 14, fontWeight: '600' },
  undoBtn: { paddingHorizontal: 14, paddingVertical: 7, borderRadius: 9, backgroundColor: 'rgba(201,169,98,0.18)' },
  undoBtnText: { color: GOLD, fontSize: 14, fontWeight: '800', letterSpacing: 0.5 },
});
