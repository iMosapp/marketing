import React, { useState } from 'react';
import { View, Text, TextInput, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { GOLD, tid } from '../inbox/ownership';
import { Label, Hint, inputStyle } from '../inbox/InboxEditorParts';

type Props = { label: string; hint?: string; items: string[]; onChange: (items: string[]) => void; placeholder: string; colors: any; testId: string; max?: number; editable?: boolean };

// A list of short lines (facts, never-say phrases, hand-off topics) as removable pills plus an add row.
export const ListEditor = ({ label, hint, items, onChange, placeholder, colors, testId, max = 20, editable = true }: Props) => {
  const [v, setV] = useState('');
  const add = () => { const t = v.trim(); if (!t || items.includes(t) || items.length >= max) return; onChange([...items, t]); setV(''); };
  return (
    <View {...tid(testId)}>
      <Label colors={colors} top>{label}</Label>
      {hint ? <Hint colors={colors}>{hint}</Hint> : null}
      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>
        {items.length === 0 ? <Text style={{ fontSize: 13, color: colors.textSecondary }} {...tid(`${testId}-empty`)}>Nothing yet.</Text> : null}
        {items.map((t, i) => (
          <View key={`${t}-${i}`} style={{ flexDirection: 'row', alignItems: 'center', gap: 6, paddingLeft: 12, paddingRight: editable ? 6 : 12, height: 34, borderRadius: 17, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, maxWidth: '100%' }} {...tid(`${testId}-item-${i}`)}>
            <Text style={{ fontSize: 13, color: colors.text, flexShrink: 1 }} numberOfLines={2}>{t}</Text>
            {editable ? <TouchableOpacity onPress={() => onChange(items.filter((_, j) => j !== i))} hitSlop={6} {...tid(`${testId}-item-${i}-remove`)}><Ionicons name="close-circle" size={18} color={colors.textSecondary} /></TouchableOpacity> : null}
          </View>
        ))}
      </View>
      {editable && items.length < max ? (
        <View style={{ flexDirection: 'row', gap: 8, marginTop: 8 }}>
          <TextInput value={v} onChangeText={setV} placeholder={placeholder} placeholderTextColor={colors.textSecondary} onSubmitEditing={add} blurOnSubmit={false} style={[inputStyle(colors), { flex: 1 }]} {...tid(`${testId}-input`)} />
          <TouchableOpacity onPress={add} disabled={!v.trim()} style={{ width: 46, height: 46, borderRadius: 12, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center', opacity: v.trim() ? 1 : 0.5 }} {...tid(`${testId}-add`)}>
            <Ionicons name="add" size={22} color="#111" />
          </TouchableOpacity>
        </View>
      ) : null}
    </View>
  );
};
