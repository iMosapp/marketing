import React, { useEffect, useRef, useState } from 'react';
import { Modal, View, Text, TouchableOpacity, Platform, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Audio } from 'expo-av';
import api from '../../services/api';
import { showAlert } from '../../services/alert';
import { GOLD, RADIUS, SPACE, TYPE, tid, tint } from '../ui/tokens';
import { PrimaryButton } from '../ui/PrimaryButton';

export type Greeting = { has_greeting: boolean; duration: number; duration_display: string; url: string | null; default_text: string; max_seconds: number };

const fmt = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;

// Record the message callers hear when the rep does not pick up: record -> listen -> use it.
export const GreetingSheet = ({ visible, greeting, colors, onClose, onSaved }: {
  visible: boolean; greeting: Greeting | null; colors: any; onClose: () => void; onSaved: (g: Greeting) => void;
}) => {
  const [phase, setPhase] = useState<'idle' | 'recording' | 'review' | 'saving'>('idle');
  const [secs, setSecs] = useState(0);
  const [uri, setUri] = useState<string | null>(null);
  const [playing, setPlaying] = useState(false);
  const recRef = useRef<Audio.Recording | null>(null);
  const soundRef = useRef<Audio.Sound | null>(null);
  const timerRef = useRef<any>(null);
  const max = greeting?.max_seconds || 60;

  useEffect(() => { if (!visible) reset(); }, [visible]);
  const reset = async () => {
    if (timerRef.current) clearInterval(timerRef.current);
    try { await recRef.current?.stopAndUnloadAsync(); } catch {}
    try { await soundRef.current?.unloadAsync(); } catch {}
    recRef.current = null; soundRef.current = null;
    setPhase('idle'); setSecs(0); setUri(null); setPlaying(false);
  };

  const start = async () => {
    try {
      const { status } = await Audio.requestPermissionsAsync();
      if (status !== 'granted') { showAlert('Microphone needed', 'Allow the microphone to record your greeting.'); return; }
      await Audio.setAudioModeAsync({ allowsRecordingIOS: true, playsInSilentModeIOS: true });
      const rec = new Audio.Recording();
      await rec.prepareToRecordAsync(Audio.RecordingOptionsPresets.HIGH_QUALITY);
      await rec.startAsync();
      recRef.current = rec; setSecs(0); setPhase('recording');
      timerRef.current = setInterval(() => setSecs(s => { if (s + 1 >= max) { stop(); return max; } return s + 1; }), 1000);
    } catch (e) { console.warn('[Greeting] start failed', e); showAlert('Could not start recording', 'Try again.'); }
  };
  const stop = async () => {
    if (timerRef.current) clearInterval(timerRef.current);
    const rec = recRef.current; recRef.current = null;
    if (!rec) return;
    try { await rec.stopAndUnloadAsync(); setUri(rec.getURI()); setPhase('review'); } catch { setPhase('idle'); }
    try { await Audio.setAudioModeAsync({ allowsRecordingIOS: false, playsInSilentModeIOS: true }); } catch {}
  };
  const preview = async () => {
    if (!uri) return;
    if (soundRef.current) { try { await soundRef.current.unloadAsync(); } catch {} soundRef.current = null; if (playing) { setPlaying(false); return; } }
    const { sound } = await Audio.Sound.createAsync({ uri }, { shouldPlay: true }, st => { if (st.isLoaded && st.didJustFinish) { setPlaying(false); } });
    soundRef.current = sound; setPlaying(true);
  };
  const save = async () => {
    if (!uri) return;
    setPhase('saving');
    try {
      const fd = new FormData();
      if (Platform.OS === 'web') { const blob = await (await fetch(uri)).blob(); fd.append('file', blob, 'greeting.webm'); }
      else fd.append('file', { uri, type: 'audio/m4a', name: 'greeting.m4a' } as any);
      const r = await api.post('/voicemails/greeting', fd, { headers: { 'Content-Type': 'multipart/form-data' }, timeout: 120000 });
      onSaved(r.data); onClose();
    } catch (e: any) {
      setPhase('review');
      showAlert('Could not save', e?.response?.data?.detail || 'Try recording again.');
    }
  };

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <TouchableOpacity style={{ flex: 1, backgroundColor: '#00000099', justifyContent: 'flex-end' }} activeOpacity={1} onPress={phase === 'recording' ? undefined : onClose}>
        <TouchableOpacity activeOpacity={1} style={{ backgroundColor: colors.bg, borderTopLeftRadius: 24, borderTopRightRadius: 24, padding: SPACE.xl, paddingBottom: Platform.OS === 'ios' ? 36 : SPACE.xl, gap: SPACE.lg }} {...tid('greeting-sheet')}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: SPACE.md }}>
            <View style={{ width: 48, height: 48, borderRadius: 24, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center' }}>
              <Ionicons name="recording" size={24} color="#0B0B0D" />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={{ fontSize: 20, fontWeight: '800', color: colors.text }}>Your voicemail greeting</Text>
              <Text style={{ fontSize: TYPE.caption, color: colors.textSecondary, marginTop: 2 }}>What callers hear when you don't pick up · up to {fmt(max)}</Text>
            </View>
            {phase !== 'recording' ? <TouchableOpacity onPress={onClose} hitSlop={10} {...tid('greeting-close')}><Ionicons name="close" size={24} color={colors.textSecondary} /></TouchableOpacity> : null}
          </View>

          {phase === 'idle' ? (
            <View style={{ backgroundColor: colors.card, borderRadius: RADIUS.lg, borderWidth: 1, borderColor: tint(GOLD, 0.35), padding: SPACE.lg, gap: 6 }}>
              <Text style={{ fontSize: TYPE.label, fontWeight: '800', color: GOLD, letterSpacing: 1 }}>SOMETHING LIKE</Text>
              <Text style={{ fontSize: TYPE.body, color: colors.text, lineHeight: 22, fontStyle: 'italic' }}>
                "Hi, you've reached {'{your name}'} at {'{your store}'}. I'm with a customer right now. Leave your name and number and I'll call you right back, or text me at this number."
              </Text>
              <Text style={{ fontSize: TYPE.caption, color: colors.textSecondary, marginTop: 4 }}>Find a quiet spot, hold the phone like a call, and speak a little slower than normal.</Text>
            </View>
          ) : null}

          <View style={{ alignItems: 'center', gap: SPACE.md, paddingVertical: SPACE.sm }}>
            {phase === 'recording' ? (
              <>
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}><View style={{ width: 10, height: 10, borderRadius: 5, backgroundColor: '#FF3B30' }} /><Text style={{ fontSize: 34, fontWeight: '800', color: colors.text, fontVariant: ['tabular-nums'] }} {...tid('greeting-timer')}>{fmt(secs)}</Text><Text style={{ fontSize: 14, color: colors.textSecondary }}>/ {fmt(max)}</Text></View>
                <TouchableOpacity onPress={stop} style={{ width: 84, height: 84, borderRadius: 42, backgroundColor: '#FF3B30', alignItems: 'center', justifyContent: 'center' }} {...tid('greeting-stop')}>
                  <Ionicons name="stop" size={34} color="#fff" />
                </TouchableOpacity>
                <Text style={{ fontSize: 14, color: colors.textSecondary }}>Tap to stop</Text>
              </>
            ) : phase === 'idle' ? (
              <>
                <TouchableOpacity onPress={start} style={{ width: 84, height: 84, borderRadius: 42, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center' }} {...tid('greeting-record')}>
                  <Ionicons name="mic" size={36} color="#0B0B0D" />
                </TouchableOpacity>
                <Text style={{ fontSize: 14, color: colors.textSecondary }}>Tap to start recording</Text>
              </>
            ) : (
              <>
                <TouchableOpacity onPress={preview} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 12, paddingHorizontal: 20, borderRadius: 999, backgroundColor: colors.card, borderWidth: 1, borderColor: tint(GOLD, 0.5) }} {...tid('greeting-preview')}>
                  <Ionicons name={playing ? 'pause' : 'play'} size={20} color={GOLD} />
                  <Text style={{ fontSize: 16, fontWeight: '700', color: colors.text }}>{playing ? 'Pause' : 'Listen'} · {fmt(secs)}</Text>
                </TouchableOpacity>
                {phase === 'saving' ? <ActivityIndicator color={GOLD} /> : (
                  <View style={{ width: '100%', gap: SPACE.sm }}>
                    <PrimaryButton label="Use this greeting" icon="checkmark" size="lg" full onPress={save} testID="greeting-save" />
                    <TouchableOpacity onPress={() => { reset(); }} style={{ alignItems: 'center', paddingVertical: SPACE.sm }} {...tid('greeting-again')}>
                      <Text style={{ fontSize: TYPE.body, fontWeight: '700', color: colors.textSecondary }}>Record again</Text>
                    </TouchableOpacity>
                  </View>
                )}
              </>
            )}
          </View>
        </TouchableOpacity>
      </TouchableOpacity>
    </Modal>
  );
};

