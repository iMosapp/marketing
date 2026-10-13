import React from 'react';
import { View, Text } from 'react-native';
import { useThemeStore } from '../../store/themeStore';
import { GOLD, GREEN, RED, AMBER, tid } from '../scripts/shared';

export type Segment = { live_id: string; user: string; engine: string; role?: string; status: string; device_id?: string | null; started_at?: string | null; ended_at?: string | null;
  billable_s: number; reserved_s: number; settled_s: number; est_cost_usd: number; cost_basis?: string | null; stop_reason?: string | null; fallback_reason?: string | null;
  reconnect_of?: string | null; segment_no?: number; unconfirmed: boolean; fake_provider: boolean; kill_attempts: number };
export type Handoff = { at?: string | null; user: string; from_live_id: string; to_live_id: string; from_engine?: string | null; to_engine: string; reason: string; from_billable_s: number; to_billable_s: number; to_status: string };
export type PilotStatus = {
  org_id: string; org_name: string; me: { user_id: string; email: string; role: string }; enrolled: boolean; global_enabled: boolean; other_enrolled_org_ids: string[];
  defaults: { premium_min: number; backup_min: number; hard_usd: number };
  policy: { enabled: boolean; killed: boolean; cap_super_admins: boolean; per_user_daily_premium_min: number; per_user_daily_backup_min: number; account_monthly_hard_usd: number | null; premium_engine: string; backup_engine: string; timezone?: string | null; updated_at?: string | null; updated_by?: string | null };
  env: { fake_provider_allowed: boolean; openai_configured: boolean; openai_reason?: string | null; build?: string | null };
  allowance: { premium_allowance_s: number; backup_allowance_s: number; premium_left_s: number; backup_left_s: number; premium_used_s: number; backup_used_s: number; premium_reserved_s: number; backup_reserved_s: number; limits: string[]; reset_at: string; timezone: string; next_engine: string | null } | null;
  today: { day: string; premium_used_s: number; premium_reserved_s: number; backup_used_s: number; backup_reserved_s: number; sessions: number };
  month: { month: string; premium_s: number; backup_s: number; premium_cost_usd: number; backup_cost_usd: number; est_cost_usd: number; cap_usd: number | null; cap_left_usd: number | null };
  active: Segment[]; handoffs: Handoff[]; recent: Segment[];
};

export const ENGINE_LABEL: Record<string, string> = { live: 'GPT-Live', mini: 'Realtime Mini' };
export const fmtS = (s: number) => (s >= 60 ? `${Math.floor(s / 60)}m ${s % 60}s` : `${s}s`);
export const usd = (n: number | null | undefined) => (n === null || n === undefined ? 'none' : `$${n.toFixed(2)}`);
export const when = (iso?: string | null) => (iso ? new Date(iso).toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit', second: '2-digit' }) : '');
export const toneOf = (ok: boolean | null) => (ok === null ? '#8E8E93' : ok ? GREEN : RED);
export { GOLD, GREEN, RED, AMBER, tid };

export const Card = ({ title, children, testID }: { title: string; children: React.ReactNode; testID: string }) => {
  const { colors } = useThemeStore();
  return (
    <View style={{ backgroundColor: colors.card, borderRadius: 16, padding: 16, borderWidth: 1, borderColor: colors.border, marginBottom: 14 }} {...tid(testID)}>
      <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.8, marginBottom: 10 }}>{title}</Text>
      {children}
    </View>
  );
};

export const Row = ({ label, value, tone, testID }: { label: string; value: string; tone?: string; testID?: string }) => {
  const { colors } = useThemeStore();
  return (
    <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: 5, gap: 12 }} {...(testID ? tid(testID) : {})}>
      <Text style={{ color: colors.textSecondary, fontSize: 13, flexShrink: 1 }}>{label}</Text>
      <Text style={{ color: tone || colors.text, fontSize: 13, fontWeight: '700', textAlign: 'right', flexShrink: 1 }}>{value}</Text>
    </View>
  );
};

export const Pill = ({ text, tone, testID }: { text: string; tone: string; testID?: string }) => (
  <View style={{ alignSelf: 'flex-start', backgroundColor: `${tone}22`, borderRadius: 10, paddingHorizontal: 9, paddingVertical: 4 }} {...(testID ? tid(testID) : {})}>
    <Text style={{ color: tone, fontSize: 11, fontWeight: '800', letterSpacing: 0.6 }}>{text}</Text>
  </View>
);
