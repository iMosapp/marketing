import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, TextInput, useWindowDimensions } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import api from '../../../services/api';
import { showConfirm } from '../../../services/alert';
import { useThemeStore } from '../../../store/themeStore';
import { useToast } from '../../../components/common/Toast';
import { CcShell, Card, Progress } from '../../../components/command-center/CcShell';
import { GOLD, ROADMAP_STATUS, fmtDay, detail, bounceIfPrivate, tid, type RoadmapPhase, type RoadmapItem } from '../../../components/command-center/shared';

const NEXT: Record<string, string> = { not_started: 'in_progress', in_progress: 'done', done: 'not_started', blocked: 'in_progress' };

// 90-DAY ROADMAP: three phases, simple milestones, tap a status to advance it, one-line add. Dependencies and editing sheets arrive in 1B.
export default function Roadmap() {
  const { colors } = useThemeStore();
  const { showToast } = useToast();
  const router = useRouter();
  const { width } = useWindowDimensions();
  const wide = width >= 1024;
  const [phases, setPhases] = useState<RoadmapPhase[] | null>(null);
  const [adding, setAdding] = useState<Record<string, string>>({});
  const load = useCallback(async () => { try { setPhases((await api.get('/command-center/roadmap')).data.phases); } catch (e: any) { if (bounceIfPrivate(e, router)) return; showToast(detail(e, 'Could not load'), 'error'); } }, []);
  useEffect(() => { load(); }, [load]);
  const cycle = async (it: RoadmapItem) => { try { await api.patch(`/command-center/roadmap/${it.id}`, { status: NEXT[it.status] }); load(); } catch (e: any) { showToast(detail(e, 'Could not update'), 'error'); } };
  const block = (it: RoadmapItem) => api.patch(`/command-center/roadmap/${it.id}`, { status: it.status === 'blocked' ? 'in_progress' : 'blocked' }).then(load);
  const remove = (it: RoadmapItem) => showConfirm('Remove this milestone?', it.title, () => api.delete(`/command-center/roadmap/${it.id}`).then(load), undefined, 'Remove');
  const add = async (phase: string) => {
    const t = (adding[phase] || '').trim(); if (!t) return;
    try { await api.post('/command-center/roadmap', { phase, title: t }); setAdding(a => ({ ...a, [phase]: '' })); load(); } catch (e: any) { showToast(detail(e, 'Could not add'), 'error'); }
  };
  const total = (phases || []).reduce((a, p) => a + p.total, 0);
  const done = (phases || []).reduce((a, p) => a + p.done, 0);

  const Column = ({ ph }: { ph: RoadmapPhase }) => (
    <View style={{ flex: wide ? 1 : undefined, gap: 10 }} {...tid(`cc-phase-${ph.phase}`)}>
      <View style={{ gap: 6 }}>
        <Text style={{ fontSize: 15, fontWeight: '800', color: colors.text }}>{ph.label}</Text>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}><View style={{ flex: 1 }}><Progress pct={ph.pct} colors={colors} testID={`cc-phase-${ph.phase}-progress`} /></View><Text style={{ fontSize: 12, fontWeight: '700', color: colors.textSecondary }} {...tid(`cc-phase-${ph.phase}-count`)}>{ph.done}/{ph.total}</Text></View>
      </View>
      {ph.items.map(it => { const st = ROADMAP_STATUS[it.status]; return (
        <View key={it.id} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: colors.card, borderRadius: 12, borderWidth: 1, borderColor: colors.border, padding: 10 }} {...tid(`cc-milestone-${it.id}`)}>
          <TouchableOpacity onPress={() => cycle(it)} hitSlop={8} {...tid(`cc-milestone-status-${it.id}`)}><Ionicons name={st.icon} size={22} color={st.color} /></TouchableOpacity>
          <View style={{ flex: 1 }}>
            <Text style={{ fontSize: 13.5, color: colors.text, textDecorationLine: it.status === 'done' ? 'line-through' : 'none', opacity: it.status === 'done' ? 0.6 : 1 }}>{it.title}</Text>
            <Text style={{ fontSize: 11.5, color: st.color, fontWeight: '700' }}>{st.label}{it.due ? ` · due ${fmtDay(it.due)}` : ''}{it.owner?.name ? ` · ${it.owner.name.split(' ')[0]}` : ''}</Text>
          </View>
          <TouchableOpacity onPress={() => block(it)} hitSlop={8} {...tid(`cc-milestone-block-${it.id}`)}><Ionicons name="alert-circle-outline" size={16} color={it.status === 'blocked' ? ROADMAP_STATUS.blocked.color : colors.textSecondary} /></TouchableOpacity>
          <TouchableOpacity onPress={() => remove(it)} hitSlop={8} {...tid(`cc-milestone-remove-${it.id}`)}><Ionicons name="close" size={16} color={colors.textSecondary} /></TouchableOpacity>
        </View>
      ); })}
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
        <TextInput value={adding[ph.phase] || ''} onChangeText={(v) => setAdding(a => ({ ...a, [ph.phase]: v }))} onSubmitEditing={() => add(ph.phase)} placeholder="Add a milestone" placeholderTextColor={colors.textSecondary} style={{ flex: 1, height: 40, borderRadius: 12, borderWidth: 1, borderColor: colors.border, paddingHorizontal: 12, color: colors.text, backgroundColor: colors.card, fontSize: 13.5 }} {...tid(`cc-phase-${ph.phase}-add-input`)} />
        <TouchableOpacity onPress={() => add(ph.phase)} style={{ width: 40, height: 40, borderRadius: 20, backgroundColor: (adding[ph.phase] || '').trim() ? GOLD : colors.border, alignItems: 'center', justifyContent: 'center' }} {...tid(`cc-phase-${ph.phase}-add`)}><Ionicons name="add" size={18} color="#1C1C1E" /></TouchableOpacity>
      </View>
    </View>
  );

  return (
    <CcShell title="90-Day Roadmap" subtitle={phases ? `${done} of ${total} milestones done` : undefined} loading={!phases}>
      <Card colors={colors} accent={GOLD} testID="cc-roadmap-summary">
        <Text style={{ fontSize: 13.5, color: colors.text, lineHeight: 19 }}>Package, then validate, then replicate. Tap the circle to move a milestone forward; tap the triangle to flag it blocked. Owner is you unless changed; due dates stay blank until you set them.</Text>
        <Progress pct={total ? Math.round(100 * done / total) : 0} colors={colors} testID="cc-roadmap-progress" />
      </Card>
      {wide ? <View style={{ flexDirection: 'row', gap: 16, alignItems: 'flex-start' }}>{(phases || []).map(ph => <Column key={ph.phase} ph={ph} />)}</View> : (phases || []).map(ph => <Column key={ph.phase} ph={ph} />)}
    </CcShell>
  );
}
