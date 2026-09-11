import React, { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, TextInput, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Avatar } from '../Avatar';
import { GOLD, tid, RepCard, InboxLite, ownershipAPI } from './ownership';

const Header = ({ title, sub, onBack, colors, testId }: { title: string; sub?: string; onBack: () => void; colors: any; testId: string }) => (
  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 6 }}>
    <TouchableOpacity onPress={onBack} hitSlop={10} {...tid(`${testId}-back`)}>
      <Ionicons name="chevron-back" size={22} color={GOLD} />
    </TouchableOpacity>
    <View style={{ flex: 1 }}>
      <Text style={{ fontSize: 16, fontWeight: '800', color: colors.text }}>{title}</Text>
      {sub ? <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 1 }}>{sub}</Text> : null}
    </View>
  </View>
);

export const NoteInput = ({ value, onChange, colors, testId, placeholder }: { value: string; onChange: (v: string) => void; colors: any; testId: string; placeholder?: string }) => (
  <TextInput
    value={value}
    onChangeText={onChange}
    placeholder={placeholder || 'Add a quick note for them (optional)'}
    placeholderTextColor={colors.textTertiary}
    maxLength={200}
    style={{ backgroundColor: colors.card, borderRadius: 12, borderWidth: 1, borderColor: colors.border, paddingHorizontal: 12, paddingVertical: 10, color: colors.text, fontSize: 14 }}
    {...tid(testId)}
  />
);

export const ConfirmButton = ({ label, onPress, busy, disabled, testId, danger }: { label: string; onPress: () => void; busy?: boolean; disabled?: boolean; testId: string; danger?: boolean }) => (
  <TouchableOpacity onPress={onPress} disabled={busy || disabled} style={{ height: 48, borderRadius: 14, backgroundColor: danger ? '#FF3B30' : GOLD, alignItems: 'center', justifyContent: 'center', opacity: busy || disabled ? 0.5 : 1 }} {...tid(testId)}>
    {busy ? <ActivityIndicator color="#111" /> : <Text style={{ fontSize: 15, fontWeight: '800', color: danger ? '#fff' : '#111' }}>{label}</Text>}
  </TouchableOpacity>
);

type RepPickerProps = {
  title: string; sub?: string; confirmLabel: string; reps: RepCard[] | null; excludeIds?: string[]; meId?: string;
  withNote?: boolean; onBack: () => void; onConfirm: (rep: RepCard, note: string) => Promise<void>; colors: any; testId: string;
};

// Pick one teammate (assign / share). `reps` null = load teammates from the API.
export function RepPicker({ title, sub, confirmLabel, reps, excludeIds = [], meId, withNote = true, onBack, onConfirm, colors, testId }: RepPickerProps) {
  const [list, setList] = useState<RepCard[] | null>(reps);
  const [picked, setPicked] = useState<RepCard | null>(null);
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const [q, setQ] = useState('');
  useEffect(() => { if (!reps) ownershipAPI.teammates().then(setList).catch(() => setList([])); }, [reps]);
  const rows = (list || []).filter(r => !excludeIds.includes(r.id) && (r.active !== false) && (!q || r.name.toLowerCase().includes(q.toLowerCase())));
  return (
    <View style={{ gap: 12 }}>
      <Header title={title} sub={sub} onBack={onBack} colors={colors} testId={testId} />
      {(list || []).length > 6 && (
        <TextInput value={q} onChangeText={setQ} placeholder="Search teammates" placeholderTextColor={colors.textTertiary}
          style={{ backgroundColor: colors.card, borderRadius: 12, paddingHorizontal: 12, paddingVertical: 9, color: colors.text, fontSize: 14 }} {...tid(`${testId}-search`)} />
      )}
      {list === null ? <ActivityIndicator color={GOLD} /> : rows.length === 0 ? (
        <Text style={{ color: colors.textSecondary, fontSize: 13, textAlign: 'center', paddingVertical: 12 }}>No teammates to choose from</Text>
      ) : rows.map(r => {
        const on = picked?.id === r.id;
        return (
          <TouchableOpacity key={r.id} onPress={() => setPicked(r)} style={{ flexDirection: 'row', alignItems: 'center', gap: 12, padding: 10, borderRadius: 12, backgroundColor: on ? GOLD + '22' : colors.card, borderWidth: 1, borderColor: on ? GOLD : 'transparent' }} {...tid(`${testId}-rep-${r.id}`)}>
            <Avatar photo={r.photo || null} name={r.name} size="sm" />
            <View style={{ flex: 1 }}>
              <Text style={{ fontSize: 14, fontWeight: '700', color: colors.text }}>{r.name}{r.id === meId ? ' (you)' : ''}</Text>
              {r.title || r.role ? <Text style={{ fontSize: 12, color: colors.textSecondary }}>{r.title || String(r.role).replace('_', ' ')}</Text> : null}
            </View>
            <Ionicons name={on ? 'radio-button-on' : 'radio-button-off'} size={18} color={on ? GOLD : colors.textSecondary} />
          </TouchableOpacity>
        );
      })}
      {withNote && <NoteInput value={note} onChange={setNote} colors={colors} testId={`${testId}-note`} />}
      <ConfirmButton label={picked ? `${confirmLabel} ${picked.name.split(' ')[0]}` : confirmLabel} disabled={!picked} busy={busy} testId={`${testId}-confirm`}
        onPress={async () => { if (!picked) return; setBusy(true); try { await onConfirm(picked, note); } finally { setBusy(false); } }} />
    </View>
  );
}