// Top of the Voicemail tab: what callers hear today + record / listen / remove.
export const GreetingCard = ({ user, colors }: { user: any; colors: any }) => {
  const [g, setG] = useState<Greeting | null>(null);
  const [open, setOpen] = useState(false);
  const [playing, setPlaying] = useState(false);
  const soundRef = useRef<Audio.Sound | null>(null);
  useEffect(() => { api.get('/voicemails/greeting').then(r => setG(r.data)).catch(() => {}); return () => { soundRef.current?.unloadAsync().catch(() => {}); }; }, [user?._id]);

  const listen = async () => {
    if (!g?.url) return;
    if (soundRef.current) { try { await soundRef.current.unloadAsync(); } catch {} soundRef.current = null; if (playing) { setPlaying(false); return; } }
    try {
      await Audio.setAudioModeAsync({ playsInSilentModeIOS: true, allowsRecordingIOS: false });
      const { sound } = await Audio.Sound.createAsync({ uri: g.url }, { shouldPlay: true }, st => { if (st.isLoaded && st.didJustFinish) setPlaying(false); });
      soundRef.current = sound; setPlaying(true);
    } catch { showAlert('Could not play', 'Try again in a moment.'); }
  };
  const remove = () => showAlert('Use the default greeting?', `Callers will hear: "${g?.default_text}"`, [
    { text: 'Cancel', style: 'cancel' },
    { text: 'Remove mine', style: 'destructive', onPress: async () => { try { const r = await api.delete('/voicemails/greeting'); setG(r.data); } catch {} } },
  ]);

  if (!g) return null;
  return (
    <View style={{ marginHorizontal: 20, marginBottom: 10, borderRadius: 14, padding: 12, backgroundColor: colors.card, borderWidth: 1, borderColor: g.has_greeting ? `${GOLD}55` : colors.border, flexDirection: 'row', alignItems: 'center', gap: 12 }} {...tid('greeting-card')}>
      <TouchableOpacity onPress={g.has_greeting ? listen : () => setOpen(true)} style={{ width: 40, height: 40, borderRadius: 20, backgroundColor: g.has_greeting ? GOLD : `${GOLD}22`, alignItems: 'center', justifyContent: 'center' }} {...tid('greeting-listen')}>
        <Ionicons name={g.has_greeting ? (playing ? 'pause' : 'play') : 'mic'} size={18} color={g.has_greeting ? '#0B0B0D' : GOLD} />
      </TouchableOpacity>
      <View style={{ flex: 1 }}>
        <Text style={{ fontSize: 14, fontWeight: '800', color: colors.text }} {...tid('greeting-status')}>{g.has_greeting ? `Your greeting · ${g.duration_display}` : 'Default greeting'}</Text>
        <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 2 }} numberOfLines={2}>
          {g.has_greeting ? 'Callers hear your recording when you don\'t pick up.' : `Callers hear: "${g.default_text}"`}
        </Text>
      </View>
      <TouchableOpacity onPress={() => setOpen(true)} style={{ paddingVertical: 8, paddingHorizontal: 12, borderRadius: 10, backgroundColor: g.has_greeting ? colors.bg : GOLD }} {...tid('greeting-record-btn')}>
        <Text style={{ fontSize: 13, fontWeight: '800', color: g.has_greeting ? colors.text : '#0B0B0D' }}>{g.has_greeting ? 'Re-record' : 'Record'}</Text>
      </TouchableOpacity>
      {g.has_greeting ? (
        <TouchableOpacity onPress={remove} hitSlop={8} {...tid('greeting-remove')}><Ionicons name="trash-outline" size={18} color={colors.textSecondary} /></TouchableOpacity>
      ) : null}
      <GreetingSheet visible={open} greeting={g} colors={colors} onClose={() => setOpen(false)} onSaved={setG} />
    </View>
  );
};
