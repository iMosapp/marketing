import React, { useEffect, useState } from 'react';
import { View, Text, Switch, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { useToast } from '../common/Toast';
import { Sheet, Field, Label, Chip, GoldButton, GOLD, tid, industries, industryOf, deptsFor, loadIndustries, stripTitlePrefix, type Challenge } from './shared';

type Props = { visible: boolean; onClose: () => void; colors: any; onStarted: (clientId: string, callId: string) => void };
const blank = { name: '', phone: '', email: '', industry: 'automotive', department: 'sales', title: '', store_name: '', vehicle: '', script_id: null as string | null, text: true, channel: 'call' as 'call' | 'text' | 'email' };

// Shop anyone on the spot: no client, no proposal. Pick the industry, the department, and the call lands in the built-in "Quick shops" bucket.
export const DemoShopSheet = ({ visible, onClose, colors, onStarted }: Props) => {
  const { showToast } = useToast();
  const [f, setF] = useState(blank);
  const [challenges, setChallenges] = useState<Challenge[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [, setTick] = useState(0);
  const set = (k: string, v: any) => { setError(''); setF(x => ({ ...x, [k]: v })); };
  const ind = industryOf(f.industry);
  const depts = deptsFor(f.industry);

  useEffect(() => { if (visible) { setF(blank); setError(''); loadIndustries().then(() => setTick(t => t + 1)); } }, [visible]);
  useEffect(() => {
    if (!visible) return;
    setChallenges(null); set('script_id', null);
    api.get('/shop-clients/demo/challenges', { params: { industry: f.industry } }).then(r => setChallenges(r.data.challenges)).catch(() => setChallenges([]));
  }, [visible, f.industry]);
  useEffect(() => { set('script_id', null); }, [f.department]);
  const pickIndustry = (key: string) => setF(x => ({ ...x, industry: key, department: deptsFor(key)[0]?.key || x.department, script_id: null }));

  const digits = f.phone.replace(/\D/g, '');
  const ready = f.name.trim().length >= 2 && digits.length >= 10 && (f.channel !== 'email' || /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(f.email.trim()));
  const pool = (challenges || []).filter(c => c.department === f.department);
  const rep = (depts.find(d => d.key === f.department)?.rep || 'a rep').replace(/^(a|an) /, '');

  const go = async () => {
    setBusy(true); setError('');
    try {
      const r = await api.post('/shop-clients/demo', { name: f.name.trim(), phone: f.phone, email: f.email.trim(), industry: f.industry, department: f.department, title: f.title, store_name: f.store_name, vehicle: f.vehicle, script_id: f.script_id, text_scorecard: f.text, channel: f.channel });
      showToast(`${f.channel === 'text' ? 'Texting' : f.channel === 'email' ? 'Emailing' : 'Calling'} ${f.name.trim().split(' ')[0]} now`, 'success'); onClose(); onStarted(r.data.client_id, r.data.call.id);
    } catch (e: any) {
      const msg = e?.response?.data?.detail || (!e?.response ? 'No connection to the server, try again in a moment' : f.channel === 'text' ? 'Could not send the text' : f.channel === 'email' ? 'Could not send the email' : 'Could not place the call');
      setError(typeof msg === 'string' ? msg : JSON.stringify(msg));
      showToast(typeof msg === 'string' ? msg : 'Could not start the shop', 'error');
    }
    finally { setBusy(false); }
  };

  return (
    <Sheet visible={visible} onClose={onClose} title="Quick shop" colors={colors} testID="demo-sheet" error={error}
      footer={<GoldButton label={ready ? `${f.channel === 'text' ? 'Text' : f.channel === 'email' ? 'Email' : 'Call'} ${f.name.trim().split(' ')[0] || 'them'} now` : f.channel === 'email' ? 'Name, cell and email first' : 'Name and cell number first'} onPress={go} busy={busy} disabled={!ready || challenges !== null && pool.length === 0} testID="demo-call" icon={f.channel === 'text' ? 'chatbubbles' : f.channel === 'email' ? 'mail' : 'call'} />}>
      <View style={{ gap: 6 }}>
        <Label t="HOW" colors={colors} />
        <View style={{ flexDirection: 'row', gap: 8 }}>
          <Chip label="Call" active={f.channel === 'call'} onPress={() => set('channel', 'call')} colors={colors} testID="demo-channel-call" />
          <Chip label="Text" active={f.channel === 'text'} onPress={() => set('channel', 'text')} colors={colors} testID="demo-channel-text" />
          <Chip label="Email" active={f.channel === 'email'} onPress={() => set('channel', 'email')} colors={colors} testID="demo-channel-email" />
        </View>
      </View>
      <Text style={{ fontSize: 13.5, color: colors.textSecondary, lineHeight: 19 }} {...tid('demo-how-text')}>{f.channel === 'email'
        ? `A real internet lead by email, no client account needed. The AI ${ind.customer} emails them the second you tap, like someone who found them online, and keeps the thread going as they reply (a real shopper takes minutes to answer). They have 24 hours to reply to each email; when the shopper wraps up, or you tap End & grade, the thread is graded: first reply within 30 minutes and every reply under 2 hours by the clock, quality by the scorecard. No reply at all scores 0%. Leave the text on and they get their scorecard by SMS right after.`
        : f.channel === 'text'
        ? `A real text lead, no client account needed. The AI ${ind.customer} texts them from the shop number the second you tap, like someone who found them online, and keeps the thread going as they reply (it takes a human minute to answer). They have 4 hours to reply to each text; when the shopper wraps up, or you tap End & grade, the thread is graded: reply speed by the clock, quality by the scorecard. No reply at all scores 0%. Leave the text on and they get their scorecard by SMS right after.`
        : `A real practice call, no client account needed. It dials the second you tap, any hour of any day; nothing is held for business hours or put on a schedule. Jessi announces the practice call and whether it's inbound or outbound; they press 1 or say ready and the AI ${ind.customer} comes on. The call is recorded and graded, and if you leave the text on they get their scorecard by SMS a minute after hanging up. If they don't pick up or press 2, the shop waits in Quick shops for you to tap Try again.`}</Text>
      <View style={{ flexDirection: 'row', gap: 10 }}>
        <View style={{ flex: 1.2 }}><Field label="WHO" value={f.name} onChange={(v: string) => set('name', v)} colors={colors} placeholder="Sam Seller" testID="demo-name" /></View>
        <View style={{ flex: 1 }}><Field label="CELL" value={f.phone} onChange={(v: string) => set('phone', v)} colors={colors} placeholder="(801) 555-0100" keyboardType="phone-pad" testID="demo-phone" /></View>
      </View>
      {f.channel === 'email' && <Field label="WORK EMAIL (WHERE THE SHOPPER WRITES)" value={f.email} onChange={(v: string) => set('email', v)} colors={colors} placeholder="sam@dealership.com" keyboardType="email-address" testID="demo-email" />}
      <View style={{ gap: 6 }}>
        <Label t="INDUSTRY" colors={colors} />
        <View style={{ flexDirection: 'row', gap: 6, flexWrap: 'wrap' }}>{industries().map(i => <Chip key={i.key} label={i.label} small active={f.industry === i.key} onPress={() => pickIndustry(i.key)} colors={colors} testID={`demo-industry-${i.key}`} />)}</View>
      </View>
      <View style={{ gap: 6 }}>
        <Label t="DEPARTMENT" colors={colors} />
        <View style={{ flexDirection: 'row', gap: 8, flexWrap: 'wrap' }}>{depts.map(d => <Chip key={d.key} label={d.label} active={f.department === d.key} onPress={() => set('department', d.key)} colors={colors} testID={`demo-dept-${d.key}`} />)}</View>
      </View>
      <View style={{ flexDirection: 'row', gap: 10 }}>
        <View style={{ flex: 1 }}><Field label={`THEIR ${ind.business.toUpperCase()} (OPTIONAL)`} value={f.store_name} onChange={(v: string) => set('store_name', v)} colors={colors} placeholder={f.industry === 'automotive' ? 'LHM Jeep' : `The ${ind.business} name`} testID="demo-store" /></View>
        <View style={{ flex: 1 }}><Field label="TITLE (OPTIONAL)" value={f.title} onChange={(v: string) => set('title', v)} colors={colors} placeholder={rep.replace(/^\w/, c => c.toUpperCase())} testID="demo-title" /></View>
      </View>
      <Field label={`A ${ind.offering.label.toUpperCase()} THE ${ind.customer.toUpperCase()} CAN MENTION (OPTIONAL)`} value={f.vehicle} onChange={(v: string) => set('vehicle', v)} colors={colors} placeholder={ind.offering.hint} testID="demo-vehicle" />
      <View style={{ gap: 6 }}>
        <Label t="CHALLENGE" colors={colors} />
        {challenges !== null && pool.length === 0 ? (
          <Text style={{ fontSize: 12.5, color: colors.textSecondary, lineHeight: 17 }} {...tid('demo-no-challenges')}>No {ind.label.toLowerCase()} challenges for this department yet. Open the Challenge library, pick {ind.label}, and let Jessi write the starters first.</Text>
        ) : (
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>
            <Chip label="Surprise me" small active={!f.script_id} onPress={() => set('script_id', null)} colors={colors} testID="demo-challenge-random" />
            {pool.map(c => <Chip key={c.id} label={stripTitlePrefix(c.title)} small active={f.script_id === c.id} onPress={() => set('script_id', c.id)} colors={colors} testID={`demo-challenge-${c.id}`} />)}
          </View>
        )}
      </View>
      <TouchableOpacity onPress={() => set('text', !f.text)} activeOpacity={0.8} style={{ flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: colors.card, borderRadius: 12, padding: 12, borderWidth: 1, borderColor: colors.border }} {...tid('demo-text-row')}>
        <Ionicons name="chatbubble-ellipses" size={18} color={GOLD} />
        <View style={{ flex: 1 }}><Text style={{ fontSize: 14, fontWeight: '700', color: colors.text }}>Text them their scorecard after</Text><Text style={{ fontSize: 12, color: colors.textSecondary }}>Score, top win, top fix and a link to the full scorecard with the {f.channel === 'text' ? 'thread' : 'recording'}. Sent from the shop number.</Text></View>
        <Switch value={f.text} onValueChange={(v) => set('text', v)} {...tid('demo-text-toggle')} />
      </TouchableOpacity>
    </Sheet>
  );
};
