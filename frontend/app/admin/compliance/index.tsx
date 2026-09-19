/**
 * Texting compliance overview: every US store's A2P 10DLC + Caller ID registration at a glance, plus the mode switch
 * (Dry run → Twilio mock → Live). Tap a store to fill in its business details and submit.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, ScrollView, ActivityIndicator, RefreshControl, TextInput } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useThemeStore } from '../../../store/themeStore';
import { useAuthStore } from '../../../store/authStore';
import { ScreenHeader } from '../../../components/common/ScreenHeader';
import api from '../../../services/api';
import { showSimpleAlert } from '../../../services/alert';

const GOLD = '#C9A962';
export const STAGE_COLOR: Record<string, string> = { draft: '#8E8E93', profile: '#FF9500', a2p: '#FF9500', brand: '#FF9500', campaign: '#FF9500', complete: '#34C759' };
export const STATUS_COLOR: Record<string, string> = { not_started: '#8E8E93', submitting: '#FF9500', pending: '#FF9500', approved: '#34C759', rejected: '#FF3B30', error: '#FF3B30' };
const MODES: { key: string; label: string; blurb: string }[] = [
  { key: 'dry_run', label: 'Dry run', blurb: 'No Twilio calls. Fake approvals so you can walk the whole flow.' },
  { key: 'mock', label: 'Twilio mock', blurb: 'Real business profiles in Twilio, mock brand and campaign: no TCR fees, cannot send.' },
  { key: 'live', label: 'Live', blurb: 'Real registration. Brand fees apply; approvals take 1 to 5 business days.' },
];

export function StagePill({ stage, label, status }: { stage: string; label: string; status: string }) {
  const bad = status === 'rejected' || status === 'error';
  const color = bad ? '#FF3B30' : STAGE_COLOR[stage] || '#8E8E93';
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 5, paddingHorizontal: 9, height: 24, borderRadius: 12, backgroundColor: `${color}20` }}>
      <View style={{ width: 7, height: 7, borderRadius: 4, backgroundColor: color }} />
      <Text style={{ fontSize: 12, fontWeight: '700', color }}>{bad ? (status === 'error' ? 'Error' : 'Rejected') : stage === 'draft' ? 'Not started' : stage === 'complete' ? 'Approved' : `${label} · ${status}`}</Text>
    </View>
  );
}

export default function ComplianceOverview() {
  const { colors } = useThemeStore();
  const user = useAuthStore((st) => st.user);
  const router = useRouter();
  const s = getS(colors);
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [savingMode, setSavingMode] = useState(false);
  const [email, setEmail] = useState('');
  const isSuper = user?.role === 'super_admin';

  const load = useCallback(async () => {
    try {
      const r = await api.get('/admin/compliance');
      setData(r.data);
      setEmail(r.data?.settings?.notify_email || '');
    } catch { showSimpleAlert('Error', 'Could not load compliance data.'); }
    finally { setLoading(false); setRefreshing(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const setMode = async (mode: string) => {
    if (!isSuper || savingMode) return;
    setSavingMode(true);
    try {
      const r = await api.put('/admin/compliance/settings', { mode, notify_email: email });
      setData((d: any) => ({ ...d, settings: r.data }));
    } catch (e: any) { showSimpleAlert('Error', e?.response?.data?.detail || 'Could not change the mode.'); }
    finally { setSavingMode(false); }
  };

  if (loading) {
    return (
      <SafeAreaView style={s.container} edges={['top']}>
        <ScreenHeader title="Texting Compliance" testID="compliance-header" />
        <ActivityIndicator size="large" color={GOLD} style={{ marginTop: 80 }} />
      </SafeAreaView>
    );
  }
  const stores: any[] = data?.stores || [];
  const done = stores.filter(x => x.stage === 'complete').length;
  const inFlight = stores.filter(x => !['draft', 'complete'].includes(x.stage) && !['rejected', 'error'].includes(x.status)).length;
  const bad = stores.filter(x => ['rejected', 'error'].includes(x.status)).length;
  const mode = data?.settings?.mode || 'dry_run';

  return (
    <SafeAreaView style={s.container} edges={['top']}>
      <ScreenHeader title="Texting Compliance" subtitle="A2P 10DLC + Caller ID per store" testID="compliance-header" />
      <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 60 }} refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} tintColor={GOLD} />}>
        <View style={s.statsRow}>
          <Stat label="Approved" value={done} color="#34C759" colors={colors} testid="compliance-stat-approved" />
          <Stat label="In review" value={inFlight} color="#FF9500" colors={colors} testid="compliance-stat-review" />
          <Stat label="Needs fix" value={bad} color="#FF3B30" colors={colors} testid="compliance-stat-bad" />
          <Stat label="Not started" value={stores.length - done - inFlight - bad} color="#8E8E93" colors={colors} testid="compliance-stat-draft" />
        </View>

        <View style={s.card} testID="compliance-mode-card">
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 10 }}>
            <Ionicons name="shield-checkmark" size={18} color={GOLD} />
            <Text style={s.cardTitle}>Registration mode</Text>
            {!isSuper && <Text style={{ fontSize: 12, color: colors.textTertiary }}>super admin only</Text>}
          </View>
          <View style={{ flexDirection: 'row', gap: 8, marginBottom: 10 }}>
            {MODES.map(m => {
              const on = mode === m.key;
              return (
                <TouchableOpacity key={m.key} onPress={() => setMode(m.key)} disabled={!isSuper || savingMode} activeOpacity={0.8}
                  style={{ flex: 1, paddingVertical: 9, borderRadius: 10, alignItems: 'center', backgroundColor: on ? GOLD : colors.bg, borderWidth: 1, borderColor: on ? GOLD : colors.border, opacity: isSuper ? 1 : 0.6 }}
                  testID={`compliance-mode-${m.key}`} dataSet={{ testid: `compliance-mode-${m.key}` } as any}>
                  <Text style={{ fontSize: 13, fontWeight: '800', color: on ? '#000' : colors.text }}>{m.label}</Text>
                </TouchableOpacity>
              );
            })}
          </View>
          <Text style={{ fontSize: 13, color: colors.textSecondary, lineHeight: 18 }} testID="compliance-mode-blurb">{MODES.find(m => m.key === mode)?.blurb}</Text>
          {isSuper && (
            <View style={{ marginTop: 12 }}>
              <Text style={s.label}>Twilio notification email</Text>
              <View style={{ flexDirection: 'row', gap: 8 }}>
                <TextInput value={email} onChangeText={setEmail} placeholder="compliance@yourcompany.com" placeholderTextColor={colors.textTertiary} autoCapitalize="none" keyboardType="email-address"
                  style={[s.input, { flex: 1 }]} testID="compliance-notify-email" dataSet={{ testid: 'compliance-notify-email' } as any} />
                <TouchableOpacity onPress={() => setMode(mode)} style={s.smallBtn} testID="compliance-notify-save" dataSet={{ testid: 'compliance-notify-save' } as any}>
                  <Text style={{ fontSize: 13, fontWeight: '800', color: '#000' }}>Save</Text>
                </TouchableOpacity>
              </View>
            </View>
          )}
        </View>

        <Text style={s.sectionLabel}>STORES ({stores.length})</Text>
        {stores.length === 0 && <Text style={{ color: colors.textTertiary, fontSize: 14 }}>No US stores yet.</Text>}
        {stores.map(st => (
          <TouchableOpacity key={st.store_id} style={s.row} onPress={() => router.push(`/admin/compliance/${st.store_id}` as any)} activeOpacity={0.8}
            testID={`compliance-store-${st.store_id}`} dataSet={{ testid: `compliance-store-${st.store_id}` } as any}>
            <View style={{ flex: 1 }}>
              <Text style={s.rowTitle} numberOfLines={1}>{st.store_name}</Text>
              <Text style={s.rowSub} numberOfLines={1}>
                {st.numbers} number{st.numbers === 1 ? '' : 's'}{st.cnam_name ? ` · Caller ID ${st.cnam_name}${st.cnam ? ` (${String(st.cnam).replace('twilio-', '')})` : ''}` : ''}{st.error ? ` · ${st.error}` : ''}
              </Text>
            </View>
            <StagePill stage={st.stage} label={st.stage_label} status={st.status} />
            <Ionicons name="chevron-forward" size={16} color={colors.textTertiary} />
          </TouchableOpacity>
        ))}
      </ScrollView>
    </SafeAreaView>
  );
}

function Stat({ label, value, color, colors, testid }: any) {
  return (
    <View style={{ flex: 1, backgroundColor: colors.card, borderRadius: 12, padding: 10, alignItems: 'center' }} testID={testid}>
      <Text style={{ fontSize: 20, fontWeight: '800', color }}>{value}</Text>
      <Text style={{ fontSize: 11, color: colors.textSecondary, marginTop: 2 }}>{label}</Text>
    </View>
  );
}

const getS = (colors: any) => StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  statsRow: { flexDirection: 'row', gap: 8, marginBottom: 14 },
  card: { backgroundColor: colors.card, borderRadius: 14, padding: 14, marginBottom: 16 },
  cardTitle: { flex: 1, fontSize: 16, fontWeight: '700', color: colors.text },
  label: { fontSize: 11, fontWeight: '800', letterSpacing: 0.6, color: colors.textSecondary, marginBottom: 6, textTransform: 'uppercase' },
  input: { backgroundColor: colors.bg, borderRadius: 10, borderWidth: 1, borderColor: colors.border, paddingHorizontal: 12, paddingVertical: 10, fontSize: 15, color: colors.text },
  smallBtn: { backgroundColor: GOLD, borderRadius: 10, paddingHorizontal: 14, justifyContent: 'center' },
  sectionLabel: { fontSize: 12, fontWeight: '800', letterSpacing: 0.8, color: colors.textSecondary, marginBottom: 8 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: colors.card, borderRadius: 12, padding: 12, marginBottom: 8 },
  rowTitle: { fontSize: 15, fontWeight: '700', color: colors.text },
  rowSub: { fontSize: 12, color: colors.textSecondary, marginTop: 2 },
});
