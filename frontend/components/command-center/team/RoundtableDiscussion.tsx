import React, { useState } from 'react';
import { View, Text, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Label } from '../../mystery-shops/shared';
import { Card, Eyebrow, Pill } from '../CcShell';
import { Bullets, Monogram } from './Roster';
import { GREEN, RED, AMBER, tid, execColor, execShort, type Executive, type Roundtable } from '../shared';

const CONF: Record<string, string> = { high: GREEN, medium: AMBER, low: RED };

// THE FULL DISCUSSION: each executive's independent assessment and what they said to each other in the challenge round. Collapsed per executive.
export const RoundtableDiscussion = ({ rt, execs, colors }: { rt: Roundtable; execs: Executive[]; colors: any }) => {
  const [open, setOpen] = useState<string | null>(null);
  const done = rt.participants.filter(p => rt.assessments[p.key]);
  if (!done.length) return null;
  return (
    <Card colors={colors} testID="cc-discussion">
      <Eyebrow t="THE FULL DISCUSSION" colors={colors} />
      {done.map(p => {
        const a = rt.assessments[p.key];
        const c = rt.challenges[p.key];
        const isOpen = open === p.key;
        return (
          <View key={p.key} style={{ gap: 8, borderTopWidth: 1, borderTopColor: colors.border, paddingTop: 10 }} {...tid(`cc-disc-${p.key}`)}>
            <TouchableOpacity onPress={() => setOpen(isOpen ? null : p.key)} style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }} {...tid(`cc-disc-${p.key}-toggle`)}>
              <Monogram e={p} size={34} />
              <View style={{ flex: 1 }}>
                <Text style={{ fontSize: 14, fontWeight: '800', color: colors.text }}>{p.title}{p.devil_advocate ? " · devil's advocate" : ''}</Text>
                {a.status === 'ok' ? <Text style={{ fontSize: 12.5, color: colors.textSecondary, lineHeight: 17 }} numberOfLines={isOpen ? undefined : 2}>{a.data!.recommendation}</Text> : <Text style={{ fontSize: 12.5, color: RED }}>Did not answer: {a.error}</Text>}
              </View>
              {a.status === 'ok' && <Pill text={`${a.data!.confidence} confidence`} color={CONF[a.data!.confidence] || AMBER} />}
              <Ionicons name={isOpen ? 'chevron-up' : 'chevron-down'} size={16} color={colors.textSecondary} />
            </TouchableOpacity>
            {isOpen && a.status === 'ok' && (
              <View style={{ gap: 10, paddingLeft: 44 }} {...tid(`cc-disc-${p.key}-body`)}>
                <Text style={{ fontSize: 13.5, color: colors.text, lineHeight: 19 }} selectable>{a.data!.perspective}</Text>
                {!!a.data!.evidence.length && <View style={{ gap: 4 }}><Label t="EVIDENCE" colors={colors} /><Bullets items={a.data!.evidence} colors={colors} /></View>}
                {!!a.data!.assumptions.length && <View style={{ gap: 4 }}><Label t="ASSUMPTIONS" colors={colors} /><Bullets items={a.data!.assumptions} colors={colors} /></View>}
                {!!a.data!.risks.length && <View style={{ gap: 4 }}><Label t="RISKS" colors={colors} /><Bullets items={a.data!.risks} colors={colors} /></View>}
                {!!a.data!.dependencies.length && <View style={{ gap: 4 }}><Label t="DEPENDENCIES" colors={colors} /><Bullets items={a.data!.dependencies} colors={colors} /></View>}
                {!!a.data!.limitations.length && <View style={{ gap: 4 }}><Label t="WHAT THEY LACKED" colors={colors} /><Bullets items={a.data!.limitations} colors={colors} /></View>}
                {!!a.data!.questions_for.length && <View style={{ gap: 4 }}><Label t="ASKED OF OTHERS" colors={colors} /><Bullets items={a.data!.questions_for.map(q => `${execShort(execs, q.to)}: ${q.question}`)} colors={colors} /></View>}
                {c?.status === 'ok' && (
                  <View style={{ gap: 8, borderRadius: 12, backgroundColor: colors.bg, padding: 10 }} {...tid(`cc-disc-${p.key}-challenges`)}>
                    <Label t="IN THE CHALLENGE ROUND" colors={colors} />
                    {c.data!.challenges.map((x, i) => (
                      <View key={i} style={{ gap: 2 }}>
                        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}><Ionicons name="flash" size={12} color={x.severity === 'material' ? RED : AMBER} /><Text style={{ fontSize: 12.5, fontWeight: '800', color: colors.text }}>To the {execShort(execs, x.to)}: {x.claim}</Text></View>
                        <Text style={{ fontSize: 12.5, color: colors.text, lineHeight: 17 }}>{x.objection}</Text>
                        {!!x.evidence && <Text style={{ fontSize: 12, color: colors.textSecondary }}>Evidence: {x.evidence}</Text>}
                      </View>
                    ))}
                    {c.data!.agreements.map((x, i) => <Text key={i} style={{ fontSize: 12.5, color: colors.textSecondary, lineHeight: 17 }}><Text style={{ color: GREEN, fontWeight: '800' }}>Agrees with the {execShort(execs, x.with)}:</Text> {x.on}</Text>)}
                    {!!c.data!.position_change && c.data!.position_change.toLowerCase() !== 'none' && <Text style={{ fontSize: 12.5, color: colors.text, lineHeight: 17, fontStyle: 'italic' }}>Changed position: {c.data!.position_change}</Text>}
                    {!!c.data!.missing_dependencies.length && <View style={{ gap: 4 }}><Label t="DEPENDENCIES NOBODY NAMED" colors={colors} /><Bullets items={c.data!.missing_dependencies} colors={colors} /></View>}
                  </View>
                )}
                {c?.status === 'failed' && <Text style={{ fontSize: 12.5, color: RED }}>Challenge round: no answer ({c.error})</Text>}
              </View>
            )}
          </View>
        );
      })}
    </Card>
  );
};
