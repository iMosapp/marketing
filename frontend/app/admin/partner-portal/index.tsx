import React, { useState, useCallback } from 'react';
import {
  View, Text, TouchableOpacity, StyleSheet, FlatList,
  ActivityIndicator, TextInput, RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import { useThemeStore } from '../../../store/themeStore';
import { useAuthStore } from '../../../store/authStore';
import { useToast } from '../../../components/common/Toast';
import api from '../../../services/api';

function timeAgo(iso?: string) {
  if (!iso) return '—';
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60)   return 'Just now';
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

const STATUS_COLOR: Record<string, string> = {
  accepted:    '#34C759',
  active:      '#007AFF',
  pending:     '#FF9500',
  deactivated: '#8E8E93',
  declined:    '#FF3B30',
};

const W9_COLOR: Record<string, string> = {
  submitted: '#34C759',
  pending:   '#FF9500',
  verified:  '#007AFF',
};

export default function PartnerPortal() {
  const router  = useRouter();
  const colors  = useThemeStore(s => s.colors);
  const { user } = useAuthStore();
  const { showToast } = useToast();
  const s = getStyles(colors);

  const [accounts, setAccounts]   = useState<any[]>([]);
  const [summary, setSummary]     = useState<any>({});
  const [loading, setLoading]     = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [search, setSearch]       = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');

  const partnerId = (user as any)?.partner_id || (user as any)?.organization_id;

  useFocusEffect(useCallback(() => {
    if (partnerId) load();
  }, [partnerId]));

  const load = async (silent = false) => {
    if (!partnerId) return;
    if (!silent) setLoading(true);
    try {
      const res = await api.get(`/subscriptions/partner/accounts?partner_id=${partnerId}&include_deactivated=true`);
      setAccounts(res.data.accounts || []);
      setSummary(res.data);
    } catch (e: any) {
      showToast(e?.response?.data?.detail || 'Failed to load accounts', 'error');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const filtered = accounts.filter(a => {
    const name = (a.customer?.name || a.business_info?.company_name || '').toLowerCase();
    const matchSearch = !search || name.includes(search.toLowerCase());
    const matchStatus = statusFilter === 'all' || a.status === statusFilter;
    return matchSearch && matchStatus;
  });

  const renderAccount = ({ item }: { item: any }) => {
    const name    = item.customer?.name || item.business_info?.company_name || 'Unknown';
    const email   = item.customer?.email || '';
    const plan    = item.plan_name || '';
    const price   = item.pricing?.final_price;
    const status  = item.status || 'pending';
    const w9      = item.w9_status || 'pending';
    const signedAt = item.accepted_at || item.created_at;

    return (
      <TouchableOpacity
        style={[s.card, { backgroundColor: colors.card }]}
        onPress={() => router.push({ pathname: '/admin/partner-portal/[id]', params: { id: item._id } } as any)}
        activeOpacity={0.8}
        data-testid={`account-${item._id}`}
      >
        {/* Name + status */}
        <View style={s.cardHeader}>
          <View style={{ flex: 1 }}>
            <Text style={[s.cardName, { color: colors.text }]} numberOfLines={1}>{name}</Text>
            {email ? <Text style={[s.cardSub, { color: colors.textSecondary }]} numberOfLines={1}>{email}</Text> : null}
          </View>
          <View style={[s.statusBadge, { backgroundColor: (STATUS_COLOR[status] || '#8E8E93') + '20' }]}>
            <Text style={[s.statusText, { color: STATUS_COLOR[status] || '#8E8E93' }]}>
              {status.toUpperCase()}
            </Text>
          </View>
        </View>

        {/* Plan + price */}
        <View style={s.cardMeta}>
          {plan ? (
            <View style={s.chip}>
              <Ionicons name="cube-outline" size={12} color={colors.textSecondary} />
              <Text style={[s.chipText, { color: colors.textSecondary }]}>{plan}</Text>
            </View>
          ) : null}
          {price !== undefined ? (
            <View style={s.chip}>
              <Ionicons name="cash-outline" size={12} color="#34C759" />
              <Text style={[s.chipText, { color: '#34C759' }]}>${price}/mo</Text>
            </View>
          ) : null}
          <View style={[s.chip, { backgroundColor: (W9_COLOR[w9] || '#FF9500') + '15' }]}>
            <Ionicons name={w9 === 'submitted' ? 'checkmark-circle' : 'document-text-outline'} size={12} color={W9_COLOR[w9] || '#FF9500'} />
            <Text style={[s.chipText, { color: W9_COLOR[w9] || '#FF9500' }]}>W-9 {w9}</Text>
          </View>
        </View>

        <Text style={[s.timestamp, { color: colors.textTertiary }]}>
          Signed {timeAgo(signedAt)} · Q-{item.quote_number || '—'}
        </Text>
      </TouchableOpacity>
    );
  };

  if (!partnerId) return (
    <SafeAreaView style={[s.container, { justifyContent: 'center', alignItems: 'center' }]}>
      <Ionicons name="alert-circle" size={48} color={colors.textSecondary} />
      <Text style={[s.emptyTitle, { color: colors.text }]}>Not linked to a partner account</Text>
    </SafeAreaView>
  );

  return (
    <SafeAreaView style={s.container} edges={['top']}>
      {/* Header */}
      <View style={s.header}>
        <TouchableOpacity onPress={() => router.back()} style={s.backBtn}>
          <Ionicons name="arrow-back" size={22} color={colors.text} />
        </TouchableOpacity>
        <Text style={s.headerTitle}>Partner Portal</Text>
        <TouchableOpacity
          style={s.createBtn}
          onPress={() => router.push('/admin/create-quote' as any)}
          data-testid="create-quote-btn"
        >
          <Ionicons name="add" size={18} color="#000" />
          <Text style={s.createBtnText}>New Quote</Text>
        </TouchableOpacity>
      </View>

      {/* Stats row */}
      {!loading && (
        <View style={s.statsRow}>
          <StatBox label="Total" value={summary.total || 0} color={colors.text} />
          <StatBox label="Active" value={summary.active || 0} color="#007AFF" />
          <StatBox label="Accepted" value={summary.accepted || 0} color="#34C759" />
          <StatBox label="W-9 Pending" value={summary.w9_pending || 0} color="#FF9500" />
        </View>
      )}

      {/* Search + filter */}
      <View style={s.filterRow}>
        <View style={[s.searchBox, { backgroundColor: colors.card, borderColor: colors.border }]}>
          <Ionicons name="search" size={16} color={colors.textSecondary} />
          <TextInput
            style={[s.searchInput, { color: colors.text }]}
            value={search}
            onChangeText={setSearch}
            placeholder="Search accounts..."
            placeholderTextColor={colors.textSecondary}
          />
        </View>
      </View>

      {/* Status filter tabs */}
      <View style={s.tabRow}>
        {(['all', 'accepted', 'active', 'pending', 'deactivated'] as const).map(t => (
          <TouchableOpacity
            key={t}
            onPress={() => setStatusFilter(t)}
            style={[s.tab, statusFilter === t && { borderBottomColor: STATUS_COLOR[t] || colors.accent, borderBottomWidth: 2 }]}
          >
            <Text style={[s.tabText, { color: statusFilter === t ? (STATUS_COLOR[t] || colors.accent) : colors.textSecondary }]}>
              {t.charAt(0).toUpperCase() + t.slice(1)}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {loading ? (
        <View style={s.center}><ActivityIndicator size="large" color={colors.accent} /></View>
      ) : (
        <FlatList
          data={filtered}
          renderItem={renderAccount}
          keyExtractor={i => i._id}
          contentContainerStyle={{ padding: 16, paddingBottom: 60 }}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(true); }} tintColor={colors.accent} />}
          ListEmptyComponent={() => (
            <View style={s.center}>
              <Ionicons name="business-outline" size={48} color={colors.textSecondary} />
              <Text style={[s.emptyTitle, { color: colors.text }]}>No accounts yet</Text>
              <Text style={[s.emptySub, { color: colors.textSecondary }]}>Create a quote to onboard your first client.</Text>
              <TouchableOpacity style={[s.createBtn, { marginTop: 20, paddingHorizontal: 24 }]} onPress={() => router.push('/admin/create-quote' as any)}>
                <Ionicons name="add" size={16} color="#000" />
                <Text style={s.createBtnText}>Create First Quote</Text>
              </TouchableOpacity>
            </View>
          )}
        />
      )}
    </SafeAreaView>
  );
}

function StatBox({ label, value, color }: any) {
  const colors = useThemeStore(s => s.colors);
  return (
    <View style={{ flex: 1, alignItems: 'center', backgroundColor: colors.card, borderRadius: 10, padding: 10, marginHorizontal: 3 }}>
      <Text style={{ fontSize: 22, fontWeight: '800', color }}>{value}</Text>
      <Text style={{ fontSize: 10, color: colors.textSecondary, marginTop: 2, textAlign: 'center' }}>{label}</Text>
    </View>
  );
}

const getStyles = (colors: any) => StyleSheet.create({
  container:    { flex: 1, backgroundColor: colors.bg },
  center:       { flex: 1, alignItems: 'center', justifyContent: 'center', paddingTop: 60 },
  header:       { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: colors.border },
  backBtn:      { width: 36, height: 36, borderRadius: 18, backgroundColor: colors.card, alignItems: 'center', justifyContent: 'center' },
  headerTitle:  { fontSize: 18, fontWeight: '700', color: colors.text },
  createBtn:    { flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: colors.accent, borderRadius: 20, paddingHorizontal: 14, paddingVertical: 8 },
  createBtnText:{ fontSize: 14, fontWeight: '700', color: '#000' },
  statsRow:     { flexDirection: 'row', padding: 12, gap: 4 },
  filterRow:    { paddingHorizontal: 16, paddingBottom: 8 },
  searchBox:    { flexDirection: 'row', alignItems: 'center', gap: 8, borderRadius: 12, paddingHorizontal: 12, paddingVertical: 10, borderWidth: 1 },
  searchInput:  { flex: 1, fontSize: 15 },
  tabRow:       { flexDirection: 'row', paddingHorizontal: 16, borderBottomWidth: 1, borderBottomColor: colors.border, marginBottom: 4 },
  tab:          { paddingVertical: 10, paddingHorizontal: 10, borderBottomWidth: 2, borderBottomColor: 'transparent' },
  tabText:      { fontSize: 12, fontWeight: '600' },
  card:         { borderRadius: 16, padding: 14, marginBottom: 10 },
  cardHeader:   { flexDirection: 'row', alignItems: 'flex-start', marginBottom: 10 },
  cardName:     { fontSize: 16, fontWeight: '700' },
  cardSub:      { fontSize: 12, marginTop: 2 },
  statusBadge:  { borderRadius: 8, paddingHorizontal: 8, paddingVertical: 4 },
  statusText:   { fontSize: 10, fontWeight: '800' },
  cardMeta:     { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginBottom: 8 },
  chip:         { flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: colors.surface, borderRadius: 8, paddingHorizontal: 8, paddingVertical: 4 },
  chipText:     { fontSize: 11, fontWeight: '600' },
  timestamp:    { fontSize: 11 },
  emptyTitle:   { fontSize: 18, fontWeight: '600', marginTop: 12 },
  emptySub:     { fontSize: 13, marginTop: 6, textAlign: 'center' },
});

