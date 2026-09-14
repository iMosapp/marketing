import React, { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, TextInput, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { useToast } from '../common/Toast';
import { Sheet, Label, Chip, GoldButton, deptLabel, GOLD, PURPLE, tid, industries, industryOfDept, deptsFor, loadIndustries, type Challenge } from '../mystery-shops/shared';
import { deptColor } from './shared';

// Pick challenges from the global library to add to a course.
export const ChallengePickerSheet = ({ visible, onClose, colors, already, defaultDept, onAdd }: { visible: boolean; onClose: () => void; colors: any; already: string[]; defaultDept?: string; onAdd: (ids: string[]) => Promise<void> }) => {
  const [rows, setRows] = useState<Challenge[] | null>(null);
  const [industry, setIndustry] = useState<string>('automotive');
  const [dept, setDept] = useState<string>('all');
  const [q, setQ] = useState('');
  const [picked, setPicked] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [, setTick] = useState(0);
  useEffect(() => {
    if (!visible) return;
    setPicked([]); setQ('');
    loadIndustries().then(() => setTick(t => t + 1));
    const hasDept = defaultDept && defaultDept !== 'mixed';
    setIndustry(hasDept ? industryOfDept(defaultDept).key : 'automotive');
    setDept(hasDept ? defaultDept : 'all');
    api.get('/shop-clients/challenges').then(r => setRows(r.data.challenges)).catch(() => setRows([]));
  }, [visible]);
  const depts = deptsFor(industry);
  const inIndustry = (c: Challenge) => depts.some(d => d.key === c.department);
  const list = (rows || []).filter(c => !already.includes(c.id) && inIndustry(c) && (dept === 'all' || c.department === dept) && (!q.trim() || c.title.toLowerCase().includes(q.toLowerCase()) || (c.purpose || '').toLowerCase().includes(q.toLowerCase())));
  const toggle = (id: string) => setPicked(p => (p.includes(id) ? p.filter(x => x !== id) : [...p, id]));
  return (
    <Sheet visible={visible} onClose={onClose} title="Add challenges" colors={colors} testID="picker-sheet" footer={<GoldButton label={picked.length ? `Add ${picked.length} to the course` : 'Pick challenges'} onPress={async () => { setBusy(true); try { await onAdd(picked); onClose(); } finally { setBusy(false); } }} busy={busy} disabled={!picked.length} testID="picker-add" />}>
      <View style={{ flexDirection: 'row', gap: 6, flexWrap: 'wrap' }}>
        {industries().map(i => <Chip key={i.key} label={i.label} small active={industry === i.key} onPress={() => { setIndustry(i.key); setDept('all'); }} colors={colors} testID={`picker-industry-${i.key}`} />)}
      </View>
      <View style={{ flexDirection: 'row', gap: 6, flexWrap: 'wrap' }}>
        <Chip label="All" small active={dept === 'all'} onPress={() => setDept('all')} colors={colors} testID="picker-dept-all" />
        {depts.map(d => <Chip key={d.key} label={d.label} small active={dept === d.key} onPress={() => setDept(d.key)} colors={colors} testID={`picker-dept-${d.key}`} />)}
      </View>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: colors.card, borderRadius: 12, paddingHorizontal: 12, height: 42, borderWidth: 1, borderColor: colors.border }}>
        <Ionicons name="search" size={16} color={colors.textSecondary} />
        <TextInput value={q} onChangeText={setQ} placeholder="Search the library" placeholderTextColor={colors.textSecondary} style={{ flex: 1, color: colors.text, fontSize: 15 }} {...tid('picker-search')} />
      </View>
      {rows === null ? <ActivityIndicator color={GOLD} /> : list.length === 0 ? <Text style={{ fontSize: 13, color: colors.textSecondary }}>Nothing left to add for {industries().find(i => i.key === industry)?.label.toLowerCase() || 'this industry'}. Write more in the Challenge Library (pick the industry there, then let Jessi write the starters).</Text> : list.map(c => {
        const on = picked.includes(c.id);
        return (
          <TouchableOpacity key={c.id} onPress={() => toggle(c.id)} style={{ flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: colors.card, borderRadius: 14, borderWidth: 1, borderColor: on ? GOLD : colors.border, padding: 12 }} {...tid(`picker-item-${c.id}`)}>
            <Ionicons name={on ? 'checkbox' : 'square-outline'} size={22} color={on ? GOLD : colors.textSecondary} />
            <View style={{ flex: 1 }}>
              <Text style={{ fontSize: 14.5, fontWeight: '800', color: colors.text }} numberOfLines={1}>{c.title}</Text>
              <Text style={{ fontSize: 12, color: colors.textSecondary }} numberOfLines={2}><Text style={{ color: deptColor(c.department), fontWeight: '700' }}>{deptLabel(c.department)}</Text> · {c.purpose}</Text>
            </View>
          </TouchableOpacity>
        );
      })}
    </Sheet>
  );
};

