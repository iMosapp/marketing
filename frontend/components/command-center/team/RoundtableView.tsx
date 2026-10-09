import React, { useEffect, useRef, useState } from 'react';
import { View, Text, TouchableOpacity, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../../services/api';
import { showConfirm } from '../../../services/alert';
import { useToast } from '../../common/Toast';
import { GoldButton } from '../../mystery-shops/shared';
import { Card, Eyebrow, Pill } from '../CcShell';
import { Monogram } from './Roster';
import { RoundtableBrief } from './RoundtableBrief';
import { RoundtableDiscussion } from './RoundtableDiscussion';
import { GOLD, GREEN, RED, AMBER, RT_STATUS, STEP_LABEL, detail, tid, type Executive, type Roundtable } from '../shared';

type Props = { id: string; colors: any; execs: Executive[]; onBack: () => void; onChanged: () => void };
const STEPS = ['assessing', 'challenging', 'synthesizing'];

// ONE ROUNDTABLE: pick the room, start, watch the three steps, then read the brief and decide. Polls every 3 s while the room is in session.
export const RoundtableView = ({ id, colors, execs, onBack, onChanged }: Props) => {
  const { showToast } = useToast();
  const [rt, setRt] = useState<Roundtable | null>(null);
  const [busy, setBusy] = useState(false);
  const timer = useRef<any>(null);
  const load = async () => { try { const r = (await api.get(`/command-center/team/roundtables/${id}`)).data; setRt(r); return r as Roundtable; } catch (e: any) { showToast(detail(e, 'Could not load the roundtable'), 'error'); return null; } };
  useEffect(() => { load(); return () => clearInterval(timer.current); }, [id]);
  useEffect(() => {
    clearInterval(timer.current);
    if (rt?.status === 'running') timer.current = setInterval(async () => { const r = await load(); if (r && r.status !== 'running') { clearInterval(timer.current); onChanged(); } }, 3000);
    return () => clearInterval(timer.current);
  }, [rt?.status, id]);
  const act = async (path: string, body?: any, method: 'post' | 'put' = 'post') => {
    setBusy(true);
    try { setRt((await (api as any)[method](`/command-center/team/roundtables/${id}/${path}`, body || {})).data); onChanged(); }
    catch (e: any) { showToast(detail(e, 'That did not work'), 'error', 6000); }
    finally { setBusy(false); }
  };
  if (!rt) return <ActivityIndicator color={GOLD} style={{ marginTop: 40 }} />;
  const st = RT_STATUS[rt.status] || RT_STATUS.failed;
  const keys = rt.participants.map(p => p.key);
  const toggle = (k: string) => act('participants', { keys: keys.includes(k) ? keys.filter(x => x !== k) : [...keys, k] }, 'put');
  const start = () => showConfirm('Start the roundtable?', `${rt.participants.length} executives, about ${rt.estimate.calls} model calls, roughly $${rt.estimate.usd.toFixed(2)}. Actual cost is measured from token counts. Nothing in the Command Center changes.`, () => act('start'), undefined, 'Start');
  const cancel = () => showConfirm('Cancel this roundtable?', 'Finished assessments stay on record.', () => act('cancel'), undefined, 'Cancel it', 'Keep');
  const dot = (step: string, key: string) => {
    const res = step === 'assessing' ? rt.assessments[key] : step === 'challenging' ? rt.challenges[key] : null;
    if (step === 'synthesizing') return rt.steps.synthesizing?.status === 'done' ? GREEN : rt.step === 'synthesizing' && rt.status === 'running' ? GOLD : colors.border;
    return res?.status === 'ok' ? GREEN : res?.status === 'failed' ? RED : rt.step === step && rt.status === 'running' ? GOLD : colors.border;
  };
  return (
    <View style={{ gap: 16 }} {...tid('cc-rt-view')}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
        <TouchableOpacity onPress={onBack} style={{ padding: 6 }} {...tid('cc-rt-back')}><Ionicons name="chevron-back" size={22} color={colors.text} /></TouchableOpacity>
        <Text style={{ flex: 1, fontSize: 16, fontWeight: '800', color: colors.text }} numberOfLines={2} {...tid('cc-rt-title')}>{rt.title}</Text>
        <Pill text={st.label} color={st.color} icon={st.icon} testID="cc-rt-status" />
      </View>
      <Card colors={colors} testID="cc-rt-question">
        <Eyebrow t="THE QUESTION, AS THE CHIEF OF STAFF RESTATED IT" colors={colors} right={<Text style={{ fontSize: 11.5, color: colors.textSecondary }} {...tid('cc-rt-cost')}>${rt.cost_usd.toFixed(3)} so far</Text>} />
        <Text style={{ fontSize: 15, fontWeight: '700', color: colors.text, lineHeight: 21 }}>{rt.restated}</Text>
        <Text style={{ fontSize: 12.5, color: colors.textSecondary, lineHeight: 17 }}>Your words: {rt.question}</Text>
        {!!rt.clarifying_question && <Text style={{ fontSize: 13, color: AMBER, lineHeight: 18 }} {...tid('cc-rt-clarify')}>Chief of Staff asks: {rt.clarifying_question}</Text>}
      </Card>
      <Card colors={colors} testID="cc-rt-room">
        <Eyebrow t={rt.status === 'selected' ? 'THE ROOM · TAP TO ADD OR REMOVE' : 'THE ROOM'} colors={colors} />
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
          {execs.filter(e => !e.is_orchestrator && e.enabled && (rt.status === 'selected' || keys.includes(e.key))).map(e => {
            const p = rt.participants.find(x => x.key === e.key);
            return (
              <TouchableOpacity key={e.key} disabled={rt.status !== 'selected' || e.key === 'strategic_advisor' || busy} onPress={() => toggle(e.key)} style={{ flexDirection: 'row', alignItems: 'center', gap: 8, padding: 6, paddingRight: 12, borderRadius: 20, backgroundColor: p ? e.color + '1F' : colors.bg, borderWidth: 1.5, borderColor: p ? e.color : colors.border, opacity: p ? 1 : 0.6 }} {...tid(`cc-rt-seat-${e.key}`)}>
                <Monogram e={e} size={30} />
                <View><Text style={{ fontSize: 13, fontWeight: '800', color: colors.text }}>{e.short}{p?.devil_advocate ? " · devil's advocate" : ''}</Text>{!!p?.why && <Text style={{ fontSize: 11, color: colors.textSecondary }} numberOfLines={1}>{p.why}</Text>}</View>
                {rt.status === 'selected' && e.key !== 'strategic_advisor' && <Ionicons name={p ? 'close-circle' : 'add-circle'} size={16} color={colors.textSecondary} />}
              </TouchableOpacity>
            );
          })}
        </View>
        {rt.participants.some(p => p.devil_advocate) && <Text style={{ fontSize: 11.5, color: colors.textSecondary, lineHeight: 15 }}>The devil's advocate is assigned by the Chief of Staff to argue the strongest case against the likely majority; their own position is still recorded.</Text>}
        {rt.status === 'selected' && (
          <View style={{ gap: 8 }}>
            <GoldButton label={`Start the roundtable · about $${rt.estimate.usd.toFixed(2)}`} icon="play" onPress={start} busy={busy} testID="cc-rt-start" />
            <TouchableOpacity onPress={cancel} style={{ alignSelf: 'center', padding: 6 }} {...tid('cc-rt-cancel')}><Text style={{ fontSize: 12.5, color: colors.textSecondary }}>Cancel</Text></TouchableOpacity>
          </View>
        )}
      </Card>
      {rt.status !== 'selected' && (
        <Card colors={colors} testID="cc-rt-steps">
          <Eyebrow t="THE SESSION" colors={colors} />
          {STEPS.map(s => (
            <View key={s} style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }} {...tid(`cc-rt-step-${s}`)}>
              <Ionicons name={rt.steps[s]?.status === 'done' ? 'checkmark-circle' : rt.step === s && rt.status === 'running' ? 'sync' : 'ellipse-outline'} size={18} color={rt.steps[s]?.status === 'done' ? GREEN : rt.step === s && rt.status === 'running' ? GOLD : colors.textSecondary} />
              <Text style={{ flex: 1, fontSize: 13.5, fontWeight: '700', color: colors.text }}>{STEP_LABEL[s]}</Text>
              <View style={{ flexDirection: 'row', gap: 4 }}>{(s === 'synthesizing' ? ['chief_of_staff'] : keys).map(k => <View key={k} style={{ width: 10, height: 10, borderRadius: 5, backgroundColor: dot(s, k) }} />)}</View>
            </View>
          ))}
          {rt.status === 'running' && <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }} {...tid('cc-rt-running')}><ActivityIndicator color={GOLD} size="small" /><Text style={{ fontSize: 12.5, color: colors.textSecondary }}>In session. Each step runs the executives in parallel; the whole thing usually takes 1 to 4 minutes. You can leave and come back.</Text></View>}
          {!!rt.error && rt.status !== 'running' && <Text style={{ fontSize: 13, color: RED, lineHeight: 18 }} {...tid('cc-rt-error')}>{rt.error}</Text>}
          {['failed', 'paused', 'interrupted'].includes(rt.status) && <GoldButton label="Resume from this step" icon="refresh" onPress={() => act('resume')} busy={busy} testID="cc-rt-resume" />}
          {['running', 'failed', 'paused', 'interrupted'].includes(rt.status) && <TouchableOpacity onPress={cancel} style={{ alignSelf: 'center', padding: 6 }} {...tid('cc-rt-cancel')}><Text style={{ fontSize: 12.5, color: colors.textSecondary }}>Cancel the roundtable</Text></TouchableOpacity>}
        </Card>
      )}
      {rt.brief && <RoundtableBrief rt={rt} execs={execs} colors={colors} onDecided={async () => { await load(); onChanged(); }} />}
      {rt.status !== 'selected' && <RoundtableDiscussion rt={rt} execs={execs} colors={colors} />}
    </View>
  );
};
