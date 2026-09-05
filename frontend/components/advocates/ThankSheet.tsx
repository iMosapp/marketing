import React, { useEffect, useState } from 'react';
import { View, Text, Modal, Pressable, TouchableOpacity, TextInput, ActivityIndicator, Platform, Linking, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';

const BLUE = '#0A84FF';
const GREEN = '#34C759';
type Mode = 'text' | 'card';

type Props = {
  visible: boolean;
  userId: string;
  advocate: { contact_id: string; name: string; first_name?: string; phone?: string } | null;
  colors: any;
  onClose: () => void;
  onSent: (contactId: string, result: any) => void;
};

const openNativeSms = (phone: string, body: string) => {
  const digits = phone.replace(/[^\d+]/g, '');
  const sep = Platform.OS === 'ios' ? '&' : '?';
  Linking.openURL(`sms:${digits}${sep}body=${encodeURIComponent(body)}`).catch(() => { /* noop */ });
};

export const ThankSheet = ({ visible, userId, advocate, colors, onClose, onSent }: Props) => {
  const [mode, setMode] = useState<Mode>('text');
  const [drafts, setDrafts] = useState<{ text: string; card: string } | null>(null);
  const [message, setMessage] = useState('');
  const [viaTwilio, setViaTwilio] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!visible || !advocate) return;
    setMode('text'); setDrafts(null); setMessage(''); setError('');
    api.get(`/relationship-health/${userId}/advocates/${advocate.contact_id}/thank`)
      .then(r => { setDrafts({ text: r.data.text, card: r.data.card }); setMessage(r.data.text); setViaTwilio(!!r.data.via_twilio); })
      .catch(() => setError('Could not load a draft. You can still write your own.'));
  }, [visible, advocate?.contact_id, userId]);

  const pick = (m: Mode) => { setMode(m); if (drafts) setMessage(drafts[m]); };

  const send = async () => {
    if (!advocate || sending) return;
    setSending(true); setError('');
    try {
      const r = await api.post(`/relationship-health/${userId}/advocates/${advocate.contact_id}/thank`, { mode, message: message.trim() });
      if (r.data.via === 'native' && r.data.phone) openNativeSms(r.data.phone, r.data.body);
      onSent(advocate.contact_id, r.data);
      onClose();
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Could not send. Try again.');
    } finally { setSending(false); }
  };

  if (!advocate) return null;
  const first = advocate.first_name || advocate.name.split(' ')[0];
  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <Pressable style={st.backdrop} onPress={onClose} testID="thank-sheet-backdrop" />
      <View style={[st.sheet, { backgroundColor: colors.card }]} testID="thank-sheet">
        <View style={st.handle} />
        <Text style={[st.title, { color: colors.text }]}>Thank {first}</Text>
        <Text style={{ fontSize: 13, color: colors.textSecondary, marginTop: 2 }}>
          {viaTwilio ? 'Sends from your business number and lands on their timeline.' : 'Opens your Messages app with the text ready to go.'}
        </Text>

        <View style={[st.seg, { backgroundColor: colors.bg }]}>
          {([['text', 'chatbubble', 'Thank-you text'], ['card', 'heart', 'Thank-you card']] as const).map(([m, icon, label]) => {
            const on = mode === m;
            return (
              <TouchableOpacity key={m} onPress={() => pick(m)} style={[st.segBtn, on && { backgroundColor: m === 'card' ? GREEN : BLUE }]} testID={`thank-mode-${m}`}>
                <Ionicons name={icon as any} size={15} color={on ? '#fff' : colors.textSecondary} />
                <Text style={{ fontSize: 13, fontWeight: '700', color: on ? '#fff' : colors.textSecondary }}>{label}</Text>
              </TouchableOpacity>
            );
          })}
        </View>
        {mode === 'card' ? (
          <Text style={{ fontSize: 12, color: colors.textTertiary || colors.textSecondary, marginTop: 8 }} testID="thank-card-note">
            A thank-you card with your photo and name is built for {first} and linked at the end of the text.
          </Text>
        ) : null}

        {drafts || error ? (
          <TextInput
            value={message} onChangeText={setMessage} multiline
            style={[st.input, { color: colors.text, backgroundColor: colors.bg, borderColor: colors.border }]}
            placeholder={`Write something for ${first}`} placeholderTextColor={colors.textTertiary}
            testID="thank-message-input"
          />
        ) : (
          <View style={{ height: 120, alignItems: 'center', justifyContent: 'center' }}><ActivityIndicator color={BLUE} /></View>
        )}
        {error ? <Text style={{ fontSize: 12, color: '#FF453A', marginTop: 6 }} testID="thank-error">{error}</Text> : null}

        <TouchableOpacity
          onPress={send} disabled={sending || !message.trim()}
          style={[st.send, { backgroundColor: mode === 'card' ? GREEN : BLUE, opacity: sending || !message.trim() ? 0.6 : 1 }]}
          testID="thank-send"
        >
          {sending ? <ActivityIndicator color="#fff" /> : (
            <>
              <Ionicons name="paper-plane" size={16} color="#fff" />
              <Text style={{ color: '#fff', fontWeight: '800', fontSize: 15 }}>{mode === 'card' ? 'Send card' : 'Send text'}</Text>
            </>
          )}
        </TouchableOpacity>
      </View>
    </Modal>
  );
};

const st = StyleSheet.create({
  backdrop: { flex: 1, backgroundColor: 'rgba(0,0,0,0.55)' },
  sheet: { borderTopLeftRadius: 24, borderTopRightRadius: 24, padding: 20, paddingBottom: 34 },
  handle: { alignSelf: 'center', width: 40, height: 4, borderRadius: 2, backgroundColor: 'rgba(255,255,255,0.18)', marginBottom: 14 },
  title: { fontSize: 20, fontWeight: '800' },
  seg: { flexDirection: 'row', borderRadius: 12, padding: 4, marginTop: 14, gap: 4 },
  segBtn: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingVertical: 10, borderRadius: 9 },
  input: { minHeight: 120, borderRadius: 12, borderWidth: 1, padding: 12, fontSize: 15, lineHeight: 21, marginTop: 12, textAlignVertical: 'top' },
  send: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, borderRadius: 14, paddingVertical: 14, marginTop: 14 },
});
