import React, { useCallback, useEffect, useRef, useState } from 'react';
import { View, Text, ScrollView, TouchableOpacity, ActivityIndicator, Platform, RefreshControl } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useLocalSearchParams, useRouter, useFocusEffect } from 'expo-router';
import api from '../../services/api';
import { useAuthStore } from '../../store/authStore';
import { useThemeStore } from '../../store/themeStore';
import { useToast } from '../../components/common/Toast';
import { showConfirm } from '../../services/alert';
import { ScreenHeader } from '../../components/common/ScreenHeader';
import { GOLD, tid, errText } from '../../components/inbox/ownership';
import { useMemoRecorder, MEMO_MAX_SECONDS } from '../../hooks/useMemoRecorder';
import { MemoCard, fmtLen } from '../../components/memos/MemoCard';
import { AttachContactSheet } from '../../components/memos/AttachContactSheet';
import { resolvePhotoUrl } from '../../utils/photoUrl';

const RED = '#FF3B30';

// Voice memos that are not about anyone yet. Record from the + menu, attach to a contact when you know who it was.
export default function VoiceMemosScreen() {
  const router = useRouter();
  const { record } = useLocalSearchParams<{ record?: string }>();
  const { user } = useAuthStore();
  const { colors } = useThemeStore();
  const { showToast } = useToast();
  const [memos, setMemos] = useState<any[] | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [attaching, setAttaching] = useState<any | null>(null);
  const [preset, setPreset] = useState<any | null>(null);
  const [playingId, setPlayingId] = useState<string | null>(null);
  const soundRef = useRef<any>(null);
  const audioRef = useRef<any>(null);
  const autoStarted = useRef(false);

  const load = useCallback(async () => {
    if (!user?._id) return;
    try { setMemos((await api.get(`/voice-memos/${user._id}`)).data.memos || []); }
    catch (e) { showToast(errText(e, 'Could not load memos'), 'error'); setMemos([]); }
  }, [user?._id]);
  useFocusEffect(useCallback(() => { load(); }, [load]));

  const rec = useMemoRecorder({
    userId: user?._id,
    onSaved: (m) => { setMemos(prev => [m, ...(prev || [])]); showToast(m.title ? `Saved: ${m.title}` : 'Memo saved', 'success'); },
    onError: (msg) => showToast(msg, 'error', 3500),
  });
  useEffect(() => { if (record === '1' && !autoStarted.current && user?._id) { autoStarted.current = true; rec.start(); } }, [record, user?._id]);
  useEffect(() => () => { stopPlayback(); }, []);

  const stopPlayback = async () => {
    if (soundRef.current) { try { await soundRef.current.unloadAsync(); } catch {} soundRef.current = null; }
    if (audioRef.current) { try { audioRef.current.pause(); } catch {} audioRef.current = null; }
    setPlayingId(null);
  };
  const play = async (m: any) => {
    const wasPlaying = playingId === m.id;
    await stopPlayback();
    if (wasPlaying) return;
    const url = m.audio_url?.startsWith('http') ? m.audio_url : resolvePhotoUrl(m.audio_url) || m.audio_url;
    try {
      if (Platform.OS === 'web') {
        const a = new (globalThis as any).Audio(url);
        a.onended = () => setPlayingId(null);
        a.onerror = () => { setPlayingId(null); showToast('Could not play that memo', 'error'); };
        await a.play(); audioRef.current = a;
      } else {
        const { Audio } = await import('expo-av');
        await Audio.setAudioModeAsync({ allowsRecordingIOS: false, playsInSilentModeIOS: true });
        const { sound } = await Audio.Sound.createAsync({ uri: url }, { shouldPlay: true }, (st: any) => { if (st.didJustFinish) { setPlayingId(null); soundRef.current = null; } });
        soundRef.current = sound;
      }
      setPlayingId(m.id);
    } catch { showToast('Could not play that memo', 'error'); }
  };

  const rename = async (m: any, title: string) => {
    try { await api.patch(`/voice-memos/${user!._id}/${m.id}`, { title }); setMemos(prev => (prev || []).map(x => x.id === m.id ? { ...x, title } : x)); }
    catch (e) { showToast(errText(e, 'Could not rename'), 'error'); }
  };
  const remove = (m: any) => showConfirm('Delete this memo?', 'The audio and transcript are gone for good.', async () => {
    try { await api.delete(`/voice-memos/${user!._id}/${m.id}`); setMemos(prev => (prev || []).filter(x => x.id !== m.id)); if (playingId === m.id) stopPlayback(); }
    catch (e) { showToast(errText(e, 'Could not delete'), 'error'); }
  }, undefined, 'Delete');
  const attached = (memoId: string, r: any) => {
    setMemos(prev => (prev || []).filter(x => x.id !== memoId));
    showToast(`Attached to ${r.contact_name}${r.tasks?.length ? ` · ${r.tasks.length} task${r.tasks.length === 1 ? '' : 's'} added` : ''}`, 'success', 4000);
    router.push(`/contact/${r.contact_id}` as any);
  };

  const live = rec.recording;
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      <ScreenHeader title="Voice memos" subtitle="Record now, attach to a contact later" testID="voice-memos-header" />
      <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 60, gap: 14 }} refreshControl={<RefreshControl refreshing={refreshing} onRefresh={async () => { setRefreshing(true); await load(); setRefreshing(false); }} tintColor={GOLD} />}>
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

        {memos === null ? <ActivityIndicator color={GOLD} style={{ marginTop: 30 }} /> : memos.length === 0 ? (
          <Text style={{ fontSize: 13, color: colors.textSecondary, textAlign: 'center', paddingVertical: 24 }} {...tid('memos-empty')}>No unattached memos. Anything you record here waits until you attach it.</Text>
        ) : (
          <>
            <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 1 }}>NOT ATTACHED YET · {memos.length}</Text>
            {memos.map(m => <MemoCard key={m.id} memo={m} colors={colors} playing={playingId === m.id} onPlay={() => play(m)} onAttach={(s) => { setPreset(s || null); setAttaching(m); }} onDelete={() => remove(m)} onRename={t => rename(m, t)} />)}
          </>
        )}
      </ScrollView>
      <AttachContactSheet visible={!!attaching} onClose={() => { setAttaching(null); setPreset(null); }} userId={user?._id} memo={attaching} colors={colors} onAttached={attached} showToast={showToast} preset={preset} />
    </SafeAreaView>
  );
}
