import React, { useEffect, useState } from 'react';
import { View, Text, TextInput, TouchableOpacity, Switch, Platform } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { GOLD, tid } from '../inbox/ownership';
import { inputStyle, Label, Hint } from '../inbox/InboxEditorParts';

export const HEX = /^#[0-9A-Fa-f]{6}$/;
export const QUICK = ['#2196F3', '#007AFF', '#1D4ED8', '#DC2626', '#E11D48', '#F97316', '#16A34A', '#0D9488', '#7C3AED', '#111111', '#C9A962', '#FFFFFF'];
export type Swatch = { hex: string; label: string; text: string };

export const contrastText = (hex: string) => {
  if (!HEX.test(hex)) return '#FFFFFF';
  const [r, g, b] = [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16) / 255);
  return 0.2126 * r + 0.7152 * g + 0.0722 * b > 0.6 ? '#111111' : '#FFFFFF';
};

type FieldProps = { label: string; hint?: string; value: string; onChange: (v: string) => void; placeholder?: string; multiline?: boolean; colors: any; testId: string; maxLength?: number; top?: boolean };
export const Field = ({ label, hint, value, onChange, placeholder, multiline, colors, testId, maxLength, top = true }: FieldProps) => (
  <View>
    <Label colors={colors} top={top}>{label}</Label>
    {hint ? <Hint colors={colors}>{hint}</Hint> : null}
    <TextInput value={value} onChangeText={onChange} placeholder={placeholder} placeholderTextColor={colors.textSecondary} multiline={multiline} maxLength={maxLength}
      style={[inputStyle(colors), multiline ? { minHeight: 70, textAlignVertical: 'top' } : null]} {...tid(testId)} />
  </View>
);

export const ToggleRow = ({ label, hint, value, onChange, colors, testId }: { label: string; hint?: string; value: boolean; onChange: (v: boolean) => void; colors: any; testId: string }) => (
  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 8 }}>
    <View style={{ flex: 1 }}>
      <Text style={{ fontSize: 14, fontWeight: '700', color: colors.text }}>{label}</Text>
      {hint ? <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 2, lineHeight: 16 }}>{hint}</Text> : null}
    </View>
    <Switch value={value} onValueChange={onChange} trackColor={{ true: GOLD }} {...tid(testId)} />
  </View>
);

type Chip = { value: string; label: string; icon?: string };
export const Chips = ({ options, value, onChange, colors, testId }: { options: Chip[]; value: string; onChange: (v: string) => void; colors: any; testId: string }) => (
  <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
    {options.map(o => {
      const on = o.value === value;
      return (
        <TouchableOpacity key={o.value} onPress={() => onChange(o.value)} style={{ flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 12, height: 36, borderRadius: 18, backgroundColor: on ? GOLD : colors.surface, borderWidth: 1, borderColor: on ? GOLD : colors.border }} {...tid(`${testId}-${o.value}`)}>
          {o.icon ? <Ionicons name={o.icon as any} size={15} color={on ? '#111' : colors.textSecondary} /> : null}
          <Text style={{ fontSize: 13, fontWeight: '700', color: on ? '#111' : colors.text }}>{o.label}</Text>
        </TouchableOpacity>
      );
    })}
  </View>
);

export const Stepper = ({ label, value, onChange, min, max, step = 1, unit, colors, testId }: { label: string; value: number; onChange: (v: number) => void; min: number; max: number; step?: number; unit?: string; colors: any; testId: string }) => (
  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 6 }}>
    <Text style={{ flex: 1, fontSize: 14, fontWeight: '700', color: colors.text }}>{label}</Text>
    <TouchableOpacity onPress={() => onChange(Math.max(min, value - step))} hitSlop={6} {...tid(`${testId}-minus`)}><Ionicons name="remove-circle-outline" size={26} color={colors.textSecondary} /></TouchableOpacity>
    <Text style={{ fontSize: 15, fontWeight: '800', color: GOLD, minWidth: 54, textAlign: 'center' }} {...tid(testId)}>{value}{unit || ''}</Text>
    <TouchableOpacity onPress={() => onChange(Math.min(max, value + step))} hitSlop={6} {...tid(`${testId}-plus`)}><Ionicons name="add-circle-outline" size={26} color={GOLD} /></TouchableOpacity>
  </View>
);

