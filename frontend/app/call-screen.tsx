import React, { useState, useEffect, useRef } from 'react';
import {
  View, Text, TouchableOpacity, StyleSheet, Platform, Linking, ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useLocalSearchParams } from 'expo-router';
import api from '../services/api';
import { useAuthStore } from '../store/authStore';
import { useThemeStore } from '../store/themeStore';

export default function CallScreen() {
  const { colors } = useThemeStore();
  const st = getST(colors);
  const router = useRouter();
  const params = useLocalSearchParams();
  const { user } = useAuthStore();

  const contactId    = (params.contact_id   as string) || '';
  const contactName  = (params.contact_name as string) || 'Unknown';
  const contactPhone = (params.phone        as string) || '';

  const [callState, setCallState] = useState<'ready' | 'connecting' | 'ringing' | 'ended' | 'error'>('ready');
  const [callSid,   setCallSid]   = useState('');
  const [statusMsg, setStatusMsg] = useState('');
  const [seconds,   setSeconds]   = useState(0);
  const timerRef     = useRef<ReturnType<typeof setInterval> | null>(null);
  const startTimeRef = useRef<number>(0);

  // Start timer once ringing
  useEffect(() => {
    if (callState === 'ringing') {
      startTimeRef.current = Date.now();
      timerRef.current = setInterval(() => {
        setSeconds(Math.floor((Date.now() - startTimeRef.current) / 1000));
      }, 1000);
    }
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [callState]);

  const formatTime = (s: number) => {
    const m   = Math.floor(s / 60);
    const sec = s % 60;
    return `${m.toString().padStart(2, '0')}:${sec.toString().padStart(2, '0')}`;
  };

  const rep             = user as any;
  const repTwilioNumber = rep?.twilio_number || rep?.mvpline_number || '';

  const startCall = async () => {
    if (!user?._id) return;

    // No Twilio number assigned → fall back to native dialer
    if (!repTwilioNumber) {
      const phoneUrl = `tel:${contactPhone}`;
      if (Platform.OS === 'web') {
        (window as any).open(phoneUrl, '_self');
      } else {
        Linking.openURL(phoneUrl);
      }
      setCallState('ringing');
      startTimeRef.current = Date.now();
      setStatusMsg('Opening native dialer — caller ID will show your personal number');
      return;
    }

    setCallState('connecting');
    setStatusMsg('Initiating call...');
    try {
      const res = await api.post('/webhooks/twilio/call', {
        rep_user_id:    user._id,
        customer_phone: contactPhone,
        contact_id:     contactId,
      });
      setCallSid(res.data.call_sid || '');
      setCallState('ringing');
      setStatusMsg(res.data.message || 'Your phone is ringing — pick up to connect');
    } catch (e: any) {
      setCallState('error');
      const detail = e?.response?.data?.detail || 'Call failed. Check your phone number in Profile settings.';
      setStatusMsg(detail);
    }
  };

  const endCall = async () => {
    if (timerRef.current) clearInterval(timerRef.current);
    setCallState('ended');
    setStatusMsg('');
    if (callSid) {
      api.post('/webhooks/twilio/call-cancel', { call_sid: callSid }).catch(() => {});
    }
  };

  return (
    <SafeAreaView style={st.safe}>
      <View style={st.container}>

        {/* Top area — contact info + status */}
        <View style={st.topSection}>
          {callState === 'connecting' && (
            <View style={[st.statusPill, { backgroundColor: '#FF950020' }]}>
              <ActivityIndicator size="small" color="#FF9500" />
              <Text style={[st.statusText, { color: '#FF9500' }]}>Connecting...</Text>
            </View>
          )}
          {callState === 'ringing' && (
            <View style={st.statusPill}>
              <View style={st.liveDot} />
              <Text style={st.statusText}>
                {repTwilioNumber ? 'Your phone is ringing' : 'Native dialer opened'}
              </Text>
            </View>
          )}
          {callState === 'ended' && (
            <View style={[st.statusPill, { backgroundColor: '#34C75920' }]}>
              <Ionicons name="checkmark-circle" size={14} color="#34C759" />
              <Text style={[st.statusText, { color: '#34C759' }]}>Call Ended</Text>
            </View>
          )}
          {callState === 'error' && (
            <View style={[st.statusPill, { backgroundColor: '#FF3B3020' }]}>
              <Ionicons name="alert-circle" size={14} color="#FF3B30" />
              <Text style={[st.statusText, { color: '#FF3B30' }]}>Error</Text>
            </View>
          )}

          <View style={st.avatarCircle}>
            <Text style={st.avatarLetter}>{contactName.charAt(0).toUpperCase()}</Text>
          </View>
          <Text style={st.contactName}>{contactName}</Text>
          <Text style={st.contactPhone}>{contactPhone}</Text>

          {callState === 'ringing' && seconds > 0 && (
            <Text style={st.timer}>{formatTime(seconds)}</Text>
          )}

          {callState === 'ready' && (
            <>
              <Text style={st.readyHint}>
                {repTwilioNumber
                  ? `Caller ID: ${repTwilioNumber}`
                  : 'No Twilio number — will open native dialer'}
              </Text>
              <Text style={[st.readyHint, { fontSize: 12, marginTop: 4, color: '#555' }]}>
                {repTwilioNumber
                  ? `Your personal phone rings first, then connects to ${contactName}`
                  : 'Assign a dedicated number in Admin → Phone Numbers'}
              </Text>
            </>
          )}

          {!!statusMsg && (
            <Text style={[st.readyHint, { marginTop: 12, textAlign: 'center', paddingHorizontal: 20 }]}>
              {statusMsg}
            </Text>
          )}
        </View>

        {/* Bottom actions */}
        <View style={st.bottomSection}>
          {callState === 'ready' && (
            <>
              <TouchableOpacity style={st.callBtn} onPress={startCall} data-testid="start-call">
                <Ionicons name="call" size={32} color="#fff" />
              </TouchableOpacity>
              <Text style={st.callBtnLabel}>
                {repTwilioNumber ? 'Tap to call via Twilio' : 'Tap to open dialer'}
              </Text>
              <TouchableOpacity style={st.cancelBtn} onPress={() => router.back()} data-testid="cancel-call">
                <Text style={st.cancelBtnText}>Cancel</Text>
              </TouchableOpacity>
            </>
          )}

          {(callState === 'connecting' || callState === 'ringing') && (
            <>
              <TouchableOpacity style={st.endBtn} onPress={endCall} data-testid="end-call">
                <Ionicons name="call" size={32} color="#fff" style={{ transform: [{ rotate: '135deg' }] }} />
              </TouchableOpacity>
              <Text style={st.endLabel}>Tap to cancel</Text>
            </>
          )}

          {callState === 'ended' && (
            <>
              <View style={st.loggedCard}>
                <Ionicons name="checkmark-circle" size={28} color="#34C759" />
                <View style={st.loggedInfo}>
                  <Text style={st.loggedTitle}>Call completed</Text>
                  <Text style={st.loggedDetail}>
                    {seconds > 0 ? `Duration: ${formatTime(seconds)} — ` : ''}Called {contactName}
                  </Text>
                </View>
              </View>
              <TouchableOpacity style={st.doneBtn} onPress={() => router.back()} data-testid="call-done">
                <Text style={st.doneBtnText}>Back</Text>
              </TouchableOpacity>
            </>
          )}

          {callState === 'error' && (
            <>
              <TouchableOpacity style={st.callBtn} onPress={startCall} data-testid="retry-call">
                <Ionicons name="refresh" size={28} color="#fff" />
              </TouchableOpacity>
              <Text style={st.callBtnLabel}>Retry</Text>
              <TouchableOpacity style={st.cancelBtn} onPress={() => router.back()}>
                <Text style={st.cancelBtnText}>Cancel</Text>
              </TouchableOpacity>
            </>
          )}
        </View>

      </View>
    </SafeAreaView>
  );
}

const getST = (colors: any) => StyleSheet.create({
  safe:       { flex: 1, backgroundColor: colors.bg },
  container:  { flex: 1, justifyContent: 'space-between' },

  topSection:  { alignItems: 'center', paddingTop: 60, flex: 1, justifyContent: 'center' },
  statusPill:  { flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: '#FF3B3020', paddingHorizontal: 14, paddingVertical: 6, borderRadius: 20, marginBottom: 24 },
  liveDot:     { width: 8, height: 8, borderRadius: 4, backgroundColor: '#FF3B30' },
  statusText:  { fontSize: 15, fontWeight: '700', color: '#FF3B30' },
  avatarCircle:{ width: 96, height: 96, borderRadius: 48, backgroundColor: colors.card, alignItems: 'center', justifyContent: 'center', marginBottom: 16, borderWidth: 3, borderColor: colors.surface },
  avatarLetter:{ fontSize: 36, fontWeight: '800', color: '#C9A962' },
  contactName: { fontSize: 26, fontWeight: '800', color: colors.text, marginBottom: 4 },
  contactPhone:{ fontSize: 18, color: '#8E8E93', marginBottom: 16 },
  timer:       { fontSize: 48, fontWeight: '300', color: colors.text, letterSpacing: 2 },
  readyHint:   { fontSize: 14, color: '#8E8E93', marginTop: 4, textAlign: 'center' },

  bottomSection: { alignItems: 'center', paddingBottom: 50, paddingHorizontal: 20 },

  callBtn:      { width: 80, height: 80, borderRadius: 40, backgroundColor: '#34C759', alignItems: 'center', justifyContent: 'center', marginBottom: 10, shadowColor: '#34C759', shadowOffset: { width: 0, height: 0 }, shadowOpacity: 0.4, shadowRadius: 20 },
  callBtnLabel: { fontSize: 16, color: '#8E8E93', marginBottom: 16 },
  cancelBtn:    { paddingVertical: 10, paddingHorizontal: 30 },
  cancelBtnText:{ fontSize: 18, fontWeight: '600', color: '#FF3B30' },

  endBtn:   { width: 80, height: 80, borderRadius: 40, backgroundColor: '#FF3B30', alignItems: 'center', justifyContent: 'center', shadowColor: '#FF3B30', shadowOffset: { width: 0, height: 0 }, shadowOpacity: 0.4, shadowRadius: 20 },
  endLabel: { fontSize: 16, color: '#8E8E93', marginTop: 10 },

  loggedCard:  { flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: '#34C75910', borderRadius: 14, padding: 16, width: '100%' as any, marginBottom: 16, borderWidth: 1, borderColor: '#34C75930' },
  loggedInfo:  { flex: 1 },
  loggedTitle: { fontSize: 17, fontWeight: '700', color: '#34C759', marginBottom: 2 },
  loggedDetail:{ fontSize: 14, color: '#8E8E93' },
  doneBtn:     { backgroundColor: '#C9A962', paddingVertical: 16, paddingHorizontal: 40, borderRadius: 50, width: '100%' as any, alignItems: 'center' },
  doneBtnText: { fontSize: 18, fontWeight: '800', color: colors.text },
});
