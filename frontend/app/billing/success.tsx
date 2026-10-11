import React, { useEffect, useState } from 'react';
import { ActivityIndicator, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useLocalSearchParams } from 'expo-router';
import api from '../../services/api';

type State = { kind: 'checking' } | { kind: 'paid'; business: string; plan: string; activated: boolean } | { kind: 'pending'; business: string } | { kind: 'error'; message: string };

export default function BillingSuccess() {
  const { session_id } = useLocalSearchParams<{ session_id?: string }>();
  const [state, setState] = useState<State>({ kind: 'checking' });

  useEffect(() => {
    if (!session_id) { setState({ kind: 'error', message: 'This link is missing its payment reference.' }); return; }
    api.post('/billing/checkout/confirm', { session_id })
      .then((res) => {
        const d = res.data;
        if (d.payment_status === 'paid' || d.payment_status === 'no_payment_required') setState({ kind: 'paid', business: d.business_name, plan: d.plan_name, activated: d.activated });
        else setState({ kind: 'pending', business: d.business_name });
      })
      .catch((e) => setState({ kind: 'error', message: e?.response?.data?.detail || 'We could not confirm the payment yet.' }));
  }, [session_id]);

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: '#0E0E10', alignItems: 'center', justifyContent: 'center', padding: 24 }}>
      <View style={{ maxWidth: 440, width: '100%', backgroundColor: '#17171A', borderRadius: 16, padding: 28, gap: 14, borderWidth: 1, borderColor: '#2A2A2E' }} data-testid="billing-success-card">
        {state.kind === 'checking' ? (<><ActivityIndicator color="#C9A962" /><Text style={{ color: '#C7C7CC', fontSize: 16 }}>Confirming your payment with Stripe...</Text></>) : null}
        {state.kind === 'paid' ? (
          <>
            <Ionicons name="checkmark-circle" size={44} color="#34C759" />
            <Text style={{ color: '#FFF', fontSize: 22, fontWeight: '800' }} data-testid="billing-success-title">Payment received</Text>
            <Text style={{ color: '#C7C7CC', fontSize: 16, lineHeight: 23 }}>
              Thank you. <Text style={{ fontWeight: '700', color: '#FFF' }}>{state.business}</Text> is set up on the {state.plan} plan.
              {state.activated ? ' Your account is active: open the app and sign in.' : ' Your I\'m On Social contact will activate your account and text you a sign-in link shortly.'}
            </Text>
            <Text style={{ color: '#8E8E93', fontSize: 13 }}>Receipts and card changes: Stripe emails you a receipt, and Billing inside the app opens your Stripe billing portal.</Text>
          </>
        ) : null}
        {state.kind === 'pending' ? (
          <>
            <Ionicons name="time" size={44} color="#FF9500" />
            <Text style={{ color: '#FFF', fontSize: 22, fontWeight: '800' }} data-testid="billing-success-title">Payment processing</Text>
            <Text style={{ color: '#C7C7CC', fontSize: 16 }}>Stripe is still processing the payment for {state.business}. You will get a receipt by email once it clears.</Text>
          </>
        ) : null}
        {state.kind === 'error' ? (
          <>
            <Ionicons name="alert-circle" size={44} color="#FF3B30" />
            <Text style={{ color: '#FFF', fontSize: 22, fontWeight: '800' }} data-testid="billing-success-title">Not confirmed</Text>
            <Text style={{ color: '#C7C7CC', fontSize: 16 }} data-testid="billing-success-error">{state.message}</Text>
          </>
        ) : null}
      </View>
    </SafeAreaView>
  );
}
