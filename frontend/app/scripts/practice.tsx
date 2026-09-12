import React, { useCallback, useEffect, useRef, useState } from 'react';
import { View, Text, ScrollView, TouchableOpacity, ActivityIndicator, TextInput, Platform, Animated, KeyboardAvoidingView } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { Audio } from 'expo-av';
import api from '../../services/api';
import { showConfirm } from '../../services/alert';
import { useThemeStore } from '../../store/themeStore';
import { useToast } from '../../components/common/Toast';
import { resolvePhotoUrl } from '../../utils/photoUrl';
import { GOLD, RED, GREEN, tid, initials, fmtClock, moodTone, type Turn, type Persona } from '../../components/scripts/shared';

const MAX_TALK = 60;
const recOptions = {
  isMeteringEnabled: false,
  android: { extension: '.m4a', outputFormat: Audio.AndroidOutputFormat.MPEG_4, audioEncoder: Audio.AndroidAudioEncoder.AAC, sampleRate: 44100, numberOfChannels: 1, bitRate: 64000 },
  ios: { extension: '.m4a', outputFormat: Audio.IOSOutputFormat.MPEG4AAC, audioQuality: Audio.IOSAudioQuality.HIGH, sampleRate: 44100, numberOfChannels: 1, bitRate: 64000, linearPCMBitDepth: 16, linearPCMIsBigEndian: false, linearPCMIsFloat: false },
  web: { mimeType: 'audio/webm', bitsPerSecond: 64000 },
};

