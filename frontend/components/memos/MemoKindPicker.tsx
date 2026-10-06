import React from 'react';
import { View, Text, TouchableOpacity, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { GOLD, tid } from '../inbox/ownership';

export type MemoKind = 'memo' | 'conversation';
type Props = { firstName: string; busy: MemoKind | null; onPick: (k: MemoKind) => void; colors: any; secondaryLabel?: string; onSecondary?: () => void };

// "How should Jessi file it?" The two ways a memo lands on a contact; shared by the Attach sheet and the New Contact screen.
export const MemoKindPicker = ({ firstName, busy, onPick, colors, secondaryLabel, onSecondary }: Props) => (
  <View style={{ gap: 10 }} {...tid('memo-kind-picker')}>
    <Text style={{ fontSize: 13, color: colors.textSecondary, lineHeight: 18 }}>How should Jessi file it on {firstName}'s record?</Text>
    <TouchableOpacity onPress={() => onPick('memo')} disabled={!!busy} style={{ flexDirection: 'row', alignItems: 'center', gap: 12, padding: 14, borderRadius: 16, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border }} {...tid('attach-as-memo')}>
      <View style={{ width: 40, height: 40, borderRadius: 20, backgroundColor: '#34C75922', alignItems: 'center', justifyContent: 'center' }}>{busy === 'memo' ? <ActivityIndicator color="#34C759" /> : <Ionicons name="mic" size={20} color="#34C759" />}</View>
      <View style={{ flex: 1 }}>
        <Text style={{ fontSize: 15, fontWeight: '800', color: colors.text }}>As a voice memo</Text>
        <Text style={{ fontSize: 12.5, color: colors.textSecondary, lineHeight: 17, marginTop: 2 }}>A note about them. Transcript goes into their profile; Jessi picks up personal details.</Text>
      </View>
    </TouchableOpacity>
    <TouchableOpacity onPress={() => onPick('conversation')} disabled={!!busy} style={{ flexDirection: 'row', alignItems: 'center', gap: 12, padding: 14, borderRadius: 16, backgroundColor: GOLD + '14', borderWidth: 1, borderColor: GOLD + '66' }} {...tid('attach-as-conversation')}>
      <View style={{ width: 40, height: 40, borderRadius: 20, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center' }}>{busy === 'conversation' ? <ActivityIndicator color="#111" /> : <Ionicons name="people" size={20} color="#111" />}</View>
      <View style={{ flex: 1 }}>
        <Text style={{ fontSize: 15, fontWeight: '800', color: colors.text }}>As a recorded conversation</Text>
        <Text style={{ fontSize: 12.5, color: colors.textSecondary, lineHeight: 17, marginTop: 2 }}>A talk with them. Jessi writes a summary, turns every commitment into a task, and can cite it later.</Text>
      </View>
    </TouchableOpacity>
    {secondaryLabel && onSecondary ? (
      <TouchableOpacity onPress={onSecondary} disabled={!!busy} style={{ alignItems: 'center', padding: 8 }} {...tid('memo-kind-secondary')}><Text style={{ color: colors.textSecondary, fontWeight: '700' }}>{secondaryLabel}</Text></TouchableOpacity>
    ) : null}
  </View>
);
