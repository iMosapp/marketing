import React, { useEffect, useState } from 'react';
import { View, Text, TextInput, TouchableOpacity, Modal, ScrollView, ActivityIndicator, Platform } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api, { tagsAPI } from '../../services/api';
import { GOLD, tid, errText } from '../inbox/ownership';

type Props = { visible: boolean; onClose: () => void; userId?: string; memo: any | null; colors: any; onSaved: (memoId: string, tags: string[]) => void; showToast: (m: string, t?: any, d?: number) => void; library: any[]; onLibrary: (tags: any[]) => void };

// Tag a memo with the same tags you use on contacts; type to filter or create a new one.
export const MemoTagSheet = ({ visible, onClose, userId, memo, colors, onSaved, showToast, library, onLibrary }: Props) => {
  const [picked, setPicked] = useState<string[]>([]);
  const [q, setQ] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (visible) { setPicked(memo?.tags || []); setQ(''); } }, [visible, memo?.id]);

  const toggle = (name: string) => setPicked(p => p.some(t => t.toLowerCase() === name.toLowerCase()) ? p.filter(t => t.toLowerCase() !== name.toLowerCase()) : [...p, name]);
  const create = async () => {
    const name = q.trim(); if (!name || !userId) return;
    try { const t = await tagsAPI.create(userId, { name, color: GOLD, icon: 'pricetag' }); onLibrary([...library, t]); toggle(name); setQ(''); }
    catch (e) { showToast(errText(e, 'Could not create that tag'), 'error'); }
  };
  const save = async () => {
    if (!memo || !userId) return;
    setBusy(true);
    try { const r = await api.patch(`/voice-memos/${userId}/${memo.id}`, { tags: picked }); onSaved(memo.id, r.data.tags || picked); onClose(); }
    catch (e) { showToast(errText(e, 'Could not save tags'), 'error'); }
    finally { setBusy(false); }
  };

  const s = q.trim().toLowerCase();
  const shown = library.filter(t => !s || t.name.toLowerCase().includes(s));
  const exact = library.some(t => t.name.toLowerCase() === s);
  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <View style={{ flex: 1, backgroundColor: '#00000088', justifyContent: 'flex-end' }}>
        <View style={{ backgroundColor: colors.bg, borderTopLeftRadius: 24, borderTopRightRadius: 24, padding: 18, paddingBottom: Platform.OS === 'ios' ? 34 : 18, maxHeight: '80%' }} {...tid('memo-tag-sheet')}>
          <View style={{ flexDirection: 'row', alignItems: 'center', marginBottom: 10 }}>
            <Text style={{ flex: 1, fontSize: 17, fontWeight: '800', color: colors.text }}>Tags for {memo?.title || 'this memo'}</Text>
            <TouchableOpacity onPress={onClose} {...tid('memo-tag-close')}><Ionicons name="close" size={24} color={colors.text} /></TouchableOpacity>
          </View>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: colors.card, borderRadius: 12, paddingHorizontal: 12, height: 44, borderWidth: 1, borderColor: colors.border }}>
            <Ionicons name="pricetag-outline" size={17} color={colors.textSecondary} />
            <TextInput value={q} onChangeText={setQ} placeholder="Find or create a tag" placeholderTextColor={colors.textSecondary} autoCorrect={false} onSubmitEditing={() => { if (s && !exact) create(); }} style={{ flex: 1, color: colors.text, fontSize: 15 }} {...tid('memo-tag-search')} />
          </View>
          <ScrollView style={{ marginTop: 8, maxHeight: 360 }} keyboardShouldPersistTaps="handled">
            {s && !exact ? (
              <TouchableOpacity onPress={create} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: colors.border }} {...tid('memo-tag-create')}>
                <Ionicons name="add-circle" size={20} color={GOLD} />
                <Text style={{ fontSize: 15, fontWeight: '700', color: GOLD }}>Create "{q.trim()}"</Text>
              </TouchableOpacity>
            ) : null}
            {shown.map(t => { const on = picked.some(p => p.toLowerCase() === t.name.toLowerCase()); return (
              <TouchableOpacity key={t._id || t.name} onPress={() => toggle(t.name)} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: colors.border }} {...tid(`memo-tag-pick-${t.name}`)}>
                <View style={{ width: 10, height: 10, borderRadius: 5, backgroundColor: t.color || GOLD }} />
                <Text style={{ flex: 1, fontSize: 15, color: colors.text }}>{t.name}</Text>
                <Ionicons name={on ? 'checkmark-circle' : 'ellipse-outline'} size={22} color={on ? GOLD : colors.border} />
              </TouchableOpacity>
            ); })}
            {!shown.length && !s ? <Text style={{ color: colors.textSecondary, padding: 14, textAlign: 'center' }}>No tags yet. Type one above to create it.</Text> : null}
          </ScrollView>
          <TouchableOpacity onPress={save} disabled={busy} style={{ marginTop: 12, height: 46, borderRadius: 14, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center' }} {...tid('memo-tag-save')}>
            {busy ? <ActivityIndicator color="#111" /> : <Text style={{ fontSize: 15, fontWeight: '800', color: '#111' }}>{picked.length ? `Save ${picked.length} tag${picked.length === 1 ? '' : 's'}` : 'Save (no tags)'}</Text>}
          </TouchableOpacity>
        </View>
      </View>
    </Modal>
  );
};
