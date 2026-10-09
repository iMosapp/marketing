import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../../services/api';
import { showConfirm } from '../../../services/alert';
import { useThemeStore } from '../../../store/themeStore';
import { useToast } from '../../../components/common/Toast';
import { Sheet, Field, Label, Chip, GoldButton } from '../../../components/mystery-shops/shared';
import { CcShell, Card, Eyebrow, Pill, Empty } from '../../../components/command-center/CcShell';
import { CaptureBar } from '../../../components/command-center/CaptureBar';
import { GOLD, RED, IDEA_STATUS, fmtDay, detail, tid, type Idea, type Focus } from '../../../components/command-center/shared';

type View_ = 'all' | 'new_week' | 'captured' | 'evaluating' | 'parked' | 'approved' | 'active' | 'rejected';
const FILTERS: [View_, string][] = [['all', 'All'], ['new_week', 'New this week'], ['captured', 'Captured'], ['evaluating', 'Evaluating'], ['parked', 'Parked'], ['approved', 'Approved'], ['active', 'Active'], ['rejected', 'Declined']];

// THE IDEA VAULT: capture first, evaluate later. Nothing here becomes work until you say so, somewhere else.
export default function IdeaVault() {
  const { colors } = useThemeStore();
  const { showToast } = useToast();
  const [rows, setRows] = useState<Idea[] | null>(null);
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [view, setView] = useState<View_>('all');
  const [meta, setMeta] = useState<Focus | null>(null);
  const [edit, setEdit] = useState<Idea | null>(null);
  const [f, setF] = useState({ title: '', description: '', pillar: '', product: '', customer: '', value: '', status: 'captured' });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const load = useCallback(async () => {
    try {
      const params = view === 'all' ? {} : view === 'new_week' ? { view: 'new_week' } : { status: view };
      const [a, b] = await Promise.all([api.get('/command-center/ideas', { params }), meta ? Promise.resolve({ data: meta }) : api.get('/command-center/focus')]);
      setRows(a.data.ideas); setCounts(a.data.counts); if (!meta) setMeta(b.data);
    } catch (e: any) { showToast(detail(e, 'Could not load'), 'error'); }
  }, [view]);
  useEffect(() => { load(); }, [load]);
  const open = (i: Idea) => { setEdit(i); setF({ title: i.title, description: i.description || '', pillar: i.pillar || '', product: i.product || '', customer: i.customer || '', value: i.value || '', status: i.status }); setErr(''); };
  const save = async () => {
    if (!edit) return; setBusy(true); setErr('');
    try { await api.patch(`/command-center/ideas/${edit.id}`, f); showToast('Idea saved'); setEdit(null); load(); }
    catch (e: any) { setErr(detail(e, 'Could not save')); } finally { setBusy(false); }
  };
  const remove = () => edit && showConfirm('Delete this idea?', 'Declining keeps it on record; deleting does not.', () => api.delete(`/command-center/ideas/${edit.id}`).then(() => { setEdit(null); showToast('Deleted'); load(); }), undefined, 'Delete');
  const countOf = (k: View_) => (k === 'all' ? Object.values(counts).reduce((a, b, i, arr) => (i < arr.length - 1 ? a + b : a), 0) : counts[k] || 0);

  return (
    <CcShell title="Idea Vault" subtitle={rows ? `${counts.captured || 0} captured · ${counts.parked || 0} parked · ${counts.new_week || 0} new this week` : undefined} loading={!rows}>
      <CaptureBar colors={colors} onCaptured={load} />
      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }} {...tid('cc-idea-filters')}>
        {FILTERS.map(([k, label]) => <Chip key={k} small label={`${label}${k !== 'all' ? ` ${countOf(k)}` : ''}`} active={view === k} onPress={() => setView(k)} colors={colors} testID={`cc-idea-filter-${k}`} />)}
      </View>
      {view === 'new_week' && <Text style={{ fontSize: 12.5, color: colors.textSecondary, lineHeight: 17 }} {...tid('cc-weekly-hint')}>Your weekly review: read these once, then move each one to Evaluating, Parked or Declined. No notifications, no rush.</Text>}
      {rows && rows.length === 0 ? <Empty t={view === 'all' ? 'Nothing captured yet. Drop the first one above.' : 'Nothing here.'} colors={colors} testID="cc-ideas-empty" /> : (
        <View style={{ gap: 10 }}>
          {(rows || []).map(i => { const st = IDEA_STATUS[i.status]; return (
            <Card key={i.id} colors={colors} accent={st.color} testID={`cc-idea-${i.id}`} onPress={() => open(i)}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                <Text style={{ flex: 1, fontSize: 15, fontWeight: '800', color: colors.text, lineHeight: 20 }}>{i.title}</Text>
                <Pill text={st.label} color={st.color} testID={`cc-idea-${i.id}-status`} />
              </View>
              {!!i.description && <Text style={{ fontSize: 13, color: colors.textSecondary, lineHeight: 18 }} numberOfLines={2}>{i.description}</Text>}
              <Text style={{ fontSize: 11.5, color: colors.textSecondary }}>{fmtDay(i.created_at)}{i.pillar ? ` · ${i.pillar}` : ''}{i.product ? ` · ${i.product.replace(/_/g, ' ')}` : ''}{i.source === 'voice' ? ' · spoken' : ''}</Text>
            </Card>
          ); })}
        </View>
      )}

      <Sheet visible={!!edit} onClose={() => setEdit(null)} title="Idea" colors={colors} testID="cc-idea-sheet" error={err}
        footer={<View style={{ gap: 8 }}><GoldButton label="Save" onPress={save} busy={busy} icon="checkmark" testID="cc-idea-save" /><TouchableOpacity onPress={remove} style={{ alignSelf: 'center', padding: 6 }} {...tid('cc-idea-delete')}><Text style={{ fontSize: 12.5, fontWeight: '800', color: RED }}>Delete</Text></TouchableOpacity></View>}>
        {!!edit && <>
          <View style={{ gap: 6 }}><Label t="STATUS" colors={colors} /><View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>{Object.entries(IDEA_STATUS).map(([k, v]) => <Chip key={k} small label={v.label} active={f.status === k} onPress={() => setF(x => ({ ...x, status: k }))} colors={colors} testID={`cc-idea-status-${k}`} />)}</View>
            <Text style={{ fontSize: 12, color: colors.textSecondary }}>Approved and Active are labels for your own tracking. Nothing is scheduled or built from here.</Text></View>
          <Field label="IDEA" value={f.title} onChange={(v: string) => setF(x => ({ ...x, title: v }))} colors={colors} multiline testID="cc-idea-title" />
          <Field label="NOTES" value={f.description} onChange={(v: string) => setF(x => ({ ...x, description: v }))} colors={colors} multiline testID="cc-idea-description" />
          <View style={{ gap: 6 }}><Label t="PILLAR" colors={colors} /><View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>{(meta?.pillars || []).map(p => <Chip key={p.key} small label={p.name} active={f.pillar === p.key} onPress={() => setF(x => ({ ...x, pillar: x.pillar === p.key ? '' : p.key }))} colors={colors} testID={`cc-idea-pillar-${p.key}`} />)}</View></View>
          <View style={{ gap: 6 }}><Label t="PRODUCT" colors={colors} /><View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>{(meta?.products || []).map(p => <Chip key={p.key} small label={p.name} active={f.product === p.key} onPress={() => setF(x => ({ ...x, product: x.product === p.key ? '' : p.key }))} colors={colors} testID={`cc-idea-product-${p.key}`} />)}</View></View>
          <Field label="POTENTIAL CUSTOMER (OPTIONAL)" value={f.customer} onChange={(v: string) => setF(x => ({ ...x, customer: v }))} colors={colors} testID="cc-idea-customer" />
          <Field label="EXPECTED BUSINESS VALUE (OPTIONAL)" value={f.value} onChange={(v: string) => setF(x => ({ ...x, value: v }))} colors={colors} multiline testID="cc-idea-value" />
          {!!edit.transcript && <Text style={{ fontSize: 12, color: colors.textSecondary }}>Spoken: {edit.transcript}</Text>}
        </>}
      </Sheet>
    </CcShell>
  );
}
