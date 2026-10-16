import React, { useEffect, useState } from 'react';
import { View, Text, ScrollView, useWindowDimensions } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { SheetShell, Chip } from './Sheet';
import { Touch, whenLabel, GOLD, tid } from './utils';
import { TrioCard, TrioPerson, TrioPreview } from './TrioCard';
import { ScanContactPicker } from '../scan/ScanContactPicker';

type Props = { userId: string; campaignId: string; touches: Touch[]; aiEnabled: boolean; colors: any; onClose: () => void };
const errText = (e: any, d: string) => e?.response?.data?.detail || d;

// Customer Preview Trio: one step written for three real customers side by side. Examples only; nothing is saved or sent.
export const CustomerPreviewSheet = ({ userId, campaignId, touches, aiEnabled, colors, onClose }: Props) => {
  const { width } = useWindowDimensions();
  const wide = width >= 900;
  const [step, setStep] = useState(0);
  const [people, setPeople] = useState<TrioPerson[]>([]);
  const [previews, setPreviews] = useState<Record<string, TrioPreview>>({});
  const [loading, setLoading] = useState<string[]>([]);
  const [swapAt, setSwapAt] = useState<number | null>(null);
  const [note, setNote] = useState('');

  const write = async (ids: string[], s = step) => {
    const t = touches[s];
    if (!t || !ids.length) return;
    setLoading(l => [...l, ...ids]);
    try {
      const r = await api.post(`/campaign-preview/${userId}/${campaignId}`, { contact_ids: ids, step_context: t.step_context || '', message_template: t.message || '', channel: t.channel || 'sms', ai_enabled: aiEnabled }, { timeout: 120000 });
      setPreviews(p => ({ ...p, ...Object.fromEntries((r.data.previews || []).map((x: TrioPreview) => [x.contact_id, x])) }));
    } catch (e) {
      setPreviews(p => ({ ...p, ...Object.fromEntries(ids.map(id => [id, { contact_id: id, name: '', message: '', knew: p[id]?.knew || [], used: [], error: errText(e, 'Could not write the preview') }])) }));
    } finally { setLoading(l => l.filter(x => !ids.includes(x))); }
  };

  useEffect(() => {
    api.get(`/campaign-preview/${userId}/${campaignId}/candidates`).then(r => {
      const list: TrioPerson[] = r.data.contacts || [];
      setPeople(list);
      if (!list.length) setNote('No customers to preview yet. Add a few contacts first.');
      write(list.map(p => p.id), 0);
    }).catch(e => setNote(errText(e, 'Could not load customers')));
  }, []);

  const pickStep = (i: number) => { setStep(i); setPreviews(p => Object.fromEntries(Object.entries(p).map(([k, v]) => [k, { ...v, message: '', used: [] }]))); write(people.map(p => p.id), i); };
  const swap = (c: { id: string; name: string }) => {
    if (swapAt === null) return;
    if (people.some(p => p.id === c.id)) { setSwapAt(null); return; }
    setPeople(ps => ps.map((p, i) => (i === swapAt ? { id: c.id, name: c.name, why: 'Your pick' } : p)));
    setSwapAt(null);
    write([c.id]);
  };
  const cardW = wide ? undefined : Math.min(340, width * 0.82);
  const cards = people.map((p, i) => (
    <TrioCard key={p.id} index={i} person={p} preview={previews[p.id]} loading={loading.includes(p.id)} colors={colors} width={cardW}
      onSwap={() => setSwapAt(i)} onRetry={() => write([p.id])} />
  ));

  return (
    <SheetShell title="Preview for 3 customers" subtitle="Same step, three real customers. Examples only: nothing is saved or sent." onClose={onClose} testId="trio-sheet" colors={colors}>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8 }} {...tid('trio-steps')}>
        {touches.map((t, i) => <Chip key={t.id || i} label={`${i + 1} · ${whenLabel(t)}`} active={i === step} colors={colors} testId={`trio-step-${i}`} onPress={() => pickStep(i)} />)}
      </ScrollView>
      {!!touches[step]?.step_context && <Text style={{ fontSize: 12.5, color: colors.textSecondary, lineHeight: 17 }} {...tid('trio-goal')}>Goal: {touches[step].step_context}</Text>}
      {!aiEnabled && (
        <View style={{ flexDirection: 'row', gap: 8, backgroundColor: colors.card, borderRadius: 12, padding: 10 }} {...tid('trio-static-note')}>
          <Ionicons name="information-circle-outline" size={16} color={GOLD} />
          <Text style={{ flex: 1, fontSize: 12.5, color: colors.textSecondary, lineHeight: 17 }}>This plan sends texts exactly as written, so everyone gets the same words. Turn on "Jessi personalizes each text" to see each one written for them.</Text>
        </View>
      )}
      {!!note && <Text style={{ fontSize: 13, color: colors.textSecondary }} {...tid('trio-note')}>{note}</Text>}
      {wide ? <View style={{ flexDirection: 'row', gap: 12, alignItems: 'flex-start' }}>{cards}</View>
        : <ScrollView horizontal snapToInterval={(cardW || 0) + 12} decelerationRate="fast" showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 12 }}>{cards}</ScrollView>}
      {swapAt !== null && (
        <View style={{ backgroundColor: colors.card, borderRadius: 14, borderWidth: 1, borderColor: GOLD + '55', padding: 12 }} {...tid('trio-swap-panel')}>
          <ScanContactPicker userId={userId} matches={[]} selected={null} onSelect={swap} colors={colors} label={`SWAP OUT ${(people[swapAt]?.name || '').toUpperCase()}`} />
        </View>
      )}
      <Text style={{ fontSize: 11.5, color: colors.textTertiary, lineHeight: 16 }}>The real text is written fresh when it's due, from what Jessi knows then, in the voice of the rep who owns that customer.</Text>
    </SheetShell>
  );
};
