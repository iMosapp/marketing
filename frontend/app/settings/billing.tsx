import React, { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, Linking, Platform, ScrollView, Text, TouchableOpacity, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { showSimpleAlert } from '../../services/alert';
import { useThemeStore } from '../../store/themeStore';
import { ScreenHeader } from '../../components/common/ScreenHeader';
import { BILLING_LABEL } from '../../components/customers/StatusPill';

const fmt = (iso?: string) => (iso ? new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' }) : '');
const money = (n?: number) => (typeof n === 'number' ? `$${n.toLocaleString(undefined, { maximumFractionDigits: 2 })}` : '');
const go = (url: string) => (Platform.OS === 'web' ? (window.location.href = url) : Linking.openURL(url));

export default function BillingScreen() {
  const { colors } = useThemeStore();
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try { setData((await api.get('/billing/me')).data); }
    catch (e: any) { setError(e?.response?.data?.detail || 'Billing is not available right now.'); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const openPortal = async () => {
    setBusy(true);
    try { go((await api.post('/billing/portal')).data.url); }
    catch (e: any) { showSimpleAlert('Not available', e?.response?.data?.detail || 'Could not open the billing portal.'); }
    finally { setBusy(false); }
  };

  const statusLine = () => {
    if (!data) return '';
    if (data.exception) return `Billing exception until ${fmt(data.exception_ends)}`;
    if (data.billing_status === 'past_due') return `Payment failed · please update your card · access continues until ${fmt(data.grace_until)}`;
    if (data.cancel_at_period_end) return `Cancels ${fmt(data.current_period_end)}`;
    if (data.current_period_end) return `${BILLING_LABEL[data.billing_status] || data.billing_status} · renews ${fmt(data.current_period_end)}`;
    return BILLING_LABEL[data.billing_status] || data.billing_status || '';
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      <ScreenHeader title="Billing" subtitle="Plan, invoices and payment method" testID="billing-header" />
      <ScrollView contentContainerStyle={{ padding: 16, gap: 14, maxWidth: 640, alignSelf: 'center', width: '100%' }}>
        {error ? <Text style={{ color: colors.textSecondary, fontSize: 16 }} data-testid="billing-me-error">{error}</Text> : null}
        {!data && !error ? <ActivityIndicator color={colors.accent} /> : null}
        {data ? (
          <>
            <View style={{ backgroundColor: colors.card, borderRadius: 12, borderWidth: 1, borderColor: colors.border, padding: 16, gap: 6 }} data-testid="billing-me-card">
              <Text style={{ fontSize: 13, fontWeight: '700', color: '#8E8E93', letterSpacing: 1.2 }}>{data.business_name?.toUpperCase()}</Text>
              <Text style={{ fontSize: 22, fontWeight: '800', color: colors.text }} data-testid="billing-me-plan">{data.plan_name} · {money(data.monthly_total)}/mo</Text>
              <Text style={{ fontSize: 14, color: colors.textSecondary }}>{data.seats_included} seat{data.seats_included === 1 ? '' : 's'} included{data.seats_extra ? ` + ${data.seats_extra} extra at ${money(data.seat_price)}/mo` : ''}</Text>
              <Text style={{ fontSize: 14, color: data.billing_status === 'past_due' ? '#FF9500' : colors.text, fontWeight: '600' }} data-testid="billing-me-status">{statusLine()}</Text>
              {data.last_payment_at ? <Text style={{ fontSize: 13, color: colors.textTertiary }}>Last payment {money(data.last_payment_amount)} on {fmt(data.last_payment_at)}</Text> : null}
            </View>
            {data.portal_available ? (
              <TouchableOpacity onPress={openPortal} disabled={busy} data-testid="billing-me-portal"
                style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#C9A962', borderRadius: 12, paddingVertical: 14, opacity: busy ? 0.6 : 1 }}>
                <Ionicons name="card" size={18} color="#111" />
                <Text style={{ fontSize: 16, fontWeight: '700', color: '#111' }}>Payment method, invoices and plan</Text>
              </TouchableOpacity>
            ) : null}
            {data.checkout_url ? (
              <TouchableOpacity onPress={() => go(data.checkout_url)} data-testid="billing-me-checkout"
                style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, borderRadius: 12, paddingVertical: 14, borderWidth: 1, borderColor: '#C9A962' }}>
                <Ionicons name="lock-closed" size={18} color="#C9A962" />
                <Text style={{ fontSize: 16, fontWeight: '700', color: '#C9A962' }}>Complete payment on Stripe</Text>
              </TouchableOpacity>
            ) : null}
            <Text style={{ fontSize: 13, color: colors.textTertiary, lineHeight: 19 }}>Payments are processed by Stripe. Your card details never reach I'm On Social. Receipts arrive by email from Stripe.</Text>
          </>
        ) : null}
      </ScrollView>
    </SafeAreaView>
  );
}
