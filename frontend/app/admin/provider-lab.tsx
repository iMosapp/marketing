import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, TextInput, TouchableOpacity, ScrollView, ActivityIndicator, KeyboardAvoidingView, Platform } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { useThemeStore } from '../../store/themeStore';
import { useToast } from '../../components/common/Toast';
import { ScreenHeader } from '../../components/common/ScreenHeader';
import { GOLD, tid, errText } from '../../components/inbox/ownership';
import { ProviderCompare } from '../../components/appraisal/ProviderCompare';
import { money } from '../../components/appraisal/shared';

const RADII = [25, 50, 100, 200];
const when = (iso?: string) => (iso ? new Date(iso).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }) : '');

// PROVIDER LAB (admins): run MarketCheck and VinAudit on the same vehicle, on purpose, and keep both answers separate. Validation only; nothing here touches an appraisal.
export default function ProviderLab() {
  const router = useRouter();
  const { colors } = useThemeStore();
  const { showToast } = useToast();
  const [info, setInfo] = useState<any | null>(null);
  const [recent, setRecent] = useState<any[]>([]);
  const [form, setForm] = useState({ vin: '', mileage: '', zip: '', radius: 100 });
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<any | null>(null);

  const load = useCallback(async () => {
    try {
      const [p, c] = await Promise.all([api.get('/appraisals/providers'), api.get('/appraisals/providers/comparisons?limit=25')]);
      setInfo(p.data); setRecent(c.data.comparisons || []);
    } catch (e: any) {
      if (e?.response?.status === 403) { showToast('Admins only', 'error'); router.replace('/appraisals' as any); return; }
      showToast(errText(e, 'Could not load provider status'), 'error');
    }
  }, []);
  useEffect(() => { load(); }, [load]);

  const configured = (info?.market || []).filter((p: any) => p.live && p.configured);
  const callsPerRun = (info?.market || []).reduce((n: number, p: any) => n + (p.live && p.configured ? (p.name === 'vinaudit' ? 2 : p.calls_per_fetch) : 0), 0);
  const vinOk = /^[A-HJ-NPR-Z0-9]{17}$/i.test(form.vin.trim());
  const zipOk = /^\d{5}$/.test(form.zip);

  const run = async (force = false) => {
    if (!vinOk) { showToast('Enter a 17-character VIN', 'error'); return; }
    if (!zipOk) { showToast('Enter the 5-digit ZIP', 'error'); return; }
    setBusy(true);
    try {
      const r = (await api.post('/appraisals/providers/compare', { vin: form.vin.trim().toUpperCase(), mileage: form.mileage ? parseInt(form.mileage, 10) : null, zip: form.zip, radius: form.radius, force })).data;
      setResult(r); load();
      const cached = (r.providers || []).filter((c: any) => c.cached).length;
      showToast(cached ? `${cached} provider answer${cached === 1 ? '' : 's'} reused from the last 24h; use Re-run to spend calls again.` : `Comparison done · ${r.calls_total} paid call${r.calls_total === 1 ? '' : 's'}`, 'success', 4500);
    } catch (e: any) {
      const st = e?.response?.status;
      showToast(errText(e, st === 429 ? 'Rate limit or quota reached' : st === 503 ? 'VIN decoder unavailable; add year/make/model' : 'Comparison failed'), 'error', 6000);
    } finally { setBusy(false); }
  };

  if (!info) return <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}><ScreenHeader title="Provider Lab" /><ActivityIndicator color={GOLD} style={{ marginTop: 40 }} /></SafeAreaView>;
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']} {...tid('provider-lab')}>
      <ScreenHeader title="Provider Lab" subtitle="MarketCheck and VinAudit, side by side, on purpose" onBack={() => (router.canGoBack() ? router.back() : router.replace('/(tabs)/more' as any))} />
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={{ flex: 1 }}>
        <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 60, gap: 14 }} keyboardShouldPersistTaps="handled">
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }} {...tid('provider-lab-status')}>
            {(info.usage_all || []).map((u: any) => (
              <View key={u.provider} style={{ flex: 1, minWidth: 150, borderRadius: 14, padding: 12, backgroundColor: colors.card, borderWidth: 1, borderColor: u.configured ? '#34C75966' : colors.border, gap: 2 }} {...tid(`provider-usage-${u.provider}`)}>
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                  <Ionicons name={u.configured ? 'shield-checkmark' : 'key-outline'} size={14} color={u.configured ? '#34C759' : colors.textSecondary} />
                  <Text style={{ fontSize: 13, fontWeight: '800', color: colors.text }}>{u.label}</Text>
                </View>
                <Text style={{ fontSize: 11.5, color: colors.textSecondary }}>{u.configured ? 'Key installed' : 'No key on this server'}</Text>
                <Text style={{ fontSize: 12.5, fontWeight: '700', color: colors.text, fontVariant: ['tabular-nums'] }}>{u.calls} / {u.cap ?? '∞'} calls this month</Text>
                <Text style={{ fontSize: 11, color: colors.textSecondary }}>{u.snapshots} appraisal pulls · {u.comparisons} comparisons · {u.failures} failures{u.quota_remaining != null ? ` · ${u.quota_remaining} left at provider` : ''}</Text>
              </View>
            ))}
          </View>
          {info.dev_market_allowed ? <Text style={{ fontSize: 12, fontWeight: '700', color: '#FF9500' }} {...tid('provider-lab-dev-warning')}>APPRAISAL_ALLOW_DEV_MARKET is on here (preview). Production must leave it empty.</Text> : null}

          <View style={{ borderRadius: 16, padding: 14, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, gap: 10 }} {...tid('provider-lab-form')}>
            <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.8 }}>ONE VEHICLE, BOTH PROVIDERS</Text>
            <TextInput value={form.vin} onChangeText={t => setForm(f => ({ ...f, vin: t.toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 17) }))} placeholder="17-character VIN" placeholderTextColor={colors.textSecondary} autoCapitalize="characters" autoCorrect={false}
              style={{ height: 48, borderRadius: 12, borderWidth: 1.5, borderColor: vinOk ? GOLD : colors.border, backgroundColor: colors.bg, color: colors.text, paddingHorizontal: 12, fontSize: 16, fontWeight: '700', letterSpacing: 1 }} {...tid('lab-vin')} />
            <View style={{ flexDirection: 'row', gap: 8 }}>
              <TextInput value={form.mileage} onChangeText={t => setForm(f => ({ ...f, mileage: t.replace(/\D/g, '').slice(0, 7) }))} keyboardType="number-pad" placeholder="Mileage" placeholderTextColor={colors.textSecondary}
                style={{ flex: 1, height: 48, borderRadius: 12, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.bg, color: colors.text, paddingHorizontal: 12, fontSize: 16, fontWeight: '700' }} {...tid('lab-mileage')} />
              <TextInput value={form.zip} onChangeText={t => setForm(f => ({ ...f, zip: t.replace(/\D/g, '').slice(0, 5) }))} keyboardType="number-pad" placeholder="ZIP" placeholderTextColor={colors.textSecondary}
                style={{ width: 110, height: 48, borderRadius: 12, borderWidth: 1.5, borderColor: zipOk ? GOLD : colors.border, backgroundColor: colors.bg, color: colors.text, paddingHorizontal: 12, fontSize: 16, fontWeight: '700' }} {...tid('lab-zip')} />
            </View>
            <View style={{ flexDirection: 'row', gap: 6 }}>
              {RADII.map(r => (
                <TouchableOpacity key={r} onPress={() => setForm(f => ({ ...f, radius: r }))} style={{ flex: 1, height: 40, borderRadius: 12, alignItems: 'center', justifyContent: 'center', backgroundColor: form.radius === r ? GOLD + '33' : colors.bg, borderWidth: 1, borderColor: form.radius === r ? GOLD : colors.border }} {...tid(`lab-radius-${r}`)}>
                  <Text style={{ fontSize: 12.5, fontWeight: '800', color: form.radius === r ? GOLD : colors.text }}>{r} mi</Text>
                </TouchableOpacity>
              ))}
            </View>
            <Text style={{ fontSize: 11.5, color: colors.textSecondary }}>Radius and ZIP drive MarketCheck's listing search. VinAudit is national by VIN and ignores both.</Text>
            <TouchableOpacity onPress={() => run(false)} disabled={busy || !configured.length} style={{ height: 50, borderRadius: 14, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 8, opacity: busy || !configured.length ? 0.5 : 1 }} {...tid('lab-run')}>
              {busy ? <ActivityIndicator color="#0B0B0D" /> : <><Ionicons name="git-compare" size={18} color="#0B0B0D" /><Text style={{ fontSize: 15, fontWeight: '800', color: '#0B0B0D' }}>Run comparison · up to {callsPerRun} paid call{callsPerRun === 1 ? '' : 's'}</Text></>}
            </TouchableOpacity>
            {!configured.length ? <Text style={{ fontSize: 12, color: '#FF9500' }} {...tid('lab-no-keys')}>No live provider key is installed on this server, so there is nothing to compare yet.</Text> : null}
            {result ? (
              <TouchableOpacity onPress={() => run(true)} disabled={busy} style={{ alignSelf: 'flex-start' }} {...tid('lab-rerun')}>
                <Text style={{ fontSize: 12.5, fontWeight: '800', color: GOLD }}>Re-run now (ignores the 24h cache, spends calls)</Text>
              </TouchableOpacity>
            ) : null}
          </View>

          {result ? <ProviderCompare colors={colors} comparison={result} /> : null}

          {(info.cost?.rows || []).length ? (
            <View style={{ borderRadius: 16, padding: 14, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, gap: 6 }} {...tid('provider-lab-cost')}>
              <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.8 }}>CALLS THIS MONTH · {info.cost.month}</Text>
              {info.cost.rows.map((r: any, i: number) => (
                <Text key={i} style={{ fontSize: 12.5, color: colors.text }}>{r.provider} · {r.purpose}: <Text style={{ fontWeight: '800' }}>{r.calls} calls</Text> over {r.fetches} pull{r.fetches === 1 ? '' : 's'}{r.failures ? ` (${r.failures} failed)` : ''}{r.calls_per_appraisal != null ? ` · ${r.calls_per_appraisal} per appraisal` : ''} · {r.avg_ms} ms avg</Text>
              ))}
            </View>
          ) : null}

          <View style={{ gap: 8 }} {...tid('provider-lab-recent')}>
            <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.8 }}>RECENT COMPARISONS</Text>
            {!recent.length ? <Text style={{ fontSize: 12.5, color: colors.textSecondary }}>None yet in your reach.</Text> : recent.map((c: any) => {
              const mc = (c.providers || []).find((p: any) => p.provider === 'marketcheck') || {};
              const va = (c.providers || []).find((p: any) => p.provider === 'vinaudit') || {};
              const v = c.vehicle || {};
              return (
                <TouchableOpacity key={c.id} onPress={() => setResult(c)} style={{ borderRadius: 12, padding: 10, backgroundColor: colors.card, borderWidth: 1, borderColor: result?.id === c.id ? GOLD : colors.border, gap: 2 }} {...tid(`lab-recent-${c.id}`)}>
                  <Text style={{ fontSize: 13, fontWeight: '800', color: colors.text }} numberOfLines={1}>{[v.year, v.make, v.model, v.trim].filter(Boolean).join(' ')}{v.vin ? ` · ${v.vin}` : ''}</Text>
                  <Text style={{ fontSize: 11.5, color: colors.textSecondary }} numberOfLines={1}>
                    MC {mc.estimated_retail ? money(mc.estimated_retail) : (mc.status || 'n/a')} · VA {va.estimated_retail ? money(va.estimated_retail) : (va.status || 'n/a')}{c.difference?.available ? ` · gap ${money(Math.abs(c.difference.dollars))} (${c.difference.percent}%)` : ''} · {when(c.created_at)}{c.purpose === 'matrix' ? ' · matrix' : ''}
                  </Text>
                </TouchableOpacity>
              );
            })}
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
