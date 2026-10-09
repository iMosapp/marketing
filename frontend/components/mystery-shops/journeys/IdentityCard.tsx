import React from 'react';
import { View, Text, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { fmtPhone, scoreColor, AMBER, GOLD, RED, tid } from '../shared';
import { LEAD_STATUS, untilText } from '../lead-shops/shared';
import { CHANNEL_WORD, type Identity } from './shared';

type Props = { s: Identity; colors: any; onPress: () => void; onRemove?: () => void };

// One virtual customer: who they are, how to reach them, what they want and where their shop stands.
export const IdentityCard = ({ s, colors, onPress, onRemove }: Props) => {
  const p = s.persona;
  const st = LEAD_STATUS[s.status] || { label: s.status, color: AMBER, icon: 'ellipse' };
  return (
    <TouchableOpacity onPress={onPress} style={{ backgroundColor: colors.card, borderRadius: 14, borderWidth: 1, borderColor: s.status === 'draft' ? AMBER + '66' : colors.border, padding: 12, gap: 8 }} {...tid(`identity-${s.id}`)}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
        <View style={{ width: 38, height: 38, borderRadius: 19, backgroundColor: GOLD + '22', alignItems: 'center', justifyContent: 'center' }}><Text style={{ fontSize: 15, fontWeight: '800', color: GOLD }}>{(p.first || '?')[0]}{(p.last || '')[0] || ''}</Text></View>
        <View style={{ flex: 1 }}>
          <Text style={{ fontSize: 15, fontWeight: '800', color: colors.text }} {...tid(`identity-name-${s.id}`)}>{p.name}</Text>
          <Text style={{ fontSize: 12, color: colors.textSecondary }} numberOfLines={1}>{p.phone ? fmtPhone(p.phone) : 'number reserved when armed'} · {p.email}</Text>
        </View>
        {s.status === 'completed' && s.score ? <Text style={{ fontSize: 20, fontWeight: '800', color: scoreColor(s.score.overall) }} {...tid(`identity-score-${s.id}`)}>{s.score.overall}%</Text> : (
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 8, height: 24, borderRadius: 12, backgroundColor: st.color + '22' }} {...tid(`identity-status-${s.id}`)}><Ionicons name={st.icon} size={12} color={st.color} /><Text style={{ fontSize: 11, fontWeight: '800', color: st.color }}>{st.label}{s.status === 'live' ? ` · ${untilText(s.expires_at)}` : ''}</Text></View>
        )}
        {onRemove && s.status === 'draft' && <TouchableOpacity onPress={onRemove} hitSlop={8} {...tid(`identity-remove-${s.id}`)}><Ionicons name="trash-outline" size={18} color={RED} /></TouchableOpacity>}
      </View>
      <Text style={{ fontSize: 13, color: colors.text, lineHeight: 18 }} numberOfLines={2} {...tid(`identity-interest-${s.id}`)}>{p.offering ? `Asking about ${p.offering}. ` : ''}{p.goals || ''}</Text>
      <View style={{ flexDirection: 'row', gap: 6, flexWrap: 'wrap' }}>
        {!!p.timeline && <Pill icon="time-outline" text={p.timeline} colors={colors} testID={`identity-timeline-${s.id}`} />}
        {!!p.channel_prefs?.length && <Pill icon={p.channel_prefs[0] === 'call' ? 'call' : p.channel_prefs[0] === 'email' ? 'mail' : 'chatbubbles'} text={`prefers ${CHANNEL_WORD[p.channel_prefs[0]]?.toLowerCase() || p.channel_prefs[0]}`} colors={colors} testID={`identity-prefs-${s.id}`} />}
        {!!p.questions?.length && <Pill icon="help-circle-outline" text={`${p.questions.length} question${p.questions.length === 1 ? '' : 's'}`} colors={colors} testID={`identity-questions-${s.id}`} />}
        {s.status !== 'draft' && <Pill icon="pulse" text={`${(s.counts?.call || 0) + (s.counts?.text || 0) + (s.counts?.email || 0)} touches`} colors={colors} testID={`identity-touches-${s.id}`} />}
      </View>
      {!!p.personality && <Text style={{ fontSize: 12, color: colors.textSecondary, fontStyle: 'italic' }} numberOfLines={1} {...tid(`identity-personality-${s.id}`)}>{p.personality}</Text>}
    </TouchableOpacity>
  );
};

const Pill = ({ icon, text, colors, testID }: { icon: any; text: string; colors: any; testID: string }) => (
  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 8, height: 22, borderRadius: 11, backgroundColor: colors.border + '88' }} {...tid(testID)}>
    <Ionicons name={icon} size={11} color={colors.textSecondary} /><Text style={{ fontSize: 11, fontWeight: '700', color: colors.textSecondary }}>{text}</Text>
  </View>
);
