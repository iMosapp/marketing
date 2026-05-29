import React, { useState } from 'react';
import {
  View, Text, TouchableOpacity, StyleSheet, Platform, Linking,
  ActivityIndicator, TextInput, Modal,
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
  const { user } = useAuthStore();

  const contactId    = (useLocalSearchParams().contact_id    as string) || '';
  const contactName  = (useLocalSearchParams().contact_name  as string) || 'Unknown';
  const contactPhone = (useLocalSearchParams().phone         as string) || '';
  const conversationId = (useLocalSearchParams().conversation_id as string) || '';

  const rep             = user as any;
  const repTwilioNumber = rep?.twilio_number || rep?.mvpline_number || '';
  const hasTwilio       = !!repTwilioNumber;

  // ── Twilio Click-to-Call state ──────────────────────────────────────────────
  const [callState,  setCallState]  = useState<'idle' | 'placing' | 'ringing' | 'done' | 'error'>('idle');
  const [callSid,    setCallSid]    = useState('');
  const [statusMsg,  setStatusMsg]  = useState('');

  // ── Native call log dialog state ────────────────────────────────────────────
  const [showLogModal, setShowLogModal] = useState(false);
  const [callNotes,    setCallNotes]    = useState('');
  const [callMins,     setCallMins]     = useState('');
  const [logging,      setLogging]      = useState(false);

  // ── Twilio Click-to-Call flow ───────────────────────────────────────────────
  const placeTwilioCall = async () => {
    if (!user?._id) return;
    setCallState('placing');
    setStatusMsg('');
    try {
      const res = await api.post('/webhooks/twilio/call', {
        rep_user_id:     user._id,
        customer_phone:  contactPhone,
        contact_id:      contactId,
        conversation_id: conversationId,  // links call to inbox thread
      });
      setCallSid(res.data.call_sid || '');
      setCallState('ringing');
      setStatusMsg(res.data.message || 'Your phone will ring shortly');
    } catch (e: any) {
      setCallState('error');
      setStatusMsg(e?.response?.data?.detail || 'Call failed — check your phone number in Profile settings.');
    }
  };

  const cancelTwilioCall = async () => {
    if (callSid) {
      api.post('/webhooks/twilio/call-cancel', { call_sid: callSid }).catch(() => {});
    }
    router.back();
  };

  // ── Native dialer + log flow ────────────────────────────────────────────────
  const openNativeDialer = () => {
    const url = `tel:${contactPhone}`;
    Platform.OS === 'web' ? (window as any).open(url, '_self') : Linking.openURL(url);
    // Show log dialog after opening dialer
    setTimeout(() => setShowLogModal(true), 1500);
  };

  const saveNativeCallLog = async () => {
    if (!user?._id) return;
    setLogging(true);
    try {
      const durationSecs = Math.round((parseFloat(callMins) || 0) * 60);
      await api.post(`/calls/${user._id}`, {
        contact_id: contactId,
        type:       'outbound',
        duration:   durationSecs,
        notes:      callNotes,
      });
      if (contactId) {
        await api.post(`/contacts/${user._id}/${contactId}/events`, {
          event_type:  'call_outbound',
          icon:        'call',
          color:       '#34C759',
          title:       'Outbound Call',
          description: `Called ${contactName}${durationSecs > 0 ? ` — ${callMins}min` : ''}${callNotes ? `\n${callNotes}` : ''}`,
          category:    'call',
        }).catch(() => {});
      }
      setShowLogModal(false);
      router.back();
    } catch (e) {
      console.error('Failed to log call:', e);
    } finally {
      setLogging(false);
    }
  };

  const initials = contactName.charAt(0).toUpperCase();

  // ─────────────────────────────────────────────────────────────────────────────
  return (
    <SafeAreaView style={st.safe}>
      <View style={st.container}>

        {/* Contact info */}
        <View style={st.top}>
          <View style={st.avatar}><Text style={st.initials}>{initials}</Text></View>
          <Text style={st.name}>{contactName}</Text>
          <Text style={st.phone}>{contactPhone}</Text>

          {hasTwilio && (
            <View style={st.callerIdPill}>
              <Ionicons name="checkmark-circle" size={13} color="#34C759" />
              <Text style={st.callerIdText}>Caller ID: {repTwilioNumber}</Text>
            </View>
          )}
        </View>

        {/* ── Twilio flow ────────────────────────────────────────────── */}
        {hasTwilio && (
          <View style={st.bottom}>
            {callState === 'idle' && (
              <>
                <TouchableOpacity style={st.callBtn} onPress={placeTwilioCall} data-testid="place-call-btn">
                  <Ionicons name="call" size={32} color="#fff" />
                </TouchableOpacity>
                <Text style={st.hint}>Tap to call via your business number</Text>
                <Text style={st.subhint}>Your personal phone rings first, then connects to {contactName}</Text>
                <TouchableOpacity onPress={() => router.back()} style={{ marginTop: 16 }}>
                  <Text style={st.cancel}>Cancel</Text>
                </TouchableOpacity>
              </>
            )}

            {callState === 'placing' && (
              <>
                <ActivityIndicator size="large" color={colors.accent} />
                <Text style={[st.hint, { marginTop: 16 }]}>Placing call...</Text>
              </>
            )}

            {callState === 'ringing' && (
              <>
                <View style={st.ringingRing}>
                  <Ionicons name="call" size={36} color="#34C759" />
                </View>
                <Text style={[st.hint, { color: '#34C759' }]}>Your phone is ringing</Text>
                <Text style={st.subhint}>{statusMsg}</Text>
                <Text style={st.subhint}>The call is handled on your personal device — hang up normally when done.</Text>
                <TouchableOpacity style={[st.callBtn, { backgroundColor: '#FF3B30', marginTop: 28 }]} onPress={cancelTwilioCall} data-testid="cancel-call-btn">
                  <Ionicons name="call" size={28} color="#fff" style={{ transform: [{ rotate: '135deg' }] }} />
                </TouchableOpacity>
                <Text style={st.cancel}>Cancel Call</Text>
              </>
            )}

            {callState === 'error' && (
              <>
                <Ionicons name="alert-circle" size={48} color="#FF3B30" />
                <Text style={[st.hint, { color: '#FF3B30', marginTop: 12 }]}>Call failed</Text>
                <Text style={st.subhint}>{statusMsg}</Text>
                <TouchableOpacity style={st.callBtn} onPress={placeTwilioCall} data-testid="retry-btn">
                  <Ionicons name="refresh" size={28} color="#fff" />
                </TouchableOpacity>
                <Text style={st.hint}>Retry</Text>
                <TouchableOpacity onPress={() => router.back()} style={{ marginTop: 12 }}>
                  <Text style={st.cancel}>Cancel</Text>
                </TouchableOpacity>
              </>
            )}
          </View>
        )}

        {/* ── No Twilio number — native dialer + log ────────────────── */}
        {!hasTwilio && (
          <View style={st.bottom}>
            <View style={[st.infoBanner, { borderColor: '#FF950040', backgroundColor: '#FF950010' }]}>
              <Ionicons name="information-circle-outline" size={16} color="#FF9500" />
              <Text style={{ fontSize: 13, color: '#FF9500', flex: 1 }}>
                No dedicated Twilio number — opens your phone's native dialer. Caller ID will show your personal number.
              </Text>
            </View>
            <TouchableOpacity style={st.callBtn} onPress={openNativeDialer} data-testid="native-dial-btn">
              <Ionicons name="call" size={32} color="#fff" />
            </TouchableOpacity>
            <Text style={st.hint}>Open native dialer</Text>
            <TouchableOpacity onPress={() => router.back()} style={{ marginTop: 16 }}>
              <Text style={st.cancel}>Cancel</Text>
            </TouchableOpacity>
          </View>
        )}
      </View>

      {/* ── Native call log modal ───────────────────────────────────── */}
      <Modal visible={showLogModal} animationType="slide" presentationStyle="pageSheet">
        <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }}>
          <View style={st.modalHeader}>
            <TouchableOpacity onPress={() => { setShowLogModal(false); router.back(); }}>
              <Text style={{ color: colors.textSecondary, fontSize: 16 }}>Skip</Text>
            </TouchableOpacity>
            <Text style={{ color: colors.text, fontSize: 17, fontWeight: '700' }}>Log Call</Text>
            <TouchableOpacity onPress={saveNativeCallLog} disabled={logging}>
              {logging ? <ActivityIndicator size="small" color={colors.accent} /> : <Text style={{ color: colors.accent, fontSize: 16, fontWeight: '700' }}>Save</Text>}
            </TouchableOpacity>
          </View>

          <View style={{ padding: 24 }}>
            <Text style={{ color: colors.text, fontSize: 22, fontWeight: '800', marginBottom: 4 }}>{contactName}</Text>
            <Text style={{ color: colors.textSecondary, marginBottom: 28 }}>{contactPhone}</Text>

            <Text style={{ color: colors.textSecondary, fontSize: 12, fontWeight: '700', marginBottom: 8, textTransform: 'uppercase' }}>Duration (minutes)</Text>
            <TextInput
              style={[st.logInput, { color: colors.text, backgroundColor: colors.card, borderColor: colors.border }]}
              value={callMins}
              onChangeText={setCallMins}
              placeholder="e.g. 3.5"
              placeholderTextColor={colors.textSecondary}
              keyboardType="decimal-pad"
            />

            <Text style={{ color: colors.textSecondary, fontSize: 12, fontWeight: '700', marginBottom: 8, marginTop: 20, textTransform: 'uppercase' }}>Notes (optional)</Text>
            <TextInput
              style={[st.logInput, { color: colors.text, backgroundColor: colors.card, borderColor: colors.border, height: 100, textAlignVertical: 'top' }]}
              value={callNotes}
              onChangeText={setCallNotes}
              placeholder="What was discussed..."
              placeholderTextColor={colors.textSecondary}
              multiline
            />
          </View>
        </SafeAreaView>
      </Modal>
    </SafeAreaView>
  );
}

