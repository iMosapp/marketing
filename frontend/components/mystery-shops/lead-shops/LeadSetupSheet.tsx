import React, { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity } from 'react-native';
import api from '../../../services/api';
import { useToast } from '../../common/Toast';
import { Sheet, Field, Label, Chip, GoldButton, tid } from '../shared';
import { CHANNELS, type LeadSetup, type LeadProcess } from './shared';

type Props = { visible: boolean; onClose: () => void; colors: any; clientId: string; setup: LeadSetup | null; onSaved: (s: LeadSetup) => void };
const NUM: [keyof LeadProcess, string][] = [['first_call_min', 'FIRST CALL WITHIN (MIN)'], ['first_text_min', 'FIRST TEXT WITHIN (MIN)'], ['first_email_min', 'FIRST EMAIL WITHIN (MIN)'], ['day1_calls', 'CALL ATTEMPTS ON DAY ONE'], ['follow_up_days', 'FOLLOW UP FOR (DAYS)']];

// The store's CRM intake address + the response process they promised. Every lead shop on this client is graded against it.
export const LeadSetupSheet = ({ visible, onClose, colors, clientId, setup, onSaved }: Props) => {
  const { showToast } = useToast();
  const [email, setEmail] = useState('');
  const [site, setSite] = useState('');
  const [nums, setNums] = useState<Record<string, string>>({});
  const [channels, setChannels] = useState<string[]>(['call', 'text', 'email']);
  const [must, setMust] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (!visible || !setup) return;
    const p = setup.lead_process;
    setEmail(setup.lead_email || ''); setSite(setup.lead_website || ''); setChannels(p.channels); setMust((p.must || []).join('\n'));
    setNums(Object.fromEntries(NUM.map(([k]) => [k, String(p[k] ?? '')])));
  }, [visible, setup]);
  const toggle = (k: string) => setChannels(c => (c.includes(k) ? (c.length > 1 ? c.filter(x => x !== k) : c) : [...c, k]));
  const save = async () => {
    setBusy(true);
    try {
      const lead_process = { ...Object.fromEntries(NUM.map(([k]) => [k, parseInt(nums[k] || '0', 10) || 0])), channels, must: must.split('\n').map(s => s.trim()).filter(Boolean) };
      const r = await api.put(`/lead-shops/setup/${clientId}`, { lead_email: email, lead_website: site, lead_process });
      onSaved(r.data); onClose(); showToast('Lead shop setup saved', 'success');
    } catch (e: any) { showToast(e?.response?.data?.detail || 'Could not save', 'error'); }
    finally { setBusy(false); }
  };
  return (
    <Sheet visible={visible} onClose={onClose} title="Lead shop setup" colors={colors} testID="lead-setup-sheet" footer={<GoldButton label="Save" onPress={save} busy={busy} testID="lead-setup-save" />}>
      <Text style={{ fontSize: 13, color: colors.textSecondary, lineHeight: 18 }}>The lead lands in the store's CRM like any other internet lead. Nobody there knows it is a shop. Fill in where their leads go and the process they promised, and every lead shop is graded against it.</Text>
      <Field label="CRM LEAD INTAKE EMAIL (WHERE THEIR ADF/XML LEADS GO)" value={email} onChange={setEmail} colors={colors} placeholder="leads@dealership.crm.com" keyboardType="email-address" autoCapitalize="none" testID="lead-setup-email" />
      <Field label="STORE WEBSITE (FOR THE MANUAL FORM OPTION)" value={site} onChange={setSite} colors={colors} placeholder="https://www.dealership.com" keyboardType="url" autoCapitalize="none" testID="lead-setup-website" />
      <View style={{ gap: 6 }}>
        <Label t="CHANNELS THE STORE PROMISED TO USE" colors={colors} />
        <View style={{ flexDirection: 'row', gap: 8 }}>{CHANNELS.map(c => <Chip key={c.key} label={c.label} active={channels.includes(c.key)} onPress={() => toggle(c.key)} colors={colors} testID={`lead-setup-channel-${c.key}`} />)}</View>
      </View>
      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 10 }}>
        {NUM.map(([k, l]) => <View key={k} style={{ flexBasis: '47%', flexGrow: 1 }}><Field label={l} value={nums[k] || ''} onChange={(v: string) => setNums(n => ({ ...n, [k]: v.replace(/\D/g, '') }))} colors={colors} keyboardType="number-pad" testID={`lead-setup-${k}`} /></View>)}
      </View>
      <Field label="MUST DO ON EVERY LEAD (ONE PER LINE)" value={must} onChange={setMust} colors={colors} multiline placeholder={'Answer the question the lead asked\nOffer a specific appointment time'} testID="lead-setup-must" />
      {setup && <TouchableOpacity onPress={() => { const p = setup.defaults; setChannels(p.channels); setMust(p.must.join('\n')); setNums(Object.fromEntries(NUM.map(([k]) => [k, String(p[k])]))); }} {...tid('lead-setup-defaults')}><Text style={{ fontSize: 12.5, fontWeight: '700', color: colors.textSecondary }}>Reset the process to our defaults</Text></TouchableOpacity>}
    </Sheet>
  );
};
