import React from 'react';
import { View, Text } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { tid } from '../inbox/ownership';

export type NotifiedManager = { user_id: string; name: string; role?: string; push: 'sent' | 'no_device' | 'sms_only' | 'quiet_hours' | 'failed'; push_label: string };

export const notifiedSummary = (rows: NotifiedManager[] | undefined) => {
  if (!rows?.length) return '';
  const names = rows.map((r) => r.name.split(' ')[0]);
  const list = names.length <= 2 ? names.join(' and ') : `${names.slice(0, -1).join(', ')} and ${names[names.length - 1]}`;
  const reached = rows.filter((r) => r.push === 'sent').length;
  return `${list} notified${reached < rows.length ? ` (${reached} of ${rows.length} reached by push)` : ''}`;
};

// Who the desk alert went to and whether it actually reached a phone, so "did the manager get it?" has an answer on the screen.
export const DeskNotified = ({ colors, rows, waiting, legacyCount = 0, testId = 'desk-notified' }: { colors: any; rows: NotifiedManager[] | undefined; waiting: boolean; legacyCount?: number; testId?: string }) => {
  if (!waiting) return null;
  if (!rows?.length && legacyCount > 0) {
    return <Text style={{ fontSize: 12.5, color: colors.textSecondary }} {...tid(`${testId}-legacy`)}>{legacyCount} manager{legacyCount > 1 ? 's' : ''} notified</Text>;
  }
  if (!rows?.length) {
    return (
      <View style={{ flexDirection: 'row', alignItems: 'flex-start', gap: 8, borderRadius: 12, padding: 10, backgroundColor: '#FF3B3014', borderWidth: 1, borderColor: '#FF3B30' }} {...tid(`${testId}-gap`)}>
        <Ionicons name="alert-circle" size={16} color="#FF3B30" style={{ marginTop: 1 }} />
        <Text style={{ flex: 1, fontSize: 12.5, color: colors.text, lineHeight: 17 }}>Nobody was alerted: no manager at this store has appraisal approvals switched on. Ask your admin to assign a manager or grant the permission in Users.</Text>
      </View>
    );
  }
  return (
    <View style={{ gap: 4 }} {...tid(testId)}>
      <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.6 }}>DESK NOTIFIED</Text>
      {rows.map((r) => {
        const ok = r.push === 'sent';
        return (
          <View key={r.user_id} style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }} {...tid(`${testId}-${r.user_id}`)}>
            <Ionicons name={ok ? 'phone-portrait' : 'phone-portrait-outline'} size={13} color={ok ? '#34C759' : '#FF9500'} />
            <Text style={{ fontSize: 12.5, color: colors.text }}>{r.name}</Text>
            <Text style={{ fontSize: 12, color: ok ? '#34C759' : '#FF9500' }}>· {r.push_label}</Text>
          </View>
        );
      })}
    </View>
  );
};
