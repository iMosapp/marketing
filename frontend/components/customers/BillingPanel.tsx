import React from 'react';
import { Linking, Platform, Text, TouchableOpacity, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import * as Clipboard from 'expo-clipboard';
import api from '../../services/api';
import { showConfirm, showSimpleAlert } from '../../services/alert';

const fmt = (iso?: string) => (iso ? new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' }) : '');
const money = (n?: number) => (typeof n === 'number' ? `$${n.toLocaleString(undefined, { maximumFractionDigits: 2 })}` : '');

type Props = { orgId: string; customer: any; colors: any; busy: boolean; act: (fn: () => Promise<any>, okTitle?: string) => Promise<any> };

const openUrl = (url: string) => (Platform.OS === 'web' ? window.open(url, '_blank') : Linking.openURL(url));

async function copy(url: string, what: string) {
  await Clipboard.setStringAsync(url);
  showSimpleAlert(`${what} copied`, 'Paste it into a text or email.');
}

export function BillingPanel({ orgId, customer: c, colors, busy, act }: Props) {
  const subscribed = !!c.stripe_subscription_id && ['active', 'trialing', 'past_due'].includes(c.billing_status);
  const sentMsg = (sent: any) => `Text ${sent?.sms_sent ? 'sent' : 'not sent'} · email ${sent?.email_sent ? 'sent' : 'not sent'}.`;
  const sendLink = () => act(async () => {
    const res = await api.post(`/customers/${orgId}/payment-link`, { send: true });
    showSimpleAlert('Payment link sent', sentMsg(res.data.sent));
    return res;
  });
  const copyLink = () => act(async () => {
    const res = await api.post(`/customers/${orgId}/payment-link`, { send: false });
    await copy(res.data.url, 'Payment link');
    return res;
  });
  const check = () => act(() => api.post(`/customers/${orgId}/sync-billing`), 'Synced with Stripe');
  const portal = () => act(async () => {
    const res = await api.post(`/customers/${orgId}/portal-link`);
    await copy(res.data.url, 'Billing portal link');
    return res;
  });
  const cancel = (flag: boolean) => showConfirm(
    flag ? 'Cancel at period end?' : 'Resume the subscription?',
    flag ? `Access and billing continue until ${fmt(c.current_period_end)}, then stop.` : 'The scheduled cancellation is removed and billing continues.',
    () => act(() => api.post(`/customers/${orgId}/cancel`, { cancel: flag }), flag ? 'Cancellation scheduled' : 'Subscription resumed'),
  );

  const lines: string[] = [];
  if (subscribed) lines.push(`Stripe: ${c.subscription_status}${c.current_period_end ? ` · renews ${fmt(c.current_period_end)}` : ''}`);
  if (c.cancel_at_period_end) lines.push(`Cancellation scheduled for ${fmt(c.current_period_end)}`);
  if (c.billing_status === 'past_due') lines.push(`Payment failed ${fmt(c.payment_failed_at)} · access continues until ${fmt(c.grace_until)} (14-day grace)`);
  if (c.last_payment_at) lines.push(`Last payment ${money(c.last_payment_amount)} on ${fmt(c.last_payment_at)}`);
  if (c.billing_status === 'awaiting_payment') lines.push(`Payment link ${c.payment_link_sent_at ? `sent ${fmt(c.payment_link_sent_at)}` : 'created'} · expires ${fmt(c.checkout_expires_at)}`);
  if (c.billing_status === 'canceled') lines.push(`Subscription canceled ${fmt(c.canceled_at)} · send a new payment link to restart`);

  const Btn = ({ label, onPress, testID, icon, tone = 'plain' }: { label: string; onPress: () => void; testID: string; icon: any; tone?: 'gold' | 'plain' | 'red' }) => (
    <TouchableOpacity onPress={onPress} disabled={busy} data-testid={testID}
      style={{ flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 12, paddingVertical: 9, borderRadius: 10, borderWidth: 1,
        borderColor: tone === 'gold' ? '#C9A962' : tone === 'red' ? '#FF3B30' : colors.border, backgroundColor: tone === 'gold' ? '#C9A962' : colors.card, opacity: busy ? 0.6 : 1 }}>
      <Ionicons name={icon} size={15} color={tone === 'gold' ? '#111' : tone === 'red' ? '#FF3B30' : colors.text} />
      <Text style={{ fontSize: 13, fontWeight: '600', color: tone === 'gold' ? '#111' : tone === 'red' ? '#FF3B30' : colors.text }}>{label}</Text>
    </TouchableOpacity>
  );

  return (
    <View style={{ gap: 10, backgroundColor: colors.card, borderRadius: 12, borderWidth: 1, borderColor: colors.border, padding: 14 }} data-testid="billing-panel">
      <Text style={{ fontSize: 13, fontWeight: '700', color: '#8E8E93', letterSpacing: 1.2 }}>STRIPE BILLING</Text>
      {lines.length ? lines.map((l, i) => <Text key={i} style={{ fontSize: 14, color: colors.text }} data-testid={`billing-line-${i}`}>{l}</Text>)
        : <Text style={{ fontSize: 14, color: colors.textSecondary }} data-testid="billing-line-0">No Stripe subscription yet. Card details are entered on Stripe's page, never in the app.</Text>}
      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
        {!subscribed ? <Btn label={c.billing_status === 'awaiting_payment' ? 'Resend payment link' : 'Send payment link'} onPress={sendLink} testID="billing-send-link" icon="paper-plane" tone="gold" /> : null}
        {!subscribed ? <Btn label="Copy payment link" onPress={copyLink} testID="billing-copy-link" icon="copy" /> : null}
        <Btn label={subscribed ? 'Sync with Stripe' : 'Check payment'} onPress={check} testID="billing-check" icon="refresh" />
        {c.stripe_customer_id ? <Btn label="Billing portal link" onPress={portal} testID="billing-portal-link" icon="card" /> : null}
        {subscribed && !c.cancel_at_period_end ? <Btn label="Cancel at period end" onPress={() => cancel(true)} testID="billing-cancel" icon="close-circle" tone="red" /> : null}
        {subscribed && c.cancel_at_period_end ? <Btn label="Resume subscription" onPress={() => cancel(false)} testID="billing-resume" icon="play-circle" tone="gold" /> : null}
        {c.stripe_subscription_id ? <Btn label="Open in Stripe" onPress={() => openUrl(`https://dashboard.stripe.com/test/subscriptions/${c.stripe_subscription_id}`)} testID="billing-open-stripe" icon="open-outline" /> : null}
      </View>
    </View>
  );
}
