import React, { useState, useEffect } from 'react';
import {
  View, Text, StyleSheet, TouchableOpacity, ScrollView,
  TextInput, ActivityIndicator, Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useLocalSearchParams, useRouter } from 'expo-router';
import api from '../../../services/api';
import { showSimpleAlert } from '../../../services/alert';

export default function QuoteAcceptPage() {
  const { quoteId } = useLocalSearchParams<{ quoteId: string }>();
  const router = useRouter();

  const [loading, setLoading]     = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [quote, setQuote]         = useState<any>(null);

  // Signature form
  const [name, setName]           = useState('');
  const [email, setEmail]         = useState('');
  const [signature, setSignature] = useState('');
  const [agreed, setAgreed]       = useState(false);

  useEffect(() => { loadQuote(); }, [quoteId]);

  const loadQuote = async () => {
    try {
      const res = await api.get(`/subscriptions/quotes/${quoteId}/public`);
      setQuote(res.data);
      if (res.data.customer?.name)  setName(res.data.customer.name);
      if (res.data.customer?.email) setEmail(res.data.customer.email);
    } catch {
      showSimpleAlert('Error', 'This quote could not be found or has expired.');
    } finally {
      setLoading(false);
    }
  };

  const handleAccept = async () => {
    if (!name.trim())      return showSimpleAlert('Required', 'Please enter your full name.');
    if (!email.trim())     return showSimpleAlert('Required', 'Please enter your email address.');
    if (!signature.trim()) return showSimpleAlert('Required', 'Please type your signature to sign.');
    if (!agreed)           return showSimpleAlert('Required', 'Please agree to the terms to continue.');

    setSubmitting(true);
    try {
      await api.post(`/subscriptions/quotes/${quoteId}/accept`, { name, email, signature });
      await loadQuote(); // reload to show accepted state
    } catch (e: any) {
      showSimpleAlert('Error', e?.response?.data?.detail || 'Failed to submit. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <View style={s.center}>
        <ActivityIndicator size="large" color="#C9A962" />
        <Text style={s.loadingText}>Loading your quote...</Text>
      </View>
    );
  }

  if (!quote) {
    return (
      <View style={s.center}>
        <Ionicons name="alert-circle" size={64} color="#FF3B30" />
        <Text style={s.errorTitle}>Quote Not Found</Text>
        <Text style={s.errorSub}>This link is invalid or has expired.</Text>
      </View>
    );
  }

  // ── Accepted state ──────────────────────────────────────────────────────────
  if (quote.status === 'accepted') {
    const sig = quote.digital_signature || {};
    return (
      <View style={s.dark}>
        <SafeAreaView edges={['top', 'bottom']} style={{ flex: 1 }}>
          <ScrollView contentContainerStyle={s.acceptedContent}>
            <View style={{ alignItems: 'center', marginBottom: 32 }}>
              <Ionicons name="checkmark-circle" size={88} color="#34C759" />
              <Text style={s.acceptedTitle}>Quote Accepted!</Text>
              <Text style={s.acceptedSub}>Check your email for your signed copy and payment setup link.</Text>
            </View>

            <View style={s.darkCard}>
              <Row label="Quote"   value={quote.quote_number} mono />
              <Row label="Plan"    value={quote.plan_name} />
              <Row label="Total"   value={`$${quote.pricing?.final_price?.toFixed(2)}/${quote.pricing?.interval}`} green />
              {sig.signed_at && <Row label="Signed"  value={new Date(sig.signed_at).toLocaleString()} />}
            </View>

            <View style={[s.darkCard, { marginTop: 16, borderColor: '#FF9500', borderWidth: 1 }]}>
              <Text style={{ fontSize: 15, fontWeight: '700', color: '#FF9500', marginBottom: 8 }}>Next Step: Set Up Payment</Text>
              <Text style={{ fontSize: 14, color: '#CCC', lineHeight: 20 }}>
                A payment setup link has been sent to your email and phone. You'll need to complete this before your trial ends.
              </Text>
            </View>

            <Text style={s.footerNote}>Questions? support@imonsocial.com</Text>
          </ScrollView>
        </SafeAreaView>
      </View>
    );
  }

  // ── Expired / cancelled ─────────────────────────────────────────────────────
  if (quote.status === 'expired' || quote.status === 'cancelled') {
    return (
      <View style={s.center}>
        <Ionicons name="time" size={64} color="#FF9500" />
        <Text style={s.errorTitle}>Quote Expired</Text>
        <Text style={s.errorSub}>This quote is no longer valid. Contact us for a new one.</Text>
        <Text style={[s.errorSub, { color: '#C9A962', marginTop: 8 }]}>support@imonsocial.com</Text>
      </View>
    );
  }

  const p        = quote.pricing || {};
  const hasDisc  = (p.discount_percent || 0) > 0;
  const companyName = quote.business_info?.company_name;

  // ── Signing form ────────────────────────────────────────────────────────────
  return (
    <View style={s.dark}>
      <SafeAreaView edges={['top']} style={{ flex: 1 }}>
        {/* Header */}
        <View style={s.header}>
          <View style={{ flex: 1 }}>
            <Text style={s.headerTitle}>{companyName || quote.plan_name}</Text>
            <Text style={s.headerSub}>i'M On Social &mdash; Subscription Quote</Text>
          </View>
          <View style={[s.badge, { backgroundColor: '#C9A96220' }]}>
            <Text style={[s.badgeText, { color: '#C9A962' }]}>{quote.quote_number}</Text>
          </View>
        </View>

        <ScrollView style={{ flex: 1 }}>

          {/* Plan Summary */}
          <View style={s.section}>
            <Text style={s.secTitle}>Plan Summary</Text>
            <View style={s.card}>
              <PriceLine label="Plan"      value={quote.plan_name} />
              {quote.plan_type === 'store' && p.num_users && (
                <PriceLine label="Users"   value={`${p.num_users} users @ $${p.price_per_user?.toFixed(2)}/user`} />
              )}
              <PriceLine label="Base Price" value={`$${p.base_price?.toFixed(2)}/${p.interval}`} />
              {hasDisc && (
                <PriceLine label={`Discount (${p.discount_percent}%)`} value={`-$${(p.base_price - p.final_price).toFixed(2)}`} green />
              )}
              {(p.trial_days || 0) > 0 && (
                <PriceLine label="Free Trial" value={`${p.trial_days} days — no charge`} green />
              )}
              <View style={s.totalRow}>
                <Text style={s.totalLabel}>Total</Text>
                <Text style={s.totalValue}>${p.final_price?.toFixed(2)}/{p.interval}</Text>
              </View>
            </View>
          </View>

          {/* Terms */}
          <View style={s.section}>
            <Text style={s.secTitle}>Service Terms</Text>
            <View style={s.card}>
              {[
                ['Cancellation', 'Either party may cancel with 30 days written notice.'],
                ['Billing',      'Billed monthly on the date service begins.'],
                ['Trial',        `${p.trial_days || 7}-day free trial — no charge during trial period.`],
                ['Refunds',      'No refunds for partial billing periods.'],
                ['Governing',    'State of Texas.'],
              ].map(([label, val]) => (
                <View key={label} style={s.termRow}>
                  <Text style={s.termLabel}>{label}</Text>
                  <Text style={s.termVal}>{val}</Text>
                </View>
              ))}
              {quote.notes ? (
                <View style={s.termRow}>
                  <Text style={s.termLabel}>Notes</Text>
                  <Text style={s.termVal}>{quote.notes}</Text>
                </View>
              ) : null}
            </View>
          </View>

          {/* Signature */}
          <View style={s.section}>
            <Text style={s.secTitle}>Sign &amp; Accept</Text>

            <Text style={s.inputLabel}>Full Name *</Text>
            <TextInput style={s.input} value={name} onChangeText={setName} placeholder="Your full legal name" placeholderTextColor="#555" />

            <Text style={s.inputLabel}>Email Address *</Text>
            <TextInput style={s.input} value={email} onChangeText={setEmail} placeholder="your@email.com" placeholderTextColor="#555" keyboardType="email-address" autoCapitalize="none" />

            <Text style={s.inputLabel}>Type Your Signature *</Text>
            <TextInput style={s.input} value={signature} onChangeText={setSignature} placeholder="Type your full legal name to sign" placeholderTextColor="#555" />
            {signature ? (
              <View style={s.sigPreview}>
                <Text style={s.sigPreviewText}>{signature}</Text>
              </View>
            ) : null}

            <TouchableOpacity style={s.agreeRow} onPress={() => setAgreed(v => !v)}>
              <View style={[s.checkbox, agreed && s.checkboxOn]}>
                {agreed && <Ionicons name="checkmark" size={15} color="#000" />}
              </View>
              <Text style={s.agreeText}>
                I have read and agree to the service terms above, including the 30-day cancellation policy, and the{' '}
                <Text
                  style={{ color: '#C9A962', textDecorationLine: 'underline' }}
                  onPress={(e) => {
                    e.stopPropagation();
                    if (typeof window !== 'undefined') window.open('https://app.imonsocial.com/imos/terms', '_blank');
                  }}
                >
                  Terms of Service
                </Text>
                {' '}and{' '}
                <Text
                  style={{ color: '#C9A962', textDecorationLine: 'underline' }}
                  onPress={(e) => {
                    e.stopPropagation();
                    if (typeof window !== 'undefined') window.open('https://app.imonsocial.com/imos/privacy', '_blank');
                  }}
                >
                  Privacy Policy
                </Text>
                .
              </Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={[s.signBtn, (!agreed || submitting) && s.signBtnDisabled]}
              onPress={handleAccept}
              disabled={!agreed || submitting}
              data-testid="sign-quote-button"
            >
              {submitting
                ? <ActivityIndicator color="#000" />
                : <><Ionicons name="create" size={20} color="#000" /><Text style={s.signBtnText}>Sign &amp; Accept Quote</Text></>
              }
            </TouchableOpacity>
          </View>

          <View style={{ height: 48 }} />
        </ScrollView>
      </SafeAreaView>
    </View>
  );
}

// ── Small reusable sub-components ──────────────────────────────────────────────
function Row({ label, value, mono, green }: { label: string; value: string; mono?: boolean; green?: boolean }) {
  return (
    <View style={{ flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: '#2C2C2E' }}>
      <Text style={{ fontSize: 13, color: '#8E8E93' }}>{label}</Text>
      <Text style={{ fontSize: 13, fontFamily: mono ? 'monospace' : undefined, color: green ? '#34C759' : '#FFF', fontWeight: '600' }}>{value}</Text>
    </View>
  );
}

function PriceLine({ label, value, green }: { label: string; value: string; green?: boolean }) {
  return (
    <View style={{ flexDirection: 'row', justifyContent: 'space-between', marginBottom: 10 }}>
      <Text style={{ fontSize: 14, color: '#8E8E93' }}>{label}</Text>
      <Text style={{ fontSize: 14, color: green ? '#34C759' : '#FFF', fontWeight: '500' }}>{value}</Text>
    </View>
  );
}

const s = StyleSheet.create({
  dark:           { flex: 1, backgroundColor: '#000' },
  center:         { flex: 1, backgroundColor: '#000', alignItems: 'center', justifyContent: 'center', padding: 40 },
  loadingText:    { color: '#8E8E93', fontSize: 16, marginTop: 16 },
  errorTitle:     { fontSize: 22, fontWeight: '700', color: '#FFF', marginTop: 16 },
  errorSub:       { fontSize: 15, color: '#8E8E93', marginTop: 8, textAlign: 'center' },

  header:         { flexDirection: 'row', alignItems: 'center', padding: 16, borderBottomWidth: 1, borderBottomColor: '#1C1C1E' },
  headerTitle:    { fontSize: 18, fontWeight: '700', color: '#FFF' },
  headerSub:      { fontSize: 13, color: '#8E8E93', marginTop: 2 },
  badge:          { borderRadius: 8, paddingHorizontal: 10, paddingVertical: 5 },
  badgeText:      { fontSize: 12, fontWeight: '700', fontFamily: 'monospace' },

  section:        { padding: 20, paddingBottom: 0 },
  secTitle:       { fontSize: 17, fontWeight: '700', color: '#FFF', marginBottom: 12 },
  card:           { backgroundColor: '#1C1C1E', borderRadius: 14, padding: 16, marginBottom: 4 },

  totalRow:       { flexDirection: 'row', justifyContent: 'space-between', paddingTop: 12, borderTopWidth: 1, borderTopColor: '#3C3C3E', marginTop: 4 },
  totalLabel:     { fontSize: 16, fontWeight: '700', color: '#FFF' },
  totalValue:     { fontSize: 20, fontWeight: '800', color: '#34C759' },

  termRow:        { flexDirection: 'row', paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: '#2C2C2E', gap: 12 },
  termLabel:      { width: 90, fontSize: 12, fontWeight: '700', color: '#8E8E93', textTransform: 'uppercase', letterSpacing: 0.4, paddingTop: 1 },
  termVal:        { flex: 1, fontSize: 13, color: '#CCC', lineHeight: 18 },

  inputLabel:     { fontSize: 14, color: '#8E8E93', marginBottom: 6, marginTop: 14 },
  input:          { backgroundColor: '#1C1C1E', borderRadius: 10, padding: 14, fontSize: 16, color: '#FFF', borderWidth: 1, borderColor: '#2C2C2E' },

  sigPreview:     { backgroundColor: '#FFF', borderRadius: 10, padding: 18, alignItems: 'center', marginTop: 10 },
  sigPreviewText: { fontSize: 26, fontStyle: 'italic', color: '#000', fontFamily: Platform.OS === 'ios' ? 'Zapfino' : 'cursive' },

  agreeRow:       { flexDirection: 'row', alignItems: 'flex-start', marginTop: 20, gap: 12 },
  checkbox:       { width: 24, height: 24, borderRadius: 6, borderWidth: 2, borderColor: '#555', alignItems: 'center', justifyContent: 'center', marginTop: 1, flexShrink: 0 },
  checkboxOn:     { backgroundColor: '#34C759', borderColor: '#34C759' },
  agreeText:      { flex: 1, fontSize: 14, color: '#CCC', lineHeight: 20 },

  signBtn:        { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', backgroundColor: '#34C759', borderRadius: 14, padding: 18, marginTop: 24, gap: 10 },
  signBtnDisabled:{ backgroundColor: '#2C2C2E' },
  signBtnText:    { fontSize: 18, fontWeight: '700', color: '#000' },

  acceptedContent: { padding: 28, alignItems: 'center' },
  acceptedTitle:  { fontSize: 28, fontWeight: '700', color: '#FFF', marginTop: 20, marginBottom: 10 },
  acceptedSub:    { fontSize: 16, color: '#8E8E93', textAlign: 'center', lineHeight: 22, marginBottom: 32 },
  darkCard:       { backgroundColor: '#1C1C1E', borderRadius: 14, padding: 20, width: '100%' },
  footerNote:     { fontSize: 13, color: '#48484A', marginTop: 28, textAlign: 'center' },
});
