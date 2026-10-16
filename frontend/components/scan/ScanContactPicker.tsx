import React, { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, TextInput } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { GOLD, tid } from '../inbox/ownership';
import { ScanMatch } from '../../hooks/useScanWithJessi';

export type PickedContact = { id: string; name: string };
type Props = { userId?: string; matches: ScanMatch[]; selected: PickedContact | null; onSelect: (c: PickedContact) => void; colors: any };

const nameOf = (c: any) => `${c.first_name || ''} ${c.last_name || ''}`.trim() || c.phone || 'Unnamed';

// Who the document is for: Jessi's guesses first (same name, phone, email or company), or search your contacts.
export const ScanContactPicker = ({ userId, matches, selected, onSelect, colors }: Props) => {
  const [q, setQ] = useState('');
  const [rows, setRows] = useState<any[]>([]);
  useEffect(() => {
    if (!userId || q.trim().length < 2) { setRows([]); return; }
    const t = setTimeout(() => {
      api.get(`/contacts/${userId}`, { params: { search: q.trim(), limit: 6 } })
        .then(r => setRows(Array.isArray(r.data) ? r.data : r.data?.contacts || [])).catch(() => setRows([]));
    }, 300);
    return () => clearTimeout(t);
  }, [q, userId]);
  const opts = [
    ...matches.map(m => ({ id: m.id, name: m.name, sub: [m.why.join(', '), m.company || m.phone].filter(Boolean).join(' · ') })),
    ...rows.map(c => ({ id: String(c._id || c.id), name: nameOf(c), sub: c.employer || c.phone || '' })).filter(c => !matches.some(m => m.id === c.id)),
  ];
  return (
    <View style={{ marginTop: 14 }} {...tid('scan-contact-picker')}>
      <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.8, marginBottom: 6 }}>WHO IS IT FOR?</Text>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, borderWidth: 1, borderColor: colors.border, borderRadius: 12, paddingHorizontal: 12, marginBottom: 8 }}>
        <Ionicons name="search" size={16} color={colors.textSecondary} />
        <TextInput value={q} onChangeText={setQ} placeholder="Search your contacts" placeholderTextColor={colors.textSecondary} autoCorrect={false}
          style={{ flex: 1, fontSize: 15, color: colors.text, paddingVertical: 10 }} {...tid('scan-contact-search')} />
      </View>
      {opts.map(o => { const on = selected?.id === o.id; return (
        <TouchableOpacity key={o.id} onPress={() => onSelect({ id: o.id, name: o.name })} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, padding: 11, borderRadius: 12, borderWidth: 1.5, borderColor: on ? GOLD : colors.border, backgroundColor: on ? `${GOLD}18` : 'transparent', marginBottom: 6 }} {...tid(`scan-contact-option-${o.id}`)}>
          <Ionicons name={on ? 'radio-button-on' : 'radio-button-off'} size={20} color={on ? GOLD : colors.border} />
          <View style={{ flex: 1 }}>
            <Text style={{ fontSize: 15, fontWeight: '700', color: colors.text }}>{o.name}</Text>
            {!!o.sub && <Text style={{ fontSize: 12.5, color: colors.textSecondary }} numberOfLines={1}>{o.sub}</Text>}
          </View>
        </TouchableOpacity>
      ); })}
      {!opts.length && <Text style={{ fontSize: 12.5, color: colors.textSecondary }} {...tid('scan-contact-none')}>{q.trim().length >= 2 ? 'No contacts match that.' : 'Type a name, phone or email.'}</Text>}
    </View>
  );
};
