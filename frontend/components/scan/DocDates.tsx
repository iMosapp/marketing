import React from 'react';
import { View, Text, TouchableOpacity, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { GOLD, tid } from '../inbox/ownership';

export type DocReminder = { key: string; what: string; date: string; label: string; title: string; due: string; status: string; task_id: string };
type Props = { dates: { date: string; what: string; label: string }[]; reminders: DocReminder[]; colors: any;
  picked?: string[]; onToggle?: (key: string) => void;                                        // pick mode: before a scan is saved
  onAdd?: (key: string) => void; onDismiss?: (key: string) => void; busyKey?: string | null };   // act mode: on a contact's Files

const GREEN = '#34C759';
export const fmtDay = (iso: string) => { const [y, m, d] = iso.split('-').map(Number); return new Date(y, m - 1, d).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' }); };
const Label = ({ text, colors, top = 0 }: any) => <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.8, marginTop: top }}>{text}</Text>;

const Row = ({ r, colors, picked, onToggle, onAdd, onDismiss, busyKey }: Omit<Props, 'dates' | 'reminders'> & { r: DocReminder }) => {
  const done = r.status === 'created';
  const on = !!picked?.includes(r.key);
  const sub = done ? `Reminder set for ${fmtDay(r.due)}` : `Remind you ${fmtDay(r.due)}`;
  const icon = done ? 'checkmark-done-circle' : onToggle ? (on ? 'checkbox' : 'square-outline') : 'alarm-outline';
  return (
    <TouchableOpacity disabled={done || !onToggle} onPress={() => onToggle?.(r.key)} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 6 }} {...tid(`doc-reminder-${r.key}`)}>
      <Ionicons name={icon as any} size={20} color={done ? GREEN : on || !onToggle ? GOLD : colors.border} />
      <View style={{ flex: 1 }}>
        <Text style={{ fontSize: 14, color: colors.text, fontWeight: '600' }}>{r.title}</Text>
        <Text style={{ fontSize: 12, color: done ? GREEN : colors.textSecondary }} {...tid(`doc-reminder-sub-${r.key}`)}>{sub}</Text>
      </View>
      {!done && onAdd && (busyKey === r.key ? <ActivityIndicator color={GOLD} /> : (
        <>
          <TouchableOpacity onPress={() => onAdd(r.key)} style={{ height: 32, paddingHorizontal: 12, borderRadius: 16, backgroundColor: GOLD, justifyContent: 'center' }} {...tid(`doc-reminder-add-${r.key}`)}>
            <Text style={{ fontSize: 12.5, fontWeight: '800', color: '#111' }}>Remind me</Text>
          </TouchableOpacity>
          <TouchableOpacity onPress={() => onDismiss?.(r.key)} hitSlop={8} {...tid(`doc-reminder-dismiss-${r.key}`)}><Ionicons name="close" size={18} color={colors.textSecondary} /></TouchableOpacity>
        </>
      ))}
    </TouchableOpacity>
  );
};

// Key dates Jessi read on a document + the reminders she suggests. Reminders are for the rep only; nothing is sent to the customer.
export const DocDates = ({ dates, reminders, colors, ...rest }: Props) => {
  if (!dates.length && !reminders.length) return null;
  return (
    <View style={{ gap: 4, backgroundColor: colors.card, borderRadius: 14, borderWidth: 1, borderColor: GOLD + '55', padding: 12 }} {...tid('doc-dates')}>
      {dates.length > 0 && <Label text="KEY DATES" colors={colors} />}
      {dates.map(d => (
        <View key={`${d.what}_${d.date}`} style={{ flexDirection: 'row', justifyContent: 'space-between', gap: 10, paddingVertical: 3 }} {...tid(`doc-date-${d.what}_${d.date}`)}>
          <Text style={{ fontSize: 13.5, color: colors.text, flex: 1 }}>{d.label}</Text>
          <Text style={{ fontSize: 13.5, fontWeight: '700', color: colors.text }}>{fmtDay(d.date)}</Text>
        </View>
      ))}
      {reminders.length > 0 && <Label text="JESSI SUGGESTS" colors={colors} top={dates.length ? 8 : 0} />}
      {reminders.map(r => <Row key={r.key} r={r} colors={colors} {...rest} />)}
      {reminders.length > 0 && <Text style={{ fontSize: 11.5, color: colors.textSecondary, marginTop: 2 }}>Just for you. Nothing is sent to the customer.</Text>}
    </View>
  );
};
