import React from 'react';
import { View, Text, TouchableOpacity, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { GOLD, tid } from './utils';

export type TrioPerson = { id: string; name: string; why?: string };
export type TrioPreview = { contact_id: string; name: string; message: string; knew: string[]; used: string[]; error: string };
type Props = { person: TrioPerson; preview?: TrioPreview | null; loading: boolean; colors: any; width?: number; index: number; onSwap: () => void; onRetry: () => void };

// One customer's version of the step: who they are to Jessi, what she knew, and the text she would write for them today.
export const TrioCard = ({ person, preview, loading, colors, width, index, onSwap, onRetry }: Props) => {
  const used = new Set(preview?.used || []);
  return (
    <View style={{ width, flex: width ? undefined : 1, backgroundColor: colors.card, borderRadius: 18, borderWidth: 1, borderColor: colors.border, padding: 14, gap: 10 }} {...tid(`trio-card-${index}`)}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
        <View style={{ flex: 1 }}>
          <Text style={{ fontSize: 16, fontWeight: '800', color: colors.text }} numberOfLines={1} {...tid(`trio-name-${index}`)}>{person.name}</Text>
          {!!person.why && <Text style={{ fontSize: 11, fontWeight: '800', color: GOLD, letterSpacing: 0.6, marginTop: 2 }}>{person.why.toUpperCase()}</Text>}
        </View>
        <TouchableOpacity onPress={onSwap} hitSlop={8} style={{ flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 10, paddingVertical: 6, borderRadius: 14, borderWidth: 1, borderColor: colors.border }} {...tid(`trio-swap-${index}`)}>
          <Ionicons name="swap-horizontal" size={14} color={colors.textSecondary} />
          <Text style={{ fontSize: 12, fontWeight: '700', color: colors.textSecondary }}>Swap</Text>
        </TouchableOpacity>
      </View>

      <View style={{ gap: 4 }}>
        <Text style={{ fontSize: 10.5, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.8 }}>WHAT JESSI KNEW</Text>
        {(preview?.knew || []).map(k => (
          <View key={k} style={{ flexDirection: 'row', gap: 6, alignItems: 'flex-start' }}>
            <Ionicons name={used.has(k) ? 'checkmark-circle' : 'ellipse-outline'} size={13} color={used.has(k) ? GOLD : colors.textTertiary} style={{ marginTop: 2 }} />
            <Text style={{ flex: 1, fontSize: 12.5, color: used.has(k) ? colors.text : colors.textSecondary, fontWeight: used.has(k) ? '700' : '400' }} numberOfLines={2}>{k}</Text>
          </View>
        ))}
        {loading && !preview && <Text style={{ fontSize: 12.5, color: colors.textTertiary }}>Looking them up…</Text>}
      </View>

      <View style={{ minHeight: 90, borderRadius: 16, borderTopLeftRadius: 4, backgroundColor: `${GOLD}1A`, borderWidth: 1, borderColor: `${GOLD}55`, padding: 12, justifyContent: 'center' }} {...tid(`trio-message-${index}`)}>
        {loading ? (
          <View style={{ alignItems: 'center', gap: 6 }}><ActivityIndicator color={GOLD} /><Text style={{ fontSize: 12, color: colors.textSecondary }}>Jessi is writing…</Text></View>
        ) : preview?.error ? (
          <View style={{ gap: 6 }}>
            <Text style={{ fontSize: 13, color: colors.textSecondary }} {...tid(`trio-error-${index}`)}>{preview.error}</Text>
            <TouchableOpacity onPress={onRetry} {...tid(`trio-retry-${index}`)}><Text style={{ fontSize: 13, fontWeight: '800', color: GOLD }}>Try again</Text></TouchableOpacity>
          </View>
        ) : (
          <Text style={{ fontSize: 14.5, lineHeight: 20, color: colors.text }}>{preview?.message || ''}</Text>
        )}
      </View>
    </View>
  );
};
