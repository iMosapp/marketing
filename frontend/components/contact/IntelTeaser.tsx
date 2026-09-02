/**
 * IntelTeaser — one-line "glance before you text" strip that expands in place.
 * Collapsed: the single most useful next step. Tap (or the chevron) to unfold the full brief.
 */
import React, { useMemo, useState } from 'react';
import { View, Text, TouchableOpacity, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import IntelBriefingCard, { parseSections } from './IntelBriefingCard';

const GOLD = '#C9A962';

export default function IntelTeaser({ colors, intelData, refreshing, onRefresh }: any) {
  const [expanded, setExpanded] = useState(false);
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
    <View style={{ marginHorizontal: 16, marginBottom: 10 }} testID="intel-teaser-wrap" dataSet={{ testid: 'intel-teaser-wrap' } as any}>
      <TouchableOpacity
        onPress={() => setExpanded(e => !e)}
        activeOpacity={0.75}
        style={{
          flexDirection: 'row', alignItems: 'center', gap: 8,
          paddingVertical: 9, paddingHorizontal: 12,
          borderRadius: 12, backgroundColor: `${GOLD}12`, borderWidth: 1, borderColor: `${GOLD}30`,
          borderBottomLeftRadius: expanded ? 0 : 12, borderBottomRightRadius: expanded ? 0 : 12,
        }}
        testID="intel-teaser"
        dataSet={{ testid: 'intel-teaser' } as any}
      >
        {refreshing && !summary ? <ActivityIndicator size="small" color={GOLD} /> : <Ionicons name="sparkles" size={15} color={GOLD} />}
        <Text style={{ flex: 1, fontSize: 13, color: colors.text, lineHeight: 18 }} numberOfLines={expanded ? undefined : 1}>
          <Text style={{ fontWeight: '800', color: GOLD }}>Jessi's brief: </Text>
          {summary ? line : 'building the brief...'}
          {!expanded && notes ? <Text style={{ color: colors.textSecondary }}>{`  ·  ${notes} voice note${notes === 1 ? '' : 's'}`}</Text> : null}
        </Text>
        <Ionicons name={expanded ? 'chevron-up' : 'chevron-down'} size={17} color={GOLD} />
      </TouchableOpacity>

      {expanded && (
        <View
          style={{ marginHorizontal: -16, marginTop: -1 }}
          testID="intel-teaser-expanded"
          dataSet={{ testid: 'intel-teaser-expanded' } as any}
        >
          <IntelBriefingCard colors={colors} intelData={intelData} refreshing={refreshing} onRefresh={onRefresh} />
        </View>
      )}
    </View>
  );
}
