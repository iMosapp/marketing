import React, { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../../services/api';
import { useToast } from '../../common/Toast';
import { Sheet, Field, Label, Chip, GoldButton, deptsOfClient, stripTitlePrefix, GOLD, tid, type Client, type Challenge } from '../shared';
import { WINDOW_OPTS, type Campaign, type JourneyOptions, type Modes } from './shared';
import { ModesEditor } from './ModesEditor';

type Props = { visible: boolean; onClose: () => void; colors: any; client: Client; opts: JourneyOptions | null; onCreated: (c: Campaign) => void };

const Stepper = ({ value, onChange, min, max, colors, testID }: { value: number; onChange: (n: number) => void; min: number; max: number; colors: any; testID: string }) => (
  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 14 }} {...tid(testID)}>
    <TouchableOpacity onPress={() => onChange(Math.max(min, value - 1))} hitSlop={8} style={{ width: 36, height: 36, borderRadius: 18, borderWidth: 1, borderColor: colors.border, alignItems: 'center', justifyContent: 'center' }} {...tid(`${testID}-minus`)}><Ionicons name="remove" size={18} color={colors.text} /></TouchableOpacity>
    <Text style={{ fontSize: 22, fontWeight: '800', color: colors.text, minWidth: 28, textAlign: 'center' }} {...tid(`${testID}-value`)}>{value}</Text>
    <TouchableOpacity onPress={() => onChange(Math.min(max, value + 1))} hitSlop={8} style={{ width: 36, height: 36, borderRadius: 18, borderWidth: 1, borderColor: colors.border, alignItems: 'center', justifyContent: 'center' }} {...tid(`${testID}-plus`)}><Ionicons name="add" size={18} color={colors.text} /></TouchableOpacity>
  </View>
);

