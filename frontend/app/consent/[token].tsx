import React, { useEffect, useState } from 'react';
import { ActivityIndicator, ScrollView, Text, TextInput, TouchableOpacity, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useLocalSearchParams } from 'expo-router';
import api from '../../services/api';
import { GOLD, GREEN, RADIUS, RED, SPACE, TYPE, tid, tint } from '../../components/ui/tokens';

const BG = '#0E0E10', CARD = '#1C1C1E', TEXT = '#F2F2F7', SUB = '#A1A1AA', LINE = '#2C2C2E';

/** Public opt-in page the contact completes on their own phone. Nothing is pre-checked: every scope, the agreement and the
 *  last four digits are the contact's own affirmative input (recorded with time, IP and device as evidence). */
export default function ConsentOptInPage() {
  const { token } = useLocalSearchParams<{ token: string }>();
  const [info, setInfo] = useState<any>(null);
  const [error, setError] = useState('');
  const [picked, setPicked] = useState<string[]>([]);
  const [agree, setAgree] = useState(false);
  const [last4, setLast4] = useState('');
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<string[] | null>(null);

  useEffect(() => {
    api.get(`/public/consent/${token}`).then(r => setInfo(r.data)).catch(e => setError(e?.response?.data?.detail || 'This link is not valid.'));
  }, [token]);

  const toggle = (s: string) => setPicked(p => (p.includes(s) ? p.filter(x => x !== s) : [...p, s]));
  const can = picked.length > 0 && agree && last4.replace(/\D/g, '').length === 4 && !busy;
  const submit = async () => {
    setBusy(true); setError('');
    try { setDone((await api.post(`/public/consent/${token}`, { scopes: picked, agree, confirm_last4: last4.replace(/\D/g, '') })).data.recorded); }
    catch (e: any) { setError(e?.response?.data?.detail || 'Could not save your choice. Try again.'); }
    finally { setBusy(false); }
  };

  const shell = (children: React.ReactNode) => (
    <SafeAreaView style={{ flex: 1, backgroundColor: BG }}>
      <ScrollView contentContainerStyle={{ padding: SPACE.xl, gap: SPACE.lg, maxWidth: 560, width: '100%', alignSelf: 'center' }} keyboardShouldPersistTaps="handled">{children}</ScrollView>
    </SafeAreaView>
  );

  if (!info && !error) return shell(<ActivityIndicator color={GOLD} style={{ marginTop: 80 }} />);
  if (!info) return shell(<Text style={{ color: TEXT, fontSize: 18, marginTop: 60, textAlign: 'center' }} {...tid('consent-public-error')}>{error}</Text>);
  if (done) {
    return shell(
      <View style={{ alignItems: 'center', gap: SPACE.md, marginTop: 60 }} {...tid('consent-public-done')}>
        <Ionicons name="checkmark-circle" size={64} color={GREEN} />
        <Text style={{ color: TEXT, fontSize: 24, fontWeight: '800', textAlign: 'center' }}>You're all set</Text>
        <Text style={{ color: SUB, fontSize: TYPE.body, textAlign: 'center', lineHeight: 22 }}>{info.business} can now text you as you chose. Reply STOP to any text to opt out, or HELP for help.</Text>
      </View>,
    );
  }
  if (info.used) return shell(<Text style={{ color: TEXT, fontSize: 18, marginTop: 60, textAlign: 'center' }} {...tid('consent-public-used')}>This opt-in was already completed. Thank you.</Text>);

  return shell(
    <>
      <Text style={{ color: GOLD, fontSize: TYPE.label, fontWeight: '800', letterSpacing: 1.4 }}>TEXT MESSAGE OPT-IN</Text>
      <Text style={{ color: TEXT, fontSize: 26, fontWeight: '800' }} {...tid('consent-public-business')}>{info.business}</Text>
      <Text style={{ color: SUB, fontSize: TYPE.body, lineHeight: 22 }}>Choose what {info.business} may text to your number ending in {info.phone_last4}. You can opt out at any time by replying STOP.</Text>
      {info.opted_out ? <Text style={{ color: RED, fontSize: TYPE.sub }}>You opted out earlier. To turn texts back on, text START to the business's number.</Text> : null}
      {(info.scopes || []).map((s: any) => {
        const on = picked.includes(s.scope);
        return (
          <TouchableOpacity key={s.scope} onPress={() => toggle(s.scope)} activeOpacity={0.85} {...tid(`consent-public-scope-${s.scope}`)}
            style={{ flexDirection: 'row', gap: SPACE.md, padding: SPACE.lg, borderRadius: RADIUS.md, backgroundColor: CARD, borderWidth: 1, borderColor: on ? GOLD : LINE }}>
            <Ionicons name={on ? 'checkbox' : 'square-outline'} size={24} color={on ? GOLD : SUB} />
            <View style={{ flex: 1, gap: 4 }}>
              <Text style={{ color: TEXT, fontSize: TYPE.body, fontWeight: '700' }}>{s.label}</Text>
              <Text style={{ color: SUB, fontSize: TYPE.sub, lineHeight: 19 }}>{s.text}</Text>
            </View>
          </TouchableOpacity>
        );
      })}
      <Text style={{ color: SUB, fontSize: TYPE.sub }}>Confirm the last 4 digits of your mobile number</Text>
      <TextInput value={last4} onChangeText={t => setLast4(t.replace(/\D/g, '').slice(0, 4))} keyboardType="number-pad" maxLength={4} placeholder="0000" placeholderTextColor="#555"
        style={{ backgroundColor: CARD, borderRadius: RADIUS.sm, borderWidth: 1, borderColor: LINE, color: TEXT, fontSize: 22, letterSpacing: 6, padding: 14, width: 140 }} {...tid('consent-public-last4')} />
      <TouchableOpacity onPress={() => setAgree(a => !a)} style={{ flexDirection: 'row', gap: SPACE.md, alignItems: 'flex-start' }} {...tid('consent-public-agree')}>
        <Ionicons name={agree ? 'checkbox' : 'square-outline'} size={24} color={agree ? GOLD : SUB} />
        <Text style={{ flex: 1, color: TEXT, fontSize: TYPE.sub, lineHeight: 20 }}>I agree to receive the texts I checked above at this number. Consent is not a condition of purchase.</Text>
      </TouchableOpacity>
      {error ? <Text style={{ color: RED, fontSize: TYPE.sub }} {...tid('consent-public-submit-error')}>{error}</Text> : null}
      <TouchableOpacity onPress={submit} disabled={!can} {...tid('consent-public-submit')}
        style={{ backgroundColor: GOLD, borderRadius: RADIUS.md, paddingVertical: 16, alignItems: 'center', opacity: can ? 1 : 0.4 }}>
        {busy ? <ActivityIndicator color="#111" /> : <Text style={{ color: '#111', fontSize: TYPE.section, fontWeight: '800' }}>Save my choice</Text>}
      </TouchableOpacity>
      <Text style={{ color: '#6E6E73', fontSize: TYPE.caption, lineHeight: 17, backgroundColor: tint('#FFFFFF', 0.02) }}>Msg & data rates may apply. Message frequency varies. Version {info.version}.</Text>
    </>,
  );
}
