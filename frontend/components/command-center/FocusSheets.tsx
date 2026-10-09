import React, { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity } from 'react-native';
import api from '../../services/api';
import { useToast } from '../common/Toast';
import { Sheet, Field, Label, Chip, GoldButton } from '../mystery-shops/shared';
import { Pill } from './CcShell';
import { OBJECTIVE_STATUS, PILLAR_COLOR, GOLD, RED, GREEN, detail, tid, type Focus, type Priority } from './shared';

type Base = { visible: boolean; onClose: () => void; colors: any; onSaved: () => void };

const Stepper = ({ value, onChange, colors, testID }: { value: number; onChange: (n: number) => void; colors: any; testID: string }) => (
  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }} {...tid(testID)}>
    {[0, 25, 50, 75, 100].map(v => <Chip key={v} small label={`${v}%`} active={value === v} onPress={() => onChange(v)} colors={colors} testID={`${testID}-${v}`} />)}
  </View>
);

// THE ONE BIG THING: title, why, target, progress, status.
export const ObjectiveSheet = ({ visible, onClose, colors, onSaved, focus }: Base & { focus: Focus | null }) => {
  const { showToast } = useToast();
  const d = focus?.objective?.data;
  const [f, setF] = useState({ title: '', why: '', target_date: '', progress_pct: 0, status: 'proposed' });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  useEffect(() => { if (visible && d) { setF({ title: d.title || '', why: d.why || '', target_date: d.target_date || '', progress_pct: d.progress_pct || 0, status: d.status || 'proposed' }); setErr(''); } }, [visible]);
  const save = async () => {
    setBusy(true); setErr('');
    try { await api.put('/command-center/blueprint/objective', { data: { ...f, target_date: f.target_date.trim() || null } }); showToast('One Big Thing saved'); onClose(); onSaved(); }
    catch (e: any) { setErr(detail(e, 'Could not save')); } finally { setBusy(false); }
  };
  return (
    <Sheet visible={visible} onClose={onClose} title="The One Big Thing" colors={colors} testID="cc-objective-sheet" error={err} footer={<GoldButton label="Save" onPress={save} busy={busy} icon="checkmark" testID="cc-objective-save" />}>
      <Field label="THE OBJECTIVE" value={f.title} onChange={(v: string) => setF(x => ({ ...x, title: v }))} colors={colors} multiline testID="cc-objective-title" />
      <Field label="WHY IT MATTERS (ONE LINE)" value={f.why} onChange={(v: string) => setF(x => ({ ...x, why: v }))} colors={colors} multiline placeholder="Leave blank until you have the words" testID="cc-objective-why" />
      <Field label="TARGET DATE (YYYY-MM-DD, OPTIONAL)" value={f.target_date} onChange={(v: string) => setF(x => ({ ...x, target_date: v }))} colors={colors} placeholder="2027-01-15" autoCapitalize="none" testID="cc-objective-date" />
      <View style={{ gap: 6 }}><Label t="PROGRESS" colors={colors} /><Stepper value={f.progress_pct} onChange={(n) => setF(x => ({ ...x, progress_pct: n }))} colors={colors} testID="cc-objective-progress" /></View>
      <View style={{ gap: 6 }}><Label t="STATUS" colors={colors} /><View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>{Object.entries(OBJECTIVE_STATUS).map(([k, v]) => <Chip key={k} small label={v.label} active={f.status === k} onPress={() => setF(x => ({ ...x, status: k }))} colors={colors} testID={`cc-objective-status-${k}`} />)}</View></View>
    </Sheet>
  );
};

