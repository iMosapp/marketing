import React, { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { useToast } from '../common/Toast';
import { Sheet, Field, Label, Chip, GoldButton, deptLabel, GOLD, GREEN, PURPLE, RED, tid, industries, industryOf, deptsFor, loadIndustries, type Challenge, type ChallengeDraft, type Dept } from './shared';

type Scope = { clientId?: string; clientName?: string; industry?: string; departments?: Dept[] };
type Props = { visible: boolean; onClose: () => void; colors: any; scope?: Scope; onSaved: (c: Challenge) => void; onEditDraft: (d: ChallengeDraft) => void };
type Draft = ChallengeDraft & { savedAs?: 'library' | 'client'; picked?: boolean; failed?: string };
const COUNTS = [1, 2, 3, 5, 10];

const EXAMPLES: Record<string, string> = {
  sales: 'Customer saw a used Tacoma online, has a trade with negative equity, wants to know if you can get them out of their loan and what the payment would be. Skeptical, has been burned before.',
  service: 'Customer hears a squeal from the front brakes on their 2021 Explorer, has a trip this weekend, wants it looked at tomorrow and asks for a loaner. Worried about cost.',
  parts: 'Customer calling parts for a front brake rotor for a 2019 F-150, wants to know if it is in stock and the price, gets impatient when put on hold.',
  rental: 'Customer whose car is in the body shop, insurance is covering a rental, needs something today with room for a car seat, nervous about the deposit.',
  collision: 'Customer was rear ended this morning in a 2022 Grand Cherokee, the other driver admitted fault, wants to know what happens next, whether they need a rental and how long repairs take.',
};
// Industries without a hand-written example get one built from the department pack (its brief + a curveball).
const exampleFor = (dept: Dept, industryKey: string) => EXAMPLES[dept.key] || `A ${industryOf(industryKey).customer} calls ${dept.rep ? dept.rep : 'the team'} about ${industryOf(industryKey).offering.hint}. ${dept.call ? `A typical ${dept.call}` : 'A typical call'}, with one wrinkle: they are comparing you with another ${industryOf(industryKey).business} and want a price before they commit.`;

// Pick one or more departments, how many each, describe a situation (or leave it blank for the everyday calls) and Jessi drafts them all,
// grounded in the department's call guide. Tick the keepers and save the whole stack in one go, or edit the almost-right ones.
export const GeneratorSheet = ({ visible, onClose, colors, scope, onSaved, onEditDraft }: Props) => {
  const { showToast } = useToast();
  const [industry, setIndustry] = useState(scope?.industry || 'automotive');
  const [picked, setPicked] = useState<string[]>([]);
  const [scenario, setScenario] = useState('');
  const [count, setCount] = useState(1);
  const [busy, setBusy] = useState<string>('');
  const [drafts, setDrafts] = useState<Draft[] | null>(null);
  const [saving, setSaving] = useState<number | 'all' | null>(null);
  const [, setTick] = useState(0);
  const depts: Dept[] = scope?.clientId && scope.departments?.length ? scope.departments : deptsFor(industry);
  const firstDept = depts.find(d => d.key === picked[0]) || depts[0];
  const example = firstDept ? exampleFor(firstDept, industry) : '';
  const total = picked.length * count;
  useEffect(() => { if (visible) { loadIndustries().then(() => setTick(t => t + 1)); setIndustry(scope?.industry || 'automotive'); setPicked([scope?.departments?.[0]?.key || deptsFor(scope?.industry || 'automotive')[0]?.key || 'sales']); } }, [visible, scope?.industry]);
  const pickIndustry = (key: string) => { setIndustry(key); setPicked([deptsFor(key)[0]?.key || 'sales']); };
  const toggleDept = (key: string) => setPicked(p => (p.includes(key) ? (p.length > 1 ? p.filter(k => k !== key) : p) : [...depts.map(d => d.key).filter(k => k === key || p.includes(k))]));

  const generate = async () => {
    setDrafts(null);
    const out: Draft[] = [];
    try {
      for (let i = 0; i < picked.length; i++) {
        const dept = picked[i];
        setBusy(picked.length > 1 ? `Writing ${deptLabel(dept, depts)} (${i + 1} of ${picked.length})…` : `Writing ${count > 1 ? `${count} ${deptLabel(dept, depts).toLowerCase()} challenges` : `a ${deptLabel(dept, depts).toLowerCase()} challenge`}…`);
        const r = await api.post('/shop-clients/challenges/generate', { department: dept, scenario, count, client_id: scope?.clientId }, { timeout: 300000 });
        out.push(...r.data.drafts.map((d: ChallengeDraft) => ({ ...d, generated_from: r.data.scenario, picked: true })));
        setDrafts([...out]);
      }
      if (!out.length) showToast('Jessi could not write those, try again', 'error');
    } catch (e: any) { showToast(e?.response?.data?.detail || 'Jessi could not write that one', 'error'); if (out.length) setDrafts([...out]); }
    finally { setBusy(''); }
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
  const saveAll = async (where: 'library' | 'client') => {
    const idx = drafts!.map((d, i) => (d.picked && !d.savedAs ? i : -1)).filter(i => i >= 0);
    if (!idx.length) return;
    setSaving('all');
    try {
      const r = await api.post('/shop-clients/challenges/bulk', { drafts: idx.map(i => drafts![i]), client_id: where === 'client' ? scope?.clientId : undefined }, { timeout: 120000 });
      const failed = new Map<number, string>((r.data.failed || []).map((f: any) => [idx[f.index], f.detail]));
      setDrafts(ds => ds!.map((x, j) => (idx.includes(j) ? (failed.has(j) ? { ...x, failed: failed.get(j) } : { ...x, savedAs: where }) : x)));
      (r.data.saved || []).forEach((c: Challenge) => onSaved(c));
      showToast(`${r.data.saved.length} saved${where === 'client' ? ` for ${scope?.clientName}` : ' to the library'}${failed.size ? `, ${failed.size} need a look` : ''}`, failed.size ? 'error' : 'success');
    } catch (e: any) { showToast(e?.response?.data?.detail || 'Could not save', 'error'); }
    finally { setSaving(null); }
  };
  const reset = () => { setDrafts(null); setScenario(''); };
  const pickedCount = drafts ? drafts.filter(d => d.picked && !d.savedAs).length : 0;
  const unsaved = drafts ? drafts.filter(d => !d.savedAs).length : 0;

  const footer = drafts && !busy
    ? (unsaved > 0
      ? <View style={{ gap: 8 }}>
          <View style={{ flexDirection: 'row', gap: 8 }}>
            <View style={{ flex: 1 }}><GoldButton label={saving === 'all' ? 'Saving…' : `Save ${pickedCount} to library`} onPress={() => saveAll('library')} busy={saving === 'all'} disabled={!pickedCount} testID="generator-save-all-library" icon="library" /></View>
            {!!scope?.clientId && <TouchableOpacity onPress={() => saveAll('client')} disabled={!pickedCount || saving === 'all'} style={{ flex: 1, height: 48, borderRadius: 14, backgroundColor: PURPLE + '22', borderWidth: 1, borderColor: PURPLE, alignItems: 'center', justifyContent: 'center', opacity: pickedCount ? 1 : 0.5 }} {...tid('generator-save-all-client')}><Text style={{ fontSize: 14, fontWeight: '800', color: PURPLE }} numberOfLines={1}>Only {scope.clientName}</Text></TouchableOpacity>}
          </View>
          <GoldButton label="Write more" onPress={reset} outline testID="generator-again" icon="refresh" />
        </View>
      : <GoldButton label="Write more" onPress={reset} outline testID="generator-again" icon="refresh" />)
    : <GoldButton label={busy ? 'Jessi is writing…' : total > 1 ? `Draft ${total} challenges` : 'Draft it'} onPress={generate} busy={!!busy} disabled={!picked.length || (scenario.trim().length > 0 && scenario.trim().length < 15)} testID="generator-go" icon="sparkles" />;

  return (
    <Sheet visible={visible} onClose={() => { onClose(); }} title="Have Jessi write challenges" colors={colors} testID="generator-sheet" footer={footer}>
      {!drafts && !busy && (
        <>
          {!scope?.clientId && <View style={{ gap: 8 }}><Label t="INDUSTRY" colors={colors} /><View style={{ flexDirection: 'row', gap: 6, flexWrap: 'wrap' }}>{industries().map(i => <Chip key={i.key} label={i.label} small active={industry === i.key} onPress={() => pickIndustry(i.key)} colors={colors} testID={`generator-industry-${i.key}`} />)}</View></View>}
          <View style={{ gap: 8 }}>
            <View style={{ flexDirection: 'row', alignItems: 'center' }}><View style={{ flex: 1 }}><Label t={`DEPARTMENTS · ${picked.length} PICKED`} colors={colors} /></View>{depts.length > 1 && <TouchableOpacity onPress={() => setPicked(picked.length === depts.length ? [depts[0].key] : depts.map(d => d.key))} {...tid('generator-dept-all')}><Text style={{ fontSize: 12.5, fontWeight: '800', color: GOLD }}>{picked.length === depts.length ? 'Just one' : 'All departments'}</Text></TouchableOpacity>}</View>
            <View style={{ flexDirection: 'row', gap: 8, flexWrap: 'wrap' }}>{depts.map(d => <Chip key={d.key} label={d.label} active={picked.includes(d.key)} onPress={() => toggleDept(d.key)} colors={colors} testID={`generator-dept-${d.key}`} />)}</View>
          </View>
          <View style={{ gap: 8 }}><Label t={picked.length > 1 ? 'HOW MANY PER DEPARTMENT' : 'HOW MANY'} colors={colors} /><View style={{ flexDirection: 'row', gap: 6 }}>{COUNTS.map(n => <Chip key={n} label={String(n)} small active={count === n} onPress={() => setCount(n)} colors={colors} testID={`generator-count-${n}`} />)}</View></View>
          <Field label="THE SCENARIO, IN YOUR WORDS (OPTIONAL)" value={scenario} onChange={setScenario} colors={colors} multiline placeholder={picked.length > 1 ? 'Leave blank and Jessi writes the everyday versions of each department\u2019s calls, or describe one situation she should build every draft around.' : example} testID="generator-scenario" />
          {picked.length === 1 && <TouchableOpacity onPress={() => setScenario(example)} {...tid('generator-example')}><Text style={{ fontSize: 12.5, fontWeight: '700', color: GOLD }}>Use the example above</Text></TouchableOpacity>}
          <Text style={{ fontSize: 12.5, color: colors.textSecondary, lineHeight: 17 }} {...tid('generator-hint')}>
            {scenario.trim() ? `Jessi builds ${total > 1 ? `${total} different callers` : 'the caller'} around your situation` : `Leave the scenario blank and Jessi writes ${total > 1 ? `${total} different everyday calls` : 'an everyday call'}`}, skipping anything already in the library, and grades against each department's call guide. Nothing is saved until you say so.
          </Text>
        </>
      )}
      {!!busy && <View style={{ alignItems: 'center', gap: 8, paddingVertical: 20 }} {...tid('generator-busy')}><ActivityIndicator color={GOLD} /><Text style={{ fontSize: 13, color: colors.textSecondary }}>{busy} About {count >= 5 ? 'a minute' : '20 seconds'} per department.</Text>{!!drafts?.length && <Text style={{ fontSize: 12.5, fontWeight: '700', color: GREEN }}>{drafts.length} drafted so far</Text>}</View>}
      {drafts && !busy && (
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }} {...tid('generator-summary')}>
          <Text style={{ flex: 1, fontSize: 13.5, fontWeight: '800', color: colors.text }}>{drafts.length} draft{drafts.length === 1 ? '' : 's'}{unsaved ? ` · ${pickedCount} ticked` : ' · all saved'}</Text>
          {unsaved > 0 && <TouchableOpacity onPress={() => setDrafts(ds => ds!.map(d => (d.savedAs ? d : { ...d, picked: pickedCount < unsaved })))} {...tid('generator-pick-all')}><Text style={{ fontSize: 12.5, fontWeight: '800', color: GOLD }}>{pickedCount < unsaved ? 'Tick all' : 'Untick all'}</Text></TouchableOpacity>}
        </View>
      )}
      {drafts && drafts.map((d, i) => (
        <View key={i} style={{ backgroundColor: colors.card, borderRadius: 16, borderWidth: 1, borderColor: d.savedAs ? GREEN + '88' : d.failed ? RED : d.picked ? GOLD + '88' : colors.border, padding: 14, gap: 8 }} {...tid(`draft-${i}`)}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
            {!d.savedAs && <TouchableOpacity onPress={() => setDrafts(ds => ds!.map((x, j) => (j === i ? { ...x, picked: !x.picked } : x)))} hitSlop={8} {...tid(`draft-pick-${i}`)}><Ionicons name={d.picked ? 'checkbox' : 'square-outline'} size={24} color={d.picked ? GOLD : colors.textSecondary} /></TouchableOpacity>}
            <Text style={{ flex: 1, fontSize: 15.5, fontWeight: '800', color: colors.text }} {...tid(`draft-title-${i}`)}>{d.title}</Text>
            {d.savedAs && <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }}><Ionicons name="checkmark-circle" size={16} color={GREEN} /><Text style={{ fontSize: 12, fontWeight: '800', color: GREEN }}>{d.savedAs === 'client' ? 'Saved for client' : 'In the library'}</Text></View>}
          </View>
          {!!d.failed && <Text style={{ fontSize: 12.5, color: RED }} {...tid(`draft-failed-${i}`)}>{d.failed}</Text>}
          <Text style={{ fontSize: 12.5, fontWeight: '800', color: GOLD }}>{deptLabel(d.department, depts).toUpperCase()} · {d.runtime}</Text>
          {!!d.purpose && <Text style={{ fontSize: 13.5, color: colors.textSecondary, fontStyle: 'italic', lineHeight: 19 }}>{d.purpose}</Text>}
          <View style={{ backgroundColor: colors.bg, borderRadius: 12, padding: 10, gap: 3 }}>
            <Text style={{ fontSize: 12.5, fontWeight: '800', color: colors.text }}>{d.persona?.name} <Text style={{ fontWeight: '500', color: colors.textSecondary }}>· {d.persona?.voice} voice</Text></Text>
            <Text style={{ fontSize: 13, color: colors.textSecondary, lineHeight: 18 }}>{d.persona?.summary}</Text>
            <Text style={{ fontSize: 13, color: colors.text, lineHeight: 18 }}>Opens with: "{d.persona?.opening_line}"</Text>
          </View>
          <View style={{ gap: 2 }}><Label t={`GRADED POINTS · ${d.success_points?.length || 0}`} colors={colors} />{(d.success_points || []).map((p, j) => <Text key={j} style={{ fontSize: 13, color: colors.text }}>• {p}</Text>)}</View>
          {!!d.curveballs?.length && <View style={{ gap: 2 }}><Label t="CURVEBALLS" colors={colors} />{d.curveballs.map((p, j) => <Text key={j} style={{ fontSize: 13, color: colors.textSecondary }}>• {p}</Text>)}</View>}
          {!!d.guide_note && <View style={{ gap: 2 }}><Label t="ON THE REP'S GUIDE" colors={colors} /><Text style={{ fontSize: 13, color: colors.text, lineHeight: 18 }}>{d.guide_note}</Text></View>}
          {!d.savedAs && (
            <View style={{ flexDirection: 'row', gap: 8, flexWrap: 'wrap' }}>
              <TouchableOpacity onPress={() => save(i, 'library')} disabled={saving !== null} style={{ flex: 1, minWidth: 140, height: 38, borderRadius: 12, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center' }} {...tid(`draft-save-library-${i}`)}><Text style={{ fontSize: 13, fontWeight: '800', color: '#111' }}>{saving === i ? 'Saving…' : 'Save to library'}</Text></TouchableOpacity>
              {!!scope?.clientId && <TouchableOpacity onPress={() => save(i, 'client')} disabled={saving !== null} style={{ flex: 1, minWidth: 140, height: 38, borderRadius: 12, backgroundColor: PURPLE + '22', borderWidth: 1, borderColor: PURPLE, alignItems: 'center', justifyContent: 'center' }} {...tid(`draft-save-client-${i}`)}><Text style={{ fontSize: 13, fontWeight: '800', color: PURPLE }}>Only {scope.clientName}</Text></TouchableOpacity>}
              <TouchableOpacity onPress={() => onEditDraft(d)} style={{ height: 38, paddingHorizontal: 14, borderRadius: 12, borderWidth: 1, borderColor: colors.border, alignItems: 'center', justifyContent: 'center' }} {...tid(`draft-edit-${i}`)}><Text style={{ fontSize: 13, fontWeight: '800', color: colors.text }}>Edit first</Text></TouchableOpacity>
            </View>
          )}
        </View>
      ))}
    </Sheet>
  );
};
