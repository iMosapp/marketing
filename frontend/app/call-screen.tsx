import React, { useState, useEffect, useRef } from 'react';
import {
  View, Text, TouchableOpacity, StyleSheet, Platform, Linking, AppState,
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

  const contactId = params.contact_id as string || '';
  const contactName = params.contact_name as string || 'Unknown';
  const contactPhone = params.phone as string || '';

  const [callState, setCallState] = useState<'ready' | 'calling' | 'ended'>('ready');
  const [seconds, setSeconds] = useState(0);
  const [logging, setLogging] = useState(false);
  const timerRef = useRef<any>(null);
  const startTimeRef = useRef<number>(0);
  const appStateRef = useRef(AppState.currentState);

  // Track when user leaves/returns to app (native dialer)
  useEffect(() => {
    const sub = AppState.addEventListener('change', (nextState) => {
      if (
        appStateRef.current.match(/inactive|background/) &&
        nextState === 'active' &&
        callState === 'calling'
      ) {
        // User came back from native dialer  - call likely ended or ongoing
        // Don't auto-end, let them tap "End Call"
      }
      appStateRef.current = nextState;
    });
    return () => sub.remove();
  }, [callState]);

  // Timer
  useEffect(() => {
    if (callState === 'calling') {
      timerRef.current = setInterval(() => {
        setSeconds(Math.floor((Date.now() - startTimeRef.current) / 1000));
      }, 1000);
    }
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [callState]);

  const formatTime = (s: number) => {
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return `${m.toString().padStart(2, '0')}:${sec.toString().padStart(2, '0')}`;
  };

  const startCall = () => {
    setCallState('calling');
    startTimeRef.current = Date.now();

    // Open native dialer
    const phoneUrl = `tel:${contactPhone}`;
    if (Platform.OS === 'web') {
      window.open(phoneUrl, '_self');
    } else {
      Linking.openURL(phoneUrl);
    }
  };

  const endCall = async () => {
    if (timerRef.current) clearInterval(timerRef.current);
    setCallState('ended');

    // Log the call
    setLogging(true);
    try {
      const user = useAuthStore.getState().user;
      if (user?._id && contactId) {
        await api.post(`/calls/${user._id}`, {
          contact_id: contactId,
          type: 'outbound',
          duration: seconds,
        });

        // Also log as a contact event for the activity feed
        try {
          await api.post(`/contacts/${user._id}/${contactId}/events`, {
            event_type: 'call_outbound',
            icon: 'call',
            color: '#34C759',
            title: 'Outbound Call',
            description: `Called ${contactName} — ${formatTime(seconds)}`,
            category: 'call',
          });
        } catch (e) {
          console.error('Failed to log call event:', e);
        }
      }
    } catch (e) {
      console.error('Error logging call:', e);
    } finally {
      setLogging(false);
    }
  };

  const goBack = () => {
    router.back();
  };

  return (
    <SafeAreaView style={st.safe}>
      <View style={st.container}>
        {/* Top area */}
        <View style={st.topSection}>
          {callState === 'calling' && (
            <View style={st.statusPill}>
              <View style={st.liveDot} />
              <Text style={st.statusText}>In Progress</Text>
            </View>
          )}
          {callState === 'ended' && (
            <View style={[st.statusPill, { backgroundColor: '#34C75920' }]}>
              <Ionicons name="checkmark-circle" size={14} color="#34C759" />
              <Text style={[st.statusText, { color: '#34C759' }]}>Call Logged</Text>
            </View>
          )}

          <View style={st.avatarCircle}>
            <Text style={st.avatarLetter}>{contactName.charAt(0).toUpperCase()}</Text>
          </View>
          <Text style={st.contactName}>{contactName}</Text>
          <Text style={st.contactPhone}>{contactPhone}</Text>

          {/* Timer */}
          {callState !== 'ready' && (
            <Text style={st.timer}>{formatTime(seconds)}</Text>
          )}
          {callState === 'ready' && (
            <Text style={st.readyHint}>Call will be logged to the activity feed</Text>
          )}
        </View>

        {/* Bottom actions */}
        <View style={st.bottomSection}>
          {callState === 'ready' && (
            <>
              <TouchableOpacity style={st.callBtn} onPress={startCall} data-testid="start-call">
                <Ionicons name="call" size={32} color={colors.text} />
              </TouchableOpacity>
              <Text style={st.callBtnLabel}>Tap to call</Text>
              <TouchableOpacity style={st.cancelBtn} onPress={goBack} data-testid="cancel-call">
                <Text style={st.cancelBtnText}>Cancel</Text>
              </TouchableOpacity>
            </>
          )}

          {callState === 'calling' && (
            <>
              <TouchableOpacity style={st.endBtn} onPress={endCall} data-testid="end-call">
                <Ionicons name="call" size={32} color={colors.text} style={{ transform: [{ rotate: '135deg' }] }} />
              </TouchableOpacity>
              <Text style={st.endLabel}>End Call & Log</Text>
            </>
          )}

          {callState === 'ended' && (
            <>
              <View style={st.loggedCard}>
                <Ionicons name="checkmark-circle" size={28} color="#34C759" />
                <View style={st.loggedInfo}>
                  <Text style={st.loggedTitle}>Call logged successfully</Text>
                  <Text style={st.loggedDetail}>Duration: {formatTime(seconds)}  - Outbound call to {contactName}</Text>
                </View>
              </View>
              <TouchableOpacity style={st.doneBtn} onPress={goBack} data-testid="call-done">
                <Text style={st.doneBtnText}>Back to Contact</Text>
              </TouchableOpacity>
            </>
          )}
        </View>
      </View>
    </SafeAreaView>
  );
}

const getST = (colors: any) => StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  container: { flex: 1, justifyContent: 'space-between' },

  topSection: { alignItems: 'center', paddingTop: 60, flex: 1, justifyContent: 'center' },
  statusPill: { flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: '#FF3B3020', paddingHorizontal: 14, paddingVertical: 6, borderRadius: 20, marginBottom: 24 },
  liveDot: { width: 8, height: 8, borderRadius: 4, backgroundColor: '#FF3B30' },
  statusText: { fontSize: 15, fontWeight: '700', color: '#FF3B30' },
  avatarCircle: { width: 96, height: 96, borderRadius: 48, backgroundColor: colors.card, alignItems: 'center', justifyContent: 'center', marginBottom: 16, borderWidth: 3, borderColor: colors.surface },
  avatarLetter: { fontSize: 36, fontWeight: '800', color: '#C9A962' },
  contactName: { fontSize: 26, fontWeight: '800', color: colors.text, marginBottom: 4 },
  contactPhone: { fontSize: 18, color: '#8E8E93', marginBottom: 16 },
  timer: { fontSize: 48, fontWeight: '300', color: colors.text, fontVariant: ['tabular-nums'], letterSpacing: 2 },
  readyHint: { fontSize: 16, color: '#555', marginTop: 8 },

  bottomSection: { alignItems: 'center', paddingBottom: 50, paddingHorizontal: 20 },

  // Ready state
  callBtn: { width: 80, height: 80, borderRadius: 40, backgroundColor: '#34C759', alignItems: 'center', justifyContent: 'center', marginBottom: 10, shadowColor: '#34C759', shadowOffset: { width: 0, height: 0 }, shadowOpacity: 0.4, shadowRadius: 20 },
  callBtnLabel: { fontSize: 16, color: '#8E8E93', marginBottom: 16 },
  cancelBtn: { paddingVertical: 10, paddingHorizontal: 30 },
  cancelBtnText: { fontSize: 18, fontWeight: '600', color: '#FF3B30' },

  // Calling state
  endBtn: { width: 80, height: 80, borderRadius: 40, backgroundColor: '#FF3B30', alignItems: 'center', justifyContent: 'center', shadowColor: '#FF3B30', shadowOffset: { width: 0, height: 0 }, shadowOpacity: 0.4, shadowRadius: 20 },
  endLabel: { fontSize: 16, color: '#8E8E93', marginTop: 10 },

  // Ended state
  loggedCard: { flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: '#34C75910', borderRadius: 14, padding: 16, width: '100%' as any, marginBottom: 16, borderWidth: 1, borderColor: '#34C75930' },
  loggedInfo: { flex: 1 },
  loggedTitle: { fontSize: 17, fontWeight: '700', color: '#34C759', marginBottom: 2 },
  loggedDetail: { fontSize: 14, color: '#8E8E93' },
  doneBtn: { backgroundColor: '#C9A962', paddingVertical: 16, paddingHorizontal: 40, borderRadius: 50, width: '100%' as any, alignItems: 'center' },
  doneBtnText: { fontSize: 18, fontWeight: '800', color: colors.text },
});
