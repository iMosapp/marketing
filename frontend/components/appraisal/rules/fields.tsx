import React from 'react';
import { View, Text, TextInput, TouchableOpacity, Switch } from 'react-native';
import { GOLD, tid } from '../../inbox/ownership';

export const SectionCard = ({ colors, title, hint, enabled, onToggle, children, testId }: { colors: any; title: string; hint?: string; enabled?: boolean; onToggle?: (v: boolean) => void; children?: React.ReactNode; testId: string }) => (
  <View style={{ borderRadius: 16, padding: 14, backgroundColor: colors.card, borderWidth: 1, borderColor: enabled === false ? colors.border : (onToggle ? GOLD + '66' : colors.border), gap: 10, opacity: 1 }} {...tid(testId)}>
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
      <View style={{ flex: 1 }}>
        <Text style={{ fontSize: 15, fontWeight: '800', color: colors.text }}>{title}</Text>
        {hint ? <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 2, lineHeight: 16 }}>{hint}</Text> : null}
      </View>
      {onToggle ? <Switch value={!!enabled} onValueChange={onToggle} trackColor={{ true: GOLD }} {...tid(`${testId}-switch`)} /> : null}
    </View>
    {enabled === false && onToggle ? <Text style={{ fontSize: 12, fontWeight: '700', color: colors.textSecondary }}>Off. No line in the breakdown.</Text> : children}
  </View>
);

export const SwitchRow = ({ colors, label, hint, value, onChange, testId }: { colors: any; label: string; hint?: string; value: boolean; onChange: (v: boolean) => void; testId: string }) => (
  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 4 }}>
    <View style={{ flex: 1 }}><Text style={{ fontSize: 13.5, fontWeight: '700', color: colors.text }}>{label}</Text>{hint ? <Text style={{ fontSize: 11.5, color: colors.textSecondary }}>{hint}</Text> : null}</View>
    <Switch value={!!value} onValueChange={onChange} trackColor={{ true: GOLD }} {...tid(testId)} />
  </View>
);

// Numeric input; empty string -> null when allowEmpty (the engine treats null as "manager review" / "not set").
export const NumField = ({ colors, label, value, onChange, prefix = '$', suffix, allowEmpty, emptyLabel, testId, negative }: { colors: any; label: string; value: number | null | undefined; onChange: (v: number | null) => void; prefix?: string; suffix?: string; allowEmpty?: boolean; emptyLabel?: string; testId: string; negative?: boolean }) => (
  <View style={{ flex: 1, minWidth: 120, gap: 4 }}>
    <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.4 }} numberOfLines={1}>{label.toUpperCase()}</Text>
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4, height: 42, borderRadius: 10, paddingHorizontal: 10, backgroundColor: colors.bg, borderWidth: 1, borderColor: colors.border }}>
      {prefix ? <Text style={{ fontSize: 14, fontWeight: '700', color: colors.textSecondary }}>{prefix}</Text> : null}
      <TextInput value={value == null ? '' : String(value)} onChangeText={t => { const c = t.replace(negative ? /[^\d-]/g : /\D/g, ''); if (c === '' || c === '-') { onChange(allowEmpty ? null : (c === '' ? null : 0)); return; } onChange(parseInt(c, 10)); }}
        keyboardType={negative ? 'numbers-and-punctuation' : 'number-pad'} placeholder={allowEmpty ? (emptyLabel || 'Manager review') : '0'} placeholderTextColor={colors.textSecondary} style={{ flex: 1, fontSize: 15, fontWeight: '700', color: colors.text }} {...tid(testId)} />
      {suffix ? <Text style={{ fontSize: 12, color: colors.textSecondary }}>{suffix}</Text> : null}
    </View>
  </View>
);

export const ChipRow = ({ colors, options, value, onChange, testId }: { colors: any; options: { key: string; label: string }[]; value: string; onChange: (k: string) => void; testId: string }) => (
  <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }} {...tid(testId)}>
    {options.map(o => { const on = value === o.key; return (
      <TouchableOpacity key={o.key} onPress={() => onChange(o.key)} style={{ height: 32, paddingHorizontal: 12, borderRadius: 16, borderWidth: 1, borderColor: on ? GOLD : colors.border, backgroundColor: on ? GOLD + '22' : colors.bg, alignItems: 'center', justifyContent: 'center' }} {...tid(`${testId}-${o.key}`)}>
        <Text style={{ fontSize: 12.5, fontWeight: '700', color: on ? GOLD : colors.textSecondary }}>{o.label}</Text>
      </TouchableOpacity>
    ); })}
  </View>
);

export const TextField = ({ colors, label, value, onChange, placeholder, testId }: { colors: any; label: string; value: string; onChange: (v: string) => void; placeholder?: string; testId: string }) => (
  <View style={{ gap: 4 }}>
    <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.4 }}>{label.toUpperCase()}</Text>
    <TextInput value={value} onChangeText={onChange} placeholder={placeholder} placeholderTextColor={colors.textSecondary} style={{ minHeight: 42, borderRadius: 10, paddingHorizontal: 10, paddingVertical: 8, backgroundColor: colors.bg, borderWidth: 1, borderColor: colors.border, color: colors.text, fontSize: 13.5 }} {...tid(testId)} />
  </View>
);
