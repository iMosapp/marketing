import React from 'react';
import { Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

const GOLD = '#C9A962';
const CITE_RE = /\[([TCVEK])(\d+)(?:@(\d+(?::\d{2})?))?\]/g;

export type Citation = {
  id: string; token: string; kind: 'text' | 'call' | 'voice_note' | 'event' | 'task'; label: string; snippet?: string;
  conversation_id?: string | null; message_id?: string; call_sid?: string | null; has_recording?: boolean; seek_seconds?: number | null;
  duration_s?: number; audio_url?: string | null; event_type?: string; task_id?: string; completed?: boolean;
};

const chipMeta = (c: Citation) => {
  switch (c.kind) {
    case 'call': return { icon: 'play' as const, label: c.seek_seconds != null ? `Call ${Math.floor(c.seek_seconds / 60)}:${String(c.seek_seconds % 60).padStart(2, '0')}` : 'Call' };
    case 'text': return { icon: 'chatbubble' as const, label: 'Text' };
    case 'voice_note': return { icon: 'mic' as const, label: 'Voice note' };
    case 'task': return { icon: 'checkbox' as const, label: 'Task' };
    default: return { icon: 'flash' as const, label: 'Event' };
  }
};

// Renders Jessi's answer with inline [C3@4:12] style markers turned into tappable source chips.
export const AnswerText = ({ content, citations, colors, onCite }: { content: string; citations: Citation[]; colors: any; onCite: (c: Citation) => void }) => {
  const byToken: Record<string, Citation> = {};
  citations.forEach(c => { byToken[c.token] = c; });
  const lines = content.split('\n');
  return (
    <View style={{ gap: 6 }}>
      {lines.map((line, li) => {
        if (!line.trim()) return null;
        const parts: React.ReactNode[] = [];
        let last = 0;
        let m: RegExpExecArray | null;
        const re = new RegExp(CITE_RE.source, 'g');
        while ((m = re.exec(line))) {
          if (m.index > last) parts.push(<Text key={`t${li}-${last}`}>{line.slice(last, m.index)}</Text>);
          const c = byToken[m[0]];
          if (c) {
            const meta = chipMeta(c);
            parts.push(
              <Text key={`c${li}-${m.index}`} onPress={() => onCite(c)} suppressHighlighting
                style={{ fontSize: 12, fontWeight: '800', color: GOLD, backgroundColor: GOLD + '22', borderRadius: 6, overflow: 'hidden' }}
                testID={`ask-cite-${c.id}`} dataSet={{ testid: `ask-cite-${c.id}` } as any}>
                {' '}<Ionicons name={meta.icon} size={11} color={GOLD} /> {meta.label}{' '}
              </Text>
            );
          }
          last = m.index + m[0].length;
        }
        if (last < line.length) parts.push(<Text key={`t${li}-end`}>{line.slice(last)}</Text>);
        return (
          <Text key={li} style={{ fontSize: 15, color: colors.text, lineHeight: 23 }}>
            {parts}
          </Text>
        );
      })}
    </View>
  );
};
