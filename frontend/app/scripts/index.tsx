import React, { useCallback, useMemo, useState } from 'react';
import { View, Text, ScrollView, TouchableOpacity, ActivityIndicator, RefreshControl, TextInput } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import api from '../../services/api';
import { useAuthStore } from '../../store/authStore';
import { useThemeStore } from '../../store/themeStore';
import { useToast } from '../../components/common/Toast';
import { ScreenHeader, HeaderIconButton } from '../../components/common/ScreenHeader';
import { ScorePill } from '../../components/scorecards/ScoreRing';
import { GOLD, tid, fmtDate, type Script, type Assignment } from '../../components/scripts/shared';

type Recent = { session_id: string; script_title: string; score_pct: number | null; adherence_pct: number | null; ended_at: string | null };

export default function ScriptsLibrary() {
  const router = useRouter();
  const { user } = useAuthStore();
  const { colors } = useThemeStore();
  const { showToast } = useToast();
  const [scripts, setScripts] = useState<Script[]>([]);
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [recent, setRecent] = useState<Recent[]>([]);
  const [canEdit, setCanEdit] = useState(false);
  const [superAdmin, setSuperAdmin] = useState(false);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState('');
  const [cat, setCat] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const res = await api.get('/scripts');
      setScripts(res.data.scripts || []); setAssignments(res.data.my_assignments || []); setRecent(res.data.my_recent || []);
      setCanEdit(!!res.data.can_edit); setSuperAdmin(!!res.data.is_super_admin);
    } catch (e: any) { showToast(e?.response?.data?.detail || 'Could not load scripts', 'error'); }
    finally { setLoading(false); }
  }, []);
  useFocusEffect(useCallback(() => { if (user?._id) load(); }, [user?._id, load]));

  const categories = useMemo(() => Array.from(new Set(scripts.map(s => s.category))).sort(), [scripts]);
  const shown = useMemo(() => scripts.filter(s => (!cat || s.category === cat) && (!q.trim() || `${s.title} ${s.purpose} ${s.body}`.toLowerCase().includes(q.trim().toLowerCase()))), [scripts, cat, q]);
  const grouped = useMemo(() => categories.filter(c => shown.some(s => s.category === c)).map(c => ({ c, items: shown.filter(s => s.category === c) })), [categories, shown]);

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      <ScreenHeader title="Scripts & Practice" subtitle="Know the call before you make it" testID="scripts-header"
        right={canEdit ? <HeaderIconButton icon="add-circle" onPress={() => router.push('/scripts/editor' as any)} testID="scripts-add" /> : undefined} />
      {loading ? <ActivityIndicator style={{ marginTop: 60 }} color={GOLD} /> : (
        <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 60, gap: 14 }} refreshControl={<RefreshControl refreshing={false} onRefresh={load} tintColor={GOLD} />} keyboardShouldPersistTaps="handled">
          {assignments.length > 0 && (
            <View style={{ gap: 8 }} {...tid('scripts-assigned-strip')}>
              <Text style={{ fontSize: 11, fontWeight: '800', color: GOLD, letterSpacing: 1 }}>ASSIGNED TO YOU</Text>
              {assignments.map(a => (
                <TouchableOpacity key={a.id} onPress={() => router.push(`/scripts/${a.script_id}?assignment=${a.id}` as any)} activeOpacity={0.85}
                  style={{ backgroundColor: GOLD, borderRadius: 16, padding: 14, flexDirection: 'row', alignItems: 'center', gap: 12 }} {...tid(`scripts-assignment-${a.id}`)}>
                  <View style={{ width: 40, height: 40, borderRadius: 20, backgroundColor: '#11111122', alignItems: 'center', justifyContent: 'center' }}><Ionicons name="call" size={20} color="#111" /></View>
                  <View style={{ flex: 1 }}>
                    <Text style={{ fontSize: 15, fontWeight: '800', color: '#111' }} numberOfLines={1}>Practice: {a.script_title}</Text>
                    <Text style={{ fontSize: 12, color: '#111', opacity: 0.75 }} numberOfLines={1}>From {a.created_by_name || 'your manager'}{a.due_by ? ` · due ${fmtDate(a.due_by)}` : ''}{a.note ? ` · ${a.note}` : ''}</Text>
                  </View>
                  <Ionicons name="chevron-forward" size={18} color="#111" />
                </TouchableOpacity>
              ))}
            </View>
          )}

          <Text style={{ fontSize: 13, color: colors.textSecondary, lineHeight: 18 }}>
            Read it, print it, or tap Practice: Jessi calls your phone as a real customer (or you type it out on the floor), then you get scored like a recorded call, plus coaching.
          </Text>

          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: colors.card, borderRadius: 12, paddingHorizontal: 12, height: 42, borderWidth: 1, borderColor: colors.border }}>
            <Ionicons name="search" size={16} color={colors.textSecondary} />
            <TextInput value={q} onChangeText={setQ} placeholder="Search scripts" placeholderTextColor={colors.textSecondary} style={{ flex: 1, color: colors.text, fontSize: 15 }} {...tid('scripts-search')} />
            {!!q && <TouchableOpacity onPress={() => setQ('')} {...tid('scripts-search-clear')}><Ionicons name="close-circle" size={16} color={colors.textSecondary} /></TouchableOpacity>}
          </View>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8 }}>
            {[null, ...categories].map(c => (
              <TouchableOpacity key={c || 'all'} onPress={() => setCat(c)} style={{ paddingHorizontal: 14, height: 34, borderRadius: 17, backgroundColor: cat === c ? GOLD : colors.card, borderWidth: 1, borderColor: cat === c ? GOLD : colors.border, justifyContent: 'center' }} {...tid(`scripts-cat-${(c || 'all').toLowerCase().replace(/\s+/g, '-')}`)}>
                <Text style={{ fontSize: 13, fontWeight: '800', color: cat === c ? '#111' : colors.text }}>{c || 'All'}</Text>
              </TouchableOpacity>
            ))}
          </ScrollView>

          {grouped.map(g => (
            <View key={g.c} style={{ gap: 8 }}>
              <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 1 }}>{g.c.toUpperCase()}</Text>
              {g.items.map(s => (
                <TouchableOpacity key={s.id} onPress={() => router.push(`/scripts/${s.id}` as any)} activeOpacity={0.85}
                  style={{ backgroundColor: colors.card, borderRadius: 16, borderWidth: 1, borderColor: colors.border, padding: 14, flexDirection: 'row', alignItems: 'center', gap: 12 }} {...tid(`script-card-${s.id}`)}>
                  <View style={{ width: 40, height: 40, borderRadius: 12, backgroundColor: GOLD + '22', alignItems: 'center', justifyContent: 'center' }}><Ionicons name="document-text" size={18} color={GOLD} /></View>
                  <View style={{ flex: 1 }}>
                    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                      <Text style={{ flex: 1, fontSize: 15, fontWeight: '800', color: colors.text }} numberOfLines={1}>{s.title}</Text>
                      {s.customized && <View style={{ paddingHorizontal: 6, paddingVertical: 2, borderRadius: 6, backgroundColor: GOLD + '22' }}><Text style={{ fontSize: 9, fontWeight: '800', color: GOLD }}>YOUR STORE</Text></View>}
                    </View>
                    <Text style={{ fontSize: 12.5, color: colors.textSecondary, lineHeight: 17, marginTop: 2 }} numberOfLines={2}>{s.purpose}</Text>
                    <Text style={{ fontSize: 11, fontWeight: '700', color: GOLD, marginTop: 4 }}>{s.runtime}{s.persona ? ` · practice with ${s.persona.name.split(' ')[0]}` : ''}</Text>
                  </View>
                  <Ionicons name="chevron-forward" size={18} color={colors.textSecondary} />
                </TouchableOpacity>
              ))}
            </View>
          ))}
          {shown.length === 0 && <Text style={{ textAlign: 'center', color: colors.textSecondary, marginTop: 20 }} {...tid('scripts-empty')}>No scripts match.</Text>}

          {recent.length > 0 && (
            <View style={{ gap: 8, marginTop: 6 }} {...tid('scripts-recent')}>
              <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 1 }}>YOUR RECENT PRACTICE</Text>
              {recent.map(r => (
                <TouchableOpacity key={r.session_id} onPress={() => router.push(`/scripts/result?session=${r.session_id}` as any)} style={{ backgroundColor: colors.card, borderRadius: 14, borderWidth: 1, borderColor: colors.border, padding: 12, flexDirection: 'row', alignItems: 'center', gap: 10 }} {...tid(`scripts-recent-${r.session_id}`)}>
                  <View style={{ flex: 1 }}>
                    <Text style={{ fontSize: 14, fontWeight: '700', color: colors.text }} numberOfLines={1}>{r.script_title}</Text>
                    <Text style={{ fontSize: 11.5, color: colors.textSecondary }}>{r.ended_at ? new Date(r.ended_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) : ''}{r.adherence_pct != null ? ` · script ${r.adherence_pct}%` : ''}</Text>
                  </View>
                  <ScorePill pct={r.score_pct} />
                </TouchableOpacity>
              ))}
            </View>
          )}

          {(canEdit || superAdmin) && (
            <View style={{ gap: 8, marginTop: 6 }}>
              {canEdit && (
                <TouchableOpacity onPress={() => router.push('/scripts/assign' as any)} style={{ backgroundColor: colors.card, borderRadius: 14, padding: 14, flexDirection: 'row', alignItems: 'center', gap: 12, borderWidth: 1, borderColor: GOLD + '66' }} {...tid('scripts-assign-link')}>
                  <Ionicons name="people" size={20} color={GOLD} />
                  <View style={{ flex: 1 }}><Text style={{ fontSize: 14, fontWeight: '800', color: colors.text }}>Assign practice calls</Text><Text style={{ fontSize: 12, color: colors.textSecondary }}>Pick a script and reps, add curveballs, see their scores</Text></View>
                  <Ionicons name="chevron-forward" size={16} color={colors.textSecondary} />
                </TouchableOpacity>
              )}
              {superAdmin && (
                <TouchableOpacity onPress={() => router.push('/scripts/training' as any)} style={{ backgroundColor: colors.card, borderRadius: 14, padding: 14, flexDirection: 'row', alignItems: 'center', gap: 12, borderWidth: 1, borderColor: colors.border }} {...tid('scripts-training-link')}>
                  <Ionicons name="videocam" size={20} color={GOLD} />
                  <View style={{ flex: 1 }}><Text style={{ fontSize: 14, fontWeight: '800', color: colors.text }}>Training video scripts</Text><Text style={{ fontSize: 12, color: colors.textSecondary }}>Jessi writes the voice-over and shot list for any feature</Text></View>
                  <Ionicons name="chevron-forward" size={16} color={colors.textSecondary} />
                </TouchableOpacity>
              )}
            </View>
          )}
        </ScrollView>
      )}
    </SafeAreaView>
  );
}
