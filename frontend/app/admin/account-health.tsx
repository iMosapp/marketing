import React, { useState, useEffect } from 'react';
import {
  View, Text, TouchableOpacity, StyleSheet, ScrollView, ActivityIndicator, TextInput,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useThemeStore } from '../../store/themeStore';
import api from '../../services/api';

type HealthGrade = { score: number; grade: string; color: string };
type Account = {
  user_id: string; name: string; email: string; role: string;
  organization: string; store: string; contacts: number;
  messages_30d: number; touchpoints_30d: number; active_campaigns: number;
  days_since_login: number; health: HealthGrade; last_login: string;
};

const FILTERS = ['All', 'Critical', 'At Risk', 'Healthy'] as const;

export default function AccountHealthDashboard() {
  const router = useRouter();
  const colors = useThemeStore((s) => s.colors);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<typeof FILTERS[number]>('All');
  const [search, setSearch] = useState('');
  const [period, setPeriod] = useState(30);

  useEffect(() => { load(); }, [period]);

  const load = async () => {
    setLoading(true);
    try {
      const res = await api.get(`/account-health/overview?period=${period}`);
      setAccounts(res.data || []);
    } catch (e) {
      console.error('Failed to load account health:', e);
    }
    setLoading(false);
  };

  const filtered = accounts.filter(a => {
    if (filter !== 'All' && a.health.grade !== filter) return false;
    if (search) {
      const q = search.toLowerCase();
      return a.name.toLowerCase().includes(q) || a.email.toLowerCase().includes(q) || a.organization.toLowerCase().includes(q);
    }
    return true;
  });

  const stats = {
    total: accounts.length,
    healthy: accounts.filter(a => a.health.grade === 'Healthy').length,
    atRisk: accounts.filter(a => a.health.grade === 'At Risk').length,
    critical: accounts.filter(a => a.health.grade === 'Critical').length,
  };

  return (
    <SafeAreaView style={[styles.safe, { backgroundColor: colors.bg }]}>
      <ScrollView style={styles.scroll} contentContainerStyle={styles.content}>
        {/* Header */}
        <View style={styles.header}>
          <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
            <Ionicons name="arrow-back" size={22} color={colors.text} />
          </TouchableOpacity>
          <View style={{ flex: 1 }}>
            <Text style={[styles.title, { color: colors.text }]}>Account Health</Text>
            <Text style={[styles.subtitle, { color: colors.textSecondary }]}>{stats.total} accounts tracked</Text>
          </View>
          {/* Period Toggle */}
          <View style={styles.periodRow}>
            {[30, 90].map(p => (
              <TouchableOpacity key={p} onPress={() => setPeriod(p)}
                style={[styles.periodBtn, period === p && { backgroundColor: '#007AFF', borderColor: '#007AFF' }, { borderColor: colors.surface, backgroundColor: colors.card }]}>
                <Text style={{ fontSize: 11, fontWeight: '600', color: period === p ? '#FFF' : colors.textSecondary }}>{p}d</Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>

        {/* Summary Cards */}
        <View style={styles.summaryRow}>
          {[
            { label: 'Healthy', value: stats.healthy, color: '#34C759', icon: 'checkmark-circle' },
            { label: 'At Risk', value: stats.atRisk, color: '#FF9500', icon: 'warning' },
            { label: 'Critical', value: stats.critical, color: '#FF3B30', icon: 'alert-circle' },
          ].map(s => (
            <TouchableOpacity key={s.label} onPress={() => setFilter(filter === s.label ? 'All' : s.label as any)}
              style={[styles.summaryCard, { backgroundColor: colors.card, borderColor: filter === s.label ? s.color : colors.surface }]}>
              <Ionicons name={s.icon as any} size={20} color={s.color} />
              <Text style={[styles.summaryValue, { color: s.color }]}>{s.value}</Text>
              <Text style={[styles.summaryLabel, { color: colors.textSecondary }]}>{s.label}</Text>
            </TouchableOpacity>
          ))}
        </View>

        {/* Search */}
        <View style={[styles.searchBox, { backgroundColor: colors.card, borderColor: colors.surface }]}>
          <Ionicons name="search" size={16} color={colors.textSecondary} />
          <TextInput
            style={[styles.searchInput, { color: colors.text }]}
            placeholder="Search by name, email, or org..."
            placeholderTextColor={colors.textSecondary}
            value={search}
            onChangeText={setSearch}
          />
          {search ? (
            <TouchableOpacity onPress={() => setSearch('')}>
              <Ionicons name="close-circle" size={16} color={colors.textSecondary} />
            </TouchableOpacity>
          ) : null}
        </View>

        {/* Filter Pills */}
        <View style={styles.filterRow}>
          {FILTERS.map(f => (
            <TouchableOpacity key={f} onPress={() => setFilter(f)}
              style={[styles.filterPill, { backgroundColor: filter === f ? '#007AFF' : colors.card, borderColor: filter === f ? '#007AFF' : colors.surface }]}>
              <Text style={{ fontSize: 12, fontWeight: '600', color: filter === f ? '#FFF' : colors.textSecondary }}>{f}</Text>
            </TouchableOpacity>
          ))}
        </View>

        {/* Account List */}
        {loading ? (
          <ActivityIndicator size="large" color="#007AFF" style={{ marginTop: 40 }} />
        ) : filtered.length === 0 ? (
          <View style={styles.emptyState}>
            <Ionicons name="pulse" size={40} color={colors.textSecondary} />
            <Text style={[styles.emptyText, { color: colors.textSecondary }]}>No accounts match your filters</Text>
          </View>
        ) : (
          filtered.map((a) => (
            <TouchableOpacity key={a.user_id}
              style={[styles.accountRow, { backgroundColor: colors.card, borderColor: colors.surface }]}
              onPress={() => router.push(`/admin/account-health/${a.user_id}` as any)}
            >
              {/* Health indicator */}
              <View style={[styles.healthDot, { backgroundColor: a.health.color }]}>
                <Text style={styles.healthScore}>{a.health.score}</Text>
              </View>

              {/* User info */}
              <View style={{ flex: 1 }}>
                <Text style={[styles.accountName, { color: colors.text }]}>{a.name}</Text>
                <Text style={[styles.accountMeta, { color: colors.textSecondary }]}>
                  {a.role} {a.organization ? `at ${a.organization}` : ''} {a.store ? `/ ${a.store}` : ''}
                </Text>
              </View>

              {/* Metrics */}
              <View style={styles.metricsRow}>
                <View style={styles.metricItem}>
                  <Text style={[styles.metricValue, { color: colors.text }]}>{a.contacts}</Text>
                  <Text style={[styles.metricLabel, { color: colors.textSecondary }]}>contacts</Text>
                </View>
                <View style={styles.metricItem}>
                  <Text style={[styles.metricValue, { color: colors.text }]}>{a.messages_30d}</Text>
                  <Text style={[styles.metricLabel, { color: colors.textSecondary }]}>msgs</Text>
                </View>
                <View style={styles.metricItem}>
                  <Text style={[styles.metricValue, { color: colors.text }]}>{a.touchpoints_30d}</Text>
                  <Text style={[styles.metricLabel, { color: colors.textSecondary }]}>touches</Text>
                </View>
              </View>

              {/* Login recency */}
              <View style={[styles.loginBadge, {
                backgroundColor: a.days_since_login <= 3 ? '#34C75915' : a.days_since_login <= 14 ? '#FF950015' : '#FF3B3015',
              }]}>
                <Text style={{
                  fontSize: 10, fontWeight: '600',
                  color: a.days_since_login <= 3 ? '#34C759' : a.days_since_login <= 14 ? '#FF9500' : '#FF3B30',
                }}>
                  {a.days_since_login <= 0 ? 'Today' : a.days_since_login >= 999 ? 'Never' : `${a.days_since_login}d ago`}
                </Text>
              </View>

              <Ionicons name="chevron-forward" size={16} color={colors.textSecondary} />
            </TouchableOpacity>
          ))
        )}

        <View style={{ height: 40 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  scroll: { flex: 1 },
  content: { padding: 16, maxWidth: 900, alignSelf: 'center' as any, width: '100%' },
  header: { flexDirection: 'row', alignItems: 'center', gap: 12, marginBottom: 16 },
  backBtn: { width: 36, height: 36, borderRadius: 18, alignItems: 'center', justifyContent: 'center' },
  title: { fontSize: 22, fontWeight: '700' },
  subtitle: { fontSize: 13, marginTop: 2 },
  periodRow: { flexDirection: 'row', gap: 6 },
  periodBtn: { paddingHorizontal: 10, paddingVertical: 5, borderRadius: 8, borderWidth: 1 },
  summaryRow: { flexDirection: 'row', gap: 10, marginBottom: 16 },
  summaryCard: { flex: 1, alignItems: 'center', padding: 14, borderRadius: 14, borderWidth: 1.5, gap: 4 },
  summaryValue: { fontSize: 22, fontWeight: '800' },
  summaryLabel: { fontSize: 11, fontWeight: '600' },
  searchBox: { flexDirection: 'row', alignItems: 'center', gap: 8, padding: 10, borderRadius: 10, borderWidth: 1, marginBottom: 10 },
  searchInput: { flex: 1, fontSize: 14 },
  filterRow: { flexDirection: 'row', gap: 6, marginBottom: 14 },
  filterPill: { paddingHorizontal: 14, paddingVertical: 6, borderRadius: 20, borderWidth: 1 },
  emptyState: { alignItems: 'center', paddingVertical: 40, gap: 10 },
  emptyText: { fontSize: 14 },
  accountRow: { flexDirection: 'row', alignItems: 'center', gap: 12, padding: 12, borderRadius: 12, borderWidth: 1, marginBottom: 6 },
  healthDot: { width: 38, height: 38, borderRadius: 19, alignItems: 'center', justifyContent: 'center' },
  healthScore: { color: '#FFF', fontSize: 12, fontWeight: '800' },
  accountName: { fontSize: 14, fontWeight: '600' },
  accountMeta: { fontSize: 11, marginTop: 2 },
  metricsRow: { flexDirection: 'row', gap: 12 },
  metricItem: { alignItems: 'center' },
  metricValue: { fontSize: 14, fontWeight: '700' },
  metricLabel: { fontSize: 9, marginTop: 1 },
  loginBadge: { paddingHorizontal: 8, paddingVertical: 4, borderRadius: 8 },
});