export default function PracticeCall() {
  const router = useRouter();
  const { script, assignment } = useLocalSearchParams<{ script: string; assignment?: string }>();
  const { colors } = useThemeStore();
  const { showToast } = useToast();
  const [phase, setPhase] = useState<'connecting' | 'live' | 'grading' | 'failed'>('connecting');
  const [sid, setSid] = useState<string | null>(null);
  const [persona, setPersona] = useState<Persona | null>(null);
  const [title, setTitle] = useState('');
  const [turns, setTurns] = useState<Turn[]>([]);
  const [talking, setTalking] = useState(false);
  const [talkSecs, setTalkSecs] = useState(0);
  const [thinking, setThinking] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [ended, setEnded] = useState(false);
  const [typed, setTyped] = useState(false);
  const [text, setText] = useState('');
  const [elapsed, setElapsed] = useState(0);
  const soundRef = useRef<Audio.Sound | null>(null);
  const recRef = useRef<Audio.Recording | null>(null);
  const talkTimer = useRef<any>(null);
  const scrollRef = useRef<ScrollView>(null);
  const pulse = useRef(new Animated.Value(1)).current;
  const endingRef = useRef(false);

  useEffect(() => {
    const loop = Animated.loop(Animated.sequence([Animated.timing(pulse, { toValue: 1.12, duration: 600, useNativeDriver: true }), Animated.timing(pulse, { toValue: 1, duration: 600, useNativeDriver: true })]));
    if (speaking || talking) loop.start(); else pulse.setValue(1);
    return () => loop.stop();
  }, [speaking, talking]);

  useEffect(() => { const t = setInterval(() => phase === 'live' && setElapsed(e => e + 1), 1000); return () => clearInterval(t); }, [phase]);
  useEffect(() => () => { soundRef.current?.unloadAsync().catch(() => {}); recRef.current?.stopAndUnloadAsync().catch(() => {}); if (talkTimer.current) clearInterval(talkTimer.current); }, []);

  const setMode = (recording: boolean) => Audio.setAudioModeAsync({ allowsRecordingIOS: recording, playsInSilentModeIOS: true, staysActiveInBackground: false }).catch(() => {});

  const play = useCallback(async (url?: string | null) => {
    if (!url) return;
    try {
      await soundRef.current?.unloadAsync().catch(() => {});
      await setMode(false);
      const { sound } = await Audio.Sound.createAsync({ uri: resolvePhotoUrl(url)! }, { shouldPlay: true }, (st: any) => {
        if (!st.isLoaded) return;
        setSpeaking(st.isPlaying);
        if (st.didJustFinish) { setSpeaking(false); sound.unloadAsync().catch(() => {}); }
      });
      soundRef.current = sound;
    } catch { setSpeaking(false); }
  }, []);

  useEffect(() => {
    (async () => {
      try {
        const res = await api.post('/scripts/roleplay/start', { script_id: script, assignment_id: assignment || null });
        setSid(res.data.session_id); setPersona(res.data.persona); setTitle(res.data.script_title || 'Practice call');
        setTurns([res.data.customer]); setPhase('live');
        play(res.data.customer?.audio_url);
      } catch (e: any) { showToast(e?.response?.data?.detail || 'Could not start the practice call', 'error'); setPhase('failed'); }
    })();
  }, [script, assignment]);

  useEffect(() => { setTimeout(() => scrollRef.current?.scrollToEnd({ animated: true }), 80); }, [turns.length, thinking]);

  const finish = useCallback(async () => {
    if (!sid || endingRef.current) return;
    endingRef.current = true;
    await soundRef.current?.unloadAsync().catch(() => {});
    setPhase('grading');
    try { await api.post(`/scripts/roleplay/${sid}/end`, {}, { timeout: 120000 }); router.replace(`/scripts/result?session=${sid}` as any); }
    catch (e: any) { showToast(e?.response?.data?.detail || 'Grading failed, try ending again', 'error'); endingRef.current = false; setPhase('live'); }
  }, [sid]);

  useEffect(() => { if (ended && !speaking && !thinking) { const t = setTimeout(finish, 900); return () => clearTimeout(t); } }, [ended, speaking, thinking, finish]);

  const sendTurn = async (body: any) => {
    if (!sid) return;
    setThinking(true);
    try {
      const res = await api.post(`/scripts/roleplay/${sid}/turn`, body, { timeout: 90000 });
      if (res.data.retry) { showToast("Didn't catch that, try again", 'error'); return; }
      setTurns(t => [...t, res.data.rep, res.data.customer]);
      if (res.data.ended) setEnded(true);
      play(res.data.customer?.audio_url);
    } catch (e: any) {
      if (e?.response?.status === 409) { setEnded(true); return; }
      showToast(e?.response?.data?.detail || 'Lost the line for a second, try again', 'error');
    } finally { setThinking(false); }
  };

  const startTalk = async () => {
    if (thinking || talking || ended) return;
    try {
      await soundRef.current?.unloadAsync().catch(() => {}); setSpeaking(false);
      const { status } = await Audio.requestPermissionsAsync();
      if (status !== 'granted') { showToast('Mic access needed. You can type instead.', 'error'); setTyped(true); return; }
      await setMode(true);
      const { recording } = await Audio.Recording.createAsync(recOptions as any);
      recRef.current = recording; setTalkSecs(0); setTalking(true);
      talkTimer.current = setInterval(() => setTalkSecs(s => { if (s + 1 >= MAX_TALK) stopTalk(); return s + 1; }), 1000);
    } catch { showToast('Could not start the mic. Type instead.', 'error'); setTyped(true); }
  };

  const stopTalk = async () => {
    if (talkTimer.current) { clearInterval(talkTimer.current); talkTimer.current = null; }
    const rec = recRef.current; recRef.current = null;
    setTalking(false);
    if (!rec) return;
    try {
      const st = await rec.getStatusAsync();
      await rec.stopAndUnloadAsync();
      await setMode(false);
      const uri = rec.getURI();
      if (!uri || (st.durationMillis || 0) < 500) return;
      let b64 = ''; let contentType = 'audio/m4a';
      if (Platform.OS === 'web') {
        const blob = await fetch(uri).then(r => r.blob());
        contentType = blob.type || 'audio/webm';
        b64 = await new Promise<string>((res, rej) => { const fr = new FileReader(); fr.onload = () => res(String(fr.result).split(',')[1] || ''); fr.onerror = rej; fr.readAsDataURL(blob); });
      } else {
        const { File: ExpoFile } = await import('expo-file-system');
        b64 = await new ExpoFile(uri).base64();
      }
      await sendTurn({ audio_b64: b64, content_type: contentType });
    } catch { showToast('Could not send that, try again', 'error'); }
  };

  const sendText = async () => { const t = text.trim(); if (!t) return; setText(''); await sendTurn({ text: t }); };

  const leave = () => {
    const repTurns = turns.filter(t => t.role === 'rep').length;
    if (phase !== 'live') { router.back(); return; }
    showConfirm('End practice call?', repTurns >= 2 ? 'Jessi will grade what you have so far.' : 'Nothing to grade yet, so this one will not be saved.', () => { if (repTurns >= 2) finish(); else router.back(); }, undefined, repTurns >= 2 ? 'End & grade' : 'Leave');
  };

  const mood = [...turns].reverse().find(t => t.role === 'customer')?.mood;
  const micLabel = talking ? `Tap when done · ${fmtClock(talkSecs)}` : thinking ? `${persona?.name?.split(' ')[0] || 'Customer'} is thinking…` : speaking ? 'Tap to talk (interrupts)' : 'Tap to talk';

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      <View style={{ flexDirection: 'row', alignItems: 'center', paddingHorizontal: 12, height: 50, gap: 10 }}>
        <TouchableOpacity onPress={leave} hitSlop={10} style={{ padding: 6 }} {...tid('practice-back')}><Ionicons name="chevron-back" size={26} color={GOLD} /></TouchableOpacity>
        <View style={{ flex: 1, alignItems: 'center' }}>
          <Text style={{ fontSize: 15, fontWeight: '800', color: colors.text }} numberOfLines={1} {...tid('practice-title')}>{title || 'Practice call'}</Text>
          <Text style={{ fontSize: 12, color: phase === 'live' ? GREEN : colors.textSecondary, fontWeight: '700' }} {...tid('practice-timer')}>{phase === 'connecting' ? 'Connecting…' : phase === 'grading' ? 'Grading…' : `On the line · ${fmtClock(elapsed)}`}</Text>
        </View>
        <View style={{ width: 38 }} />
      </View>

      {phase === 'connecting' && <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', gap: 12 }}><ActivityIndicator color={GOLD} size="large" /><Text style={{ color: colors.textSecondary }}>Dialing the customer…</Text></View>}
      {phase === 'failed' && <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', gap: 12 }} {...tid('practice-failed')}><Ionicons name="call-outline" size={40} color={RED} /><Text style={{ color: colors.text, fontWeight: '700' }}>Could not connect</Text><TouchableOpacity onPress={() => router.back()}><Text style={{ color: GOLD, fontWeight: '800' }}>Go back</Text></TouchableOpacity></View>}
      {phase === 'grading' && (
        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', gap: 14, padding: 30 }} {...tid('practice-grading')}>
          <ActivityIndicator color={GOLD} size="large" />
          <Text style={{ fontSize: 17, fontWeight: '800', color: colors.text }}>Jessi is grading your call</Text>
          <Text style={{ fontSize: 13, color: colors.textSecondary, textAlign: 'center', lineHeight: 19 }}>Checking the scorecard, the script points and writing coaching. About 20 seconds.</Text>
        </View>
      )}

      {phase === 'live' && persona && (
        <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
          <View style={{ alignItems: 'center', paddingVertical: 12, gap: 6 }} {...tid('practice-persona')}>
            <Animated.View style={{ width: 84, height: 84, borderRadius: 42, backgroundColor: speaking ? GOLD : talking ? RED : colors.card, borderWidth: 3, borderColor: speaking ? GOLD : talking ? RED : colors.border, alignItems: 'center', justifyContent: 'center', transform: [{ scale: pulse }] }}>
              <Text style={{ fontSize: 28, fontWeight: '800', color: speaking || talking ? '#111' : colors.text }}>{initials(persona.name)}</Text>
            </Animated.View>
            <Text style={{ fontSize: 18, fontWeight: '800', color: colors.text }}>{persona.name}</Text>
            <View style={{ flexDirection: 'row', gap: 6, alignItems: 'center' }}>
              <View style={{ paddingHorizontal: 8, paddingVertical: 3, borderRadius: 8, backgroundColor: moodTone(mood) + '22' }}><Text style={{ fontSize: 11, fontWeight: '800', color: moodTone(mood) }} {...tid('practice-mood')}>{(mood || 'neutral').toUpperCase()}</Text></View>
              <Text style={{ fontSize: 12, color: colors.textSecondary }} numberOfLines={1}>{speaking ? 'Speaking…' : talking ? 'Listening to you' : thinking ? 'Thinking…' : 'Waiting on you'}</Text>
            </View>
          </View>

          <ScrollView ref={scrollRef} style={{ flex: 1 }} contentContainerStyle={{ paddingHorizontal: 16, paddingBottom: 12, gap: 10 }} {...tid('practice-transcript')}>
            {turns.map((t, i) => (
              <View key={i} style={{ flexDirection: 'row', justifyContent: t.role === 'rep' ? 'flex-end' : 'flex-start' }}>
                <TouchableOpacity disabled={t.role === 'rep' || !t.audio_url} onPress={() => play(t.audio_url)} activeOpacity={0.8}
                  style={{ maxWidth: '84%', backgroundColor: t.role === 'rep' ? GOLD : colors.card, borderRadius: 18, borderBottomRightRadius: t.role === 'rep' ? 4 : 18, borderBottomLeftRadius: t.role === 'rep' ? 18 : 4, padding: 12, borderWidth: t.role === 'rep' ? 0 : 1, borderColor: colors.border }} {...tid(`practice-turn-${i}`)}>
                  <Text style={{ fontSize: 15, lineHeight: 21, color: t.role === 'rep' ? '#111' : colors.text }}>{t.text}</Text>
                  {t.role === 'customer' && !!t.audio_url && <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4, marginTop: 6 }}><Ionicons name="volume-medium" size={12} color={colors.textSecondary} /><Text style={{ fontSize: 10.5, color: colors.textSecondary, fontWeight: '700' }}>Tap to replay</Text></View>}
                </TouchableOpacity>
              </View>
            ))}
            {thinking && <View style={{ flexDirection: 'row' }}><View style={{ backgroundColor: colors.card, borderRadius: 18, padding: 12, borderWidth: 1, borderColor: colors.border }}><ActivityIndicator size="small" color={GOLD} /></View></View>}
            {ended && <Text style={{ textAlign: 'center', fontSize: 12.5, color: colors.textSecondary, fontStyle: 'italic', marginTop: 6 }} {...tid('practice-ended-note')}>{persona.name.split(' ')[0]} hung up. Grading in a moment…</Text>}
          </ScrollView>

          <View style={{ padding: 16, paddingBottom: 26, borderTopWidth: 1, borderTopColor: colors.border, gap: 12 }}>
            {typed ? (
              <View style={{ flexDirection: 'row', alignItems: 'flex-end', gap: 8 }}>
                <TouchableOpacity onPress={() => setTyped(false)} style={{ width: 44, height: 44, borderRadius: 22, backgroundColor: colors.card, alignItems: 'center', justifyContent: 'center', borderWidth: 1, borderColor: colors.border }} {...tid('practice-use-mic')}><Ionicons name="mic" size={20} color={colors.text} /></TouchableOpacity>
                <TextInput value={text} onChangeText={setText} placeholder="Type what you'd say…" placeholderTextColor={colors.textSecondary} multiline editable={!thinking && !ended}
                  style={{ flex: 1, minHeight: 44, maxHeight: 110, backgroundColor: colors.card, borderRadius: 16, paddingHorizontal: 14, paddingVertical: 10, color: colors.text, fontSize: 15, borderWidth: 1, borderColor: colors.border }} {...tid('practice-text-input')} />
                <TouchableOpacity onPress={sendText} disabled={!text.trim() || thinking || ended} style={{ width: 44, height: 44, borderRadius: 22, backgroundColor: text.trim() && !thinking ? GOLD : colors.surface, alignItems: 'center', justifyContent: 'center' }} {...tid('practice-text-send')}><Ionicons name="arrow-up" size={20} color={text.trim() && !thinking ? '#111' : colors.textSecondary} /></TouchableOpacity>
                <TouchableOpacity onPress={leave} style={{ width: 44, height: 44, borderRadius: 22, backgroundColor: RED, alignItems: 'center', justifyContent: 'center' }} {...tid('practice-end-btn')}>
                  <Ionicons name="call" size={19} color="#fff" style={{ transform: [{ rotate: '135deg' }] }} />
                </TouchableOpacity>
              </View>
            ) : (
              <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
                <TouchableOpacity onPress={() => setTyped(true)} style={{ width: 52, height: 52, borderRadius: 26, backgroundColor: colors.card, alignItems: 'center', justifyContent: 'center', borderWidth: 1, borderColor: colors.border }} {...tid('practice-use-keyboard')}>
                  <Ionicons name="chatbox-ellipses-outline" size={22} color={colors.text} />
                </TouchableOpacity>
                <TouchableOpacity onPress={talking ? stopTalk : startTalk} disabled={thinking || ended} activeOpacity={0.85}
                  style={{ width: 86, height: 86, borderRadius: 43, backgroundColor: talking ? RED : thinking || ended ? colors.surface : GOLD, alignItems: 'center', justifyContent: 'center', borderWidth: 4, borderColor: talking ? RED + '55' : GOLD + '33' }} {...tid('practice-mic-btn')}>
                  {thinking ? <ActivityIndicator color={colors.textSecondary} /> : <Ionicons name={talking ? 'stop' : 'mic'} size={38} color={talking ? '#fff' : ended ? colors.textSecondary : '#111'} />}
                </TouchableOpacity>
                <TouchableOpacity onPress={leave} style={{ width: 52, height: 52, borderRadius: 26, backgroundColor: RED, alignItems: 'center', justifyContent: 'center' }} {...tid('practice-end-btn')}>
                  <Ionicons name="call" size={22} color="#fff" style={{ transform: [{ rotate: '135deg' }] }} />
                </TouchableOpacity>
              </View>
            )}
            {!typed && <Text style={{ textAlign: 'center', fontSize: 12.5, fontWeight: '700', color: talking ? RED : colors.textSecondary }} {...tid('practice-mic-label')}>{micLabel}</Text>}
          </View>
        </KeyboardAvoidingView>
      )}
    </SafeAreaView>
  );
}
