import React, { useEffect, useState } from 'react';
import { View, Text, TextInput, TouchableOpacity, Modal, FlatList, Platform } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { router } from 'expo-router';
import api, { contactsAPI } from '../../services/api';
import { useContactSearch } from '../../hooks/useContactSearch';
import { GOLD, tid, errText } from '../inbox/ownership';
import { MemoKindPicker, MemoKind } from './MemoKindPicker';
import { newContactFromMemoHref } from './memoLinks';

type Props = { visible: boolean; onClose: () => void; userId?: string; memo: any | null; colors: any; onAttached: (memoId: string, result: any) => void; showToast: (m: string, t?: any, d?: number) => void; preset?: any | null };

const nameOf = (c: any) => c?.name || [c?.first_name, c?.last_name].filter(Boolean).join(' ') || c?.phone || 'Contact';

// Pick who the memo was about (Jessi's guesses first), then attach it as a quick memo or as a full recorded conversation (summary + tasks).
export const AttachContactSheet = ({ visible, onClose, userId, memo, colors, onAttached, showToast, preset }: Props) => {
  const [q, setQ] = useState('');
  const [contacts, setContacts] = useState<any[]>([]);
  const [picked, setPicked] = useState<any | null>(null);
  const [busy, setBusy] = useState<MemoKind | null>(null);
  useContactSearch(userId, q, setContacts, visible);
  useEffect(() => {
    if (!visible || !userId) return;
    setPicked(preset ? { _id: preset.contact_id, name: preset.name, phone: preset.phone } : null); setQ('');
    contactsAPI.getAll(userId).then((d: any) => setContacts(Array.isArray(d) ? d : d?.contacts || [])).catch(() => {});
  }, [visible, userId, preset]);

  const goCreate = (person: any | null) => { if (!memo) return; onClose(); router.push(newContactFromMemoHref(memo.id, person) as any); };
  const attach = async (asKind: MemoKind) => {
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
              {memo?.suggested_contacts?.length ? (
                <View style={{ marginBottom: 10, gap: 6 }} {...tid('attach-suggestions')}>
                  <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.6 }}>JESSI'S GUESS</Text>
                  {memo.suggested_contacts.map((s: any) => (
                    <TouchableOpacity key={s.contact_id} onPress={() => setPicked({ _id: s.contact_id, name: s.name, phone: s.phone })} style={{ flexDirection: 'row', alignItems: 'center', gap: 12, padding: 10, borderRadius: 14, backgroundColor: GOLD + '14', borderWidth: 1, borderColor: GOLD + '66' }} {...tid(`attach-suggest-${s.contact_id}`)}>
                      <View style={{ width: 38, height: 38, borderRadius: 19, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center' }}><Ionicons name="sparkles" size={18} color="#111" /></View>
                      <View style={{ flex: 1 }}>
                        <Text style={{ fontSize: 15, fontWeight: '800', color: textColor }}>{s.name}{s.company ? <Text style={{ fontWeight: '500', color: colors.textSecondary }}> · {s.company}</Text> : null}</Text>
                        <Text style={{ fontSize: 12, color: colors.textSecondary }}>{s.reason}</Text>
                      </View>
                      <Ionicons name="chevron-forward" size={16} color={GOLD} />
                    </TouchableOpacity>
                  ))}
                  <Text style={{ fontSize: 11.5, color: colors.textSecondary }}>Not them? Search below.</Text>
                </View>
              ) : null}
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: colors.card, borderRadius: 12, paddingHorizontal: 12, height: 46, borderWidth: 1, borderColor: colors.border }}>
                <Ionicons name="search" size={18} color={colors.textSecondary} />
                <TextInput value={q} onChangeText={setQ} placeholder="Search by name or number" placeholderTextColor={colors.textSecondary} autoFocus={!memo?.suggested_contacts?.length} style={{ flex: 1, color: textColor, fontSize: 15 }} {...tid('attach-search')} />
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
              <TouchableOpacity onPress={() => goCreate(null)} style={{ flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 12 }} {...tid('attach-new-contact')}>
                <Ionicons name="person-add-outline" size={18} color={GOLD} />
                <Text style={{ color: GOLD, fontWeight: '700' }}>{memo?.new_people?.length ? 'Someone else who is not in my contacts yet' : 'They are not in my contacts yet'}</Text>
              </TouchableOpacity>
              {memo?.new_people?.length ? (
                <View style={{ gap: 6, paddingBottom: 6 }} {...tid('attach-new-people')}>
                  <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.6 }}>JESSI HEARD · NOT IN YOUR CONTACTS YET</Text>
                  {memo.new_people.map((p: any, i: number) => (
                    <TouchableOpacity key={`${p.name}-${i}`} onPress={() => goCreate(p)} style={{ flexDirection: 'row', alignItems: 'center', gap: 12, padding: 10, borderRadius: 14, backgroundColor: colors.card, borderWidth: 1, borderColor: GOLD + '66' }} {...tid(`attach-create-${i}`)}>
                      <View style={{ width: 38, height: 38, borderRadius: 19, backgroundColor: GOLD + '22', alignItems: 'center', justifyContent: 'center' }}><Ionicons name="person-add" size={17} color={GOLD} /></View>
                      <View style={{ flex: 1 }}>
                        <Text style={{ fontSize: 15, fontWeight: '800', color: textColor }}>Add {p.name} as a new contact</Text>
                        <Text style={{ fontSize: 12, color: colors.textSecondary }}>{p.company ? `${p.company} · name and company prefilled` : 'Name prefilled, you add the number'}</Text>
                      </View>
                      <Ionicons name="chevron-forward" size={16} color={GOLD} />
                    </TouchableOpacity>
                  ))}
                </View>
              ) : null}
            </>
          ) : (
            <MemoKindPicker firstName={nameOf(picked).split(' ')[0]} busy={busy} onPick={attach} colors={colors} secondaryLabel="Pick someone else" onSecondary={() => setPicked(null)} />
          )}
        </View>
      </View>
    </Modal>
  );
};
