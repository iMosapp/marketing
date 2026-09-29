import React, { useMemo, useState } from 'react';
import { View, Text, ScrollView, TouchableOpacity, TextInput, ActivityIndicator, useWindowDimensions } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { showConfirm } from '../../services/alert';
import { GOLD, GREEN, RED, tid } from './shared';

// The admin's editor for a read-along call guide: lines, questions, KPI checks and point values, saved as the guide everyone reads.
export type GuideBlock = { kind: 'say' | 'ask' | 'label' | 'note' | 'warn' | 'list'; text: string };
export type GuideSection = { title: string; blocks: GuideBlock[]; kpi: string[] };
export type GuideDoc = { title: string; kpi_chain: string[]; kpi_note: string; sections: GuideSection[]; scorecard: { label: string; points: number }[]; total: number; source: string; industry_label: string; department_label: string };
type Draft = { title: string; kpi_chain: string[]; kpi_note: string; sections: GuideSection[]; scorecard: { label: string; points: string }[] };

const C = { bg: '#0E0F12', card: '#17191E', border: '#262932', text: '#F4F1E8', dim: '#9A9A94', input: '#1F2229' };
const KINDS: { key: GuideBlock['kind']; label: string; hint: string }[] = [
  { key: 'say', label: 'Say', hint: 'a word-for-word line' }, { key: 'ask', label: 'Ask', hint: 'a question to ask' }, { key: 'label', label: 'Heading', hint: 'a small sub-heading' },
  { key: 'note', label: 'Note', hint: 'a coaching note' }, { key: 'warn', label: 'Never', hint: 'something never to do' }, { key: 'list', label: 'Check', hint: 'an item to confirm or document' },
];
const draftOf = (g: GuideDoc): Draft => ({ title: g.title || '', kpi_chain: [...(g.kpi_chain || [])], kpi_note: g.kpi_note || '', sections: (g.sections || []).map(s => ({ title: s.title, blocks: s.blocks.map(b => ({ ...b })), kpi: [...s.kpi] })), scorecard: (g.scorecard || []).map(r => ({ label: r.label, points: String(r.points) })) });
const move = <T,>(arr: T[], i: number, dir: -1 | 1): T[] => { const j = i + dir; if (j < 0 || j >= arr.length) return arr; const n = [...arr]; [n[i], n[j]] = [n[j], n[i]]; return n; };

const Inp = ({ value, onChange, placeholder, multiline, big, testID, style, keyboardType }: { value: string; onChange: (v: string) => void; placeholder?: string; multiline?: boolean; big?: boolean; testID: string; style?: any; keyboardType?: any }) => (
  <TextInput value={value} onChangeText={onChange} placeholder={placeholder} placeholderTextColor={C.dim} multiline={multiline} keyboardType={keyboardType}
    style={[{ backgroundColor: C.input, borderRadius: 10, borderWidth: 1, borderColor: C.border, paddingHorizontal: 12, paddingVertical: 9, color: C.text, fontSize: big ? 17 : 15, fontWeight: big ? '800' : '500', minHeight: multiline ? 64 : 42, textAlignVertical: 'top' }, style]} {...tid(testID)} />
);
const IconBtn = ({ icon, onPress, color = C.dim, testID, disabled }: { icon: any; onPress: () => void; color?: string; testID: string; disabled?: boolean }) => (
  <TouchableOpacity onPress={onPress} disabled={disabled} hitSlop={6} style={{ padding: 4, opacity: disabled ? 0.3 : 1 }} {...tid(testID)}><Ionicons name={icon} size={19} color={color} /></TouchableOpacity>
);
const AddBtn = ({ label, onPress, testID }: { label: string; onPress: () => void; testID: string }) => (
  <TouchableOpacity onPress={onPress} style={{ flexDirection: 'row', alignItems: 'center', gap: 6, alignSelf: 'flex-start', paddingVertical: 6, paddingHorizontal: 10, borderRadius: 10, borderWidth: 1, borderColor: GOLD + '77' }} {...tid(testID)}>
    <Ionicons name="add" size={16} color={GOLD} /><Text style={{ fontSize: 13, fontWeight: '800', color: GOLD }}>{label}</Text>
  </TouchableOpacity>
);
const Head = ({ t, sub }: { t: string; sub?: string }) => (
  <View style={{ gap: 2 }}><Text style={{ fontSize: 11, fontWeight: '800', color: GOLD, letterSpacing: 1.2 }}>{t}</Text>{!!sub && <Text style={{ fontSize: 12, color: C.dim, lineHeight: 17 }}>{sub}</Text>}</View>
);