// A strategic priority: create or edit, and the four moves (activate, pause, complete, replace).
export const PrioritySheet = ({ visible, onClose, colors, onSaved, focus, priority, onReplace }: Base & { focus: Focus | null; priority: Priority | null; onReplace: (p: Priority, active: Priority[]) => void }) => {
  const { showToast } = useToast();
  const [f, setF] = useState({ title: '', pillar: '', product: '', purpose: '', next_action: '', due: '', progress_pct: 0, definition_of_done: '' });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  useEffect(() => {
    if (!visible) return;
    setErr('');
    setF(priority ? { title: priority.title, pillar: priority.pillar || '', product: priority.product || '', purpose: priority.purpose || '', next_action: priority.next_action || '', due: priority.due || '', progress_pct: priority.progress_pct || 0, definition_of_done: priority.definition_of_done || '' }
      : { title: '', pillar: '', product: '', purpose: '', next_action: '', due: '', progress_pct: 0, definition_of_done: '' });
  }, [visible, priority?.id]);
  const body = () => ({ ...f, due: f.due.trim() || null });
  const run = async (fn: () => Promise<any>, ok: string) => {
    setBusy(true); setErr('');
    try { await fn(); showToast(ok); onClose(); onSaved(); }
    catch (e: any) {
      if (e?.response?.status === 409 && priority) { onClose(); onReplace(priority, e.response.data?.detail?.active || focus?.active || []); return; }
      setErr(detail(e, 'Could not save'));
    } finally { setBusy(false); }
  };
  const save = () => run(async () => { if (priority) await api.patch(`/command-center/priorities/${priority.id}`, body()); else await api.post('/command-center/priorities', body()); }, 'Priority saved');
  const saveThen = async (path: string, ok: string) => {
    setBusy(true); setErr('');
    try {
      const r = priority ? await api.patch(`/command-center/priorities/${priority.id}`, body()) : await api.post('/command-center/priorities', body());
      const saved = r.data as Priority;
      try { await api.post(`/command-center/priorities/${saved.id}/${path}`); showToast(ok); onClose(); onSaved(); }
      catch (e: any) {
        if (e?.response?.status === 409) { onClose(); onSaved(); onReplace(saved, e.response.data?.detail?.active || focus?.active || []); return; }
        setErr(detail(e, 'Could not do that'));
      }
    } catch (e: any) { setErr(detail(e, 'Could not save')); }
    finally { setBusy(false); }
  };
  const isActive = priority?.status === 'active';
  const canActivate = !!f.pillar && !!f.purpose.trim() && !!f.title.trim();
  return (
    <Sheet visible={visible} onClose={onClose} title={priority ? (isActive ? `Priority ${priority.slot}` : 'Priority') : 'Propose a priority'} colors={colors} testID="cc-priority-sheet" error={err}
      footer={
        <View style={{ gap: 8 }}>
          <GoldButton label="Save" onPress={save} busy={busy} icon="checkmark" testID="cc-priority-save" />
          {!isActive && priority?.status !== 'completed' && priority?.status !== 'replaced' && <GoldButton label={canActivate ? 'Save & make it one of my three' : 'Add a pillar and a purpose to activate'} onPress={() => saveThen('activate', 'Now one of your three')} busy={busy} disabled={!canActivate} outline icon="flag" testID="cc-priority-activate" />}
          {isActive && <View style={{ flexDirection: 'row', gap: 8 }}><View style={{ flex: 1 }}><GoldButton label="Pause" onPress={() => saveThen('pause', 'Paused, slot freed')} busy={busy} outline icon="pause" testID="cc-priority-pause" /></View><View style={{ flex: 1 }}><GoldButton label="Complete" onPress={() => saveThen('complete', 'Completed. Nice work.')} busy={busy} color={GREEN} icon="checkmark-done" testID="cc-priority-complete" /></View></View>}
        </View>
      }>
      {priority && <Pill text={isActive ? `Active · slot ${priority.slot}` : priority.status} color={isActive ? GREEN : priority.status === 'paused' ? GOLD : colors.textSecondary} testID="cc-priority-status" />}
      <Field label="PRIORITY" value={f.title} onChange={(v: string) => setF(x => ({ ...x, title: v }))} colors={colors} multiline testID="cc-priority-title" />
      <View style={{ gap: 6 }}>
        <Label t="SUPPORTS WHICH PILLAR (REQUIRED TO ACTIVATE)" colors={colors} />
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>{(focus?.pillars || []).map(p => <Chip key={p.key} small label={p.name} active={f.pillar === p.key} onPress={() => setF(x => ({ ...x, pillar: x.pillar === p.key ? '' : p.key }))} colors={colors} testID={`cc-priority-pillar-${p.key}`} />)}</View>
      </View>
      <View style={{ gap: 6 }}>
        <Label t="COMMERCIAL PRODUCT (OPTIONAL)" colors={colors} />
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>{(focus?.products || []).map(p => <Chip key={p.key} small label={p.name} active={f.product === p.key} onPress={() => setF(x => ({ ...x, product: x.product === p.key ? '' : p.key }))} colors={colors} testID={`cc-priority-product-${p.key}`} />)}</View>
      </View>
      <Field label="COMMERCIAL PURPOSE (REQUIRED TO ACTIVATE)" value={f.purpose} onChange={(v: string) => setF(x => ({ ...x, purpose: v }))} colors={colors} multiline placeholder="How this creates or protects revenue" testID="cc-priority-purpose" />
      <Field label="NEXT ACTION" value={f.next_action} onChange={(v: string) => setF(x => ({ ...x, next_action: v }))} colors={colors} multiline placeholder="The next concrete step" testID="cc-priority-next" />
      <Field label="DUE (YYYY-MM-DD, OPTIONAL)" value={f.due} onChange={(v: string) => setF(x => ({ ...x, due: v }))} colors={colors} placeholder="leave blank for now" autoCapitalize="none" testID="cc-priority-due" />
      <View style={{ gap: 6 }}><Label t="PROGRESS" colors={colors} /><Stepper value={f.progress_pct} onChange={(n) => setF(x => ({ ...x, progress_pct: n }))} colors={colors} testID="cc-priority-progress" /></View>
      <Field label="DONE WHEN" value={f.definition_of_done} onChange={(v: string) => setF(x => ({ ...x, definition_of_done: v }))} colors={colors} multiline placeholder="What finished looks like" testID="cc-priority-done" />
    </Sheet>
  );
};

