import React from 'react';
import { View, Text, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { GOLD, GREEN, AMBER, PURPLE, tid, type AdvisorMessage, type Suggestion } from './shared';

const when = (iso?: string) => (iso ? new Date(iso).toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' }) : '');

export const suggestionTitle = (s: Suggestion) => (s.kind === 'set_next_action' ? 'Set Next Best Action' : s.kind === 'park_idea' ? `Park idea: ${s.idea_title}` : `Move idea to validation: ${s.idea_title}`);
export const suggestionBody = (s: Suggestion) => (s.kind === 'set_next_action' ? s.text : s.why);

// One proposed change: the founder sees exactly what would happen and confirms it; nothing is applied until then.
export const SuggestionCard = ({ s, colors, onApply, index }: { s: Suggestion; colors: any; onApply: (s: Suggestion) => void; index: number }) => {
  const color = s.kind === 'set_next_action' ? GOLD : s.kind === 'park_idea' ? PURPLE : AMBER;
  return (
    <View style={{ borderRadius: 14, borderWidth: 1, borderColor: color, backgroundColor: color + '14', padding: 12, gap: 6 }} {...tid(`cc-suggestion-${index}`)}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
        <Ionicons name="sparkles" size={14} color={color} />
        <Text style={{ fontSize: 11, fontWeight: '800', color, letterSpacing: 0.8 }}>PROPOSED CHANGE · NEEDS YOUR OK</Text>
      </View>
      <Text style={{ fontSize: 14.5, fontWeight: '800', color: colors.text }}>{suggestionTitle(s)}</Text>
      <Text style={{ fontSize: 13, color: colors.text, lineHeight: 18 }}>{suggestionBody(s)}</Text>
      {s.kind === 'set_next_action' && !!s.why && <Text style={{ fontSize: 12, color: colors.textSecondary }}>Why: {s.why}</Text>}
      <TouchableOpacity onPress={() => onApply(s)} style={{ alignSelf: 'flex-start', paddingHorizontal: 14, height: 32, borderRadius: 16, backgroundColor: color, alignItems: 'center', justifyContent: 'center' }} {...tid(`cc-suggestion-${index}-review`)}>
        <Text style={{ fontSize: 12.5, fontWeight: '800', color: '#1C1C1E' }}>Review and confirm</Text>
      </TouchableOpacity>
    </View>
  );
};

export const MessageBubble = ({ m, colors, onApply, label, color = GOLD }: { m: AdvisorMessage; colors: any; onApply: (s: Suggestion) => void; label?: string; color?: string }) => {
  const mine = m.role === 'founder';
  return (
    <View style={{ alignSelf: mine ? 'flex-end' : 'flex-start', maxWidth: '92%', gap: 8 }} {...tid(`cc-msg-${m.role}`)}>
      <View style={{ borderRadius: 16, borderTopRightRadius: mine ? 4 : 16, borderTopLeftRadius: mine ? 16 : 4, padding: 12, backgroundColor: mine ? GOLD : colors.card, borderWidth: mine ? 0 : 1, borderColor: mine ? 'transparent' : color === GOLD ? colors.border : color + '66' }}>
        {!mine && <Text style={{ fontSize: 10.5, fontWeight: '800', color, letterSpacing: 1, marginBottom: 4 }} {...tid('cc-msg-role')}>{(label || 'ADVISOR').toUpperCase()}{m.voice ? ' · SPOKEN' : ''}</Text>}
        <Text style={{ fontSize: 15, lineHeight: 22, color: mine ? '#1C1C1E' : colors.text }} selectable>{m.text}</Text>
        <Text style={{ fontSize: 10.5, color: mine ? '#1C1C1E99' : colors.textSecondary, marginTop: 6, textAlign: 'right' }}>{when(m.at)}{!mine && m.usage?.ms ? ` · ${(m.usage.ms / 1000).toFixed(1)}s` : ''}</Text>
      </View>
      {!mine && (m.suggestions || []).map((s, i) => <SuggestionCard key={i} s={s} colors={colors} onApply={onApply} index={i} />)}
    </View>
  );
};

export const StarterChips = ({ questions, colors, onPick }: { questions: string[]; colors: any; onPick: (q: string) => void }) => (
  <View style={{ gap: 8 }} {...tid('cc-advisor-starters')}>
    <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 1 }}>ASK ABOUT TODAY</Text>
    <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
      {questions.map((q, i) => (
        <TouchableOpacity key={q} onPress={() => onPick(q)} style={{ paddingHorizontal: 12, paddingVertical: 8, borderRadius: 14, borderWidth: 1, borderColor: GOLD + '88', backgroundColor: colors.card }} {...tid(`cc-starter-${i}`)}>
          <Text style={{ fontSize: 13, color: colors.text }}>{q}</Text>
        </TouchableOpacity>
      ))}
    </View>
  </View>
);

export const ThreadRow = ({ c, active, colors, onPress }: { c: { id: string; title: string; last_text: string; message_count: number; source: string; updated_at: string }; active: boolean; colors: any; onPress: () => void }) => (
  <TouchableOpacity onPress={onPress} style={{ padding: 12, borderRadius: 14, backgroundColor: active ? GOLD + '22' : colors.card, borderWidth: 1, borderColor: active ? GOLD : colors.border, gap: 3 }} {...tid(`cc-thread-${c.id}`)}>
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
      <Ionicons name={c.source === 'voice' ? 'mic' : 'chatbubble-ellipses'} size={13} color={active ? GOLD : colors.textSecondary} />
      <Text style={{ flex: 1, fontSize: 13.5, fontWeight: '800', color: colors.text }} numberOfLines={1}>{c.title}</Text>
    </View>
    {!!c.last_text && <Text style={{ fontSize: 12, color: colors.textSecondary }} numberOfLines={2}>{c.last_text}</Text>}
    <Text style={{ fontSize: 11, color: colors.textSecondary }}>{c.message_count} messages · {new Date(c.updated_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}</Text>
  </TouchableOpacity>
);

export const FactsLine = ({ facts, colors }: { facts?: string[]; colors: any }) => (facts?.length ? (
  <View style={{ flexDirection: 'row', alignItems: 'flex-start', gap: 6 }} {...tid('cc-facts-line')}>
    <Ionicons name="shield-checkmark" size={13} color={GREEN} style={{ marginTop: 2 }} />
    <Text style={{ flex: 1, fontSize: 11.5, color: colors.textSecondary, lineHeight: 16 }}>Grounded in: {facts.join(' · ')}</Text>
  </View>
) : null);
