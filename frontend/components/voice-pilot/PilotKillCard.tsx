import React from 'react';
import { Text, TouchableOpacity, ActivityIndicator } from 'react-native';
import { useThemeStore } from '../../store/themeStore';
import { showAlert } from '../../services/alert';
import { Card, PilotStatus, GREEN, RED, tid } from './shared';

type Props = { s: PilotStatus; busy: boolean; onKill: () => Promise<void>; onResume: () => Promise<void> };

// The kill switch: no new voice sessions on the account and every open one is hung up on the provider side right now.
export const PilotKillCard = ({ s, busy, onKill, onResume }: Props) => {
  const { colors } = useThemeStore();
  const killed = s.policy.killed;
  const open = s.active.length;
  const confirmKill = () => showAlert('Stop the pilot now?', `New voice sessions are refused and ${open} open session${open === 1 ? '' : 's'} ${open === 1 ? 'is' : 'are'} ended immediately. You can resume any time.`,
    [{ text: 'Cancel', style: 'cancel' }, { text: 'Stop now', style: 'destructive', onPress: () => { onKill(); } }]);
  return (
    <Card title="KILL SWITCH" testID="pilot-kill-card">
      <Text style={{ color: colors.textSecondary, fontSize: 12, marginBottom: 12 }}>
        {killed ? 'Live Jessi is paused for this account: nobody can start a voice session and the app offers typed Jessi instead.' : 'Stops new sessions and terminates active ones, server side. The app shows "Paused by the account owner" and offers typed Jessi.'}
      </Text>
      {killed ? (
        <TouchableOpacity onPress={() => onResume()} disabled={busy} style={{ borderRadius: 24, paddingVertical: 13, alignItems: 'center', backgroundColor: GREEN, opacity: busy ? 0.5 : 1 }} {...tid('pilot-resume-btn')}>
          {busy ? <ActivityIndicator color="#0B0B0D" /> : <Text style={{ color: '#0B0B0D', fontWeight: '800', fontSize: 15 }}>Resume the pilot</Text>}
        </TouchableOpacity>
      ) : (
        <TouchableOpacity onPress={confirmKill} disabled={busy || !s.enrolled} style={{ borderRadius: 24, paddingVertical: 13, alignItems: 'center', backgroundColor: RED, opacity: busy || !s.enrolled ? 0.5 : 1 }} {...tid('pilot-kill-btn')}>
          {busy ? <ActivityIndicator color="#fff" /> : <Text style={{ color: '#fff', fontWeight: '800', fontSize: 15 }}>Stop pilot now{open ? ` · end ${open} open` : ''}</Text>}
        </TouchableOpacity>
      )}
    </Card>
  );
};
