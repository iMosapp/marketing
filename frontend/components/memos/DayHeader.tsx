import React, { useState } from 'react';
import { View, Text, TextInput, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { GOLD, tid } from '../inbox/ownership';

type Props = { dayKey: string; title: string; label: string; count: number; onRename: (label: string) => void; colors: any };

// One recording day. Tap the pencil to name it ("NADA show day 2"); the name sticks to that day across both tabs.
export const DayHeader = ({ dayKey, title, label, count, onRename, colors }: Props) => {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(label);
  const commit = () => { setEditing(false); if (draft.trim() !== label) onRename(draft.trim()); };
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 4 }} {...tid(`memo-day-${dayKey}`)}>
      <Ionicons name="folder-open-outline" size={15} color={GOLD} />
      {editing ? (
        <TextInput value={draft} onChangeText={setDraft} onBlur={commit} onSubmitEditing={commit} autoFocus maxLength={60} placeholder={`Name this day, e.g. "NADA show day 2"`} placeholderTextColor={colors.textSecondary}
          style={{ flex: 1, fontSize: 14, fontWeight: '800', color: colors.text, borderBottomWidth: 1, borderBottomColor: GOLD, paddingVertical: 2 }} {...tid(`memo-day-input-${dayKey}`)} />
      ) : (
        <TouchableOpacity onPress={() => { setDraft(label); setEditing(true); }} hitSlop={8} style={{ flex: 1, flexDirection: 'row', alignItems: 'baseline', gap: 6, paddingVertical: 6 }} {...tid(`memo-day-rename-${dayKey}`)}>
          <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 1 }}>{title.toUpperCase()} · {count}</Text>
          {label ? <Text style={{ fontSize: 14, fontWeight: '800', color: colors.text }} numberOfLines={1} {...tid(`memo-day-label-${dayKey}`)}>{label}</Text> : null}
          <Ionicons name="pencil" size={12} color={colors.textSecondary} />
        </TouchableOpacity>
      )}
    </View>
  );
};