export const GuideEditor = ({ guide, industry, department, onSaved, onClose }: { guide: GuideDoc; industry: string; department: string; onSaved: (g: GuideDoc) => void; onClose: () => void }) => {
  const { width } = useWindowDimensions();
  const [d, setD] = useState<Draft>(() => draftOf(guide));
  const [busy, setBusy] = useState<'' | 'save' | 'reset'>('');
  const [err, setErr] = useState('');
  const total = useMemo(() => d.scorecard.reduce((n, r) => n + (parseInt(r.points, 10) || 0), 0), [d.scorecard]);
  const pad = Math.max(16, (width - 720) / 2);
  const patch = (p: Partial<Draft>) => setD(prev => ({ ...prev, ...p }));
  const setSection = (i: number, s: GuideSection) => patch({ sections: d.sections.map((x, k) => (k === i ? s : x)) });

  const save = async () => {
    setBusy('save'); setErr('');
    try {
      const body = { ...d, scorecard: d.scorecard.map(r => ({ label: r.label, points: parseInt(r.points, 10) || 0 })) };
      const r = await api.put(`/shop-clients/guides/${industry}/${department}`, body);
      onSaved(r.data);
    } catch (e: any) { setErr(e?.response?.data?.detail || 'Could not save the guide'); }
    finally { setBusy(''); }
  };
  const reset = () => showConfirm('Throw away your edits?', guide.source === 'seed' || industry === 'equipment' ? 'The guide goes back to the original Customer Engagement Standard.' : 'Jessi writes a fresh guide from this department\u2019s scorecard. That takes about a minute.', async () => {
    setBusy('reset'); setErr('');
    try { const r = await api.post(`/shop-clients/guides/${industry}/${department}/reset`, {}, { timeout: 150000 }); onSaved(r.data); }
    catch (e: any) { setErr(e?.response?.data?.detail || 'Could not reset the guide'); }
    finally { setBusy(''); }
  }, undefined, 'Reset');

  return (
    <View style={{ flex: 1, backgroundColor: C.bg }} {...tid('guide-editor')}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingHorizontal: 14, paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: C.border }}>
        <TouchableOpacity onPress={onClose} hitSlop={10} {...tid('guide-edit-close')}><Ionicons name="close" size={26} color={C.dim} /></TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={{ fontSize: 12, fontWeight: '800', color: GOLD, letterSpacing: 1 }} numberOfLines={1}>EDIT {guide.department_label.toUpperCase()} GUIDE</Text>
          <Text style={{ fontSize: 12.5, color: total === 100 ? C.dim : RED }} numberOfLines={1} {...tid('guide-edit-total')}>{d.sections.length} sections · scorecard totals {total}{total === 100 ? '' : ' (aim for 100)'}</Text>
        </View>
        <TouchableOpacity onPress={save} disabled={!!busy} style={{ backgroundColor: GOLD, borderRadius: 12, paddingHorizontal: 16, height: 38, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 6, opacity: busy ? 0.6 : 1 }} {...tid('guide-edit-save')}>
          {busy === 'save' ? <ActivityIndicator color="#111" /> : <Ionicons name="checkmark" size={18} color="#111" />}<Text style={{ fontSize: 14, fontWeight: '900', color: '#111' }}>Save</Text>
        </TouchableOpacity>
      </View>
      <ScrollView contentContainerStyle={{ paddingHorizontal: pad, paddingTop: 16, paddingBottom: 80, gap: 18 }} keyboardShouldPersistTaps="handled" {...tid('guide-edit-scroll')}>
        {!!err && <View style={{ flexDirection: 'row', gap: 8, backgroundColor: RED + '1A', borderRadius: 10, padding: 10, borderWidth: 1, borderColor: RED + '66' }} {...tid('guide-edit-error')}><Ionicons name="alert-circle" size={16} color={RED} /><Text style={{ flex: 1, fontSize: 13, color: C.text }}>{err}</Text></View>}
        <View style={{ gap: 8 }}>
          <Head t="TITLE" />
          <Inp value={d.title} onChange={v => patch({ title: v })} placeholder="Kubota Sales Customer Engagement Standard" big testID="guide-edit-title" />
        </View>
        <ChainEditor chain={d.kpi_chain} note={d.kpi_note} onChain={v => patch({ kpi_chain: v })} onNote={v => patch({ kpi_note: v })} />
        <View style={{ gap: 10 }}>
          <Head t="SECTIONS" sub="In the order the call happens. Say = a line to read word for word, Ask = a question, Never = something to avoid. KPI checks are what the rep taps during the call." />
          {d.sections.map((s, i) => <SectionEditor key={i} i={i} s={s} count={d.sections.length} onChange={x => setSection(i, x)} onMove={dir => patch({ sections: move(d.sections, i, dir) })} onRemove={() => patch({ sections: d.sections.filter((_, k) => k !== i) })} />)}
          <AddBtn label="Add section" onPress={() => patch({ sections: [...d.sections, { title: '', blocks: [{ kind: 'say', text: '' }], kpi: [] }] })} testID="guide-edit-section-add" />
        </View>
        <ScorecardEditor rows={d.scorecard} total={total} onChange={rows => patch({ scorecard: rows })} />
        <TouchableOpacity onPress={reset} disabled={!!busy} style={{ height: 46, borderRadius: 14, borderWidth: 1, borderColor: RED, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 8, opacity: busy ? 0.6 : 1 }} {...tid('guide-edit-reset')}>
          {busy === 'reset' ? <ActivityIndicator color={RED} /> : <Ionicons name="refresh" size={16} color={RED} />}<Text style={{ fontSize: 15, fontWeight: '800', color: RED }}>{busy === 'reset' ? 'Rewriting…' : 'Reset to the original guide'}</Text>
        </TouchableOpacity>
      </ScrollView>
    </View>
  );
};

