/**
 * Admin > Relationship Intelligence: the Phase 1B operations console.
 * Shows the three flags, runs the READ-ONLY backfill dry run (writes nothing) and renders the report with the per-store breakdown.
 * Execute / rollback stay API-only on purpose: this screen cannot write anything.
 */
import React, { useEffect, useState } from 'react';
import { View, Text, ScrollView, TouchableOpacity, ActivityIndicator, Platform } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import api from '../../services/api';
import { useThemeStore } from '../../store/themeStore';
import { useToast } from '../../components/common/Toast';
import { ScreenHeader } from '../../components/common/ScreenHeader';
import { GOLD, tid, errText } from '../../components/inbox/ownership';

function Flag({ name, on, colors }: { name: string; on: boolean; colors: any }) {
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 6 }} {...tid(`intel-flag-${name}`)}>
      <View style={{ width: 9, height: 9, borderRadius: 5, backgroundColor: on ? '#34C759' : colors.textTertiary }} />
      <Text style={{ flex: 1, fontSize: 13.5, color: colors.text, fontFamily: Platform.OS === 'web' ? 'monospace' : undefined }}>{name}</Text>
      <Text style={{ fontSize: 12.5, fontWeight: '800', color: on ? '#34C759' : colors.textSecondary }}>{on ? 'ON' : 'OFF'}</Text>
    </View>
  );
}

function Stat({ label, value, colors, testid }: any) {
  return (
    <View style={{ minWidth: 120, flexGrow: 1, padding: 12, borderRadius: 12, backgroundColor: colors.surface }} {...tid(testid)}>
      <Text style={{ fontSize: 20, fontWeight: '800', color: colors.text }}>{value}</Text>
      <Text style={{ fontSize: 11.5, color: colors.textSecondary, marginTop: 2 }}>{label}</Text>
    </View>
  );
}

