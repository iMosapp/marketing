import React, { useEffect, useMemo, useRef, useState } from 'react';
import { View, Text, TextInput, TouchableOpacity, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { GOLD, tid, errText } from '../inbox/ownership';
import { showConfirm } from '../../services/alert';
import { money } from './shared';

type Props = { colors: any; zip: string; radius: number; callsPerVehicle: number; showToast: (m: string, t?: any, d?: number) => void; onFinished?: () => void };
const when = (iso?: string) => (iso ? new Date(iso).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }) : '');

// One line per vehicle: "VIN, mileage[, zip]" or "year make model[, mileage[, zip]]".
export const parseVehicles = (text: string) =>
  text.split(/\n+/).map(l => l.trim()).filter(Boolean).map(line => {
    const parts = line.split(/[,\t;]+/).map(p => p.trim()).filter(Boolean);
    const vin = parts[0] && /^[A-HJ-NPR-Z0-9]{17}$/i.test(parts[0]) ? parts[0].toUpperCase() : '';
    if (vin) return { vin, mileage: parts[1] ? parts[1].replace(/\D/g, '') : null, zip: parts[2] && /^\d{5}$/.test(parts[2]) ? parts[2] : null };
    const m = parts[0]?.match(/^(\d{4})\s+(\S+)\s+(.+)$/);
    if (!m) return { raw: line };
    return { year: m[1], make: m[2], model: m[3], mileage: parts[1] ? parts[1].replace(/\D/g, '') : null, zip: parts[2] && /^\d{5}$/.test(parts[2]) ? parts[2] : null };
  });

