import React from 'react';
import { View, Text } from 'react-native';
import { useThemeStore } from '../../store/themeStore';
import { Card, Row, Pill, PilotStatus, GOLD, GREEN, RED, AMBER, usd, toneOf } from './shared';

// Where the pilot stands and the production safety flags the founder must see before enrolling anyone.
export const PilotStatusCard = ({ s }: { s: PilotStatus }) => {
  const { colors } = useThemeStore();
  const p = s.policy;
  const state = p.killed ? 'STOPPED' : s.enrolled ? 'ENROLLED' : 'NOT ENROLLED';
  const tone = p.killed ? RED : s.enrolled ? GREEN : '#8E8E93';
  const others = s.other_enrolled_org_ids.length;
  return (
    <Card title={`YOUR ACCOUNT · ${s.org_name.toUpperCase()}`} testID="pilot-status-card">
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 8 }}>
        <Pill text={state} tone={tone} testID="pilot-state" />
        <Text style={{ color: colors.textSecondary, fontSize: 12 }}>{s.me.email}</Text>
      </View>
      {s.enrolled && (
        <>
          <Row label="Premium (GPT-Live) per person per day" value={`${p.per_user_daily_premium_min} min`} testID="pilot-policy-premium" />
          <Row label="Standard voice (Realtime Mini) per person per day" value={`${p.per_user_daily_backup_min} min`} testID="pilot-policy-backup" />
          <Row label="Hard monthly spending cap (whole account, both engines)" value={usd(p.account_monthly_hard_usd)} tone={p.account_monthly_hard_usd === null ? RED : colors.text} testID="pilot-policy-cap" />
          <Row label="Super admins capped like everyone" value={p.cap_super_admins ? 'Yes' : 'No'} tone={toneOf(p.cap_super_admins)} testID="pilot-policy-capsuper" />
        </>
      )}
      <View style={{ height: 1, backgroundColor: colors.border, marginVertical: 8 }} />
      <Row label="Other accounts enrolled" value={others === 0 ? 'None (good)' : `${others} account${others === 1 ? '' : 's'}`} tone={toneOf(others === 0)} testID="pilot-others" />
      <Row label="Voice controls master switch" value={s.global_enabled ? 'On' : 'OFF (everyone on legacy caps)'} tone={toneOf(s.global_enabled)} testID="pilot-global" />
      <Row label="OpenAI key on this server" value={s.env.openai_configured ? 'Present' : `Missing${s.env.openai_reason ? '' : ''}`} tone={toneOf(s.env.openai_configured)} testID="pilot-env-openai" />
      <Row label="Fake voice provider (test only)" value={s.env.fake_provider_allowed ? 'ALLOWED, must be OFF in production' : 'Off'} tone={s.env.fake_provider_allowed ? AMBER : GREEN} testID="pilot-env-fake" />
      <Row label="Server build" value={s.env.build || 'unknown'} testID="pilot-env-build" />
      {!s.enrolled && <Text style={{ color: GOLD, fontSize: 12, marginTop: 8 }}>Everyone on this account is on the legacy caps right now. Enrolling changes this account only.</Text>}
    </Card>
  );
};
