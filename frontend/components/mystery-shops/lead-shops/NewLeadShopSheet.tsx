import React, { useEffect, useState } from 'react';
import { View, Text } from 'react-native';
import api from '../../../services/api';
import { useToast } from '../../common/Toast';
import { Sheet, Field, Label, Chip, GoldButton, deptsOfClient, stripTitlePrefix, tid, type Client, type Challenge } from '../shared';
import { type LeadSetup, type LeadShop } from './shared';

type Props = { visible: boolean; onClose: () => void; colors: any; client: Client; setup: LeadSetup | null; onCreated: (shop: LeadShop) => void };

// One covert lead: persona + reachable cell/email, pushed to the CRM (ADF) or handed to you as an identity card for the store's web form.
export const NewLeadShopSheet = ({ visible, onClose, colors, client, setup, onCreated }: Props) => {
  const { showToast } = useToast();
  const depts = deptsOfClient(client);
  const blank = { method: 'adf' as 'adf' | 'manual', department: depts[0]?.key || 'sales', offering: '', source_name: 'Website', window_hours: 72, script_id: null as string | null, notes: '' };
  const [f, setF] = useState(blank);
  const [challenges, setChallenges] = useState<Challenge[] | null>(null);
  const [busy, setBusy] = useState(false);
  const set = (k: string, v: any) => setF(x => ({ ...x, [k]: v }));
  useEffect(() => { if (visible) { setF(blank); api.get(`/shop-clients/${client.id}/challenges`).then(r => setChallenges(r.data.challenges)).catch(() => setChallenges([])); } }, [visible]);
  useEffect(() => { set('script_id', null); }, [f.department]);
  const pool = (challenges || []).filter(c => c.department === f.department);
  const hasEmail = !!setup?.lead_email;
  const blocked = !setup?.email_ready ? 'Email receiving is not set up on the server yet (INBOUND_EMAIL_DOMAIN)' : f.method === 'adf' && !hasEmail ? "Add the store's CRM lead email in Lead shop setup first" : challenges !== null && pool.length === 0 ? 'No challenge for this department yet' : '';
  const go = async () => {
    setBusy(true);
    try {
      const r = await api.post('/lead-shops', { client_id: client.id, ...f, offering: f.offering.trim(), source_name: f.source_name.trim() });
      showToast(f.method === 'adf' ? `Lead sent to ${setup?.lead_email}` : 'Identity ready, submit their form', 'success'); onClose(); onCreated(r.data);
    } catch (e: any) { showToast(e?.response?.data?.detail || 'Could not create the lead shop', 'error'); }
    finally { setBusy(false); }
  };
  return (
    <Sheet visible={visible} onClose={onClose} title="Send a lead" colors={colors} testID="lead-new-sheet"
      footer={<GoldButton label={blocked || (f.method === 'adf' ? 'Send the lead to their CRM' : 'Create the identity')} onPress={go} busy={busy} disabled={!!blocked} icon={f.method === 'adf' ? 'paper-plane' : 'id-card'} testID="lead-new-submit" />}>
      <Text style={{ fontSize: 13, color: colors.textSecondary, lineHeight: 18 }} {...tid('lead-new-how')}>A brand new lead with a real cell number and email lands at {client.name}. Whoever calls gets the AI shopper in persona, texts and emails get real replies, and the clock runs on every channel. Nobody at the store knows.</Text>
      <View style={{ gap: 6 }}>
        <Label t="HOW IT GETS TO THE STORE" colors={colors} />
        <View style={{ flexDirection: 'row', gap: 8 }}>
          <Chip label="ADF email to their CRM" active={f.method === 'adf'} onPress={() => set('method', 'adf')} colors={colors} testID="lead-new-method-adf" />
          <Chip label="I'll submit their web form" active={f.method === 'manual'} onPress={() => set('method', 'manual')} colors={colors} testID="lead-new-method-manual" />
        </View>
        <Text style={{ fontSize: 12, color: colors.textSecondary, lineHeight: 16 }}>{f.method === 'adf' ? (hasEmail ? `Goes straight to ${setup?.lead_email} as an ADF/XML internet lead. The clock starts the second it is sent.` : 'Needs the CRM lead intake email under Lead shop setup.') : 'You get a name, cell, email and message to type into the store\'s own website form. Tap "I submitted it" and the clock starts.'}</Text>
      </View>
      <View style={{ gap: 6 }}>
        <Label t="DEPARTMENT" colors={colors} />
        <View style={{ flexDirection: 'row', gap: 8, flexWrap: 'wrap' }}>{depts.map(d => <Chip key={d.key} label={d.label} active={f.department === d.key} onPress={() => set('department', d.key)} colors={colors} testID={`lead-new-dept-${d.key}`} />)}</View>
      </View>
      <Field label={`WHAT THE LEAD IS ASKING ABOUT (${(client.offering?.label || 'vehicle').toUpperCase()}, OPTIONAL)`} value={f.offering} onChange={(v: string) => set('offering', v)} colors={colors} placeholder={client.offerings?.[0] || client.offering?.hint || '2022 Jeep Grand Cherokee'} testID="lead-new-offering" />
      <Field label="LEAD SOURCE THE STORE SEES" value={f.source_name} onChange={(v: string) => set('source_name', v)} colors={colors} placeholder="Website, Cars.com, Autotrader" testID="lead-new-source" />
      <View style={{ gap: 6 }}>
        <Label t="HOW LONG WE WAIT FOR THEM" colors={colors} />
        <View style={{ flexDirection: 'row', gap: 8 }}>{(setup?.windows || [{ hours: 24, label: '24 hours' }, { hours: 72, label: '3 days' }, { hours: 168, label: '7 days' }]).map(w => <Chip key={w.hours} label={w.label} active={f.window_hours === w.hours} onPress={() => set('window_hours', w.hours)} colors={colors} testID={`lead-new-window-${w.hours}`} />)}</View>
      </View>
      <View style={{ gap: 6 }}>
        <Label t="SHOPPER PERSONA" colors={colors} />
        {challenges !== null && pool.length === 0 ? <Text style={{ fontSize: 12.5, color: colors.textSecondary }} {...tid('lead-new-no-challenges')}>No challenges for this department yet. Add some under Challenges first.</Text> : (
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>
            <Chip label="Surprise me" small active={!f.script_id} onPress={() => set('script_id', null)} colors={colors} testID="lead-new-challenge-random" />
            {pool.map(c => <Chip key={c.id} label={stripTitlePrefix(c.title)} small active={f.script_id === c.id} onPress={() => set('script_id', c.id)} colors={colors} testID={`lead-new-challenge-${c.id}`} />)}
          </View>
        )}
      </View>
      <Field label="NOTES (ONLY YOU SEE THESE)" value={f.notes} onChange={(v: string) => set('notes', v)} colors={colors} placeholder="GM asked us to test the weekend BDC" testID="lead-new-notes" />
    </Sheet>
  );
};
