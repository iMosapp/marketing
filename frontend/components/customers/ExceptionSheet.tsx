import React, { useState } from 'react';
import { Text, TextInput, TouchableOpacity, View } from 'react-native';

const DAYS = [30, 60, 90];

export function ExceptionSheet({ colors, onSubmit, onCancel, busy }: {
  colors: any; busy: boolean; onCancel: () => void;
  onSubmit: (reason: string, expiresAt: string) => void;
}) {
  const [reason, setReason] = useState('');
  const [days, setDays] = useState(30);
  const expires = new Date(Date.now() + days * 86400000);
  const expiresAt = expires.toISOString().slice(0, 10);
  return (
    <View style={{ backgroundColor: colors.card, borderRadius: 14, borderWidth: 1, borderColor: '#FF9500', padding: 16, gap: 12 }} data-testid="exception-sheet">
      <Text style={{ fontSize: 16, fontWeight: '700', color: colors.text }}>Billing exception</Text>
      <Text style={{ fontSize: 14, color: colors.textSecondary, lineHeight: 19 }}>
        Lets you activate without a Stripe payment. It is recorded as an exception, never as a payment. Say why, and when it ends.
      </Text>
      <TextInput
        style={{ borderWidth: 1, borderColor: colors.border, borderRadius: 10, padding: 12, fontSize: 16, color: colors.text, minHeight: 70 }}
        placeholder="Reason (e.g. paid by check #1041, pilot courtesy through November)"
        placeholderTextColor="#8E8E93"
        value={reason}
        onChangeText={setReason}
        multiline
        data-testid="exception-reason"
      />
      <View style={{ flexDirection: 'row', gap: 8, alignItems: 'center' }}>
        <Text style={{ fontSize: 14, color: colors.textSecondary }}>Ends in</Text>
        {DAYS.map((d) => (
          <TouchableOpacity
            key={d}
            onPress={() => setDays(d)}
            style={{ paddingVertical: 6, paddingHorizontal: 12, borderRadius: 16, borderWidth: 1, borderColor: days === d ? '#FF9500' : colors.border, backgroundColor: days === d ? 'rgba(255,149,0,0.12)' : 'transparent' }}
            data-testid={`exception-days-${d}`}
          >
            <Text style={{ fontSize: 14, fontWeight: '600', color: days === d ? '#FF9500' : colors.textSecondary }}>{d} days</Text>
          </TouchableOpacity>
        ))}
      </View>
      <Text style={{ fontSize: 13, color: colors.textTertiary }} data-testid="exception-expires">Expires {expiresAt}</Text>
      <View style={{ flexDirection: 'row', gap: 10 }}>
        <TouchableOpacity onPress={onCancel} style={{ flex: 1, padding: 12, borderRadius: 10, borderWidth: 1, borderColor: colors.border, alignItems: 'center' }} data-testid="exception-cancel">
          <Text style={{ fontSize: 15, fontWeight: '600', color: colors.textSecondary }}>Cancel</Text>
        </TouchableOpacity>
        <TouchableOpacity
          onPress={() => onSubmit(reason.trim(), expiresAt)}
          disabled={busy || reason.trim().length < 5}
          style={{ flex: 1, padding: 12, borderRadius: 10, backgroundColor: reason.trim().length < 5 ? '#8E8E93' : '#FF9500', alignItems: 'center' }}
          data-testid="exception-submit"
        >
          <Text style={{ fontSize: 15, fontWeight: '700', color: '#000' }}>{busy ? 'Saving...' : 'Grant exception'}</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}