type InboxPickerProps = {
  inboxes: InboxLite[]; currentId?: string | null; onBack: () => void; colors: any; testId: string;
  onConfirm: (inbox: InboxLite, rep: RepCard | null, note: string) => Promise<void>;
};

// Move a thread to another inbox, optionally straight to one of its members.
export function InboxPicker({ inboxes, currentId, onBack, onConfirm, colors, testId }: InboxPickerProps) {
  const [picked, setPicked] = useState<InboxLite | null>(null);
  const [rep, setRep] = useState<RepCard | null>(null);
  const [members, setMembers] = useState<RepCard[]>([]);
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    setRep(null);
    if (!picked) return;
    ownershipAPI.teammates().then(all => setMembers(all.filter(u => picked.members.includes(u.id)))).catch(() => setMembers([]));
  }, [picked?.id]);
  const options = inboxes.filter(i => i.id !== currentId);
  return (
    <View style={{ gap: 12 }}>
      <Header title="Move to another inbox" sub="The customer will hear back from that inbox's number" onBack={onBack} colors={colors} testId={testId} />
      {options.length === 0 ? (
        <Text style={{ color: colors.textSecondary, fontSize: 13, textAlign: 'center', paddingVertical: 12 }}>No other inboxes yet. Create one under Hub, Inboxes.</Text>
      ) : options.map(i => {
        const on = picked?.id === i.id;
        return (
          <TouchableOpacity key={i.id} onPress={() => setPicked(i)} style={{ flexDirection: 'row', alignItems: 'center', gap: 12, padding: 12, borderRadius: 12, backgroundColor: on ? GOLD + '22' : colors.card, borderWidth: 1, borderColor: on ? GOLD : 'transparent' }} {...tid(`${testId}-inbox-${i.id}`)}>
            <View style={{ width: 12, height: 12, borderRadius: 6, backgroundColor: i.color || GOLD }} />
            <Text style={{ flex: 1, fontSize: 14, fontWeight: '700', color: colors.text }}>{i.name}</Text>
            <Text style={{ fontSize: 12, color: colors.textSecondary }}>{i.members.length} on it</Text>
            <Ionicons name={on ? 'radio-button-on' : 'radio-button-off'} size={18} color={on ? GOLD : colors.textSecondary} />
          </TouchableOpacity>
        );
      })}
      {picked && (
        <View style={{ gap: 8 }}>
          <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 1 }}>HAND IT TO (OPTIONAL)</Text>
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
            <TouchableOpacity onPress={() => setRep(null)} style={{ paddingHorizontal: 12, paddingVertical: 7, borderRadius: 16, backgroundColor: !rep ? GOLD : colors.card, borderWidth: 1, borderColor: !rep ? GOLD : colors.border }} {...tid(`${testId}-rep-none`)}>
              <Text style={{ fontSize: 13, fontWeight: '700', color: !rep ? '#111' : colors.text }}>Whole team (up for grabs)</Text>
            </TouchableOpacity>
            {members.map(m => {
              const on = rep?.id === m.id;
              return (
                <TouchableOpacity key={m.id} onPress={() => setRep(m)} style={{ paddingHorizontal: 12, paddingVertical: 7, borderRadius: 16, backgroundColor: on ? GOLD : colors.card, borderWidth: 1, borderColor: on ? GOLD : colors.border }} {...tid(`${testId}-rep-${m.id}`)}>
                  <Text style={{ fontSize: 13, fontWeight: '700', color: on ? '#111' : colors.text }}>{m.name.split(' ')[0]}</Text>
                </TouchableOpacity>
              );
            })}
          </View>
        </View>
      )}
      <NoteInput value={note} onChange={setNote} colors={colors} testId={`${testId}-note`} placeholder="Why it's moving (optional)" />
      <ConfirmButton label={picked ? `Move to ${picked.name}` : 'Move'} disabled={!picked} busy={busy} testId={`${testId}-confirm`}
        onPress={async () => { if (!picked) return; setBusy(true); try { await onConfirm(picked, rep, note); } finally { setBusy(false); } }} />
    </View>
  );
}

// Release to the inbox queue / confirm graduate: a note + one button.
export function NoteConfirm({ title, sub, confirmLabel, onBack, onConfirm, colors, testId, danger, placeholder }: { title: string; sub?: string; confirmLabel: string; onBack: () => void; onConfirm: (note: string) => Promise<void>; colors: any; testId: string; danger?: boolean; placeholder?: string }) {
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  return (
    <View style={{ gap: 12 }}>
      <Header title={title} sub={sub} onBack={onBack} colors={colors} testId={testId} />
      {placeholder !== null && <NoteInput value={note} onChange={setNote} colors={colors} testId={`${testId}-note`} placeholder={placeholder} />}
      <ConfirmButton label={confirmLabel} busy={busy} danger={danger} testId={`${testId}-confirm`}
        onPress={async () => { setBusy(true); try { await onConfirm(note); } finally { setBusy(false); } }} />
    </View>
  );
}
