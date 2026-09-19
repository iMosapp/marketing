/**
 * Texting compliance overview: every US store's A2P 10DLC + Caller ID registration and where its client onboarding form sits,
 * plus the team settings (mode, notification emails, auto-send at signup, reminder days, daily digest, port-out details).
 */
import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, ScrollView, ActivityIndicator, RefreshControl, TextInput, Switch } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useThemeStore } from '../../../store/themeStore';
import { useAuthStore } from '../../../store/authStore';
import { ScreenHeader } from '../../../components/common/ScreenHeader';
import api from '../../../services/api';
import { showSimpleAlert } from '../../../services/alert';
import { OnboardingPill } from '../../../components/compliance/OnboardingCard';

const GOLD = '#C9A962';
export const STAGE_COLOR: Record<string, string> = { draft: '#8E8E93', profile: '#FF9500', a2p: '#FF9500', brand: '#FF9500', campaign: '#FF9500', complete: '#34C759' };
const MODES: { key: string; label: string; blurb: string }[] = [
  { key: 'dry_run', label: 'Dry run', blurb: 'No Twilio calls. Fake approvals so you can walk the whole flow.' },
  { key: 'mock', label: 'Twilio mock', blurb: 'Real business profiles in Twilio, mock brand and campaign: no TCR fees, cannot send.' },
  { key: 'live', label: 'Live', blurb: 'Real registration. Brand fees apply; approvals take 1 to 5 business days.' },
];
const FILTERS = [['all', 'All'], ['client', 'Waiting on client'], ['team', 'Needs the team'], ['twilio', 'In Twilio review'], ['bad', 'Needs fix'], ['done', 'Approved']];

export function StagePill({ stage, label, status }: { stage: string; label: string; status: string }) {
  const bad = status === 'rejected' || status === 'error';
  const color = bad ? '#FF3B30' : STAGE_COLOR[stage] || '#8E8E93';
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 5, paddingHorizontal: 9, height: 24, borderRadius: 12, backgroundColor: `${color}20` }}>
      <View style={{ width: 7, height: 7, borderRadius: 4, backgroundColor: color }} />
      <Text style={{ fontSize: 12, fontWeight: '700', color }}>{bad ? (status === 'error' ? 'Error' : 'Rejected') : stage === 'draft' ? 'Not submitted' : stage === 'complete' ? 'Approved' : `${label} · ${status}`}</Text>
    </View>
  );
}

const bucket = (st: any) => {
  if (st.stage === 'complete') return 'done';
  if (['rejected', 'error'].includes(st.status)) return 'bad';
  if (st.stage !== 'draft') return 'twilio';
  if (['not_sent', 'returned', 'reviewed'].includes(st.onboarding) || (st.onboarding === 'returned_incomplete' && !st.missing)) return 'team';
  return 'client';
};

