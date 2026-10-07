import React from 'react';
import { View, Text, ScrollView, TouchableOpacity } from 'react-native';
import { GOLD, tid } from '../../inbox/ownership';

export type Filters = { days: number; store_id?: string; user_id?: string; manager_id?: string; outcome?: string; make?: string };
const RANGES = [{ d: 30, label: '30 days' }, { d: 90, label: '90 days' }, { d: 365, label: 'Year' }, { d: 0, label: 'All time' }];

const Row = ({ colors, label, options, value, onPick, testId }: { colors: any; label: string; options: { id: string; name: string }[]; value?: string; onPick: (id?: string) => void; testId: string }) => {
  if (!options.length) return null;
  return (
    <View style={{ gap: 4 }}>
      <Text style={{ fontSize: 10.5, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.5 }}>{label}</Text>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 6 }}>
        <Pill colors={colors} on={!value} label="All" onPress={() => onPick(undefined)} testId={`${testId}-all`} />
        {options.map(o => <Pill key={o.id} colors={colors} on={value === o.id} label={o.name} onPress={() => onPick(value === o.id ? undefined : o.id)} testId={`${testId}-${o.id}`} />)}
      </ScrollView>
    </View>
  );
};

const Pill = ({ colors, on, label, onPress, testId }: { colors: any; on: boolean; label: string; onPress: () => void; testId: string }) => (
  <TouchableOpacity onPress={onPress} style={{ height: 30, paddingHorizontal: 11, borderRadius: 15, borderWidth: 1, borderColor: on ? GOLD : colors.border, backgroundColor: on ? GOLD + '22' : colors.card, alignItems: 'center', justifyContent: 'center' }} {...tid(testId)}>
    <Text style={{ fontSize: 12, fontWeight: '700', color: on ? GOLD : colors.textSecondary }}>{label}</Text>
  </TouchableOpacity>
);

// Date range + store / salesperson / manager / outcome / make. Options come from the data the caller can see, so nothing leaks across tenants.
export const ReportFilters = ({ colors, filters, set, options }: { colors: any; filters: Filters; set: (p: Partial<Filters>) => void; options: any }) => (
  <View style={{ gap: 8 }} {...tid('report-filters')}>
    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 6 }}>
      {RANGES.map(r => <Pill key={r.d} colors={colors} on={filters.days === r.d} label={r.label} onPress={() => set({ days: r.d })} testId={`report-range-${r.d}`} />)}
    </ScrollView>
    {(options?.stores || []).length > 1 ? <Row colors={colors} label="STORE" options={options.stores} value={filters.store_id} onPick={v => set({ store_id: v })} testId="report-store" /> : null}
    <Row colors={colors} label="SALESPERSON" options={options?.salespeople || []} value={filters.user_id} onPick={v => set({ user_id: v })} testId="report-rep" />
    <Row colors={colors} label="MANAGER" options={options?.managers || []} value={filters.manager_id} onPick={v => set({ manager_id: v })} testId="report-manager" />
    <Row colors={colors} label="OUTCOME" options={Object.entries(options?.outcomes || {}).map(([id, name]: any) => ({ id, name }))} value={filters.outcome} onPick={v => set({ outcome: v })} testId="report-outcome" />
    <Row colors={colors} label="MAKE" options={(options?.makes || []).map((m: string) => ({ id: m, name: m }))} value={filters.make} onPick={v => set({ make: v })} testId="report-make" />
  </View>
);
