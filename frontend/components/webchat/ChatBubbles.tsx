import React from 'react';
import { View, Text } from 'react-native';
import { GOLD, tid } from '../inbox/ownership';

export type ChatMsg = { role: 'visitor' | 'jessi' | 'rep' | 'system' | 'note'; text: string; who?: string; uid?: string; at?: string | null };

const hhmm = (iso?: string | null) => {
  if (!iso) return '';
  const d = new Date(iso);
  return isNaN(d.getTime()) ? '' : d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
};

// Rep-side transcript: visitor left, Jessi grey, rep gold, system/notes centered.
export const ChatBubbles = ({ messages, colors, meId }: { messages: ChatMsg[]; colors: any; meId?: string }) => (
  <View style={{ gap: 8, padding: 14 }} {...tid('webchat-messages')}>
    {messages.map((m, i) => {
      if (m.role === 'system' || m.role === 'note') {
        return (
          <Text key={i} style={{ alignSelf: 'center', fontSize: 12, color: m.role === 'note' ? GOLD : colors.textSecondary, textAlign: 'center', paddingHorizontal: 12 }} {...tid(`webchat-msg-${i}`)}>
            {m.role === 'note' ? 'Only you see this · ' : ''}{m.text}
          </Text>
        );
      }
      const visitor = m.role === 'visitor', rep = m.role === 'rep';
      return (
        <View key={i} style={{ alignSelf: visitor ? 'flex-start' : 'flex-end', maxWidth: '84%' }} {...tid(`webchat-msg-${i}`)}>
          <View style={{ paddingVertical: 9, paddingHorizontal: 12, borderRadius: 14, backgroundColor: visitor ? colors.surface : rep ? GOLD : colors.card, borderWidth: rep ? 0 : 1, borderColor: colors.border,
            borderBottomLeftRadius: visitor ? 4 : 14, borderBottomRightRadius: visitor ? 14 : 4 }}>
            {!visitor ? <Text style={{ fontSize: 11, fontWeight: '800', color: rep ? '#111' : colors.textSecondary, opacity: 0.75, marginBottom: 2 }}>{rep ? (m.uid && meId && m.uid === meId ? 'You' : m.who || 'Team') : 'Jessi'}</Text> : null}
            <Text style={{ fontSize: 15, lineHeight: 20, color: rep ? '#111' : colors.text }}>{m.text}</Text>
          </View>
          <Text style={{ fontSize: 10, color: colors.textSecondary, marginTop: 2, textAlign: visitor ? 'left' : 'right' }}>{hhmm(m.at)}</Text>
        </View>
      );
    })}
  </View>
);
