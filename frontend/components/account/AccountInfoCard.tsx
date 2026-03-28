/**
 * AccountInfoCard.tsx — Read-only account info rows (phone, org, store).
 */

import React from 'react';
import { View, Text, StyleSheet } from 'react-native';

interface Props {
  user: any;
  colors: Record<string, string>;
}

export function AccountInfoCard({ user, colors }: Props) {
  const rows = [
    { label: 'Phone', value: user?.mvpline_number || 'Not assigned' },
    { label: 'Organization', value: user?.organization_name || 'Independent' },
    { label: 'Store', value: user?.store_name || 'N/A' },
  ];

  return (
    <View style={s.section}>
      <Text style={[s.title, { color: colors.textTertiary }]}>Account Info</Text>
      <View style={[s.card, { backgroundColor: colors.card }]}>
        {rows.map((row, i) => (
          <View
            key={row.label}
            style={[s.row, { borderBottomColor: colors.border }, i === rows.length - 1 && s.lastRow]}
          >
            <Text style={[s.label, { color: colors.textSecondary }]}>{row.label}</Text>
            <Text style={[s.value, { color: colors.text }]}>{row.value}</Text>
          </View>
        ))}
      </View>
    </View>
  );
}

const s = StyleSheet.create({
  section: { marginTop: 24, paddingHorizontal: 16 },
  title: { fontSize: 15, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 12 },
  card: { borderRadius: 12, padding: 4 },
  row: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 10, paddingHorizontal: 12, borderBottomWidth: 1 },
  lastRow: { borderBottomWidth: 0 },
  label: { fontSize: 16 },
  value: { fontSize: 16, fontWeight: '600' },
});
