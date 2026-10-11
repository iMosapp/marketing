import React, { useState } from 'react';
import { Text, TextInput, TouchableOpacity, View } from 'react-native';

export type PilotAction = 'extend' | 'end' | 'resume';
const DAYS = [30, 60, 90];
const COPY: Record<PilotAction, { title: string; body: string; cta: string; color: string; placeholder: string }> = {
  extend: { title: 'Extend the pilot', body: 'Adds complimentary days to the end of the pilot. Nothing is charged; reminders already sent are not repeated.', cta: 'Extend pilot', color: '#C9A962', placeholder: 'Reason (e.g. owner was on vacation two weeks, agreed to 30 more days)' },
  end: { title: 'End the pilot', body: 'Every person at this company is signed out and cannot sign in or use the app. Their contacts, messages, memos and card stay exactly as they are; nothing is deleted. You can resume access any time.', cta: 'End pilot and block access', color: '#FF3B30', placeholder: 'Reason (e.g. no response after day 90, chose not to continue)' },
  resume: { title: 'Resume access', body: 'Turns the company back on and lets everyone sign in again. Optionally add complimentary days so they have time to decide.', cta: 'Resume access', color: '#34C759', placeholder: 'Reason (e.g. owner called back, wants two more weeks to decide)' },
};

/** Founder sheet for extend / end / resume with a required reason (audited). */
export function PilotSheet({ action, colors, busy, onCancel, onSubmit }: {
  action: PilotAction; colors: any; busy: boolean; onCancel: () => void; onSubmit: (reason: string, days: number) => void;
}) {
  const [reason, setReason] = useState('');
  const [days, setDays] = useState(action === 'extend' ? 30 : 0);
  const c = COPY[action];
  const ok = reason.trim().length >= 5;
  return (
    <View style={{ backgroundColor: colors.card, borderRadius: 14, borderWidth: 1, borderColor: c.color, padding: 16, gap: 12 }} data-testid={`pilot-sheet-${action}`}>
      <Text style={{ fontSize: 16, fontWeight: '700', color: colors.text }}>{c.title}</Text>
      <Text style={{ fontSize: 14, color: colors.textSecondary, lineHeight: 19 }}>{c.body}</Text>
      <TextInput
        style={{ borderWidth: 1, borderColor: colors.border, borderRadius: 10, padding: 12, fontSize: 16, color: colors.text, minHeight: 70 }}
        placeholder={c.placeholder} placeholderTextColor="#8E8E93" value={reason} onChangeText={setReason} multiline data-testid="pilot-sheet-reason"
      />
      {action !== 'end' ? (
        <View style={{ flexDirection: 'row', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <Text style={{ fontSize: 14, color: colors.textSecondary }}>{action === 'extend' ? 'Add' : 'Also add'}</Text>
          {(action === 'resume' ? [0, ...DAYS] : DAYS).map((d) => (
            <TouchableOpacity key={d} onPress={() => setDays(d)} data-testid={`pilot-sheet-days-${d}`}
              style={{ paddingVertical: 6, paddingHorizontal: 12, borderRadius: 16, borderWidth: 1, borderColor: days === d ? c.color : colors.border, backgroundColor: days === d ? `${c.color}1F` : 'transparent' }}>
              <Text style={{ fontSize: 14, fontWeight: '600', color: days === d ? c.color : colors.textSecondary }}>{d === 0 ? 'no days' : `${d} days`}</Text>
            </TouchableOpacity>
          ))}
        </View>
      ) : null}
      <View style={{ flexDirection: 'row', gap: 10 }}>
        <TouchableOpacity onPress={onCancel} style={{ flex: 1, padding: 12, borderRadius: 10, borderWidth: 1, borderColor: colors.border, alignItems: 'center' }} data-testid="pilot-sheet-cancel">
          <Text style={{ fontSize: 15, fontWeight: '600', color: colors.textSecondary }}>Cancel</Text>
        </TouchableOpacity>
        <TouchableOpacity onPress={() => onSubmit(reason.trim(), days)} disabled={busy || !ok} data-testid="pilot-sheet-submit"
          style={{ flex: 1, padding: 12, borderRadius: 10, backgroundColor: ok ? c.color : '#8E8E93', alignItems: 'center' }}>
          <Text style={{ fontSize: 15, fontWeight: '700', color: action === 'end' ? '#FFF' : '#000' }}>{busy ? 'Saving...' : c.cta}</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}