const desktopWeb = Platform.OS === 'web' && typeof navigator !== 'undefined' && !/iPhone|iPad|iPod|Android/.test(navigator.userAgent);

// Hex field + eyedropper (desktop web opens the browser's color wheel) + quick picks + the colors pulled off the dealer's site.
export const ColorField = ({ label, hint, value, onChange, colors, testId, swatches }: { label: string; hint?: string; value: string; onChange: (hex: string) => void; colors: any; testId: string; swatches?: Swatch[] }) => {
  const [hex, setHex] = useState(value);
  useEffect(() => { setHex(value); }, [value]);
  const set = (t: string) => { const v = t.startsWith('#') ? t : `#${t}`; setHex(v); if (HEX.test(v)) onChange(v.toUpperCase()); };
  const openWheel = () => {
    if (!desktopWeb) return;
    const input = document.createElement('input');
    input.type = 'color'; input.value = HEX.test(value) ? value : '#2196F3';
    input.style.cssText = 'position:fixed;top:-9999px;left:-9999px;opacity:0;';
    document.body.appendChild(input);
    input.addEventListener('input', (e: any) => set(e.target.value));
    input.addEventListener('change', () => { try { document.body.removeChild(input); } catch {} });
    input.click();
  };
  const Dot = ({ c, id, title }: { c: string; id: string; title?: string }) => (
    <TouchableOpacity onPress={() => set(c)} style={{ alignItems: 'center', width: 44 }} {...tid(id)}>
      <View style={{ width: 30, height: 30, borderRadius: 15, backgroundColor: c, borderWidth: value.toUpperCase() === c.toUpperCase() ? 3 : 1, borderColor: value.toUpperCase() === c.toUpperCase() ? GOLD : colors.border, alignItems: 'center', justifyContent: 'center' }}>
        {value.toUpperCase() === c.toUpperCase() ? <Ionicons name="checkmark" size={14} color={contrastText(c)} /> : null}
      </View>
      {title ? <Text style={{ fontSize: 9, color: colors.textSecondary, marginTop: 3, textAlign: 'center' }} numberOfLines={1}>{title}</Text> : null}
    </TouchableOpacity>
  );
  return (
    <View>
      <Label colors={colors} top>{label}</Label>
      {hint ? <Hint colors={colors}>{hint}</Hint> : null}
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
        <TouchableOpacity onPress={openWheel} activeOpacity={desktopWeb ? 0.8 : 1} style={{ width: 48, height: 48, borderRadius: 14, backgroundColor: HEX.test(value) ? value : colors.border, alignItems: 'center', justifyContent: 'center', borderWidth: 1, borderColor: colors.border }} {...tid(`${testId}-swatch`)}>
          {desktopWeb ? <Ionicons name="eyedrop-outline" size={18} color={contrastText(value)} /> : null}
        </TouchableOpacity>
        <TextInput value={hex} onChangeText={set} placeholder="#2196F3" placeholderTextColor={colors.textSecondary} maxLength={7} autoCapitalize="characters" autoCorrect={false}
          style={[inputStyle(colors), { flex: 1, fontFamily: Platform.OS === 'web' ? 'monospace' : undefined }]} {...tid(`${testId}-hex`)} />
      </View>
      {desktopWeb ? <Text style={{ fontSize: 11, color: colors.textSecondary, marginTop: 6 }}>Tap the swatch for a color wheel, or paste the exact hex from your site.</Text> : null}
      {swatches && swatches.length > 0 ? (
        <View style={{ marginTop: 10 }}>
          <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 1, marginBottom: 6 }}>FROM YOUR WEBSITE</Text>
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 4 }} {...tid(`${testId}-site-swatches`)}>
            {swatches.map((s, i) => <Dot key={s.hex} c={s.hex} id={`${testId}-site-${i}`} title={s.label} />)}
          </View>
        </View>
      ) : null}
      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 4, marginTop: 10 }}>
        {QUICK.map(c => <Dot key={c} c={c} id={`${testId}-quick-${c.slice(1)}`} />)}
      </View>
    </View>
  );
};
