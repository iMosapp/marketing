import React, { useState } from 'react';
import { View, Text, TouchableOpacity, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { useToast } from '../common/Toast';
import { Sheet, Field, Label, Chip, GoldButton, DEPTS, deptLabel, GOLD, GREEN, PURPLE, tid, type Challenge, type ChallengeDraft } from './shared';

type Scope = { clientId?: string; clientName?: string };
type Props = { visible: boolean; onClose: () => void; colors: any; scope?: Scope; onSaved: (c: Challenge) => void; onEditDraft: (d: ChallengeDraft) => void };
type Draft = ChallengeDraft & { savedAs?: 'library' | 'client' };

const EXAMPLES: Record<string, string> = {
  sales: 'Customer saw a used Tacoma online, has a trade with negative equity, wants to know if you can get them out of their loan and what the payment would be. Skeptical, has been burned before.',
  service: 'Customer hears a squeal from the front brakes on their 2021 Explorer, has a trip this weekend, wants it looked at tomorrow and asks for a loaner. Worried about cost.',
  parts: 'Customer calling parts for a front brake rotor for a 2019 F-150, wants to know if it is in stock and the price, gets impatient when put on hold.',
  rental: 'Customer whose car is in the body shop, insurance is covering a rental, needs something today with room for a car seat, nervous about the deposit.',
};

// Describe the situation, pick a department, get 1 to 5 fully written challenges back. Save the keepers, edit the almost-right ones.
export const GeneratorSheet = ({ visible, onClose, colors, scope, onSaved, onEditDraft }: Props) => {
  const { showToast } = useToast();
  const [department, setDepartment] = useState('sales');
  const [scenario, setScenario] = useState('');
  const [count, setCount] = useState(1);
  const [busy, setBusy] = useState(false);
  const [drafts, setDrafts] = useState<Draft[] | null>(null);
  const [saving, setSaving] = useState<number | null>(null);

  const generate = async () => {
    setBusy(true); setDrafts(null);
    try { const r = await api.post('/shop-clients/challenges/generate', { department, scenario, count, client_id: scope?.clientId }); setDrafts(r.data.drafts.map((d: ChallengeDraft) => ({ ...d, generated_from: r.data.scenario }))); }
    catch (e: any) { showToast(e?.response?.data?.detail || 'Jessi could not write that one', 'error'); }
    finally { setBusy(false); }
  };
  const save = async (i: number, where: 'library' | 'client') => {
    const d = drafts![i];
    setSaving(i);
    try {
      const r = where === 'client' && scope?.clientId ? await api.post(`/shop-clients/${scope.clientId}/challenges`, d) : await api.post('/shop-clients/challenges', d);
      setDrafts(ds => ds!.map((x, j) => (j === i ? { ...x, savedAs: where } : x))); onSaved(r.data); showToast(where === 'client' ? `Added to ${scope?.clientName}'s pool` : 'Added to the library', 'success');
    } catch (e: any) { showToast(e?.response?.data?.detail || 'Could not save', 'error'); }
    finally { setSaving(null); }
  };
  const reset = () => { setDrafts(null); setScenario(''); };

  return (
    <Sheet visible={visible} onClose={() => { onClose(); }} title="Have Jessi write a challenge" colors={colors} testID="generator-sheet"
      footer={drafts ? <GoldButton label="Write another scenario" onPress={reset} outline testID="generator-again" icon="refresh" /> : <GoldButton label={busy ? 'Jessi is writing…' : count > 1 ? `Draft ${count} challenges` : 'Draft it'} onPress={generate} busy={busy} disabled={scenario.trim().length < 15} testID="generator-go" icon="sparkles" />}>
      {!drafts && (
        <>
          <View style={{ gap: 8 }}><Label t="DEPARTMENT" colors={colors} /><View style={{ flexDirection: 'row', gap: 8, flexWrap: 'wrap' }}>{DEPTS.map(d => <Chip key={d.key} label={d.label} active={department === d.key} onPress={() => setDepartment(d.key)} colors={colors} testID={`generator-dept-${d.key}`} />)}</View></View>
          <Field label="THE SCENARIO, IN YOUR WORDS" value={scenario} onChange={setScenario} colors={colors} multiline placeholder={EXAMPLES[department]} testID="generator-scenario" />
          <TouchableOpacity onPress={() => setScenario(EXAMPLES[department])} {...tid('generator-example')}><Text style={{ fontSize: 12.5, fontWeight: '700', color: GOLD }}>Use the example above</Text></TouchableOpacity>
          <View style={{ gap: 8 }}><Label t="HOW MANY VARIATIONS" colors={colors} /><View style={{ flexDirection: 'row', gap: 6 }}>{[1, 2, 3, 4, 5].map(n => <Chip key={n} label={String(n)} small active={count === n} onPress={() => setCount(n)} colors={colors} testID={`generator-count-${n}`} />)}</View></View>
          <Text style={{ fontSize: 12.5, color: colors.textSecondary, lineHeight: 17 }}>Jessi writes the shopper (who they are, how they open, what they push back with), what a great rep does, the graded points and a few curveballs. Nothing is saved until you say so.</Text>
          {busy && <View style={{ alignItems: 'center', gap: 8, paddingVertical: 20 }}><ActivityIndicator color={GOLD} /><Text style={{ fontSize: 13, color: colors.textSecondary }}>Writing {count > 1 ? `${count} ${deptLabel(department).toLowerCase()} challenges` : `a ${deptLabel(department).toLowerCase()} challenge`}, about 20 seconds…</Text></View>}
        </>
      )}
      {drafts && drafts.map((d, i) => (
        <View key={i} style={{ backgroundColor: colors.card, borderRadius: 16, borderWidth: 1, borderColor: d.savedAs ? GREEN + '88' : colors.border, padding: 14, gap: 8 }} {...tid(`draft-${i}`)}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
            <Text style={{ flex: 1, fontSize: 15.5, fontWeight: '800', color: colors.text }} {...tid(`draft-title-${i}`)}>{d.title}</Text>
            {d.savedAs && <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }}><Ionicons name="checkmark-circle" size={16} color={GREEN} /><Text style={{ fontSize: 12, fontWeight: '800', color: GREEN }}>{d.savedAs === 'client' ? 'Saved for client' : 'In the library'}</Text></View>}
          </View>
          <Text style={{ fontSize: 12.5, fontWeight: '800', color: GOLD }}>{deptLabel(d.department).toUpperCase()} · {d.runtime}</Text>
          {!!d.purpose && <Text style={{ fontSize: 13.5, color: colors.textSecondary, fontStyle: 'italic', lineHeight: 19 }}>{d.purpose}</Text>}
          <View style={{ backgroundColor: colors.bg, borderRadius: 12, padding: 10, gap: 3 }}>
            <Text style={{ fontSize: 12.5, fontWeight: '800', color: colors.text }}>{d.persona?.name} <Text style={{ fontWeight: '500', color: colors.textSecondary }}>· {d.persona?.voice} voice</Text></Text>
            <Text style={{ fontSize: 13, color: colors.textSecondary, lineHeight: 18 }}>{d.persona?.summary}</Text>
            <Text style={{ fontSize: 13, color: colors.text, lineHeight: 18 }}>Opens with: "{d.persona?.opening_line}"</Text>
          </View>
          <View style={{ gap: 2 }}><Label t={`GRADED POINTS · ${d.success_points?.length || 0}`} colors={colors} />{(d.success_points || []).map((p, j) => <Text key={j} style={{ fontSize: 13, color: colors.text }}>• {p}</Text>)}</View>
          {!!d.curveballs?.length && <View style={{ gap: 2 }}><Label t="CURVEBALLS" colors={colors} />{d.curveballs.map((p, j) => <Text key={j} style={{ fontSize: 13, color: colors.textSecondary }}>• {p}</Text>)}</View>}
          {!d.savedAs && (
            <View style={{ flexDirection: 'row', gap: 8, flexWrap: 'wrap' }}>
              <TouchableOpacity onPress={() => save(i, 'library')} disabled={saving === i} style={{ flex: 1, minWidth: 140, height: 38, borderRadius: 12, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center' }} {...tid(`draft-save-library-${i}`)}><Text style={{ fontSize: 13, fontWeight: '800', color: '#111' }}>{saving === i ? 'Saving…' : 'Save to library'}</Text></TouchableOpacity>
              {!!scope?.clientId && <TouchableOpacity onPress={() => save(i, 'client')} disabled={saving === i} style={{ flex: 1, minWidth: 140, height: 38, borderRadius: 12, backgroundColor: PURPLE + '22', borderWidth: 1, borderColor: PURPLE, alignItems: 'center', justifyContent: 'center' }} {...tid(`draft-save-client-${i}`)}><Text style={{ fontSize: 13, fontWeight: '800', color: PURPLE }}>Only {scope.clientName}</Text></TouchableOpacity>}
              <TouchableOpacity onPress={() => onEditDraft(d)} style={{ height: 38, paddingHorizontal: 14, borderRadius: 12, borderWidth: 1, borderColor: colors.border, alignItems: 'center', justifyContent: 'center' }} {...tid(`draft-edit-${i}`)}><Text style={{ fontSize: 13, fontWeight: '800', color: colors.text }}>Edit first</Text></TouchableOpacity>
            </View>
          )}
        </View>
      ))}
    </Sheet>
  );
};
