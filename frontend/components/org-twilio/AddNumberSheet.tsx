/** Add Phone Number: pick who it is for (area-code suggestions follow), search by area code / digits / city with SMS-MMS-voice filters,
 * pick a number, confirm the purchase. The admin always approves before anything is bought. */
import React, { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, ActivityIndicator, TextInput, ScrollView, Modal, Switch } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { showAlert, showSimpleAlert } from '../../services/alert';
import { GOLD, prettyPhone, tid } from './shared';

type Props = { orgId: string; view: any; colors: any; s: any; visible: boolean; onClose: () => void; onBought: () => Promise<void> };
const TYPES = [{ key: 'USER', label: 'Rep' }, { key: 'STORE', label: 'Store' }, { key: 'SHARED', label: 'Shared' }, { key: 'VA', label: 'VA' }];

export const AddNumberSheet = ({ orgId, view, colors, s, visible, onClose, onBought }: Props) => {
  const [type, setType] = useState('USER');
  const [userId, setUserId] = useState<string | null>(null);
  const [storeId, setStoreId] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<any[]>([]);
  const [areaCode, setAreaCode] = useState('');
  const [contains, setContains] = useState('');
  const [locality, setLocality] = useState('');
  const [caps, setCaps] = useState({ sms: true, mms: true, voice: true });
  const [results, setResults] = useState<any[] | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const people: any[] = view.people || [];
  const locations: any[] = view.locations || [];

  useEffect(() => {
    if (!visible) return;
    const q = new URLSearchParams();
    if (userId) q.set('user_id', userId);
    if (storeId) q.set('store_id', storeId);
    api.get(`/admin/organizations/${orgId}/twilio/numbers/suggest?${q.toString()}`).then(r => {
      setSuggestions(r.data.suggestions || []);
      if (!areaCode && r.data.suggestions?.[0]) setAreaCode(r.data.suggestions[0].area_code);
    }).catch(() => setSuggestions([]));
  }, [visible, userId, storeId, orgId]);

  const search = async () => {
    setBusy('search');
    try {
      const q = new URLSearchParams({ area_code: areaCode, contains, locality, sms: String(caps.sms), mms: String(caps.mms), voice: String(caps.voice), limit: '12' });
      const r = await api.get(`/admin/organizations/${orgId}/twilio/numbers/search?${q.toString()}`);
      setResults(r.data.numbers || []);
    } catch (e: any) { showSimpleAlert('Search', e?.response?.data?.detail || 'Twilio search failed.'); }
    finally { setBusy(null); }
  };
  const buy = (n: any) => {
    const who = userId ? people.find(p => p.id === userId)?.name : storeId ? locations.find(l => l.id === storeId)?.name : view.organization?.name;
    showAlert('Buy this number?', `${prettyPhone(n.phone_number)} (${n.locality || ''}${n.region ? `, ${n.region}` : ''}) for ${who}. About $${n.monthly_cost_usd}/month.${view.settings?.mode === 'dry_run' ? ' Dry run: nothing is bought in Twilio.' : ''}`, [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Buy & set up', onPress: async () => {
        setBusy(n.phone_number);
        try {
          await api.post(`/admin/organizations/${orgId}/twilio/numbers`, { phone_number: n.phone_number, number_type: type, assigned_user_id: type === 'USER' ? userId : null, location_id: storeId, voice_enabled: caps.voice });
          await onBought();
          setResults(null);
          onClose();
        } catch (e: any) { showSimpleAlert('Not bought', e?.response?.data?.detail || 'Twilio refused the purchase.'); }
        finally { setBusy(null); }
      } },
    ]);
  };

  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={onClose}>
      <View style={{ flex: 1, backgroundColor: 'rgba(0,0,0,0.55)', justifyContent: 'flex-end' }}>
        <View style={{ backgroundColor: colors.bg, borderTopLeftRadius: 20, borderTopRightRadius: 20, maxHeight: '92%', padding: 16 }} {...tid('add-number-sheet')}>
          <View style={{ flexDirection: 'row', alignItems: 'center', marginBottom: 10 }}>
            <Text style={{ flex: 1, fontSize: 18, fontWeight: '800', color: colors.text }}>Add phone number</Text>
            <TouchableOpacity onPress={onClose} hitSlop={10} {...tid('add-number-close')}><Ionicons name="close" size={22} color={colors.textSecondary} /></TouchableOpacity>
          </View>
          <ScrollView keyboardShouldPersistTaps="handled">
            <Text style={s.label}>Number type</Text>
            <View style={{ flexDirection: 'row', gap: 6, marginBottom: 12, flexWrap: 'wrap' }}>
              {TYPES.map(t => (
                <TouchableOpacity key={t.key} onPress={() => { setType(t.key); if (t.key !== 'USER') setUserId(null); }} style={[s.chip, { borderColor: type === t.key ? GOLD : colors.border, backgroundColor: type === t.key ? GOLD : colors.card }]} {...tid(`add-number-type-${t.key}`)}>
                  <Text style={{ fontSize: 12.5, fontWeight: '700', color: type === t.key ? '#000' : colors.text }}>{t.label}</Text>
                </TouchableOpacity>
              ))}
            </View>
            {type === 'USER' && (
              <>
                <Text style={s.label}>For which rep</Text>
                <View style={{ flexDirection: 'row', gap: 6, marginBottom: 12, flexWrap: 'wrap' }}>
                  {people.map(p => (
                    <TouchableOpacity key={p.id} onPress={() => { setUserId(p.id); if (p.store_id) setStoreId(p.store_id); }} style={[s.chip, { borderColor: userId === p.id ? GOLD : colors.border, backgroundColor: userId === p.id ? GOLD : colors.card }]} {...tid(`add-number-user-${p.id}`)}>
                      <Text style={{ fontSize: 12.5, fontWeight: '700', color: userId === p.id ? '#000' : colors.text }}>{p.name}{p.twilio_number ? ' ✓' : ''}</Text>
                    </TouchableOpacity>
                  ))}
                  {people.length === 0 && <Text style={s.hint}>No users on this organization yet.</Text>}
                </View>
              </>
            )}
            <Text style={s.label}>Location</Text>
            <View style={{ flexDirection: 'row', gap: 6, marginBottom: 12, flexWrap: 'wrap' }}>
              {locations.map(l => (
                <TouchableOpacity key={l.id} onPress={() => setStoreId(storeId === l.id ? null : l.id)} style={[s.chip, { borderColor: storeId === l.id ? GOLD : colors.border, backgroundColor: storeId === l.id ? GOLD : colors.card }]} {...tid(`add-number-location-${l.id}`)}>
                  <Text style={{ fontSize: 12.5, fontWeight: '700', color: storeId === l.id ? '#000' : colors.text }}>{l.name}</Text>
                </TouchableOpacity>
              ))}
            </View>
            {suggestions.length > 0 && (
              <>
                <Text style={s.label}>Suggested local area codes</Text>
                <View style={{ flexDirection: 'row', gap: 6, marginBottom: 12, flexWrap: 'wrap' }} {...tid('area-code-suggestions')}>
                  {suggestions.map(sg => (
                    <TouchableOpacity key={sg.area_code} onPress={() => setAreaCode(sg.area_code)} style={[s.chip, { borderColor: areaCode === sg.area_code ? GOLD : colors.border, backgroundColor: areaCode === sg.area_code ? GOLD : colors.card }]} {...tid(`area-code-${sg.area_code}`)}>
                      <Text style={{ fontSize: 12.5, fontWeight: '700', color: areaCode === sg.area_code ? '#000' : colors.text }}>{sg.area_code} <Text style={{ fontWeight: '400', opacity: 0.7 }}>· {sg.reason}</Text></Text>
                    </TouchableOpacity>
                  ))}
                </View>
              </>
            )}
            <View style={{ flexDirection: 'row', gap: 8 }}>
              <View style={{ flex: 1 }}><Text style={s.label}>Area code</Text><TextInput value={areaCode} onChangeText={v => setAreaCode(v.replace(/\D/g, '').slice(0, 3))} keyboardType="number-pad" placeholder="801" placeholderTextColor={colors.textTertiary} style={s.input} {...tid('search-area-code')} /></View>
              <View style={{ flex: 1 }}><Text style={s.label}>Contains</Text><TextInput value={contains} onChangeText={setContains} placeholder="digits" placeholderTextColor={colors.textTertiary} style={s.input} {...tid('search-contains')} /></View>
              <View style={{ flex: 1.4 }}><Text style={s.label}>City</Text><TextInput value={locality} onChangeText={setLocality} placeholder="optional" placeholderTextColor={colors.textTertiary} style={s.input} {...tid('search-locality')} /></View>
            </View>
            <View style={{ flexDirection: 'row', gap: 16, marginTop: 10, alignItems: 'center' }}>
              {(['sms', 'mms', 'voice'] as const).map(k => (
                <View key={k} style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                  <Switch value={caps[k]} onValueChange={v => setCaps(c => ({ ...c, [k]: v }))} trackColor={{ false: 'rgba(128,128,128,0.3)', true: '#34C75966' }} thumbColor={caps[k] ? '#34C759' : '#f4f3f4'} {...tid(`search-cap-${k}`)} />
                  <Text style={{ fontSize: 12.5, fontWeight: '700', color: colors.text }}>{k.toUpperCase()}</Text>
                </View>
              ))}
            </View>
            <TouchableOpacity onPress={search} disabled={busy === 'search'} style={[s.btn, { backgroundColor: GOLD, marginTop: 12 }]} {...tid('search-numbers-btn')}>
              {busy === 'search' ? <ActivityIndicator color="#000" /> : <><Ionicons name="search" size={16} color="#000" /><Text style={s.btnText}>Show available numbers</Text></>}
            </TouchableOpacity>
            {results !== null && (
              <View style={{ marginTop: 12 }} {...tid('search-results')}>
                {results.length === 0 && <Text style={s.hint} {...tid('search-empty')}>Nothing available with those filters. Try a nearby area code.</Text>}
                {results.map(n => (
                  <TouchableOpacity key={n.phone_number} onPress={() => buy(n)} disabled={!!busy} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 10, borderTopWidth: 1, borderTopColor: colors.border }} {...tid(`result-${n.phone_number.replace(/\D/g, '')}`)}>
                    <Ionicons name="call" size={16} color={GOLD} />
                    <View style={{ flex: 1 }}>
                      <Text style={{ fontSize: 15, fontWeight: '800', color: colors.text }}>{prettyPhone(n.phone_number)}</Text>
                      <Text style={{ fontSize: 12, color: colors.textTertiary }}>{[n.locality, n.region].filter(Boolean).join(', ')} · {['sms', 'mms', 'voice'].filter(k => n.capabilities?.[k]).join(' · ').toUpperCase()} · ${n.monthly_cost_usd}/mo</Text>
                    </View>
                    {busy === n.phone_number ? <ActivityIndicator color={GOLD} /> : <Text style={{ fontSize: 12.5, fontWeight: '800', color: GOLD }}>Buy</Text>}
                  </TouchableOpacity>
                ))}
              </View>
            )}
            <View style={{ height: 30 }} />
          </ScrollView>
        </View>
      </View>
    </Modal>
  );
};
