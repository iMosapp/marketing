import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { View, Text, ScrollView, TouchableOpacity, ActivityIndicator, RefreshControl } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useLocalSearchParams, useRouter, useFocusEffect } from 'expo-router';
import api, { tagsAPI } from '../../services/api';
import { useAuthStore } from '../../store/authStore';
import { useThemeStore } from '../../store/themeStore';
import { useToast } from '../../components/common/Toast';
import { showConfirm } from '../../services/alert';
import { ScreenHeader } from '../../components/common/ScreenHeader';
import { GOLD, tid, errText } from '../../components/inbox/ownership';
import { useMemoRecorder, MEMO_MAX_SECONDS } from '../../hooks/useMemoRecorder';
import { useMemoPlayer } from '../../hooks/useMemoPlayer';
import { MemoCard, fmtLen } from '../../components/memos/MemoCard';
import { AttachContactSheet } from '../../components/memos/AttachContactSheet';
import { MemoTagSheet } from '../../components/memos/MemoTagSheet';
import { MemoFilters, MemoView } from '../../components/memos/MemoFilters';
import { DayHeader } from '../../components/memos/DayHeader';
import { groupByDay, memoMatches, tagsInUse } from '../../components/memos/memoGroups';

const RED = '#FF3B30';

// Voice memos in one place: the to-file pile and everything already filed, searchable, tagged, grouped by day.
export default function VoiceMemosScreen() {
  const router = useRouter();
  const { record } = useLocalSearchParams<{ record?: string }>();
  const { user } = useAuthStore();
  const { colors } = useThemeStore();
  const { showToast } = useToast();
  const [view, setView] = useState<MemoView>('unattached');
  const [memos, setMemos] = useState<any[] | null>(null);
  const [counts, setCounts] = useState({ unattached: 0, attached: 0 });
  const [dayLabels, setDayLabels] = useState<Record<string, string>>({});
  const [q, setQ] = useState('');
  const [activeTag, setActiveTag] = useState<string | null>(null);
  const [library, setLibrary] = useState<any[]>([]);
  const [refreshing, setRefreshing] = useState(false);
  const [attaching, setAttaching] = useState<any | null>(null);
  const [preset, setPreset] = useState<any | null>(null);
  const [tagging, setTagging] = useState<any | null>(null);
  const autoStarted = useRef(false);
  const viewRef = useRef<MemoView>('unattached');
  const player = useMemoPlayer((msg) => showToast(msg, 'error'));

  const load = useCallback(async () => {
    if (!user?._id) return;
    const v = viewRef.current;
    try {
      const d = (await api.get(`/voice-memos/${user._id}`, { params: { view: v } })).data;
      if (viewRef.current !== v) return;
      setMemos(d.memos || []); setCounts(d.counts || { unattached: 0, attached: 0 }); setDayLabels(d.day_labels || {});
    } catch (e) { showToast(errText(e, 'Could not load memos'), 'error'); setMemos([]); }
  }, [user?._id]);
  useFocusEffect(useCallback(() => { load(); }, [load]));
  useEffect(() => { if (user?._id) tagsAPI.getAll(user._id).then((t: any) => setLibrary(Array.isArray(t) ? t : [])).catch(() => {}); }, [user?._id]);
  const switchView = (v: MemoView) => { if (v === view) return; viewRef.current = v; setView(v); setMemos(null); setActiveTag(null); load(); };

  const rec = useMemoRecorder({
    userId: user?._id,
    onSaved: (m) => { setCounts(c => ({ ...c, unattached: c.unattached + 1 })); if (view === 'unattached') setMemos(prev => [m, ...(prev || [])]); showToast(m.title ? `Saved: ${m.title}` : 'Memo saved', 'success'); },
    onError: (msg) => showToast(msg, 'error', 3500),
  });
  useEffect(() => { if (record === '1' && !autoStarted.current && user?._id) { autoStarted.current = true; rec.start(); } }, [record, user?._id]);

  const tagColor = useCallback((t: string) => library.find(x => x.name?.toLowerCase() === t.toLowerCase())?.color || GOLD, [library]);
  const patch = (id: string, upd: any) => setMemos(prev => (prev || []).map(x => x.id === id ? { ...x, ...upd } : x));
  const rename = async (m: any, title: string) => {
    try { await api.patch(`/voice-memos/${user!._id}/${m.id}`, { title }); patch(m.id, { title }); }
    catch (e) { showToast(errText(e, 'Could not rename'), 'error'); }
  };
  const remove = (m: any) => showConfirm('Delete this memo?', 'The audio and transcript are gone for good.', async () => {
    try { await api.delete(`/voice-memos/${user!._id}/${m.id}`); setMemos(prev => (prev || []).filter(x => x.id !== m.id)); setCounts(c => ({ ...c, unattached: Math.max(0, c.unattached - 1) })); if (player.playingId === m.id) player.stop(); }
    catch (e) { showToast(errText(e, 'Could not delete'), 'error'); }
  }, undefined, 'Delete');
  const [retryingId, setRetryingId] = useState<string | null>(null);
  const retry = async (m: any) => {
    if (retryingId) return;
    setRetryingId(m.id);
    try {
      const r = (await api.post(`/voice-memos/${user!._id}/${m.id}/retry-transcript`, {}, { timeout: 120000 })).data;
      patch(m.id, r);
      if (r?.transcript_status === 'done') showToast(r.title ? `Transcribed: ${r.title}` : 'Transcribed', 'success');
      else showToast("Still couldn't transcribe it. You can play it and add a note.", 'error', 5000);
    } catch (e) { showToast(errText(e, 'Retry did not go through'), 'error'); }
    finally { setRetryingId(null); }
  };
  const anyRetrying = (memos || []).some(m => m.transcript_status === 'retrying');
  useEffect(() => { if (!anyRetrying) return; const t = setInterval(load, 30000); return () => clearInterval(t); }, [anyRetrying, load]);
  const attached = (memoId: string, r: any) => {
    setMemos(prev => (prev || []).filter(x => x.id !== memoId));
    setCounts(c => ({ unattached: Math.max(0, c.unattached - 1), attached: c.attached + 1 }));
    showToast(`Attached to ${r.contact_name}${r.tasks?.length ? ` · ${r.tasks.length} task${r.tasks.length === 1 ? '' : 's'} added` : ''}`, 'success', 4000);
    router.push(`/contact/${r.contact_id}` as any);
  };
  const labelDay = async (day: string, label: string) => {
    try { await api.put(`/voice-memos/${user!._id}/day-label`, { day, label }); setDayLabels(p => { const n = { ...p }; if (label) n[day] = label; else delete n[day]; return n; }); }
    catch (e) { showToast(errText(e, 'Could not name that day'), 'error'); }
  };

  const shown = useMemo(() => (memos || []).filter(m => memoMatches(m, q) && (!activeTag || (m.tags || []).some((t: string) => t.toLowerCase() === activeTag.toLowerCase()))), [memos, q, activeTag]);
  const groups = useMemo(() => groupByDay(shown), [shown]);
  const tags = useMemo(() => tagsInUse(memos || []), [memos]);
  const live = rec.recording;
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      <ScreenHeader title="Voice memos" subtitle="Record now, attach to a contact later" testID="voice-memos-header" />
      <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 60, gap: 14 }} keyboardShouldPersistTaps="handled" refreshControl={<RefreshControl refreshing={refreshing} onRefresh={async () => { setRefreshing(true); await load(); setRefreshing(false); }} tintColor={GOLD} />}>
        <View style={{ alignItems: 'center', paddingVertical: 18, gap: 12, backgroundColor: colors.card, borderRadius: 20, borderWidth: 1, borderColor: live ? RED : colors.border }} {...tid('memo-recorder')}>
          <TouchableOpacity onPress={live ? rec.stop : rec.start} disabled={!!rec.saving} activeOpacity={0.85}
            style={{ width: 92, height: 92, borderRadius: 46, backgroundColor: live ? RED : rec.saving ? GOLD + '33' : GOLD, alignItems: 'center', justifyContent: 'center' }} {...tid(live ? 'memo-stop' : 'memo-record')}>
            {rec.saving ? <ActivityIndicator color={GOLD} /> : <Ionicons name={live ? 'stop' : 'mic'} size={38} color={live ? '#fff' : '#111'} />}
          </TouchableOpacity>
          <Text style={{ fontSize: 17, fontWeight: '800', color: live ? RED : colors.text }} {...tid('memo-recorder-status')}>
            {rec.saving ? rec.saving : live ? `Recording · ${fmtLen(rec.seconds)}` : 'Tap to record'}
          </Text>
          <Text style={{ fontSize: 12.5, color: colors.textSecondary, textAlign: 'center', paddingHorizontal: 24, lineHeight: 17 }}>
            {live ? 'Keep the screen on. Tap the square when you are done.' : `A presentation, a walk-around, a thought. Up to ${MEMO_MAX_SECONDS / 60} minutes. Jessi transcribes and summarizes it; attach it to the right person whenever you like.`}
          </Text>
        </View>

        <MemoFilters view={view} onView={switchView} counts={counts} q={q} onQ={setQ} tags={tags} activeTag={activeTag} onTag={setActiveTag} tagColor={tagColor} colors={colors} />

        {memos === null ? <ActivityIndicator color={GOLD} style={{ marginTop: 30 }} /> : shown.length === 0 ? (
          <Text style={{ fontSize: 13, color: colors.textSecondary, textAlign: 'center', paddingVertical: 24 }} {...tid('memos-empty')}>
            {q || activeTag ? 'Nothing matches that search.' : view === 'attached' ? 'Nothing filed yet. Memos you attach to a contact show up here with who they went to.' : 'No unattached memos. Anything you record here waits until you attach it.'}
          </Text>
        ) : groups.map(g => (
          <View key={g.key} style={{ gap: 10 }} {...tid(`memo-group-${g.key}`)}>
            <DayHeader dayKey={g.key} title={g.title} label={dayLabels[g.key] || ''} count={g.memos.length} onRename={(l) => labelDay(g.key, l)} colors={colors} />
            {g.memos.map(m => <MemoCard key={m.id} memo={m} colors={colors} playing={player.playingId === m.id} onPlay={() => player.play(m)} onAttach={(s) => { setPreset(s || null); setAttaching(m); }} onDelete={() => remove(m)} onRename={t => rename(m, t)} onTag={() => setTagging(m)} tagColor={tagColor} onRetry={() => retry(m)} retrying={retryingId === m.id} />)}
          </View>
        ))}
      </ScrollView>
      <AttachContactSheet visible={!!attaching} onClose={() => { setAttaching(null); setPreset(null); }} userId={user?._id} memo={attaching} colors={colors} onAttached={attached} showToast={showToast} preset={preset} />
      <MemoTagSheet visible={!!tagging} onClose={() => setTagging(null)} userId={user?._id} memo={tagging} colors={colors} onSaved={(id, t) => patch(id, { tags: t })} showToast={showToast} library={library} onLibrary={setLibrary} />
    </SafeAreaView>
  );
}
