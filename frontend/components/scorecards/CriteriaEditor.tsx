import React from 'react';
import { View, Text, TextInput, TouchableOpacity, Switch } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { GOLD, RED, tid, type Criterion } from './shared';

type Props = { criteria: Criterion[]; onChange: (c: Criterion[]) => void; colors: any };

const newId = () => Math.random().toString(36).slice(2, 10);

// Editable list of what the AI checks on every call: text, coaching hint, weight (1-5), critical flag, move up/down, remove.
export const CriteriaEditor = ({ criteria, onChange, colors }: Props) => {
  const upd = (i: number, p: Partial<Criterion>) => onChange(criteria.map((c, j) => (j === i ? { ...c, ...p } : c)));
  const move = (i: number, d: number) => { const j = i + d; if (j < 0 || j >= criteria.length) return; const a = [...criteria]; [a[i], a[j]] = [a[j], a[i]]; onChange(a); };
  const input = { backgroundColor: colors.card, borderRadius: 10, padding: 10, color: colors.text, fontSize: 14, borderWidth: 1, borderColor: colors.border } as const;
  return (
    <View style={{ gap: 10 }} {...tid('criteria-editor')}>
      {criteria.map((c, i) => (
        <View key={c.id} style={{ backgroundColor: colors.surface, borderRadius: 14, padding: 12, gap: 8, borderLeftWidth: 3, borderLeftColor: c.critical ? RED : GOLD }} {...tid(`criterion-${i}`)}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
            <Text style={{ fontSize: 12, fontWeight: '800', color: colors.textSecondary, width: 22 }}>{i + 1}.</Text>
            <TextInput value={c.text} onChangeText={v => upd(i, { text: v })} placeholder="What should the rep do? e.g. Asked for the trade" placeholderTextColor={colors.textSecondary} style={[input, { flex: 1 }]} {...tid(`criterion-${i}-text`)} />
          </View>
          <TextInput value={c.hint} onChangeText={v => upd(i, { hint: v })} placeholder="Coaching hint shown when missed (optional)" placeholderTextColor={colors.textSecondary} style={[input, { marginLeft: 30, fontSize: 13 }]} {...tid(`criterion-${i}-hint`)} />
          <View style={{ flexDirection: 'row', alignItems: 'center', marginLeft: 30, gap: 10 }}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
              <Text style={{ fontSize: 12, fontWeight: '700', color: colors.textSecondary }}>Weight</Text>
              <TouchableOpacity onPress={() => upd(i, { weight: Math.max(1, c.weight - 1) })} hitSlop={6} {...tid(`criterion-${i}-weight-minus`)}><Ionicons name="remove-circle-outline" size={22} color={colors.text} /></TouchableOpacity>
              <Text style={{ fontSize: 14, fontWeight: '800', color: colors.text, width: 14, textAlign: 'center' }} {...tid(`criterion-${i}-weight`)}>{c.weight}</Text>
              <TouchableOpacity onPress={() => upd(i, { weight: Math.min(5, c.weight + 1) })} hitSlop={6} {...tid(`criterion-${i}-weight-plus`)}><Ionicons name="add-circle-outline" size={22} color={colors.text} /></TouchableOpacity>
            </View>
            <View style={{ flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'flex-end', gap: 6 }}>
              <Text style={{ fontSize: 12, fontWeight: '700', color: c.critical ? RED : colors.textSecondary }}>Critical</Text>
              <Switch value={c.critical} onValueChange={v => upd(i, { critical: v })} trackColor={{ true: RED }} style={{ transform: [{ scale: 0.8 }] }} {...tid(`criterion-${i}-critical`)} />
            </View>
            <TouchableOpacity onPress={() => move(i, -1)} disabled={i === 0} hitSlop={6} style={{ opacity: i === 0 ? 0.3 : 1 }} {...tid(`criterion-${i}-up`)}><Ionicons name="chevron-up" size={20} color={colors.text} /></TouchableOpacity>
            <TouchableOpacity onPress={() => move(i, 1)} disabled={i === criteria.length - 1} hitSlop={6} style={{ opacity: i === criteria.length - 1 ? 0.3 : 1 }} {...tid(`criterion-${i}-down`)}><Ionicons name="chevron-down" size={20} color={colors.text} /></TouchableOpacity>
            <TouchableOpacity onPress={() => onChange(criteria.filter((_, j) => j !== i))} hitSlop={6} {...tid(`criterion-${i}-remove`)}><Ionicons name="trash-outline" size={18} color={RED} /></TouchableOpacity>
          </View>
        </View>
      ))}
      {criteria.length < 25 && (
        <TouchableOpacity onPress={() => onChange([...criteria, { id: newId(), text: '', hint: '', weight: 1, critical: false }])} style={{ height: 46, borderRadius: 12, borderWidth: 1, borderStyle: 'dashed', borderColor: GOLD, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 6 }} {...tid('criterion-add')}>
          <Ionicons name="add" size={18} color={GOLD} /><Text style={{ fontSize: 14, fontWeight: '800', color: GOLD }}>Add a criterion</Text>
        </TouchableOpacity>
      )}
    </View>
  );
};
