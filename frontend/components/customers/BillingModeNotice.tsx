// Founder notice when paid conversion is paused (Stripe test key in production, or no billing key at all)
import React from 'react';
import { View, Text } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

export type BillingConfig = { configured: boolean; mode: 'live' | 'test' | null; conversion_enabled: boolean };

export const conversionOn = (cfg?: BillingConfig | null) => !cfg || cfg.conversion_enabled;

export function BillingModeNotice({ config, colors }: { config?: BillingConfig | null; colors: any }) {
  if (!config || config.conversion_enabled) return null;
  const text = !config.configured
    ? 'Stripe billing is not configured on this server. Paid conversion is off; complimentary pilots are not affected.'
    : 'Stripe is in TEST mode on this server. Paid conversion is paused until the live key and webhook are configured; complimentary pilots are not affected.';
  return (
    <View style={{ flexDirection: 'row', gap: 8, alignItems: 'flex-start', backgroundColor: '#FF950022', borderColor: '#FF9500', borderWidth: 1, borderRadius: 10, padding: 10 }} data-testid="billing-mode-notice">
      <Ionicons name="warning" size={16} color="#FF9500" style={{ marginTop: 1 }} />
      <Text style={{ flex: 1, fontSize: 13, color: colors.text, lineHeight: 18 }}>{text}</Text>
    </View>
  );
}
