import React, { useEffect, useState } from 'react';
import { View, Text, Switch, ActivityIndicator, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../../services/api';
import { showConfirm } from '../../../services/alert';
import { useToast } from '../../common/Toast';
import { Field, GoldButton, Label } from '../../mystery-shops/shared';
import { Card, Eyebrow, Progress } from '../CcShell';
import { MorningBrief } from './MorningBrief';
import { GOLD, GREEN, RED, AMBER, detail, tid, type TeamUsage } from '../shared';

const KIND_LABEL: Record<string, string> = { lt_chat: 'Ask an Executive', lt_voice: 'Live voice turns', lt_select: 'Roundtable: room selection', lt_assess: 'Roundtable: assessments', lt_challenge: 'Roundtable: challenge round', lt_synth: 'Roundtable: synthesis', lt_review: 'Operating review' };

// CONTROLS: measured spend against the soft and hard limits, the emergency stop, and the audit trail. Costs come from provider token counts, never from guesses.
export const Controls = ({ colors, onChanged }: { colors: any; onChanged: () => void }) => {
  const { showToast } = useToast();
  const [u, setU] = useState<TeamUsage | null>(null);
  const [soft, setSoft] = useState('');
  const [hard, setHard] = useState('');
  const [busy, setBusy] = useState(false);
  const [audit, setAudit] = useState<any[]>([]);
  const [showAudit, setShowAudit] = useState(false);
  const load = async () => {
    try { const r = (await api.get('/command-center/team/usage')).data; setU(r); setSoft(String(r.controls.soft_usd)); setHard(String(r.controls.hard_usd)); } catch (e: any) { showToast(detail(e, 'Could not load'), 'error'); }
    try { setAudit((await api.get('/command-center/team/audit?limit=25')).data.entries); } catch {}
  };
  useEffect(() => { load(); }, []);
  const save = async (body: any, msg: string) => {
    setBusy(true);
    try { await api.put('/command-center/team/controls', body); showToast(msg); await load(); onChanged(); } catch (e: any) { showToast(detail(e, 'Could not save'), 'error'); } finally { setBusy(false); }
  };
  const stop = (v: boolean) => (v ? showConfirm('Emergency stop?', 'Every roundtable pauses within one step and no executive answers until you resume. Reading briefs and decisions keeps working.', () => save({ stopped: true }, 'Emergency stop is on'), undefined, 'Stop everything') : save({ stopped: false }, 'Resumed'));
  if (!u) return <ActivityIndicator color={GOLD} style={{ marginTop: 30 }} />;
  const pct = u.controls.hard_usd ? (100 * u.month_spend_usd) / u.controls.hard_usd : 0;
  const color = u.hard_reached ? RED : u.soft_warning ? AMBER : GREEN;
  return (
    <View style={{ gap: 16 }} {...tid('cc-controls')}>
      <Card colors={colors} accent={u.controls.stopped ? RED : color} testID="cc-budget-card">
        <Eyebrow t="THIS MONTH" colors={colors} right={<Text style={{ fontSize: 11.5, color: colors.textSecondary }}>{u.model}</Text>} />
        <View style={{ flexDirection: 'row', alignItems: 'flex-end', gap: 6 }}>
          <Text style={{ fontSize: 34, fontWeight: '900', color: colors.text, letterSpacing: -1 }} {...tid('cc-month-spend')}>${u.month_spend_usd.toFixed(2)}</Text>
          <Text style={{ fontSize: 13, color: colors.textSecondary, marginBottom: 6 }}>of ${u.controls.hard_usd.toFixed(0)} hard limit · soft warning at ${u.controls.soft_usd.toFixed(0)}</Text>
        </View>
        <Progress pct={pct} color={color} colors={colors} testID="cc-budget-progress" />
        {u.hard_reached && <Text style={{ fontSize: 13, color: RED, fontWeight: '700' }} {...tid('cc-budget-hard')}>Hard limit reached: no new AI work until you raise it.</Text>}
        {!u.hard_reached && u.soft_warning && <Text style={{ fontSize: 13, color: AMBER, fontWeight: '700' }} {...tid('cc-budget-soft')}>Past the soft warning. Everything still works; keep an eye on it.</Text>}
        <Text style={{ fontSize: 11.5, color: colors.textSecondary, lineHeight: 15 }}>{u.measured_note} This figure includes the Founder Advisor's own calls.</Text>
      </Card>
      <Card colors={colors} testID="cc-stop-card">
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
          <Ionicons name="hand-left" size={22} color={u.controls.stopped ? RED : colors.textSecondary} />
          <View style={{ flex: 1 }}><Text style={{ fontSize: 15, fontWeight: '800', color: colors.text }}>Emergency stop</Text><Text style={{ fontSize: 12.5, color: colors.textSecondary, lineHeight: 17 }}>{u.controls.stopped ? 'ON. Nothing runs. Flip it back to resume.' : 'Off. The team answers when asked.'}</Text></View>
          <Switch value={u.controls.stopped} onValueChange={stop} disabled={busy} trackColor={{ true: RED }} {...tid('cc-stop-switch')} />
        </View>
      </Card>
      <MorningBrief colors={colors} onChanged={onChanged} />
      <Card colors={colors} testID="cc-limits-card">
        <Eyebrow t="LIMITS" colors={colors} />
        <View style={{ flexDirection: 'row', gap: 10 }}>
          <View style={{ flex: 1 }}><Field label="SOFT WARNING (USD)" value={soft} onChange={setSoft} colors={colors} keyboardType="decimal-pad" testID="cc-limit-soft" /></View>
          <View style={{ flex: 1 }}><Field label="HARD LIMIT (USD)" value={hard} onChange={setHard} colors={colors} keyboardType="decimal-pad" testID="cc-limit-hard" /></View>
        </View>
        <GoldButton label="Save limits" icon="checkmark" busy={busy} disabled={isNaN(parseFloat(soft)) || isNaN(parseFloat(hard))} onPress={() => save({ soft_usd: parseFloat(soft), hard_usd: parseFloat(hard) }, 'Limits saved')} testID="cc-limits-save" />
        <Text style={{ fontSize: 11.5, color: colors.textSecondary }}>Up to {u.controls.max_participants} executives per roundtable · {u.controls.hourly_calls} model calls per hour.</Text>
      </Card>
      <Card colors={colors} testID="cc-usage-card">
        <Eyebrow t="LAST 30 DAYS · LEADERSHIP TEAM CALLS" colors={colors} />
        <Text style={{ fontSize: 13, color: colors.text }}>{u.last_30d.requests} calls · {u.last_30d.failures} failed · {(u.last_30d.prompt_tokens / 1000).toFixed(1)}k in / {(u.last_30d.completion_tokens / 1000).toFixed(1)}k out tokens · ${u.last_30d.approx_cost_usd.toFixed(2)}</Text>
        {Object.entries(u.last_30d.by_kind).sort((a, b) => b[1].approx_cost_usd - a[1].approx_cost_usd).map(([k, v]) => (
          <View key={k} style={{ flexDirection: 'row', justifyContent: 'space-between' }} {...tid(`cc-usage-${k}`)}>
            <Text style={{ fontSize: 12.5, color: colors.textSecondary }}>{KIND_LABEL[k] || k} · {v.n}</Text><Text style={{ fontSize: 12.5, fontWeight: '700', color: colors.text }}>${v.approx_cost_usd.toFixed(3)}</Text>
          </View>
        ))}
        {!Object.keys(u.last_30d.by_kind).length && <Text style={{ fontSize: 12.5, color: colors.textSecondary }}>No leadership-team calls yet.</Text>}
      </Card>
      <Card colors={colors} testID="cc-audit-card">
        <TouchableOpacity onPress={() => setShowAudit(v => !v)} style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }} {...tid('cc-audit-toggle')}>
          <Label t={`AUDIT TRAIL · ${audit.length} RECENT`} colors={colors} /><Ionicons name={showAudit ? 'chevron-up' : 'chevron-down'} size={16} color={colors.textSecondary} />
        </TouchableOpacity>
        {showAudit && audit.map(a => (
          <View key={a.id} style={{ gap: 1 }} {...tid(`cc-audit-${a.id}`)}>
            <Text style={{ fontSize: 12.5, fontWeight: '700', color: colors.text }}>{a.action.replace(/_/g, ' ')} · {a.subject?.kind} {String(a.subject?.id || '').slice(-6)}</Text>
            <Text style={{ fontSize: 11.5, color: colors.textSecondary }}>{a.actor?.name || a.actor?.kind} · {new Date(a.at).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}{a.reason ? ` · ${a.reason}` : ''}</Text>
          </View>
        ))}
      </Card>
    </View>
  );
};
