import React from 'react';
import { View, Text } from 'react-native';
import { useThemeStore } from '../../store/themeStore';
import { Card, Row, PilotStatus, GOLD, GREEN, RED, AMBER, fmtS, usd, ENGINE_LABEL } from './shared';

// Today's pools, this month's estimated spend against the hard cap, and what the next session would get.
export const PilotUsageCard = ({ s }: { s: PilotStatus }) => {
  const { colors } = useThemeStore();
  const m = s.month;
  const pct = m.cap_usd ? Math.min(100, Math.round((m.est_cost_usd / m.cap_usd) * 100)) : 0;
  const barTone = pct >= 100 ? RED : pct >= 80 ? AMBER : GREEN;
  const a = s.allowance;
  return (
    <Card title={`USAGE · TODAY ${s.today.day} · ${s.allowance?.timezone || s.policy.timezone || ''}`} testID="pilot-usage-card">
      <Row label="GPT-Live used today (account)" value={fmtS(s.today.premium_used_s)} testID="pilot-today-premium" />
      <Row label="Realtime Mini used today (account)" value={fmtS(s.today.backup_used_s)} testID="pilot-today-backup" />
      <Row label="Held by open sessions right now" value={`${fmtS(s.today.premium_reserved_s)} GPT-Live · ${fmtS(s.today.backup_reserved_s)} Mini`} tone={s.today.premium_reserved_s + s.today.backup_reserved_s > 0 ? GOLD : colors.text} testID="pilot-today-reserved" />
      <Row label="Sessions today" value={String(s.today.sessions)} testID="pilot-today-sessions" />
      <View style={{ height: 1, backgroundColor: colors.border, marginVertical: 8 }} />
      <Row label={`Estimated spend ${m.month}`} value={`${usd(m.est_cost_usd)} of ${usd(m.cap_usd)}`} tone={barTone} testID="pilot-month-spend" />
      <Row label="GPT-Live / Mini this month" value={`${fmtS(m.premium_s)} (${usd(m.premium_cost_usd)}) · ${fmtS(m.backup_s)} (${usd(m.backup_cost_usd)})`} testID="pilot-month-split" />
      {m.cap_usd !== null && (
        <View style={{ height: 8, borderRadius: 4, backgroundColor: colors.border, marginTop: 6, overflow: 'hidden' }}>
          <View style={{ width: `${pct}%`, height: 8, backgroundColor: barTone }} />
        </View>
      )}
      {a && (
        <>
          <View style={{ height: 1, backgroundColor: colors.border, marginVertical: 8 }} />
          <Row label="My next session would start on" value={a.next_engine ? ENGINE_LABEL[a.next_engine] || a.next_engine : 'Nothing (text only)'} tone={a.next_engine === 'live' ? GREEN : a.next_engine ? AMBER : RED} testID="pilot-next-engine" />
          <Row label="My GPT-Live left today" value={`${fmtS(a.premium_left_s)} of ${fmtS(a.premium_allowance_s)}`} testID="pilot-my-premium" />
          <Row label="My Mini left today" value={`${fmtS(a.backup_left_s)} of ${fmtS(a.backup_allowance_s)}`} testID="pilot-my-backup" />
          <Text style={{ color: colors.textSecondary, fontSize: 11, marginTop: 6 }} {...{ testID: 'pilot-limits', dataSet: { testid: 'pilot-limits' } as any }}>Limits in play: {a.limits.join(', ') || 'none'} · resets {new Date(a.reset_at).toLocaleString()}</Text>
        </>
      )}
    </Card>
  );
};
