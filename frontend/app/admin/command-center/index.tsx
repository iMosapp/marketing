import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, useWindowDimensions } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import api from '../../../services/api';
import { showConfirm } from '../../../services/alert';
import { useThemeStore } from '../../../store/themeStore';
import { useToast } from '../../../components/common/Toast';
import { CcShell, Card, Eyebrow, Progress, Pill, Empty } from '../../../components/command-center/CcShell';
import { CaptureBar } from '../../../components/command-center/CaptureBar';
import { ObjectiveSheet, PrioritySheet, ReplaceSheet, NextActionSheet, NoteSheet, SmallAction } from '../../../components/command-center/FocusSheets';
import { GOLD, GREEN, RED, OBJECTIVE_STATUS, PILLAR_COLOR, fmtDay, detail, tid, type Focus, type Priority } from '../../../components/command-center/shared';

// FOUNDER FOCUS: the daily briefing. One objective, three priorities, one next action, what you wait on, what you won, and a place to drop ideas.
export default function FounderFocus() {
  const { colors } = useThemeStore();
  const { showToast } = useToast();
  const router = useRouter();
  const { width } = useWindowDimensions();
  const wide = width >= 1024;
  const [f, setF] = useState<Focus | null>(null);
  const [sheet, setSheet] = useState<'objective' | 'priority' | 'next' | 'waiting' | 'win' | null>(null);
  const [editing, setEditing] = useState<Priority | null>(null);
  const [replace, setReplace] = useState<{ incoming: Priority; active: Priority[] } | null>(null);
  const [showMore, setShowMore] = useState(false);

  const load = useCallback(async () => {
    try { setF((await api.get('/command-center/focus')).data); }
    catch (e: any) { showToast(detail(e, 'Could not load'), 'error'); if (e?.response?.status === 403) router.back(); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const openPriority = (p: Priority | null) => { setEditing(p); setSheet('priority'); };
  const doneNote = (id: string) => api.patch(`/command-center/notes/${id}`, { status: 'done' }).then(load);
  const removeNote = (id: string) => api.delete(`/command-center/notes/${id}`).then(load);
  const clearNext = () => showConfirm('Clear the next action?', 'You can set a new one any time.', () => api.delete('/command-center/next-action').then(() => { showToast('Cleared'); load(); }), undefined, 'Clear');

  const ob = f?.objective?.data;
  const na = f?.next_action?.data;
  const obSt = OBJECTIVE_STATUS[ob?.status || 'proposed'] || OBJECTIVE_STATUS.proposed;
  const slots = [0, 1, 2].map(i => (f?.active || []).find(p => p.slot === i + 1) || null);

  const Left = (
    <View style={{ flex: 1, gap: 20 }}>
      <Card colors={colors} accent={GOLD} testID="cc-objective" onPress={() => setSheet('objective')}>
        <Eyebrow t="THE ONE BIG THING" colors={colors} right={<Pill text={obSt.label} color={obSt.color} testID="cc-objective-status" />} />
        <Text style={{ fontSize: wide ? 26 : 22, fontWeight: '800', color: colors.text, lineHeight: wide ? 34 : 29, letterSpacing: -0.3 }} {...tid('cc-objective-title')}>{ob?.title || 'Set the one objective that matters most right now.'}</Text>
        {!!ob?.why && <Text style={{ fontSize: 14, color: colors.textSecondary, lineHeight: 20 }} {...tid('cc-objective-why')}>{ob.why}</Text>}
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
          <View style={{ flex: 1 }}><Progress pct={ob?.progress_pct || 0} colors={colors} testID="cc-objective-progress" /></View>
          <Text style={{ fontSize: 12.5, fontWeight: '700', color: colors.textSecondary }} {...tid('cc-objective-meta')}>{ob?.progress_pct || 0}%{ob?.target_date ? ` · target ${fmtDay(ob.target_date)}` : ' · no target date yet'}</Text>
        </View>
      </Card>

      <View style={{ gap: 10 }}>
        <Eyebrow t="MY THREE PRIORITIES" colors={colors} right={<SmallAction label="+ Propose" onPress={() => openPriority(null)} colors={colors} testID="cc-priority-propose" />} />
        {slots.map((p, i) => p ? (
          <Card key={p.id} colors={colors} accent={PILLAR_COLOR[p.pillar] || GOLD} testID={`cc-slot-${i + 1}`} onPress={() => openPriority(p)}>
            <View style={{ flexDirection: 'row', alignItems: 'flex-start', gap: 12 }}>
              <View style={{ width: 30, height: 30, borderRadius: 15, backgroundColor: (PILLAR_COLOR[p.pillar] || GOLD) + '33', alignItems: 'center', justifyContent: 'center' }}><Text style={{ fontSize: 13, fontWeight: '800', color: PILLAR_COLOR[p.pillar] || GOLD }}>{i + 1}</Text></View>
              <View style={{ flex: 1, gap: 6 }}>
                <Text style={{ fontSize: 16, fontWeight: '800', color: colors.text, lineHeight: 22 }} {...tid(`cc-slot-${i + 1}-title`)}>{p.title}</Text>
                {!!p.next_action && <Text style={{ fontSize: 13.5, color: colors.text, lineHeight: 19 }} {...tid(`cc-slot-${i + 1}-next`)}><Text style={{ fontWeight: '800', color: colors.textSecondary }}>Next: </Text>{p.next_action}</Text>}
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
                  <View style={{ flex: 1 }}><Progress pct={p.progress_pct} color={PILLAR_COLOR[p.pillar] || GOLD} colors={colors} /></View>
                  <Text style={{ fontSize: 12, fontWeight: '700', color: colors.textSecondary }}>{p.progress_pct}%{p.due ? ` · due ${fmtDay(p.due)}` : ''}{p.owner?.name ? ` · ${p.owner.name.split(' ')[0]}` : ''}</Text>
                </View>
                {!!p.definition_of_done && <Text style={{ fontSize: 12.5, color: colors.textSecondary, lineHeight: 17 }} numberOfLines={2}><Text style={{ fontWeight: '800' }}>Done when: </Text>{p.definition_of_done}</Text>}
              </View>
            </View>
          </Card>
        ) : (
          <TouchableOpacity key={`empty-${i}`} onPress={() => openPriority(null)} style={{ borderRadius: 18, borderWidth: 1, borderStyle: 'dashed', borderColor: colors.border, padding: 16, flexDirection: 'row', alignItems: 'center', gap: 10 }} {...tid(`cc-slot-${i + 1}-empty`)}>
            <View style={{ width: 30, height: 30, borderRadius: 15, borderWidth: 1, borderColor: colors.border, alignItems: 'center', justifyContent: 'center' }}><Text style={{ fontSize: 13, fontWeight: '800', color: colors.textSecondary }}>{i + 1}</Text></View>
            <Text style={{ fontSize: 14, color: colors.textSecondary }}>Open slot. {f?.proposed?.length ? 'Activate a proposed priority or propose a new one.' : 'Propose a priority.'}</Text>
          </TouchableOpacity>
        ))}
        {!!(f?.proposed?.length || f?.paused?.length) && (
          <View style={{ gap: 6 }}>
            <TouchableOpacity onPress={() => setShowMore(v => !v)} style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }} {...tid('cc-more-toggle')}>
              <Ionicons name={showMore ? 'chevron-down' : 'chevron-forward'} size={14} color={colors.textSecondary} />
              <Text style={{ fontSize: 12.5, fontWeight: '700', color: colors.textSecondary }}>{(f?.proposed?.length || 0)} proposed · {(f?.paused?.length || 0)} paused</Text>
            </TouchableOpacity>
            {showMore && [...(f?.proposed || []), ...(f?.paused || [])].map(p => (
              <TouchableOpacity key={p.id} onPress={() => openPriority(p)} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 8, paddingHorizontal: 12, borderRadius: 12, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border }} {...tid(`cc-pending-${p.id}`)}>
                <Pill text={p.status} color={p.status === 'paused' ? GOLD : colors.textSecondary} />
                <Text style={{ flex: 1, fontSize: 13.5, color: colors.text }} numberOfLines={1}>{p.title}</Text>
                <Ionicons name="chevron-forward" size={14} color={colors.textSecondary} />
              </TouchableOpacity>
            ))}
          </View>
        )}
      </View>

      <Card colors={colors} accent={na?.text ? GREEN : colors.border} testID="cc-next-action" onPress={() => setSheet('next')}>
        <Eyebrow t="NEXT BEST ACTION" colors={colors} right={na?.text ? <SmallAction label="Clear" onPress={clearNext} colors={colors} testID="cc-next-clear" color={RED} /> : undefined} />
        <Text style={{ fontSize: 17, fontWeight: '700', color: na?.text ? colors.text : colors.textSecondary, lineHeight: 24 }} {...tid('cc-next-text')}>{na?.text || 'What is the one thing that moves the business forward today? Tap to set it.'}</Text>
        {!!na?.why && <Text style={{ fontSize: 13, color: colors.textSecondary, lineHeight: 18 }} {...tid('cc-next-why')}>Why: {na.why}</Text>}
      </Card>
    </View>
  );

  const Right = (
    <View style={{ width: wide ? 360 : undefined, gap: 20 }}>
      {!wide && <CaptureBar colors={colors} onCaptured={load} />}
      {wide && <CaptureBar colors={colors} onCaptured={load} />}
      <View style={{ gap: 8 }}>
        <Eyebrow t={`WAITING ON${f?.waiting?.length ? ` · ${f.waiting.length}` : ''}`} colors={colors} right={<SmallAction label="+ Add" onPress={() => setSheet('waiting')} colors={colors} testID="cc-waiting-add" />} />
        {!f?.waiting?.length ? <Empty t="Nothing blocking you right now." colors={colors} testID="cc-waiting-empty" /> : f.waiting.map(n => (
          <View key={n.id} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: colors.card, borderRadius: 12, borderWidth: 1, borderColor: colors.border, padding: 12 }} {...tid(`cc-waiting-${n.id}`)}>
            <Ionicons name="hourglass-outline" size={16} color={GOLD} />
            <View style={{ flex: 1 }}><Text style={{ fontSize: 13.5, color: colors.text }}>{n.title}</Text><Text style={{ fontSize: 12, color: colors.textSecondary }}>{n.party ? `${n.party} · ` : ''}since {fmtDay(n.created_at)}{n.due ? ` · needed by ${fmtDay(n.due)}` : ''}</Text></View>
            <TouchableOpacity onPress={() => doneNote(n.id)} hitSlop={8} {...tid(`cc-waiting-done-${n.id}`)}><Ionicons name="checkmark-circle-outline" size={20} color={GREEN} /></TouchableOpacity>
          </View>
        ))}
      </View>
      <View style={{ gap: 8 }}>
        <Eyebrow t="THIS WEEK'S WINS" colors={colors} right={<SmallAction label="+ Add" onPress={() => setSheet('win')} colors={colors} testID="cc-win-add" />} />
        {!f?.wins?.length ? <Empty t="Record the first one. Small counts." colors={colors} testID="cc-wins-empty" /> : f.wins.map(n => (
          <View key={n.id} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 6 }} {...tid(`cc-win-${n.id}`)}>
            <Ionicons name="checkmark-circle" size={16} color={GREEN} />
            <Text style={{ flex: 1, fontSize: 13.5, color: colors.text }}>{n.title}</Text>
            <Text style={{ fontSize: 12, color: colors.textSecondary }}>{fmtDay(n.created_at)}</Text>
            <TouchableOpacity onPress={() => removeNote(n.id)} hitSlop={8} {...tid(`cc-win-remove-${n.id}`)}><Ionicons name="close" size={14} color={colors.textSecondary} /></TouchableOpacity>
          </View>
        ))}
      </View>
      {!!f?.ideas_new_week && <TouchableOpacity onPress={() => router.push('/admin/command-center/ideas' as any)} {...tid('cc-ideas-link')}><Text style={{ fontSize: 12.5, color: colors.textSecondary }}>{f.ideas_new_week} idea{f.ideas_new_week === 1 ? '' : 's'} captured this week · open the vault</Text></TouchableOpacity>}
    </View>
  );

  return (
    <CcShell title="Founder Focus" subtitle={f ? `${f.active.length} of ${f.slots} priorities active` : undefined} loading={!f}>
      {wide ? <View style={{ flexDirection: 'row', gap: 24, alignItems: 'flex-start' }}>{Left}{Right}</View> : <>{Left}{Right}</>}
      <ObjectiveSheet visible={sheet === 'objective'} onClose={() => setSheet(null)} colors={colors} onSaved={load} focus={f} />
      <PrioritySheet visible={sheet === 'priority'} onClose={() => setSheet(null)} colors={colors} onSaved={load} focus={f} priority={editing} onReplace={(p, active) => setReplace({ incoming: p, active })} />
      <ReplaceSheet visible={!!replace} onClose={() => setReplace(null)} colors={colors} onSaved={load} incoming={replace?.incoming || null} active={replace?.active || []} />
      <NextActionSheet visible={sheet === 'next'} onClose={() => setSheet(null)} colors={colors} onSaved={load} current={na || null} />
      <NoteSheet visible={sheet === 'waiting'} onClose={() => setSheet(null)} colors={colors} onSaved={load} kind="waiting" />
      <NoteSheet visible={sheet === 'win'} onClose={() => setSheet(null)} colors={colors} onSaved={load} kind="win" />
    </CcShell>
  );
}
