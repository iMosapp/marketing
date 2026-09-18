/**
 * SnapshotCard — the one gold card: who this is in five lines (drives, last touch, personal, Jessi's next step, numbers).
 * "Full intel" unfolds the complete briefing and the editable Personal Intelligence. Replaces JessiCard + the Details-tab intel + stats.
 */
import React, { useEffect, useMemo, useState } from 'react';
import { View, Text, TouchableOpacity, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import IntelBriefingCard, { parseSections } from './IntelBriefingCard';
import PersonalIntelSection from '../PersonalIntelSection';
import { formatEventTime, getEventTitle, getTimeInSystem, getTimeInSystemLabel } from '../../utils/contactHelpers';

const GOLD = '#C9A962';

function Line({ icon, label, value, colors, gold, testid, lines = 1 }: any) {
  if (!value) return null;
  return (
    <View style={{ flexDirection: 'row', alignItems: 'flex-start', gap: 10, paddingVertical: 5 }} testID={testid} dataSet={{ testid } as any}>
      <Ionicons name={icon} size={14} color={GOLD} style={{ marginTop: 3, width: 16 }} />
      <Text style={{ width: 86, fontSize: 10.5, fontWeight: '800', color: colors.textSecondary, textTransform: 'uppercase', letterSpacing: 0.5, marginTop: 2 }} numberOfLines={1}>{label}</Text>
      <Text style={{ flex: 1, fontSize: 14, lineHeight: 19, color: gold ? GOLD : colors.text, fontWeight: gold ? '600' : '500' }} numberOfLines={lines}>{value}</Text>
    </View>
  );
}

export default function SnapshotCard({ colors, contact, stats, events, intelData, refreshing, onRefresh, firstName, onAsk, userId, contactId, onUpdate, onDetailsChanged, voiceNotesCount }: any) {
  const [expanded, setExpanded] = useState(false);
  const [pd, setPd] = useState<any>(null);

  useEffect(() => {
    if (!userId || !contactId) return;
    let alive = true;
    api.get(`/contacts/${userId}/${contactId}/personal-details`)
      .then(r => { if (alive) setPd(r.data?.personal_details || {}); })
      .catch(() => { if (alive) setPd({}); });
    return () => { alive = false; };
  }, [userId, contactId]);

  const summary: string = intelData?.summary || '';
  const sections = useMemo(() => parseSections(summary), [summary]);
  const jessiLine = ((sections['Before Your Next Interaction'] || [])[0] || (sections['Quick Take'] || []).join(' ') || '').replace(/\s+/g, ' ').trim();

  const drives = contact.vehicle || (pd?.vehicle_purchased ? `${pd.vehicle_purchased}${pd.vehicle_color ? ` (${pd.vehicle_color})` : ''}` : '');
  const last = events?.[0];
  const lastTouch = last ? `${getEventTitle(last) || 'Activity'} · ${formatEventTime(last.timestamp)}` : '';
  const personal = pd ? [
    pd.spouse_name ? `Spouse ${pd.spouse_name}` : '',
    pd.kids?.length ? `Kids ${pd.kids.map((k: any) => k.name).join(', ')}` : '',
    (pd.interests || []).slice(0, 3).join(', '),
    !pd.spouse_name && !pd.kids?.length && !(pd.interests || []).length ? (pd.purchase_context || pd.personal_notes || '') : '',
  ].filter(Boolean).join(' · ') : '';
  const personalLine = personal || (sections['Personal Notes'] || [])[0] || '';
  const rel = stats?.created_at ? `${getTimeInSystem(stats.created_at)} ${getTimeInSystemLabel(stats.created_at)} relationship` : '';
  const numbers = stats ? [
    `${stats.total_touchpoints || 0} touch${stats.total_touchpoints === 1 ? '' : 'es'}`,
    `${stats.messages_sent || 0} text${stats.messages_sent === 1 ? '' : 's'}`,
    stats.link_clicks ? `${stats.link_clicks} link click${stats.link_clicks === 1 ? '' : 's'}` : '',
    voiceNotesCount ? `${voiceNotesCount} memo${voiceNotesCount === 1 ? '' : 's'}` : '',
    rel,
  ].filter(Boolean).join(' · ') : '';
  const jessiValue = summary ? jessiLine : refreshing ? 'Reading every text, call and voice note...' : `Nothing yet. Texts, calls and voice notes teach Jessi about ${firstName || 'this customer'}.`;

  return (
    <View style={{ marginHorizontal: 16, marginBottom: 12, borderRadius: 16, borderWidth: 1, borderColor: `${GOLD}55`, backgroundColor: `${GOLD}10`, overflow: 'hidden' }} testID="snapshot-card" dataSet={{ testid: 'snapshot-card' } as any}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, paddingHorizontal: 14, paddingTop: 12, paddingBottom: 4 }}>
        {refreshing && !summary ? <ActivityIndicator size="small" color={GOLD} /> : <Ionicons name="sparkles" size={15} color={GOLD} />}
        <Text style={{ flex: 1, fontSize: 11, fontWeight: '800', color: GOLD, textTransform: 'uppercase', letterSpacing: 0.8 }}>Snapshot</Text>
        <TouchableOpacity onPress={onAsk} activeOpacity={0.8} style={{ flexDirection: 'row', alignItems: 'center', gap: 5, backgroundColor: GOLD, borderRadius: 999, paddingHorizontal: 12, paddingVertical: 6 }} testID="contact-ask-jessi-btn" dataSet={{ testid: 'contact-ask-jessi-btn' } as any}>
          <Ionicons name="chatbubble-ellipses" size={13} color="#111" />
          <Text style={{ fontSize: 12.5, fontWeight: '800', color: '#111' }}>Ask about {firstName || 'them'}</Text>
        </TouchableOpacity>
      </View>
      <View style={{ paddingHorizontal: 14, paddingBottom: 8 }}>
        <Line icon="car-sport" label="Drives" value={drives} colors={colors} testid="snapshot-line-drives" />
        <Line icon="time" label="Last touch" value={lastTouch} colors={colors} testid="snapshot-line-last-touch" />
        <Line icon="heart" label="Personal" value={personalLine} colors={colors} testid="snapshot-line-personal" lines={2} />
        <Line icon="sparkles" label="Jessi" value={jessiValue} colors={colors} gold testid="snapshot-line-jessi" lines={2} />
        <Line icon="stats-chart" label="Numbers" value={numbers} colors={colors} testid="snapshot-line-numbers" lines={2} />
      </View>
      <TouchableOpacity onPress={() => setExpanded(e => !e)} activeOpacity={0.75} style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingVertical: 9, borderTopWidth: 1, borderTopColor: `${GOLD}33` }} testID="snapshot-toggle" dataSet={{ testid: 'snapshot-toggle' } as any}>
        <Text style={{ fontSize: 12.5, fontWeight: '800', color: GOLD }}>{expanded ? 'Less' : 'Full intel & personal details'}</Text>
        <Ionicons name={expanded ? 'chevron-up' : 'chevron-down'} size={15} color={GOLD} />
      </TouchableOpacity>
      {expanded && (
        <View style={{ borderTopWidth: 1, borderTopColor: `${GOLD}33`, backgroundColor: colors.bg }} testID="snapshot-expanded" dataSet={{ testid: 'snapshot-expanded' } as any}>
          {!!summary && (
            <IntelBriefingCard colors={colors} intelData={intelData} refreshing={refreshing} onRefresh={onRefresh} userId={userId} contactId={contactId} onUpdate={onUpdate} onDetailsChanged={onDetailsChanged} embedded />
          )}
          <View style={{ paddingTop: 12 }}>
            <PersonalIntelSection contactId={contactId} userId={userId} colors={colors} />
          </View>
        </View>
      )}
    </View>
  );
}
