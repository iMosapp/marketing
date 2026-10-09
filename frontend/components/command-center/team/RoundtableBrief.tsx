import React, { useState } from 'react';
import { View, Text, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../../services/api';
import { useToast } from '../../common/Toast';
import { Field, GoldButton, Label } from '../../mystery-shops/shared';
import { Card, Eyebrow, Pill } from '../CcShell';
import { Bullets, Monogram } from './Roster';
import { GOLD, GREEN, RED, AMBER, PURPLE, DECISION_STATUS, detail, tid, execColor, execShort, type Executive, type Roundtable, type Dissent } from '../shared';

type Props = { rt: Roundtable; execs: Executive[]; colors: any; onDecided: () => void };
const ACTIONS = [['approve', 'Approve', GREEN, 'checkmark-circle'], ['modify', 'Modify', AMBER, 'create'], ['defer', 'Defer', PURPLE, 'time'], ['reject', 'Reject', RED, 'close-circle']] as const;

const Para = ({ t, label, colors, testID }: { t?: string; label: string; colors: any; testID?: string }) => (t ? <View style={{ gap: 4 }} {...tid(testID || `cc-brief-${label.toLowerCase()}`)}><Label t={label} colors={colors} /><Text style={{ fontSize: 13.5, color: colors.text, lineHeight: 19 }} selectable>{t}</Text></View> : null);

const DissentCard = ({ d, execs, colors }: { d: Dissent; execs: Executive[]; colors: any }) => (
  <View style={{ borderRadius: 14, borderWidth: 1, borderColor: d.resolved ? colors.border : RED + '88', backgroundColor: d.resolved ? colors.bg : RED + '0D', padding: 12, gap: 8 }} {...tid(`cc-dissent-${d.id}`)}>
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
      <Ionicons name={d.resolved ? 'checkmark-done' : 'flash'} size={14} color={d.resolved ? GREEN : RED} />
      <Text style={{ flex: 1, fontSize: 13.5, fontWeight: '800', color: colors.text }}>{d.issue}</Text>
      <Pill text={d.resolved ? 'Resolved in discussion' : 'Needs you'} color={d.resolved ? GREEN : RED} />
    </View>
    {d.positions.map((p, i) => (
      <View key={i} style={{ flexDirection: 'row', gap: 8, alignItems: 'flex-start' }}>
        <Monogram e={{ short: execShort(execs, p.key), color: execColor(execs, p.key) }} size={26} />
        <Text style={{ flex: 1, fontSize: 13, color: colors.text, lineHeight: 18 }}>{p.position}</Text>
      </View>
    ))}
    {!!d.evidence && <Text style={{ fontSize: 12.5, color: colors.textSecondary, lineHeight: 17 }}>Evidence: {d.evidence}</Text>}
    {!!d.consequences && <Text style={{ fontSize: 12.5, color: colors.textSecondary, lineHeight: 17 }}>If wrong: {d.consequences}</Text>}
    {!!d.how && <Text style={{ fontSize: 12.5, color: colors.textSecondary, lineHeight: 17, fontStyle: 'italic' }}>{d.how}</Text>}
    {d.raised_by_devil_advocate && <Text style={{ fontSize: 11, color: AMBER }}>Raised under the devil's advocate duty</Text>}
  </View>
);

// THE DECISION BRIEF: the Advisor's view first, every material disagreement preserved, and the four buttons that are yours alone.
export const RoundtableBrief = ({ rt, execs, colors, onDecided }: Props) => {
  const { showToast } = useToast();
  const b = rt.brief!;
  const d = rt.decision;
  const [action, setAction] = useState<string | null>(null);
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const [more, setMore] = useState(false);
  const deptViews = [...b.department_recommendations].sort((x, y) => (x.key === 'strategic_advisor' ? -1 : y.key === 'strategic_advisor' ? 1 : 0));
  const open = d && (d.status === 'pending' || d.status === 'deferred');
  const decide = async () => {
    if (!d || !action) return;
    if (action === 'modify' && !reason.trim()) { showToast('Say what should change', 'error'); return; }
    setBusy(true);
    try { await api.post(`/command-center/team/decisions/${d.id}`, { action, reason: reason.trim() }); showToast(action === 'modify' ? 'The Chief of Staff is re-synthesizing with your changes' : `Decision recorded: ${action}`); setAction(null); setReason(''); onDecided(); }
    catch (e: any) { showToast(detail(e, 'Could not record the decision'), 'error', 6000); } finally { setBusy(false); }
  };
  return (
    <Card colors={colors} accent={GOLD} testID="cc-brief">
      <Eyebrow t="DECISION BRIEF · CHIEF OF STAFF" colors={colors} right={d ? <Pill text={DECISION_STATUS[d.status]?.label || d.status} color={DECISION_STATUS[d.status]?.color || GOLD} testID="cc-decision-status" /> : undefined} />
      <Text style={{ fontSize: 17, fontWeight: '800', color: colors.text, lineHeight: 23 }}>{b.title}</Text>
      <Para t={b.opportunity} label="THE OPPORTUNITY" colors={colors} />
      <View style={{ borderRadius: 14, backgroundColor: GOLD + '1A', borderWidth: 1, borderColor: GOLD, padding: 12, gap: 4 }} {...tid('cc-brief-recommendation')}>
        <Label t="RECOMMENDED DECISION" colors={colors} /><Text style={{ fontSize: 15, fontWeight: '700', color: colors.text, lineHeight: 21 }} selectable>{b.recommended_decision}</Text>
      </View>
      <Para t={b.alignment} label="STRATEGIC ALIGNMENT" colors={colors} />
      <View style={{ gap: 8 }} {...tid('cc-brief-departments')}>
        <Label t="EACH EXECUTIVE'S VIEW" colors={colors} />
        {deptViews.map((v, i) => (
          <View key={i} style={{ flexDirection: 'row', gap: 10, alignItems: 'flex-start' }} {...tid(`cc-brief-view-${v.key}`)}>
            <Monogram e={{ short: execShort(execs, v.key), color: execColor(execs, v.key) }} size={30} />
            <Text style={{ flex: 1, fontSize: 13.5, color: colors.text, lineHeight: 19 }} selectable>{v.summary}</Text>
          </View>
        ))}
      </View>
      <View style={{ gap: 8 }} {...tid('cc-dissent-register')}>
        <Label t={`DISSENT REGISTER · ${rt.dissent.filter(x => !x.resolved).length} UNRESOLVED`} colors={colors} />
        {!rt.dissent.length && <Text style={{ fontSize: 13, color: colors.textSecondary, lineHeight: 18 }}>No material disagreement was raised. Treat that with suspicion: either the question was easy or the room was too polite.</Text>}
        {rt.dissent.map(x => <DissentCard key={x.id} d={x} execs={execs} colors={colors} />)}
        {!!b.disagreements && <Text style={{ fontSize: 13, color: colors.text, lineHeight: 18 }} selectable>{b.disagreements}</Text>}
      </View>
      {!!b.unassessed.length && <View style={{ gap: 4 }} {...tid('cc-brief-unassessed')}><Label t="UNASSESSED" colors={colors} /><Bullets items={b.unassessed} colors={colors} /></View>}
      {!!rt.unsupported.length && (
        <View style={{ gap: 4, borderRadius: 12, borderWidth: 1, borderColor: AMBER, padding: 10 }} {...tid('cc-brief-unsupported')}>
          <Label t="CLAIMS LABELLED FACT WITHOUT A SOURCE" colors={colors} />
          {rt.unsupported.map((u, i) => <Text key={i} style={{ fontSize: 12.5, color: colors.text, lineHeight: 17 }}>{execShort(execs, u.agent_key)}: {u.claim}</Text>)}
        </View>
      )}
      <TouchableOpacity onPress={() => setMore(v => !v)} style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }} {...tid('cc-brief-more')}>
        <Ionicons name={more ? 'chevron-up' : 'chevron-down'} size={16} color={GOLD} /><Text style={{ fontSize: 13, fontWeight: '800', color: GOLD }}>{more ? 'Hide' : 'Show'} technical, financial, operational and commercial detail</Text>
      </TouchableOpacity>
      {more && (
        <View style={{ gap: 12 }} {...tid('cc-brief-detail')}>
          <Para t={b.technical} label="TECHNICAL" colors={colors} /><Para t={b.financial} label="FINANCIAL" colors={colors} /><Para t={b.operational} label="OPERATIONAL" colors={colors} /><Para t={b.commercial} label="COMMERCIAL" colors={colors} />
          {!!b.agreements.length && <View style={{ gap: 4 }}><Label t="WHERE THE ROOM AGREES" colors={colors} /><Bullets items={b.agreements} colors={colors} /></View>}
          {!!b.dependencies.length && <View style={{ gap: 4 }}><Label t="DEPENDENCIES" colors={colors} /><Bullets items={b.dependencies} colors={colors} /></View>}
          {!!b.risks.length && <View style={{ gap: 4 }}><Label t="RISKS" colors={colors} /><Bullets items={b.risks} colors={colors} /></View>}
          {!!b.missing.length && <View style={{ gap: 4 }}><Label t="WHAT THE COMPANY HAS NOT RECORDED" colors={colors} /><Bullets items={b.missing} colors={colors} /></View>}
        </View>
      )}
      {!!b.next_actions.length && (
        <View style={{ gap: 6 }} {...tid('cc-brief-next')}>
          <Label t="PROPOSED NEXT ACTIONS · NOTHING IS ASSIGNED UNTIL YOU SAY SO" colors={colors} />
          {b.next_actions.map((a, i) => (
            <View key={i} style={{ flexDirection: 'row', gap: 8, alignItems: 'flex-start' }}>
              <Pill text={execShort(execs, a.owner_key)} color={a.owner_key === 'founder' ? GOLD : execColor(execs, a.owner_key)} />
              <View style={{ flex: 1 }}><Text style={{ fontSize: 13.5, color: colors.text, lineHeight: 19 }}>{a.action}</Text>{!!a.why && <Text style={{ fontSize: 12, color: colors.textSecondary }}>{a.why}</Text>}</View>
            </View>
          ))}
        </View>
      )}
      {!!b.decisions_required.length && (
        <View style={{ gap: 6 }} {...tid('cc-brief-decisions')}>
          <Label t="DECISIONS ONLY YOU CAN MAKE" colors={colors} />
          {b.decisions_required.map((x, i) => <View key={i}><Text style={{ fontSize: 13.5, fontWeight: '700', color: colors.text }}>{x.title}</Text><Text style={{ fontSize: 12.5, color: colors.textSecondary, lineHeight: 17 }}>{x.detail}</Text></View>)}
        </View>
      )}
      {d && !open && d.founder && (
        <View style={{ borderRadius: 12, padding: 12, backgroundColor: (DECISION_STATUS[d.status]?.color || GOLD) + '1A', gap: 2 }} {...tid('cc-decision-verdict')}>
          <Text style={{ fontSize: 13.5, fontWeight: '800', color: colors.text }}>You {d.founder.action === 'modify' ? 'asked for changes' : `${d.founder.action}d`} on {new Date(d.founder.at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}</Text>
          {!!d.founder.reason && <Text style={{ fontSize: 13, color: colors.text, lineHeight: 18 }}>{d.founder.reason}</Text>}
        </View>
      )}
      {open && (
        <View style={{ gap: 10 }} {...tid('cc-decision-bar')}>
          <Label t="YOUR DECISION" colors={colors} />
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
            {ACTIONS.filter(([k]) => !(k === 'modify' && rt.modify_count >= 1)).map(([k, label, color, icon]) => (
              <TouchableOpacity key={k} onPress={() => setAction(k)} style={{ flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 14, height: 38, borderRadius: 19, backgroundColor: action === k ? color : color + '1A', borderWidth: 1, borderColor: color }} {...tid(`cc-decide-${k}`)}>
                <Ionicons name={icon as any} size={15} color={action === k ? '#111' : color} /><Text style={{ fontSize: 13, fontWeight: '800', color: action === k ? '#111' : color }}>{label}</Text>
              </TouchableOpacity>
            ))}
          </View>
          {action && (
            <View style={{ gap: 8 }}>
              <Field label={action === 'modify' ? 'WHAT SHOULD CHANGE (THE CHIEF OF STAFF RE-SYNTHESIZES ONCE)' : 'YOUR REASON (OPTIONAL, GOES ON RECORD)'} value={reason} onChange={setReason} colors={colors} multiline testID="cc-decide-reason" />
              <GoldButton label={`Confirm: ${action}`} onPress={decide} busy={busy} color={ACTIONS.find(a => a[0] === action)?.[2]} testID="cc-decide-confirm" />
            </View>
          )}
        </View>
      )}
    </Card>
  );
};
