import React from 'react';
import { Text, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { showAlert } from '../../services/alert';
import { GOLD, tid } from '../scripts/shared';
import { liveSupported, LIVE_UNSUPPORTED_TITLE, LIVE_UNSUPPORTED_BODY } from '../../hooks/useLiveJessi';
import { useLiveJessiLauncher } from './LiveJessiProvider';
import { useLiveConfig } from './useLiveConfig';

// Sits in the Do-this-next card: Jessi walks the rep through the day stop by stop (replies waiting, overdue touchpoints, today's 3, hot leads).
export const WalkMyDayButton = ({ color, onDone }: { color: string; onDone?: () => void }) => {
  const router = useRouter();
  const { config, reload } = useLiveConfig();
  const jessi = useLiveJessiLauncher();
  if (!config?.available || !config.configured) return null;

  const press = (e: any) => {
    e?.stopPropagation?.();
    if (!liveSupported()) {
      showAlert(LIVE_UNSUPPORTED_TITLE, `${LIVE_UNSUPPORTED_BODY} Opening the typed Ask Jessi instead.`, [{ text: 'OK', onPress: () => router.push('/jessie' as any) }]);
      return;
    }
    jessi.open({
      options: { mode: 'assistant', overrides: { walkthrough: true } },
      title: 'Your day with Jessi',
      hint: 'Jessi runs your board top to bottom. Say "draft it", "done", "skip" or "next" and she moves on.',
      onClose: () => { reload(); onDone?.(); },
    });
  };

  return (
    <TouchableOpacity onPress={press} activeOpacity={0.8} hitSlop={6}
      style={{ marginTop: 12, alignSelf: 'flex-start', flexDirection: 'row', alignItems: 'center', gap: 7, borderRadius: 16, paddingHorizontal: 12, paddingVertical: 7, backgroundColor: `${GOLD}22`, borderWidth: 1, borderColor: `${GOLD}66` }}
      {...tid('walk-my-day-btn')}>
      <Ionicons name="mic" size={14} color={GOLD} />
      <Text style={{ fontSize: 12.5, fontWeight: '800', color: GOLD }}>{jessi.active ? 'Jessi is on it' : 'Walk me through it'}</Text>
      <Ionicons name="chevron-forward" size={13} color={color} style={{ opacity: 0.7 }} />
    </TouchableOpacity>
  );
};
