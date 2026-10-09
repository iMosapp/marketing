import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { Field } from '../mystery-shops/shared';
import { GOLD, RED, VERDICT, detail, tid, type Evaluation } from './shared';

const when = (iso: string) => new Date(iso).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
const Dots = ({ n }: { n: number | null }) => <View style={{ flexDirection: 'row', gap: 3 }}>{[1, 2, 3, 4, 5].map(i => <View key={i} style={{ width: 9, height: 9, borderRadius: 4.5, backgroundColor: n && i <= n ? (n >= 4 ? '#34C759' : n >= 3 ? '#FF9500' : '#FF3B30') : '#8E8E9333' }} />)}</View>;
const Lines = ({ t, items, colors, color }: { t: string; items: string[]; colors: any; color?: string }) => (items?.length ? (
  <View style={{ gap: 3 }}><Text style={{ fontSize: 11, fontWeight: '800', color: color || colors.textSecondary, letterSpacing: 0.8 }}>{t}</Text>{items.map((x, i) => <Text key={i} style={{ fontSize: 13, color: colors.text, lineHeight: 18 }}>• {x}</Text>)}</View>
) : null);

const EvaluationView = ({ e, colors, onDisagree }: { e: Evaluation; colors: any; onDisagree: (reason: string) => Promise<void> }) => {
  const v = VERDICT[e.recommendation] || VERDICT.PARK;
  const [reason, setReason] = useState('');
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  return (
    <View style={{ gap: 12, borderRadius: 16, borderWidth: 1.5, borderColor: v.color, backgroundColor: v.color + '12', padding: 12 }} {...tid(`cc-eval-${e.id}`)}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
        <View style={{ paddingHorizontal: 10, height: 26, borderRadius: 13, backgroundColor: v.color, alignItems: 'center', justifyContent: 'center' }} {...tid('cc-eval-verdict')}><Text style={{ fontSize: 12, fontWeight: '800', color: '#1C1C1E' }}>{v.label.toUpperCase()}</Text></View>
        <Text style={{ flex: 1, fontSize: 11.5, color: colors.textSecondary }}>{when(e.created_at)} · {e.model}</Text>
      </View>
      <Text style={{ fontSize: 14, color: colors.text, lineHeight: 20 }} {...tid('cc-eval-rationale')}>{e.rationale}</Text>
      <View style={{ gap: 8 }}>
        {Object.entries(e.scores || {}).map(([k, s]) => (
          <View key={k} style={{ gap: 2 }} {...tid(`cc-eval-dim-${k}`)}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}><Text style={{ flex: 1, fontSize: 12.5, fontWeight: '800', color: colors.text }}>{s.label}</Text><Dots n={s.score} /><Text style={{ width: 22, fontSize: 12.5, fontWeight: '800', color: colors.textSecondary, textAlign: 'right' }}>{s.score ?? '?'}</Text></View>
            {!!s.why && <Text style={{ fontSize: 12, color: colors.textSecondary, lineHeight: 16 }}>{s.why}</Text>}
          </View>
        ))}
      </View>
      <Lines t="DEAL-BREAKERS" items={e.deal_breakers} colors={colors} color={RED} />
      <Lines t="DEPENDENCIES" items={e.dependencies} colors={colors} />
      <Lines t="UNCERTAIN" items={e.uncertainty} colors={colors} />
      {e.experiment && (e.experiment.what || e.experiment.success_signal) ? (
        <View style={{ gap: 3 }} {...tid('cc-eval-experiment')}><Text style={{ fontSize: 11, fontWeight: '800', color: '#FF9500', letterSpacing: 0.8 }}>VALIDATION EXPERIMENT</Text>
          <Text style={{ fontSize: 13, color: colors.text, lineHeight: 18 }}>{e.experiment.what}{e.experiment.with_whom ? ` · with ${e.experiment.with_whom}` : ''}</Text>
          {!!e.experiment.success_signal && <Text style={{ fontSize: 12.5, color: colors.textSecondary }}>Success looks like: {e.experiment.success_signal}{e.experiment.time_box ? ` · ${e.experiment.time_box}` : ''}</Text>}</View>
      ) : null}
      {!!e.advances && <Text style={{ fontSize: 13, color: colors.text }} {...tid('cc-eval-advances')}><Text style={{ fontWeight: '800' }}>Advances: </Text>{e.advances}{e.displaces ? `\nDisplaces: ${e.displaces}` : ''}</Text>}
      <Lines t="MISSING INFORMATION" items={e.missing_info} colors={colors} />
      {e.disagreement ? (
        <View style={{ flexDirection: 'row', gap: 6, alignItems: 'flex-start' }} {...tid('cc-eval-disagreement')}><Ionicons name="chatbox-ellipses" size={14} color={GOLD} style={{ marginTop: 2 }} /><Text style={{ flex: 1, fontSize: 12.5, color: colors.text, lineHeight: 17 }}>You disagreed ({when(e.disagreement.at)}): {e.disagreement.reason}</Text></View>
      ) : open ? (
        <View style={{ gap: 8 }}>
          <Field label="WHY YOU DISAGREE" value={reason} onChange={setReason} colors={colors} multiline testID="cc-eval-disagree-reason" />
          <TouchableOpacity disabled={!reason.trim() || busy} onPress={async () => { setBusy(true); try { await onDisagree(reason.trim()); setOpen(false); } finally { setBusy(false); } }} style={{ alignSelf: 'flex-start', paddingHorizontal: 14, height: 32, borderRadius: 16, backgroundColor: reason.trim() ? GOLD : colors.border, alignItems: 'center', justifyContent: 'center' }} {...tid('cc-eval-disagree-save')}><Text style={{ fontSize: 12.5, fontWeight: '800', color: '#1C1C1E' }}>Record my view</Text></TouchableOpacity>
        </View>
      ) : (
        <TouchableOpacity onPress={() => setOpen(true)} style={{ alignSelf: 'flex-start' }} {...tid('cc-eval-disagree')}><Text style={{ fontSize: 12.5, fontWeight: '800', color: GOLD }}>I disagree</Text></TouchableOpacity>
      )}
    </View>
  );
};

