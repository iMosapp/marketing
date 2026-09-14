import React, { useCallback, useState } from 'react';
import { View, Text, ScrollView, TouchableOpacity, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useFocusEffect } from 'expo-router';
import api from '../../../services/api';
import { useThemeStore } from '../../../store/themeStore';
import { ScreenHeader, HeaderIconButton } from '../../../components/common/ScreenHeader';
import { showConfirm } from '../../../services/alert';
import { useToast } from '../../../components/common/Toast';
import { ChallengeEditorSheet } from '../../../components/mystery-shops/ChallengeEditorSheet';
import { ChallengeDetailSheet, ChallengeGroups } from '../../../components/mystery-shops/ChallengeDetailSheet';
import { GeneratorSheet } from '../../../components/mystery-shops/GeneratorSheet';
import { Chip, GOLD, PURPLE, tid, afterModal, industries, industryOf, deptsFor, loadIndustries, type Challenge, type ChallengeDraft, type Dept, type Industry } from '../../../components/mystery-shops/shared';

// The global challenge library: what every client's caller (and every course) draws from, one industry at a time.
export default function ChallengeLibrary() {
  const { colors } = useThemeStore();
  const { showToast } = useToast();
  const [rows, setRows] = useState<Challenge[] | null>(null);
  const [inds, setInds] = useState<Industry[]>(industries());
  const [industry, setIndustry] = useState('automotive');
  const [open, setOpen] = useState<Challenge | null>(null);
  const [editor, setEditor] = useState<null | { existing?: Challenge; draft?: ChallengeDraft }>(null);
  const [generator, setGenerator] = useState(false);
  const [seeding, setSeeding] = useState<string | null>(null);

  const load = useCallback(async () => {
    try { const r = await api.get('/shop-clients/challenges'); setRows(r.data.challenges); } catch { setRows([]); }
    try { setInds(await loadIndustries(true)); } catch {}
  }, []);
  useFocusEffect(useCallback(() => { load(); }, [load]));

  const pack = industryOf(industry);
  const depts = deptsFor(industry);
  const mine = (rows || []).filter(r => depts.some(d => d.key === r.department));
  const missing = depts.filter(d => !mine.some(r => r.department === d.key));

  const remove = (c: Challenge) => showConfirm('Hide this challenge?', 'It disappears from every client\'s pool and from the Quick shop picker.', async () => {
    try { await api.delete(`/shop-clients/challenges/${c.id}`); setOpen(null); load(); } catch (e: any) { showToast(e?.response?.data?.detail || 'Could not remove', 'error'); }
  }, undefined, 'Hide');

  // Jessi writes 2 starter challenges per empty department, one department per request so nothing times out.
  const seed = async (only?: Dept) => {
    const targets = only ? [only] : missing;
    if (!targets.length) return;
    setSeeding(only ? only.key : 'all');
    let made = 0;
    try {
      for (const d of targets) { const r = await api.post('/shop-clients/challenges/seed', { industry, department: d.key }, { timeout: 180000 }); made += (r.data.created || []).length; }
      showToast(made ? `Jessi wrote ${made} starter challenge${made === 1 ? '' : 's'}` : 'Nothing to write, those departments already have starters', 'success');
      load();
    } catch (e: any) { showToast(e?.response?.data?.detail || 'Jessi could not finish, try again', 'error'); load(); }
    finally { setSeeding(null); }
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      <ScreenHeader title="Challenge Library" subtitle={rows ? `${rows.length} challenges across ${inds.length} industries` : undefined} testID="library-header" right={<HeaderIconButton icon="add-circle" onPress={() => setEditor({})} testID="library-add" />} />
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ paddingHorizontal: 16, gap: 6, paddingVertical: 8 }} style={{ flexGrow: 0, flexShrink: 0 }}>
        {inds.map(i => { const n = (rows || []).filter(r => i.departments.some(d => d.key === r.department)).length; return <Chip key={i.key} label={`${i.label}${rows ? ` · ${n}` : ''}`} small active={industry === i.key} onPress={() => setIndustry(i.key)} colors={colors} testID={`library-industry-${i.key}`} />; })}
      </ScrollView>
      <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 60, gap: 16 }}>
        <TouchableOpacity onPress={() => setGenerator(true)} style={{ flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: GOLD, borderRadius: 16, padding: 14 }} {...tid('library-generate')}>
          <View style={{ width: 40, height: 40, borderRadius: 12, backgroundColor: '#11111122', alignItems: 'center', justifyContent: 'center' }}><Ionicons name="sparkles" size={20} color="#111" /></View>
          <View style={{ flex: 1 }}>
            <Text style={{ fontSize: 15.5, fontWeight: '800', color: '#111' }}>Describe a scenario, Jessi writes it</Text>
            <Text style={{ fontSize: 12.5, color: '#111111AA' }}>{depts.map(d => d.label).join(', ')}. One to five variations at a time.</Text>
          </View>
          <Ionicons name="chevron-forward" size={18} color="#111" />
        </TouchableOpacity>
        <TouchableOpacity onPress={() => setEditor({})} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: colors.card, borderRadius: 14, padding: 12, borderWidth: 1, borderColor: colors.border }} {...tid('library-write')}>
          <Ionicons name="create-outline" size={18} color={PURPLE} />
          <Text style={{ flex: 1, fontSize: 14, fontWeight: '700', color: colors.text }}>Write one by hand or paste a script</Text>
          <Ionicons name="chevron-forward" size={16} color={colors.textSecondary} />
        </TouchableOpacity>
        {rows !== null && missing.length > 0 && (
          <TouchableOpacity onPress={() => seed()} disabled={!!seeding} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: PURPLE + '1A', borderRadius: 14, padding: 12, borderWidth: 1, borderColor: PURPLE + '66', opacity: seeding ? 0.7 : 1 }} {...tid('library-seed')}>
            {seeding === 'all' ? <ActivityIndicator color={PURPLE} /> : <Ionicons name="color-wand-outline" size={18} color={PURPLE} />}
            <View style={{ flex: 1 }}>
              <Text style={{ fontSize: 14, fontWeight: '700', color: colors.text }}>{seeding === 'all' ? `Jessi is writing ${pack.label.toLowerCase()} starters…` : `Let Jessi write the ${pack.label.toLowerCase()} starters`}</Text>
              <Text style={{ fontSize: 12, color: colors.textSecondary }}>Two everyday scenarios for each empty department: {missing.map(d => d.label.toLowerCase()).join(', ')}. About 30 seconds each.</Text>
            </View>
          </TouchableOpacity>
        )}
        <ChallengeGroups rows={rows === null ? null : mine} colors={colors} onOpen={setOpen} departments={depts} renderEmpty={(d) => (
          <TouchableOpacity onPress={() => seed(d)} disabled={!!seeding} style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }} {...tid(`library-seed-${d.key}`)}>
            {seeding === d.key ? <ActivityIndicator size="small" color={PURPLE} /> : <Ionicons name="color-wand-outline" size={14} color={PURPLE} />}
            <Text style={{ fontSize: 12.5, fontWeight: '700', color: PURPLE }}>{seeding === d.key ? 'Jessi is writing…' : `Nothing yet. Have Jessi write two ${d.label.toLowerCase()} starters`}</Text>
          </TouchableOpacity>
        )} />
      </ScrollView>
      <ChallengeDetailSheet open={open} onClose={() => setOpen(null)} colors={colors} onEdit={(c) => { setOpen(null); afterModal(() => setEditor({ existing: c })); }} onDelete={remove} />
      <ChallengeEditorSheet visible={!!editor} onClose={() => setEditor(null)} colors={colors} existing={editor?.existing} initial={editor?.draft} scope={{ industry }} onSaved={load} />
      <GeneratorSheet visible={generator} onClose={() => setGenerator(false)} colors={colors} scope={{ industry }} onSaved={load} onEditDraft={(d) => { setGenerator(false); afterModal(() => setEditor({ draft: d })); }} />
    </SafeAreaView>
  );
}
