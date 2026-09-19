/** Super admin: migration report of every number IMOS / Twilio knows about, mapped to organization / location / user, and the
 * one-tap "Import into registry" (registers rows, never moves or releases anything in Twilio). Also the global texting flags. */
import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, ScrollView, ActivityIndicator, Switch } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useThemeStore } from '../../store/themeStore';
import { ScreenHeader } from '../../components/common/ScreenHeader';
import api from '../../services/api';
import { showAlert, showSimpleAlert } from '../../services/alert';
import { GOLD, Pill, getS, prettyPhone, tid } from '../../components/org-twilio/shared';

const FILTERS = [{ key: 'all', label: 'All' }, { key: 'import', label: 'Importable' }, { key: 'review', label: 'Needs review' }, { key: 'already registered', label: 'Registered' }];

export default function TwilioMigration() {
  const { colors } = useThemeStore();
  const router = useRouter();
  const s = getS(colors);
  const [report, setReport] = useState<any>(null);
  const [flags, setFlags] = useState<any>(null);
  const [filter, setFilter] = useState('all');
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [r, f] = await Promise.all([api.get('/admin/twilio/migration-report'), api.get('/admin/twilio/flags')]);
      setReport(r.data);
      setFlags(f.data);
    } catch (e: any) { showSimpleAlert('Error', e?.response?.data?.detail || 'Could not build the report.'); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const importAll = () => showAlert('Import into the registry?', `${report.summary.importable} number${report.summary.importable === 1 ? '' : 's'} get a registry record with the mapping shown. Nothing is moved, changed or released in Twilio.`, [
    { text: 'Cancel', style: 'cancel' },
    { text: 'Import', onPress: async () => {
      setBusy('import');
      try { const r = await api.post('/admin/twilio/migration-report/import', {}); showSimpleAlert('Imported', `${r.data.count} registered${r.data.skipped?.length ? `, ${r.data.skipped.length} skipped` : ''}.`); await load(); }
      catch (e: any) { showSimpleAlert('Error', e?.response?.data?.detail || 'Import failed.'); }
      finally { setBusy(null); }
    } },
  ]);
  const importOne = async (phone: string) => {
    setBusy(phone);
    try { await api.post('/admin/twilio/migration-report/import', { phone_numbers: [phone] }); await load(); }
    catch (e: any) { showSimpleAlert('Error', e?.response?.data?.detail || 'Import failed.'); }
    finally { setBusy(null); }
  };
  const setFlag = async (key: string, v: boolean) => {
    try { const r = await api.put('/admin/twilio/flags', { [key]: v }); setFlags(r.data); }
    catch (e: any) { showSimpleAlert('Error', e?.response?.data?.detail || 'Could not save.'); }
  };

  if (!report) {
    return (
      <SafeAreaView style={s.container} edges={['top']}>
        <ScreenHeader title="Twilio migration" testID="twilio-migration-header" />
        <ActivityIndicator size="large" color={GOLD} style={{ marginTop: 80 }} />
      </SafeAreaView>
    );
  }
  const sm = report.summary || {};
  const rows: any[] = (report.rows || []).filter((r: any) => filter === 'all' || r.proposed_action === filter);
  const Stat = ({ label, value, testID }: any) => (
    <View style={{ flex: 1, minWidth: 100, backgroundColor: colors.card, borderRadius: 12, padding: 12 }} {...tid(testID)}>
      <Text style={{ fontSize: 22, fontWeight: '800', color: colors.text }}>{value ?? 0}</Text>
      <Text style={{ fontSize: 11, fontWeight: '700', color: colors.textTertiary, textTransform: 'uppercase', letterSpacing: 0.4 }}>{label}</Text>
    </View>
  );
  return (
    <SafeAreaView style={s.container} edges={['top']}>
      <ScreenHeader title="Twilio migration" subtitle={report.twilio_reachable ? 'Twilio account + IMOS records' : 'IMOS records only'} testID="twilio-migration-header" />
      <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 80 }} {...tid('twilio-migration-screen')}>
        <View style={{ flexDirection: 'row', gap: 8, flexWrap: 'wrap', marginBottom: 14 }}>
          <Stat label="Numbers" value={sm.total} testID="mig-total" />
          <Stat label="In Twilio" value={sm.in_twilio} testID="mig-in-twilio" />
          <Stat label="Registered" value={sm.in_registry} testID="mig-in-registry" />
          <Stat label="Importable" value={sm.importable} testID="mig-importable" />
          <Stat label="Needs review" value={sm.needs_review} testID="mig-review" />
          <Stat label="No org" value={sm.no_org} testID="mig-no-org" />
        </View>
        {!!report.note && <Text style={[s.hint, { marginBottom: 10 }]} {...tid('mig-note')}>{report.note}</Text>}
        <View style={{ flexDirection: 'row', gap: 8, marginBottom: 14 }}>
          <TouchableOpacity onPress={importAll} disabled={!!busy || !sm.importable} style={[s.btn, { backgroundColor: GOLD, opacity: sm.importable ? 1 : 0.4 }]} {...tid('mig-import-all-btn')}>
            {busy === 'import' ? <ActivityIndicator color="#000" /> : <><Ionicons name="download" size={16} color="#000" /><Text style={s.btnText}>Import {sm.importable || 0} into registry</Text></>}
          </TouchableOpacity>
          <TouchableOpacity onPress={load} style={[s.btn, { flex: 0, paddingHorizontal: 14, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border }]} {...tid('mig-refresh-btn')}>
            <Ionicons name="refresh" size={16} color={colors.text} />
          </TouchableOpacity>
        </View>
        <Text style={[s.hint, { marginBottom: 12 }]}>Read-only mapping first, then import. Existing production numbers are never moved or released by this screen; per-organization changes happen on Organizations → Communications.</Text>

        {flags && (
          <View style={s.card} {...tid('twilio-flags-card')}>
            <Text style={s.cardTitle}>Texting rules</Text>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
              <View style={{ flex: 1 }}>
                <Text style={{ fontSize: 14, fontWeight: '700', color: colors.text }}>Gate sends on MESSAGING READY</Text>
                <Text style={s.hint}>When on, a registry number only texts once its organization's campaign is approved and the number sits on the Messaging Service. Legacy numbers outside the registry are never blocked.</Text>
              </View>
              <Switch value={!!flags.enforce_ready} onValueChange={(v) => setFlag('enforce_ready', v)} trackColor={{ false: 'rgba(128,128,128,0.3)', true: '#34C75966' }} thumbColor={flags.enforce_ready ? '#34C759' : '#f4f3f4'} {...tid('flag-enforce-ready')} />
            </View>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, marginTop: 12, paddingTop: 10, borderTopWidth: 1, borderTopColor: colors.border }}>
              <View style={{ flex: 1 }}>
                <Text style={{ fontSize: 14, fontWeight: '700', color: colors.text }}>Auto-provision Twilio at signup</Text>
                <Text style={s.hint}>When on, every new account from the setup wizard gets its subaccount and provisioning started right away. Off = a super admin presses Provision Twilio on the organization.</Text>
              </View>
              <Switch value={!!flags.auto_provision} onValueChange={(v) => setFlag('auto_provision', v)} trackColor={{ false: 'rgba(128,128,128,0.3)', true: '#34C75966' }} thumbColor={flags.auto_provision ? '#34C759' : '#f4f3f4'} {...tid('flag-auto-provision')} />
            </View>
            <Text style={[s.hint, { marginTop: 10 }]} {...tid('flag-webhook-validation')}>Webhook signature validation: <Text style={{ fontWeight: '800' }}>{flags.webhook_validation}</Text> (server env TWILIO_WEBHOOK_VALIDATION: off / log / enforce).</Text>
          </View>
        )}

        <View style={{ flexDirection: 'row', gap: 6, marginBottom: 10, flexWrap: 'wrap' }}>
          {FILTERS.map(f => (
            <TouchableOpacity key={f.key} onPress={() => setFilter(f.key)} style={[s.chip, { borderColor: filter === f.key ? GOLD : colors.border, backgroundColor: filter === f.key ? GOLD : colors.card }]} {...tid(`mig-filter-${f.key.replace(' ', '-')}`)}>
              <Text style={{ fontSize: 12.5, fontWeight: '700', color: filter === f.key ? '#000' : colors.text }}>{f.label}</Text>
            </TouchableOpacity>
          ))}
        </View>
        {rows.map((r: any) => {
          const color = r.proposed_action === 'already registered' ? '#34C759' : r.proposed_action === 'import' ? '#5AC8FA' : '#FF9500';
          return (
            <View key={r.phone_number} style={[s.card, { marginBottom: 10 }]} {...tid(`mig-row-${r.phone_number.replace(/\D/g, '')}`)}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                <Text style={{ flex: 1, fontSize: 15, fontWeight: '800', color: colors.text }}>{prettyPhone(r.phone_number)} <Text style={{ fontWeight: '400', color: colors.textTertiary }}>· {r.number_type}</Text></Text>
                <Pill label={r.proposed_action} color={color} />
              </View>
              <Text style={{ fontSize: 12.5, color: colors.textSecondary, marginTop: 4 }}>
                {r.organization_name ? `Org: ${r.organization_name}` : 'Org: none'}{r.store_name ? ` · ${r.store_name}` : ''}{r.user_name ? ` · ${r.user_name}` : ''}
              </Text>
              <Text style={s.mono}>{r.sid || 'no SID'}{r.messaging_service_sid ? ` · ${r.messaging_service_sid}` : ''}{r.account_sid ? ` · ${r.account_sid.slice(0, 10)}…` : ''}</Text>
              <Text style={[s.hint, { marginTop: 2 }]}>Found in: {r.sources.join(', ')}</Text>
              {r.webhook_sms_url ? <Text style={[s.hint, { color: r.webhook_ok ? colors.textTertiary : '#FF9500' }]}>Webhook: {r.webhook_sms_url}</Text> : null}
              {r.issues.length > 0 && <Text style={{ fontSize: 12, color: '#FF9500', marginTop: 4 }}>{r.issues.join(' · ')}</Text>}
              <View style={{ flexDirection: 'row', gap: 6, marginTop: 8 }}>
                {!r.in_registry && r.sid && (
                  <TouchableOpacity onPress={() => importOne(r.phone_number)} disabled={!!busy} style={[s.chip, { borderColor: GOLD, backgroundColor: colors.bg }]} {...tid(`mig-import-${r.phone_number.replace(/\D/g, '')}`)}>
                    {busy === r.phone_number ? <ActivityIndicator size="small" color={GOLD} /> : <Text style={{ fontSize: 12, fontWeight: '700', color: colors.text }}>Import this one</Text>}
                  </TouchableOpacity>
                )}
                {r.organization_id && (
                  <TouchableOpacity onPress={() => router.push(`/admin/org-twilio/${r.organization_id}` as any)} style={[s.chip, { borderColor: colors.border, backgroundColor: colors.bg }]} {...tid(`mig-open-org-${r.phone_number.replace(/\D/g, '')}`)}>
                    <Text style={{ fontSize: 12, fontWeight: '700', color: colors.text }}>Open organization</Text>
                  </TouchableOpacity>
                )}
              </View>
            </View>
          );
        })}
        {rows.length === 0 && <Text style={s.hint} {...tid('mig-empty')}>Nothing in this filter.</Text>}
      </ScrollView>
    </SafeAreaView>
  );
}
