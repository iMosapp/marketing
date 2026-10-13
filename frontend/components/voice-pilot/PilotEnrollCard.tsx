import React, { useEffect, useState } from 'react';
import { View, Text, TextInput, TouchableOpacity, ActivityIndicator } from 'react-native';
import { useThemeStore } from '../../store/themeStore';
import { showAlert } from '../../services/alert';
import { Card, PilotStatus, GOLD, RED, tid } from './shared';

type Props = { s: PilotStatus; busy: boolean; onEnroll: (premium_min: number, backup_min: number, hard_usd: number) => Promise<void>; onLeave: () => Promise<void> };

type FieldProps = { label: string; value: string; onChange: (v: string) => void; testID: string; colors: any };
const Field = ({ label, value, onChange, testID, colors }: FieldProps) => (
  <View style={{ flex: 1 }}>
    <Text style={{ color: colors.textSecondary, fontSize: 11, marginBottom: 6 }}>{label}</Text>
    <TextInput value={value} onChangeText={onChange} keyboardType="decimal-pad" {...tid(testID)}
      style={{ backgroundColor: colors.bg, borderRadius: 10, borderWidth: 1, borderColor: colors.border, color: colors.text, padding: 10, fontSize: 15, fontWeight: '700', textAlign: 'center' }} />
  </View>
);

// Enrol (or re-save the limits of) the founder's own account. Nothing here touches any other account.
export const PilotEnrollCard = ({ s, busy, onEnroll, onLeave }: Props) => {
  const { colors } = useThemeStore();
  const p = s.policy;
  const [premium, setPremium] = useState(String(s.enrolled ? p.per_user_daily_premium_min : s.defaults.premium_min));
  const [backup, setBackup] = useState(String(s.enrolled ? p.per_user_daily_backup_min : s.defaults.backup_min));
  const [cap, setCap] = useState(String(s.enrolled && p.account_monthly_hard_usd !== null ? p.account_monthly_hard_usd : s.defaults.hard_usd));
  useEffect(() => {
    if (!s.enrolled) return;
    setPremium(String(p.per_user_daily_premium_min)); setBackup(String(p.per_user_daily_backup_min));
    if (p.account_monthly_hard_usd !== null) setCap(String(p.account_monthly_hard_usd));
  }, [s.enrolled, p.per_user_daily_premium_min, p.per_user_daily_backup_min, p.account_monthly_hard_usd]);

  const valid = Number(premium) >= 1 && Number(backup) >= 1 && Number(cap) > 0;
  const submit = () => onEnroll(Math.round(Number(premium)), Math.round(Number(backup)), Number(cap));
  const leave = () => showAlert('Leave the pilot?', 'Your account goes back to the legacy caps. Any open voice session is ended. Usage history is kept.', [{ text: 'Cancel', style: 'cancel' }, { text: 'Leave pilot', style: 'destructive', onPress: () => { onLeave(); } }]);
  return (
    <Card title={s.enrolled ? 'PILOT LIMITS' : 'ENROL MY ACCOUNT'} testID="pilot-enroll-card">
      <View style={{ flexDirection: 'row', gap: 10 }}>
        <Field label="GPT-Live min / day" value={premium} onChange={setPremium} testID="pilot-premium-input" colors={colors} />
        <Field label="Mini min / day" value={backup} onChange={setBackup} testID="pilot-backup-input" colors={colors} />
        <Field label="Hard cap $ / month" value={cap} onChange={setCap} testID="pilot-cap-input" colors={colors} />
      </View>
      <Text style={{ color: colors.textSecondary, fontSize: 11, marginTop: 8 }}>Per person per day for every user on this account (super admins included). The $ cap is the whole account's estimated spend for the month on both engines; when it is reached nobody can start a voice session.</Text>
      <TouchableOpacity onPress={submit} disabled={busy || !valid} style={{ marginTop: 12, borderRadius: 24, paddingVertical: 13, alignItems: 'center', backgroundColor: GOLD, opacity: busy || !valid ? 0.5 : 1 }} {...tid('pilot-enroll-btn')}>
        {busy ? <ActivityIndicator color="#0B0B0D" /> : <Text style={{ color: '#0B0B0D', fontWeight: '800', fontSize: 15 }}>{s.enrolled ? 'Save limits' : 'Enrol my account only'}</Text>}
      </TouchableOpacity>
      {s.enrolled && (
        <TouchableOpacity onPress={leave} disabled={busy} style={{ marginTop: 10, alignItems: 'center', paddingVertical: 8 }} {...tid('pilot-leave-btn')}>
          <Text style={{ color: RED, fontWeight: '700', fontSize: 13 }}>Leave the pilot (back to legacy caps)</Text>
        </TouchableOpacity>
      )}
    </Card>
  );
};
