import React from 'react';
import { View, Text } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { GOLD, tid, initials, type Persona, type Training } from './shared';

const TOKEN = /(\{[a-z_]+\})/g;

// Script text: [stage directions] in gold caps, {merge_fields} highlighted, quoted objections bold.
export const ScriptBody = ({ text, colors, testID }: { text: string; colors: any; testID?: string }) => (
  <View style={{ gap: 10 }} {...(testID ? tid(testID) : {})}>
    {text.split('\n').filter((p, i, arr) => p.trim() || (arr[i - 1] || '').trim()).map((para, i) => {
      const t = para.trim();
      if (!t) return <View key={i} style={{ height: 2 }} />;
      if (t.startsWith('[') && t.endsWith(']')) {
        return <Text key={i} style={{ fontSize: 11.5, fontWeight: '800', color: GOLD, letterSpacing: 1, marginTop: 4 }}>{t.slice(1, -1).toUpperCase()}</Text>;
      }
      const quoted = t.startsWith('"');
      return (
        <Text key={i} style={{ fontSize: 16, lineHeight: 25, color: colors.text, fontWeight: quoted ? '800' : '500' }}>
          {t.split(TOKEN).map((part, j) => TOKEN.test(part)
            ? <Text key={j} style={{ color: GOLD, fontWeight: '800', backgroundColor: GOLD + '1A' }}>{part.slice(1, -1).replace(/_/g, ' ')}</Text>
            : part)}
        </Text>
      );
    })}
  </View>
);

export const SuccessPoints = ({ points, colors, hits }: { points: string[]; colors: any; hits?: Record<string, boolean> }) => (
  <View style={{ gap: 8 }} {...tid('script-success-points')}>
    {points.map((p, i) => {
      const state = hits ? hits[p] : undefined;
      const icon = state === true ? 'checkmark-circle' : state === false ? 'close-circle' : 'ellipse-outline';
      const color = state === true ? '#34C759' : state === false ? '#FF3B30' : GOLD;
      return (
        <View key={i} style={{ flexDirection: 'row', alignItems: 'flex-start', gap: 10 }}>
          <Ionicons name={icon as any} size={19} color={color} style={{ marginTop: 1 }} />
          <Text style={{ flex: 1, fontSize: 14.5, lineHeight: 20, color: colors.text, fontWeight: '600' }}>{p}</Text>
        </View>
      );
    })}
  </View>
);

export const PersonaCard = ({ persona, colors, compact }: { persona: Persona; colors: any; compact?: boolean }) => (
  <View style={{ backgroundColor: colors.card, borderRadius: 16, borderWidth: 1, borderColor: colors.border, padding: 14, flexDirection: 'row', gap: 12 }} {...tid('script-persona')}>
    <View style={{ width: 46, height: 46, borderRadius: 23, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center' }}>
      <Text style={{ fontSize: 17, fontWeight: '800', color: '#111' }}>{initials(persona.name)}</Text>
    </View>
    <View style={{ flex: 1 }}>
      <Text style={{ fontSize: 11, fontWeight: '800', color: GOLD, letterSpacing: 1 }}>YOU'LL BE TALKING TO</Text>
      <Text style={{ fontSize: 16, fontWeight: '800', color: colors.text, marginTop: 2 }}>{persona.name}</Text>
      <Text style={{ fontSize: 13, color: colors.textSecondary, lineHeight: 18, marginTop: 2 }}>{persona.summary}</Text>
      {!compact && !!persona.objections?.length && (
        <View style={{ marginTop: 8, gap: 3 }}>
          <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.5 }}>EXPECT TO HEAR</Text>
          {persona.objections.map((o, i) => <Text key={i} style={{ fontSize: 13, color: colors.text, fontStyle: 'italic' }}>"{o}"</Text>)}
        </View>
      )}
    </View>
  </View>
);

export const TrainingBody = ({ training, colors }: { training: Training; colors: any }) => (
  <View style={{ gap: 12 }} {...tid('script-training-body')}>
    <View style={{ backgroundColor: GOLD + '14', borderLeftWidth: 3, borderLeftColor: GOLD, borderRadius: 12, padding: 12 }}>
      <Text style={{ fontSize: 11, fontWeight: '800', color: GOLD, letterSpacing: 1, marginBottom: 4 }}>HOOK · FIRST 5 SECONDS</Text>
      <Text style={{ fontSize: 16, fontWeight: '700', color: colors.text, lineHeight: 23 }}>{training.hook}</Text>
    </View>
    {training.scenes.map((s, i) => (
      <View key={i} style={{ backgroundColor: colors.card, borderRadius: 14, borderWidth: 1, borderColor: colors.border, padding: 14, gap: 8 }}>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
          <View style={{ width: 26, height: 26, borderRadius: 13, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center' }}><Text style={{ fontSize: 12, fontWeight: '800', color: '#111' }}>{i + 1}</Text></View>
          <Text style={{ flex: 1, fontSize: 12, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.5 }}>SCENE {i + 1} · {s.seconds}s</Text>
        </View>
        <View style={{ flexDirection: 'row', gap: 8 }}><Ionicons name="phone-portrait-outline" size={15} color={colors.textSecondary} style={{ marginTop: 3 }} /><Text style={{ flex: 1, fontSize: 13.5, color: colors.textSecondary, lineHeight: 19 }}>{s.on_screen}</Text></View>
        <View style={{ flexDirection: 'row', gap: 8 }}><Ionicons name="mic-outline" size={15} color={GOLD} style={{ marginTop: 3 }} /><Text style={{ flex: 1, fontSize: 16, color: colors.text, lineHeight: 24, fontWeight: '600' }}>{s.voice_over}</Text></View>
      </View>
    ))}
    <View style={{ backgroundColor: colors.card, borderRadius: 12, padding: 12, borderWidth: 1, borderColor: GOLD + '66' }}>
      <Text style={{ fontSize: 11, fontWeight: '800', color: GOLD, letterSpacing: 1, marginBottom: 4 }}>CLOSING LINE</Text>
      <Text style={{ fontSize: 15, fontWeight: '700', color: colors.text, lineHeight: 22 }}>{training.cta}</Text>
    </View>
    {!!training.notes && <Text style={{ fontSize: 12.5, color: colors.textSecondary, fontStyle: 'italic', lineHeight: 18 }}>Recording tip: {training.notes}</Text>}
  </View>
);
