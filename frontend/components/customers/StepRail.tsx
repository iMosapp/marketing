import React from 'react';
import { Text, TouchableOpacity, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

export type Step = {
  key: string;
  title: string;
  detail: string;
  done: boolean;
  current?: boolean;
  action?: { label: string; onPress: () => void; disabled?: boolean; testID: string; tone?: 'gold' | 'orange' | 'plain' };
  secondary?: { label: string; onPress: () => void; testID: string };
  tertiary?: { label: string; onPress: () => void; testID: string };
};

export function StepRail({ steps, colors, busy }: { steps: Step[]; colors: any; busy: boolean }) {
  return (
    <View style={{ gap: 8 }} data-testid="customer-steps">
      {steps.map((s, i) => {
        const color = s.done ? '#34C759' : s.current ? '#C9A962' : colors.textTertiary;
        const bg = { gold: '#C9A962', orange: '#FF9500', plain: colors.card }[s.action?.tone || 'gold'];
        return (
          <View key={s.key} style={{ flexDirection: 'row', gap: 12, backgroundColor: colors.card, borderRadius: 12, borderWidth: 1, borderColor: s.current ? '#C9A962' : colors.border, padding: 14 }} data-testid={`step-${s.key}`}>
            <View style={{ width: 28, height: 28, borderRadius: 14, alignItems: 'center', justifyContent: 'center', backgroundColor: `${color}22` }}>
              {s.done ? <Ionicons name="checkmark" size={16} color={color} /> : <Text style={{ fontSize: 13, fontWeight: '800', color }}>{i + 1}</Text>}
            </View>
            <View style={{ flex: 1, gap: 4 }}>
              <Text style={{ fontSize: 16, fontWeight: '700', color: colors.text }}>{s.title}</Text>
              <Text style={{ fontSize: 13, color: colors.textSecondary, lineHeight: 18 }} data-testid={`step-${s.key}-detail`}>{s.detail}</Text>
              {s.action && !s.done ? (
                <TouchableOpacity
                  onPress={s.action.onPress}
                  disabled={busy || s.action.disabled}
                  style={{ alignSelf: 'flex-start', marginTop: 6, paddingVertical: 9, paddingHorizontal: 16, borderRadius: 10, backgroundColor: s.action.disabled ? '#8E8E9355' : bg, borderWidth: s.action.tone === 'plain' ? 1 : 0, borderColor: colors.border }}
                  data-testid={s.action.testID}
                >
                  <Text style={{ fontSize: 14, fontWeight: '700', color: s.action.tone === 'plain' ? colors.text : '#000' }}>{s.action.label}</Text>
                </TouchableOpacity>
              ) : null}
              {s.secondary ? (
                <TouchableOpacity onPress={s.secondary.onPress} disabled={busy} style={{ alignSelf: 'flex-start', marginTop: 4 }} data-testid={s.secondary.testID}>
                  <Text style={{ fontSize: 14, fontWeight: '600', color: '#C9A962' }}>{s.secondary.label}</Text>
                </TouchableOpacity>
              ) : null}
              {s.tertiary ? (
                <TouchableOpacity onPress={s.tertiary.onPress} disabled={busy} style={{ alignSelf: 'flex-start', marginTop: 2 }} data-testid={s.tertiary.testID}>
                  <Text style={{ fontSize: 14, fontWeight: '600', color: colors.textSecondary }}>{s.tertiary.label}</Text>
                </TouchableOpacity>
              ) : null}
            </View>
          </View>
        );
      })}
    </View>
  );
}