const getST = (colors: any) => StyleSheet.create({
  safe:       { flex: 1, backgroundColor: colors.bg },
  container:  { flex: 1 },
  top:        { flex: 1, alignItems: 'center', justifyContent: 'center', paddingTop: 40 },
  avatar:     { width: 96, height: 96, borderRadius: 48, backgroundColor: colors.card, alignItems: 'center', justifyContent: 'center', marginBottom: 16, borderWidth: 3, borderColor: colors.surface },
  initials:   { fontSize: 36, fontWeight: '800', color: '#C9A962' },
  name:       { fontSize: 26, fontWeight: '800', color: colors.text, marginBottom: 4 },
  phone:      { fontSize: 17, color: '#8E8E93', marginBottom: 12 },
  callerIdPill: { flexDirection: 'row', alignItems: 'center', gap: 5, backgroundColor: '#34C75910', borderRadius: 20, paddingHorizontal: 12, paddingVertical: 5 },
  callerIdText: { fontSize: 13, color: '#34C759', fontWeight: '600' },
  bottom:     { alignItems: 'center', paddingBottom: 60, paddingHorizontal: 24 },
  callBtn:    { width: 76, height: 76, borderRadius: 38, backgroundColor: '#34C759', alignItems: 'center', justifyContent: 'center', marginBottom: 12, shadowColor: '#34C759', shadowOffset: { width: 0, height: 0 }, shadowOpacity: 0.4, shadowRadius: 16 },
  hint:       { fontSize: 16, color: colors.text, fontWeight: '600', marginBottom: 6, textAlign: 'center' },
  subhint:    { fontSize: 13, color: colors.textSecondary, textAlign: 'center', marginBottom: 6, paddingHorizontal: 16 },
  cancel:     { fontSize: 16, color: '#FF3B30', fontWeight: '600' },
  ringingRing:{ width: 100, height: 100, borderRadius: 50, borderWidth: 3, borderColor: '#34C759', alignItems: 'center', justifyContent: 'center', marginBottom: 20 },
  infoBanner: { flexDirection: 'row', gap: 8, borderRadius: 12, padding: 12, marginBottom: 24, borderWidth: 1, alignItems: 'flex-start', width: '100%' as any },
  modalHeader:{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 20, paddingVertical: 16, borderBottomWidth: 1, borderBottomColor: colors.border },
  logInput:   { borderRadius: 12, borderWidth: 1, padding: 14, fontSize: 16, marginBottom: 4 },
});