type Person = { id: string; name: string; role?: string; department?: string; client_name?: string; enrolled: boolean };

// Enroll reps (managers) or mystery-shop people (iMOS admins) in a course.
export const AssignSheet = ({ visible, onClose, colors, courseId, onDone }: { visible: boolean; onClose: () => void; colors: any; courseId: string; onDone: () => void }) => {
  const { showToast } = useToast();
  const [data, setData] = useState<{ users: Person[]; targets: Person[] } | null>(null);
  const [tab, setTab] = useState<'users' | 'targets'>('users');
  const [q, setQ] = useState('');
  const [users, setUsers] = useState<string[]>([]);
  const [targets, setTargets] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (visible) { setUsers([]); setTargets([]); setQ(''); setTab('users'); api.get(`/courses/${courseId}/people`).then(r => setData(r.data)).catch(() => setData({ users: [], targets: [] })); } }, [visible, courseId]);
  const rows = (data ? data[tab] : []).filter(p => !q.trim() || p.name.toLowerCase().includes(q.toLowerCase()) || (p.client_name || '').toLowerCase().includes(q.toLowerCase()));
  const sel = tab === 'users' ? users : targets;
  const setSel = tab === 'users' ? setUsers : setTargets;
  const go = async () => {
    setBusy(true);
    try { const r = await api.post(`/courses/${courseId}/assign`, { user_ids: users, target_ids: targets }); showToast(`Enrolled ${r.data.enrollments.length} ${r.data.enrollments.length === 1 ? 'person' : 'people'}`, 'success'); onDone(); onClose(); }
    catch (e: any) { showToast(e?.response?.data?.detail || 'Could not enroll', 'error'); }
    finally { setBusy(false); }
  };
  const n = users.length + targets.length;
  return (
    <Sheet visible={visible} onClose={onClose} title="Enroll people" colors={colors} testID="assign-sheet" footer={<GoldButton label={n ? `Enroll ${n} ${n === 1 ? 'person' : 'people'}` : 'Pick people'} onPress={go} busy={busy} disabled={!n} testID="assign-go" icon="school" />}>
      {!!data?.targets?.length && (
        <View style={{ flexDirection: 'row', gap: 8 }}>
          <Chip label={`Reps${users.length ? ` · ${users.length}` : ''}`} active={tab === 'users'} onPress={() => setTab('users')} colors={colors} testID="assign-tab-users" />
          <Chip label={`Mystery-shop people${targets.length ? ` · ${targets.length}` : ''}`} active={tab === 'targets'} onPress={() => setTab('targets')} colors={colors} color={PURPLE} testID="assign-tab-targets" />
        </View>
      )}
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: colors.card, borderRadius: 12, paddingHorizontal: 12, height: 42, borderWidth: 1, borderColor: colors.border }}>
        <Ionicons name="search" size={16} color={colors.textSecondary} />
        <TextInput value={q} onChangeText={setQ} placeholder={tab === 'users' ? 'Search reps' : 'Search people or stores'} placeholderTextColor={colors.textSecondary} style={{ flex: 1, color: colors.text, fontSize: 15 }} {...tid('assign-search')} />
      </View>
      <Text style={{ fontSize: 12.5, color: colors.textSecondary }}>{tab === 'users' ? 'Reps get a push and see the course in Scripts & Practice. They practice each challenge by phone with Jessi.' : 'Mystery-shop people get called with each challenge, inside their store hours, until they pass every one. Their scorecard is texted after each call.'}</Text>
      {data === null ? <ActivityIndicator color={GOLD} /> : rows.length === 0 ? <Text style={{ fontSize: 13, color: colors.textSecondary }}>Nobody to show.</Text> : rows.map(p => {
        const on = sel.includes(p.id);
        return (
          <TouchableOpacity key={p.id} disabled={p.enrolled} onPress={() => setSel(s => (on ? s.filter(x => x !== p.id) : [...s, p.id]))} style={{ flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: colors.card, borderRadius: 14, borderWidth: 1, borderColor: on ? GOLD : colors.border, padding: 12, opacity: p.enrolled ? 0.55 : 1 }} {...tid(`assign-person-${p.id}`)}>
            <Ionicons name={p.enrolled ? 'checkmark-done' : on ? 'checkbox' : 'square-outline'} size={22} color={p.enrolled ? colors.textSecondary : on ? GOLD : colors.textSecondary} />
            <View style={{ flex: 1 }}>
              <Text style={{ fontSize: 14.5, fontWeight: '800', color: colors.text }}>{p.name}</Text>
              <Text style={{ fontSize: 12, color: colors.textSecondary }}>{p.enrolled ? 'Already enrolled' : tab === 'users' ? (p.role || '').replace('_', ' ') : `${deptLabel(p.department)} · ${p.client_name}`}</Text>
            </View>
          </TouchableOpacity>
        );
      })}
    </Sheet>
  );
};
