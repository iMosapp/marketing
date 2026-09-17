import React, { useCallback, useEffect, useRef, useState } from 'react';
import { View, Text, TouchableOpacity, ActivityIndicator, Animated, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import api from '../../services/api';
import { showConfirm } from '../../services/alert';
import { useAuthStore } from '../../store/authStore';
import { useThemeStore } from '../../store/themeStore';
import { GOLD, GREEN, RED, tid, fmtClock } from '../scripts/shared';

export type InterviewSession = {
  id: string; status: string; call_status?: string | null; fail_reason?: string | null; elapsed_s: number; rep_turns: number;
  covered: string[]; topics_total: number; highlights: string[]; applied_fields: string[]; extracted?: Record<string, any> | null;
  labels: Record<string, string>; ended_at?: string | null; voice?: any; turns?: { role: string; text: string; at?: string }[]; dry_run?: boolean; applied?: boolean;
};
export type InterviewStatus = {
  session: InterviewSession | null; voice: { configured: boolean; status: string; enrolled: boolean; percent?: number | null; at?: string | null; error?: string | null };
  phone: string; can_call: boolean; persona_filled: number; interviewed_at?: string | null; available: boolean; is_super_admin?: boolean;
  photo_request?: { status: 'open' | 'done' | 'expired'; had_photo: boolean; asked_at?: string | null; photo_saved_at?: string | null; sms_ok: boolean; to_phone?: string } | null;
};

const ACTIVE = ['dialing', 'live', 'ending', 'building'];
const CALL_LABEL: Record<string, string> = { queued: 'Calling your phone…', initiated: 'Calling your phone…', ringing: 'Ringing… pick up', 'in-progress': 'On the line' };

export const voiceLabel = (v: InterviewStatus['voice'] | undefined, admin?: boolean) => {
  if (!v) return '';
  if (v.enrolled) return 'Voice ID on';
  if (v.status === 'not_configured') return v.configured ? 'Voice ID: learning your voice from your interview recording…' : admin ? `Voice ID off on this server: ${v.error || 'PICOVOICE_ACCESS_KEY missing'}` : 'Voice ID: coming soon';
  if (v.status === 'partial') return `Voice ID: needs a longer call (${Math.round(v.percent || 0)}%)`;
  if (v.status === 'too_short') return 'Voice ID: call was too short';
  if (v.status === 'failed') return 'Voice ID: could not learn your voice yet';
  return '';
};

export function useInterviewStatus() {
  const [data, setData] = useState<InterviewStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const pollRef = useRef<any>(null);
  const load = useCallback(async () => {
    try { const r = await api.get('/interview/status'); setData(r.data); return r.data as InterviewStatus; }
    catch { return null; }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);
  const active = !!data?.session && ACTIVE.includes(data.session.status);
  useEffect(() => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
    if (active) pollRef.current = setInterval(load, 2500);
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [active, load]);
  return { data, loading, reload: load, setData };
}

export function InterviewCard({ compact, dryRun }: { compact?: boolean; dryRun?: boolean }) {
  const router = useRouter();
  const { colors } = useThemeStore();
  const setUser = useAuthStore((s: any) => s.setUser);
  const user = useAuthStore((s: any) => s.user);
  const { data, loading, reload, setData } = useInterviewStatus();
  const [busy, setBusy] = useState(false);
  const pulse = useRef(new Animated.Value(1)).current;
  const wasActive = useRef(false);

  const s = data?.session || null;
  const active = !!s && ACTIVE.includes(s.status);
  const onCall = !!s && ['dialing', 'live', 'ending'].includes(s.status);

  useEffect(() => {
    const loop = Animated.loop(Animated.sequence([Animated.timing(pulse, { toValue: 1.15, duration: 700, useNativeDriver: true }), Animated.timing(pulse, { toValue: 1, duration: 700, useNativeDriver: true })]));
    if (onCall) loop.start(); else pulse.setValue(1);
    return () => loop.stop();
  }, [onCall]);
  useEffect(() => {
    if (active) wasActive.current = true;
    else if (wasActive.current && s?.status === 'completed') {
      wasActive.current = false;
      if (s.applied) api.get('/auth/me').then(r => { if (r.data?.user) setUser({ ...user, ...r.data.user }); }).catch(() => {});
      router.push(`/interview/review?session=${s.id}` as any);
    }
  }, [active, s?.status]);

  const start = async () => {
    setBusy(true);
    try {
      const r = await api.post('/interview/start', { dry_run: !!dryRun });
      setData(d => d ? { ...d, session: r.data } : d);
      await reload();
    } catch (e: any) {
      const msg = e?.response?.data?.detail || 'Could not place the call, try again in a minute';
      setData(d => d ? { ...d, session: { ...(d.session || { id: '', elapsed_s: 0, rep_turns: 0, covered: [], topics_total: 10, highlights: [], applied_fields: [], labels: {} }), status: 'failed', fail_reason: msg } as any } : d);
    } finally { setBusy(false); }
  };
  const confirmRedo = () => showConfirm(dryRun ? 'Run the interview again?' : 'Redo the interview?', dryRun ? 'Jessi calls you again. Nothing is saved to your profile unless you tap Save afterwards.' : 'Jessi calls you again and updates your VA with what you say. Anything she learns replaces the old answers.', start, undefined, 'Call me');
  const hangup = () => { if (!s) return; showConfirm('Hang up?', s.rep_turns >= 3 ? (dryRun ? 'Jessi will write up what you said so far (nothing saved to your profile).' : 'Jessi will build your VA from what you said so far.') : 'The call ends and nothing is saved yet.', async () => { try { await api.post(`/interview/sessions/${s.id}/hangup`); } catch { /* poll decides */ } reload(); }, undefined, 'Hang up'); };

  if (loading || !data) return null;
  if (!dryRun && !data.available) return null;
  const done = s?.status === 'completed' || (!dryRun && !!data.interviewed_at);
  const st = StyleSheet.create({
    card: { marginHorizontal: compact ? 0 : 16, marginTop: compact ? 0 : 14, marginBottom: compact ? 16 : 0, backgroundColor: colors.card, borderRadius: 16, padding: 16, borderWidth: 1, borderColor: `${GOLD}55` },
    title: { fontSize: 15, fontWeight: '800', color: colors.text },
    sub: { fontSize: 12, color: colors.textSecondary, lineHeight: 17, marginTop: 3 },
    gold: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: GOLD, borderRadius: 12, paddingVertical: 12, paddingHorizontal: 14, marginTop: 12 },
    goldText: { fontSize: 14, fontWeight: '800', color: '#000' },
    ghost: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, borderRadius: 12, paddingVertical: 11, paddingHorizontal: 12, borderWidth: 1, borderColor: `${GOLD}66`, marginTop: 10, flex: 1 },
    ghostText: { fontSize: 13, fontWeight: '700', color: GOLD },
    status: { fontSize: 14, fontWeight: '700', color: colors.text },
    meta: { fontSize: 12, color: colors.textSecondary, marginTop: 2 },
    pill: { flexDirection: 'row', alignItems: 'center', gap: 5, alignSelf: 'flex-start', backgroundColor: `${GREEN}18`, borderRadius: 10, paddingHorizontal: 8, paddingVertical: 3, marginTop: 8 },
  });

  const header = (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
      <Animated.View style={{ width: 42, height: 42, borderRadius: 21, backgroundColor: `${GOLD}22`, alignItems: 'center', justifyContent: 'center', transform: [{ scale: pulse }] }}>
        <Ionicons name={onCall ? 'call' : 'mic'} size={20} color={GOLD} />
      </Animated.View>
      <View style={{ flex: 1 }}>
        <Text style={st.title}>{dryRun ? (done && !active ? 'Test run done' : 'Test the interview') : done && !active ? 'Jessi knows you' : 'Let Jessi interview you'}</Text>
        {!active && <Text style={st.sub}>{dryRun
          ? (done ? 'Nothing was saved to your profile. Open the write-up to read it or save it.' : `Jessi calls ${data.phone}, interviews you for about 5 minutes and writes up what she learned. Nothing is saved to your profile unless you tap Save afterwards.`)
          : done ? `${data.persona_filled} of 11 things your VA knows came from you.` : 'A 5 minute phone call. Jessi asks about you, then writes your VA, bio and card in your voice. She learns your voice too, so we always know when it is you on a call.'}</Text>}
      </View>
    </View>
  );

  if (active && s) {
    const label = s.status === 'building' ? 'Jessi is writing your profile…' : s.status === 'ending' ? 'Wrapping up…' : s.status === 'live' ? `On the line · ${fmtClock(s.elapsed_s)}` : CALL_LABEL[s.call_status || ''] || 'Calling your phone…';
    return (
      <View style={st.card} {...tid('interview-card')}>
        {header}
        <View style={{ marginTop: 12, flexDirection: 'row', alignItems: 'center', gap: 10 }}>
          {s.status === 'building' ? <ActivityIndicator color={GOLD} /> : <View style={{ width: 10, height: 10, borderRadius: 5, backgroundColor: s.status === 'live' ? GREEN : GOLD }} />}
          <View style={{ flex: 1 }}>
            <Text style={st.status} {...tid('interview-status')}>{label}</Text>
            <Text style={st.meta}>{s.status === 'building' ? (dryRun ? 'About a minute. Jessi is writing up what she learned (not saved to your profile).' : 'About a minute. Your VA, bio and card are being written.') : s.status === 'live' ? `${s.covered.length} of ${s.topics_total} topics · pick up ${data.phone}` : `Calling ${data.phone}`}</Text>
          </View>
        </View>
        {s.status !== 'building' && (
          <TouchableOpacity style={[st.ghost, { borderColor: `${RED}66` }]} onPress={hangup} {...tid('interview-hangup')}>
            <Ionicons name="call" size={15} color={RED} style={{ transform: [{ rotate: '135deg' }] }} />
            <Text style={[st.ghostText, { color: RED }]}>Hang up</Text>
          </TouchableOpacity>
        )}
      </View>
    );
  }

  const failed = s && (s.status === 'failed' || s.status === 'abandoned');
  const pr = data.photo_request;
  const photoRow = pr && (pr.status === 'open' || pr.status === 'done') && s && s.status === 'completed' ? (
    <View style={[st.pill, { backgroundColor: pr.status === 'done' ? `${GREEN}18` : `${GOLD}18`, alignSelf: 'stretch' }]} {...tid(pr.status === 'done' ? 'interview-photo-done' : 'interview-photo-hint')}>
      <Ionicons name={pr.status === 'done' ? 'checkmark-circle' : 'camera'} size={13} color={pr.status === 'done' ? GREEN : GOLD} />
      <Text style={{ fontSize: 12, fontWeight: '700', color: pr.status === 'done' ? GREEN : GOLD, flex: 1 }}>{pr.status === 'done' ? 'Your card photo came in by text' : pr.sms_ok ? `Check your texts: reply to Jessi with a photo and it goes on your card${pr.had_photo ? ' (replaces the current one)' : ''}` : 'Jessi could not text you for a photo. Add one under My Profile.'}</Text>
    </View>
  ) : null;
  return (
    <View style={st.card} {...tid('interview-card')}>
      {header}
      {failed && <Text style={{ fontSize: 12, color: RED, marginTop: 10, lineHeight: 17 }} {...tid('interview-fail-reason')}>{s.fail_reason || 'The call ended early'}</Text>}
      {photoRow}
      {done && !dryRun && (
        <View style={st.pill} {...tid('interview-voice-pill')}>
          <Ionicons name={data.voice.enrolled ? 'shield-checkmark' : 'shield-outline'} size={13} color={data.voice.enrolled ? GREEN : colors.textSecondary} />
          <Text style={{ fontSize: 12, fontWeight: '700', color: data.voice.enrolled ? GREEN : colors.textSecondary, flex: 1 }}>{voiceLabel(data.voice, data.is_super_admin) || 'Voice ID pending'}</Text>
        </View>
      )}
      {!data.can_call ? (
        <TouchableOpacity style={st.gold} onPress={() => router.push('/my-account' as any)} {...tid('interview-add-phone')}>
          <Ionicons name="call-outline" size={16} color="#000" />
          <Text style={st.goldText}>Add your cell number first</Text>
        </TouchableOpacity>
      ) : done && !failed ? (
        <View style={{ flexDirection: 'row', gap: 10 }}>
          <TouchableOpacity style={[st.ghost, { backgroundColor: GOLD, borderColor: GOLD }]} onPress={() => router.push(`/interview/review${s ? `?session=${s.id}` : ''}` as any)} {...tid('interview-review-btn')}>
            <Ionicons name="sparkles" size={15} color="#000" />
            <Text style={[st.ghostText, { color: '#000' }]}>What Jessi learned</Text>
          </TouchableOpacity>
          <TouchableOpacity style={st.ghost} onPress={confirmRedo} disabled={busy} {...tid('interview-redo-btn')}>
            {busy ? <ActivityIndicator size="small" color={GOLD} /> : <><Ionicons name="refresh" size={15} color={GOLD} /><Text style={st.ghostText}>{dryRun ? 'Run again' : 'Redo'}</Text></>}
          </TouchableOpacity>
        </View>
      ) : (
        <TouchableOpacity style={st.gold} onPress={s?.status === 'failed' && s.fail_reason?.includes('Jessi could not') ? () => router.push(`/interview/review?session=${s.id}` as any) : start} disabled={busy} {...tid('interview-start-btn')}>
          {busy ? <ActivityIndicator size="small" color="#000" /> : <><Ionicons name="call" size={16} color="#000" /><Text style={st.goldText}>{failed ? 'Call me again' : `Call me now at ${data.phone}`}</Text></>}
        </TouchableOpacity>
      )}
    </View>
  );
}
