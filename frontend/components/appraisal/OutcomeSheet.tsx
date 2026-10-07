import React, { useState } from 'react';
import { View, Text, TextInput, TouchableOpacity, Modal, ScrollView } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { GOLD, tid, errText } from '../inbox/ownership';
import { money } from './shared';

type Props = { colors: any; appraisal: any; visible: boolean; onClose: () => void; onSaved: (appraisal: any) => void; showToast: (m: string, t?: any, d?: number) => void };
const OUTCOMES: { key: string; label: string; icon: any; sub: string }[] = [
  { key: 'accepted', label: 'Accepted', icon: 'checkmark-circle', sub: 'Taking the trade at this number' },
  { key: 'wants_more', label: 'Wants more', icon: 'trending-up', sub: 'Tell us the number they want' },
  { key: 'thinking', label: 'Thinking about it', icon: 'time', sub: 'Left to decide' },
  { key: 'not_trading', label: 'Not trading', icon: 'close-circle', sub: 'Keeping the vehicle or selling it elsewhere' },
  { key: 'other', label: 'Other', icon: 'ellipsis-horizontal-circle', sub: 'Say what happened in the note' },
];

// What did the customer say? One tap, an amount when they want more, an optional note. Closes the appraisal and updates the relationship record.
export const OutcomeSheet = ({ colors, appraisal, visible, onClose, onSaved, showToast }: Props) => {
  const [pick, setPick] = useState<string | null>(null);
  const [amount, setAmount] = useState('');
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const approved = appraisal.workflow?.approved_value ?? appraisal.approved_value;
  const save = async () => {
    if (!pick) return;
    const n = amount ? parseInt(amount.replace(/\D/g, ''), 10) : undefined;
    if (pick === 'wants_more' && !n) { showToast('Enter the number the customer wants', 'error'); return; }
    setBusy(true);
    try {
      const r = (await api.post(`/appraisals/${appraisal.id}/outcome`, { outcome: pick, expected_value: pick === 'wants_more' ? n : undefined, note })).data;
      onSaved({ ...r.appraisal, workflow: r.workflow, abilities: r.abilities }); onClose();
      showToast('Outcome saved on the customer\u2019s record', 'success');
    } catch (e) { showToast(errText(e, 'Could not save the outcome'), 'error', 5000); }
    finally { setBusy(false); }
  };
  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <TouchableOpacity activeOpacity={1} onPress={onClose} style={{ flex: 1, backgroundColor: '#00000088' }} />
      <View style={{ backgroundColor: colors.bg, borderTopLeftRadius: 22, borderTopRightRadius: 22, padding: 18, paddingBottom: 34, maxHeight: '88%' }} {...tid('outcome-sheet')}>
        <View style={{ flexDirection: 'row', alignItems: 'center', marginBottom: 10 }}>
          <View style={{ flex: 1 }}>
            <Text style={{ fontSize: 19, fontWeight: '800', color: colors.text }}>What did the customer say?</Text>
            <Text style={{ fontSize: 12.5, color: colors.textSecondary, marginTop: 2 }}>{appraisal.status === 'declined' ? 'The desk declined this trade.' : `You presented ${money(approved)}.`}</Text>
          </View>
          <TouchableOpacity onPress={onClose} hitSlop={10} {...tid('outcome-close')}><Ionicons name="close" size={24} color={colors.textSecondary} /></TouchableOpacity>
        </View>
        <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={{ gap: 8 }}>
          {OUTCOMES.map(o => { const on = pick === o.key; return (
            <TouchableOpacity key={o.key} onPress={() => setPick(o.key)} activeOpacity={0.85} style={{ flexDirection: 'row', alignItems: 'center', gap: 12, padding: 12, borderRadius: 14, backgroundColor: on ? GOLD + '22' : colors.card, borderWidth: 1, borderColor: on ? GOLD : colors.border }} {...tid(`outcome-${o.key}`)}>
              <Ionicons name={o.icon} size={22} color={on ? GOLD : colors.textSecondary} />
              <View style={{ flex: 1 }}><Text style={{ fontSize: 15, fontWeight: '800', color: colors.text }}>{o.label}</Text><Text style={{ fontSize: 12, color: colors.textSecondary }}>{o.sub}</Text></View>
              {on ? <Ionicons name="checkmark-circle" size={20} color={GOLD} /> : null}
            </TouchableOpacity>
          ); })}
          {pick === 'wants_more' ? (
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, height: 50, borderRadius: 14, paddingHorizontal: 14, backgroundColor: colors.card, borderWidth: 1, borderColor: GOLD }}>
              <Text style={{ fontSize: 18, fontWeight: '800', color: colors.textSecondary }}>$</Text>
              <TextInput value={amount} onChangeText={t => setAmount(t.replace(/\D/g, '').slice(0, 7))} keyboardType="number-pad" placeholder="Number they want" placeholderTextColor={colors.textSecondary} style={{ flex: 1, fontSize: 18, fontWeight: '800', color: colors.text }} autoFocus {...tid('outcome-amount')} />
            </View>
          ) : null}
          <TextInput value={note} onChangeText={setNote} placeholder="Note (optional): what they said, when to follow up" placeholderTextColor={colors.textSecondary} multiline style={{ minHeight: 64, borderRadius: 14, padding: 12, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, color: colors.text, fontSize: 14, textAlignVertical: 'top' }} {...tid('outcome-note')} />
          <TouchableOpacity onPress={save} disabled={!pick || busy} style={{ height: 52, borderRadius: 14, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center', opacity: !pick || busy ? 0.5 : 1 }} {...tid('outcome-save')}>
            <Text style={{ fontSize: 15, fontWeight: '800', color: '#0B0B0D' }}>Save outcome</Text>
          </TouchableOpacity>
        </ScrollView>
      </View>
    </Modal>
  );
};
