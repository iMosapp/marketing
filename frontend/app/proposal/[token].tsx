import React, { useEffect, useState } from 'react';
import { View, Text, ScrollView, TouchableOpacity, ActivityIndicator, TextInput, useWindowDimensions } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useLocalSearchParams } from 'expo-router';
import api from '../../services/api';
import { openUrl } from '../../components/mystery-shops/ReportView';
import { money, GOLD, GREEN, RED, tid, type Dept } from '../../components/mystery-shops/shared';

const L = { bg: '#F6F4EE', card: '#FFFFFF', border: '#E4DFD2', text: '#161616', textSecondary: '#6B6B6B' };
type P = { status: string; terms: any; currency?: string; per_month?: Record<string, number>; departments?: Dept[]; offering?: { label: string; plural: string }; business_noun?: string; client_name: string; contact_name: string; contact_email: string; sender_name: string; sections: { title: string; body: string }[]; signer?: any; signed_at?: string | null; invoice?: { hosted_invoice_url?: string; status?: string; amount?: number }; kickoff_url?: string | null };

// The client GM opens this from the proposal email: read, type name, agree, sign. Stripe emails the first invoice right after.
export default function PublicProposal() {
  const { token } = useLocalSearchParams<{ token: string }>();
  const { width } = useWindowDimensions();
  const [p, setP] = useState<P | null>(null);
  const [error, setError] = useState('');
  const [name, setName] = useState('');
  const [title, setTitle] = useState('');
  const [email, setEmail] = useState('');
  const [agree, setAgree] = useState(false);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<{ invoice?: { hosted_invoice_url?: string; status?: string; amount?: number }; kickoff_url?: string | null } | null>(null);
  const [err, setErr] = useState('');

  useEffect(() => {
    if (!token) return;
    api.get(`/public/proposal/${token}`).then(r => { setP(r.data); setName(r.data.contact_name || ''); setEmail(r.data.contact_email || ''); }).catch(() => setError('This proposal link is not valid anymore.'));
  }, [token]);

  const sign = async () => {
    setBusy(true); setErr('');
    try { const r = await api.post(`/public/proposal/${token}/sign`, { name, title, email, agree }, { timeout: 90000 }); setDone(r.data); }
    catch (e: any) { setErr(e?.response?.data?.detail || 'Something went wrong, try again'); }
    finally { setBusy(false); }
  };

  const wide = width > 800;
  const signed = !!done || (p && ['signed', 'paid'].includes(p.status));
  const invoice = done?.invoice || p?.invoice;
  const kickoffUrl = done?.kickoff_url || p?.kickoff_url;
  const t = p?.terms || {};
  const per: Record<string, number> = p?.per_month && Object.keys(p.per_month).length ? p.per_month : { sales: t.sales_per_month || 0, service: t.service_per_month || 0 };
  const label = (k: string) => (p?.departments || []).find(d => d.key === k)?.label?.toLowerCase() || k.replace(/^[a-z]+_/, '').replace(/_/g, ' ');
  const tiles = [...Object.entries(per).filter(([, n]) => (n || 0) > 0).map(([k, n]) => [String(n), `${label(k)} shops / month`]), [money(t.price_monthly, p?.currency), 'per month'], [`${t.term_months} mo`, 'initial term']];
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: L.bg }}>
      <ScrollView contentContainerStyle={{ padding: wide ? 32 : 16, paddingBottom: 60, alignItems: 'center' }} keyboardShouldPersistTaps="handled">
        <View style={{ width: '100%', maxWidth: 760, gap: 18 }}>
          <Text style={{ fontSize: 11, fontWeight: '800', color: GOLD, letterSpacing: 2 }}>I'M ON SOCIAL · PROPOSAL</Text>
          {error ? <Text style={{ fontSize: 15, color: L.textSecondary }} {...tid('proposal-error')}>{error}</Text> : !p ? <ActivityIndicator color={GOLD} style={{ marginTop: 40 }} /> : (
            <>
              <Text style={{ fontSize: wide ? 32 : 26, fontWeight: '800', color: L.text }} {...tid('proposal-title')}>Phone mystery shopping for {p.client_name}</Text>
              <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 10 }}>
                {tiles.map(([v, l]) => (
                  <View key={l} style={{ flex: 1, minWidth: 140, backgroundColor: L.card, borderRadius: 14, padding: 14, borderWidth: 1, borderColor: L.border }}>
                    <Text style={{ fontSize: 24, fontWeight: '800', color: L.text }}>{v}</Text><Text style={{ fontSize: 12, color: L.textSecondary, fontWeight: '700' }}>{l.toUpperCase()}</Text>
                  </View>
                ))}
              </View>
              {p.sections.map((s, i) => (
                <View key={i} style={{ gap: 4 }} {...tid(`proposal-section-${i}`)}>
                  <Text style={{ fontSize: 15, fontWeight: '800', color: L.text }}>{s.title}</Text>
                  <Text style={{ fontSize: 15, color: L.text, lineHeight: 23 }}>{s.body}</Text>
                </View>
              ))}

              {signed ? (
                <View style={{ backgroundColor: L.card, borderRadius: 18, padding: 20, borderWidth: 1, borderColor: GREEN + '88', gap: 10 }} {...tid('proposal-signed')}>
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}><Ionicons name="checkmark-circle" size={26} color={GREEN} /><Text style={{ fontSize: 18, fontWeight: '800', color: L.text }}>Signed{p.signer?.name || name ? ` by ${p.signer?.name || name}` : ''}</Text></View>
                  {invoice?.hosted_invoice_url ? (
                    <>
                      <Text style={{ fontSize: 15, color: L.text, lineHeight: 22 }}>Your first invoice for {money(invoice.amount, p?.currency)} is on its way to {p.signer?.email || email}. You can pay it right now by card or bank transfer, and the shops begin as soon as it clears.</Text>
                      <TouchableOpacity onPress={() => openUrl(invoice.hosted_invoice_url!)} style={{ height: 50, borderRadius: 14, backgroundColor: invoice.status === 'paid' ? GREEN : GOLD, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 8 }} {...tid('proposal-pay')}>
                        <Ionicons name={invoice.status === 'paid' ? 'checkmark' : 'card'} size={18} color="#111" /><Text style={{ fontSize: 16, fontWeight: '800', color: '#111' }}>{invoice.status === 'paid' ? 'Paid, thank you' : `Pay ${money(invoice.amount, p?.currency)} now`}</Text>
                      </TouchableOpacity>
                    </>
                  ) : <Text style={{ fontSize: 15, color: L.text, lineHeight: 22 }}>Thank you. {p.sender_name || 'We'} will send your first invoice shortly.</Text>}
                  {!!kickoffUrl && (
                    <View style={{ gap: 8, marginTop: 6, paddingTop: 14, borderTopWidth: 1, borderTopColor: L.border }}>
                      <Text style={{ fontSize: 15, fontWeight: '800', color: L.text }}>Next: tell us who to shop</Text>
                      <Text style={{ fontSize: 14, color: L.textSecondary, lineHeight: 20 }}>Five minutes: your business hours, a few {p.offering?.plural || 'vehicles'} our caller can mention, and the names and cell numbers of the people to shop. No login, and you can come back to it any time.</Text>
                      <TouchableOpacity onPress={() => openUrl(kickoffUrl)} style={{ height: 48, borderRadius: 14, borderWidth: 1.5, borderColor: GOLD, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 8 }} {...tid('proposal-kickoff')}>
                        <Ionicons name="clipboard-outline" size={18} color={GOLD} /><Text style={{ fontSize: 15, fontWeight: '800', color: GOLD }}>Set up your {p.business_noun || 'store'} now</Text>
                      </TouchableOpacity>
                    </View>
                  )}
                </View>
              ) : (
                <View style={{ backgroundColor: L.card, borderRadius: 18, padding: 20, borderWidth: 1, borderColor: L.border, gap: 14 }} {...tid('proposal-sign-card')}>
                  <Text style={{ fontSize: 18, fontWeight: '800', color: L.text }}>Sign to get started</Text>
                  <View style={{ flexDirection: wide ? 'row' : 'column', gap: 10 }}>
                    <TextInput value={name} onChangeText={setName} placeholder="Your full name" placeholderTextColor={L.textSecondary} style={[inp, { flex: 1.4 }]} {...tid('proposal-sign-name')} />
                    <TextInput value={title} onChangeText={setTitle} placeholder="Title (GM, Owner)" placeholderTextColor={L.textSecondary} style={[inp, { flex: 1 }]} {...tid('proposal-sign-title')} />
                  </View>
                  <TextInput value={email} onChangeText={setEmail} placeholder="Email for the invoice and report" placeholderTextColor={L.textSecondary} keyboardType="email-address" autoCapitalize="none" style={inp} {...tid('proposal-sign-email')} />
                  {!!name.trim() && <View style={{ borderBottomWidth: 1, borderBottomColor: L.text, paddingBottom: 4, alignSelf: 'flex-start', minWidth: 220 }}><Text style={{ fontSize: 30, fontStyle: 'italic', color: L.text, fontFamily: 'cursive' as any }} {...tid('proposal-sign-preview')}>{name}</Text><Text style={{ fontSize: 10, color: L.textSecondary, letterSpacing: 1 }}>ELECTRONIC SIGNATURE</Text></View>}
                  <TouchableOpacity onPress={() => setAgree(a => !a)} style={{ flexDirection: 'row', alignItems: 'flex-start', gap: 10 }} {...tid('proposal-sign-agree')}>
                    <Ionicons name={agree ? 'checkbox' : 'square-outline'} size={24} color={agree ? GOLD : L.textSecondary} />
                    <Text style={{ flex: 1, fontSize: 14, color: L.text, lineHeight: 20 }}>I have authority to sign for {p.client_name} and agree to the terms above, including recording and evaluating our staff's business calls.</Text>
                  </TouchableOpacity>
                  {!!err && <Text style={{ fontSize: 13.5, color: RED, fontWeight: '600' }} {...tid('proposal-sign-error')}>{err}</Text>}
                  <TouchableOpacity onPress={sign} disabled={busy || !agree || name.trim().length < 3 || !email.includes('@')} style={{ height: 50, borderRadius: 14, backgroundColor: agree && name.trim().length >= 3 && email.includes('@') ? GOLD : L.border, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 8 }} {...tid('proposal-sign-submit')}>
                    {busy ? <ActivityIndicator color="#111" /> : <Ionicons name="create" size={18} color="#111" />}<Text style={{ fontSize: 16, fontWeight: '800', color: '#111' }}>{busy ? 'Signing…' : 'Sign and send my first invoice'}</Text>
                  </TouchableOpacity>
                </View>
              )}
              <Text style={{ fontSize: 12, color: L.textSecondary, textAlign: 'center', marginTop: 10 }}>I'm On Social LLC · 1741 Lunford Ln, Riverton, UT 84065 · Prepared by {p.sender_name}</Text>
            </>
          )}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const inp = { backgroundColor: '#F6F4EE', borderRadius: 12, borderWidth: 1, borderColor: '#E4DFD2', paddingHorizontal: 12, height: 46, color: '#161616', fontSize: 15 } as const;