// Inside the idea sheet: ask for an independent read, see the latest verdict, keep every earlier one. The idea's status never changes from here.
export const EvaluationPanel = ({ ideaId, colors, showToast }: { ideaId: string; colors: any; showToast: (m: string, t?: any, d?: number) => void }) => {
  const [rows, setRows] = useState<Evaluation[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [showAll, setShowAll] = useState(false);
  const load = useCallback(async () => { try { setRows((await api.get(`/command-center/ideas/${ideaId}/evaluations`)).data.evaluations); } catch { setRows([]); } }, [ideaId]);
  useEffect(() => { load(); }, [load]);
  const evaluate = async () => {
    setBusy(true);
    try { await api.post(`/command-center/ideas/${ideaId}/evaluate`, {}, { timeout: 100000 }); showToast('Evaluation saved'); await load(); }
    catch (e: any) { showToast(detail(e, 'The advisor could not evaluate this idea'), 'error', 6000); }
    finally { setBusy(false); }
  };
  const disagree = (e: Evaluation) => async (reason: string) => { await api.post(`/command-center/advisor/evaluations/${e.id}/disagree`, { reason }); showToast('Your view is on record'); load(); };
  const latest = rows?.[0];
  return (
    <View style={{ gap: 10 }} {...tid('cc-eval-panel')}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
        <Text style={{ flex: 1, fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 1 }}>ADVISOR EVALUATION{rows?.length ? ` · ${rows.length}` : ''}</Text>
        <TouchableOpacity onPress={evaluate} disabled={busy} style={{ flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 12, height: 32, borderRadius: 16, backgroundColor: GOLD, opacity: busy ? 0.6 : 1 }} {...tid('cc-idea-evaluate')}>
          {busy ? <ActivityIndicator color="#1C1C1E" size="small" /> : <Ionicons name="sparkles" size={14} color="#1C1C1E" />}
          <Text style={{ fontSize: 12.5, fontWeight: '800', color: '#1C1C1E' }}>{busy ? 'Evaluating' : latest ? 'Evaluate again' : 'Evaluate with Advisor'}</Text>
        </TouchableOpacity>
      </View>
      {busy && <Text style={{ fontSize: 12, color: colors.textSecondary }} {...tid('cc-eval-busy')}>Scoring six dimensions against the live strategy. 15 to 40 seconds.</Text>}
      {rows === null ? <ActivityIndicator color={GOLD} /> : !rows.length ? <Text style={{ fontSize: 12.5, color: colors.textSecondary }} {...tid('cc-eval-none')}>Not evaluated yet. The advisor scores alignment, revenue, priority impact, evidence, effort and distraction, then recommends build, validate, park or reject. Nothing changes without you.</Text> : (
        <>
          <EvaluationView e={latest!} colors={colors} onDisagree={disagree(latest!)} />
          {rows.length > 1 && (
            <TouchableOpacity onPress={() => setShowAll(v => !v)} style={{ alignSelf: 'flex-start' }} {...tid('cc-eval-history-toggle')}><Text style={{ fontSize: 12.5, fontWeight: '800', color: GOLD }}>{showAll ? 'Hide' : 'Show'} {rows.length - 1} earlier evaluation{rows.length > 2 ? 's' : ''}</Text></TouchableOpacity>
          )}
          {showAll && rows.slice(1).map(e => <EvaluationView key={e.id} e={e} colors={colors} onDisagree={disagree(e)} />)}
        </>
      )}
    </View>
  );
};
