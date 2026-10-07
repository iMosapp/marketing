import React from 'react';
import { View, Text, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { GOLD, tid } from '../../inbox/ownership';
import { SectionCard, NumField } from './fields';
import { SourceTagSmall } from '../ValueBreakdown';

type Props = { colors: any; basis: any; options: Record<string, any>; onChange: (b: any) => void };

// STARTING VALUE: the dealership's preferred order. The engine takes the first reference that exists on the appraisal.
export const BasisEditor = ({ colors, basis, options, onChange }: Props) => {
  const order: string[] = basis.order || [];
  const move = (i: number, d: number) => { const n = [...order]; const j = i + d; if (j < 0 || j >= n.length) return; [n[i], n[j]] = [n[j], n[i]]; onChange({ ...basis, order: n }); };
  const remove = (k: string) => onChange({ ...basis, order: order.filter(x => x !== k) });
  const add = (k: string) => onChange({ ...basis, order: [...order, k] });
  const rest = Object.keys(options).filter(k => !order.includes(k));
  return (
    <SectionCard colors={colors} title="Starting value" hint="Tried in this order; the first one that exists on the appraisal wins. Market retail is a retail number, so target gross comes off it. Book wholesale numbers skip target gross." testId="rules-basis">
      {order.length === 0 ? <Text style={{ fontSize: 13, color: '#FF3B30', fontWeight: '700' }}>Pick at least one.</Text> : null}
      {order.map((k, i) => (
        <View key={k} style={{ flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 8, borderTopWidth: i ? 1 : 0, borderTopColor: colors.border }} {...tid(`basis-row-${k.replace(':', '-')}`)}>
          <Text style={{ width: 18, fontSize: 13, fontWeight: '800', color: GOLD }}>{i + 1}</Text>
          <View style={{ flex: 1, gap: 3 }}>
            <Text style={{ fontSize: 14, fontWeight: '700', color: colors.text }}>{options[k]?.label || k}</Text>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}><SourceTagSmall source={options[k]?.source || 'MANUAL'} /><Text style={{ flex: 1, fontSize: 11, color: colors.textSecondary }} numberOfLines={1}>{options[k]?.hint}</Text></View>
          </View>
          <TouchableOpacity onPress={() => move(i, -1)} disabled={i === 0} hitSlop={6} {...tid(`basis-up-${k.replace(':', '-')}`)}><Ionicons name="chevron-up" size={20} color={i === 0 ? colors.border : colors.textSecondary} /></TouchableOpacity>
          <TouchableOpacity onPress={() => move(i, 1)} disabled={i === order.length - 1} hitSlop={6} {...tid(`basis-down-${k.replace(':', '-')}`)}><Ionicons name="chevron-down" size={20} color={i === order.length - 1 ? colors.border : colors.textSecondary} /></TouchableOpacity>
          <TouchableOpacity onPress={() => remove(k)} hitSlop={6} {...tid(`basis-remove-${k.replace(':', '-')}`)}><Ionicons name="close-circle" size={20} color="#FF3B30" /></TouchableOpacity>
        </View>
      ))}
      {rest.length ? (
        <View style={{ gap: 6 }}>
          <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.4 }}>ADD A FALLBACK</Text>
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>
            {rest.map(k => (
              <TouchableOpacity key={k} onPress={() => add(k)} style={{ flexDirection: 'row', alignItems: 'center', gap: 4, height: 32, paddingHorizontal: 10, borderRadius: 16, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.bg }} {...tid(`basis-add-${k.replace(':', '-')}`)}>
                <Ionicons name="add" size={14} color={GOLD} /><Text style={{ fontSize: 12, fontWeight: '700', color: colors.text }}>{options[k]?.label || k}</Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>
      ) : null}
      <View style={{ flexDirection: 'row', gap: 10 }}>
        <NumField colors={colors} label="Min comparables to trust the median / average" value={basis.min_comps} onChange={v => onChange({ ...basis, min_comps: v ?? 1 })} prefix="" testId="basis-min-comps" />
      </View>
    </SectionCard>
  );
};
