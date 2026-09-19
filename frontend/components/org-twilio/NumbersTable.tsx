/** The organization's numbers: type, status, who holds it, location. Assign / reassign / unassign (admins), suspend / release (super, release confirmed twice). */
import React, { useState } from 'react';
import { View, Text, TouchableOpacity, ActivityIndicator, ScrollView } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { showAlert, showSimpleAlert } from '../../services/alert';
import { GOLD, NUM_STATUS, Pill, prettyPhone, tid } from './shared';

type Props = { orgId: string; view: any; colors: any; s: any; onAdd: () => void; onChanged: () => Promise<void> };

export const NumbersTable = ({ orgId, view, colors, s, onAdd, onChanged }: Props) => {
  const [busy, setBusy] = useState<string | null>(null);
  const [picker, setPicker] = useState<string | null>(null);
  const numbers: any[] = view.numbers || [];
  const people: any[] = view.people || [];
  const full = !!view.full;

  const act = async (n: any, what: string, body?: any) => {
    setBusy(n.id);
    try {
      await api.post(`/admin/organizations/${orgId}/twilio/numbers/${n.id}/${what}`, body || {});
      setPicker(null);
      await onChanged();
    } catch (e: any) { showSimpleAlert('Number', e?.response?.data?.detail || 'Something went wrong.'); }
    finally { setBusy(null); }
  };
  const release = (n: any) => showAlert('Release this number?', `${prettyPhone(n.phone_number)} goes back to Twilio for good: billing stops, ${n.owner_name || 'nobody'} loses it and it cannot be ported afterwards.`, [
    { text: 'Cancel', style: 'cancel' },
    { text: 'Release', style: 'destructive', onPress: () => showAlert('Are you sure?', 'This cannot be undone. Conversation history stays in IMOS.', [
      { text: 'Keep it', style: 'cancel' },
      { text: 'Yes, release', style: 'destructive', onPress: async () => {
        setBusy(n.id);
        try { await api.delete(`/admin/organizations/${orgId}/twilio/numbers/${n.id}?confirm=true`); await onChanged(); }
        catch (e: any) { showSimpleAlert('Number', e?.response?.data?.detail || 'Could not release.'); }
        finally { setBusy(null); }
      } }]) },
  ]);

  return (
    <View style={s.card} {...tid('numbers-table')}>
      <View style={{ flexDirection: 'row', alignItems: 'center' }}>
        <Text style={[s.cardTitle, { flex: 1, marginBottom: 0 }]}>Phone numbers ({numbers.length})</Text>
        <TouchableOpacity onPress={onAdd} style={[s.chip, { borderColor: GOLD, backgroundColor: GOLD, flexDirection: 'row', alignItems: 'center', gap: 4 }]} {...tid('add-number-btn')}>
          <Ionicons name="add" size={15} color="#000" /><Text style={{ fontSize: 12.5, fontWeight: '800', color: '#000' }}>Add number</Text>
        </TouchableOpacity>
      </View>
      <Text style={s.hint}>The organization owns every number. Assign one to a rep, take it back when they leave; their conversations stay with the history.</Text>
      {numbers.length === 0 && <Text style={[s.hint, { marginTop: 10 }]} {...tid('numbers-empty')}>No numbers yet. Add one to give a rep a local texting line.</Text>}
      {numbers.map(n => {
        const st = NUM_STATUS[n.status] || NUM_STATUS.AVAILABLE;
        const open = picker === n.id;
        return (
          <View key={n.id} style={{ paddingTop: 10, borderTopWidth: 1, borderTopColor: colors.border, marginTop: 10 }} {...tid(`number-row-${n.id}`)} dataSet={{ testid: `number-row-${n.id}`, status: n.status } as any}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
              <View style={{ flex: 1 }}>
                <Text style={{ fontSize: 15, fontWeight: '800', color: colors.text }} {...tid(`number-phone-${n.id}`)}>{prettyPhone(n.phone_number)}{n.dry_run ? ' · dry run' : ''}</Text>
                <Text style={{ fontSize: 12.5, color: colors.textSecondary }} {...tid(`number-owner-${n.id}`)}>
                  {n.type_label}{n.owner_name ? ` · ${n.owner_name}` : n.status === 'AVAILABLE' ? ' · unassigned' : ''}{n.location_name ? ` · ${n.location_name}` : ''}
                </Text>
                {full && <Text style={s.mono}>{n.twilio_phone_number_sid}{n.messaging_service_sid ? ` · ${n.messaging_service_sid}` : ' · not on a Messaging Service'}</Text>}
              </View>
              <Pill label={st.label} color={st.color} testID={`number-status-${n.id}`} />
            </View>
            <View style={{ flexDirection: 'row', gap: 6, marginTop: 8, flexWrap: 'wrap' }}>
              {n.status !== 'RELEASED' && n.status !== 'SUSPENDED' && (
                <TouchableOpacity onPress={() => setPicker(open ? null : n.id)} disabled={busy === n.id} style={[s.chip, { borderColor: GOLD, backgroundColor: open ? GOLD : colors.bg }]} {...tid(`number-assign-btn-${n.id}`)}>
                  <Text style={{ fontSize: 12, fontWeight: '700', color: open ? '#000' : colors.text }}>{n.assigned_user_id ? 'Reassign' : 'Assign to user'}</Text>
                </TouchableOpacity>
              )}
              {n.assigned_user_id && n.status === 'ASSIGNED' && (
                <TouchableOpacity onPress={() => act(n, 'unassign', { reason: 'admin' })} disabled={busy === n.id} style={[s.chip, { borderColor: colors.border, backgroundColor: colors.bg }]} {...tid(`number-unassign-btn-${n.id}`)}>
                  <Text style={{ fontSize: 12, fontWeight: '700', color: colors.text }}>Unassign</Text>
                </TouchableOpacity>
              )}
              {full && n.status !== 'RELEASED' && (n.status === 'SUSPENDED' ? (
                <TouchableOpacity onPress={() => act(n, 'reactivate')} disabled={busy === n.id} style={[s.chip, { borderColor: '#34C759', backgroundColor: '#34C75915' }]} {...tid(`number-reactivate-btn-${n.id}`)}>
                  <Text style={{ fontSize: 12, fontWeight: '700', color: '#34C759' }}>Reactivate</Text>
                </TouchableOpacity>
              ) : (
                <TouchableOpacity onPress={() => act(n, 'suspend', { reason: 'admin' })} disabled={busy === n.id} style={[s.chip, { borderColor: '#FF9500', backgroundColor: '#FF950015' }]} {...tid(`number-suspend-btn-${n.id}`)}>
                  <Text style={{ fontSize: 12, fontWeight: '700', color: '#FF9500' }}>Suspend</Text>
                </TouchableOpacity>
              ))}
              {full && n.status !== 'RELEASED' && (
                <TouchableOpacity onPress={() => release(n)} disabled={busy === n.id} style={[s.chip, { borderColor: '#FF3B30', backgroundColor: '#FF3B3015' }]} {...tid(`number-release-btn-${n.id}`)}>
                  {busy === n.id ? <ActivityIndicator size="small" color="#FF3B30" /> : <Text style={{ fontSize: 12, fontWeight: '700', color: '#FF3B30' }}>Release</Text>}
                </TouchableOpacity>
              )}
            </View>
            {open && (
              <View style={{ marginTop: 8, backgroundColor: colors.bg, borderRadius: 12, padding: 8, maxHeight: 220 }} {...tid(`assign-picker-${n.id}`)}>
                <ScrollView nestedScrollEnabled>
                  {people.length === 0 && <Text style={s.hint}>No users on this organization yet.</Text>}
                  {people.map(p => (
                    <TouchableOpacity key={p.id} onPress={() => act(n, 'assign', { user_id: p.id })} disabled={busy === n.id || p.id === n.assigned_user_id}
                      style={{ flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: colors.border, opacity: p.id === n.assigned_user_id ? 0.4 : 1 }} {...tid(`assign-user-${n.id}-${p.id}`)}>
                      <Ionicons name="person-circle" size={20} color={colors.textTertiary} />
                      <View style={{ flex: 1 }}>
                        <Text style={{ fontSize: 13.5, fontWeight: '700', color: colors.text }}>{p.name}</Text>
                        <Text style={{ fontSize: 11.5, color: colors.textTertiary }}>{p.role}{p.store_name ? ` · ${p.store_name}` : ''}{p.twilio_number ? ` · has ${prettyPhone(p.twilio_number)}` : ''}</Text>
                      </View>
                    </TouchableOpacity>
                  ))}
                </ScrollView>
              </View>
            )}
          </View>
        );
      })}
    </View>
  );
};
