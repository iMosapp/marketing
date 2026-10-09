import React, { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../../services/api';
import { Pill } from '../CcShell';
import { GOLD, GREEN, RED, AMBER, DECISION_STATUS, RT_STATUS, tid, type Executive, type ExecMemory, type MemoryEntry } from '../shared';

const CONF: Record<string, string> = { high: GREEN, medium: AMBER, low: RED };
const plural = (n: number, w: string) => `${n} ${w}${n === 1 ? '' : 's'}`;

export const memoryLine = (m?: ExecMemory) => {
  if (!m || !m.roundtables) return 'No roundtables yet';
  const bits = [plural(m.roundtables, 'roundtable')];
  if (m.dissents) bits.push(`${m.open_dissents} open of ${plural(m.dissents, 'dissent')}`);
  if (m.approved) bits.push(`${m.approved} approved`);
  return bits.join(' · ');
};

// One line on the roster tile: how often this executive has been in the room and where they still disagree.
export const MemoryLine = ({ e, colors }: { e: Executive; colors: any }) => (
  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }} {...tid(`cc-exec-${e.key}-memory`)}>
    <Ionicons name="time-outline" size={13} color={colors.textSecondary} />
    <Text style={{ fontSize: 11.5, color: colors.textSecondary }} numberOfLines={1}>{memoryLine(e.memory)}</Text>
  </View>
);

const Stat = ({ n, label, color, colors, testID }: { n: number; label: string; color?: string; colors: any; testID: string }) => (
  <View style={{ flex: 1, alignItems: 'center', paddingVertical: 8, borderRadius: 10, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border }} {...tid(testID)}>
    <Text style={{ fontSize: 18, fontWeight: '900', color: color || colors.text }}>{n}</Text>
    <Text style={{ fontSize: 9.5, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.6 }} numberOfLines={1}>{label}</Text>
  </View>
);

const Entry = ({ en, colors, onOpen }: { en: MemoryEntry; colors: any; onOpen: () => void }) => {
  const ds = en.decision ? DECISION_STATUS[en.decision.status] : null;
  const st = RT_STATUS[en.status];
  const when = new Date(en.at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
  const meta = [when, en.devil_advocate ? "devil's advocate" : '', en.challenges_raised ? `raised ${plural(en.challenges_raised, 'material challenge')}` : '', en.challenged_on ? `challenged ${en.challenged_on}x` : ''].filter(Boolean).join(' · ');
  return (
    <TouchableOpacity onPress={onOpen} style={{ gap: 6, padding: 12, borderRadius: 12, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border }} {...tid(`cc-memory-${en.roundtable_id}`)}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
        <Text style={{ flex: 1, fontSize: 13.5, fontWeight: '800', color: colors.text }} numberOfLines={2}>{en.title}</Text>
        <Ionicons name="chevron-forward" size={14} color={colors.textSecondary} />
      </View>
      <Text style={{ fontSize: 11.5, color: colors.textSecondary }}>{meta}</Text>
      <Text style={{ fontSize: 13, color: colors.text, lineHeight: 18 }} numberOfLines={4} {...tid(`cc-memory-${en.roundtable_id}-position`)}>{en.position}</Text>
      {!!en.position_change && <Text style={{ fontSize: 12, color: AMBER, lineHeight: 16 }}>After the challenge round: {en.position_change}</Text>}
      {en.dissents.map(d => (
        <View key={d.id} style={{ flexDirection: 'row', gap: 6, alignItems: 'flex-start' }} {...tid(`cc-memory-${en.roundtable_id}-dissent-${d.id}`)}>
          <Ionicons name={d.resolved ? 'checkmark-circle' : 'alert-circle'} size={14} color={d.resolved ? GREEN : RED} style={{ marginTop: 2 }} />
          <Text style={{ flex: 1, fontSize: 12, color: colors.textSecondary, lineHeight: 16 }} numberOfLines={3}>{d.raised ? 'Dissented: ' : 'Challenged on: '}{d.issue}{d.resolved ? ' (resolved)' : ''}</Text>
        </View>
      ))}
      <View style={{ flexDirection: 'row', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
        <Pill text={`${en.confidence} confidence`} color={CONF[en.confidence] || RED} />
        {ds ? <Pill text={`You: ${ds.label}`} color={ds.color} testID={`cc-memory-${en.roundtable_id}-verdict`} /> : <Pill text={st?.label || en.status} color={st?.color || GOLD} />}
      </View>
    </TouchableOpacity>
  );
};

// MEMORY LANE: every roundtable this executive sat in, their recommendation, the dissents they raised or took, and how the founder decided. Built from the records; no model scores anything.
export const MemoryLane = ({ execKey, colors, onOpenRoundtable }: { execKey: string; colors: any; onOpenRoundtable: (id: string) => void }) => {
  const [data, setData] = useState<{ summary: ExecMemory; entries: MemoryEntry[] } | null | undefined>(undefined);
  useEffect(() => { setData(undefined); api.get(`/command-center/team/roster/${execKey}/history`).then(r => setData(r.data)).catch(() => setData(null)); }, [execKey]);
  if (data === undefined) return <ActivityIndicator color={GOLD} />;
  if (data === null) return <Text style={{ fontSize: 12.5, color: colors.textSecondary }} {...tid('cc-memory-error')}>Could not load the history.</Text>;
  const s = data.summary;
  if (!s.roundtables) return <Text style={{ fontSize: 13, color: colors.textSecondary, lineHeight: 18 }} {...tid('cc-memory-empty')}>Not in a roundtable yet. Convene one and this executive's positions, dissents and your verdicts will be kept here.</Text>;
  return (
    <View style={{ gap: 10 }} {...tid('cc-exec-sheet-memory')}>
      <View style={{ flexDirection: 'row', gap: 8 }}>
        <Stat n={s.roundtables} label="ROUNDTABLES" colors={colors} testID="cc-memory-stat-roundtables" />
        <Stat n={s.open_dissents} label="OPEN DISSENTS" color={s.open_dissents ? AMBER : undefined} colors={colors} testID="cc-memory-stat-dissents" />
        <Stat n={s.approved} label="APPROVED" color={s.approved ? GREEN : undefined} colors={colors} testID="cc-memory-stat-approved" />
        <Stat n={s.devil_advocate} label="DEVIL'S ADV." colors={colors} testID="cc-memory-stat-devil" />
      </View>
      {data.entries.map(en => <Entry key={en.roundtable_id} en={en} colors={colors} onOpen={() => onOpenRoundtable(en.roundtable_id)} />)}
      <Text style={{ fontSize: 11, color: colors.textSecondary, lineHeight: 15 }}>The position is the executive's own recommendation from the independent assessment; the verdict is yours. Nothing here is scored by a model.</Text>
    </View>
  );
};
