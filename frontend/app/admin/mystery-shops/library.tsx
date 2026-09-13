import React, { useCallback, useState } from 'react';
import { View, Text, ScrollView, TouchableOpacity } from 'react-native';
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
import { GOLD, PURPLE, tid, type Challenge, type ChallengeDraft } from '../../../components/mystery-shops/shared';

// The global challenge library: what every client's shopper (and every course) draws from.
export default function ChallengeLibrary() {
  const { colors } = useThemeStore();
  const { showToast } = useToast();
  const [rows, setRows] = useState<Challenge[] | null>(null);
  const [open, setOpen] = useState<Challenge | null>(null);
  const [editor, setEditor] = useState<null | { existing?: Challenge; draft?: ChallengeDraft }>(null);
  const [generator, setGenerator] = useState(false);

  const load = useCallback(async () => { try { const r = await api.get('/shop-clients/challenges'); setRows(r.data.challenges); } catch { setRows([]); } }, []);
  useFocusEffect(useCallback(() => { load(); }, [load]));

  const remove = (c: Challenge) => showConfirm('Hide this challenge?', 'It disappears from every client\'s pool and from the Quick shop picker.', async () => {
    try { await api.delete(`/shop-clients/challenges/${c.id}`); setOpen(null); load(); } catch (e: any) { showToast(e?.response?.data?.detail || 'Could not remove', 'error'); }
  }, undefined, 'Hide');

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      <ScreenHeader title="Challenge Library" subtitle={rows ? `${rows.length} challenges every client draws from` : undefined} testID="library-header" right={<HeaderIconButton icon="add-circle" onPress={() => setEditor({})} testID="library-add" />} />
      <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 60, gap: 16 }}>
        <TouchableOpacity onPress={() => setGenerator(true)} style={{ flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: GOLD, borderRadius: 16, padding: 14 }} {...tid('library-generate')}>
          <View style={{ width: 40, height: 40, borderRadius: 12, backgroundColor: '#11111122', alignItems: 'center', justifyContent: 'center' }}><Ionicons name="sparkles" size={20} color="#111" /></View>
          <View style={{ flex: 1 }}>
            <Text style={{ fontSize: 15.5, fontWeight: '800', color: '#111' }}>Describe a scenario, Jessi writes it</Text>
            <Text style={{ fontSize: 12.5, color: '#111111AA' }}>Sales, service, parts or rental. One to five variations at a time.</Text>
          </View>
          <Ionicons name="chevron-forward" size={18} color="#111" />
        </TouchableOpacity>
        <TouchableOpacity onPress={() => setEditor({})} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: colors.card, borderRadius: 14, padding: 12, borderWidth: 1, borderColor: colors.border }} {...tid('library-write')}>
          <Ionicons name="create-outline" size={18} color={PURPLE} />
          <Text style={{ flex: 1, fontSize: 14, fontWeight: '700', color: colors.text }}>Write one by hand or paste a script</Text>
          <Ionicons name="chevron-forward" size={16} color={colors.textSecondary} />
        </TouchableOpacity>
        <ChallengeGroups rows={rows} colors={colors} onOpen={setOpen} emptyHint="Nothing for this department yet." />
      </ScrollView>
      <ChallengeDetailSheet open={open} onClose={() => setOpen(null)} colors={colors} onEdit={(c) => { setOpen(null); setEditor({ existing: c }); }} onDelete={remove} />
      <ChallengeEditorSheet visible={!!editor} onClose={() => setEditor(null)} colors={colors} existing={editor?.existing} initial={editor?.draft} onSaved={load} />
      <GeneratorSheet visible={generator} onClose={() => setGenerator(false)} colors={colors} onSaved={load} onEditDraft={(d) => { setGenerator(false); setEditor({ draft: d }); }} />
    </SafeAreaView>
  );
}
