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
  const [confirming, setConfirming] = useState(false);

  const load = useCallback(async () => {
    try { setData((await api.get('/billing/me')).data); }
    catch (e: any) { setError(e?.response?.data?.detail || 'Billing is not available right now.'); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const startCheckout = async () => {
    setBusy(true);
    try { go((await api.post('/billing/checkout')).data.url); }
    catch (e: any) { showSimpleAlert('Not available', e?.response?.data?.detail || 'Could not open Stripe right now.'); }
    finally { setBusy(false); }
  };

  const openPortal = async () => {
    setBusy(true);
    try { go((await api.post('/billing/portal')).data.url); }
    catch (e: any) { showSimpleAlert('Not available', e?.response?.data?.detail || 'Could not open the billing portal.'); }
    finally { setBusy(false); }
  };

  const statusLine = () => {
    if (!data) return '';
    const p = data.pilot;
    if (p && data.billing_status === 'pilot') {
      if (p.state === 'pending') return 'Founding Partner Pilot · 90 complimentary days start when you activate';
      if (p.state === 'active') return `Founding Partner Pilot · ${p.days_left} day${p.days_left === 1 ? '' : 's'} left · complimentary until ${fmt(p.ends_at)}`;
      if (p.state === 'completed') return `Your complimentary pilot ended ${fmt(p.ends_at)} · nothing has been charged`;
    }
    if (data.exception) return `Billing exception until ${fmt(data.exception_ends)}`;
    if (data.billing_status === 'past_due') return `Payment failed · please update your card · access continues until ${fmt(data.grace_until)}`;
    if (data.cancel_at_period_end) return `Cancels ${fmt(data.current_period_end)}`;
    if (data.billing_status === 'trialing' && p?.state === 'converted') return `Card saved · first charge ${money(data.monthly_total)} on ${fmt(data.current_period_end)} · then monthly`;
    if (data.current_period_end) return `${BILLING_LABEL[data.billing_status] || data.billing_status} · renews ${fmt(data.current_period_end)}`;
    return BILLING_LABEL[data.billing_status] || data.billing_status || '';
  };
  const pilot = data?.pilot;
  const canContinue = !!pilot?.can_continue;

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
            {canContinue && !confirming ? (
              <TouchableOpacity onPress={() => setConfirming(true)} data-testid="billing-me-continue"
                style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#C9A962', borderRadius: 12, paddingVertical: 14 }}>
                <Ionicons name="checkmark-circle" size={18} color="#111" />
                <Text style={{ fontSize: 16, fontWeight: '700', color: '#111' }}>Continue after the pilot</Text>
              </TouchableOpacity>
            ) : null}
            {canContinue && confirming ? (
              <View style={{ backgroundColor: colors.card, borderRadius: 12, borderWidth: 1, borderColor: '#C9A962', padding: 16, gap: 10 }} data-testid="billing-me-terms">
                <Text style={{ fontSize: 16, fontWeight: '700', color: colors.text }}>Before you authorize</Text>
                <Text style={{ fontSize: 14, color: colors.text, lineHeight: 20 }} data-testid="billing-me-terms-price">Price: {data.plan_name} at {money(data.monthly_total)} per month ({data.seats_included} seats included{data.seats_extra ? ` + ${data.seats_extra} extra at ${money(data.seat_price)}/mo` : ''}; extra seats {money(data.seat_price)}/mo each).</Text>
                <Text style={{ fontSize: 14, color: colors.text, lineHeight: 20 }} data-testid="billing-me-terms-date">First charge: {fmt(pilot.first_charge_on)}, the day your complimentary pilot ends. Nothing is charged today. It then renews monthly on that date.</Text>
                <Text style={{ fontSize: 14, color: colors.text, lineHeight: 20 }} data-testid="billing-me-terms-cancel">Cancel any time before {fmt(pilot.first_charge_on)} from this screen and you will not be charged. After that, cancellation takes effect at the end of the paid month.</Text>
                <Text style={{ fontSize: 13, color: colors.textSecondary, lineHeight: 19 }}>Your card is saved securely by Stripe on the next page; it never reaches I'm On Social. Receipts and reminders come from Stripe by email.</Text>
                <TouchableOpacity onPress={startCheckout} disabled={busy} data-testid="billing-me-authorize"
                  style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#C9A962', borderRadius: 12, paddingVertical: 14, opacity: busy ? 0.6 : 1 }}>
                  <Ionicons name="lock-closed" size={18} color="#111" />
                  <Text style={{ fontSize: 16, fontWeight: '700', color: '#111' }}>I authorize billing from {fmt(pilot.first_charge_on)} · Save card on Stripe</Text>
                </TouchableOpacity>
                <TouchableOpacity onPress={() => setConfirming(false)} data-testid="billing-me-not-now" style={{ alignItems: 'center', paddingVertical: 8 }}>
                  <Text style={{ fontSize: 15, fontWeight: '600', color: colors.textSecondary }}>Not now</Text>
                </TouchableOpacity>
              </View>
            ) : null}
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