export default function ComplianceOverview() {
  const { colors } = useThemeStore();
  const user = useAuthStore((st) => st.user);
  const router = useRouter();
  const s = getS(colors);
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState<any>({});
  const [showSettings, setShowSettings] = useState(false);
  const [filter, setFilter] = useState('all');
  const isSuper = user?.role === 'super_admin';

  const load = useCallback(async () => {
    try {
      const r = await api.get('/admin/compliance');
      setData(r.data);
      const st = r.data?.settings || {};
      setForm({ notify_email: st.notify_email || '', reminder_days: (st.reminder_days || []).join(', '), portout_pin: st.portout_pin || '', portout_service_address: st.portout_service_address || '', digest_hour: String(st.digest_hour ?? 8) });
    } catch { showSimpleAlert('Error', 'Could not load compliance data.'); }
    finally { setLoading(false); setRefreshing(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const saveSettings = async (patch: any) => {
    if (!isSuper || saving) return;
    setSaving(true);
    try {
      const r = await api.put('/admin/compliance/settings', patch);
      setData((d: any) => ({ ...d, settings: r.data }));
    } catch (e: any) { showSimpleAlert('Error', e?.response?.data?.detail || 'Could not save settings.'); }
    finally { setSaving(false); }
  };
  const saveForm = () => saveSettings({
    notify_email: form.notify_email, portout_pin: form.portout_pin, portout_service_address: form.portout_service_address,
    reminder_days: String(form.reminder_days || '').split(/[,\s]+/).filter(Boolean), digest_hour: parseInt(form.digest_hour || '8', 10),
  });

  if (loading) {
    return (
      <SafeAreaView style={s.container} edges={['top']}>
        <ScreenHeader title="Texting Compliance" testID="compliance-header" />
        <ActivityIndicator size="large" color={GOLD} style={{ marginTop: 80 }} />
      </SafeAreaView>
    );
  }
  const stores: any[] = data?.stores || [];
  const counts: Record<string, number> = { all: stores.length };
  stores.forEach(st => { const b = bucket(st); counts[b] = (counts[b] || 0) + 1; });
  const shown = stores.filter(st => filter === 'all' || bucket(st) === filter);
  const st = data?.settings || {};
  const mode = st.mode || 'dry_run';

  return (
    <SafeAreaView style={s.container} edges={['top']}>
      <ScreenHeader title="Texting Compliance" subtitle="A2P 10DLC + Caller ID per store" testID="compliance-header" />
      <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 60 }} refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} tintColor={GOLD} />}>
        <View style={s.statsRow}>
          <Stat label="Approved" value={counts.done || 0} color="#34C759" colors={colors} testid="compliance-stat-approved" />
          <Stat label="In review" value={counts.twilio || 0} color="#FF9500" colors={colors} testid="compliance-stat-review" />
          <Stat label="Needs fix" value={counts.bad || 0} color="#FF3B30" colors={colors} testid="compliance-stat-bad" />
          <Stat label="On client" value={counts.client || 0} color="#FF9500" colors={colors} testid="compliance-stat-client" />
          <Stat label="On team" value={counts.team || 0} color={GOLD} colors={colors} testid="compliance-stat-team" />
        </View>

        <View style={s.card} testID="compliance-mode-card">
          <TouchableOpacity onPress={() => setShowSettings(v => !v)} style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }} testID="compliance-settings-toggle">
            <Ionicons name="shield-checkmark" size={18} color={GOLD} />
            <Text style={s.cardTitle}>Settings</Text>
            <Text style={{ fontSize: 12, color: colors.textTertiary }}>{MODES.find(m => m.key === mode)?.label} · auto-send {st.auto_invite === false ? 'off' : 'on'} · digest {st.digest === false ? 'off' : 'on'}</Text>
            <Ionicons name={showSettings ? 'chevron-up' : 'chevron-down'} size={16} color={colors.textSecondary} />
          </TouchableOpacity>
          {showSettings && (
            <View style={{ marginTop: 12 }}>
              <Text style={s.label}>Registration mode{!isSuper ? ' · super admin only' : ''}</Text>
              <View style={{ flexDirection: 'row', gap: 8, marginBottom: 8 }}>
                {MODES.map(m => {
                  const on = mode === m.key;
                  return (
                    <TouchableOpacity key={m.key} onPress={() => saveSettings({ mode: m.key })} disabled={!isSuper || saving} activeOpacity={0.8}
                      style={{ flex: 1, paddingVertical: 9, borderRadius: 10, alignItems: 'center', backgroundColor: on ? GOLD : colors.bg, borderWidth: 1, borderColor: on ? GOLD : colors.border, opacity: isSuper ? 1 : 0.6 }}
                      testID={`compliance-mode-${m.key}`} dataSet={{ testid: `compliance-mode-${m.key}` } as any}>
                      <Text style={{ fontSize: 13, fontWeight: '800', color: on ? '#000' : colors.text }}>{m.label}</Text>
                    </TouchableOpacity>
                  );
                })}
              </View>
              <Text style={{ fontSize: 13, color: colors.textSecondary, lineHeight: 18, marginBottom: 12 }} testID="compliance-mode-blurb">{MODES.find(m => m.key === mode)?.blurb}</Text>
              {isSuper && (
                <>
                  <Toggle label="Send the client form automatically when a store signs up" value={st.auto_invite !== false} onChange={(v: boolean) => saveSettings({ auto_invite: v })} colors={colors} testid="compliance-auto-invite" />
                  <Toggle label={`Daily digest at ${st.digest_hour ?? 8}:00 Mountain of every store not yet approved`} value={st.digest !== false} onChange={(v: boolean) => saveSettings({ digest: v })} colors={colors} testid="compliance-digest" />
                  <Text style={[s.label, { marginTop: 10 }]}>Team notification emails (comma separated)</Text>
                  <TextInput value={form.notify_email} onChangeText={v => setForm({ ...form, notify_email: v })} placeholder="onboarding@imonsocial.com, forest@imonsocial.com" placeholderTextColor={colors.textTertiary} autoCapitalize="none" keyboardType="email-address" style={s.input} testID="compliance-notify-email" dataSet={{ testid: 'compliance-notify-email' } as any} />
                  <View style={{ flexDirection: 'row', gap: 8, marginTop: 10 }}>
                    <View style={{ flex: 1 }}>
                      <Text style={s.label}>Client reminders (days after first send)</Text>
                      <TextInput value={form.reminder_days} onChangeText={v => setForm({ ...form, reminder_days: v })} placeholder="2, 5, 9" placeholderTextColor={colors.textTertiary} style={s.input} testID="compliance-reminder-days" dataSet={{ testid: 'compliance-reminder-days' } as any} />
                    </View>
                    <View style={{ width: 110 }}>
                      <Text style={s.label}>Digest hour</Text>
                      <TextInput value={form.digest_hour} onChangeText={v => setForm({ ...form, digest_hour: v })} placeholder="8" placeholderTextColor={colors.textTertiary} keyboardType="number-pad" style={s.input} testID="compliance-digest-hour" dataSet={{ testid: 'compliance-digest-hour' } as any} />
                    </View>
                  </View>
                  <Text style={[s.label, { marginTop: 10 }]}>Port-out PIN (from porting@twilio.com) and service address, shown on the client's port-out packet</Text>
                  <View style={{ flexDirection: 'row', gap: 8 }}>
                    <TextInput value={form.portout_pin} onChangeText={v => setForm({ ...form, portout_pin: v })} placeholder="PIN" placeholderTextColor={colors.textTertiary} style={[s.input, { width: 110 }]} testID="compliance-portout-pin" dataSet={{ testid: 'compliance-portout-pin' } as any} />
                    <TextInput value={form.portout_service_address} onChangeText={v => setForm({ ...form, portout_service_address: v })} placeholder="Service address Twilio porting gives you" placeholderTextColor={colors.textTertiary} style={[s.input, { flex: 1 }]} testID="compliance-portout-address" dataSet={{ testid: 'compliance-portout-address' } as any} />
                  </View>
                  <TouchableOpacity onPress={saveForm} disabled={saving} style={[s.smallBtn, { marginTop: 12, alignSelf: 'flex-start', paddingVertical: 10 }]} testID="compliance-notify-save" dataSet={{ testid: 'compliance-notify-save' } as any}>
                    {saving ? <ActivityIndicator color="#000" /> : <Text style={{ fontSize: 13, fontWeight: '800', color: '#000' }}>Save settings</Text>}
                  </TouchableOpacity>
                </>
              )}
            </View>
          )}
        </View>

        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginBottom: 10 }}>
          {FILTERS.map(([k, l]) => (
            <TouchableOpacity key={k} onPress={() => setFilter(k)} style={{ paddingHorizontal: 11, paddingVertical: 6, borderRadius: 14, backgroundColor: filter === k ? GOLD : colors.card, borderWidth: 1, borderColor: filter === k ? GOLD : colors.border }} testID={`compliance-filter-${k}`}>
              <Text style={{ fontSize: 12.5, fontWeight: '700', color: filter === k ? '#000' : colors.text }}>{l} {counts[k] || 0}</Text>
            </TouchableOpacity>
          ))}
        </View>
        {shown.length === 0 && <Text style={{ color: colors.textTertiary, fontSize: 14 }} testID="compliance-empty">Nothing here.</Text>}
        {shown.map(x => (
          <TouchableOpacity key={x.store_id} style={s.row} onPress={() => router.push(`/admin/compliance/${x.store_id}` as any)} activeOpacity={0.8}
            testID={`compliance-store-${x.store_id}`} dataSet={{ testid: `compliance-store-${x.store_id}` } as any}>
            <View style={{ flex: 1, gap: 4 }}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                <Text style={[s.rowTitle, { flex: 1 }]} numberOfLines={1}>{x.store_name}</Text>
                <StagePill stage={x.stage} label={x.stage_label} status={x.status} />
              </View>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                {x.stage === 'draft' && <OnboardingPill status={x.onboarding} label={x.onboarding_label} />}
                {x.preflight && <Text style={{ fontSize: 12, fontWeight: '700', color: x.preflight.verdict === 'likely' ? '#34C759' : x.preflight.verdict === 'reject' ? '#FF3B30' : '#FF9500' }}>Pre-flight {x.preflight.score}</Text>}
                <Text style={s.rowSub}>{x.numbers} number{x.numbers === 1 ? '' : 's'}{x.cnam_name ? ` · Caller ID ${x.cnam_name}` : ''}</Text>
              </View>
              <Text style={[s.rowSub, { color: colors.text }]} numberOfLines={2} testID={`compliance-next-${x.store_id}`}>{x.next_action}</Text>
            </View>
            <Ionicons name="chevron-forward" size={16} color={colors.textTertiary} />
          </TouchableOpacity>
        ))}
      </ScrollView>
    </SafeAreaView>
  );
}

