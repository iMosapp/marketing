import React from 'react';
import { View, Text, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

export type ReplyRationale = {
  topic?: string | null;
  why?: string | null;
  mode?: string | null;
  summary?: string | null;
  evidence?: { fact_id: string; label: string; source?: string | null; at?: string | null; confirmed?: boolean }[];
} | null | undefined;

const GOLD = '#C9A962';

/** "Why this reply?" line under an AI draft: each chip is a fact Jessi leaned on; tapping opens its source sheet. */
export default function WhyThisReply({ rationale, colors, onWhy, testPrefix }: { rationale: ReplyRationale; colors: any; onWhy?: (factId: string) => void; testPrefix: string }) {
  const evidence = (rationale?.evidence || []).slice(0, 3);
  if (!rationale || (!evidence.length && !rationale.why)) return null;
  const tid = (id: string) => ({ testID: id, dataSet: { testid: id } as any });
  return (
    <View style={{ gap: 6 }} {...tid(testPrefix)}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 5 }}>
        <Ionicons name="sparkles-outline" size={12} color={GOLD} />
        <Text style={{ flex: 1, fontSize: 12, color: colors.textSecondary }} numberOfLines={2} {...tid(`${testPrefix}-text`)}>
          {evidence.length ? 'Based on:' : `Why: ${rationale.why}`}
        </Text>
      </View>
      {evidence.length > 0 && (
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>
          {evidence.map((e, i) => (
            <TouchableOpacity
              key={e.fact_id || i}
              onPress={() => e.fact_id && onWhy?.(e.fact_id)}
              activeOpacity={0.7}
              style={{ flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 9, paddingVertical: 4, borderRadius: 999, borderWidth: 1, borderColor: `${GOLD}66`, backgroundColor: `${GOLD}14` }}
              {...tid(`${testPrefix}-${i}`)}
            >
              <Text style={{ fontSize: 11, color: colors.text }} numberOfLines={1}>{e.label}</Text>
              {e.confirmed === false && <Ionicons name="help-circle-outline" size={11} color={colors.textSecondary} />}
            </TouchableOpacity>
          ))}
        </View>
      )}
    </View>
  );
}
