/**
 * JessiCard — the one gold card on the contact screen: Jessi's one-line brief (tap to unfold the full briefing)
 * and the "Ask" button that opens the grounded chat over every text, call and voice note.
 */
import React, { useMemo, useState } from 'react';
import { View, Text, TouchableOpacity, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import IntelBriefingCard, { parseSections } from './IntelBriefingCard';

const GOLD = '#C9A962';

export default function JessiCard({ colors, intelData, refreshing, onRefresh, firstName, onAsk, userId, contactId, onUpdate, onDetailsChanged }: any) {
  const [expanded, setExpanded] = useState(false);
  const summary: string = intelData?.summary || '';
  const line = useMemo(() => {
    const sections = parseSections(summary);
    const next = (sections['Before Your Next Interaction'] || [])[0];
    const take = (sections['Quick Take'] || []).join(' ');
    return (next || take || summary).replace(/\s+/g, ' ').trim();
  }, [summary]);

  return (
    <View style={{ marginHorizontal: 16, marginBottom: 14, borderRadius: 16, borderWidth: 1, borderColor: `${GOLD}55`, backgroundColor: `${GOLD}12`, overflow: 'hidden' }} testID="jessi-card" dataSet={{ testid: 'jessi-card' } as any}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, paddingHorizontal: 14, paddingTop: 12 }}>
        {refreshing && !summary ? <ActivityIndicator size="small" color={GOLD} /> : <Ionicons name="sparkles" size={15} color={GOLD} />}
        <Text style={{ flex: 1, fontSize: 11, fontWeight: '800', color: GOLD, textTransform: 'uppercase', letterSpacing: 0.8 }}>Jessi's brief</Text>
        <TouchableOpacity onPress={onAsk} activeOpacity={0.8} style={{ flexDirection: 'row', alignItems: 'center', gap: 5, backgroundColor: GOLD, borderRadius: 999, paddingHorizontal: 12, paddingVertical: 6 }} testID="contact-ask-jessi-btn" dataSet={{ testid: 'contact-ask-jessi-btn' } as any}>
          <Ionicons name="chatbubble-ellipses" size={13} color="#111" />
          <Text style={{ fontSize: 12.5, fontWeight: '800', color: '#111' }}>Ask about {firstName || 'them'}</Text>
        </TouchableOpacity>
      </View>
      <TouchableOpacity onPress={() => setExpanded(e => !e)} activeOpacity={0.75} style={{ flexDirection: 'row', alignItems: 'flex-start', gap: 8, paddingHorizontal: 14, paddingTop: 8, paddingBottom: 12 }} testID="intel-teaser" dataSet={{ testid: 'intel-teaser' } as any}>
        <Text style={{ flex: 1, fontSize: 15, lineHeight: 21, color: colors.text }} numberOfLines={expanded ? undefined : 2}>
          {summary ? line : refreshing ? 'Reading every text, call and voice note...' : `Nothing yet. Texts, calls and voice notes teach Jessi about ${firstName || 'this customer'}.`}
        </Text>
        {!!summary && <Ionicons name={expanded ? 'chevron-up' : 'chevron-down'} size={18} color={GOLD} style={{ marginTop: 2 }} />}
      </TouchableOpacity>
      {expanded && !!summary && (
        <View style={{ borderTopWidth: 1, borderTopColor: `${GOLD}33` }} testID="intel-teaser-expanded" dataSet={{ testid: 'intel-teaser-expanded' } as any}>
          <IntelBriefingCard colors={colors} intelData={intelData} refreshing={refreshing} onRefresh={onRefresh} userId={userId} contactId={contactId} onUpdate={onUpdate} onDetailsChanged={onDetailsChanged} embedded />
        </View>
      )}
    </View>
  );
}
