import React from 'react';
import { View, Text, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { GOLD, tid } from '../inbox/ownership';
import { Section, Label, Hint } from '../inbox/InboxEditorParts';
import { Chips, Field } from './parts';

export type PageRule = { match: string; greeting: string; door: '' | 'text' | 'call' | 'chat' };
type Props = { rules: PageRule[]; onChange: (rules: PageRule[]) => void; doors: any; colors: any; onPreview: (path: string) => void; previewPath: string };

const SUGGESTED: PageRule[] = [
  { match: '/inventory', greeting: 'Looking at a specific vehicle? Ask Jessi if it is still here.', door: 'chat' },
  { match: '/service', greeting: 'Need service? Text us and we will get you booked.', door: 'text' },
  { match: '/specials', greeting: 'Want the details on a special? Text us, we reply in minutes.', door: 'text' },
  { match: '/finance', greeting: 'Payment questions? A real person can call you right now.', door: 'call' },
  { match: 'pricing', greeting: 'Questions about a price? Text us and a person answers.', door: 'text' },
];

export const PageRulesSection = ({ rules, onChange, doors, colors, onPreview, previewPath }: Props) => {
  const doorOptions = [{ value: '', label: 'Let them choose', icon: 'apps-outline' }, ...(['text', 'call', 'chat'] as const).filter(d => doors?.[d]?.on).map(d => ({ value: d, label: doors[d].label || d, icon: d === 'text' ? 'phone-portrait-outline' : d === 'call' ? 'call-outline' : 'chatbubble-outline' }))];
  const patch = (i: number, p: Partial<PageRule>) => onChange(rules.map((r, j) => (j === i ? { ...r, ...p } : r)));
  const unused = SUGGESTED.filter(s => !rules.some(r => r.match.toLowerCase() === s.match));
  return (
    <Section colors={colors} testId="widget-section-page-rules">
      <Label colors={colors}>Page greetings</Label>
      <Hint colors={colors}>Say something different depending on the page. First matching rule wins, and it can open a specific door. Rules beat the greeting above on those pages.</Hint>
      {rules.length === 0 ? <Text style={{ fontSize: 13, color: colors.textSecondary }} {...tid('widget-page-rules-empty')}>No page rules yet. Visitors see the same greeting everywhere.</Text> : null}
      {rules.map((r, i) => (
        <View key={i} style={{ padding: 10, borderRadius: 12, backgroundColor: colors.surface, marginBottom: 8, gap: 4 }} {...tid(`widget-page-rule-${i}`)}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
            <View style={{ flex: 1 }}>
              <Field label="When the page address contains" value={r.match} onChange={v => patch(i, { match: v })} placeholder="/inventory" colors={colors} testId={`widget-page-rule-${i}-match`} maxLength={120} top={false} />
            </View>
            <TouchableOpacity onPress={() => onChange(rules.filter((_, j) => j !== i))} hitSlop={8} style={{ marginTop: 20 }} {...tid(`widget-page-rule-${i}-remove`)}><Ionicons name="trash-outline" size={20} color="#FF3B30" /></TouchableOpacity>
          </View>
          <Field label="Greeting on that page" value={r.greeting} onChange={v => patch(i, { greeting: v })} multiline colors={colors} testId={`widget-page-rule-${i}-greeting`} maxLength={200} />
          <Label colors={colors} top>Tapping it opens</Label>
          <Chips options={doorOptions} value={r.door || ''} onChange={v => patch(i, { door: v as PageRule['door'] })} colors={colors} testId={`widget-page-rule-${i}-door`} />
          <TouchableOpacity onPress={() => onPreview(previewPath === r.match ? '' : r.match)} disabled={!r.match.trim()} style={{ flexDirection: 'row', alignItems: 'center', gap: 6, alignSelf: 'flex-start', paddingVertical: 8, opacity: r.match.trim() ? 1 : 0.5 }} {...tid(`widget-page-rule-${i}-preview`)}>
            <Ionicons name={previewPath === r.match ? 'eye-off-outline' : 'eye-outline'} size={16} color={GOLD} />
            <Text style={{ fontSize: 13, fontWeight: '700', color: GOLD }}>{previewPath === r.match ? 'Back to the normal preview' : 'Preview this page'}</Text>
          </TouchableOpacity>
        </View>
      ))}
      {rules.length < 12 ? (
        <TouchableOpacity onPress={() => onChange([...rules, { match: '', greeting: '', door: '' }])} style={{ flexDirection: 'row', alignItems: 'center', gap: 6, paddingVertical: 8 }} {...tid('widget-page-rule-add')}>
          <Ionicons name="add-circle-outline" size={20} color={GOLD} />
          <Text style={{ fontSize: 14, fontWeight: '700', color: GOLD }}>Add a page rule</Text>
        </TouchableOpacity>
      ) : null}
      {unused.length ? (
        <View style={{ marginTop: 6 }}>
          <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 1, marginBottom: 6 }}>QUICK ADD</Text>
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>
            {unused.map(s => (
              <TouchableOpacity key={s.match} onPress={() => onChange([...rules, { ...s, door: doors?.[s.door]?.on ? s.door : '' }])} style={{ paddingHorizontal: 12, height: 32, borderRadius: 16, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, justifyContent: 'center' }} {...tid(`widget-page-rule-suggest-${s.match.replace('/', '')}`)}>
                <Text style={{ fontSize: 12, fontWeight: '700', color: colors.text }}>{s.match}</Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>
      ) : null}
    </Section>
  );
};
