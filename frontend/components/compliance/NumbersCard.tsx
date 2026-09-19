/** Store page: the numbers that text on the store's behalf, and what happens to them when the client cancels (release or port out). */
import React, { useState } from 'react';
import { View, Text, TouchableOpacity, ActivityIndicator, TextInput } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import * as Clipboard from 'expo-clipboard';
import api from '../../services/api';
import { showAlert, showSimpleAlert } from '../../services/alert';

const GOLD = '#C9A962';
const tid = (id: string) => ({ testID: id, dataSet: { testid: id } as any });
const pill = { height: 40, borderRadius: 12, paddingHorizontal: 14, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 6 } as const;
const STATUS: Record<string, { label: string; color: string }> = { active: { label: 'Active', color: '#34C759' }, port_requested: { label: 'Port requested', color: '#FF9500' }, ported: { label: 'Ported out', color: '#8E8E93' }, released: { label: 'Released', color: '#8E8E93' } };

type Props = { storeId: string; view: any; contact: any; colors: any; s: any; onChanged: () => Promise<void> };

export const NumbersCard = ({ storeId, view, contact, colors, s, onChanged }: Props) => {
  const [busy, setBusy] = useState<string | null>(null);
  const [exit, setExit] = useState(false);
  const [email, setEmail] = useState(contact?.email || '');
  const [phone, setPhone] = useState(contact?.phone || '');
  const numbers: any[] = view?.numbers || [];
  const live = numbers.filter(n => n.status !== 'released' && n.status !== 'ported');

  const setStatus = async (sid: string, status: string) => {
    setBusy(sid);
    try { await api.post(`/admin/compliance/${storeId}/numbers/${sid}/status`, { status }); await onChanged(); }
    catch (e: any) { showSimpleAlert('Error', e?.response?.data?.detail || 'Could not update.'); }
    finally { setBusy(null); }
  };
  const release = (n: any) => showAlert('Release this number?', `${n.number} goes back to Twilio for good: billing stops, ${n.owner || 'the pool'} loses it, and it cannot be ported afterwards. Only do this when the client is NOT moving the number to another carrier.`, [
    { text: 'Cancel', style: 'cancel' },
    { text: 'Release', style: 'destructive', onPress: async () => {
      setBusy(n.sid);
      try { await api.post(`/admin/compliance/${storeId}/numbers/${n.sid}/release`); await onChanged(); }
      catch (e: any) { showSimpleAlert('Error', e?.response?.data?.detail || 'Could not release.'); }
      finally { setBusy(null); }
    } },
  ]);
  const sendPacket = async () => {
    setBusy('packet');
    try {
      const r = await api.post(`/admin/compliance/${storeId}/portout/send`, { email, phone, channel: 'both' });
      const failed = (r.data.results || []).filter((x: any) => !x.ok);
      showSimpleAlert(failed.length ? 'Partly sent' : 'Packet sent', failed.length ? failed.map((x: any) => `${x.channel}: ${x.error || 'failed'}`).join('\n') : 'The client has the account number, PIN instructions and steps.');
      await onChanged();
    } catch (e: any) { showSimpleAlert('Not sent', e?.response?.data?.detail || 'Something went wrong.'); }
    finally { setBusy(null); }
  };
  const copy = async () => { await Clipboard.setStringAsync(view.portout_url); showSimpleAlert('Copied', 'Port-out packet link is on your clipboard.'); };

  return (
    <View style={s.card} {...tid('numbers-card')}>
      <View style={{ flexDirection: 'row', alignItems: 'center' }}>
        <Text style={[s.cardTitle, { flex: 1, marginBottom: 0 }]}>Numbers ({live.length})</Text>
        <TouchableOpacity onPress={() => setExit(v => !v)} style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }} {...tid('numbers-exit-toggle')}>
          <Ionicons name="exit-outline" size={15} color={colors.textSecondary} /><Text style={{ fontSize: 12.5, fontWeight: '700', color: colors.textSecondary }}>Client cancelling?</Text>
        </TouchableOpacity>
      </View>
      <Text style={s.hint}>Reps' Twilio numbers on this store. New numbers are attached to the profile and campaign automatically.</Text>
      {numbers.length === 0 && <Text style={[s.hint, { marginTop: 8 }]} {...tid('numbers-empty')}>No rep on this store has a Twilio number yet.</Text>}
      {numbers.map(n => {
        const st = STATUS[n.status] || STATUS.active;
        return (
          <View key={n.sid} style={{ paddingTop: 10, borderTopWidth: 1, borderTopColor: colors.border, marginTop: 8 }} {...tid(`number-row-${n.sid}`)}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
              <Text style={{ flex: 1, fontSize: 14, fontWeight: '700', color: colors.text }}>{n.number} <Text style={{ fontWeight: '400', color: colors.textTertiary }}>· {n.owner || 'pool'}</Text></Text>
              <Text style={{ fontSize: 12, fontWeight: '700', color: st.color }} {...tid(`number-status-${n.sid}`)}>{st.label}</Text>
            </View>
            {exit && n.status !== 'released' && (
              <View style={{ flexDirection: 'row', gap: 6, marginTop: 8, flexWrap: 'wrap' }}>
                {n.status !== 'ported' && ['active', 'port_requested', 'ported'].map(k => (
                  <TouchableOpacity key={k} onPress={() => setStatus(n.sid, k)} disabled={busy === n.sid || n.status === k} style={{ paddingHorizontal: 10, paddingVertical: 6, borderRadius: 12, backgroundColor: n.status === k ? GOLD : colors.bg, borderWidth: 1, borderColor: n.status === k ? GOLD : colors.border }} {...tid(`number-set-${k}-${n.sid}`)}>
                    <Text style={{ fontSize: 12, fontWeight: '700', color: n.status === k ? '#000' : colors.text }}>{STATUS[k].label}</Text>
                  </TouchableOpacity>
                ))}
                {n.status !== 'ported' && !n.gone && (
                  <TouchableOpacity onPress={() => release(n)} disabled={busy === n.sid} style={{ paddingHorizontal: 10, paddingVertical: 6, borderRadius: 12, backgroundColor: '#FF3B3015', borderWidth: 1, borderColor: '#FF3B30' }} {...tid(`number-release-${n.sid}`)}>
                    {busy === n.sid ? <ActivityIndicator size="small" color="#FF3B30" /> : <Text style={{ fontSize: 12, fontWeight: '700', color: '#FF3B30' }}>Release</Text>}
                  </TouchableOpacity>
                )}
              </View>
            )}
            {!!n.note && <Text style={[s.hint, { marginTop: 4 }]}>{n.note}</Text>}
          </View>
        );
      })}
      {exit && (
        <View style={{ marginTop: 12, backgroundColor: colors.bg, borderRadius: 12, padding: 12, gap: 8 }} {...tid('portout-panel')}>
          <Text style={{ fontSize: 14, fontWeight: '700', color: colors.text }}>Port-out packet</Text>
          <Text style={s.hint}>One page for the client with what their new carrier asks for: account number {view?.account_number || ''} (last 8 of our Twilio account), the port-out PIN, authorized name "Twilio, Inc.", service address, and the steps. Mark each number "Port requested" when they tell you the date, "Ported out" when it completes (we then pull it off the campaign). Use Release only when nobody is taking the number.</Text>
          <View style={{ flexDirection: 'row', gap: 8 }}>
            <TextInput value={email} onChangeText={setEmail} placeholder="client email" placeholderTextColor={colors.textTertiary} autoCapitalize="none" keyboardType="email-address" style={[s.input, { flex: 1.4 }]} {...tid('portout-email')} />
            <TextInput value={phone} onChangeText={setPhone} placeholder="client cell" placeholderTextColor={colors.textTertiary} keyboardType="phone-pad" style={[s.input, { flex: 1 }]} {...tid('portout-phone')} />
          </View>
          <View style={{ flexDirection: 'row', gap: 8 }}>
            <TouchableOpacity onPress={sendPacket} disabled={busy === 'packet'} style={[s.btn, { backgroundColor: GOLD }]} {...tid('portout-send-btn')}>
              {busy === 'packet' ? <ActivityIndicator color="#000" /> : <Text style={s.btnText}>Text + email the packet</Text>}
            </TouchableOpacity>
            <TouchableOpacity onPress={copy} style={[pill, { backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border }]} {...tid('portout-copy-btn')}>
              <Ionicons name="link" size={16} color={colors.textSecondary} />
            </TouchableOpacity>
          </View>
          {!!view?.portout?.last_sent_at && <Text style={s.hint} {...tid('portout-last-sent')}>Packet last sent {new Date(view.portout.last_sent_at).toLocaleString([], { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}</Text>}
        </View>
      )}
    </View>
  );
};