// VALIDATION MATRIX: paste 10-25 real vehicles, see the paid-call bill up front, run both providers in the background on the server that holds
// the keys, watch the rows land, read the side-by-side. Nothing is averaged; nothing touches an appraisal.
export const ProviderMatrix = ({ colors, zip, radius, callsPerVehicle, showToast, onFinished }: Props) => {
  const [text, setText] = useState('');
  const [run, setRun] = useState<any | null>(null);
  const [runs, setRuns] = useState<any[]>([]);
  const [busy, setBusy] = useState(false);
  const poll = useRef<any>(null);
  const vehicles = useMemo(() => parseVehicles(text), [text]);
  const good = vehicles.filter(v => !(v as any).raw).slice(0, 25);
  const bad = vehicles.filter(v => (v as any).raw);
  const zipOk = /^\d{5}$/.test(zip);
  const totalCalls = good.length * callsPerVehicle;

  const loadRuns = async () => { try { setRuns((await api.get('/appraisals/providers/matrix?limit=5')).data.runs || []); } catch { /* best effort */ } };
  useEffect(() => { loadRuns(); return () => { if (poll.current) clearInterval(poll.current); }; }, []);

  const watch = (id: string) => {
    if (poll.current) clearInterval(poll.current);
    poll.current = setInterval(async () => {
      try {
        const r = (await api.get(`/appraisals/providers/matrix/${id}`)).data;
        setRun(r);
        if (r.status !== 'running') { clearInterval(poll.current); poll.current = null; loadRuns(); onFinished?.(); showToast(r.status === 'done' ? `Matrix done · ${r.summary?.calls_total ?? 0} paid calls` : `Matrix stopped: ${r.last_error || 'error'}`, r.status === 'done' ? 'success' : 'error', 5000); }
      } catch { /* keep polling */ }
    }, 3000);
  };

  const start = () => {
    if (!good.length) { showToast('Paste at least one vehicle: VIN, mileage', 'error'); return; }
    if (!zipOk) { showToast('Set the default ZIP in the form above first', 'error'); return; }
    showConfirm(`Spend about ${totalCalls} paid API calls?`, `${good.length} vehicle${good.length === 1 ? '' : 's'} × ${callsPerVehicle} calls. Answers from the last 24h are reused, not re-bought.`, async () => {
      setBusy(true);
      try {
        const r = (await api.post('/appraisals/providers/matrix', { vehicles: good, zip, radius })).data;
        setRun(r); watch(r.id);
      } catch (e: any) { showToast(errText(e, 'Could not start the matrix'), 'error', 6000); }
      finally { setBusy(false); }
    });
  };

  const open = async (id: string) => {
    try { const r = (await api.get(`/appraisals/providers/matrix/${id}`)).data; setRun(r); if (r.status === 'running') watch(id); }
    catch (e: any) { showToast(errText(e, 'Could not open that run'), 'error'); }
  };

  const s = run?.summary;
  return (
    <View style={{ gap: 12 }} {...tid('provider-matrix')}>
      <View style={{ borderRadius: 16, padding: 14, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, gap: 10 }}>
        <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.8 }}>VALIDATION MATRIX · 10 TO 25 REAL VEHICLES</Text>
        <Text style={{ fontSize: 12.5, color: colors.textSecondary, lineHeight: 18 }}>One per line: <Text style={{ fontWeight: '800', color: colors.text }}>VIN, mileage</Text> (ZIP optional third). Or <Text style={{ fontWeight: '800', color: colors.text }}>2021 Jeep Gladiator, 41000</Text>. Runs on the server that holds the keys, so nothing is pasted anywhere.</Text>
        <TextInput value={text} onChangeText={setText} multiline placeholder={'1C6JJTEG5ML512345, 41200\n5TFCZ5AN8KX012345, 63800, 84070\n2022 Ford F-150, 28000'} placeholderTextColor={colors.textSecondary} autoCapitalize="characters" autoCorrect={false}
          style={{ minHeight: 120, borderRadius: 12, borderWidth: 1, borderColor: good.length ? GOLD : colors.border, backgroundColor: colors.bg, color: colors.text, padding: 12, fontSize: 14, fontWeight: '600', textAlignVertical: 'top' }} {...tid('matrix-input')} />
        <Text style={{ fontSize: 12, color: colors.textSecondary }} {...tid('matrix-plan')}>
          {good.length} vehicle{good.length === 1 ? '' : 's'} · {callsPerVehicle} paid call{callsPerVehicle === 1 ? '' : 's'} each · <Text style={{ fontWeight: '800', color: colors.text }}>{totalCalls} calls total</Text> · default ZIP {zipOk ? zip : 'missing'} · {radius} mi{bad.length ? ` · ${bad.length} line${bad.length === 1 ? '' : 's'} not understood` : ''}
        </Text>
        <TouchableOpacity onPress={start} disabled={busy || !good.length || !callsPerVehicle || run?.status === 'running'} style={{ height: 50, borderRadius: 14, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 8, opacity: busy || !good.length || !callsPerVehicle || run?.status === 'running' ? 0.5 : 1 }} {...tid('matrix-run')}>
          {busy ? <ActivityIndicator color="#0B0B0D" /> : <><Ionicons name="grid" size={18} color="#0B0B0D" /><Text style={{ fontSize: 15, fontWeight: '800', color: '#0B0B0D' }}>{callsPerVehicle ? `Run the matrix · ${totalCalls} paid calls` : 'Run the matrix · no live key installed'}</Text></>}
        </TouchableOpacity>
      </View>

      {run ? (
        <View style={{ borderRadius: 16, padding: 14, backgroundColor: colors.card, borderWidth: 1, borderColor: run.status === 'running' ? GOLD : colors.border, gap: 10 }} {...tid('matrix-run-card')}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
            {run.status === 'running' ? <ActivityIndicator color={GOLD} size="small" /> : <Ionicons name={run.status === 'done' ? 'checkmark-circle' : 'alert-circle'} size={18} color={run.status === 'done' ? '#34C759' : '#FF3B30'} />}
            <Text style={{ fontSize: 13.5, fontWeight: '800', color: colors.text, flex: 1 }} {...tid('matrix-progress')}>{run.status === 'running' ? `Running · ${run.done} of ${run.total} vehicles` : run.status === 'done' ? `Done · ${run.rows.length}${run.errors?.length ? ` of ${run.total}` : ''} vehicles` : `Stopped · ${run.last_error || 'error'}`} · {when(run.created_at)}</Text>
          </View>
          {s ? (
            <View style={{ gap: 3 }} {...tid('matrix-summary')}>
              <Text style={{ fontSize: 12.5, color: colors.text }}>Both answered on <Text style={{ fontWeight: '800' }}>{s.both_answered}</Text> of {s.vehicles}. MarketCheck higher on {s.marketcheck_higher}, VinAudit higher on {s.vinaudit_higher}.{s.median_abs_gap != null ? ` Median gap ${money(s.median_abs_gap)} (${s.median_abs_percent}%).` : ''}</Text>
              <Text style={{ fontSize: 12, color: colors.textSecondary }}>MarketCheck answered {s.marketcheck_answered}, VinAudit {s.vinaudit_answered} · {s.calls_total} paid calls · median response MC {s.mc_median_ms ?? '-'} ms, VA {s.va_median_ms ?? '-'} ms{s.skipped ? ` · ${s.skipped} skipped` : ''}. Each number is the provider's own; nothing was averaged.</Text>
            </View>
          ) : null}
          {run.rows.map((r: any, i: number) => (
            <View key={r.comparison_id || i} style={{ borderTopWidth: 1, borderTopColor: colors.border, paddingTop: 8, gap: 2 }} {...tid(`matrix-row-${i}`)}>
              <Text style={{ fontSize: 13, fontWeight: '800', color: colors.text }} numberOfLines={1}>{i + 1}. {[r.year, r.make, r.model, r.trim].filter(Boolean).join(' ')}{r.mileage ? ` · ${Number(r.mileage).toLocaleString()} mi` : ''}</Text>
              <Text style={{ fontSize: 11.5, color: colors.textSecondary }} numberOfLines={1}>{r.vin || ''}{r.zip ? ` · ${r.zip}` : ''}</Text>
              <View style={{ flexDirection: 'row', gap: 10, marginTop: 2 }}>
                <View style={{ flex: 1 }}>
                  <Text style={{ fontSize: 10.5, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.5 }}>MARKETCHECK</Text>
                  <Text style={{ fontSize: 14, fontWeight: '800', color: r.mc.retail ? colors.text : '#FF9500' }} numberOfLines={1}>{r.mc.retail ? money(r.mc.retail) : (r.mc.error ? 'error' : r.mc.status || 'n/a')}</Text>
                  <Text style={{ fontSize: 11, color: colors.textSecondary }} numberOfLines={2}>{r.mc.comps != null ? `${r.mc.comps} comps, median ${r.mc.comps_median ? money(r.mc.comps_median) : '-'}` : ''}{r.mc.confidence ? ` · ${r.mc.confidence}` : ''}{r.mc.ms ? ` · ${r.mc.ms} ms` : ''}{r.mc.cached ? ' · reused' : ''}</Text>
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={{ fontSize: 10.5, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.5 }}>VINAUDIT</Text>
                  <Text style={{ fontSize: 14, fontWeight: '800', color: r.va.retail ? colors.text : '#FF9500' }} numberOfLines={1}>{r.va.retail ? money(r.va.retail) : (r.va.error ? 'error' : r.va.status || 'n/a')}</Text>
                  <Text style={{ fontSize: 11, color: colors.textSecondary }} numberOfLines={2}>{r.va.trade_in ? `trade-in ${money(r.va.trade_in)}` : ''}{r.va.records != null ? ` · ${r.va.records} records` : ''}{r.va.certainty != null ? ` (${r.va.certainty}%)` : ''}{r.va.ms ? ` · ${r.va.ms} ms` : ''}{r.va.cached ? ' · reused' : ''}</Text>
                </View>
                <View style={{ width: 88, alignItems: 'flex-end' }}>
                  <Text style={{ fontSize: 10.5, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.5 }}>GAP</Text>
                  <Text style={{ fontSize: 14, fontWeight: '800', color: GOLD }} {...tid(`matrix-gap-${i}`)}>{r.diff_dollars != null ? `${r.diff_dollars > 0 ? '+' : r.diff_dollars < 0 ? '-' : ''}${money(Math.abs(r.diff_dollars))}` : 'n/a'}</Text>
                  <Text style={{ fontSize: 11, color: colors.textSecondary }}>{r.diff_percent != null ? `${r.diff_percent}% · MC vs VA` : ''}</Text>
                </View>
              </View>
              {(r.mc.error || r.va.error) ? <Text style={{ fontSize: 11, color: '#FF9500' }} numberOfLines={2}>{r.mc.error ? `MC: ${r.mc.error}` : ''}{r.mc.error && r.va.error ? ' · ' : ''}{r.va.error ? `VA: ${r.va.error}` : ''}</Text> : null}
            </View>
          ))}
          {run.errors?.length ? run.errors.map((e: any, i: number) => <Text key={i} style={{ fontSize: 11.5, color: '#FF9500' }} {...tid(`matrix-skip-${i}`)}>Skipped {e.vin || 'a row'}: {e.error}</Text>) : null}
        </View>
      ) : null}

      {runs.length ? (
        <View style={{ gap: 6 }} {...tid('matrix-recent')}>
          <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.8 }}>PAST MATRIX RUNS</Text>
          {runs.map((r: any) => (
            <TouchableOpacity key={r.id} onPress={() => open(r.id)} style={{ borderRadius: 12, padding: 10, backgroundColor: colors.card, borderWidth: 1, borderColor: run?.id === r.id ? GOLD : colors.border }} {...tid(`matrix-past-${r.id}`)}>
              <Text style={{ fontSize: 13, fontWeight: '800', color: colors.text }}>{when(r.created_at)} · {r.plan?.vehicles ?? r.total} vehicles · {r.status}{r.summary?.both_answered != null ? ` · both answered on ${r.summary.both_answered}` : ''}{r.summary?.median_abs_gap != null ? ` · median gap ${money(r.summary.median_abs_gap)}` : ''}</Text>
              <Text style={{ fontSize: 11.5, color: colors.textSecondary }}>{r.by_name || 'admin'} · ZIP {r.zip} · {r.summary?.calls_total ?? r.plan?.total_calls ?? 0} paid calls</Text>
            </TouchableOpacity>
          ))}
        </View>
      ) : null}
    </View>
  );
};
