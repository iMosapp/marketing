import React, { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../../services/api';
import { useToast } from '../../common/Toast';
import { Eyebrow, Empty, Pill } from '../CcShell';
import { GOLD, DECISION_STATUS, detail, tid, type Decision } from '../shared';

// DECISION RECORDS: every brief the team produced and what the founder did with it. Permanent, read-only here; decisions are made on the brief itself.
export const Decisions = ({ colors, onOpen }: { colors: any; onOpen: (roundtableId: string) => void }) => {
  const { showToast } = useToast();
  const [rows, setRows] = useState<Decision[] | null>(null);
  useEffect(() => { api.get('/command-center/team/decisions').then(r => setRows(r.data.decisions)).catch((e: any) => showToast(detail(e, 'Could not load'), 'error')); }, []);
  const pending = (rows || []).filter(d => d.status === 'pending' || d.status === 'deferred');
  const made = (rows || []).filter(d => !pending.includes(d));
  const Row = ({ d }: { d: Decision }) => (
    <TouchableOpacity onPress={() => onOpen(d.roundtable_id)} style={{ padding: 14, borderRadius: 16, backgroundColor: colors.card, borderWidth: 1, borderColor: d.status === 'pending' ? GOLD : colors.border, gap: 6 }} {...tid(`cc-decision-${d.id}`)}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
        <Text style={{ flex: 1, fontSize: 14.5, fontWeight: '800', color: colors.text }} numberOfLines={2}>{d.title}</Text>
        <Pill text={DECISION_STATUS[d.status]?.label || d.status} color={DECISION_STATUS[d.status]?.color || GOLD} />
      </View>
      <Text style={{ fontSize: 13, color: colors.text, lineHeight: 18 }} numberOfLines={3}>{d.recommendation}</Text>
      {!!d.founder?.reason && <Text style={{ fontSize: 12.5, color: colors.textSecondary, lineHeight: 17 }} numberOfLines={2}>You: {d.founder.reason}</Text>}
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
        <Text style={{ fontSize: 11.5, color: colors.textSecondary }}>{d.next_actions.length} proposed action{d.next_actions.length === 1 ? '' : 's'} · {new Date(d.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}</Text>
        <Ionicons name="chevron-forward" size={14} color={colors.textSecondary} style={{ marginLeft: 'auto' }} />
      </View>
    </TouchableOpacity>
  );
  return (
    <View style={{ gap: 16 }} {...tid('cc-decisions')}>
      {rows === null && <ActivityIndicator color={GOLD} />}
      {rows && !rows.length && <Empty t="No decision records yet. A roundtable ends in one." colors={colors} testID="cc-decisions-empty" />}
      {!!pending.length && <View style={{ gap: 8 }}><Eyebrow t="WAITING ON YOU" colors={colors} />{pending.map(d => <Row key={d.id} d={d} />)}</View>}
      {!!made.length && <View style={{ gap: 8 }}><Eyebrow t="DECIDED" colors={colors} />{made.map(d => <Row key={d.id} d={d} />)}</View>}
    </View>
  );
};
