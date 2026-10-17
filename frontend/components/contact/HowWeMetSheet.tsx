// Edit "How we met": the rep's entry always wins over what Jessi filled in. Clearing every field removes it.
import React, { useEffect, useState } from 'react';
import { Modal, View, Text, TextInput, TouchableOpacity, KeyboardAvoidingView, Platform } from 'react-native';
import api from '../../services/api';
import { SheetGrabber } from '../common/SheetGrabber';
import { PrimaryButton } from '../ui/PrimaryButton';
import { GOLD, RED, RADIUS, SPACE, TYPE, tid } from '../ui/tokens';

export type HowWeMet = { event?: string; place?: string; date?: string; summary?: string; source?: string };

const FIELDS: { key: 'event' | 'place' | 'date'; label: string; placeholder: string }[] = [
  { key: 'event', label: 'Where or how', placeholder: 'NADA, the golf tournament, walked into the store' },
  { key: 'place', label: 'City or venue', placeholder: 'Las Vegas' },
  { key: 'date', label: 'When (YYYY-MM-DD or YYYY-MM)', placeholder: '2026-02-12' },
];

export default function HowWeMetSheet({ visible, onClose, colors, userId, contactId, value, onSaved, showToast }: any) {
  const [form, setForm] = useState({ event: '', place: '', date: '' });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');

  useEffect(() => {
    if (visible) { setForm({ event: value?.event || '', place: value?.place || '', date: value?.date || '' }); setErr(''); }
  }, [visible, value]);

  const save = async (clear = false) => {
    const body = clear ? { event: '', place: '', date: '' } : form;
    if (!clear && body.date && !/^\d{4}-\d{2}(-\d{2})?$/.test(body.date.trim())) { setErr('Use YYYY-MM-DD or YYYY-MM for the date, or leave it empty.'); return; }
    setBusy(true);
    try {
      const r = await api.patch(`/contacts/${userId}/${contactId}/how-we-met`, body);
      onSaved?.(r.data?.how_we_met || {});
      showToast?.(clear ? 'How we met cleared' : 'How we met saved', 'success');
      onClose();
    } catch (e: any) {
      setErr(e?.response?.data?.detail || 'Could not save. Try again.');
    } finally { setBusy(false); }
  };

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <TouchableOpacity style={{ flex: 1, backgroundColor: 'rgba(0,0,0,0.5)' }} activeOpacity={1} onPress={onClose} />
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <View style={{ backgroundColor: colors.bg, borderTopLeftRadius: RADIUS.xl, borderTopRightRadius: RADIUS.xl, padding: SPACE.lg, paddingBottom: SPACE.xxl }} {...tid('how-we-met-sheet')}>
          <SheetGrabber onClose={onClose} color={colors.border} />
          <Text style={{ fontSize: TYPE.section, fontWeight: '800', color: colors.text, marginTop: SPACE.sm }}>How we met</Text>
          <Text style={{ fontSize: TYPE.sub, color: colors.textSecondary, marginTop: 4, marginBottom: SPACE.md }}>Jessi and your campaigns use this to remember where you met.</Text>
          {FIELDS.map(f => (
            <View key={f.key} style={{ marginBottom: SPACE.md }}>
              <Text style={{ fontSize: TYPE.label, fontWeight: '800', color: colors.textSecondary, textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 6 }}>{f.label}</Text>
              <TextInput value={form[f.key]} onChangeText={t => { setErr(''); setForm(p => ({ ...p, [f.key]: t })); }} placeholder={f.placeholder} placeholderTextColor={colors.textTertiary}
                autoCapitalize={f.key === 'date' ? 'none' : 'words'} keyboardType={f.key === 'date' ? 'numbers-and-punctuation' : 'default'}
                style={{ fontSize: TYPE.body, color: colors.text, backgroundColor: colors.card, borderRadius: RADIUS.sm, borderWidth: 1, borderColor: colors.border, paddingHorizontal: SPACE.md, paddingVertical: 12 }}
                {...tid(`how-we-met-input-${f.key}`)} />
            </View>
          ))}
          {!!err && <Text style={{ color: RED, fontSize: TYPE.sub, marginBottom: SPACE.sm }} {...tid('how-we-met-error')}>{err}</Text>}
          <PrimaryButton label="Save" icon="checkmark" full loading={busy} onPress={() => save(false)} testID="how-we-met-save" />
          {!!value?.summary && (
            <TouchableOpacity onPress={() => save(true)} disabled={busy} style={{ alignSelf: 'center', paddingVertical: SPACE.md }} {...tid('how-we-met-clear')}>
              <Text style={{ color: GOLD, fontWeight: '700', fontSize: TYPE.sub }}>Clear</Text>
            </TouchableOpacity>
          )}
        </View>
      </KeyboardAvoidingView>
    </Modal>
  );
}
