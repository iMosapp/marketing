/**
 * The link in Jessi's invite text. No login: the new user has no account yet. One button, Jessi rings them.
 */
import React, { useEffect, useRef, useState } from 'react';
import { View, Text, ActivityIndicator, useWindowDimensions, Image } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useLocalSearchParams } from 'expo-router';
import api from '../../services/api';
import { PrimaryButton } from '../../components/ui/PrimaryButton';
import { GOLD, GREEN, RED, tid, tint } from '../../components/ui/tokens';

const L = { bg: '#F6F4EE', card: '#FFFFFF', border: '#E4DFD2', text: '#161616', textSecondary: '#6B6B6B' };
type Info = { first_name: string; phone: string; state: string; paused: boolean; can_call: boolean; call_status?: string | null };

const STATUS_COPY: Record<string, string> = {
  dialing: 'Ringing your phone now. Pick up!',
  live: "You're on the call with Jessi.",
  ending: 'Wrapping up…',
  building: 'Jessi is writing up what she learned. Check your texts in a minute.',
  completed: 'All done. Jessi texted you the next step.',
  failed: "The call didn't connect. Tap the button to try again.",
  abandoned: 'Looks like the call got cut off. Tap the button and Jessi rings you again.',
};

export default function JessiCallPage() {
  const { token } = useLocalSearchParams<{ token: string }>();
  const { width } = useWindowDimensions();
  const [info, setInfo] = useState<Info | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [called, setCalled] = useState(false);
  const poll = useRef<any>(null);

  const load = async () => {
    try { const r = await api.get(`/onboarding-jessi/call/${token}`); setInfo(r.data); }
    catch (e: any) { setError(e?.response?.data?.detail || 'This link is not valid any more.'); }
  };
  useEffect(() => { if (token) load(); return () => clearInterval(poll.current); }, [token]);

  const call = async () => {
    setBusy(true); setError('');
    try {
      await api.post(`/onboarding-jessi/call/${token}`);
      setCalled(true);
      clearInterval(poll.current);
      poll.current = setInterval(load, 4000);
      await load();
    } catch (e: any) { setError(e?.response?.data?.detail || 'The call could not be placed. Try again in a minute.'); }
    finally { setBusy(false); }
  };

  const wide = width > 600;
  const status = info?.call_status || '';
  const inFlight = called || ['dialing', 'live', 'ending', 'building'].includes(status);
  const done = !!info && !info.can_call;
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: L.bg }} {...tid('jessi-call-page')}>
      <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', padding: wide ? 32 : 20 }}>
        <View style={{ width: '100%', maxWidth: 460, backgroundColor: L.card, borderRadius: 24, borderWidth: 1, borderColor: L.border, padding: wide ? 32 : 24, alignItems: 'center', gap: 14 }}>
          <Image source={require('../../assets/images/icon.png')} style={{ width: 56, height: 56, borderRadius: 14 }} />
          <Text style={{ fontSize: 11, fontWeight: '800', color: GOLD, letterSpacing: 2 }}>I'M ON SOCIAL</Text>
          {!info && !error ? <ActivityIndicator color={GOLD} style={{ marginVertical: 30 }} /> : error && !info ? (
            <>
              <Ionicons name="alert-circle" size={36} color={RED} />
              <Text style={{ fontSize: 17, fontWeight: '700', color: L.text, textAlign: 'center' }} {...tid('jessi-call-error')}>{error}</Text>
              <Text style={{ fontSize: 14, color: L.textSecondary, textAlign: 'center', lineHeight: 20 }}>Text Jessi back and she'll send you a fresh one.</Text>
            </>
          ) : info ? (
            <>
              <Text style={{ fontSize: wide ? 30 : 26, fontWeight: '800', color: L.text, textAlign: 'center', lineHeight: wide ? 36 : 32 }} {...tid('jessi-call-title')}>
                {done ? `You're all set, ${info.first_name}.` : `Hey ${info.first_name}, ready for your setup call?`}
              </Text>
              {done ? (
                <Text style={{ fontSize: 15, color: L.textSecondary, textAlign: 'center', lineHeight: 22 }} {...tid('jessi-call-done')}>Your interview is already done. Check your texts from Jessi for the next step.</Text>
              ) : (
                <>
                  <Text style={{ fontSize: 15, color: L.textSecondary, textAlign: 'center', lineHeight: 22 }}>
                    Jessi rings you at <Text style={{ fontWeight: '800', color: L.text }}>{info.phone}</Text> and asks about you, what you sell, your customers and how you like to talk with them. About 5 to 10 minutes, and that's what builds your profile and your assistant.
                  </Text>
                  {inFlight && (
                    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, paddingHorizontal: 14, paddingVertical: 10, borderRadius: 14, backgroundColor: tint(status === 'completed' ? GREEN : GOLD, 0.14) }} {...tid('jessi-call-status')}>
                      {['dialing', 'live', 'ending', 'building'].includes(status) || (called && !status) ? <ActivityIndicator size="small" color={GOLD} /> : <Ionicons name="checkmark-circle" size={18} color={GREEN} />}
                      <Text style={{ fontSize: 14, fontWeight: '700', color: L.text, flex: 1 }}>{STATUS_COPY[status] || 'Calling you now. Pick up!'}</Text>
                    </View>
                  )}
                  {!!error && <Text style={{ fontSize: 13, color: RED, textAlign: 'center' }} {...tid('jessi-call-error')}>{error}</Text>}
                  <PrimaryButton size="lg" full icon="call" label={inFlight && status !== 'failed' && status !== 'abandoned' ? 'Calling…' : called ? 'Call me again' : 'Call me now'} loading={busy}
                    disabled={inFlight && !['failed', 'abandoned'].includes(status)} onPress={call} testID="jessi-call-btn" style={{ marginTop: 6 }} />
                  <Text style={{ fontSize: 12, color: L.textSecondary, textAlign: 'center' }}>Not a good time? Text CALL to Jessi whenever you're free.</Text>
                </>
              )}
            </>
          ) : null}
        </View>
      </View>
    </SafeAreaView>
  );
}
