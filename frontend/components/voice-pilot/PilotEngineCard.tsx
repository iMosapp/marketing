import React from 'react';
import { Text, TouchableOpacity } from 'react-native';
import { useThemeStore } from '../../store/themeStore';
import { Card, PilotStatus, GOLD, tid } from './shared';

export type EngineMode = 'live_first' | 'mini_only';
type Props = { s: PilotStatus; busy: boolean; onMode: (mode: EngineMode) => Promise<void> };

const OPTIONS: { key: EngineMode; title: string; hint: string }[] = [
  { key: 'live_first', title: 'GPT-Live first, then Mini', hint: 'Premium minutes first, automatic hand-off to Realtime Mini when they run out (current behaviour).' },
  { key: 'mini_only', title: 'Realtime Mini only', hint: 'Every conversation starts and stays on Mini. Uses the Mini pool only; GPT-Live minutes are left untouched.' },
];

// Founder engine test for this account only. Limits, the $ cap, the ledger and the kill switch work the same on both.
export const PilotEngineCard = ({ s, busy, onMode }: Props) => {
  const { colors } = useThemeStore();
  const cur: EngineMode = s.policy.engine_mode || 'live_first';
  return (
    <Card title="ENGINE TEST (MY ACCOUNT)" testID="pilot-engine-card">
      {OPTIONS.map(o => {
        const on = cur === o.key;
        return (
          <TouchableOpacity key={o.key} disabled={busy || on} onPress={() => onMode(o.key)} {...tid(`pilot-engine-${o.key.replace('_', '-')}`)}
            style={{ borderRadius: 12, borderWidth: 1, borderColor: on ? GOLD : colors.border, backgroundColor: on ? `${GOLD}1A` : colors.bg, padding: 12, marginBottom: 8, opacity: busy ? 0.6 : 1 }}>
            <Text style={{ color: on ? GOLD : colors.text, fontWeight: '800', fontSize: 14 }}>{o.title}{on ? '  ·  active' : ''}</Text>
            <Text style={{ color: colors.textSecondary, fontSize: 11, marginTop: 4 }}>{o.hint}</Text>
          </TouchableOpacity>
        );
      })}
      <Text style={{ color: colors.textSecondary, fontSize: 11 }} {...tid('pilot-engine-note')}>Founder test setting for this account only. Next conversation starts on {s.allowance?.next_engine === 'mini' ? 'Realtime Mini' : s.allowance?.next_engine === 'live' ? 'GPT-Live' : 'nothing (no minutes left)'}.</Text>
    </Card>
  );
};
