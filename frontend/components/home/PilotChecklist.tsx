import React from 'react';
import { Text, TouchableOpacity, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { GOLD, GREEN, RADIUS, SPACE, tid, tint } from '../ui/tokens';

export type PilotStep = { key: string; title: string; hint: string; route: string; done: boolean; done_at?: string | null };
export type PilotChecklistData = { steps: PilotStep[]; done: number; total: number; complete: boolean };

export function PilotChecklist({ data, colors, onStep }: { data: PilotChecklistData; colors: any; onStep: (s: PilotStep) => void }) {
  if (data.complete) {
    return (
      <View style={{ marginHorizontal: SPACE.lg, marginBottom: SPACE.xl, flexDirection: 'row', alignItems: 'center', gap: 10, padding: SPACE.md, borderRadius: RADIUS.md, backgroundColor: tint(GREEN, 0.1), borderWidth: 1, borderColor: tint(GREEN, 0.35) }} {...tid('pilot-checklist-complete')}>
        <Ionicons name="checkmark-circle" size={22} color={GREEN} />
        <Text style={{ flex: 1, fontSize: 14, fontWeight: '600', color: colors.text }}>You're all set up. Everything below is yours to use every day.</Text>
      </View>
    );
  }
  const nextKey = data.steps.find(s => !s.done)?.key;
  const pct = Math.round((data.done / Math.max(1, data.total)) * 100);
  return (
    <View style={{ marginHorizontal: SPACE.lg, marginBottom: SPACE.xl, borderRadius: RADIUS.xl, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, overflow: 'hidden' }} {...tid('pilot-checklist')}>
      <View style={{ padding: SPACE.lg, paddingBottom: SPACE.md }}>
        <View style={{ flexDirection: 'row', alignItems: 'flex-end', justifyContent: 'space-between' }}>
          <Text style={{ fontSize: 11, fontWeight: '800', letterSpacing: 1.4, color: GOLD }}>GET SET UP</Text>
          <Text style={{ fontSize: 13, fontWeight: '700', color: colors.textSecondary }} {...tid('pilot-progress')}>{data.done} of {data.total} done</Text>
        </View>
        <View style={{ height: 6, borderRadius: 3, backgroundColor: colors.border, marginTop: 10, overflow: 'hidden' }}>
          <View style={{ width: `${pct}%`, height: 6, backgroundColor: GOLD, borderRadius: 3 }} />
        </View>
      </View>
      {data.steps.map((s, i) => {
        const isNext = s.key === nextKey;
        return (
          <TouchableOpacity
            key={s.key}
            onPress={() => onStep(s)}
            activeOpacity={0.75}
            style={{
              flexDirection: 'row', alignItems: 'center', gap: 12, paddingHorizontal: SPACE.lg, paddingVertical: 13,
              borderTopWidth: i === 0 ? 0 : 0.5, borderTopColor: colors.border,
              backgroundColor: isNext ? tint(GOLD, 0.08) : 'transparent',
            }}
            {...tid(`pilot-step-${s.key}`)}
          >
            <Ionicons
              name={s.done ? 'checkmark-circle' : isNext ? 'arrow-forward-circle' : 'ellipse-outline'}
              size={24}
              color={s.done ? GREEN : isNext ? GOLD : colors.textTertiary || colors.textSecondary}
            />
            <View style={{ flex: 1 }}>
              <Text style={{ fontSize: 15, fontWeight: isNext ? '700' : '600', color: s.done ? colors.textSecondary : colors.text, textDecorationLine: s.done ? 'line-through' : 'none' }}>{s.title}</Text>
              {!s.done ? <Text style={{ fontSize: 12.5, color: colors.textSecondary, marginTop: 2 }}>{s.hint}</Text> : null}
            </View>
            {!s.done ? <Ionicons name="chevron-forward" size={16} color={isNext ? GOLD : colors.border} /> : null}
          </TouchableOpacity>
        );
      })}
    </View>
  );
}
