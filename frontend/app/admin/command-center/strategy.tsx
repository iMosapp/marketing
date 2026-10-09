import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, useWindowDimensions } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../../services/api';
import { useThemeStore } from '../../../store/themeStore';
import { useToast } from '../../../components/common/Toast';
import { Sheet, Field, GoldButton } from '../../../components/mystery-shops/shared';
import { CcShell, Card, Eyebrow, Pill } from '../../../components/command-center/CcShell';
import { GOLD, GREEN, AMBER, PILLAR_COLOR, PILLAR_ICON, STATEMENT_LABEL, detail, tid, type Statement, type Pillar, type Product } from '../../../components/command-center/shared';

type Blueprint = { statements: Record<string, Statement>; pillars: Pillar[]; products: Product[] };
const ORDER = ['company', 'category', 'vision', 'promise', 'mission', 'philosophy', 'positioning'];

// STRATEGY: the North Star (editable drafts you approve with a reason), the four pillars and the three commercial packages (seeded; editing arrives in 1B).
export default function Strategy() {
  const { colors } = useThemeStore();
  const { showToast } = useToast();
  const { width } = useWindowDimensions();
  const cols = width >= 1024 ? 2 : 1;
  const [bp, setBp] = useState<Blueprint | null>(null);
  const [edit, setEdit] = useState<Statement | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const [text, setText] = useState('');
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const load = useCallback(async () => { try { setBp((await api.get('/command-center/blueprint')).data); } catch (e: any) { showToast(detail(e, 'Could not load'), 'error'); } }, []);
  useEffect(() => { load(); }, [load]);
  const startEdit = (s: Statement) => { setEdit(s); setText(s.data?.text || ''); setReason(''); setErr(''); };
  const saveDraft = async () => {
    if (!edit) return; setBusy(true); setErr('');
    try { await api.put(`/command-center/blueprint/${edit.key}`, { data: { text }, reason }); showToast('Draft saved (previous version kept)'); setEdit(null); load(); }
    catch (e: any) { setErr(detail(e, 'Could not save')); } finally { setBusy(false); }
  };
  const approve = async () => {
    if (!edit) return; setBusy(true); setErr('');
    try {
      if (text.trim() !== (edit.data?.text || '')) await api.put(`/command-center/blueprint/${edit.key}`, { data: { text }, reason });
      await api.post(`/command-center/blueprint/${edit.key}/approve`, { reason }); showToast('Approved'); setEdit(null); load();
    } catch (e: any) { setErr(detail(e, 'Could not approve')); } finally { setBusy(false); }
  };
  const grid = (items: React.ReactNode[]) => cols === 1 ? <View style={{ gap: 12 }}>{items}</View> : <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 12 }}>{items.map((it, i) => <View key={i} style={{ width: '49%' }}>{it}</View>)}</View>;

  return (
    <CcShell title="Strategy" subtitle="North Star · Pillars · Products" loading={!bp}>
      <View style={{ gap: 10 }}>
        <Eyebrow t="COMPANY NORTH STAR" colors={colors} />
        <Card colors={colors} accent={GOLD} testID="cc-northstar">
          {ORDER.map(k => { const s = bp?.statements?.[k]; if (!s) return null; const big = k === 'promise' || k === 'vision'; return (
            <TouchableOpacity key={k} onPress={() => startEdit(s)} style={{ gap: 4, paddingVertical: 6 }} {...tid(`cc-statement-${k}`)}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                <Text style={{ fontSize: 11.5, fontWeight: '800', letterSpacing: 1, color: colors.textSecondary }}>{STATEMENT_LABEL[k].toUpperCase()}</Text>
                <Pill text={s.status === 'approved' ? 'Approved' : 'Draft'} color={s.status === 'approved' ? GREEN : AMBER} testID={`cc-statement-${k}-status`} />
                {s.versions > 0 && <Text style={{ fontSize: 11, color: colors.textSecondary }}>{s.versions} earlier version{s.versions === 1 ? '' : 's'}</Text>}
              </View>
              <Text style={{ fontSize: big ? 18 : 15, fontWeight: big ? '800' : '600', color: colors.text, lineHeight: big ? 25 : 21, fontStyle: k === 'promise' ? 'italic' : 'normal' }} {...tid(`cc-statement-${k}-text`)}>{k === 'promise' ? `“${s.data?.text}”` : s.data?.text}</Text>
            </TouchableOpacity>
          ); })}
          <Text style={{ fontSize: 12, color: colors.textSecondary }}>Tap a statement to edit. Saving keeps the previous version; approving asks for a reason.</Text>
        </Card>
      </View>

      <View style={{ gap: 10 }}>
        <Eyebrow t="THE FOUR PILLARS" colors={colors} />
        {grid((bp?.pillars || []).filter(Boolean).map(p => {
          const d = p.data; const c = PILLAR_COLOR[d.key] || GOLD; const isOpen = open === p.key;
          return (
            <Card key={p.key} colors={colors} accent={c} testID={`cc-pillar-${d.key}`} onPress={() => setOpen(isOpen ? null : p.key)}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
                <View style={{ width: 34, height: 34, borderRadius: 17, backgroundColor: c + '22', alignItems: 'center', justifyContent: 'center' }}><Ionicons name={PILLAR_ICON[d.key]} size={17} color={c} /></View>
                <View style={{ flex: 1 }}><Text style={{ fontSize: 17, fontWeight: '800', color: colors.text }}>{d.name}</Text><Text style={{ fontSize: 13.5, color: colors.text, fontStyle: 'italic' }}>{d.promise}</Text></View>
                <Ionicons name={isOpen ? 'chevron-up' : 'chevron-down'} size={16} color={colors.textSecondary} />
              </View>
              <Text style={{ fontSize: 13, color: colors.textSecondary, lineHeight: 18 }}>{d.outcome}</Text>
              {isOpen && (
                <View style={{ gap: 8, paddingTop: 4 }} {...tid(`cc-pillar-${d.key}-detail`)}>
                  <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>{d.capabilities.map(x => <View key={x} style={{ paddingHorizontal: 9, height: 24, borderRadius: 12, backgroundColor: colors.border + '88', justifyContent: 'center' }}><Text style={{ fontSize: 11.5, fontWeight: '700', color: colors.text }}>{x}</Text></View>)}</View>
                  <Text style={{ fontSize: 12, color: colors.textSecondary }}>Status {d.status || 'unknown'} · target customer {d.target_customer || 'not set'} · revenue opportunity {d.revenue_opportunity || 'not set'} · KPIs {d.kpis?.length || 0}. Editing these details arrives in the next phase.</Text>
                </View>
              )}
            </Card>
          );
        }))}
      </View>

      <View style={{ gap: 10 }}>
        <Eyebrow t="THREE COMMERCIAL PRODUCTS · ONE PLATFORM" colors={colors} />
        {grid((bp?.products || []).filter(Boolean).map(p => {
          const d = p.data; const isOpen = open === p.key; const rd = d.readiness || {};
          return (
            <Card key={p.key} colors={colors} testID={`cc-product-${d.key}`} onPress={() => setOpen(isOpen ? null : p.key)}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                <Text style={{ flex: 1, fontSize: 17, fontWeight: '800', color: colors.text }}>{d.name}</Text>
                <Pill text={`pricing ${d.pricing?.status || 'uncommitted'}`} color={AMBER} testID={`cc-product-${d.key}-pricing`} />
              </View>
              <Text style={{ fontSize: 14, fontWeight: '600', color: colors.text, fontStyle: 'italic', lineHeight: 20 }}>“{d.promise}”</Text>
              <Text style={{ fontSize: 13, color: colors.textSecondary, lineHeight: 18 }}>For {d.target}</Text>
              {isOpen && (
                <View style={{ gap: 8, paddingTop: 4 }} {...tid(`cc-product-${d.key}-detail`)}>
                  <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>{d.includes.map(x => <View key={x} style={{ paddingHorizontal: 9, height: 24, borderRadius: 12, backgroundColor: colors.border + '88', justifyContent: 'center' }}><Text style={{ fontSize: 11.5, fontWeight: '700', color: colors.text }}>{x}</Text></View>)}</View>
                  <Text style={{ fontSize: 12, color: colors.textSecondary }} {...tid(`cc-product-${d.key}-readiness`)}>Readiness · product {rd.product} · demo {rd.demo} · collateral {rd.collateral} · pilot {rd.pilot}. Nothing here is claimed until you set it.</Text>
                </View>
              )}
            </Card>
          );
        }))}
      </View>

      <Sheet visible={!!edit} onClose={() => setEdit(null)} title={edit ? STATEMENT_LABEL[edit.key] : ''} colors={colors} testID="cc-statement-sheet" error={err}
        footer={<View style={{ gap: 8 }}><GoldButton label="Save as draft" onPress={saveDraft} busy={busy} outline icon="save-outline" testID="cc-statement-save" /><GoldButton label="Approve this wording" onPress={approve} busy={busy} disabled={!reason.trim()} icon="checkmark-circle" testID="cc-statement-approve" /></View>}>
        {!!edit && <>
          <Field label="WORDING" value={text} onChange={setText} colors={colors} multiline testID="cc-statement-text" />
          <Field label="REASON (REQUIRED TO APPROVE, KEPT WITH THE VERSION)" value={reason} onChange={setReason} colors={colors} multiline placeholder="Sharper, matches the equipment dealer pitch" testID="cc-statement-reason" />
          <Text style={{ fontSize: 12, color: colors.textSecondary }}>{edit.status === 'approved' ? 'This wording is approved. Saving a draft keeps it in history and marks the statement draft until you approve again.' : 'This wording is a draft.'}</Text>
        </>}
      </Sheet>
    </CcShell>
  );
}
