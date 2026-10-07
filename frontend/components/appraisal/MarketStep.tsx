import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, TextInput, TouchableOpacity, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { GOLD, tid, errText } from '../inbox/ownership';
import { BigButton, StepTitle, BusyBar } from './shared';
import { MarketSnapshotCard, ProviderBadge } from './MarketSnapshotCard';
import { ComparablesList } from './ComparablesList';
import { BookValuesEditor } from './BookValuesEditor';

type Props = { colors: any; appraisal: any; onSaved: (appraisal: any) => void; showToast: (m: string, t?: any, d?: number) => void };
const RADII = [25, 50, 100, 200];

// MARKET ANALYSIS: what this vehicle lists for around the store, the best comparables, and the book values the rep has. No ACV here (MVP4).
export const MarketStep = ({ colors, appraisal, onSaved, showToast }: Props) => {
  const [data, setData] = useState<any | null>(null);
  const [zip, setZip] = useState('');
  const [radius, setRadius] = useState(100);
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const d = (await api.get(`/appraisals/${appraisal.id}/market`)).data;
      setData(d); setZip(z => z || d.zip?.zip || ''); setRadius(d.zip?.radius || 100);
    } catch (e) { showToast(errText(e, 'Could not load market data'), 'error'); }
  }, [appraisal.id]);
  useEffect(() => { load(); }, [load]);

  const refresh = async (force = false) => {
    if (!/^\d{5}$/.test(zip)) { showToast('Enter the 5-digit ZIP to search around', 'error'); return; }
    setBusy(force ? 'Refreshing market data…' : 'Pulling market data…'); setErr(null);
    try {
      const d = (await api.post(`/appraisals/${appraisal.id}/market/refresh`, { zip, radius, force })).data;
      setData(d);
      if (d.cached) showToast('Same search in the last 24 hours, so the saved snapshot is shown. Use Refresh to pull again.', 'info', 4500);
    } catch (e: any) {
      const st = e?.response?.status;
      const m = errText(e, st === 429 ? 'Market data limit reached. Try again shortly.' : st === 503 ? 'The market data provider is not answering right now.' : 'Could not pull market data');
      setErr(m); showToast(m, 'error', 5000);
    } finally { setBusy(null); }
  };
  const next = async () => {
    try { const r = (await api.patch(`/appraisals/${appraisal.id}`, { step: 'expectation' })).data; onSaved(r.appraisal); }
    catch (e) { showToast(errText(e, 'Could not continue'), 'error'); }
  };

  if (!data) return <ActivityIndicator color={GOLD} style={{ marginTop: 30 }} />;
  const snap = data.snapshot;
  const prov = data.provider || {};
  return (
    <View style={{ gap: 14 }} {...tid('market-step')}>
      <StepTitle colors={colors} title="Market analysis" sub="What this vehicle is listed for near you, the closest comparables, and any book values you have. Market data only; the dealership's number comes in the next step of the rollout." />
      <View style={{ borderRadius: 16, padding: 14, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, gap: 10 }} {...tid('market-search')}>
        <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
          <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.8 }}>SEARCH AROUND</Text>
          <ProviderBadge live={!!prov.live} badge={prov.badge} testId="market-active-provider" />
        </View>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
          <TextInput value={zip} onChangeText={t => setZip(t.replace(/\D/g, '').slice(0, 5))} keyboardType="number-pad" placeholder="ZIP" placeholderTextColor={colors.textSecondary}
            style={{ width: 96, height: 48, borderRadius: 12, borderWidth: 1.5, borderColor: /^\d{5}$/.test(zip) ? GOLD : colors.border, backgroundColor: colors.bg, color: colors.text, paddingHorizontal: 12, fontSize: 18, fontWeight: '700', fontVariant: ['tabular-nums'] }} {...tid('market-zip')} />
          <View style={{ flex: 1, flexDirection: 'row', gap: 6 }}>
            {RADII.map(r => (
              <TouchableOpacity key={r} onPress={() => setRadius(r)} style={{ flex: 1, height: 48, borderRadius: 12, alignItems: 'center', justifyContent: 'center', backgroundColor: radius === r ? GOLD + '33' : colors.bg, borderWidth: 1, borderColor: radius === r ? GOLD : colors.border }} {...tid(`market-radius-${r}`)}>
                <Text style={{ fontSize: 12.5, fontWeight: '800', color: radius === r ? GOLD : colors.text }}>{r} mi</Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>
        <Text style={{ fontSize: 11.5, color: colors.textSecondary }} {...tid('market-zip-source')}>
          {data.zip?.zip_source === 'store' ? `ZIP from ${data.zip.store_name || 'your store'}` : data.zip?.zip_source === 'appraisal' ? 'ZIP saved on this appraisal' : data.zip?.zip_source === 'profile' ? 'ZIP from your profile' : 'No store ZIP on file. Type one.'}
          {' · '}{appraisal.vehicle_label}{appraisal.mileage_confirmed != null ? ` · ${appraisal.mileage_confirmed.toLocaleString()} mi` : ''}
        </Text>
        {snap ? (
          <TouchableOpacity onPress={() => refresh(true)} disabled={!!busy} style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, height: 46, borderRadius: 12, borderWidth: 1, borderColor: GOLD, opacity: busy ? 0.5 : 1 }} {...tid('market-refresh')}>
            <Ionicons name="refresh" size={16} color={GOLD} /><Text style={{ fontSize: 14, fontWeight: '800', color: GOLD }}>Refresh market data</Text>
          </TouchableOpacity>
        ) : (
          <BigButton colors={colors} icon="stats-chart" label="Pull market data" sub={prov.live ? `${prov.label} · uses the store's monthly quota` : 'Development data while no MarketCheck key is set'} onPress={() => refresh(false)} primary disabled={!!busy} testId="market-pull" />
        )}
        <BusyBar text={busy} colors={colors} />
        {err ? <Text style={{ fontSize: 12.5, color: '#FF3B30' }} {...tid('market-error')}>{err}</Text> : null}
      </View>
      {snap ? <MarketSnapshotCard colors={colors} snapshot={snap} mileage={data.mileage} historyCount={(data.history || []).length} /> : null}
      {snap ? <ComparablesList colors={colors} comps={data.comparables || []} live={!!snap.live} /> : null}
      <BookValuesEditor colors={colors} appraisalId={appraisal.id} bookValues={data.book_values || []} sources={data.book_sources || {}} types={data.value_types || {}} onChanged={bv => setData((d: any) => ({ ...d, book_values: bv }))} showToast={showToast} />
      <BigButton colors={colors} icon="checkmark" label="Continue" sub={snap ? undefined : 'You can come back for market data any time'} onPress={next} primary={!!snap} testId="market-continue" />
    </View>
  );
};
