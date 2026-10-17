import React from 'react';
import { View, Text, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { GOLD, tid } from '../scripts/shared';

export type UnfiledMemo = { memo_id: string; title: string; when_label: string; when_spoken: string; quote: string; why: string; link: string };

// Who mentioned: the rep's own voice memos that match but are not filed to anyone yet. Tap opens that exact memo in the memo inbox.
export const UnfiledMemoHits = ({ memos, colors }: { memos: UnfiledMemo[]; colors: any }) => {
  const router = useRouter();
  if (!memos?.length) return null;
  return (
    <View style={{ gap: 8, marginBottom: 6 }} {...tid('memory-search-unfiled')}>
      <Text style={{ fontSize: 12, fontWeight: '700', color: colors.textSecondary, letterSpacing: 0.5 }}>VOICE MEMOS NOT FILED YET</Text>
      {memos.map(m => (
        <TouchableOpacity key={m.memo_id} onPress={() => router.push(m.link as any)} style={{ backgroundColor: colors.card, borderRadius: 14, borderWidth: 1, borderColor: colors.border, padding: 12, gap: 4 }} {...tid(`unfiled-memo-${m.memo_id}`)}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
            <Ionicons name="mic-outline" size={14} color={GOLD} />
            <Text style={{ flex: 1, fontSize: 13.5, fontWeight: '800', color: colors.text }} numberOfLines={1}>{m.title || 'Untitled memo'}</Text>
            <Text style={{ fontSize: 11.5, color: colors.textSecondary }}>{m.when_label}</Text>
            <Ionicons name="chevron-forward" size={14} color={colors.textTertiary} />
          </View>
          <Text style={{ fontSize: 13, color: colors.text, fontStyle: 'italic', lineHeight: 18 }} numberOfLines={3}>"{m.quote}"</Text>
          <Text style={{ fontSize: 12, fontWeight: '700', color: GOLD }}>Open memo to play or file it</Text>
        </TouchableOpacity>
      ))}
    </View>
  );
};
