// Pinned tools: one row of gold chips at the top of Tools. Tap opens the tool, the small x unpins it.
import React from 'react';
import { View, Text, TouchableOpacity, ScrollView } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

const GOLD = '#C9A962';
const tid = (id: string) => ({ testID: id, dataSet: { testid: id } as any });

export type PinnedItem = { id: string; title: string; icon: string; color?: string; onPress: () => void };

type Props = { items: PinnedItem[]; colors: any; onUnpin: (id: string) => void };

export const PinnedStrip = ({ items, colors, onUnpin }: Props) => {
  if (!items.length) return null;
  return (
    <View style={{ marginHorizontal: 16, marginBottom: 10 }} {...tid('pinned-strip')}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 6 }}>
        <Ionicons name="bookmark" size={11} color={GOLD} />
        <Text style={{ fontSize: 11, fontWeight: '700', letterSpacing: 1.4, color: GOLD, textTransform: 'uppercase' }}>Pinned</Text>
        <Text style={{ fontSize: 11, color: colors.textTertiary, marginLeft: 4 }}>Bookmark any tool below to add it here</Text>
      </View>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8 }}>
        {items.map(it => (
          <TouchableOpacity key={it.id} onPress={it.onPress} activeOpacity={0.8}
            style={{ flexDirection: 'row', alignItems: 'center', gap: 8, paddingLeft: 12, paddingRight: 6, paddingVertical: 9, borderRadius: 999, backgroundColor: colors.card, borderWidth: 1.5, borderColor: `${GOLD}99` }}
            {...tid(`pinned-${it.id}`)}>
            <Ionicons name={it.icon as any} size={16} color={it.color || GOLD} />
            <Text style={{ fontSize: 14, fontWeight: '700', color: colors.text }} numberOfLines={1}>{it.title}</Text>
            <TouchableOpacity onPress={(e: any) => { e?.stopPropagation?.(); onUnpin(it.id); }} hitSlop={8}
              style={{ width: 22, height: 22, borderRadius: 11, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.border }}
              {...tid(`unpin-${it.id}`)}>
              <Ionicons name="close" size={13} color={colors.textSecondary} />
            </TouchableOpacity>
          </TouchableOpacity>
        ))}
      </ScrollView>
    </View>
  );
};
