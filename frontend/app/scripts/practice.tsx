import React, { useCallback, useEffect, useRef, useState } from 'react';
import { View, Text, ScrollView, TouchableOpacity, ActivityIndicator, TextInput, Platform, Animated, KeyboardAvoidingView } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useLocalSearchParams } from 'expo-router';
import api from '../../services/api';
import { showConfirm } from '../../services/alert';
import { useAuthStore } from '../../store/authStore';
import { useThemeStore } from '../../store/themeStore';
import { useToast } from '../../components/common/Toast';
import { GOLD, RED, GREEN, tid, initials, fmtClock, moodTone, type Turn, type Persona } from '../../components/scripts/shared';

type Mode = 'phone' | 'text';
type Phase = 'choose' | 'connecting' | 'live' | 'grading' | 'failed';
const maskPhone = (p?: string | null) => { const d = (p || '').replace(/\D/g, '').slice(-10); return d.length === 10 ? `(${d.slice(0, 3)}) •••-${d.slice(6)}` : p || ''; };
const PHONE_LABEL: Record<string, string> = { dialing: 'Calling your phone…', queued: 'Calling your phone…', initiated: 'Calling your phone…', ringing: 'Ringing… pick up', live: 'On the line', ending: 'Wrapping up…', grading: 'Grading…' };