const ChainEditor = ({ chain, note, onChain, onNote }: { chain: string[]; note: string; onChain: (v: string[]) => void; onNote: (v: string) => void }) => (
  <View style={{ gap: 8 }}>
    <Head t="PRIMARY KPI" sub="The three to five words at the top of the guide, in order (DISCOVER, RECOMMEND, ADVANCE, REMEMBER)." />
    {chain.map((k, i) => (
      <View key={i} style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
        <Text style={{ width: 18, fontSize: 12, fontWeight: '800', color: C.dim }}>{i + 1}</Text>
        <View style={{ flex: 1 }}><Inp value={k} onChange={v => onChain(chain.map((x, j) => (j === i ? v : x)))} placeholder="DISCOVER" testID={`guide-edit-chain-${i}`} /></View>
        <IconBtn icon="close-circle" onPress={() => onChain(chain.filter((_, j) => j !== i))} color={RED} testID={`guide-edit-chain-${i}-remove`} />
      </View>
    ))}
    {chain.length < 5 && <AddBtn label="Add step" onPress={() => onChain([...chain, ''])} testID="guide-edit-chain-add" />}
    <Head t="ONE-LINE NOTE UNDER IT" />
    <Inp value={note} onChange={onNote} multiline placeholder="Every qualified conversation should accomplish four things…" testID="guide-edit-note" />
  </View>
);

