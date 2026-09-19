/**
 * Renders a call's AI summary as clean blocks (Summary paragraph, Key details / Next steps bullets). Tolerates legacy
 * summaries that still carry markdown asterisks, bracket tags or leaked prompt lines.
 */
import React from 'react';
import { View, Text } from 'react-native';

export type SummarySection = { title: string; lines: string[] };

const HEADINGS: Record<string, string> = {
  'call summary': 'Summary', summary: 'Summary', overview: 'Summary',
  'key details': 'Key details', details: 'Key details', 'key info': 'Key details', 'key information': 'Key details',
  'follow-up actions': 'Next steps', 'follow up actions': 'Next steps', 'follow-up': 'Next steps', 'follow ups': 'Next steps',
  'next steps': 'Next steps', 'action items': 'Next steps', actions: 'Next steps',
};
const LEAKS = ['list 2-4', 'list 2 to 4', 'be concrete', 'skip any section', 'format your response', 'keep total response', 'under 200 words',
  'under 180 words', '2-3 sentences capturing', 'if mentioned]', 'what they want]', 'concerns raised]', 'urgency or timeframe]', 'anything personal'];
const HEAD_RE = new RegExp('^[#>*_\\-•\\s]*(' + Object.keys(HEADINGS).sort((a, b) => b.length - a.length).map(k => k.replace(/[-]/g, '\\-')).join('|') + ')(?:\\s*[:\\-]\\s*(.*)|\\s*)$', 'i');
const EMPTY_FACT = /^(- )?[^:]{1,40}:\s*(not mentioned|not discussed|n\/?a|none|nothing|unknown|not specified|not stated)?\.?$/i;

export function parseCallSummary(raw: string): SummarySection[] {
  const t = String(raw || '').replace(/\r/g, '').replace(/^\s*\[(voicemail|no answer|busy)\]\s*/i, '').replace(/(\*\*|__|`+)/g, '').replace(/\[[^\]\n]{0,80}\]/g, '');
  const out: SummarySection[] = [];
  let cur: SummarySection = { title: 'Summary', lines: [] };
  for (const rawLine of t.split('\n')) {
    let line = rawLine.trim();
    if (!line) continue;
    const low = line.toLowerCase();
    if (LEAKS.some(k => low.includes(k))) continue;
    const h = HEAD_RE.exec(line);
    if (h) {
      if (cur.lines.length) out.push(cur);
      cur = { title: HEADINGS[h[1].toLowerCase()], lines: [] };
      line = (h[2] || '').trim();
      if (!line) continue;
    }
    line = line.replace(/^\s*(?:[-•*·–]|\d+[.)])\s+/, '').replace(/^#+\s*/, '').trim();
    if (!line || EMPTY_FACT.test(line)) continue;
    cur.lines.push(line);
  }
  if (cur.lines.length) out.push(cur);
  return out;
}

export function summaryPreview(raw: string): string {
  const s = parseCallSummary(raw).find(x => x.title === 'Summary');
  return s ? s.lines.join(' ') : parseCallSummary(raw)[0]?.lines.join(' ') || '';
}

type Props = { text: string; textColor: string; mutedColor: string; accentColor: string; fontSize?: number; testID?: string };

export const CallSummaryView = ({ text, textColor, mutedColor, accentColor, fontSize = 13, testID }: Props) => {
  const sections = parseCallSummary(text);
  if (!sections.length) return null;
  return (
    <View testID={testID}>
      {sections.map((sec, i) => (
        <View key={`${sec.title}-${i}`} style={{ marginTop: i === 0 ? 0 : 10 }} testID={testID ? `${testID}-${sec.title.toLowerCase().replace(/\s+/g, '-')}` : undefined}>
          {sec.title !== 'Summary' && (
            <Text style={{ fontSize: fontSize - 2, fontWeight: '800', color: accentColor, letterSpacing: 0.6, textTransform: 'uppercase', marginBottom: 4 }}>{sec.title}</Text>
          )}
          {sec.title === 'Summary' ? (
            <Text style={{ fontSize, color: textColor, lineHeight: fontSize + 6 }}>{sec.lines.join(' ')}</Text>
          ) : sec.lines.map((l, j) => (
            <View key={j} style={{ flexDirection: 'row', alignItems: 'flex-start', gap: 8, marginBottom: 3 }}>
              <View style={{ width: 5, height: 5, borderRadius: 3, backgroundColor: mutedColor, marginTop: (fontSize + 6) / 2 - 2.5 }} />
              <Text style={{ flex: 1, fontSize, color: textColor, lineHeight: fontSize + 6 }}>{l}</Text>
            </View>
          ))}
        </View>
      ))}
    </View>
  );
};
