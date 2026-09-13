import React, { useEffect, useState } from 'react';
import { View, Text, Switch, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { useToast } from '../common/Toast';
import { Sheet, Field, Label, Chip, GoldButton, DEPTS, GOLD, tid, type Challenge } from './shared';

type Props = { visible: boolean; onClose: () => void; colors: any; onStarted: (clientId: string, callId: string) => void };
const blank = { name: '', phone: '', department: 'sales', title: '', store_name: '', vehicle: '', script_id: null as string | null, text: true };

// Shop anyone on the spot: no client, no proposal. The call lands in the built-in "Quick shops" bucket.
export const DemoShopSheet = ({ visible, onClose, colors, onStarted }: Props) => {
  const { showToast } = useToast();
  const [f, setF] = useState(blank);
  const [challenges, setChallenges] = useState<Challenge[]>([]);
  const [busy, setBusy] = useState(false);
  const set = (k: string, v: any) => setF(x => ({ ...x, [k]: v }));

  useEffect(() => { if (visible) { setF(blank); api.get('/shop-clients/demo/challenges').then(r => setChallenges(r.data.challenges)).catch(() => {}); } }, [visible]);
  useEffect(() => { set('script_id', null); }, [f.department]);

  const digits = f.phone.replace(/\D/g, '');
  const ready = f.name.trim().length >= 2 && digits.length >= 10;
  const pool = challenges.filter(c => c.department === f.department);

  const go = async () => {
    setBusy(true);
    try {
      const r = await api.post('/shop-clients/demo', { name: f.name.trim(), phone: f.phone, department: f.department, title: f.title, store_name: f.store_name, vehicle: f.vehicle, script_id: f.script_id, text_scorecard: f.text });
      showToast(`Calling ${f.name.trim().split(' ')[0]} now`, 'success'); onClose(); onStarted(r.data.client_id, r.data.call.id);
    } catch (e: any) { showToast(e?.response?.data?.detail || 'Could not place the call', 'error'); }
    finally { setBusy(false); }
  };

  return (
    <Sheet visible={visible} onClose={onClose} title="Quick shop" colors={colors} testID="demo-sheet"
      footer={<GoldButton label={ready ? `Call ${f.name.trim().split(' ')[0] || 'them'} now` : 'Name and cell number first'} onPress={go} busy={busy} disabled={!ready} testID="demo-call" icon="call" />}>
      <Text style={{ fontSize: 13.5, color: colors.textSecondary, lineHeight: 19 }}>A real practice call, no client account needed. Their phone rings within seconds. Jessi announces the practice call and whether it's inbound or outbound; they press 1 or say ready and the AI customer comes on. The call is recorded and graded, and if you leave the text on they get their scorecard by SMS a minute after hanging up. Everything lands in Quick shops.</Text>
      <View style={{ flexDirection: 'row', gap: 10 }}>
        <View style={{ flex: 1.2 }}><Field label="WHO" value={f.name} onChange={(v: string) => set('name', v)} colors={colors} placeholder="Sam Seller" testID="demo-name" /></View>
        <View style={{ flex: 1 }}><Field label="CELL" value={f.phone} onChange={(v: string) => set('phone', v)} colors={colors} placeholder="(801) 555-0100" keyboardType="phone-pad" testID="demo-phone" /></View>
      </View>
      <View style={{ gap: 6 }}>
        <Label t="DEPARTMENT" colors={colors} />
        <View style={{ flexDirection: 'row', gap: 8 }}>{DEPTS.map(d => <Chip key={d.key} label={d.label} active={f.department === d.key} onPress={() => set('department', d.key)} colors={colors} testID={`demo-dept-${d.key}`} />)}</View>
      </View>
      <View style={{ flexDirection: 'row', gap: 10 }}>
        <View style={{ flex: 1 }}><Field label="THEIR STORE (OPTIONAL)" value={f.store_name} onChange={(v: string) => set('store_name', v)} colors={colors} placeholder="LHM Jeep" testID="demo-store" /></View>
        <View style={{ flex: 1 }}><Field label="TITLE (OPTIONAL)" value={f.title} onChange={(v: string) => set('title', v)} colors={colors} placeholder="Sales consultant" testID="demo-title" /></View>
      </View>
      <Field label="A VEHICLE THE SHOPPER CAN MENTION (OPTIONAL)" value={f.vehicle} onChange={(v: string) => set('vehicle', v)} colors={colors} placeholder="2024 Jeep Grand Cherokee L Limited" testID="demo-vehicle" />
      <View style={{ gap: 6 }}>
        <Label t="CHALLENGE" colors={colors} />
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>
          <Chip label="Surprise me" small active={!f.script_id} onPress={() => set('script_id', null)} colors={colors} testID="demo-challenge-random" />
          {pool.map(c => <Chip key={c.id} label={c.title.replace(/^(Shopper|Service caller):\s*/i, '')} small active={f.script_id === c.id} onPress={() => set('script_id', c.id)} colors={colors} testID={`demo-challenge-${c.id}`} />)}
        </View>
      </View>
      <TouchableOpacity onPress={() => set('text', !f.text)} activeOpacity={0.8} style={{ flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: colors.card, borderRadius: 12, padding: 12, borderWidth: 1, borderColor: colors.border }} {...tid('demo-text-row')}>
        <Ionicons name="chatbubble-ellipses" size={18} color={GOLD} />
        <View style={{ flex: 1 }}><Text style={{ fontSize: 14, fontWeight: '700', color: colors.text }}>Text them their scorecard after</Text><Text style={{ fontSize: 12, color: colors.textSecondary }}>Score, top win, top fix and a link to the full scorecard with the recording. Sent from your number.</Text></View>
        <Switch value={f.text} onValueChange={(v) => set('text', v)} {...tid('demo-text-toggle')} />
      </TouchableOpacity>
    </Sheet>
  );
};