const SectionEditor = ({ i, s, count, onChange, onMove, onRemove }: { i: number; s: GuideSection; count: number; onChange: (s: GuideSection) => void; onMove: (dir: -1 | 1) => void; onRemove: () => void }) => (
  <View style={{ backgroundColor: C.card, borderRadius: 16, borderWidth: 1, borderColor: C.border, padding: 14, gap: 10 }} {...tid(`guide-edit-section-${i}`)}>
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
      <View style={{ width: 26, height: 26, borderRadius: 13, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center' }}><Text style={{ fontWeight: '900', color: '#111', fontSize: 13 }}>{i + 1}</Text></View>
      <View style={{ flex: 1 }}><Inp value={s.title} onChange={v => onChange({ ...s, title: v })} placeholder="Section title (Open strong)" big testID={`guide-edit-section-${i}-title`} /></View>
      <IconBtn icon="chevron-up" onPress={() => onMove(-1)} disabled={i === 0} testID={`guide-edit-section-${i}-up`} />
      <IconBtn icon="chevron-down" onPress={() => onMove(1)} disabled={i === count - 1} testID={`guide-edit-section-${i}-down`} />
      <IconBtn icon="trash-outline" onPress={onRemove} color={RED} testID={`guide-edit-section-${i}-remove`} />
    </View>
    {s.blocks.map((b, j) => <BlockEditor key={j} i={i} j={j} b={b} count={s.blocks.length} onChange={x => onChange({ ...s, blocks: s.blocks.map((y, k) => (k === j ? x : y)) })} onMove={dir => onChange({ ...s, blocks: move(s.blocks, j, dir) })} onRemove={() => onChange({ ...s, blocks: s.blocks.filter((_, k) => k !== j) })} />)}
    <AddBtn label="Add line" onPress={() => onChange({ ...s, blocks: [...s.blocks, { kind: s.blocks[s.blocks.length - 1]?.kind === 'ask' ? 'ask' : 'say', text: '' }] })} testID={`guide-edit-section-${i}-block-add`} />
    <View style={{ gap: 6, marginTop: 4 }}>
      <Text style={{ fontSize: 11, fontWeight: '800', color: GOLD, letterSpacing: 1.2 }}>KPI CHECKS</Text>
      {s.kpi.map((k, j) => (
        <View key={j} style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
          <Ionicons name="checkmark-circle-outline" size={18} color={GREEN} />
          <View style={{ flex: 1 }}><Inp value={k} onChange={v => onChange({ ...s, kpi: s.kpi.map((x, m) => (m === j ? v : x)) })} placeholder="Get customer's name" testID={`guide-edit-section-${i}-kpi-${j}`} /></View>
          <IconBtn icon="close-circle" onPress={() => onChange({ ...s, kpi: s.kpi.filter((_, m) => m !== j) })} color={RED} testID={`guide-edit-section-${i}-kpi-${j}-remove`} />
        </View>
      ))}
      <AddBtn label="Add KPI check" onPress={() => onChange({ ...s, kpi: [...s.kpi, ''] })} testID={`guide-edit-section-${i}-kpi-add`} />
    </View>
  </View>
);

const BlockEditor = ({ i, j, b, count, onChange, onMove, onRemove }: { i: number; j: number; b: GuideBlock; count: number; onChange: (b: GuideBlock) => void; onMove: (dir: -1 | 1) => void; onRemove: () => void }) => (
  <View style={{ gap: 6, paddingTop: 8, borderTopWidth: 1, borderTopColor: C.border }} {...tid(`guide-edit-section-${i}-block-${j}`)}>
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4, flexWrap: 'wrap' }}>
      {KINDS.map(k => {
        const on = b.kind === k.key;
        return (
          <TouchableOpacity key={k.key} onPress={() => onChange({ ...b, kind: k.key })} style={{ paddingHorizontal: 9, height: 26, borderRadius: 13, backgroundColor: on ? (k.key === 'warn' ? RED : GOLD) : 'transparent', borderWidth: 1, borderColor: on ? 'transparent' : C.border, justifyContent: 'center' }} {...tid(`guide-edit-section-${i}-block-${j}-kind-${k.key}`)}>
            <Text style={{ fontSize: 11.5, fontWeight: '800', color: on ? '#111' : C.dim }}>{k.label}</Text>
          </TouchableOpacity>
        );
      })}
      <View style={{ flex: 1 }} />
      <IconBtn icon="chevron-up" onPress={() => onMove(-1)} disabled={j === 0} testID={`guide-edit-section-${i}-block-${j}-up`} />
      <IconBtn icon="chevron-down" onPress={() => onMove(1)} disabled={j === count - 1} testID={`guide-edit-section-${i}-block-${j}-down`} />
      <IconBtn icon="trash-outline" onPress={onRemove} color={RED} testID={`guide-edit-section-${i}-block-${j}-remove`} />
    </View>
    <Inp value={b.text} onChange={v => onChange({ ...b, text: v })} multiline placeholder={KINDS.find(k => k.key === b.kind)?.hint} testID={`guide-edit-section-${i}-block-${j}-text`} style={b.kind === 'say' ? { borderLeftWidth: 3, borderLeftColor: GOLD } : b.kind === 'warn' ? { borderLeftWidth: 3, borderLeftColor: RED } : undefined} />
  </View>
);

const ScorecardEditor = ({ rows, total, onChange }: { rows: Draft['scorecard']; total: number; onChange: (rows: Draft['scorecard']) => void }) => (
  <View style={{ backgroundColor: C.card, borderRadius: 16, borderWidth: 1, borderColor: GOLD + '66', padding: 14, gap: 8 }} {...tid('guide-edit-scorecard')}>
    <Head t="KPI SCORECARD" sub="What the rep taps after the call to self-score. Points should add up to 100." />
    {rows.map((r, i) => (
      <View key={i} style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
        <View style={{ flex: 1 }}><Inp value={r.label} onChange={v => onChange(rows.map((x, j) => (j === i ? { ...x, label: v } : x)))} placeholder="Application Discovery" testID={`guide-edit-score-${i}-label`} /></View>
        <Inp value={r.points} onChange={v => onChange(rows.map((x, j) => (j === i ? { ...x, points: v.replace(/\D/g, '').slice(0, 3) } : x)))} placeholder="10" keyboardType="number-pad" testID={`guide-edit-score-${i}-points`} style={{ width: 64, textAlign: 'center', fontWeight: '800' }} />
        <IconBtn icon="close-circle" onPress={() => onChange(rows.filter((_, j) => j !== i))} color={RED} testID={`guide-edit-score-${i}-remove`} />
      </View>
    ))}
    <AddBtn label="Add row" onPress={() => onChange([...rows, { label: '', points: '5' }])} testID="guide-edit-score-add" />
    <View style={{ flexDirection: 'row', justifyContent: 'space-between', borderTopWidth: 1, borderTopColor: GOLD + '66', paddingTop: 10 }}>
      <Text style={{ fontSize: 14, fontWeight: '900', color: GOLD, letterSpacing: 1 }}>TOTAL</Text>
      <Text style={{ fontSize: 14, fontWeight: '900', color: total === 100 ? GREEN : RED }} {...tid('guide-edit-scorecard-total')}>{total}{total === 100 ? '' : ' / 100'}</Text>
    </View>
  </View>
);
