import React from 'react';
import { View, Text, TouchableOpacity, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { GOLD, tid } from '../inbox/ownership';

export const money = (n?: number | null) => (n == null ? '' : `$${Math.round(n).toLocaleString()}`);
export const miles = (n?: number | null) => (n == null ? '' : `${Math.round(n).toLocaleString()} mi`);
export const STEP_LABELS: Record<string, string> = { mode: 'How', identity: 'Vehicle', mileage: 'Mileage', expectation: 'Expectation', review: 'Review' };
export const STEP_ORDER = ['mode', 'identity', 'mileage', 'expectation', 'review'];

// Big, thumb-friendly action for a rep standing next to a car. Gold = primary, outline = secondary.
export const BigButton = ({ icon, label, sub, onPress, primary, disabled, testId, colors }: { icon: any; label: string; sub?: string; onPress: () => void; primary?: boolean; disabled?: boolean; testId: string; colors: any }) => (
  <TouchableOpacity onPress={onPress} disabled={disabled} activeOpacity={0.85} {...tid(testId)}
    style={{ flexDirection: 'row', alignItems: 'center', gap: 14, minHeight: 64, paddingHorizontal: 16, paddingVertical: 12, borderRadius: 16, backgroundColor: primary ? GOLD : colors.card, borderWidth: 1, borderColor: primary ? GOLD : colors.border, opacity: disabled ? 0.5 : 1 }}>
    <View style={{ width: 40, height: 40, borderRadius: 20, backgroundColor: primary ? '#0B0B0D22' : GOLD + '1F', alignItems: 'center', justifyContent: 'center' }}>
      <Ionicons name={icon} size={20} color={primary ? '#0B0B0D' : GOLD} />
    </View>
    <View style={{ flex: 1 }}>
      <Text style={{ fontSize: 16, fontWeight: '800', color: primary ? '#0B0B0D' : colors.text }}>{label}</Text>
      {sub ? <Text style={{ fontSize: 12, color: primary ? '#0B0B0D99' : colors.textSecondary, marginTop: 2 }}>{sub}</Text> : null}
    </View>
    <Ionicons name="chevron-forward" size={18} color={primary ? '#0B0B0D' : colors.textSecondary} />
  </TouchableOpacity>
);

export const StepTitle = ({ title, sub, colors }: { title: string; sub?: string; colors: any }) => (
  <View style={{ gap: 4, marginBottom: 6 }}>
    <Text style={{ fontSize: 22, fontWeight: '800', color: colors.text }} {...tid('step-title')}>{title}</Text>
    {sub ? <Text style={{ fontSize: 13.5, color: colors.textSecondary, lineHeight: 19 }}>{sub}</Text> : null}
  </View>
);

export const BusyBar = ({ text, colors }: { text: string | null; colors: any }) => text ? (
  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, padding: 12, borderRadius: 12, backgroundColor: colors.card, borderWidth: 1, borderColor: GOLD + '66' }} {...tid('appraisal-busy')}>
    <ActivityIndicator color={GOLD} /><Text style={{ flex: 1, fontSize: 13, color: colors.text }}>{text}</Text>
  </View>
) : null;

export const SourceTag = ({ source, colors }: { source?: string; colors: any }) => {
  const label = source === 'customer_supplied' ? 'Customer sent' : source === 'uploaded_by_rep' ? 'Imported' : source === 'captured_by_rep' ? 'Captured' : '';
  if (!label) return null;
  const c = source === 'customer_supplied' ? '#5AC8FA' : source === 'uploaded_by_rep' ? '#AF52DE' : '#34C759';
  return <View style={{ backgroundColor: c + '22', borderRadius: 8, paddingHorizontal: 7, paddingVertical: 2 }} {...tid(`media-source-${source}`)}><Text style={{ fontSize: 10.5, fontWeight: '800', color: c }}>{label}</Text></View>;
};

// Progress dots across the top of the stepper.
export const StepDots = ({ step, colors }: { step: string; colors: any }) => {
  const idx = Math.max(0, STEP_ORDER.indexOf(step));
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 16, paddingVertical: 10 }} {...tid('step-dots')}>
      {STEP_ORDER.map((s, i) => (
        <View key={s} style={{ flex: 1, alignItems: 'center', gap: 4 }}>
          <View style={{ height: 4, alignSelf: 'stretch', borderRadius: 2, backgroundColor: i <= idx ? GOLD : colors.border }} />
          <Text style={{ fontSize: 10, fontWeight: '700', color: i === idx ? GOLD : colors.textSecondary }}>{STEP_LABELS[s]}</Text>
        </View>
      ))}
    </View>
  );
};
