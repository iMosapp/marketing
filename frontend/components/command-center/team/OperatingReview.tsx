import React, { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../../services/api';
import { useToast } from '../../common/Toast';
import { Label } from '../../mystery-shops/shared';
import { Card, Eyebrow, Pill } from '../CcShell';
import { Bullets } from './Roster';
import { hourLabel } from './MorningBrief';
import { GOLD, detail, tid, execColor, execShort, type Executive, type OperatingReview as Review } from '../shared';

type Props = { colors: any; execs: Executive[]; morning?: { enabled: boolean; hour: number }; onOpenControls?: () => void };

// OPERATING REVIEW (Mode D lite): one Chief of Staff call over the live Command Center, pending decisions and readiness gaps. On demand, or pushed every morning when the brief is on.
export const OperatingReview = ({ colors, execs, morning, onOpenControls }: Props) => {
  const { showToast } = useToast();
  const [r, setR] = useState<Review | null | undefined>(undefined);
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState(false);
  useEffect(() => { api.get('/command-center/team/review').then(x => setR(x.data.review)).catch(() => setR(null)); }, []);
  const run = async () => {
    setBusy(true);
    try { setR((await api.post('/command-center/team/review', {}, { timeout: 120000 })).data.review); setOpen(true); } catch (e: any) { showToast(detail(e, 'The Chief of Staff could not write the review'), 'error', 6000); } finally { setBusy(false); }
  };
  const when = r?.generated_at ? new Date(r.generated_at).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }) : '';
  return (
    <Card colors={colors} accent={GOLD} testID="cc-review">
      <Eyebrow t="EXECUTIVE OPERATING REVIEW" colors={colors} right={
        busy ? <ActivityIndicator color={GOLD} size="small" /> : (
          <TouchableOpacity onPress={run} style={{ flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 10, height: 28, borderRadius: 14, backgroundColor: GOLD }} {...tid('cc-review-run')}><Ionicons name="sparkles" size={13} color="#1C1C1E" /><Text style={{ fontSize: 12, fontWeight: '800', color: '#1C1C1E' }}>{r ? 'Refresh' : 'Run it'}</Text></TouchableOpacity>
        )} />
      {r === undefined && <ActivityIndicator color={GOLD} />}
      {r === null && <Text style={{ fontSize: 13, color: colors.textSecondary, lineHeight: 18 }}>The Chief of Staff reads the Command Center, pending decisions and each executive's knowledge gaps, then tells you what changed, what needs you and what to do next. One model call.</Text>}
      {r && (
        <View style={{ gap: 10 }}>
          <TouchableOpacity onPress={() => setOpen(v => !v)} {...tid('cc-review-toggle')}>
            <Text style={{ fontSize: 15, fontWeight: '700', color: colors.text, lineHeight: 21 }}>{r.headline}</Text>
            <Text style={{ fontSize: 11.5, color: colors.textSecondary, marginTop: 4 }}>{when} · tap to {open ? 'collapse' : 'expand'}</Text>
          </TouchableOpacity>
          {open && (
            <View style={{ gap: 10 }} {...tid('cc-review-body')}>
              {!!r.one_big_thing && <View style={{ gap: 4 }}><Label t="ONE BIG THING" colors={colors} /><Text style={{ fontSize: 13.5, color: colors.text, lineHeight: 19 }}>{r.one_big_thing}</Text></View>}
              {!!r.priorities.length && <View style={{ gap: 4 }}><Label t="PRIORITIES" colors={colors} /><Bullets items={r.priorities} colors={colors} /></View>}
              {!!r.roadmap && <View style={{ gap: 4 }}><Label t="ROADMAP" colors={colors} /><Text style={{ fontSize: 13.5, color: colors.text, lineHeight: 19 }}>{r.roadmap}</Text></View>}
              {!!r.pending_decisions.length && <View style={{ gap: 4 }}><Label t="WAITING ON YOU" colors={colors} /><Bullets items={r.pending_decisions} colors={colors} /></View>}
              {!!r.risks.length && <View style={{ gap: 4 }}><Label t="RISKS" colors={colors} /><Bullets items={r.risks} colors={colors} /></View>}
              {!!r.wins.length && <View style={{ gap: 4 }}><Label t="WINS" colors={colors} /><Bullets items={r.wins} colors={colors} /></View>}
              {!!r.next_actions.length && (
                <View style={{ gap: 6 }}><Label t="RECOMMENDED NEXT ACTIONS" colors={colors} />
                  {r.next_actions.map((a, i) => <View key={i} style={{ flexDirection: 'row', gap: 8, alignItems: 'flex-start' }}><Pill text={execShort(execs, a.owner_key)} color={a.owner_key === 'founder' ? GOLD : execColor(execs, a.owner_key)} /><Text style={{ flex: 1, fontSize: 13.5, color: colors.text, lineHeight: 19 }}>{a.action}{a.why ? ` (${a.why})` : ''}</Text></View>)}
                </View>
              )}
              {!!r.missing_knowledge.length && <View style={{ gap: 4 }}><Label t="WHAT THE TEAM STILL DOES NOT KNOW" colors={colors} /><Bullets items={r.missing_knowledge} colors={colors} /></View>}
              {!!r.readiness_gaps.length && <View style={{ gap: 4 }}><Label t="READINESS GAPS" colors={colors} /><Bullets items={r.readiness_gaps} colors={colors} /></View>}
            </View>
          )}
        </View>
      )}
      {!!morning && (
        <TouchableOpacity onPress={onOpenControls} style={{ flexDirection: 'row', alignItems: 'center', gap: 6, flexWrap: 'wrap' }} {...tid('cc-review-morning')}>
          <Ionicons name="sunny" size={13} color={morning.enabled ? GOLD : colors.textSecondary} />
          <Text style={{ fontSize: 11.5, color: colors.textSecondary }}>{morning.enabled ? `Pushed to your phone every morning at ${hourLabel(morning.hour)}.` : 'Want this on your phone every morning?'}</Text>
          <Text style={{ fontSize: 11.5, fontWeight: '800', color: GOLD }}>{morning.enabled ? 'Change' : 'Set it up'}</Text>
        </TouchableOpacity>
      )}
    </Card>
  );
};