// A campaign is drafted here; nothing reaches the store until it is armed from the campaign screen.
export const NewCampaignSheet = ({ visible, onClose, colors, client, opts, onCreated }: Props) => {
  const { showToast } = useToast();
  const depts = deptsOfClient(client);
  const defaults: Modes = opts?.default_modes || { email: 'approve', sms: 'approve', voice: 'voicemail' };
  const blank = { name: '', department: depts[0]?.key || 'sales', offering: '', method: 'manual' as 'adf' | 'manual', source_name: 'Website', window_hours: 168, count: 3, script_id: null as string | null, notes: '', modes: defaults };
  const [f, setF] = useState(blank);
  const [challenges, setChallenges] = useState<Challenge[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const set = (k: string, v: any) => setF(x => ({ ...x, [k]: v }));
  useEffect(() => { if (visible) { setF({ ...blank, modes: defaults }); setErr(''); api.get(`/shop-clients/${client.id}/challenges`).then(r => setChallenges(r.data.challenges)).catch(() => setChallenges([])); } }, [visible]);
  useEffect(() => { set('script_id', null); }, [f.department]);
  const pool = (challenges || []).filter(c => c.department === f.department);
  const blocked = opts && !opts.email_ready ? 'Email receiving is not set up on the server yet (INBOUND_EMAIL_DOMAIN)' : challenges !== null && pool.length === 0 ? 'No challenge for this department yet' : '';
  const go = async () => {
    setBusy(true); setErr('');
    try {
      const r = await api.post('/journeys', { client_id: client.id, ...f, offering: f.offering.trim(), source_name: f.source_name.trim(), name: f.name.trim() });
      showToast(`${r.data.counts.total} identit${r.data.counts.total === 1 ? 'y' : 'ies'} drafted`, 'success'); onClose(); onCreated(r.data);
    } catch (e: any) { setErr(e?.response?.data?.detail || 'Could not create the campaign'); }
    finally { setBusy(false); }
  };
  return (
    <Sheet visible={visible} onClose={onClose} title="New journey campaign" colors={colors} testID="journey-new-sheet" error={err}
      footer={<GoldButton label={blocked || `Draft ${f.count} identit${f.count === 1 ? 'y' : 'ies'}`} onPress={go} busy={busy} disabled={!!blocked} icon="people" testID="journey-new-submit" />}>
      <Text style={{ fontSize: 13, color: colors.textSecondary, lineHeight: 18 }} {...tid('journey-new-how')}>Jessi writes each customer: a name, story, buying timeline, personality, the questions they still need answered. You can edit any of it. Nothing reaches {client.name} until you arm the campaign.</Text>
      <Field label="CAMPAIGN NAME (OPTIONAL)" value={f.name} onChange={(v: string) => set('name', v)} colors={colors} placeholder={`${depts.find(d => d.key === f.department)?.label || 'Sales'} journey · weekend BDC`} testID="journey-new-name" />
      <View style={{ gap: 6 }}>
        <Label t="DEPARTMENT" colors={colors} />
        <View style={{ flexDirection: 'row', gap: 8, flexWrap: 'wrap' }}>{depts.map(d => <Chip key={d.key} label={d.label} active={f.department === d.key} onPress={() => set('department', d.key)} colors={colors} testID={`journey-new-dept-${d.key}`} />)}</View>
      </View>
      <View style={{ gap: 6 }}>
        <Label t="HOW MANY VIRTUAL CUSTOMERS" colors={colors} />
        <Stepper value={f.count} onChange={(n) => set('count', n)} min={1} max={opts?.max_identities || 10} colors={colors} testID="journey-new-count" />
        <Text style={{ fontSize: 12, color: colors.textSecondary }}>Each one needs a free shopper number when you arm the campaign{opts?.pool ? ` (${opts.pool.available} ready now, ${opts.pool.cap} max)` : ''}.</Text>
      </View>
      <Field label={`WHAT THEY ARE ASKING ABOUT (${(client.offering?.label || 'vehicle').toUpperCase()}, OPTIONAL)`} value={f.offering} onChange={(v: string) => set('offering', v)} colors={colors} placeholder={client.offerings?.[0] || client.offering?.hint || '2022 Jeep Grand Cherokee'} testID="journey-new-offering" />
      <View style={{ gap: 6 }}>
        <Label t="HOW THE LEADS REACH THE STORE" colors={colors} />
        <View style={{ flexDirection: 'row', gap: 8 }}>
          <Chip label="I'll submit their web form" active={f.method === 'manual'} onPress={() => set('method', 'manual')} colors={colors} testID="journey-new-method-manual" />
          <Chip label="ADF email to their CRM" active={f.method === 'adf'} onPress={() => set('method', 'adf')} colors={colors} testID="journey-new-method-adf" />
        </View>
        <Text style={{ fontSize: 12, color: colors.textSecondary, lineHeight: 16 }}>{f.method === 'manual' ? 'Each identity gets a card you type into the store\'s website form; the clock starts when you confirm it was submitted.' : 'Each lead is emailed to the CRM intake address under Lead shop setup the moment the campaign is armed.'}</Text>
      </View>
      <Field label="LEAD SOURCE THE STORE SEES" value={f.source_name} onChange={(v: string) => set('source_name', v)} colors={colors} placeholder="Website, Cars.com, Autotrader" testID="journey-new-source" />
      <View style={{ gap: 6 }}>
        <Label t="HOW LONG WE WATCH" colors={colors} />
        <View style={{ flexDirection: 'row', gap: 8, flexWrap: 'wrap' }}>{(opts?.windows || WINDOW_OPTS).map(w => <Chip key={w.hours} label={w.label} active={f.window_hours === w.hours} onPress={() => set('window_hours', w.hours)} colors={colors} testID={`journey-new-window-${w.hours}`} />)}</View>
      </View>
      <ModesEditor modes={f.modes} onChange={(m) => set('modes', m)} colors={colors} prefix="journey-new-mode" />
      <View style={{ gap: 6 }}>
        <Label t="SCENARIO" colors={colors} />
        {challenges !== null && pool.length === 0 ? <Text style={{ fontSize: 12.5, color: colors.textSecondary }} {...tid('journey-new-no-challenges')}>No challenges for this department yet. Add some under Challenges first.</Text> : (
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>
            <Chip label="Mix them up" small active={!f.script_id} onPress={() => set('script_id', null)} colors={colors} testID="journey-new-challenge-random" />
            {pool.map(c => <Chip key={c.id} label={stripTitlePrefix(c.title)} small active={f.script_id === c.id} onPress={() => set('script_id', c.id)} colors={colors} testID={`journey-new-challenge-${c.id}`} />)}
          </View>
        )}
        <Text style={{ fontSize: 12, color: colors.textSecondary }}>Mix = every identity draws a different challenge persona from the library.</Text>
      </View>
      <Field label="NOTES FOR JESSI (SHAPES THE IDENTITIES)" value={f.notes} onChange={(v: string) => set('notes', v)} colors={colors} multiline placeholder="Weekend shoppers, two of them with a trade, one asking about financing" testID="journey-new-notes" />
      <View style={{ flexDirection: 'row', gap: 8, alignItems: 'flex-start' }}><Ionicons name="shield-checkmark" size={16} color={GOLD} style={{ marginTop: 1 }} /><Text style={{ flex: 1, fontSize: 12, color: colors.textSecondary, lineHeight: 16 }}>Every identity carries the hard rule: never confirm an appointment, never commit to buy. Nobody at the store ends up holding a car for a customer who does not exist.</Text></View>
    </Sheet>
  );
};
