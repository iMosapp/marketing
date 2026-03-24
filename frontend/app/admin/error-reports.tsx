import React, { useState, useCallback } from 'react';
import {
  View, Text, TouchableOpacity, StyleSheet, ScrollView, ActivityIndicator, Platform, RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import { useThemeStore } from '../../store/themeStore';
import { useAuthStore } from '../../store/authStore';
import api from '../../services/api';
import { showSimpleAlert } from '../../services/alert';

const FILTERS = [
  { key: 'all', label: 'All' },
  { key: 'render_crash', label: 'Crashes' },
  { key: 'api_error', label: 'API Errors' },
  { key: 'js_error', label: 'JS Errors' },
  { key: 'unhandled_rejection', label: 'Promises' },
];

function formatTime(iso: string) {
  try {
    const d = new Date(iso);
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const diffMin = Math.floor(diffMs / 60000);
    if (diffMin < 1) return 'just now';
    if (diffMin < 60) return `${diffMin}m ago`;
    const diffHrs = Math.floor(diffMin / 60);
    if (diffHrs < 24) return `${diffHrs}h ago`;
    const diffDays = Math.floor(diffHrs / 24);
    return `${diffDays}d ago`;
  } catch {
    return iso;
  }
}

function typeColor(t: string) {
  switch (t) {
    case 'render_crash': return '#FF3B30';
    case 'api_error': return '#FF9500';
    case 'js_error': return '#FF2D55';
    case 'unhandled_rejection': return '#AF52DE';
    default: return '#8E8E93';
  }
}

function typeLabel(t: string) {
  switch (t) {
    case 'render_crash': return 'CRASH';
    case 'api_error': return 'API';
    case 'js_error': return 'JS';
    case 'unhandled_rejection': return 'PROMISE';
    default: return t.toUpperCase();
  }
}

export default function ErrorReportsPage() {
  const { colors } = useThemeStore();
  const { user } = useAuthStore();
  const router = useRouter();
  const [reports, setReports] = useState<any[]>([]);
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all');
  const [copied, setCopied] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const fetchReports = useCallback(async () => {
    try {
      let url = '/errors/recent?limit=100';
      if (filter !== 'all') url += `&error_type=${filter}`;
      const res = await api.get(url);
      setReports(res.data.reports || []);
      setCount(res.data.count || 0);
    } catch (e) {
      console.error('Failed to fetch error reports:', e);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [filter]);

  useFocusEffect(
    useCallback(() => {
      setLoading(true);
      fetchReports();
    }, [fetchReports])
  );

  const onRefresh = () => {
    setRefreshing(true);
    fetchReports();
  };

  const buildCopyText = () => {
    if (reports.length === 0) return 'No error reports found.';
    const lines = [`ERROR REPORTS (${count} total, filter: ${filter})\n${'='.repeat(50)}`];
    reports.forEach((r, i) => {
      lines.push(`\n--- #${i + 1} [${typeLabel(r.error_type)}] ${r.created_at} ---`);
      lines.push(`Page: ${r.page || 'unknown'}`);
      lines.push(`User: ${r.user_name || 'unknown'} (${r.user_email || r.user_id || '?'})`);
      lines.push(`Platform: ${r.platform || '?'}`);
      lines.push(`Error: ${r.error_message}`);
      if (r.error_stack) lines.push(`Stack: ${r.error_stack.slice(0, 500)}`);
      if (r.component_stack) lines.push(`Component: ${r.component_stack.slice(0, 300)}`);
    });
    return lines.join('\n');
  };

  const handleCopy = async () => {
    const text = buildCopyText();
    try {
      if (Platform.OS === 'web') {
        if (navigator.clipboard) {
          await navigator.clipboard.writeText(text);
        } else {
          const ta = document.createElement('textarea');
          ta.value = text;
          ta.style.position = 'fixed';
          ta.style.opacity = '0';
          document.body.appendChild(ta);
          ta.select();
          document.execCommand('copy');
          document.body.removeChild(ta);
        }
      }
      setCopied(true);
      setTimeout(() => setCopied(false), 3000);
    } catch {
      showSimpleAlert('Copy Failed', 'Could not copy to clipboard. Try selecting the text manually.');
    }
  };

  const handleClear = () => {
    showSimpleAlert(
      'Clear All Reports?',
      'This will delete all error reports. This cannot be undone.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Clear All', style: 'destructive', onPress: async () => {
            try {
              await api.delete('/errors/clear');
              setReports([]);
              setCount(0);
            } catch {}
          }
        },
      ]
    );
  };

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: colors.bg }]}>
      {/* Header */}
      <View style={[styles.header, { borderBottomColor: colors.border }]}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backBtn} data-testid="error-reports-back">
          <Ionicons name="chevron-back" size={24} color={colors.text} />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={[styles.title, { color: colors.text }]}>Error Reports</Text>
          <Text style={[styles.subtitle, { color: colors.textSecondary }]}>
            {count} report{count !== 1 ? 's' : ''} captured
          </Text>
        </View>
        <TouchableOpacity onPress={handleClear} style={styles.clearBtn} data-testid="error-reports-clear">
          <Ionicons name="trash-outline" size={20} color="#FF3B30" />
        </TouchableOpacity>
      </View>

      {/* Copy Button — big and prominent */}
      <TouchableOpacity
        style={[styles.copyButton, copied && styles.copyButtonCopied]}
        onPress={handleCopy}
        activeOpacity={0.7}
        data-testid="error-reports-copy"
      >
        <Ionicons name={copied ? 'checkmark-circle' : 'copy-outline'} size={22} color="#FFF" />
        <Text style={styles.copyText}>{copied ? 'Copied!' : 'Copy All Reports'}</Text>
      </TouchableOpacity>

      {/* Filters */}
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.filterRow} contentContainerStyle={styles.filterContent}>
        {FILTERS.map(f => (
          <TouchableOpacity
            key={f.key}
            style={[styles.filterChip, filter === f.key && { backgroundColor: '#C9A962' }]}
            onPress={() => { setFilter(f.key); setLoading(true); }}
            data-testid={`error-filter-${f.key}`}
          >
            <Text style={[styles.filterText, filter === f.key && { color: '#000' }]}>{f.label}</Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      {/* Reports List */}
      {loading ? (
        <View style={styles.center}><ActivityIndicator size="large" color="#C9A962" /></View>
      ) : reports.length === 0 ? (
        <View style={styles.center}>
          <Ionicons name="shield-checkmark" size={48} color="#34C759" />
          <Text style={[styles.emptyTitle, { color: colors.text }]}>No errors</Text>
          <Text style={[styles.emptySubtitle, { color: colors.textSecondary }]}>Everything is running clean</Text>
        </View>
      ) : (
        <ScrollView
          style={styles.list}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#C9A962" />}
        >
          {reports.map((r, i) => (
            <View key={i} style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
              <View style={styles.cardHeader}>
                <View style={[styles.typeBadge, { backgroundColor: typeColor(r.error_type) + '20' }]}>
                  <Text style={[styles.typeText, { color: typeColor(r.error_type) }]}>{typeLabel(r.error_type)}</Text>
                </View>
                <Text style={[styles.time, { color: colors.textSecondary }]}>{formatTime(r.created_at)}</Text>
              </View>
              <Text style={[styles.errorMsg, { color: colors.text }]} numberOfLines={3}>{r.error_message}</Text>
              <View style={styles.meta}>
                <Text style={[styles.metaText, { color: colors.textSecondary }]}>
                  {r.page || '?'} {r.platform ? `(${r.platform})` : ''}
                </Text>
                <Text style={[styles.metaText, { color: colors.textSecondary }]}>
                  {r.user_name || r.user_email || r.user_id || 'unknown user'}
                </Text>
              </View>
              {r.error_stack ? (
                <View style={[styles.stackBox, { backgroundColor: colors.bg }]}>
                  <Text style={styles.stackText} numberOfLines={4}>{r.error_stack}</Text>
                </View>
              ) : null}
            </View>
          ))}
          <View style={{ height: 40 }} />
        </ScrollView>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  header: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: 0.5 },
  backBtn: { marginRight: 12, padding: 4 },
  title: { fontSize: 20, fontWeight: '700' },
  subtitle: { fontSize: 13, marginTop: 2 },
  clearBtn: { padding: 8 },
  copyButton: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8,
    marginHorizontal: 16, marginTop: 12, paddingVertical: 14,
    backgroundColor: '#007AFF', borderRadius: 12,
  },
  copyButtonCopied: { backgroundColor: '#34C759' },
  copyText: { color: '#FFF', fontSize: 16, fontWeight: '700' },
  filterRow: { maxHeight: 44, marginTop: 12 },
  filterContent: { paddingHorizontal: 16, gap: 8 },
  filterChip: {
    paddingHorizontal: 14, paddingVertical: 6,
    borderRadius: 16, backgroundColor: '#2C2C2E', marginRight: 8,
  },
  filterText: { fontSize: 13, fontWeight: '600', color: '#FFF' },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 32 },
  emptyTitle: { fontSize: 18, fontWeight: '700', marginTop: 12 },
  emptySubtitle: { fontSize: 14, marginTop: 4 },
  list: { flex: 1, paddingHorizontal: 16, paddingTop: 12 },
  card: { borderRadius: 12, borderWidth: 0.5, padding: 14, marginBottom: 10 },
  cardHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 },
  typeBadge: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 6 },
  typeText: { fontSize: 11, fontWeight: '800', letterSpacing: 0.5 },
  time: { fontSize: 12 },
  errorMsg: { fontSize: 14, fontWeight: '600', lineHeight: 20, marginBottom: 8 },
  meta: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 6 },
  metaText: { fontSize: 12 },
  stackBox: { borderRadius: 8, padding: 10, marginTop: 4 },
  stackText: { fontSize: 11, fontFamily: 'monospace', color: '#FF6B6B', lineHeight: 16 },
});
