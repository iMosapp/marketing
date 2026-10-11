import React from 'react';
import { Text, View } from 'react-native';

export const STEP_LABEL: Record<string, string> = {
  created: 'Created',
  payment_link_sent: 'Payment link sent',
  paid: 'Paid',
  activated: 'Activated',
  owner_invited: 'Owner invited',
  owner_active: 'Owner active',
};

export const BILLING_LABEL: Record<string, string> = {
  unpaid: 'Unpaid',
  awaiting_payment: 'Awaiting payment',
  trialing: 'Card saved',
  active: 'Paid',
  past_due: 'Past due',
  canceled: 'Canceled',
  exception: 'Exception',
  pilot: 'Pilot',
};

const COLOR: Record<string, string> = {
  created: '#8E8E93', payment_link_sent: '#FF9500', paid: '#34C759', activated: '#007AFF',
  owner_invited: '#AF52DE', owner_active: '#34C759',
};

export function StatusPill({ status, billing, testID }: { status?: string; billing?: string; testID?: string }) {
  const color = COLOR[status || ''] || '#8E8E93';
  const warn = billing === 'exception' || billing === 'unpaid' || billing === 'past_due';
  const billingColor = billing === 'pilot' ? '#C9A962' : warn ? '#FF9500' : '#34C759';
  return (
    <View style={{ alignItems: 'flex-end', gap: 3 }} data-testid={testID}>
      <View style={{ paddingHorizontal: 8, paddingVertical: 3, borderRadius: 8, backgroundColor: `${color}20` }}>
        <Text style={{ fontSize: 12, fontWeight: '600', color }}>{STEP_LABEL[status || ''] || status || 'New'}</Text>
      </View>
      {billing ? (
        <Text style={{ fontSize: 11, fontWeight: '600', color: billingColor }}>{BILLING_LABEL[billing] || billing}</Text>
      ) : null}
    </View>
  );
}