// The 409 flow: three are active, so complete / pause / replace one, or park the new one as an idea.
export const ReplaceSheet = ({ visible, onClose, colors, onSaved, incoming, active }: Base & { incoming: Priority | null; active: Priority[] }) => {
  const { showToast } = useToast();
  const [pick, setPick] = useState<string | null>(null);
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  useEffect(() => { if (visible) { setPick(null); setReason(''); setErr(''); } }, [visible]);
  if (!incoming) return null;
  const go = async (path: 'replace' | 'park') => {
    setBusy(true); setErr('');
    try {
      if (path === 'park') {
        await api.post('/command-center/ideas', { title: incoming.title, description: incoming.purpose || '', pillar: incoming.pillar || '', product: incoming.product || '', source: 'text' });
        if (incoming.status === 'proposed') await api.delete(`/command-center/priorities/${incoming.id}`).catch(() => {});
        showToast('Parked in the Idea Vault');
      }
      else { await api.post(`/command-center/priorities/${incoming.id}/replace`, { replace_id: pick, reason }); showToast('Replaced. Still three.'); }
      onClose(); onSaved();
    } catch (e: any) { setErr(detail(e, 'Could not do that')); } finally { setBusy(false); }
  };
  return (
    <Sheet visible={visible} onClose={onClose} title="Your three slots are full" colors={colors} testID="cc-replace-sheet" error={err}
      footer={<View style={{ gap: 8 }}><GoldButton label={pick ? 'Replace it' : 'Pick the one it replaces'} onPress={() => go('replace')} busy={busy} disabled={!pick || !reason.trim()} icon="swap-horizontal" testID="cc-replace-confirm" /><GoldButton label="Park this as an idea instead" onPress={() => go('park')} busy={busy} outline icon="bulb-outline" testID="cc-replace-park" /></View>}>
      <Text style={{ fontSize: 14, color: colors.text, lineHeight: 20 }} {...tid('cc-replace-question')}>Which existing priority should <Text style={{ fontWeight: '800' }}>{incoming.title}</Text> replace, or should we park it? A fourth active priority is not an option.</Text>
      <View style={{ gap: 8 }}>
        {active.map(p => (
          <TouchableOpacity key={p.id} onPress={() => setPick(p.id)} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, padding: 12, borderRadius: 12, borderWidth: 1, borderColor: pick === p.id ? GOLD : colors.border, backgroundColor: colors.card }} {...tid(`cc-replace-pick-${p.id}`)}>
            <View style={{ width: 26, height: 26, borderRadius: 13, backgroundColor: (PILLAR_COLOR[p.pillar] || GOLD) + '33', alignItems: 'center', justifyContent: 'center' }}><Text style={{ fontSize: 12, fontWeight: '800', color: PILLAR_COLOR[p.pillar] || GOLD }}>{p.slot}</Text></View>
            <Text style={{ flex: 1, fontSize: 14, fontWeight: '700', color: colors.text }}>{p.title}</Text>
            <Text style={{ fontSize: 12, color: colors.textSecondary }}>{p.progress_pct}%</Text>
          </TouchableOpacity>
        ))}
      </View>
      <Field label="WHY (RECORDED ON BOTH)" value={reason} onChange={setReason} colors={colors} multiline placeholder="The pilot moved up; positioning is done enough" testID="cc-replace-reason" />
      <Text style={{ fontSize: 12, color: colors.textSecondary }}>Complete or pause from the priority card are the other two ways to free a slot.</Text>
    </Sheet>
  );
};

