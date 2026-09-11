import React, { useCallback, useState } from 'react';
import { View, Text, ScrollView, TouchableOpacity, ActivityIndicator, RefreshControl, Modal } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import api from '../../services/api';
import { showConfirm } from '../../services/alert';
import { useAuthStore } from '../../store/authStore';
import { useThemeStore } from '../../store/themeStore';
import { useToast } from '../../components/common/Toast';
import { ScreenHeader, HeaderIconButton } from '../../components/common/ScreenHeader';
import { GOLD, RED, tid, scoreTone, type Scorecard } from '../../components/scorecards/shared';

type Template = { key: string; name: string; department: string; description: string; criteria_count: number };

export default function ScorecardsLibrary() {
  const router = useRouter();
  const { user } = useAuthStore();
  const { colors } = useThemeStore();
  const { showToast } = useToast();
  const [cards, setCards] = useState<Scorecard[]>([]);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [names, setNames] = useState<Record<string, string>>({});
  const [canManage, setCanManage] = useState(false);
  const [loading, setLoading] = useState(true);
  const [picker, setPicker] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const res = await api.get('/scorecards');
      setCards(res.data.scorecards || []); setTemplates(res.data.templates || []); setCanManage(!!res.data.can_manage);
      const n: Record<string, string> = {};
      (res.data.reps || []).forEach((r: any) => { n[r._id] = (r.name || '').split(' ')[0]; });
      (res.data.inboxes || []).forEach((i: any) => { n[i.id] = `${i.name} inbox`; });
      (res.data.sources || []).forEach((s: any) => { n[s.id] = s.name; });
      setNames(n);
      if (!res.data.can_manage) router.replace('/scorecards/my' as any);
    } catch (e: any) { showToast(e?.response?.data?.detail || 'Could not load scorecards', 'error'); }
    finally { setLoading(false); }
  }, []);
  useFocusEffect(useCallback(() => { if (user?._id) load(); }, [user?._id, load]));

  const create = async (key: string | null) => {
    setBusy(key || 'blank');
    try {
      const res = await api.post('/scorecards', key ? { template_key: key } : { name: 'New scorecard', criteria: [] });
      setPicker(false); router.push(`/scorecards/${res.data.id}` as any);
    } catch (e: any) { showToast(e?.response?.data?.detail || 'Could not create', 'error'); }
    finally { setBusy(null); }
  };
  const duplicate = async (c: Scorecard) => {
    setBusy(c.id);
    try { const res = await api.post(`/scorecards/${c.id}/duplicate`); setCards(p => [...p, res.data]); showToast(`Copied "${c.name}"`, 'success'); }
    catch (e: any) { showToast(e?.response?.data?.detail || 'Could not duplicate', 'error'); }
    finally { setBusy(null); }
  };
  const remove = (c: Scorecard) => showConfirm('Delete scorecard', `Delete "${c.name}"? Calls already graded keep their scores.`, async () => {
    try { await api.delete(`/scorecards/${c.id}`); setCards(p => p.filter(x => x.id !== c.id)); showToast('Scorecard deleted', 'success'); }
    catch (e: any) { showToast(e?.response?.data?.detail || 'Could not delete', 'error'); }
  }, undefined, 'Delete');

  const appliesLabel = (c: Scorecard) => {
    const bits = [...c.applies_to.inbox_ids, ...c.applies_to.user_ids, ...c.applies_to.source_ids].map(id => names[id]).filter(Boolean);
    if (c.is_default) bits.unshift('Every call by default');
    return bits.length ? bits.join(' · ') : 'Not applied to anyone yet';
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      <ScreenHeader title="Scorecards" subtitle="What every call gets graded on" testID="scorecards-header"
        right={canManage ? <HeaderIconButton icon="add-circle" onPress={() => setPicker(true)} testID="scorecards-add" /> : undefined} />
      {loading ? <ActivityIndicator style={{ marginTop: 60 }} color={GOLD} /> : (
        <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 60, gap: 12 }} refreshControl={<RefreshControl refreshing={false} onRefresh={load} tintColor={GOLD} />}>
          <Text style={{ fontSize: 13, color: colors.textSecondary, lineHeight: 18 }}>
            A minute after any recorded call, Jessi grades it against the scorecard that applies: pass or fail per item, a summary, coaching tips. Critical misses ping the managers.
          </Text>
          <TouchableOpacity onPress={() => router.push('/scorecards/team' as any)} style={{ backgroundColor: GOLD, borderRadius: 16, padding: 14, flexDirection: 'row', alignItems: 'center', gap: 12 }} {...tid('scorecards-team-link')}>
            <Ionicons name="podium" size={22} color="#111" />
            <View style={{ flex: 1 }}><Text style={{ fontSize: 15, fontWeight: '800', color: '#111' }}>Team Call Scores</Text><Text style={{ fontSize: 12, color: '#111', opacity: 0.75 }}>Leaderboard, who misses what, critical-miss alerts</Text></View>
            <Ionicons name="chevron-forward" size={18} color="#111" />
          </TouchableOpacity>

          {cards.length === 0 && (
            <View style={{ backgroundColor: colors.card, borderRadius: 18, padding: 20, alignItems: 'center', gap: 10, borderWidth: 1, borderColor: colors.border }} {...tid('scorecards-empty')}>
              <Ionicons name="clipboard-outline" size={36} color={GOLD} />
              <Text style={{ fontSize: 16, fontWeight: '800', color: colors.text }}>No scorecards yet</Text>
              <Text style={{ fontSize: 13, color: colors.textSecondary, textAlign: 'center' }}>Start from a proven template for Internet Sales, Service BDC or Phone-Ups.</Text>
            </View>
          )}
          {cards.map(c => (
            <View key={c.id} style={{ backgroundColor: colors.card, borderRadius: 18, borderWidth: 1, borderColor: colors.border, padding: 16, gap: 10 }} {...tid(`scorecard-card-${c.id}`)}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
                <View style={{ width: 38, height: 38, borderRadius: 12, backgroundColor: GOLD + '22', alignItems: 'center', justifyContent: 'center' }}><Ionicons name="clipboard" size={18} color={GOLD} /></View>
                <View style={{ flex: 1 }}>
                  <Text style={{ fontSize: 16, fontWeight: '800', color: colors.text }} {...tid(`scorecard-name-${c.id}`)}>{c.name}</Text>
                  <Text style={{ fontSize: 12, color: colors.textSecondary }}>{c.department || 'No department'} · {c.criteria.length} criteria · {c.critical_count} critical</Text>
                </View>
                {c.is_default && <View style={{ paddingHorizontal: 8, paddingVertical: 3, borderRadius: 8, backgroundColor: GOLD + '22' }}><Text style={{ fontSize: 10, fontWeight: '800', color: GOLD }}>DEFAULT</Text></View>}
              </View>
              {c.description ? <Text style={{ fontSize: 13, color: colors.textSecondary, lineHeight: 18 }}>{c.description}</Text> : null}
              <View style={{ flexDirection: 'row', gap: 6 }}>
                <View style={{ flex: 1, alignItems: 'center', backgroundColor: colors.surface, borderRadius: 10, paddingVertical: 8 }}><Text style={{ fontSize: 14, fontWeight: '800', color: colors.text }}>{c.calls_30d ?? 0}</Text><Text style={{ fontSize: 9, fontWeight: '700', color: colors.textSecondary }}>CALLS · 30D</Text></View>
                <View style={{ flex: 1, alignItems: 'center', backgroundColor: colors.surface, borderRadius: 10, paddingVertical: 8 }}><Text style={{ fontSize: 14, fontWeight: '800', color: scoreTone(c.avg_30d) }}>{c.avg_30d == null ? '--' : `${c.avg_30d}%`}</Text><Text style={{ fontSize: 9, fontWeight: '700', color: colors.textSecondary }}>AVG SCORE</Text></View>
                <View style={{ flex: 2, justifyContent: 'center', backgroundColor: colors.surface, borderRadius: 10, paddingVertical: 8, paddingHorizontal: 10 }}><Text style={{ fontSize: 11, fontWeight: '700', color: colors.text }} numberOfLines={2}>{appliesLabel(c)}</Text></View>
              </View>
              <View style={{ flexDirection: 'row', gap: 8, marginTop: 2 }}>
                <TouchableOpacity onPress={() => router.push(`/scorecards/${c.id}` as any)} style={{ flex: 1, height: 42, borderRadius: 12, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 6 }} {...tid(`scorecard-edit-${c.id}`)}>
                  <Ionicons name="create-outline" size={16} color="#111" /><Text style={{ fontSize: 14, fontWeight: '800', color: '#111' }}>Edit</Text>
                </TouchableOpacity>
                <TouchableOpacity onPress={() => duplicate(c)} disabled={busy === c.id} style={{ height: 42, paddingHorizontal: 14, borderRadius: 12, borderWidth: 1, borderColor: colors.border, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 6 }} {...tid(`scorecard-duplicate-${c.id}`)}>
                  <Ionicons name="copy-outline" size={16} color={colors.text} /><Text style={{ fontSize: 13, fontWeight: '700', color: colors.text }}>Duplicate</Text>
                </TouchableOpacity>
                <TouchableOpacity onPress={() => remove(c)} style={{ height: 42, width: 42, borderRadius: 12, borderWidth: 1, borderColor: colors.border, alignItems: 'center', justifyContent: 'center' }} {...tid(`scorecard-delete-${c.id}`)}>
                  <Ionicons name="trash-outline" size={16} color={RED} />
                </TouchableOpacity>
              </View>
            </View>
          ))}
          <TouchableOpacity onPress={() => setPicker(true)} style={{ height: 50, borderRadius: 14, borderWidth: 1, borderStyle: 'dashed', borderColor: GOLD, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 8 }} {...tid('scorecards-new')}>
            <Ionicons name="add" size={20} color={GOLD} /><Text style={{ fontSize: 15, fontWeight: '800', color: GOLD }}>New scorecard</Text>
          </TouchableOpacity>
        </ScrollView>
      )}

      <Modal visible={picker} animationType="slide" transparent onRequestClose={() => setPicker(false)}>
        <View style={{ flex: 1, backgroundColor: '#00000088', justifyContent: 'flex-end' }}>
          <View style={{ backgroundColor: colors.bg, borderTopLeftRadius: 24, borderTopRightRadius: 24, maxHeight: '85%' }} {...tid('scorecard-template-sheet')}>
            <View style={{ flexDirection: 'row', alignItems: 'center', padding: 16, gap: 12 }}>
              <Text style={{ flex: 1, fontSize: 18, fontWeight: '800', color: colors.text }}>Start a new scorecard</Text>
              <TouchableOpacity onPress={() => setPicker(false)} {...tid('scorecard-template-close')}><Ionicons name="close" size={24} color={colors.text} /></TouchableOpacity>
            </View>
            <ScrollView contentContainerStyle={{ paddingHorizontal: 16, paddingBottom: 40, gap: 10 }}>
              {templates.map(t => (
                <TouchableOpacity key={t.key} onPress={() => create(t.key)} disabled={!!busy} style={{ backgroundColor: colors.card, borderRadius: 14, padding: 14, borderWidth: 1, borderColor: colors.border, flexDirection: 'row', gap: 12, alignItems: 'center' }} {...tid(`scorecard-template-${t.key}`)}>
                  <Ionicons name="clipboard" size={20} color={GOLD} />
                  <View style={{ flex: 1 }}>
                    <Text style={{ fontSize: 15, fontWeight: '800', color: colors.text }}>{t.name}</Text>
                    <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 2, lineHeight: 16 }}>{t.description}</Text>
                    <Text style={{ fontSize: 11, color: GOLD, marginTop: 4, fontWeight: '700' }}>{t.department} · {t.criteria_count} criteria</Text>
                  </View>
                  {busy === t.key ? <ActivityIndicator color={GOLD} /> : <Ionicons name="chevron-forward" size={18} color={colors.textSecondary} />}
                </TouchableOpacity>
              ))}
              <TouchableOpacity onPress={() => create(null)} disabled={!!busy} style={{ alignItems: 'center', paddingVertical: 12 }} {...tid('scorecard-template-blank')}>
                <Text style={{ fontSize: 14, fontWeight: '700', color: colors.textSecondary }}>Start from a blank scorecard</Text>
              </TouchableOpacity>
            </ScrollView>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}
