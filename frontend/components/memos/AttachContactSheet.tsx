import React, { useEffect, useState } from 'react';
import { View, Text, TextInput, TouchableOpacity, Modal, FlatList, ActivityIndicator, Platform } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api, { contactsAPI } from '../../services/api';
import { useContactSearch } from '../../hooks/useContactSearch';
import { GOLD, tid, errText } from '../inbox/ownership';

type Props = { visible: boolean; onClose: () => void; userId?: string; memo: any | null; colors: any; onAttached: (memoId: string, result: any) => void; showToast: (m: string, t?: any, d?: number) => void };

const nameOf = (c: any) => c?.name || [c?.first_name, c?.last_name].filter(Boolean).join(' ') || c?.phone || 'Contact';

// Pick who the memo was about, then attach it as a quick memo or as a full recorded conversation (summary + tasks).
export const AttachContactSheet = ({ visible, onClose, userId, memo, colors, onAttached, showToast }: Props) => {
  const [q, setQ] = useState('');
  const [contacts, setContacts] = useState<any[]>([]);
  const [picked, setPicked] = useState<any | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  useContactSearch(userId, q, setContacts, visible);
  useEffect(() => {
    if (!visible || !userId) return;
    setPicked(null); setQ('');
    contactsAPI.getAll(userId).then((d: any) => setContacts(Array.isArray(d) ? d : d?.contacts || [])).catch(() => {});
  }, [visible, userId]);

  const attach = async (asKind: 'memo' | 'conversation') => {
    if (!picked || !memo || !userId) return;
    setBusy(asKind);
    try {
      const r = await api.post(`/voice-memos/${userId}/${memo.id}/attach`, { contact_id: picked._id || picked.id, as_kind: asKind });
      onAttached(memo.id, r.data);
      onClose();
    } catch (e: any) { showToast(errText(e, 'Could not attach'), 'error', 3500); }
    finally { setBusy(null); }
  };

  const textColor = colors.text;
  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <View style={{ flex: 1, backgroundColor: '#00000088', justifyContent: 'flex-end' }}>
        <View style={{ backgroundColor: colors.bg, borderTopLeftRadius: 24, borderTopRightRadius: 24, padding: 18, paddingBottom: Platform.OS === 'ios' ? 34 : 18, maxHeight: '88%' }} {...tid('attach-sheet')}>
          <View style={{ flexDirection: 'row', alignItems: 'center', marginBottom: 10 }}>
            <Text style={{ flex: 1, fontSize: 17, fontWeight: '800', color: textColor }}>{picked ? `Attach to ${nameOf(picked)}` : 'Who was this about?'}</Text>
            <TouchableOpacity onPress={onClose} {...tid('attach-close')}><Ionicons name="close" size={24} color={textColor} /></TouchableOpacity>
          </View>
          {!picked ? (
            <>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: colors.card, borderRadius: 12, paddingHorizontal: 12, height: 46, borderWidth: 1, borderColor: colors.border }}>
                <Ionicons name="search" size={18} color={colors.textSecondary} />
                <TextInput value={q} onChangeText={setQ} placeholder="Search by name or number" placeholderTextColor={colors.textSecondary} autoFocus style={{ flex: 1, color: textColor, fontSize: 15 }} {...tid('attach-search')} />
              </View>
              <FlatList data={contacts.slice(0, 60)} keyExtractor={(c: any) => String(c._id || c.id)} style={{ marginTop: 8, maxHeight: 420 }} keyboardShouldPersistTaps="handled"
                ListEmptyComponent={<Text style={{ color: colors.textSecondary, padding: 14, textAlign: 'center' }}>{q.length >= 2 ? 'No one matches.' : 'Type a name to search your whole book.'}</Text>}
                renderItem={({ item }: any) => (
                  <TouchableOpacity onPress={() => setPicked(item)} style={{ flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: colors.border }} {...tid(`attach-contact-${item._id || item.id}`)}>
                    <View style={{ width: 38, height: 38, borderRadius: 19, backgroundColor: GOLD + '22', alignItems: 'center', justifyContent: 'center' }}><Text style={{ color: GOLD, fontWeight: '800' }}>{nameOf(item).charAt(0).toUpperCase()}</Text></View>
                    <View style={{ flex: 1 }}>
                      <Text style={{ fontSize: 15, fontWeight: '700', color: textColor }}>{nameOf(item)}</Text>
                      {item.phone ? <Text style={{ fontSize: 12, color: colors.textSecondary }}>{item.phone}</Text> : null}
                    </View>
                    <Ionicons name="chevron-forward" size={16} color={colors.textSecondary} />
                  </TouchableOpacity>
                )} />
              <TouchableOpacity onPress={() => { onClose(); require('expo-router').router.push('/contact/new'); }} style={{ flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 12 }} {...tid('attach-new-contact')}>
                <Ionicons name="person-add-outline" size={18} color={GOLD} />
                <Text style={{ color: GOLD, fontWeight: '700' }}>They are not in my contacts yet</Text>
              </TouchableOpacity>
            </>
          ) : (
            <View style={{ gap: 10 }}>
              <Text style={{ fontSize: 13, color: colors.textSecondary, lineHeight: 18 }}>How should Jessi file it on {nameOf(picked).split(' ')[0]}'s record?</Text>
              <TouchableOpacity onPress={() => attach('memo')} disabled={!!busy} style={{ flexDirection: 'row', alignItems: 'center', gap: 12, padding: 14, borderRadius: 16, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border }} {...tid('attach-as-memo')}>
                <View style={{ width: 40, height: 40, borderRadius: 20, backgroundColor: '#34C75922', alignItems: 'center', justifyContent: 'center' }}>{busy === 'memo' ? <ActivityIndicator color="#34C759" /> : <Ionicons name="mic" size={20} color="#34C759" />}</View>
                <View style={{ flex: 1 }}>
                  <Text style={{ fontSize: 15, fontWeight: '800', color: textColor }}>As a voice memo</Text>
                  <Text style={{ fontSize: 12.5, color: colors.textSecondary, lineHeight: 17, marginTop: 2 }}>A note about them. Transcript goes into their profile; Jessi picks up personal details.</Text>
                </View>
              </TouchableOpacity>
              <TouchableOpacity onPress={() => attach('conversation')} disabled={!!busy} style={{ flexDirection: 'row', alignItems: 'center', gap: 12, padding: 14, borderRadius: 16, backgroundColor: GOLD + '14', borderWidth: 1, borderColor: GOLD + '66' }} {...tid('attach-as-conversation')}>
                <View style={{ width: 40, height: 40, borderRadius: 20, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center' }}>{busy === 'conversation' ? <ActivityIndicator color="#111" /> : <Ionicons name="people" size={20} color="#111" />}</View>
                <View style={{ flex: 1 }}>
                  <Text style={{ fontSize: 15, fontWeight: '800', color: textColor }}>As a recorded conversation</Text>
                  <Text style={{ fontSize: 12.5, color: colors.textSecondary, lineHeight: 17, marginTop: 2 }}>A talk with them. Jessi writes a summary, turns every commitment into a task, and can cite it later.</Text>
                </View>
              </TouchableOpacity>
              <TouchableOpacity onPress={() => setPicked(null)} style={{ alignItems: 'center', padding: 8 }} {...tid('attach-back')}><Text style={{ color: colors.textSecondary, fontWeight: '700' }}>Pick someone else</Text></TouchableOpacity>
            </View>
          )}
        </View>
      </View>
    </Modal>
  );
};
