/** Provision Twilio / Sync Twilio, provisioning state, actionable error, history (super admin), subaccount controls. */
import React, { useState } from 'react';
import { View, Text, TouchableOpacity, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { showAlert, showSimpleAlert } from '../../services/alert';
import { GOLD, Pill, PROV_COLOR, tid, when } from './shared';

type Props = { orgId: string; view: any; colors: any; s: any; onChanged: (v: any) => void };

export const ProvisioningCard = ({ orgId, view, colors, s, onChanged }: Props) => {
  const [busy, setBusy] = useState<string | null>(null);
  const [showHist, setShowHist] = useState(false);
  const p = view.provisioning || {};
  const rec = view.record || {};
  const full = !!view.full;
  const color = PROV_COLOR[p.status] || '#8E8E93';

  const call = async (what: 'provision' | 'sync', body?: any) => {
    setBusy(what);
    try {
      const r = await api.post(`/admin/organizations/${orgId}/twilio/${what}`, body || {});
      onChanged(r.data);
    } catch (e: any) { showSimpleAlert('Twilio', e?.response?.data?.detail || 'Something went wrong.'); }
    finally { setBusy(null); }
  };
  const provision = () => {
    if (p.status === 'NOT_STARTED') {
      showAlert('Provision Twilio?', `Creates a Twilio subaccount for ${view.organization?.name} (${view.settings?.mode === 'dry_run' ? 'dry run: nothing is created in Twilio' : 'live'}), links the compliance record and walks the steps that can run now. Steps that wait on Twilio approval resume automatically.`,
        [{ text: 'Cancel', style: 'cancel' }, { text: 'Provision', onPress: () => call('provision') }]);
    } else call('provision');
  };
  const subaccount = (status: 'suspended' | 'active') => showAlert(status === 'suspended' ? 'Suspend subaccount?' : 'Reactivate subaccount?',
    status === 'suspended' ? 'Every number on this organization stops sending and receiving until reactivated.' : 'Messaging resumes on every number.',
    [{ text: 'Cancel', style: 'cancel' }, { text: status === 'suspended' ? 'Suspend' : 'Reactivate', style: status === 'suspended' ? 'destructive' : 'default', onPress: async () => {
      setBusy('sub');
      try { const r = await api.post(`/admin/organizations/${orgId}/twilio/subaccount`, { status }); onChanged(r.data); }
      catch (e: any) { showSimpleAlert('Twilio', e?.response?.data?.detail || 'Could not change the subaccount.'); }
      finally { setBusy(null); }
    } }]);

  return (
    <View style={s.card} {...tid('provisioning-card')}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
        <Text style={[s.cardTitle, { flex: 1, marginBottom: 0 }]}>Provisioning</Text>
        <Pill label={p.label || p.status} color={color} testID="provisioning-status" />
      </View>
      {!!p.step && p.status !== 'NOT_STARTED' && <Text style={[s.hint, { marginTop: 6 }]} {...tid('provisioning-step')}>Current step: {p.step}{rec.last_synced_at ? ` · synced ${when(rec.last_synced_at)}` : ''}</Text>}
      {!!p.error && (
        <View style={{ marginTop: 10, backgroundColor: `${color}15`, borderRadius: 10, padding: 10, flexDirection: 'row', gap: 8 }} {...tid('provisioning-error')}>
          <Ionicons name={p.status === 'ERROR' ? 'alert-circle' : 'information-circle'} size={16} color={color} />
          <Text style={{ flex: 1, fontSize: 13, color: colors.text, lineHeight: 18 }}>{p.error}</Text>
        </View>
      )}
      {full && (
        <>
          <View style={{ flexDirection: 'row', gap: 8, marginTop: 12 }}>
            <TouchableOpacity onPress={provision} disabled={!!busy} style={[s.btn, { backgroundColor: GOLD }]} {...tid('provision-twilio-btn')}>
              {busy === 'provision' ? <ActivityIndicator color="#000" /> : <><Ionicons name="rocket" size={16} color="#000" /><Text style={s.btnText}>{p.status === 'NOT_STARTED' ? 'Provision Twilio' : p.status === 'READY' ? 'Re-run provisioning' : 'Retry / continue'}</Text></>}
            </TouchableOpacity>
            <TouchableOpacity onPress={() => call('sync')} disabled={!!busy} style={[s.btn, { backgroundColor: colors.bg, borderWidth: 1, borderColor: colors.border }]} {...tid('sync-twilio-btn')}>
              {busy === 'sync' ? <ActivityIndicator color={colors.text} /> : <><Ionicons name="refresh" size={16} color={colors.text} /><Text style={[s.btnText, { color: colors.text }]}>Sync Twilio</Text></>}
            </TouchableOpacity>
          </View>
          {!!rec.subaccount_sid && (
            <View style={{ marginTop: 12, paddingTop: 10, borderTopWidth: 1, borderTopColor: colors.border }} {...tid('subaccount-block')}>
              <Text style={s.label}>Subaccount</Text>
              <Text style={{ fontSize: 13, color: colors.text }}>{rec.subaccount_friendly_name}</Text>
              <Text style={s.mono} {...tid('subaccount-sid')}>{rec.subaccount_sid} · {rec.subaccount_status || 'active'}</Text>
              <View style={{ flexDirection: 'row', gap: 8, marginTop: 8 }}>
                {rec.subaccount_status !== 'suspended' ? (
                  <TouchableOpacity onPress={() => subaccount('suspended')} disabled={!!busy} style={[s.chip, { borderColor: '#FF9500', backgroundColor: '#FF950015' }]} {...tid('subaccount-suspend-btn')}>
                    <Text style={{ fontSize: 12.5, fontWeight: '700', color: '#FF9500' }}>Suspend subaccount</Text>
                  </TouchableOpacity>
                ) : (
                  <TouchableOpacity onPress={() => subaccount('active')} disabled={!!busy} style={[s.chip, { borderColor: '#34C759', backgroundColor: '#34C75915' }]} {...tid('subaccount-activate-btn')}>
                    <Text style={{ fontSize: 12.5, fontWeight: '700', color: '#34C759' }}>Reactivate subaccount</Text>
                  </TouchableOpacity>
                )}
              </View>
            </View>
          )}
          {(p.history || []).length > 0 && (
            <View style={{ marginTop: 12 }}>
              <TouchableOpacity onPress={() => setShowHist(v => !v)} style={{ flexDirection: 'row', alignItems: 'center' }} {...tid('provisioning-history-toggle')}>
                <Text style={{ flex: 1, fontSize: 13, fontWeight: '700', color: colors.textSecondary }}>Provisioning history ({p.history.length})</Text>
                <Ionicons name={showHist ? 'chevron-up' : 'chevron-down'} size={16} color={colors.textSecondary} />
              </TouchableOpacity>
              {showHist && [...p.history].reverse().map((h: any, i: number) => (
                <Text key={i} style={{ fontSize: 12, color: colors.textSecondary, paddingTop: 6 }} {...tid(`provisioning-history-${i}`)}>{when(h.at)} · {h.step} · {h.status}{h.note ? ` · ${h.note}` : ''}</Text>
              ))}
            </View>
          )}
        </>
      )}
    </View>
  );
};
