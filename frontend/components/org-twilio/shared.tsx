/** Shared bits for the Organization -> Communications -> Twilio screens. */
import React from 'react';
import { View, Text, StyleSheet } from 'react-native';

export const GOLD = '#C9A962';
export const tid = (id: string) => ({ testID: id, dataSet: { testid: id } as any });

export const STATUS_COLOR: Record<string, string> = {
  NOT_STARTED: '#8E8E93', INFORMATION_REQUIRED: '#FF9500', SUBMITTED: '#5AC8FA', PENDING: '#FF9500',
  APPROVED: '#34C759', REJECTED: '#FF3B30', ACTION_REQUIRED: '#FF3B30',
};
export const PROV_COLOR: Record<string, string> = {
  NOT_STARTED: '#8E8E93', IN_PROGRESS: '#5AC8FA', INFORMATION_REQUIRED: '#FF9500', WAITING_APPROVAL: '#FF9500', READY: '#34C759', ERROR: '#FF3B30',
};
export const NUM_STATUS: Record<string, { label: string; color: string }> = {
  AVAILABLE: { label: 'Available', color: '#5AC8FA' }, ASSIGNED: { label: 'Assigned', color: '#34C759' },
  SUSPENDED: { label: 'Suspended', color: '#FF9500' }, RELEASED: { label: 'Released', color: '#8E8E93' },
};

export const prettyPhone = (p: string) => {
  const d = (p || '').replace(/\D/g, '');
  if (d.length === 11 && d.startsWith('1')) return `(${d.slice(1, 4)}) ${d.slice(4, 7)}-${d.slice(7)}`;
  return p || '';
};
export const when = (iso?: string | null) => (iso ? new Date(iso).toLocaleString([], { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }) : '');

export function Pill({ label, color, testID }: { label: string; color: string; testID?: string }) {
  return (
    <View style={[pill.wrap, { backgroundColor: `${color}22`, borderColor: `${color}66` }]} {...(testID ? tid(testID) : {})}>
      <View style={[pill.dot, { backgroundColor: color }]} />
      <Text style={[pill.text, { color }]}>{label}</Text>
    </View>
  );
}

const pill = StyleSheet.create({
  wrap: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 9, paddingVertical: 4, borderRadius: 12, borderWidth: 1, alignSelf: 'flex-start' },
  dot: { width: 7, height: 7, borderRadius: 4 },
  text: { fontSize: 11.5, fontWeight: '800', letterSpacing: 0.3 },
});

export const getS = (colors: any) => StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  card: { backgroundColor: colors.card, borderRadius: 14, padding: 14, marginBottom: 14 },
  cardTitle: { fontSize: 16, fontWeight: '700', color: colors.text, marginBottom: 10 },
  label: { fontSize: 11, fontWeight: '800', letterSpacing: 0.6, color: colors.textSecondary, marginBottom: 6, textTransform: 'uppercase' },
  hint: { fontSize: 12, color: colors.textTertiary, lineHeight: 17, marginTop: 4 },
  input: { backgroundColor: colors.bg, borderRadius: 10, borderWidth: 1, borderColor: colors.border, paddingHorizontal: 12, paddingVertical: 10, fontSize: 15, color: colors.text },
  btn: { flex: 1, height: 44, borderRadius: 12, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 6 },
  btnText: { fontSize: 15, fontWeight: '800', color: '#000' },
  chip: { paddingHorizontal: 11, paddingVertical: 7, borderRadius: 14, borderWidth: 1 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  mono: { fontSize: 11.5, color: colors.textTertiary, fontFamily: 'monospace' as any },
});
