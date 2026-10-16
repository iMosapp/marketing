import React from 'react';
import { View, Text, TouchableOpacity } from 'react-native';
import { useThemeStore } from '../../store/themeStore';
import { GOLD, tid } from '../scripts/shared';

export type Scope = 'off' | 'test_orgs' | 'all';
export type PhotoSettings = {
  replies: Scope; intelligence: Scope; paused: boolean; scopes: Scope[]; model: string;
  test_orgs: { id: string; name: string }[];
  my_org: { id: string; name: string; is_test: boolean; replies_on: boolean; intelligence_on: boolean } | null;
  updated_at?: string | null; updated_by?: string | null;
};
export type Stat = { received: number; analyzed: number; reused: number; successful: number; failed: number; fetch_failed: number; not_analyzed?: number;
  paused?: number; est_cost_usd: number; active_reps: number; avg_cost_per_analyzed: number; cost_per_active_rep: number; avg_ms: number };
export type Usage = {
  days: number; cost_method: string; totals: Stat;
  daily: ({ day: string } & Partial<Stat>)[]; monthly: ({ month: string } & Stat)[];
  organizations: ({ organization_id: string; name: string } & Stat)[];
  stores: ({ store_id: string; name: string; org_name: string } & Stat)[];
  reps: ({ user_id: string; name: string; org_name: string; store_name: string } & Stat)[];
  by_source: ({ source: string } & Stat)[]; by_model: ({ model: string } & Stat)[];
  monitoring: { unattributed_rows: number; duplicate_processing: number };
};

export const SCOPE_LABEL: Record<Scope, string> = { off: 'Off', test_orgs: 'Test orgs only', all: 'All orgs' };
export const money = (n: number | undefined) => (n ? (n < 0.01 ? `$${n.toFixed(4)}` : `$${n.toFixed(2)}`) : '$0.00');
export const pct = (a: number, b: number) => (b ? `${Math.round((a / b) * 100)}%` : '0%');

export const Segmented = ({ value, options, onChange, disabled, testID }: { value: string; options: { key: string; label: string }[]; onChange: (k: string) => void; disabled?: boolean; testID: string }) => {
  const { colors } = useThemeStore();
  return (
    <View style={{ flexDirection: 'row', backgroundColor: colors.bg, borderRadius: 11, padding: 3, gap: 3 }} {...tid(testID)}>
      {options.map(o => {
        const on = o.key === value;
        return (
          <TouchableOpacity key={o.key} disabled={disabled} onPress={() => onChange(o.key)}
            style={{ flex: 1, paddingVertical: 8, borderRadius: 9, alignItems: 'center', backgroundColor: on ? GOLD : 'transparent', opacity: disabled ? 0.5 : 1 }} {...tid(`${testID}-${o.key}`)}>
            <Text style={{ fontSize: 12.5, fontWeight: on ? '800' : '600', color: on ? '#111' : colors.textSecondary }}>{o.label}</Text>
          </TouchableOpacity>
        );
      })}
    </View>
  );
};

export const Tile = ({ label, value, sub, testID }: { label: string; value: string; sub?: string; testID: string }) => {
  const { colors } = useThemeStore();
  return (
    <View style={{ flexBasis: '47%', flexGrow: 1, backgroundColor: colors.bg, borderRadius: 12, padding: 12 }} {...tid(testID)}>
      <Text style={{ fontSize: 11, color: colors.textSecondary, fontWeight: '700', letterSpacing: 0.5 }}>{label}</Text>
      <Text style={{ fontSize: 20, color: colors.text, fontWeight: '800', marginTop: 4 }} {...tid(`${testID}-value`)}>{value}</Text>
      {!!sub && <Text style={{ fontSize: 11.5, color: colors.textSecondary, marginTop: 2 }}>{sub}</Text>}
    </View>
  );
};
