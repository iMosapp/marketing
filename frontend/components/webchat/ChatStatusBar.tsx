import React, { useState } from 'react';
import { View, Text, TouchableOpacity, TextInput, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { GOLD, tid } from '../inbox/ownership';
import { inputStyle } from '../inbox/InboxEditorParts';

type Props = { chat: any; meId: string; colors: any; busy: string; onJoin: () => void; onLeave: () => void; onEnd: () => void; onSaveLead: (name: string, phone: string) => Promise<void> };

const Btn = ({ label, onPress, colors, testId, gold, busy }: { label: string; onPress: () => void; colors: any; testId: string; gold?: boolean; busy?: boolean }) => (
  <TouchableOpacity onPress={onPress} disabled={busy} style={{ height: 34, paddingHorizontal: 14, borderRadius: 17, backgroundColor: gold ? GOLD : colors.surface, borderWidth: gold ? 0 : 1, borderColor: colors.border, justifyContent: 'center', opacity: busy ? 0.6 : 1 }} {...tid(testId)}>
    {busy ? <ActivityIndicator size="small" color={gold ? '#111' : colors.text} /> : <Text style={{ fontSize: 13, fontWeight: '800', color: gold ? '#111' : colors.text }}>{label}</Text>}
  </TouchableOpacity>
);

// Who has the chat (Jessi / you / another rep / ended) + the one action that makes sense right now.
export const ChatStatusBar = ({ chat, meId, colors, busy, onJoin, onLeave, onEnd, onSaveLead }: Props) => {
  const router = useRouter();
  const [leadOpen, setLeadOpen] = useState(false);
  const [name, setName] = useState(chat.name || '');
  const [phone, setPhone] = useState(chat.phone || '');
  const mine = chat.mode === 'human' && String(chat.rep_user_id) === String(meId);
  const closed = chat.status === 'closed';
  const line = closed ? 'Chat ended' : chat.mode === 'human' ? (mine ? "You're chatting with the visitor" : `${chat.agent || 'A teammate'} is chatting`) : 'Jessi is answering';
  const dot = closed ? colors.textSecondary : chat.mode === 'human' ? GOLD : '#34C759';
  return (
    <View style={{ paddingHorizontal: 14, paddingVertical: 10, gap: 10, borderBottomWidth: 1, borderBottomColor: colors.border, backgroundColor: colors.card }} {...tid('webchat-status')}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
        <View style={{ width: 8, height: 8, borderRadius: 4, backgroundColor: dot }} />
        <Text style={{ flex: 1, fontSize: 13, fontWeight: '700', color: colors.text }} {...tid('webchat-status-line')}>{line}</Text>
        {!closed && chat.mode !== 'human' ? <Btn label="Jump in" onPress={onJoin} colors={colors} testId="webchat-join" gold busy={busy === 'join'} /> : null}
        {!closed && chat.mode === 'human' && !mine ? <Btn label="Take over" onPress={onJoin} colors={colors} testId="webchat-join" gold busy={busy === 'join'} /> : null}
        {!closed && mine ? <Btn label="Hand back to Jessi" onPress={onLeave} colors={colors} testId="webchat-leave" busy={busy === 'leave'} /> : null}
        {!closed ? <TouchableOpacity onPress={onEnd} hitSlop={8} {...tid('webchat-end')}><Ionicons name="close-circle-outline" size={24} color={colors.textSecondary} /></TouchableOpacity> : null}
      </View>
      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>
        {chat.booking ? <Text style={{ fontSize: 12, fontWeight: '700', color: '#34C759' }} {...tid('webchat-booking')}>✓ {chat.booking.kind} · {chat.booking.when}{chat.booking.vehicle ? ` · ${chat.booking.vehicle}` : ''}</Text> : null}
        {chat.phone ? <Text style={{ fontSize: 12, color: colors.textSecondary }} {...tid('webchat-phone')}>{chat.phone}</Text> : null}
        {chat.contact_id ? <TouchableOpacity onPress={() => router.push(`/contact/${chat.contact_id}` as any)} {...tid('webchat-open-contact')}><Text style={{ fontSize: 12, fontWeight: '700', color: GOLD }}>Open contact</Text></TouchableOpacity> : null}
        {chat.conversation_id ? <TouchableOpacity onPress={() => router.push(`/thread/${chat.conversation_id}` as any)} {...tid('webchat-open-thread')}><Text style={{ fontSize: 12, fontWeight: '700', color: GOLD }}>Text thread</Text></TouchableOpacity> : null}
        {!chat.contact_id && !closed ? <TouchableOpacity onPress={() => setLeadOpen(v => !v)} {...tid('webchat-save-lead-toggle')}><Text style={{ fontSize: 12, fontWeight: '700', color: GOLD }}>{leadOpen ? 'Cancel' : 'Save as lead'}</Text></TouchableOpacity> : null}
      </View>
      {leadOpen ? (
        <View style={{ gap: 8 }} {...tid('webchat-save-lead-form')}>
          <TextInput value={name} onChangeText={setName} placeholder="Name" placeholderTextColor={colors.textSecondary} style={inputStyle(colors)} {...tid('webchat-lead-name')} />
          <View style={{ flexDirection: 'row', gap: 8 }}>
            <TextInput value={phone} onChangeText={setPhone} placeholder="Mobile number" placeholderTextColor={colors.textSecondary} keyboardType="phone-pad" style={[inputStyle(colors), { flex: 1 }]} {...tid('webchat-lead-phone')} />
            <Btn label="Save" onPress={async () => { await onSaveLead(name, phone); setLeadOpen(false); }} colors={colors} testId="webchat-lead-save" gold busy={busy === 'lead'} />
          </View>
          <Text style={{ fontSize: 11, color: colors.textSecondary }}>Creates the contact and Inbox thread. No text goes out, you are already talking to them.</Text>
        </View>
      ) : null}
    </View>
  );
};
