import React, { useState } from 'react';
import { View, Text, TouchableOpacity, ActivityIndicator } from 'react-native';
import { GOLD, tid } from '../inbox/ownership';
import { ScanMatch } from '../../hooks/useScanWithJessi';
import { ScanFound } from './ScanReview';
import { DocDates } from './DocDates';
import { ScanContactPicker, PickedContact } from './ScanContactPicker';

type Props = { scan: any; matches: ScanMatch[]; userId?: string; colors: any; busy: boolean;
  onSave: (c: PickedContact, reminders: string[]) => void; onCreate: (reminders: string[]) => void; onDiscard: () => void };

// A quote, invoice, service paper, screenshot or other photo: what Jessi found, key dates + reminders to tick, who it is for.
export const ScanDocReview = ({ scan, matches, userId, colors, busy, onSave, onCreate, onDiscard }: Props) => {
  const [picked, setPicked] = useState<string[]>([]);
  const [who, setWho] = useState<PickedContact | null>(matches.length === 1 ? { id: matches[0].id, name: matches[0].name } : null);
  const ready = scan.status === 'ready';
  const canCreate = ready && !scan.sensitive && !!(scan.fields?.first_name || scan.fields?.phone);
  const toggle = (k: string) => setPicked(p => (p.includes(k) ? p.filter(x => x !== k) : [...p, k]));
  return (
    <View {...tid('scan-doc-review')}>
      <ScanFound scan={scan} colors={colors} />
      {ready && !scan.sensitive && (
        <View style={{ marginTop: 12 }}><DocDates dates={scan.dates || []} reminders={scan.reminders || []} colors={colors} picked={picked} onToggle={toggle} /></View>
      )}
      {scan.sensitive && <Text style={{ fontSize: 12.5, color: colors.textSecondary, marginTop: 10 }} {...tid('scan-doc-private')}>It can only be attached privately: just you can see it, and it is removed after 30 days.</Text>}
      <ScanContactPicker userId={userId} matches={matches} selected={who} onSelect={setWho} colors={colors} />
      <View style={{ gap: 8, marginTop: 14 }}>
        <TouchableOpacity disabled={!who || busy} onPress={() => who && onSave(who, picked)} style={{ height: 48, borderRadius: 12, backgroundColor: who ? GOLD : colors.border, alignItems: 'center', justifyContent: 'center' }} {...tid('scan-doc-save')}>
          {busy ? <ActivityIndicator color="#111" /> : <Text style={{ fontSize: 15.5, fontWeight: '800', color: '#111' }} numberOfLines={1}>{who ? `Save to ${who.name}${picked.length ? ` + ${picked.length} reminder${picked.length === 1 ? '' : 's'}` : ''}` : 'Pick who it is for'}</Text>}
        </TouchableOpacity>
        {canCreate && (
          <TouchableOpacity onPress={() => onCreate(picked)} style={{ height: 44, borderRadius: 12, borderWidth: 1, borderColor: GOLD, alignItems: 'center', justifyContent: 'center' }} {...tid('scan-doc-create')}>
            <Text style={{ fontSize: 14.5, fontWeight: '700', color: GOLD }}>New contact from this</Text>
          </TouchableOpacity>
        )}
        <TouchableOpacity onPress={onDiscard} style={{ height: 44, borderRadius: 12, borderWidth: 1, borderColor: colors.border, alignItems: 'center', justifyContent: 'center' }} {...tid('scan-discard')}>
          <Text style={{ fontSize: 14.5, fontWeight: '700', color: colors.text }}>Discard</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
};
