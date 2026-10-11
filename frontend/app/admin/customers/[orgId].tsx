import React, { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, ScrollView, Text, TextInput, TouchableOpacity, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useThemeStore } from '../../../store/themeStore';
import { useAuthStore } from '../../../store/authStore';
import api from '../../../services/api';
import { showConfirm, showSimpleAlert } from '../../../services/alert';
import { ScreenHeader } from '../../../components/common/ScreenHeader';
import { StatusPill } from '../../../components/customers/StatusPill';
import { ExceptionSheet } from '../../../components/customers/ExceptionSheet';
import { BillingPanel } from '../../../components/customers/BillingPanel';
import { Step, StepRail } from '../../../components/customers/StepRail';

const fmt = (iso?: string) => (iso ? new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' }) : '');
const money = (n?: number) => (typeof n === 'number' ? `$${n.toLocaleString(undefined, { maximumFractionDigits: 0 })}` : '');

export default function CustomerScreen() {
  const { orgId } = useLocalSearchParams<{ orgId: string }>();
  const router = useRouter();
  const { colors } = useThemeStore();
  const me = useAuthStore((s) => s.user);
  const isSuper = me?.role === 'super_admin';
  const [row, setRow] = useState<any>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [showException, setShowException] = useState(false);
  const [notes, setNotes] = useState('');

  const load = useCallback(async () => {
    try {
      const res = await api.get(`/customers/${orgId}`);
      setRow(res.data);
      setNotes(res.data?.customer?.notes || '');
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Could not load this customer');
    }
  }, [orgId]);

  useEffect(() => { load(); }, [load]);

  const act = async (fn: () => Promise<any>, okTitle?: string) => {
    setBusy(true);
    try {
      const res = await fn();
      await load();
      if (okTitle) showSimpleAlert(okTitle, res?.data?.message);
      return res;
    } catch (e: any) {
      showSimpleAlert('Not done', e?.response?.data?.detail || 'Something went wrong');
    } finally {
      setBusy(false);
    }
  };

  if (error) {
    return (
      <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
        <ScreenHeader title="Customer" testID="customer-header" />
        <Text style={{ padding: 24, color: colors.textSecondary, fontSize: 16 }} data-testid="customer-error">{error}</Text>
      </SafeAreaView>
    );
  }
  if (!row) {
    return <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg, alignItems: 'center', justifyContent: 'center' }}><ActivityIndicator color={colors.accent} /></SafeAreaView>;
  }

  const c = row.customer || {};
  const owner = row.owner;
  const billingOk = ['active', 'trialing', 'exception'].includes(c.billing_status) && !c.exception_expired;
  const activated = !!c.activated_at;
  const invited = !!c.owner_invited_at;
  const ownerActive = !!c.owner_activated_at || !!owner?.activated;
  const exc = c.billing_exception;
  const billingDetail = () => {
    if (c.billing_status === 'exception') return `Billing exception: ${exc?.reason} (ends ${fmt(exc?.expires_at)}). Not a Stripe payment.`;
    if (c.billing_status === 'active' || c.billing_status === 'trialing') return `Paid through Stripe${c.current_period_end ? ` · renews ${fmt(c.current_period_end)}` : ''}${c.cancel_at_period_end ? ' · cancellation scheduled' : ''}`;
    if (c.billing_status === 'past_due') return `Payment failed · Stripe is retrying · access continues until ${fmt(c.grace_until)}`;
    if (c.billing_status === 'awaiting_payment') return `Payment link sent ${fmt(c.payment_link_sent_at || c.checkout_created_at)} · waiting for the owner to pay on Stripe`;
    if (c.billing_status === 'canceled') return `Subscription canceled ${fmt(c.canceled_at)} · send a new payment link or grant an exception`;
    if (c.exception_expired) return `The billing exception ended ${fmt(exc?.expires_at)}. Grant a new one or send a payment link.`;
    return 'Text or email the owner a Stripe payment link (card details go to Stripe, never to us). A super admin can also grant a billing exception with a reason and an end date.';
  };
  const sendLink = () => act(async () => {
    const res = await api.post(`/customers/${orgId}/payment-link`, { send: true });
    showSimpleAlert('Payment link sent', `Text ${res.data.sent?.sms_sent ? 'sent' : 'not sent'} · email ${res.data.sent?.email_sent ? 'sent' : 'not sent'}.`);
    return res;
  });

  const steps: Step[] = [
    {
      key: 'created', title: 'Customer created', done: true,
      detail: `${c.plan_name} · ${money(c.amount)}/mo · ${row.seats.included} seats included${row.seats.extra ? ` + ${row.seats.extra} extra` : ''} · created ${fmt(c.created_at)}`,
    },
    {
      key: 'billing', title: 'Plan and payment', done: billingOk, current: !billingOk,
      detail: billingDetail(),
      action: isSuper && !billingOk ? (c.billing_status === 'awaiting_payment'
        ? { label: 'Check payment', onPress: () => act(() => api.post(`/customers/${orgId}/sync-billing`), 'Synced with Stripe'), testID: 'customer-check-payment-btn' }
        : { label: 'Send payment link', onPress: sendLink, testID: 'customer-payment-link-btn' }) : undefined,
      secondary: isSuper && !billingOk ? { label: 'Grant billing exception instead', onPress: () => setShowException(true), testID: 'customer-exception-btn' } : undefined,
    },
    {
      key: 'activate', title: 'Activate account', done: activated, current: billingOk && !activated,
      detail: activated ? `Activated ${fmt(c.activated_at)}. The company is live and the owner can be invited.` : 'Turns the company on and unlocks the owner login. Needs payment or a billing exception first.',
      action: isSuper && !activated ? {
        label: 'Activate account', testID: 'customer-activate-btn', disabled: !billingOk,
        onPress: () => showConfirm('Activate this account?', `${row.name} goes live and the owner can be invited.`, () => act(() => api.post(`/customers/${orgId}/activate`), 'Account activated')),
      } : undefined,
    },
    {
      key: 'invite', title: 'Invite the owner', done: invited, current: activated && !invited,
      detail: owner ? `${owner.name} · ${owner.phone || 'no phone'}${owner.email ? ` · ${owner.email}` : ''}${invited ? ` · link sent ${fmt(c.owner_invited_at)}, expires ${fmt(c.invite_expires_at)}` : ''}` : 'No owner on file',
      action: isSuper && !invited ? {
        label: 'Send activation link', testID: 'customer-invite-btn', disabled: !activated,
        onPress: () => act(() => api.post(`/customers/${orgId}/invite-owner`), 'Invitation sent'),
      } : undefined,
      secondary: isSuper && invited && !ownerActive ? { label: 'Resend activation link', testID: 'customer-reinvite-btn', onPress: () => act(() => api.post(`/customers/${orgId}/invite-owner`), 'Invitation sent again') } : undefined,
    },
    {
      key: 'onboarding', title: 'Owner signs in and sets up', done: ownerActive, current: invited && !ownerActive,
      detail: ownerActive
        ? `Owner active since ${fmt(c.owner_activated_at)} · ${row.users.activated}/${row.users.total} people activated · ${row.users.with_work_number} with a work number · texting registration: ${row.store?.a2p_status || 'not started'}`
        : 'The owner taps the link, chooses a password and lands in the app. You get a push when that happens.',
      secondary: { label: 'Open team and phone numbers', testID: 'customer-open-org', onPress: () => router.push(`/admin/organizations/${orgId}` as any) },
    },
  ];

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      <ScreenHeader title={row.name} subtitle={`${row.city || ''}${row.state ? `, ${row.state}` : ''}`} testID="customer-header"
        right={<StatusPill status={c.onboarding_status} billing={c.billing_status} testID="customer-status" />} />
      <ScrollView contentContainerStyle={{ padding: 16, gap: 16, maxWidth: 760, alignSelf: 'center', width: '100%' }} keyboardShouldPersistTaps="handled">
        <View style={{ flexDirection: 'row', gap: 10 }}>
          <Stat colors={colors} label="Seats" value={`${row.seats.used}/${row.seats.limit}`} testID="customer-seats" />
          <Stat colors={colors} label="People active" value={`${row.users.activated}`} testID="customer-active-users" />
          <Stat colors={colors} label="Monthly" value={money(c.amount + (c.seat_price || 0) * (c.seats_extra || 0))} testID="customer-monthly" />
        </View>
        {isSuper && c.seat_price ? (
          <TouchableOpacity
            onPress={() => showConfirm('Add a seat?', `Adds one seat at ${money(c.seat_price)}/mo.${c.stripe_subscription_id ? ' The Stripe subscription is updated and the prorated amount is invoiced now.' : ' Billing follows once the customer pays through Stripe.'}`, () => act(() => api.patch(`/customers/${orgId}`, { seats_extra: (c.seats_extra || 0) + 1 }), 'Seat added'))}
            disabled={busy}
            style={{ alignSelf: 'flex-start', flexDirection: 'row', alignItems: 'center', gap: 6 }}
            data-testid="customer-add-seat"
          >
            <Ionicons name="add-circle" size={18} color="#C9A962" />
            <Text style={{ fontSize: 14, fontWeight: '600', color: '#C9A962' }}>Add a seat ({money(c.seat_price)}/mo)</Text>
          </TouchableOpacity>
        ) : null}

        {showException ? (
          <ExceptionSheet
            colors={colors}
            busy={busy}
            onCancel={() => setShowException(false)}
            onSubmit={(reason, expiresAt) => act(() => api.post(`/customers/${orgId}/billing-exception`, { reason, expires_at: expiresAt }), 'Exception recorded').then(() => setShowException(false))}
          />
        ) : null}

        <StepRail steps={steps} colors={colors} busy={busy} />

        {isSuper ? <BillingPanel orgId={orgId} customer={c} colors={colors} busy={busy} act={act} /> : null}

        {isSuper ? (
          <View style={{ gap: 8 }}>
            <Text style={{ fontSize: 13, fontWeight: '700', color: '#8E8E93', letterSpacing: 1.2 }}>NOTES</Text>
            <TextInput
              style={{ backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, borderRadius: 12, padding: 12, fontSize: 15, color: colors.text, minHeight: 60 }}
              value={notes}
              onChangeText={setNotes}
              onBlur={() => notes !== (c.notes || '') && act(() => api.patch(`/customers/${orgId}`, { notes }))}
              placeholder="Anything the next person should know"
              placeholderTextColor="#8E8E93"
              multiline
              data-testid="customer-notes"
            />
          </View>
        ) : null}

        <View style={{ gap: 6 }}>
          <Text style={{ fontSize: 13, fontWeight: '700', color: '#8E8E93', letterSpacing: 1.2 }}>HISTORY</Text>
          {(row.audit || []).map((a: any, i: number) => (
            <View key={i} style={{ flexDirection: 'row', gap: 8, paddingVertical: 6, borderBottomWidth: 0.5, borderBottomColor: colors.border }} data-testid={`audit-${a.action}`}>
              <Text style={{ fontSize: 13, color: colors.textTertiary, width: 92 }}>{fmt(a.at)}</Text>
              <Text style={{ fontSize: 13, color: colors.text, flex: 1 }}>
                {a.action.replace(/_/g, ' ')} · {a.actor_name}{a.details?.reason ? ` · ${a.details.reason}` : ''}
              </Text>
            </View>
          ))}
        </View>
        <View style={{ height: 40 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

function Stat({ colors, label, value, testID }: { colors: any; label: string; value: string; testID: string }) {
  return (
    <View style={{ flex: 1, backgroundColor: colors.card, borderRadius: 12, borderWidth: 1, borderColor: colors.border, padding: 12 }} data-testid={testID}>
      <Text style={{ fontSize: 12, color: colors.textSecondary }}>{label}</Text>
      <Text style={{ fontSize: 20, fontWeight: '800', color: colors.text, marginTop: 2 }}>{value}</Text>
    </View>
  );
}
