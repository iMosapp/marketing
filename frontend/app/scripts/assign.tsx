import React, { useCallback, useState } from 'react';
import { View, Text, ScrollView, TouchableOpacity, ActivityIndicator, TextInput, Modal, RefreshControl } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import api from '../../services/api';
import { showConfirm } from '../../services/alert';
import { useThemeStore } from '../../store/themeStore';
import { useToast } from '../../components/common/Toast';
import { ScreenHeader, HeaderIconButton } from '../../components/common/ScreenHeader';
import { ScorePill } from '../../components/scorecards/ScoreRing';
import { GOLD, RED, GREEN, tid, fmtDate, type Script, type Assignment } from '../../components/scripts/shared';

type Rep = { id: string; name: string; role: string };
const DUE = [{ l: 'No deadline', d: null }, { l: 'Today', d: 0 }, { l: 'Tomorrow', d: 1 }, { l: '3 days', d: 3 }, { l: '1 week', d: 7 }];

export default function AssignPractice() {
  const router = useRouter();
  const { colors } = useThemeStore();
  const { showToast } = useToast();
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [reps, setReps] = useState<Rep[]>([]);
  const [scripts, setScripts] = useState<Script[]>([]);
  const [loading, setLoading] = useState(true);
  const [sheet, setSheet] = useState(false);
  const [scriptId, setScriptId] = useState<string | null>(null);
  const [picked, setPicked] = useState<string[]>([]);
  const [due, setDue] = useState<number | null>(null);
  const [curveballs, setCurveballs] = useState<string[]>([]);
  const [note, setNote] = useState('');
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      const [a, s] = await Promise.all([api.get('/scripts/mystery-shops/list'), api.get('/scripts')]);
      setAssignments(a.data.assignments || []); setReps(a.data.reps || []); setScripts((s.data.scripts || []).filter((x: Script) => x.kind === 'phone'));
      if (!s.data.can_assign) { showToast('Managers assign practice calls', 'error'); router.back(); }
    } catch (e: any) { showToast(e?.response?.data?.detail || 'Could not load', 'error'); }
    finally { setLoading(false); }
  }, []);
  useFocusEffect(useCallback(() => { load(); }, [load]));

  const create = async () => {
    if (!scriptId) { showToast('Pick a script', 'error'); return; }
    if (!picked.length) { showToast('Pick at least one rep', 'error'); return; }
    setSaving(true);
    try {
      let due_by: string | null = null;
      if (due != null) { const d = new Date(); d.setDate(d.getDate() + due); d.setHours(18, 0, 0, 0); due_by = d.toISOString(); }
      await api.post('/scripts/mystery-shops', { script_id: scriptId, rep_ids: picked, due_by, curveballs: curveballs.filter(c => c.trim()), note: note.trim() });
      showToast(`Assigned to ${picked.length} rep${picked.length === 1 ? '' : 's'}`, 'success');
      setSheet(false); setScriptId(null); setPicked([]); setDue(null); setCurveballs([]); setNote(''); load();
    } catch (e: any) { showToast(e?.response?.data?.detail || 'Could not assign', 'error'); }
    finally { setSaving(false); }
  };
  const cancel = (a: Assignment) => showConfirm('Cancel assignment', `Remove "${a.script_title}" from ${a.rep_ids.length} rep${a.rep_ids.length === 1 ? '' : 's'}? Finished scores stay.`, async () => {
    try { await api.delete(`/scripts/mystery-shops/${a.id}`); setAssignments(p => p.filter(x => x.id !== a.id)); } catch (e: any) { showToast(e?.response?.data?.detail || 'Could not cancel', 'error'); }
  }, undefined, 'Cancel it');

  const toggle = (id: string) => setPicked(p => (p.includes(id) ? p.filter(x => x !== id) : [...p, id]));
  const Label = ({ t }: { t: string }) => <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 1 }}>{t}</Text>;

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      <ScreenHeader title="Assign practice calls" subtitle="Mystery shop your own team" testID="assign-header" right={<HeaderIconButton icon="add-circle" onPress={() => setSheet(true)} testID="assign-new" />} />
      {loading ? <ActivityIndicator style={{ marginTop: 60 }} color={GOLD} /> : (
        <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 60, gap: 12 }} refreshControl={<RefreshControl refreshing={false} onRefresh={load} tintColor={GOLD} />}>
          <Text style={{ fontSize: 13, color: colors.textSecondary, lineHeight: 18 }}>Pick a script and the reps who should run it. Jessi plays the customer, throws your curveballs, and you see every score here.</Text>
          {assignments.length === 0 && (
            <View style={{ backgroundColor: colors.card, borderRadius: 18, padding: 20, alignItems: 'center', gap: 10, borderWidth: 1, borderColor: colors.border }} {...tid('assign-empty')}>
              <Ionicons name="mic-outline" size={36} color={GOLD} />
              <Text style={{ fontSize: 16, fontWeight: '800', color: colors.text }}>No practice calls assigned</Text>
              <Text style={{ fontSize: 13, color: colors.textSecondary, textAlign: 'center' }}>Tap + to send the first one. Reps get a push and it shows at the top of their Scripts screen.</Text>
            </View>
          )}
          {assignments.map(a => {
            const done = Object.keys(a.completed || {}).length;
            return (
              <View key={a.id} style={{ backgroundColor: colors.card, borderRadius: 16, borderWidth: 1, borderColor: colors.border, padding: 14, gap: 10 }} {...tid(`assign-card-${a.id}`)}>
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
                  <View style={{ flex: 1 }}>
                    <Text style={{ fontSize: 15, fontWeight: '800', color: colors.text }}>{a.script_title}</Text>
                    <Text style={{ fontSize: 12, color: colors.textSecondary }}>{done} of {a.rep_ids.length} done{a.due_by ? ` · due ${fmtDate(a.due_by)}` : ''}{a.curveballs.length ? ` · ${a.curveballs.length} curveball${a.curveballs.length === 1 ? '' : 's'}` : ''}</Text>
                  </View>
                  <TouchableOpacity onPress={() => cancel(a)} hitSlop={8} {...tid(`assign-cancel-${a.id}`)}><Ionicons name="trash-outline" size={18} color={RED} /></TouchableOpacity>
                </View>
                {!!a.note && <Text style={{ fontSize: 13, color: colors.text, fontStyle: 'italic' }}>"{a.note}"</Text>}
                <View style={{ gap: 6 }}>
                  {a.rep_ids.map(rid => {
                    const c = a.completed?.[rid];
                    return (
                      <TouchableOpacity key={rid} disabled={!c} onPress={() => c && router.push(`/scripts/result?session=${c.session_id}` as any)} style={{ flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: colors.surface, borderRadius: 10, padding: 8 }} {...tid(`assign-rep-${a.id}-${rid}`)}>
                        <Ionicons name={c ? 'checkmark-circle' : 'time-outline'} size={16} color={c ? GREEN : colors.textSecondary} />
                        <Text style={{ flex: 1, fontSize: 13.5, fontWeight: '700', color: colors.text }}>{a.rep_names?.[rid] || 'Rep'}</Text>
                        {c ? <ScorePill pct={c.score_pct ?? c.adherence_pct} /> : <Text style={{ fontSize: 12, color: colors.textSecondary }}>Not yet</Text>}
                      </TouchableOpacity>
                    );
                  })}
                </View>
              </View>
            );
          })}
        </ScrollView>
      )}

      <Modal visible={sheet} animationType="slide" transparent onRequestClose={() => setSheet(false)}>
        <View style={{ flex: 1, backgroundColor: '#00000088', justifyContent: 'flex-end' }}>
          <View style={{ backgroundColor: colors.bg, borderTopLeftRadius: 24, borderTopRightRadius: 24, maxHeight: '92%' }} {...tid('assign-sheet')}>
            <View style={{ flexDirection: 'row', alignItems: 'center', padding: 16, gap: 12 }}>
              <Text style={{ flex: 1, fontSize: 18, fontWeight: '800', color: colors.text }}>New practice call</Text>
              <TouchableOpacity onPress={() => setSheet(false)} {...tid('assign-sheet-close')}><Ionicons name="close" size={24} color={colors.text} /></TouchableOpacity>
            </View>
            <ScrollView contentContainerStyle={{ paddingHorizontal: 16, paddingBottom: 30, gap: 16 }} keyboardShouldPersistTaps="handled">
              <View style={{ gap: 8 }}>
                <Label t="SCRIPT" />
                {scripts.map(s => (
                  <TouchableOpacity key={s.id} onPress={() => setScriptId(s.id)} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, padding: 12, borderRadius: 12, backgroundColor: scriptId === s.id ? GOLD + '22' : colors.card, borderWidth: 1, borderColor: scriptId === s.id ? GOLD : colors.border }} {...tid(`assign-script-${s.id}`)}>
                    <Ionicons name={scriptId === s.id ? 'radio-button-on' : 'radio-button-off'} size={18} color={scriptId === s.id ? GOLD : colors.textSecondary} />
                    <View style={{ flex: 1 }}><Text style={{ fontSize: 14, fontWeight: '700', color: colors.text }}>{s.title}</Text><Text style={{ fontSize: 11.5, color: colors.textSecondary }}>{s.category}{s.persona ? ` · with ${s.persona.name}` : ''}</Text></View>
                  </TouchableOpacity>
                ))}
              </View>
              <View style={{ gap: 8 }}>
                <Label t="REPS" />
                {reps.length === 0 && <Text style={{ fontSize: 13, color: colors.textSecondary }}>No reps on your store yet.</Text>}
                <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
                  {reps.map(r => (
                    <TouchableOpacity key={r.id} onPress={() => toggle(r.id)} style={{ paddingHorizontal: 12, height: 36, borderRadius: 18, backgroundColor: picked.includes(r.id) ? GOLD : colors.card, borderWidth: 1, borderColor: picked.includes(r.id) ? GOLD : colors.border, justifyContent: 'center', flexDirection: 'row', alignItems: 'center', gap: 6 }} {...tid(`assign-rep-pick-${r.id}`)}>
                      {picked.includes(r.id) && <Ionicons name="checkmark" size={14} color="#111" />}
                      <Text style={{ fontSize: 13, fontWeight: '800', color: picked.includes(r.id) ? '#111' : colors.text }}>{r.name}</Text>
                    </TouchableOpacity>
                  ))}
                </View>
                {reps.length > 1 && <TouchableOpacity onPress={() => setPicked(picked.length === reps.length ? [] : reps.map(r => r.id))} {...tid('assign-rep-all')}><Text style={{ fontSize: 12.5, fontWeight: '800', color: GOLD }}>{picked.length === reps.length ? 'Clear all' : 'Everyone'}</Text></TouchableOpacity>}
              </View>
              <View style={{ gap: 8 }}>
                <Label t="DUE" />
                <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
                  {DUE.map(o => (
                    <TouchableOpacity key={o.l} onPress={() => setDue(o.d)} style={{ paddingHorizontal: 12, height: 32, borderRadius: 16, backgroundColor: due === o.d ? GOLD : colors.card, borderWidth: 1, borderColor: due === o.d ? GOLD : colors.border, justifyContent: 'center' }} {...tid(`assign-due-${o.d ?? 'none'}`)}>
                      <Text style={{ fontSize: 12.5, fontWeight: '800', color: due === o.d ? '#111' : colors.text }}>{o.l}</Text>
                    </TouchableOpacity>
                  ))}
                </View>
              </View>
              <View style={{ gap: 8 }}>
                <Label t="CURVEBALLS (OPTIONAL, UP TO 5)" />
                <Text style={{ fontSize: 12.5, color: colors.textSecondary, lineHeight: 17 }}>Extra things the customer will bring up, like "my credit is rough" or "I already have a quote from the store across town".</Text>
                {curveballs.map((c, i) => (
                  <View key={i} style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                    <TextInput value={c} onChangeText={v => setCurveballs(curveballs.map((x, j) => (j === i ? v : x)))} placeholder="They mention a competitor's quote" placeholderTextColor={colors.textSecondary} style={{ flex: 1, height: 44, backgroundColor: colors.card, borderRadius: 12, borderWidth: 1, borderColor: colors.border, paddingHorizontal: 12, color: colors.text, fontSize: 14 }} {...tid(`assign-curveball-${i}`)} />
                    <TouchableOpacity onPress={() => setCurveballs(curveballs.filter((_, j) => j !== i))} {...tid(`assign-curveball-remove-${i}`)}><Ionicons name="close-circle" size={22} color={colors.textSecondary} /></TouchableOpacity>
                  </View>
                ))}
                {curveballs.length < 5 && <TouchableOpacity onPress={() => setCurveballs([...curveballs, ''])} style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }} {...tid('assign-curveball-add')}><Ionicons name="add-circle-outline" size={18} color={GOLD} /><Text style={{ fontSize: 13, fontWeight: '800', color: GOLD }}>Add a curveball</Text></TouchableOpacity>}
              </View>
              <View style={{ gap: 8 }}>
                <Label t="NOTE TO REPS (OPTIONAL)" />
                <TextInput value={note} onChangeText={setNote} placeholder="Focus on offering two appointment times" placeholderTextColor={colors.textSecondary} style={{ height: 44, backgroundColor: colors.card, borderRadius: 12, borderWidth: 1, borderColor: colors.border, paddingHorizontal: 12, color: colors.text, fontSize: 14 }} {...tid('assign-note')} />
              </View>
              <TouchableOpacity onPress={create} disabled={saving} style={{ height: 52, borderRadius: 14, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 8 }} {...tid('assign-submit')}>
                {saving ? <ActivityIndicator color="#111" /> : <><Ionicons name="paper-plane" size={18} color="#111" /><Text style={{ fontSize: 15, fontWeight: '800', color: '#111' }}>Send to {picked.length || ''} rep{picked.length === 1 ? '' : 's'}</Text></>}
              </TouchableOpacity>
            </ScrollView>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}
