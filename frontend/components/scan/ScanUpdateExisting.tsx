import React, { useState } from 'react';
import { View, Text, TouchableOpacity, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { GOLD, tid } from '../inbox/ownership';
import { ScanMatch } from '../../hooks/useScanWithJessi';

const ORDER = ['first_name', 'last_name', 'company', 'title', 'phone', 'phone_office', 'email', 'website', 'address_street', 'address_city', 'address_state', 'address_zip'];
const norm = (v: string) => (v || '').toLowerCase().replace(/[^a-z0-9@.]/g, '');
const same = (k: string, a: string, b: string) => (k.startsWith('phone') ? (a || '').replace(/\D/g, '').slice(-10) === (b || '').replace(/\D/g, '').slice(-10) : norm(a) === norm(b));
const ADDS = new Set(['phone', 'phone_office', 'email']);   // extra numbers/emails are added next to what is saved, never replace it

type Props = { match: ScanMatch; values: Record<string, string>; labels: Record<string, string>; colors: any; busy: boolean;
  onBack: () => void; onSave: (fields: string[]) => void };

// Card vs what the contact already has. Empty slots are ticked; anything that would REPLACE a saved value starts unticked.
export const ScanUpdateExisting = ({ match, values, labels, colors, busy, onBack, onSave }: Props) => {
  const rows = ORDER.filter(k => values[k] && !same(k, values[k], match.current?.[k] || ''));
  const [picked, setPicked] = useState<string[]>(rows.filter(k => !match.current?.[k] || ADDS.has(k)));
  const toggle = (k: string) => setPicked(p => (p.includes(k) ? p.filter(x => x !== k) : [...p, k]));
  return (
    <View {...tid('scan-update-existing')}>
      <TouchableOpacity onPress={onBack} style={{ flexDirection: 'row', alignItems: 'center', gap: 4, marginBottom: 8 }} {...tid('scan-update-back')}>
        <Ionicons name="chevron-back" size={16} color={GOLD} /><Text style={{ color: GOLD, fontWeight: '700' }}>Back</Text>
      </TouchableOpacity>
      <Text style={{ fontSize: 17, fontWeight: '800', color: colors.text }}>Update {match.name}</Text>
      <Text style={{ fontSize: 12.5, color: colors.textSecondary, marginTop: 2, marginBottom: 10 }}>Only what you tick is saved. The card is added to their Files either way.</Text>
      {rows.length === 0 && <Text style={{ fontSize: 13.5, color: colors.textSecondary }} {...tid('scan-update-nothing')}>Everything on the card is already on this contact.</Text>}
      {rows.map(k => {
        const cur = match.current?.[k] || '';
        const on = picked.includes(k);
        return (
          <TouchableOpacity key={k} onPress={() => toggle(k)} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: colors.border }} {...tid(`scan-update-row-${k}`)}>
            <Ionicons name={on ? 'checkbox' : 'square-outline'} size={22} color={on ? GOLD : colors.textSecondary} />
            <View style={{ flex: 1 }}>
              <Text style={{ fontSize: 12, color: colors.textSecondary }}>{labels[k] || k}</Text>
              <Text style={{ fontSize: 15, color: colors.text, fontWeight: '600' }}>{values[k]}</Text>
              {!!cur && (ADDS.has(k)
                ? <Text style={{ fontSize: 12, color: colors.textSecondary }}>Added next to {cur}</Text>
                : <Text style={{ fontSize: 12, color: '#FF9500' }} {...tid(`scan-update-replaces-${k}`)}>Replaces "{cur}"</Text>)}
            </View>
          </TouchableOpacity>
        );
      })}
      <TouchableOpacity disabled={busy} onPress={() => onSave(picked)} style={{ height: 48, borderRadius: 12, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center', marginTop: 16, opacity: busy ? 0.6 : 1 }} {...tid('scan-update-save')}>
        {busy ? <ActivityIndicator color="#111" /> : <Text style={{ fontSize: 15.5, fontWeight: '800', color: '#111' }}>{picked.length ? `Save ${picked.length} detail${picked.length === 1 ? '' : 's'} + card` : 'Save the card only'}</Text>}
      </TouchableOpacity>
    </View>
  );
};