export default function PracticeCall() {
  const router = useRouter();
  const { script, assignment, enrollment, course } = useLocalSearchParams<{ script: string; assignment?: string; enrollment?: string; course?: string }>();
  const { user } = useAuthStore();
  const { colors } = useThemeStore();
  const { showToast } = useToast();
  const [mode, setMode] = useState<Mode | null>(null);
  const [phase, setPhase] = useState<Phase>('choose');
  const [sid, setSid] = useState<string | null>(null);
  const [persona, setPersona] = useState<Persona | null>(null);
  const [inbound, setInbound] = useState(false);
  const [title, setTitle] = useState('');
  const [turns, setTurns] = useState<Turn[]>([]);
  const [status, setStatus] = useState('dialing');
  const [failReason, setFailReason] = useState('');
  const [thinking, setThinking] = useState(false);
  const [ended, setEnded] = useState(false);
  const [text, setText] = useState('');
  const [elapsed, setElapsed] = useState(0);
  const scrollRef = useRef<ScrollView>(null);
  const pulse = useRef(new Animated.Value(1)).current;
  const endingRef = useRef(false);
  const pollRef = useRef<any>(null);

  const speaking = mode === 'phone' && phase === 'live' && status === 'live';
  useEffect(() => {
    const loop = Animated.loop(Animated.sequence([Animated.timing(pulse, { toValue: 1.1, duration: 700, useNativeDriver: true }), Animated.timing(pulse, { toValue: 1, duration: 700, useNativeDriver: true })]));
    if (speaking || (phase === 'connecting' && mode === 'phone')) loop.start(); else pulse.setValue(1);
    return () => loop.stop();
  }, [speaking, phase, mode]);
  useEffect(() => { const t = setInterval(() => phase === 'live' && setElapsed(e => e + 1), 1000); return () => clearInterval(t); }, [phase]);
  useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current); }, []);
  useEffect(() => { setTimeout(() => scrollRef.current?.scrollToEnd({ animated: true }), 80); }, [turns.length, thinking]);

  useEffect(() => { if (script) api.get(`/scripts/${script}`).then(r => setTitle(r.data?.title || '')).catch(() => {}); }, [script]);

  const goResult = useCallback((id: string) => { if (pollRef.current) clearInterval(pollRef.current); router.replace(`/scripts/result?session=${id}${course ? `&course=${course}` : ''}` as any); }, [course]);

  // ---- phone mode: we ring the rep's cell, then just mirror the live transcript
  const startPhone = async () => {
    setMode('phone'); setPhase('connecting');
    try {
      const res = await api.post('/scripts/roleplay/call', { script_id: script, assignment_id: assignment || null, enrollment_id: enrollment || null });
      setSid(res.data.session_id); setPersona(res.data.persona); setInbound(res.data.direction === 'inbound'); setTitle(res.data.script_title || 'Practice call'); setStatus('dialing'); setPhase('live');
      pollRef.current = setInterval(async () => {
        try {
          const g = await api.get(`/scripts/roleplay/${res.data.session_id}`);
          setTurns(g.data.turns || []);
          setStatus(g.data.status === 'dialing' ? (g.data.call_status === 'ringing' ? 'ringing' : 'dialing') : g.data.status);
          if (g.data.status === 'completed') goResult(res.data.session_id);
          else if (g.data.status === 'grading') setPhase('grading');
          else if (g.data.status === 'failed' || g.data.status === 'abandoned') { clearInterval(pollRef.current); setFailReason(g.data.fail_reason || 'The call ended early'); setPhase('failed'); }
        } catch { /* keep polling */ }
      }, 2000);
    } catch (e: any) { setFailReason(e?.response?.data?.detail || 'Could not place the call'); setPhase('failed'); }
  };
  const hangup = async () => {
    if (!sid) return;
    setPhase('grading');
    try { await api.post(`/scripts/roleplay/${sid}/hangup`); } catch { /* status poll decides */ }
  };

  // ---- text mode: typed turns, no audio anywhere
  const startText = async () => {
    setMode('text'); setPhase('connecting');
    try {
      const res = await api.post('/scripts/roleplay/start', { script_id: script, assignment_id: assignment || null, enrollment_id: enrollment || null });
      setSid(res.data.session_id); setPersona(res.data.persona); setInbound(res.data.direction === 'inbound'); setTitle(res.data.script_title || 'Practice call'); setTurns(res.data.customer ? [res.data.customer] : []); setStatus('live'); setPhase('live');
    } catch (e: any) { setFailReason(e?.response?.data?.detail || 'Could not start'); setPhase('failed'); }
  };
  const finishText = useCallback(async () => {
    if (!sid || endingRef.current) return;
    endingRef.current = true; setPhase('grading');
    try { await api.post(`/scripts/roleplay/${sid}/end`, {}, { timeout: 120000 }); goResult(sid); }
    catch (e: any) { showToast(e?.response?.data?.detail || 'Grading failed, try ending again', 'error'); endingRef.current = false; setPhase('live'); }
  }, [sid]);
  useEffect(() => { if (mode === 'text' && ended && !thinking) { const t = setTimeout(finishText, 900); return () => clearTimeout(t); } }, [ended, thinking, finishText, mode]);
  const sendText = async () => {
    const t = text.trim(); if (!t || !sid) return;
    setText(''); setThinking(true);
    try {
      const res = await api.post(`/scripts/roleplay/${sid}/turn`, { text: t }, { timeout: 90000 });
      setTurns(x => [...x, res.data.rep, res.data.customer]);
      if (res.data.ended) setEnded(true);
    } catch (e: any) {
      if (e?.response?.status === 409) setEnded(true); else showToast(e?.response?.data?.detail || 'Try that again', 'error');
    } finally { setThinking(false); }
  };

  const leave = () => {
    const repTurns = turns.filter(t => t.role === 'rep').length;
    if (phase !== 'live') { if (pollRef.current) clearInterval(pollRef.current); router.back(); return; }
    if (mode === 'phone') { showConfirm('Hang up?', repTurns >= 2 ? 'Jessi will grade what you have so far.' : 'The call will end. Nothing to grade yet.', hangup, undefined, 'Hang up'); return; }
    showConfirm('End practice call?', repTurns >= 2 ? 'Jessi will grade what you have so far.' : 'Nothing to grade yet, so this one will not be saved.', () => { if (repTurns >= 2) finishText(); else router.back(); }, undefined, repTurns >= 2 ? 'End & grade' : 'Leave');
  };

  const mood = [...turns].reverse().find(t => t.role === 'customer')?.mood;
  const subtitle = phase === 'connecting' ? (mode === 'phone' ? 'Calling your phone…' : 'Connecting…') : phase === 'grading' ? 'Grading…' : phase === 'live' ? (mode === 'phone' && status !== 'live' ? PHONE_LABEL[status] || 'Calling…' : `On the line · ${fmtClock(elapsed)}`) : '';

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      <View style={{ flexDirection: 'row', alignItems: 'center', paddingHorizontal: 12, height: 50, gap: 10 }}>
        <TouchableOpacity onPress={leave} hitSlop={10} style={{ padding: 6 }} {...tid('practice-back')}><Ionicons name="chevron-back" size={26} color={GOLD} /></TouchableOpacity>
        <View style={{ flex: 1, alignItems: 'center' }}>
          <Text style={{ fontSize: 15, fontWeight: '800', color: colors.text }} numberOfLines={1} {...tid('practice-title')}>{title || 'Practice call'}</Text>
          {!!subtitle && <Text style={{ fontSize: 12, color: phase === 'live' && (mode === 'text' || status === 'live') ? GREEN : colors.textSecondary, fontWeight: '700' }} {...tid('practice-timer')}>{subtitle}</Text>}
        </View>
        <View style={{ width: 38 }} />
      </View>

      {phase === 'choose' && (
        <ScrollView contentContainerStyle={{ padding: 20, gap: 14 }} {...tid('practice-chooser')}>
          <Text style={{ fontSize: 22, fontWeight: '800', color: colors.text }}>How do you want to practice?</Text>
          <TouchableOpacity onPress={startPhone} activeOpacity={0.85} style={{ backgroundColor: GOLD, borderRadius: 18, padding: 18, gap: 8 }} {...tid('practice-mode-phone')}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
              <View style={{ width: 44, height: 44, borderRadius: 22, backgroundColor: '#11111122', alignItems: 'center', justifyContent: 'center' }}><Ionicons name="call" size={22} color="#111" /></View>
              <View style={{ flex: 1 }}>
                <Text style={{ fontSize: 17, fontWeight: '800', color: '#111' }}>Call my phone</Text>
                <Text style={{ fontSize: 13, color: '#111', opacity: 0.8 }}>{user?.phone ? `We ring ${maskPhone(user.phone)} in a few seconds` : 'Add your cell number to your profile first'}</Text>
              </View>
              <Ionicons name="chevron-forward" size={18} color="#111" />
            </View>
            <Text style={{ fontSize: 13, color: '#111', opacity: 0.85, lineHeight: 18 }}>A real call. The customer answers, you talk like you would on the floor, interrupt them, hang up when you're done. Scored the moment you hang up.</Text>
          </TouchableOpacity>
          <TouchableOpacity onPress={startText} activeOpacity={0.85} style={{ backgroundColor: colors.card, borderRadius: 18, padding: 18, borderWidth: 1, borderColor: colors.border, flexDirection: 'row', alignItems: 'center', gap: 10 }} {...tid('practice-mode-text')}>
            <View style={{ width: 44, height: 44, borderRadius: 22, backgroundColor: GOLD + '22', alignItems: 'center', justifyContent: 'center' }}><Ionicons name="chatbox-ellipses" size={22} color={GOLD} /></View>
            <View style={{ flex: 1 }}>
              <Text style={{ fontSize: 16, fontWeight: '800', color: colors.text }}>Practice by typing</Text>
              <Text style={{ fontSize: 13, color: colors.textSecondary, lineHeight: 18 }}>Silent mode for the showroom. Type what you'd say, the customer types back.</Text>
            </View>
            <Ionicons name="chevron-forward" size={18} color={colors.textSecondary} />
          </TouchableOpacity>
        </ScrollView>
      )}

      {phase === 'connecting' && <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', gap: 12 }}><ActivityIndicator color={GOLD} size="large" /><Text style={{ color: colors.textSecondary }}>{mode === 'phone' ? 'Dialing your phone…' : 'Connecting…'}</Text></View>}
      {phase === 'failed' && (
        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', gap: 12, padding: 30 }} {...tid('practice-failed')}>
          <Ionicons name="call-outline" size={40} color={RED} />
          <Text style={{ color: colors.text, fontWeight: '800', fontSize: 17 }}>Call didn't happen</Text>
          <Text style={{ color: colors.textSecondary, textAlign: 'center', lineHeight: 19 }} {...tid('practice-fail-reason')}>{failReason}</Text>
          <TouchableOpacity onPress={() => { setPhase('choose'); setMode(null); setTurns([]); setSid(null); }} style={{ marginTop: 8, height: 46, paddingHorizontal: 22, borderRadius: 12, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center' }} {...tid('practice-retry')}><Text style={{ fontWeight: '800', color: '#111' }}>Try again</Text></TouchableOpacity>
          <TouchableOpacity onPress={() => router.back()} {...tid('practice-failed-back')}><Text style={{ color: colors.textSecondary, fontWeight: '700' }}>Back to the script</Text></TouchableOpacity>
        </View>
      )}
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
            <Animated.View style={{ width: 84, height: 84, borderRadius: 42, backgroundColor: speaking ? GOLD : colors.card, borderWidth: 3, borderColor: speaking ? GOLD : colors.border, alignItems: 'center', justifyContent: 'center', transform: [{ scale: pulse }] }}>
              <Text style={{ fontSize: 28, fontWeight: '800', color: speaking ? '#111' : colors.text }}>{initials(persona.name)}</Text>
            </Animated.View>
            <Text style={{ fontSize: 18, fontWeight: '800', color: colors.text }}>{persona.name}</Text>
            <View style={{ flexDirection: 'row', gap: 6, alignItems: 'center' }}>
              <View style={{ paddingHorizontal: 8, paddingVertical: 3, borderRadius: 8, backgroundColor: moodTone(mood) + '22' }}><Text style={{ fontSize: 11, fontWeight: '800', color: moodTone(mood) }} {...tid('practice-mood')}>{(mood || 'neutral').toUpperCase()}</Text></View>
              <Text style={{ fontSize: 12, color: colors.textSecondary }} numberOfLines={1}>{mode === 'phone' ? (status === 'live' ? (inbound && turns.length === 0 ? 'Waiting for you to answer' : 'Talking on your phone') : PHONE_LABEL[status] || 'Calling…') : thinking ? 'Thinking…' : inbound && turns.length === 0 ? 'Calling you…' : 'Waiting on you'}</Text>
            </View>
          </View>

          <ScrollView ref={scrollRef} style={{ flex: 1 }} contentContainerStyle={{ paddingHorizontal: 16, paddingBottom: 12, gap: 10 }} {...tid('practice-transcript')}>
            {mode === 'phone' && turns.length === 0 && (
              <View style={{ alignItems: 'center', padding: 24, gap: 8 }} {...tid('practice-phone-waiting')}>
                <Ionicons name="call" size={28} color={GOLD} />
                <Text style={{ fontSize: 14, color: colors.textSecondary, textAlign: 'center', lineHeight: 20 }}>{inbound
                  ? `Pick up when your phone rings and answer it like a real inbound call: "Thanks for calling, this is ${(user?.name || '').split(' ')[0] || 'your name'}." ${persona.name.split(' ')[0]} waits for you to speak first.`
                  : `Pick up when your phone rings. ${persona.name.split(' ')[0]} starts talking right away and this screen follows along.`}</Text>
              </View>
            )}
            {mode === 'text' && inbound && turns.length === 0 && (
              <View style={{ alignItems: 'center', padding: 24, gap: 8 }} {...tid('practice-inbound-waiting')}>
                <Ionicons name="call-outline" size={28} color={GOLD} />
                <Text style={{ fontSize: 14, color: colors.textSecondary, textAlign: 'center', lineHeight: 20 }}>{persona.name.split(' ')[0]} is calling in. Type how you'd answer the phone, they'll talk after your greeting.</Text>
              </View>
            )}
            {turns.map((t, i) => (
              <View key={i} style={{ flexDirection: 'row', justifyContent: t.role === 'rep' ? 'flex-end' : 'flex-start' }}>
                <View style={{ maxWidth: '84%', backgroundColor: t.role === 'rep' ? GOLD : colors.card, borderRadius: 18, borderBottomRightRadius: t.role === 'rep' ? 4 : 18, borderBottomLeftRadius: t.role === 'rep' ? 18 : 4, padding: 12, borderWidth: t.role === 'rep' ? 0 : 1, borderColor: colors.border }} {...tid(`practice-turn-${i}`)}>
                  <Text style={{ fontSize: 15, lineHeight: 21, color: t.role === 'rep' ? '#111' : colors.text }}>{t.text}</Text>
                </View>
              </View>
            ))}
            {thinking && <View style={{ flexDirection: 'row' }}><View style={{ backgroundColor: colors.card, borderRadius: 18, padding: 12, borderWidth: 1, borderColor: colors.border }}><ActivityIndicator size="small" color={GOLD} /></View></View>}
            {ended && <Text style={{ textAlign: 'center', fontSize: 12.5, color: colors.textSecondary, fontStyle: 'italic', marginTop: 6 }} {...tid('practice-ended-note')}>{persona.name.split(' ')[0]} hung up. Grading in a moment…</Text>}
          </ScrollView>

          <View style={{ padding: 16, paddingBottom: 26, borderTopWidth: 1, borderTopColor: colors.border, gap: 12 }}>
            {mode === 'text' ? (
              <View style={{ flexDirection: 'row', alignItems: 'flex-end', gap: 8 }}>
                <TextInput value={text} onChangeText={setText} placeholder={inbound && turns.length === 0 ? 'Thanks for calling, this is…' : "Type what you'd say…"} placeholderTextColor={colors.textSecondary} multiline editable={!thinking && !ended}
                  style={{ flex: 1, minHeight: 44, maxHeight: 110, backgroundColor: colors.card, borderRadius: 16, paddingHorizontal: 14, paddingVertical: 10, color: colors.text, fontSize: 15, borderWidth: 1, borderColor: colors.border }} {...tid('practice-text-input')} />
                <TouchableOpacity onPress={sendText} disabled={!text.trim() || thinking || ended} style={{ width: 44, height: 44, borderRadius: 22, backgroundColor: text.trim() && !thinking ? GOLD : colors.surface, alignItems: 'center', justifyContent: 'center' }} {...tid('practice-text-send')}><Ionicons name="arrow-up" size={20} color={text.trim() && !thinking ? '#111' : colors.textSecondary} /></TouchableOpacity>
                <TouchableOpacity onPress={leave} style={{ width: 44, height: 44, borderRadius: 22, backgroundColor: RED, alignItems: 'center', justifyContent: 'center' }} {...tid('practice-end-btn')}>
                  <Ionicons name="call" size={19} color="#fff" style={{ transform: [{ rotate: '135deg' }] }} />
                </TouchableOpacity>
              </View>
            ) : (
              <TouchableOpacity onPress={leave} style={{ height: 54, borderRadius: 27, backgroundColor: RED, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 10 }} {...tid('practice-end-btn')}>
                <Ionicons name="call" size={22} color="#fff" style={{ transform: [{ rotate: '135deg' }] }} />
                <Text style={{ fontSize: 16, fontWeight: '800', color: '#fff' }}>{status === 'live' ? 'Hang up & grade' : 'Cancel call'}</Text>
              </TouchableOpacity>
            )}
          </View>
        </KeyboardAvoidingView>
      )}
    </SafeAreaView>
  );
}
