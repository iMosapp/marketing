import React from 'react';
import { View, Text, TouchableOpacity, ActivityIndicator } from 'react-native';
import { useThemeStore } from '../../store/themeStore';
import { showAlert } from '../../services/alert';
import { Card, Row, Pill, PilotStatus, GOLD, GREEN, RED, usd, tid } from './shared';

type Props = { s: PilotStatus; busy: boolean; onRollout: (on: boolean) => Promise<void> };

// Voice limits for every account at once (accounts with their own settings keep them). Super admins are never capped.
export const RolloutCard = ({ s, busy, onRollout }: Props) => {
  const { colors } = useThemeStore();
  const r = s.rollout;
  const on = r.all_accounts;
  const confirm = () => showAlert(
    on ? 'Turn off for every account?' : 'Turn on for every account?',
    on ? 'Accounts go back to the old caps unless they were switched on one by one. Usage history is kept.'
      : `Every rep gets ${r.premium_min} min of GPT-Live then ${r.backup_min} min of Mini a day, and each account stops at ${usd(r.hard_usd)} a month. Super admins are never capped. Your pilot limits go back to these defaults.`,
    [{ text: 'Cancel', style: 'cancel' }, { text: on ? 'Turn off' : 'Turn on', style: on ? 'destructive' : 'default', onPress: () => { onRollout(!on); } }],
  );
  return (
    <Card title="EVERY ACCOUNT" testID="rollout-card">
      <Pill text={on ? 'ON FOR EVERY ACCOUNT' : 'OFF'} tone={on ? GREEN : '#8E8E93'} testID="rollout-status-pill" />
      <View style={{ marginTop: 10 }}>
        <Row label="GPT-Live per rep / day" value={`${r.premium_min} min`} testID="rollout-premium" />
        <Row label="Mini per rep / day (after GPT-Live)" value={`${r.backup_min} min`} testID="rollout-backup" />
        <Row label="Cap per account / month" value={usd(r.hard_usd)} testID="rollout-cap" />
        <Row label="Super admins" value="Never capped" tone={GOLD} testID="rollout-super-admins" />
      </View>
      <Text style={{ color: colors.textSecondary, fontSize: 11, marginTop: 8 }}>Accounts with their own settings keep them. The kill switch still works per account.</Text>
      <TouchableOpacity onPress={confirm} disabled={busy} style={{ marginTop: 12, borderRadius: 24, paddingVertical: 13, alignItems: 'center', backgroundColor: on ? 'transparent' : GOLD, borderWidth: on ? 1 : 0, borderColor: RED, opacity: busy ? 0.5 : 1 }} {...tid('rollout-toggle-btn')}>
        {busy ? <ActivityIndicator color={on ? RED : '#0B0B0D'} /> : <Text style={{ color: on ? RED : '#0B0B0D', fontWeight: '800', fontSize: 15 }}>{on ? 'Turn off for every account' : 'Turn on for every account'}</Text>}
      </TouchableOpacity>
    </Card>
  );
};