export default function IntelligenceOpsScreen() {
  const router = useRouter();
  const { colors } = useThemeStore();
  const { showToast } = useToast();
  const [cfg, setCfg] = useState<any>(null);
  const [report, setReport] = useState<any>(null);
  const [running, setRunning] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    api.get('/intel/config').then(r => setCfg(r.data)).catch((e: any) => {
      if (e?.response?.status === 403) { showToast('Managers only', 'error', 4000); if (router.canGoBack()) router.back(); else router.replace('/(tabs)/more' as any); return; }
      showToast(errText(e, 'Could not load the intelligence config'), 'error');
    });
  }, []);

  const run = async () => {
    setRunning(true); setReport(null); setCopied(false);
    try {
      const d = (await api.get('/intel/backfill/dry-run', { timeout: 180000 })).data;
      setReport(d);
      showToast(d.read_only ? 'Dry run finished. Nothing was written.' : 'Dry run finished.', 'success');
    } catch (e: any) {
      showToast(errText(e, 'Dry run failed'), 'error', 6000);
    } finally {
      setRunning(false);
    }
  };

  const copy = async () => {
    if (!report) return;
    const { samples, ...rest } = report;
    const text = JSON.stringify({ ...rest, samples: (samples || []).map((s: any) => ({ name: s.name, facts: s.facts?.length, projection_diff: s.projection_diff })) }, null, 2);
    try {
      if (Platform.OS === 'web' && (navigator as any)?.clipboard) await (navigator as any).clipboard.writeText(text);
      else { const Clipboard = await import('expo-clipboard'); await Clipboard.setStringAsync(text); }
      setCopied(true);
    } catch { showToast('Could not copy', 'error'); }
  };

  const flags = cfg?.flags || {};
  const anyOn = !!(flags.ingest || flags.legacy_projection || flags.backfill_execute || flags.nudges);

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      <ScreenHeader title="Relationship Intelligence" subtitle="Phase 1B operations, read-only here" onBack={() => (router.canGoBack() ? router.back() : router.replace('/admin' as any))} />
      <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 60, gap: 14 }} {...tid('intel-ops-screen')}>
        <View style={{ padding: 14, borderRadius: 16, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.card }}>
          <Text style={{ fontSize: 11, fontWeight: '800', color: GOLD, textTransform: 'uppercase', letterSpacing: 0.8, marginBottom: 6 }}>Flags on this server</Text>
          {!cfg ? <ActivityIndicator color={GOLD} /> : (
            <>
              <Flag name="INTEL_FACTS_INGEST" on={!!flags.ingest} colors={colors} />
              <Flag name="INTEL_LEGACY_PROJECTION" on={!!flags.legacy_projection} colors={colors} />
              <Flag name="INTEL_BACKFILL_EXECUTE" on={!!flags.backfill_execute} colors={colors} />
              <Flag name="INTEL_NUDGES" on={!!flags.nudges} colors={colors} />
              <Text style={{ fontSize: 12.5, color: colors.textSecondary, marginTop: 8, lineHeight: 18 }} {...tid('intel-flags-summary')}>
                {anyOn ? 'At least one write path is on: new events may create facts, and legacy fields may follow them.' : 'All write flags are off: the engine reads only. No fact is written, no legacy field changes, no nudge task is created, the fact store is not even created.'}
              </Text>
            </>
          )}
        </View>

        <View style={{ padding: 14, borderRadius: 16, borderWidth: 1, borderColor: `${GOLD}66`, backgroundColor: `${GOLD}10` }}>
          <Text style={{ fontSize: 11, fontWeight: '800', color: GOLD, textTransform: 'uppercase', letterSpacing: 0.8, marginBottom: 6 }}>Backfill dry run</Text>
          <Text style={{ fontSize: 13.5, color: colors.text, lineHeight: 19 }}>Counts what the backfill would create and how the legacy fields would differ, per store. It writes nothing: not a fact, not a field, not even its own report.</Text>
          <TouchableOpacity onPress={run} disabled={running} activeOpacity={0.8} style={{ marginTop: 12, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, paddingVertical: 12, borderRadius: 12, backgroundColor: GOLD, opacity: running ? 0.6 : 1 }} {...tid('intel-dry-run-btn')}>
            {running ? <ActivityIndicator size="small" color="#111" /> : <Ionicons name="eye-outline" size={16} color="#111" />}
            <Text style={{ fontSize: 14, fontWeight: '800', color: '#111' }}>{running ? 'Reading every contact...' : 'Run read-only dry run'}</Text>
          </TouchableOpacity>
        </View>

        {report && (
          <View style={{ padding: 14, borderRadius: 16, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.card, gap: 10 }} {...tid('intel-dry-run-report')}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
              <Ionicons name={report.read_only ? 'lock-closed' : 'lock-open'} size={15} color={report.read_only ? '#34C759' : '#FF9500'} />
              <Text style={{ flex: 1, fontSize: 13, fontWeight: '700', color: report.read_only ? '#34C759' : '#FF9500' }} {...tid('intel-dry-run-readonly')}>
                {report.read_only ? 'read_only: true · writes_performed: []' : `writes_performed: ${JSON.stringify(report.writes_performed)}`}
              </Text>
              <Text style={{ fontSize: 12, color: colors.textSecondary }} {...tid('intel-dry-run-ms')}>{report.processing_ms} ms</Text>
            </View>
            <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
              <Stat label="contacts scanned" value={report.contacts_scanned} colors={colors} testid="intel-stat-contacts" />
              <Stat label="would receive facts" value={report.contacts_with_facts} colors={colors} testid="intel-stat-with-facts" />
              <Stat label="facts (distinct)" value={report.facts_distinct} colors={colors} testid="intel-stat-facts" />
              <Stat label="repeat evidence folded" value={report.repeat_evidence} colors={colors} testid="intel-stat-repeats" />
              <Stat label="conflicts" value={report.scalar_conflicts} colors={colors} testid="intel-stat-conflicts" />
              <Stat label="legacy fields would change" value={report.contacts_whose_legacy_fields_would_change} colors={colors} testid="intel-stat-legacy" />
              <Stat label="facts already stored" value={report.existing_facts} colors={colors} testid="intel-stat-existing" />
            </View>
            {!!report.legacy_fields_changed && Object.keys(report.legacy_fields_changed).length > 0 && (
              <Text style={{ fontSize: 12.5, color: colors.textSecondary }}>Fields: {Object.entries(report.legacy_fields_changed).map(([k, v]) => `${k} ×${v}`).join(', ')}</Text>
            )}
            <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, textTransform: 'uppercase', letterSpacing: 0.6, marginTop: 4 }}>Per store</Text>
            {Object.entries(report.by_store || {}).map(([sid, row]: any) => (
              <View key={sid} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 6, borderTopWidth: 1, borderTopColor: colors.border }} {...tid(`intel-store-${sid}`)}>
                <Text style={{ flex: 1, fontSize: 12.5, color: colors.text, fontFamily: Platform.OS === 'web' ? 'monospace' : undefined }} numberOfLines={1}>{sid}</Text>
                <Text style={{ fontSize: 12.5, color: colors.textSecondary }}>{row.contacts} contacts · {row.with_facts} with facts · {row.facts_distinct} facts · {row.legacy_changes} legacy changes</Text>
              </View>
            ))}
            <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, textTransform: 'uppercase', letterSpacing: 0.6, marginTop: 4 }}>By source</Text>
            <Text style={{ fontSize: 12.5, color: colors.text }}>{Object.entries(report.by_source || {}).map(([k, v]) => `${k} ${v}`).join(' · ') || 'none'}</Text>
            {(report.samples || []).some((s: any) => s.projection_diff && Object.keys(s.projection_diff).length) && (
              <>
                <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, textTransform: 'uppercase', letterSpacing: 0.6, marginTop: 4 }}>Sample legacy differences</Text>
                {(report.samples || []).filter((s: any) => s.projection_diff && Object.keys(s.projection_diff).length).map((s: any) => (
                  <View key={s.contact_id} style={{ paddingVertical: 4 }}>
                    <Text style={{ fontSize: 12.5, fontWeight: '700', color: colors.text }}>{s.name || s.contact_id}</Text>
                    {Object.entries(s.projection_diff).map(([k, v]: any) => <Text key={k} style={{ fontSize: 12, color: colors.textSecondary }}>{k}: {String(v[0]) || '(empty)'} → {String(v[1])}</Text>)}
                  </View>
                ))}
              </>
            )}
            <TouchableOpacity onPress={copy} activeOpacity={0.8} style={{ marginTop: 6, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, paddingVertical: 11, borderRadius: 12, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.surface }} {...tid('intel-copy-report')}>
              <Ionicons name={copied ? 'checkmark' : 'copy-outline'} size={15} color={colors.text} />
              <Text style={{ fontSize: 13.5, fontWeight: '700', color: colors.text }}>{copied ? 'Report copied' : 'Copy report as JSON'}</Text>
            </TouchableOpacity>
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}
