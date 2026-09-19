/** Public port-out packet: everything a dealership's new carrier needs to move numbers away from our Twilio account, plus the steps. */
import React, { useEffect, useState } from 'react';
import { View, Text, ScrollView, ActivityIndicator, useWindowDimensions, Linking, TouchableOpacity } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useLocalSearchParams } from 'expo-router';
import api from '../../services/api';
import { LIGHT, GOLD, GREEN } from '../../components/mystery-shops/shared';

const tid = (id: string) => ({ testID: id, dataSet: { testid: id } as any });
const Row = ({ label, value, testID, hint }: { label: string; value: string; testID: string; hint?: string }) => (
  <View style={{ paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: LIGHT.border, gap: 2 }} {...tid(testID)}>
    <Text style={{ fontSize: 11, fontWeight: '800', color: LIGHT.textSecondary, letterSpacing: 0.6, textTransform: 'uppercase' }}>{label}</Text>
    <Text style={{ fontSize: 17, fontWeight: '700', color: LIGHT.text }} selectable>{value}</Text>
    {!!hint && <Text style={{ fontSize: 12.5, color: LIGHT.textSecondary, lineHeight: 18 }}>{hint}</Text>}
  </View>
);

export default function PublicPortOut() {
  const { token } = useLocalSearchParams<{ token: string }>();
  const { width } = useWindowDimensions();
  const wide = width > 800;
  const [d, setD] = useState<any>(null);
  const [error, setError] = useState(false);
  useEffect(() => { if (token) api.get(`/public/port-out/${token}`).then(r => setD(r.data)).catch(() => setError(true)); }, [token]);
  const b = d?.business || {};
  const addr = [b.street, b.city, b.state && b.postal_code ? `${b.state} ${b.postal_code}` : b.state || b.postal_code].filter(Boolean).join(', ');
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: LIGHT.bg }}>
      <ScrollView contentContainerStyle={{ padding: wide ? 32 : 16, paddingBottom: 80, alignItems: 'center' }}>
        <View style={{ width: '100%', maxWidth: 720, gap: 18 }} {...tid('portout-page')}>
          <Text style={{ fontSize: 11, fontWeight: '800', color: GOLD, letterSpacing: 2 }}>PHONE NUMBER PORT-OUT</Text>
          {error ? <Text style={{ fontSize: 15, color: LIGHT.textSecondary }} {...tid('portout-error')}>This link is not valid any more. Reply to the message you received and we will send a fresh one.</Text> : !d ? <ActivityIndicator color={GOLD} style={{ marginTop: 40 }} /> : (
            <>
              <Text style={{ fontSize: wide ? 30 : 24, fontWeight: '800', color: LIGHT.text }} {...tid('portout-title')}>Moving {d.store?.name}'s numbers to a new carrier</Text>
              <Text style={{ fontSize: 15, color: LIGHT.text, lineHeight: 23 }}>Your numbers belong to you. Give the details below to your new carrier and they do the rest; we approve the request on our side the moment it arrives. One rule: <Text style={{ fontWeight: '800' }}>keep the numbers active with us until the port completes.</Text> A cancelled number cannot be moved.</Text>

              <View style={{ backgroundColor: LIGHT.card, borderRadius: 18, borderWidth: 1, borderColor: LIGHT.border, padding: 18 }} {...tid('portout-numbers')}>
                <Text style={{ fontSize: 18, fontWeight: '800', color: LIGHT.text, marginBottom: 6 }}>Numbers ({d.numbers.length})</Text>
                {d.numbers.length === 0 && <Text style={{ fontSize: 14, color: LIGHT.textSecondary }}>No active numbers are on this account right now.</Text>}
                {d.numbers.map((n: any, i: number) => (
                  <View key={n.number || i} style={{ flexDirection: 'row', alignItems: 'center', paddingVertical: 8, borderBottomWidth: i === d.numbers.length - 1 ? 0 : 1, borderBottomColor: LIGHT.border }} {...tid(`portout-number-${i}`)}>
                    <Text style={{ flex: 1, fontSize: 16, fontWeight: '700', color: LIGHT.text }} selectable>{n.number}</Text>
                    <Text style={{ fontSize: 13, color: LIGHT.textSecondary }}>{n.owner || ''}{n.status && n.status !== 'active' ? ` · ${n.status.replace('_', ' ')}` : ''}</Text>
                  </View>
                ))}
              </View>

              <View style={{ backgroundColor: LIGHT.card, borderRadius: 18, borderWidth: 1, borderColor: LIGHT.border, padding: 18 }} {...tid('portout-details')}>
                <Text style={{ fontSize: 18, fontWeight: '800', color: LIGHT.text }}>What your new carrier will ask for</Text>
                <Row label="Current carrier" value="Twilio" testID="portout-carrier" />
                <Row label="Account number" value={d.account_number || 'Ask us'} testID="portout-account" hint="The last 8 characters of the Twilio account. If their form only takes digits, use the digits in this string." />
                <Row label="Port-out PIN" value={d.pin || `Ask ${d.sender_name}; we request it from Twilio porting for you`} testID="portout-pin" hint="Required for US local numbers." />
                <Row label="Authorized name on the LOA" value={d.authorized_name} testID="portout-authorized" hint="Twilio, Inc. is the owner of record for the numbers, not the dealership." />
                <Row label="Service address" value={d.service_address || `Ask ${d.sender_name}; we confirm it with Twilio porting`} testID="portout-address" />
                {!!addr && <Row label="Your business (for the LOA signer)" value={`${b.legal_name || d.store?.name}, ${addr}`} testID="portout-business" />}
              </View>

              <View style={{ backgroundColor: LIGHT.card, borderRadius: 18, borderWidth: 1, borderColor: LIGHT.border, padding: 18, gap: 10 }} {...tid('portout-steps')}>
                <Text style={{ fontSize: 18, fontWeight: '800', color: LIGHT.text }}>Steps</Text>
                {d.steps.map((s: string, i: number) => (
                  <View key={i} style={{ flexDirection: 'row', gap: 10 }} {...tid(`portout-step-${i}`)}>
                    <View style={{ width: 24, height: 24, borderRadius: 12, backgroundColor: i === 0 ? GOLD : GREEN + '22', alignItems: 'center', justifyContent: 'center' }}><Text style={{ fontSize: 12, fontWeight: '800', color: i === 0 ? '#111' : GREEN }}>{i + 1}</Text></View>
                    <Text style={{ flex: 1, fontSize: 14.5, color: LIGHT.text, lineHeight: 21 }}>{s}</Text>
                  </View>
                ))}
              </View>

              <TouchableOpacity onPress={() => Linking.openURL(d.help_url)} style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }} {...tid('portout-help')}>
                <Ionicons name="open-outline" size={16} color={GOLD} />
                <Text style={{ fontSize: 14, fontWeight: '700', color: GOLD }}>Twilio's own port-away guide</Text>
              </TouchableOpacity>
              <Text style={{ fontSize: 13, color: LIGHT.textSecondary, lineHeight: 19 }}>Questions or a rejection notice: email {d.contact_email}. I'm On Social LLC · 1741 Lunford Ln, Riverton, UT 84065</Text>
            </>
          )}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}
