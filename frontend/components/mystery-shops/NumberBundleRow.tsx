import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, TextInput, TouchableOpacity, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { useToast } from '../common/Toast';
import { GOLD, GREEN, AMBER, tid } from './shared';

type BundleRow = { country: string; needs: string; bundle_sid: string; address_sid: string; on_file: boolean };

// UK / Irish / Belgian numbers: Twilio wants one regulatory bundle per country. Paste the SIDs once, every client in that country buys against it.
export const NumberBundleRow = ({ country, colors, onSaved }: { country: string; colors: any; onSaved: () => void }) => {
  const { showToast } = useToast();
  const [row, setRow] = useState<BundleRow | null>(null);
  const [edit, setEdit] = useState(false);
  const [bundle, setBundle] = useState('');
  const [address, setAddress] = useState('');
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    api.get('/shop-clients/number/bundles').then(r => {
      const hit = (r.data.countries as BundleRow[]).find(x => x.country === country) || null;
      setRow(hit); setBundle(hit?.bundle_sid || ''); setAddress(hit?.address_sid || '');
    }).catch(() => {});
  }, [country]);
  useEffect(load, [load]);

  const save = async () => {
    setBusy(true);
    try {
      await api.put('/shop-clients/number/bundles', { country, bundle_sid: bundle.trim(), address_sid: address.trim() });
      showToast(bundle.trim() ? 'Bundle saved, numbers can be bought now' : 'Bundle removed', 'success'); setEdit(false); load(); onSaved();
    } catch (e: any) { showToast(e?.response?.data?.detail || 'Could not save', 'error'); }
    finally { setBusy(false); }
  };

  if (!row) return null;
  const tone = row.on_file ? GREEN : AMBER;
  return (
    <View style={{ borderTopWidth: 1, borderTopColor: colors.border, paddingTop: 8, gap: 6 }} {...tid('number-bundle-row')}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
        <Ionicons name={row.on_file ? 'shield-checkmark' : 'shield-outline'} size={15} color={tone} />
        <Text style={{ flex: 1, fontSize: 12.5, fontWeight: '700', color: colors.text }} {...tid('number-bundle-status')}>
          {row.on_file ? `Twilio bundle on file for ${country} · ${row.bundle_sid.slice(0, 6)}…${row.bundle_sid.slice(-4)}` : `Twilio needs a regulatory bundle before it sells ${country} numbers`}
        </Text>
        {!edit && <TouchableOpacity onPress={() => setEdit(true)} {...tid('number-bundle-edit')}><Text style={{ fontSize: 12.5, fontWeight: '800', color: GOLD }}>{row.on_file ? 'Change' : 'Add'}</Text></TouchableOpacity>}
      </View>
      {!row.on_file && !edit && <Text style={{ fontSize: 11.5, color: colors.textSecondary, lineHeight: 16 }}>Needs {row.needs}. Create it once in the Twilio Console (Phone Numbers › Regulatory Compliance), then paste the two SIDs here; after that every {country} client gets its number automatically at kickoff.</Text>}
      {edit && (
        <View style={{ gap: 6 }}>
          <TextInput value={bundle} onChangeText={setBundle} placeholder="Bundle SID (BU…)" placeholderTextColor={colors.textSecondary} autoCapitalize="none" autoCorrect={false}
            style={{ height: 38, borderRadius: 10, borderWidth: 1, borderColor: colors.border, paddingHorizontal: 10, color: colors.text, fontSize: 13, backgroundColor: colors.background }} {...tid('number-bundle-sid')} />
          <TextInput value={address} onChangeText={setAddress} placeholder="Address SID (AD…)" placeholderTextColor={colors.textSecondary} autoCapitalize="none" autoCorrect={false}
            style={{ height: 38, borderRadius: 10, borderWidth: 1, borderColor: colors.border, paddingHorizontal: 10, color: colors.text, fontSize: 13, backgroundColor: colors.background }} {...tid('number-bundle-address')} />
          <View style={{ flexDirection: 'row', gap: 8 }}>
            <TouchableOpacity onPress={save} disabled={busy || (!row.on_file && !bundle.trim() && !address.trim())} accessibilityState={{ disabled: busy || (!row.on_file && !bundle.trim() && !address.trim()) }} style={{ flex: 1, height: 36, borderRadius: 12, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center', opacity: busy || (!row.on_file && !bundle.trim() && !address.trim()) ? 0.5 : 1 }} {...tid('number-bundle-save')}>
              {busy ? <ActivityIndicator color="#111" size="small" /> : <Text style={{ fontSize: 13, fontWeight: '800', color: '#111' }}>{row.on_file && !bundle.trim() && !address.trim() ? 'Remove bundle' : 'Save bundle'}</Text>}
            </TouchableOpacity>
            <TouchableOpacity onPress={() => { setEdit(false); setBundle(row.bundle_sid); setAddress(row.address_sid); }} style={{ height: 36, paddingHorizontal: 14, borderRadius: 12, borderWidth: 1, borderColor: colors.border, alignItems: 'center', justifyContent: 'center' }} {...tid('number-bundle-cancel')}>
              <Text style={{ fontSize: 13, fontWeight: '700', color: colors.textSecondary }}>Cancel</Text>
            </TouchableOpacity>
          </View>
        </View>
      )}
    </View>
  );
};