function Toggle({ label, value, onChange, colors, testid }: any) {
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 6 }}>
      <Text style={{ flex: 1, fontSize: 13.5, color: colors.text }}>{label}</Text>
      <Switch value={value} onValueChange={onChange} trackColor={{ false: 'rgba(128,128,128,0.3)', true: '#34C75966' }} thumbColor={value ? '#34C759' : '#f4f3f4'} testID={testid} dataSet={{ testid } as any} />
    </View>
  );
}

function Stat({ label, value, color, colors, testid }: any) {
  return (
    <View style={{ flex: 1, backgroundColor: colors.card, borderRadius: 12, padding: 10, alignItems: 'center' }} testID={testid}>
      <Text style={{ fontSize: 20, fontWeight: '800', color }}>{value}</Text>
      <Text style={{ fontSize: 10.5, color: colors.textSecondary, marginTop: 2 }}>{label}</Text>
    </View>
  );
}

const getS = (colors: any) => StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  statsRow: { flexDirection: 'row', gap: 6, marginBottom: 14 },
  card: { backgroundColor: colors.card, borderRadius: 14, padding: 14, marginBottom: 16 },
  cardTitle: { flex: 1, fontSize: 16, fontWeight: '700', color: colors.text },
  label: { fontSize: 11, fontWeight: '800', letterSpacing: 0.6, color: colors.textSecondary, marginBottom: 6, textTransform: 'uppercase' },
  input: { backgroundColor: colors.bg, borderRadius: 10, borderWidth: 1, borderColor: colors.border, paddingHorizontal: 12, paddingVertical: 10, fontSize: 15, color: colors.text },
  smallBtn: { backgroundColor: GOLD, borderRadius: 10, paddingHorizontal: 14, justifyContent: 'center' },
  row: { flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: colors.card, borderRadius: 12, padding: 12, marginBottom: 8 },
  rowTitle: { fontSize: 15, fontWeight: '700', color: colors.text },
  rowSub: { fontSize: 12, color: colors.textSecondary },
});
