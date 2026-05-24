import React, { useState, useCallback } from 'react';
import {
  View, Text, TouchableOpacity, StyleSheet, FlatList,
  ActivityIndicator, RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import { useThemeStore } from '../../store/themeStore';
import { useAuthStore } from '../../store/authStore';
import api from '../../services/api';

const LEVEL_COLOR: Record<string, string> = {
  error:   '#FF3B30',
  warning: '#FF9500',
  info:    '#007AFF',
};
const LEVEL_BG: Record<string, string> = {
  error:   '#FF3B3020',
  warning: '#FF950020',
  info:    '#007AFF15',
};

function timeAgo(iso?: string) {
  if (!iso) return '';
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60)   return `${Math.round(diff)}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

export default function SystemLogsScreen() {
  const router  = useRouter();
  const colors  = useThemeStore(s => s.colors);
  const { user } = useAuthStore();
  const s = getST(colors);

  const [logs,       setLogs]       = useState<any[]>([]);
  const [counts,     setCounts]     = useState<any>({});
  const [categories, setCategories] = useState<string[]>([]);
  const [loading,    setLoading]    = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [levelFilter, setLevelFilter] = useState<'all' | 'error' | 'warning' | 'info'>('all');
  const [catFilter,   setCatFilter]   = useState('all');
  const [expanded,    setExpanded]    = useState<string | null>(null);

  const load = useCallback(async (silent = false) => {
    if (!user?._id) return;
    if (!silent) setLoading(true);
    try {
      const res = await api.get(`/admin/system-logs?level=${levelFilter}&category=${catFilter}&limit=200`, {
        headers: { 'X-User-ID': user._id },
      });
      setLogs(res.data.logs || []);
      setCounts(res.data.counts || {});
      setCategories(res.data.categories || []);
    } catch (e) {
      console.error('Failed to load logs:', e);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [user?._id, levelFilter, catFilter]);

  useFocusEffect(useCallback(() => { load(); }, [load]));

  const clearLogs = async () => {
    try {
      await api.delete('/admin/system-logs', { headers: { 'X-User-ID': user!._id } });
      setLogs([]);
      setCounts({});
    } catch {}
  };

  const renderLog = ({ item }: { item: any }) => {
    const isExpanded = expanded === item._id;
    const color = LEVEL_COLOR[item.level] || '#8E8E93';
    const bg    = LEVEL_BG[item.level]    || '#8E8E9315';
    return (
      <TouchableOpacity
        onPress={() => setExpanded(isExpanded ? null : item._id)}
        style={[s.logCard, { backgroundColor: colors.card, borderLeftColor: color }]}
        activeOpacity={0.8}
        data-testid={`log-${item._id}`}
      >
        {/* Header row */}
        <View style={s.logHeader}>
          <View style={[s.levelBadge, { backgroundColor: bg }]}>
            <Text style={[s.levelText, { color }]}>{(item.level || '').toUpperCase()}</Text>
          </View>
          <View style={[s.catBadge, { backgroundColor: colors.surface }]}>
            <Text style={[s.catText, { color: colors.textSecondary }]}>{item.category || '—'}</Text>
          </View>
          <Text style={[s.timeText, { color: colors.textTertiary }]}>{timeAgo(item.timestamp)}</Text>
          <Ionicons name={isExpanded ? 'chevron-up' : 'chevron-down'} size={14} color={colors.textSecondary} />
        </View>

        {/* Message */}
        <Text style={[s.logMsg, { color: colors.text }]} numberOfLines={isExpanded ? 0 : 2}>
          {item.message}
        </Text>

        {/* Expanded details */}
        {isExpanded && (
          <View style={[s.details, { backgroundColor: colors.surface, borderColor: colors.border }]}>
            {Object.entries(item)
              .filter(([k]) => !['_id', 'level', 'category', 'message', 'timestamp'].includes(k))
              .filter(([, v]) => v !== null && v !== undefined && v !== '')
              .map(([k, v]) => (
                <View key={k} style={s.detailRow}>
                  <Text style={[s.detailKey, { color: colors.textSecondary }]}>{k}</Text>
                  <Text style={[s.detailVal, { color: colors.text }]} selectable numberOfLines={4}>
                    {String(v)}
                  </Text>
                </View>
              ))}
          </View>
        )}
      </TouchableOpacity>
    );
  };

  return (
    <SafeAreaView style={[s.container, { backgroundColor: colors.bg }]} edges={['top']}>
      {/* Header */}
      <View style={[s.header, { borderBottomColor: colors.border }]}>
        <TouchableOpacity onPress={() => router.back()} style={s.backBtn}>
          <Ionicons name="arrow-back" size={22} color={colors.text} />
        </TouchableOpacity>
        <Text style={[s.title, { color: colors.text }]}>System Logs</Text>
        <TouchableOpacity onPress={clearLogs} style={s.clearBtn}>
          <Text style={{ fontSize: 13, color: '#FF3B30', fontWeight: '600' }}>Clear</Text>
        </TouchableOpacity>
      </View>

      {/* Count pills */}
      <View style={s.statsRow}>
        {(['all', 'error', 'warning', 'info'] as const).map(lvl => {
          const cnt = lvl === 'all' ? (counts.error || 0) + (counts.warning || 0) + (counts.info || 0) : (counts[lvl] || 0);
          const active = levelFilter === lvl;
          const col = lvl === 'all' ? '#C9A962' : LEVEL_COLOR[lvl];
          return (
            <TouchableOpacity
              key={lvl}
              onPress={() => { setLevelFilter(lvl); setTimeout(() => load(), 50); }}
              style={[s.pill, { backgroundColor: active ? col : colors.card, borderColor: col + '60' }]}
              data-testid={`log-filter-${lvl}`}
            >
              <Text style={{ fontSize: 12, fontWeight: '700', color: active ? '#fff' : col }}>
                {lvl === 'all' ? 'All' : lvl.charAt(0).toUpperCase() + lvl.slice(1)} {cnt > 0 ? `(${cnt})` : ''}
              </Text>
            </TouchableOpacity>
          );
        })}
      </View>

      {/* Category filter */}
      {categories.length > 0 && (
        <View style={s.catRow}>
          {['all', ...categories].map(cat => (
            <TouchableOpacity
              key={cat}
              onPress={() => { setCatFilter(cat); setTimeout(() => load(), 50); }}
              style={[s.catPill, { backgroundColor: catFilter === cat ? colors.accent + '30' : colors.surface, borderColor: catFilter === cat ? colors.accent : 'transparent' }]}
            >
              <Text style={{ fontSize: 11, color: catFilter === cat ? colors.accent : colors.textSecondary, fontWeight: '600' }}>
                {cat === 'all' ? 'All Categories' : cat}
              </Text>
            </TouchableOpacity>
          ))}
        </View>
      )}

      {loading ? (
        <View style={s.center}><ActivityIndicator size="large" color={colors.accent} /></View>
      ) : logs.length === 0 ? (
        <View style={s.center}>
          <Ionicons name="checkmark-circle" size={48} color="#34C759" />
          <Text style={[s.emptyText, { color: colors.text }]}>No logs — everything is clean</Text>
        </View>
      ) : (
        <FlatList
          data={logs}
          renderItem={renderLog}
          keyExtractor={i => i._id}
          contentContainerStyle={{ padding: 12, paddingBottom: 40 }}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(true); }} tintColor={colors.accent} />}
        />
      )}
    </SafeAreaView>
  );
}

const getST = (colors: any) => StyleSheet.create({
  container:  { flex: 1 },
  header:     { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: 1 },
  backBtn:    { width: 36, height: 36, borderRadius: 18, backgroundColor: colors.card, alignItems: 'center', justifyContent: 'center' },
  title:      { fontSize: 18, fontWeight: '700' },
  clearBtn:   { paddingHorizontal: 12, paddingVertical: 6 },
  statsRow:   { flexDirection: 'row', gap: 8, padding: 12, paddingBottom: 4 },
  pill:       { borderRadius: 20, paddingHorizontal: 12, paddingVertical: 6, borderWidth: 1 },
  catRow:     { flexDirection: 'row', flexWrap: 'wrap', gap: 6, paddingHorizontal: 12, paddingBottom: 8 },
  catPill:    { borderRadius: 10, paddingHorizontal: 10, paddingVertical: 4, borderWidth: 1 },
  center:     { flex: 1, alignItems: 'center', justifyContent: 'center', paddingTop: 60 },
  emptyText:  { fontSize: 16, fontWeight: '600', marginTop: 12 },
  logCard:    { borderRadius: 12, padding: 12, marginBottom: 8, borderLeftWidth: 4 },
  logHeader:  { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 6 },
  levelBadge: { borderRadius: 6, paddingHorizontal: 7, paddingVertical: 3 },
  levelText:  { fontSize: 10, fontWeight: '800', letterSpacing: 0.5 },
  catBadge:   { borderRadius: 6, paddingHorizontal: 7, paddingVertical: 3 },
  catText:    { fontSize: 10, fontWeight: '600' },
  timeText:   { fontSize: 11, flex: 1, textAlign: 'right' },
  logMsg:     { fontSize: 13, lineHeight: 18 },
  details:    { marginTop: 10, borderRadius: 8, padding: 10, borderWidth: 1 },
  detailRow:  { flexDirection: 'row', gap: 8, marginBottom: 6 },
  detailKey:  { fontSize: 11, fontWeight: '700', width: 100, flexShrink: 0 },
  detailVal:  { fontSize: 11, flex: 1, lineHeight: 16 },
});
