/**
 * IntelTeaser — one-line "glance before you text" strip.
 * The full Relationship Intel brief lives in the Details tab; this just points at it.
 */
import React, { useMemo } from 'react';
import { View, Text, TouchableOpacity, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { parseSections } from './IntelBriefingCard';

const GOLD = '#C9A962';

export default function IntelTeaser({ colors, intelData, refreshing, onPress }: any) {
  const summary: string = intelData?.summary || '';
  const line = useMemo(() => {
    const sections = parseSections(summary);
    const next = (sections['Before Your Next Interaction'] || [])[0];
    const take = (sections['Quick Take'] || []).join(' ');
    return (next || take || summary).replace(/\s+/g, ' ').trim();
  }, [summary]);

  if (!summary && !refreshing) return null;
  const notes = intelData?.data_points?.voice_notes || 0;

  return (
    <TouchableOpacity
      onPress={onPress}
      activeOpacity={0.75}
      style={{
        flexDirection: 'row', alignItems: 'center', gap: 8,
        marginHorizontal: 16, marginBottom: 10, paddingVertical: 9, paddingHorizontal: 12,
        borderRadius: 12, backgroundColor: `${GOLD}12`, borderWidth: 1, borderColor: `${GOLD}30`,
      }}
      testID="intel-teaser"
      dataSet={{ testid: 'intel-teaser' } as any}
    >
      {refreshing && !summary ? <ActivityIndicator size="small" color={GOLD} /> : <Ionicons name="sparkles" size={15} color={GOLD} />}
      <Text style={{ flex: 1, fontSize: 13, color: colors.text, lineHeight: 18 }} numberOfLines={1}>
        <Text style={{ fontWeight: '800', color: GOLD }}>Jessi's brief: </Text>
        {summary ? line : 'building the brief...'}
        {notes ? <Text style={{ color: colors.textSecondary }}>{`  ·  ${notes} voice note${notes === 1 ? '' : 's'}`}</Text> : null}
      </Text>
      <Ionicons name="chevron-forward" size={15} color={colors.textTertiary} />
    </TouchableOpacity>
  );
}
