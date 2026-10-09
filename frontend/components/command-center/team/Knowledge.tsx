import React, { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../../services/api';
import { showConfirm } from '../../../services/alert';
import { useToast } from '../../common/Toast';
import { Sheet, Field, Label, Chip, GoldButton } from '../../mystery-shops/shared';
import { Eyebrow, Empty, Pill } from '../CcShell';
import { GOLD, GREEN, RED, AMBER, FACT_STATUS, detail, tid, type Fact } from '../shared';

const DOMAIN_LABEL: Record<string, string> = { strategy: 'Strategy', products: 'Products', technology: 'Technology', customers: 'Customers and partners', commercial: 'Commercial and pricing', financials: 'Financials', operations: 'Operations', departments: 'Departments and people', decisions: 'Decisions', compliance: 'Compliance' };

// COMPANY KNOWLEDGE: facts with a status, a source and a freshness date. Executives may cite only VERIFIED facts as FACT; the founder verifies, disputes or retires them here.
export const Knowledge = ({ colors, onChanged }: { colors: any; onChanged: () => void }) => {
  const { showToast } = useToast();
  const [facts, setFacts] = useState<Fact[] | null>(null);
  const [meta, setMeta] = useState<{ domains: string[]; kinds: string[]; source_kinds: string[] }>({ domains: [], kinds: [], source_kinds: [] });
  const [adding, setAdding] = useState(false);
  const load = async () => { try { const r = await api.get('/command-center/team/knowledge'); setFacts(r.data.facts); setMeta(r.data); } catch (e: any) { showToast(detail(e, 'Could not load'), 'error'); } };
  useEffect(() => { load(); }, []);
  const setStatus = (f: Fact, status: string) => showConfirm(`${FACT_STATUS[status].label}: ${f.key}`, status === 'verified' ? 'Executives may then cite it as FACT. Only do this when you know it is true today.' : status === 'disputed' ? 'It stays visible, labelled disputed, and counts only as an assumption.' : 'It disappears from every executive prompt.', async () => {
    try { await api.post(`/command-center/team/knowledge/${f.id}/status`, { status }); showToast(`${f.key} is now ${status}`); load(); onChanged(); } catch (e: any) { showToast(detail(e, 'Could not update'), 'error'); }
  }, undefined, FACT_STATUS[status].label);
  const live = (facts || []).filter(f => f.status !== 'retired');
  const groups = meta.domains.filter(d => live.some(f => f.domain === d));
  return (
    <View style={{ gap: 16 }} {...tid('cc-knowledge')}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
        <Text style={{ flex: 1, fontSize: 13, color: colors.textSecondary, lineHeight: 18 }}>{live.filter(f => f.status === 'verified').length} verified · {live.filter(f => f.status === 'proposed').length} proposed · {live.filter(f => f.status === 'disputed').length} disputed. An executive's readiness grows as its required facts become verified and fresh.</Text>
        <TouchableOpacity onPress={() => setAdding(true)} style={{ flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 12, height: 34, borderRadius: 17, backgroundColor: GOLD }} {...tid('cc-fact-add')}><Ionicons name="add" size={16} color="#1C1C1E" /><Text style={{ fontSize: 12.5, fontWeight: '800', color: '#1C1C1E' }}>Add a fact</Text></TouchableOpacity>
      </View>
      {facts === null && <ActivityIndicator color={GOLD} />}
      {facts && !live.length && <Empty t="No facts recorded yet." colors={colors} testID="cc-knowledge-empty" />}
      {groups.map(d => (
        <View key={d} style={{ gap: 8 }}>
          <Eyebrow t={(DOMAIN_LABEL[d] || d).toUpperCase()} colors={colors} />
          {live.filter(f => f.domain === d).map(f => {
            const st = FACT_STATUS[f.status];
            return (
              <View key={f.id} style={{ padding: 12, borderRadius: 14, backgroundColor: colors.card, borderWidth: 1, borderColor: f.status === 'disputed' ? RED + '88' : colors.border, gap: 6 }} {...tid(`cc-fact-${f.key}`)}>
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                  <Text style={{ flex: 1, fontSize: 12, fontWeight: '800', color: colors.textSecondary, minWidth: 120 }} numberOfLines={1}>{f.key}</Text>
                  <Pill text={st.label + (f.kind !== 'fact' ? ` · ${f.kind}` : '')} color={st.color} testID={`cc-fact-${f.key}-status`} />
                  {f.stale && <Pill text="May be outdated" color={AMBER} icon="time" />}
                </View>
                <Text style={{ fontSize: 13.5, color: colors.text, lineHeight: 19 }} selectable>{f.statement}</Text>
                <Text style={{ fontSize: 11.5, color: colors.textSecondary }}>Source: {f.source.kind}{f.source.ref ? ` · ${f.source.ref}` : ''} · as of {f.as_of?.slice(0, 10)}</Text>
                <View style={{ flexDirection: 'row', gap: 8 }}>
                  {f.status !== 'verified' && <Act label="Verify" color={GREEN} onPress={() => setStatus(f, 'verified')} testID={`cc-fact-${f.key}-verify`} />}
                  {f.status !== 'disputed' && <Act label="Dispute" color={RED} onPress={() => setStatus(f, 'disputed')} testID={`cc-fact-${f.key}-dispute`} />}
                  <Act label="Retire" color={colors.textSecondary} onPress={() => setStatus(f, 'retired')} testID={`cc-fact-${f.key}-retire`} />
                </View>
              </View>
            );
          })}
        </View>
      ))}
      <AddFactSheet visible={adding} onClose={() => setAdding(false)} colors={colors} domains={meta.domains} kinds={meta.kinds} onSaved={() => { load(); onChanged(); }} />
    </View>
  );
};

const Act = ({ label, color, onPress, testID }: { label: string; color: string; onPress: () => void; testID: string }) => (
  <TouchableOpacity onPress={onPress} style={{ paddingHorizontal: 10, height: 28, borderRadius: 14, borderWidth: 1, borderColor: color, justifyContent: 'center' }} {...tid(testID)}><Text style={{ fontSize: 12, fontWeight: '800', color }}>{label}</Text></TouchableOpacity>
);

const AddFactSheet = ({ visible, onClose, colors, domains, kinds, onSaved }: { visible: boolean; onClose: () => void; colors: any; domains: string[]; kinds: string[]; onSaved: () => void }) => {
  const { showToast } = useToast();
  const [f, setF] = useState({ key: '', statement: '', domain: 'commercial', kind: 'fact', status: 'proposed', ref: '' });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  useEffect(() => { if (visible) { setF({ key: '', statement: '', domain: 'commercial', kind: 'fact', status: 'proposed', ref: '' }); setErr(''); } }, [visible]);
  const save = async () => {
    setBusy(true); setErr('');
    try { await api.post('/command-center/team/knowledge', { key: f.key, statement: f.statement, domain: f.domain, kind: f.kind, status: f.status, source: { kind: 'human', ref: f.ref } }); showToast('Fact recorded'); onClose(); onSaved(); }
    catch (e: any) { setErr(detail(e, 'Could not save')); } finally { setBusy(false); }
  };
  return (
    <Sheet visible={visible} onClose={onClose} title="Add a company fact" colors={colors} testID="cc-fact-sheet" error={err} footer={<GoldButton label="Record it" icon="checkmark" onPress={save} busy={busy} disabled={!f.key.trim() || !f.statement.trim()} testID="cc-fact-save" />}>
      <Field label="KEY (DOTTED, STABLE)" value={f.key} onChange={(v: string) => setF(x => ({ ...x, key: v }))} colors={colors} placeholder="commercial.pricing.floor" autoCapitalize="none" testID="cc-fact-key" />
      <Field label="THE STATEMENT" value={f.statement} onChange={(v: string) => setF(x => ({ ...x, statement: v }))} colors={colors} multiline placeholder="Mystery Shops is never sold below 300 USD per month." testID="cc-fact-statement" />
      <View style={{ gap: 6 }}><Label t="DOMAIN" colors={colors} /><View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>{domains.map(d => <Chip key={d} small label={DOMAIN_LABEL[d] || d} active={f.domain === d} onPress={() => setF(x => ({ ...x, domain: d }))} colors={colors} testID={`cc-fact-domain-${d}`} />)}</View></View>
      <View style={{ gap: 6 }}><Label t="KIND" colors={colors} /><View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>{kinds.map(k => <Chip key={k} small label={k} active={f.kind === k} onPress={() => setF(x => ({ ...x, kind: k }))} colors={colors} testID={`cc-fact-kind-${k}`} />)}</View></View>
      <View style={{ gap: 6 }}><Label t="STATUS" colors={colors} /><View style={{ flexDirection: 'row', gap: 6 }}>{['proposed', 'verified'].map(s => <Chip key={s} small label={s === 'verified' ? 'Verified (I know this is true)' : 'Proposed'} active={f.status === s} onPress={() => setF(x => ({ ...x, status: s }))} colors={colors} color={s === 'verified' ? GREEN : GOLD} testID={`cc-fact-status-${s}`} />)}</View></View>
      <Field label="SOURCE (OPTIONAL)" value={f.ref} onChange={(v: string) => setF(x => ({ ...x, ref: v }))} colors={colors} placeholder="Pricing call with TracTru, Oct 3" testID="cc-fact-ref" />
    </Sheet>
  );
};