export const NextActionSheet = ({ visible, onClose, colors, onSaved, current }: Base & { current: { text: string; why: string } | null }) => {
  const { showToast } = useToast();
  const [text, setText] = useState('');
  const [why, setWhy] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  useEffect(() => { if (visible) { setText(current?.text || ''); setWhy(current?.why || ''); setErr(''); } }, [visible]);
  const save = async () => {
    setBusy(true); setErr('');
    try { await api.put('/command-center/next-action', { text, why }); showToast('Next action set'); onClose(); onSaved(); }
    catch (e: any) { setErr(detail(e, 'Could not save')); } finally { setBusy(false); }
  };
  return (
    <Sheet visible={visible} onClose={onClose} title="Next best action" colors={colors} testID="cc-next-sheet" error={err} footer={<GoldButton label="Set it" onPress={save} busy={busy} disabled={!text.trim()} icon="arrow-forward" testID="cc-next-save" />}>
      <Field label="ONE SPECIFIC, ACHIEVABLE ACTION" value={text} onChange={setText} colors={colors} multiline placeholder="Send the three product one-pagers to TracTru before Tuesday" testID="cc-next-text" />
      <Field label="WHY NOW (OPTIONAL)" value={why} onChange={setWhy} colors={colors} multiline placeholder="Unblocks priority 1 and the pilot list" testID="cc-next-why" />
    </Sheet>
  );
};

export const NoteSheet = ({ visible, onClose, colors, onSaved, kind }: Base & { kind: 'waiting' | 'win' }) => {
  const { showToast } = useToast();
  const [title, setTitle] = useState('');
  const [party, setParty] = useState('');
  const [due, setDue] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  useEffect(() => { if (visible) { setTitle(''); setParty(''); setDue(''); setErr(''); } }, [visible]);
  const save = async () => {
    setBusy(true); setErr('');
    try { await api.post('/command-center/notes', { kind, title, party, due: due.trim() || null, status: kind === 'win' ? 'done' : 'open' }); showToast(kind === 'win' ? 'Win recorded' : 'Added to Waiting On'); onClose(); onSaved(); }
    catch (e: any) { setErr(detail(e, 'Could not save')); } finally { setBusy(false); }
  };
  return (
    <Sheet visible={visible} onClose={onClose} title={kind === 'win' ? "This week's win" : 'Waiting on'} colors={colors} testID={`cc-note-sheet-${kind}`} error={err} footer={<GoldButton label="Add" onPress={save} busy={busy} disabled={!title.trim()} icon="add" testID="cc-note-save" />}>
      <Field label={kind === 'win' ? 'WHAT GOT DONE' : 'WHAT ARE YOU WAITING FOR'} value={title} onChange={setTitle} colors={colors} multiline testID="cc-note-title" />
      {kind === 'waiting' && <Field label="FROM WHOM" value={party} onChange={setParty} colors={colors} placeholder="TracTru, Stripe, a developer" testID="cc-note-party" />}
      {kind === 'waiting' && <Field label="NEEDED BY (YYYY-MM-DD, OPTIONAL)" value={due} onChange={setDue} colors={colors} autoCapitalize="none" testID="cc-note-due" />}
    </Sheet>
  );
};

export const SmallAction = ({ label, onPress, colors, testID, color }: { label: string; onPress: () => void; colors: any; testID: string; color?: string }) => (
  <TouchableOpacity onPress={onPress} hitSlop={8} {...tid(testID)}><Text style={{ fontSize: 12.5, fontWeight: '800', color: color || GOLD }}>{label}</Text></TouchableOpacity>
);

export { RED };
