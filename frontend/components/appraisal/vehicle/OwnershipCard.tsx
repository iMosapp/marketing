import React, { useState } from 'react';
import { View, Text, TouchableOpacity, TextInput } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { GOLD, tid } from '../../inbox/ownership';
import { showConfirm } from '../../../services/alert';

type Props = { colors: any; vehicle: any; onSet: (status: string, note: string) => Promise<void>; canEdit: boolean };
const when = (iso?: string) => (iso ? new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' }) : '');
const OWN_COLOR: Record<string, string> = { owns: '#34C759', traded: GOLD, sold: '#8E8E93', no_longer_owns: '#8E8E93', unknown: '#FF9500' };

// What actually happened to the car. An accepted offer is intent; only a person (or a deal) confirms the trade here.
export const OwnershipCard = ({ colors, vehicle: v, onSet, canEdit }: Props) => {
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const color = OWN_COLOR[v.ownership_status] || colors.textSecondary;
  const go = (status: string, title: string, body: string) => showConfirm(title, body, async () => {
    setBusy(true);
    try { await onSet(status, note.trim()); setNote(''); } finally { setBusy(false); }
  }, undefined, 'Confirm');
  const accepted = v.trade_intent_status === 'accepted' && v.ownership_status === 'owns';
  return (
    <View style={{ borderRadius: 16, padding: 14, backgroundColor: colors.card, borderWidth: 1.5, borderColor: accepted ? GOLD : colors.border, gap: 10 }} {...tid('ownership-card')}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
        <Ionicons name={v.ownership_status === 'owns' ? 'key' : v.ownership_status === 'traded' ? 'swap-horizontal' : 'exit-outline'} size={18} color={color} />
        <Text style={{ flex: 1, fontSize: 15, fontWeight: '800', color: colors.text }} {...tid('ownership-label')}>{v.ownership_label}</Text>
        {v.trade_intent_label ? <View style={{ backgroundColor: GOLD + '22', borderRadius: 8, paddingHorizontal: 7, paddingVertical: 2 }} {...tid('trade-intent-chip')}><Text style={{ fontSize: 10.5, fontWeight: '800', color: GOLD }}>{v.trade_intent_label}</Text></View> : null}
      </View>
      {accepted ? <Text style={{ fontSize: 12.5, color: colors.text, lineHeight: 17 }} {...tid('ownership-accepted-hint')}>The customer accepted the offer, but the trade is not done until the deal closes. Confirm it here when the keys change hands.</Text> : null}
      {v.ownership_updated_at ? <Text style={{ fontSize: 12, color: colors.textSecondary }} {...tid('ownership-updated')}>Set by {v.ownership_updated_by_name || 'a teammate'} {when(v.ownership_updated_at)}{v.ownership_note ? ` · ${v.ownership_note}` : ''}</Text> : null}
      {v.trade_confirmed_at ? <Text style={{ fontSize: 12, fontWeight: '700', color: GOLD }} {...tid('trade-confirmed')}>Trade confirmed {when(v.trade_confirmed_at)}</Text> : null}
      {canEdit ? (
        <>
          <TextInput value={note} onChangeText={setNote} placeholder="Optional note (deal #, where it went)" placeholderTextColor={colors.textSecondary} style={{ height: 40, borderRadius: 10, paddingHorizontal: 10, backgroundColor: colors.bg, borderWidth: 1, borderColor: colors.border, color: colors.text, fontSize: 13 }} {...tid('ownership-note')} />
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
            {v.ownership_status !== 'traded' ? <Btn colors={colors} label="Confirm trade" icon="checkmark-circle" primary disabled={busy} testId="ownership-traded" onPress={() => go('traded', 'Confirm the trade?', `${v.label} is marked traded in to us. This is the only thing that closes the vehicle out.`)} /> : null}
            {v.ownership_status !== 'sold' ? <Btn colors={colors} label="Sold elsewhere" icon="storefront-outline" disabled={busy} testId="ownership-sold" onPress={() => go('sold', 'Sold elsewhere?', `${v.label} was sold or traded somewhere else.`)} /> : null}
            {v.ownership_status !== 'owns' ? <Btn colors={colors} label="Still owns it" icon="key" disabled={busy} testId="ownership-owns" onPress={() => go('owns', 'Still owns it?', 'Puts the vehicle back to currently owned and clears the trade confirmation.')} /> : null}
            {v.ownership_status !== 'no_longer_owns' ? <Btn colors={colors} label="No longer owns" icon="exit-outline" disabled={busy} testId="ownership-gone" onPress={() => go('no_longer_owns', 'No longer owns it?', 'Totaled, gifted, or gone. We stop suggesting reappraisals.')} /> : null}
          </View>
        </>
      ) : null}
    </View>
  );
};

const Btn = ({ colors, label, icon, onPress, primary, disabled, testId }: { colors: any; label: string; icon: any; onPress: () => void; primary?: boolean; disabled?: boolean; testId: string }) => (
  <TouchableOpacity onPress={onPress} disabled={disabled} style={{ flexDirection: 'row', alignItems: 'center', gap: 5, height: 36, paddingHorizontal: 12, borderRadius: 10, backgroundColor: primary ? GOLD : colors.bg, borderWidth: 1, borderColor: primary ? GOLD : colors.border, opacity: disabled ? 0.5 : 1 }} {...tid(testId)}>
    <Ionicons name={icon} size={14} color={primary ? '#0B0B0D' : colors.text} /><Text style={{ fontSize: 12.5, fontWeight: '800', color: primary ? '#0B0B0D' : colors.text }}>{label}</Text>
  </TouchableOpacity>
);
