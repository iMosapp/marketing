import React, { useCallback, useEffect, useRef, useState } from 'react';
import { View, Text, ScrollView, TouchableOpacity, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useLocalSearchParams } from 'expo-router';
import api from '../../../services/api';
import { useThemeStore } from '../../../store/themeStore';
import { useToast } from '../../../components/common/Toast';
import { showConfirm } from '../../../services/alert';
import { ScreenHeader, HeaderTextButton } from '../../../components/common/ScreenHeader';
import { DispositionSheet } from '../../../components/dialer/DispositionSheet';
import { GOLD, GREEN, RED, AMBER, GREY, BLUE, tid, pct, fmtDur, fmtWhen, type SessionView, type Leg } from '../../../components/dialer/shared';

const LEG_TONE: Record<string, string> = { queued: GREY, ringing: AMBER, answered: GREEN, connected: GREEN, abandoned: RED, voicemail: GREY, no_answer: GREY, busy: GREY, failed: RED, canceled: GREY, canceling: GREY, completed: GREY };
const LEG_LABEL: Record<string, string> = { queued: 'dialing', ringing: 'ringing', answered: 'answered', connected: 'on your phone', abandoned: 'abandoned', voicemail: 'voicemail', no_answer: 'no answer', busy: 'busy', failed: 'failed', canceled: 'cancelled', canceling: 'cancelled', completed: 'ended' };

const LegRow = ({ l, colors }: { l: Leg; colors: any }) => (
  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 6 }} {...tid(`leg-${l.attempt_id}`)}>
    <View style={{ width: 8, height: 8, borderRadius: 4, backgroundColor: LEG_TONE[l.status] || GREY }} />
    <Text style={{ flex: 1, fontSize: 13.5, fontWeight: '700', color: colors.text }} numberOfLines={1}>{l.lead_name}<Text style={{ fontWeight: '500', color: colors.textSecondary }}>{l.state ? ` · ${l.state}` : ''}{l.local_time ? ` · ${l.local_time}` : ''}</Text></Text>
    <Text style={{ fontSize: 11.5, fontWeight: '800', color: LEG_TONE[l.status] || GREY }}>{(LEG_LABEL[l.status] || l.status).toUpperCase()}</Text>
  </View>
);

const useTicker = (from?: string | null) => {
  const [s, setS] = useState(0);
  useEffect(() => { if (!from) { setS(0); return; } const t = setInterval(() => setS(Math.max(0, Math.round((Date.now() - new Date(from).getTime()) / 1000))), 1000); return () => clearInterval(t); }, [from]);
  return s;
};

export default function DialerSession() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const { colors } = useThemeStore();
  const { showToast } = useToast();
  const [s, setS] = useState<SessionView | null>(null);
  const [busy, setBusy] = useState<'dial' | 'hangup' | 'end' | null>(null);
  const [dispo, setDispo] = useState(false);
  const [showScript, setShowScript] = useState(true);
  const autoOpened = useRef<string | null>(null);
  const talk = useTicker(s?.status === 'connected' ? s.current?.attempt.connected_at : null);

  const load = useCallback(async () => { try { const r = await api.get(`/dialer/sessions/${id}`); setS(r.data); } catch (e: any) { showToast(e?.response?.data?.detail || 'Lost the session', 'error'); } }, [id]);
  useEffect(() => { load(); const t = setInterval(load, 2000); return () => clearInterval(t); }, [load]);
  useEffect(() => {
    const a = s?.current?.attempt;
    if (s && s.status !== 'connected' && s.current?.needs_disposition && a && autoOpened.current !== a.id) { autoOpened.current = a.id; setDispo(true); }
  }, [s?.status, s?.current?.attempt.id, s?.current?.needs_disposition]);

  const dial = async () => {
    setBusy('dial');
    try { const r = await api.post(`/dialer/sessions/${id}/dial`); setS(r.data.session); if (!r.data.dialed) showToast(r.data.skipped_window ? `${r.data.skipped_window} leads are outside their calling window` : 'No leads left to call', 'info'); }
    catch (e: any) { showToast(e?.response?.data?.detail || 'Could not dial', 'error'); }
    finally { setBusy(null); }
  };
  const hangup = async () => { setBusy('hangup'); try { await api.post(`/dialer/sessions/${id}/hangup`); } catch (e: any) { showToast(e?.response?.data?.detail || 'Could not hang up', 'error'); } finally { setBusy(null); } };
  const end = () => showConfirm('End the session?', 'Your phone hangs up. Anything not marked goes back into the list.', async () => {
    setBusy('end'); try { const r = await api.post(`/dialer/sessions/${id}/end`); setS(r.data); } catch (e: any) { showToast(e?.response?.data?.detail || 'Could not end', 'error'); } finally { setBusy(null); }
  }, undefined, 'End session');

  if (!s) return <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}><ScreenHeader title="Dialer" testID="session-header" /><ActivityIndicator style={{ marginTop: 60 }} color={GOLD} /></SafeAreaView>;
  const card = { backgroundColor: colors.card, borderRadius: 16, padding: 14, borderWidth: 1, borderColor: colors.border } as const;
  const lead = s.current?.lead;
  const a = s.current?.attempt;
  const tone = s.status === 'connected' ? GREEN : s.status === 'dialing' ? AMBER : s.status === 'ended' ? GREY : GOLD;
  const lines = s.stats.lines_effective || s.campaign?.lines || 1;
  const canDial = s.status === 'idle' || s.status === 'wrapup';

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      <ScreenHeader title={s.campaign?.name || 'Dialer'} subtitle={`Caller ID ${s.caller_id} · ${s.campaign?.connect_mode === 'press1' ? 'press 1 to accept' : 'instant connect'}`} testID="session-header"
        onBack={() => router.replace('/dialer' as any)} right={s.status !== 'ended' ? <HeaderTextButton label="End" onPress={end} testID="session-end" color={RED} /> : undefined} />
      <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 60, gap: 12 }}>
        <View style={{ ...card, borderColor: `${tone}66`, flexDirection: 'row', alignItems: 'center', gap: 12 }} {...tid('session-status')}>
          {s.status === 'starting' || s.status === 'dialing' ? <ActivityIndicator color={tone} /> : <Ionicons name={s.status === 'connected' ? 'call' : s.status === 'ended' ? 'checkmark-done' : 'radio-button-on'} size={22} color={tone} />}
          <View style={{ flex: 1 }}>
            <Text style={{ fontSize: 15.5, fontWeight: '800', color: colors.text }} {...tid('session-line')}>{s.status === 'connected' && lead ? `On the call with ${lead.name}` : s.line}</Text>
            {!!s.message && s.status !== 'connected' && <Text style={{ fontSize: 12.5, color: colors.textSecondary, marginTop: 2 }} {...tid('session-message')}>{s.message}</Text>}
            {s.status === 'connected' && <Text style={{ fontSize: 12.5, color: colors.textSecondary, marginTop: 2 }} {...tid('session-talk')}>{fmtDur(talk)}{a?.voicemail_detected ? ' · voicemail detected' : ''}{s.burst?.record ? ' · recording' : ''}</Text>}
            {s.status === 'ended' && <Text style={{ fontSize: 12.5, color: colors.textSecondary, marginTop: 2 }}>{s.end_reason === 'rep_no_answer' ? 'You did not pick up.' : s.end_reason === 'idle_timeout' ? 'Ended after 30 quiet minutes.' : `Started ${fmtWhen(s.started_at)}`}</Text>}
          </View>
        </View>

        {s.status === 'starting' && <Text style={{ fontSize: 13, color: colors.textSecondary, lineHeight: 18 }} {...tid('session-starting-hint')}>Pick up the call on {s.rep_phone}. You stay on that one call for the whole session; every press of 1 (or Dial next here) rings the next {lines === 1 ? 'lead' : `${lines} leads`}.</Text>}

        {(s.status === 'connected' || s.status === 'wrapup') && lead && (
          <View style={{ ...card, gap: 6 }} {...tid('session-lead-card')}>
            <Text style={{ fontSize: 22, fontWeight: '800', color: colors.text }}>{lead.name}</Text>
            {!!(lead.title || lead.company) && <Text style={{ fontSize: 14, color: colors.text }}>{[lead.title, lead.company].filter(Boolean).join(' · ')}</Text>}
            <Text style={{ fontSize: 13, color: colors.textSecondary }}>{lead.phone}{lead.city || lead.state ? ` · ${[lead.city, lead.state].filter(Boolean).join(', ')}` : ''}{lead.local_time ? ` · ${lead.local_time} there` : ''} · try {lead.attempts}</Text>
            {!!lead.notes && <Text style={{ fontSize: 13, color: colors.text, lineHeight: 18, marginTop: 4 }}>{lead.notes}</Text>}
            {!!lead.email && <Text style={{ fontSize: 12.5, color: BLUE }}>{lead.email}</Text>}
            {lead.ghl_contact_id && <Text style={{ fontSize: 11.5, color: colors.textSecondary }}>From GoHighLevel · outcome syncs back</Text>}
            {s.status === 'connected' && (
              <TouchableOpacity onPress={hangup} disabled={busy === 'hangup'} style={{ marginTop: 8, height: 48, borderRadius: 14, backgroundColor: RED, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 8 }} {...tid('session-hangup')}>
                <Ionicons name="call" size={18} color="#fff" style={{ transform: [{ rotate: '135deg' }] }} /><Text style={{ fontSize: 15, fontWeight: '800', color: '#fff' }}>{a?.voicemail_detected ? 'Hang up (voicemail)' : 'Hang up'}</Text>
              </TouchableOpacity>
            )}
            {s.status === 'wrapup' && s.current?.needs_disposition && <TouchableOpacity onPress={() => setDispo(true)} style={{ marginTop: 8, height: 48, borderRadius: 14, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center' }} {...tid('session-mark-outcome')}><Text style={{ fontSize: 15, fontWeight: '800', color: '#111' }}>Mark the outcome</Text></TouchableOpacity>}
          </View>
        )}

        {s.status === 'dialing' && s.burst && (
          <View style={card} {...tid('session-burst')}>
            <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.8, marginBottom: 4 }}>RINGING {s.burst.legs.length} {s.burst.legs.length === 1 ? 'LEAD' : 'LEADS'}</Text>
            {s.burst.legs.map(l => <LegRow key={l.attempt_id} l={l} colors={colors} />)}
            <Text style={{ fontSize: 11.5, color: colors.textSecondary, marginTop: 6 }}>The first live answer is on your phone; the others stop ringing.</Text>
          </View>
        )}

        {s.status !== 'ended' && canDial && (
          <TouchableOpacity onPress={dial} disabled={busy === 'dial' || (s.campaign?.status !== 'active')} style={{ height: 64, borderRadius: 18, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 10, opacity: busy === 'dial' ? 0.7 : 1 }} {...tid('session-dial')}>
            <Ionicons name="call" size={22} color="#111" />
            <View><Text style={{ fontSize: 17, fontWeight: '800', color: '#111' }}>{busy === 'dial' ? 'Dialing…' : `Dial next${lines > 1 ? ` · ${lines} lines` : ''}`}</Text><Text style={{ fontSize: 11.5, color: '#111111AA' }}>or press 1 on your phone</Text></View>
          </TouchableOpacity>
        )}
        {s.queue && s.status !== 'ended' && (
          <Text style={{ fontSize: 12.5, color: colors.textSecondary, textAlign: 'center' }} {...tid('session-queue')}>{s.queue.ready} ready · {s.queue.waiting_window} waiting on hours{s.stats.throttled ? ' · throttled to 1 line (abandon rate)' : ''}</Text>
        )}

        {!!s.campaign?.script && s.status !== 'ended' && (
          <View style={card}>
            <TouchableOpacity onPress={() => setShowScript(v => !v)} style={{ flexDirection: 'row', alignItems: 'center' }} {...tid('session-script-toggle')}>
              <Text style={{ flex: 1, fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.8 }}>SCRIPT</Text><Ionicons name={showScript ? 'chevron-up' : 'chevron-down'} size={14} color={colors.textSecondary} />
            </TouchableOpacity>
            {showScript && <Text style={{ fontSize: 14, color: colors.text, lineHeight: 21, marginTop: 6 }} {...tid('session-script')}>{lead ? s.campaign.script.replace(/\{first name\}|\{first_name\}/gi, lead.first_name || lead.name).replace(/\{company\}/gi, lead.company || '') : s.campaign.script}</Text>}
          </View>
        )}

        <View style={{ ...card, flexDirection: 'row', flexWrap: 'wrap', gap: 14 }} {...tid('session-stats')}>
          {[['Dials', s.stats.dials], ['Connects', s.stats.connects], ['Voicemails', s.stats.voicemails], ['Abandoned', s.stats.abandoned], ['Marked', s.stats.dispositions]].map(([k, v]) => (
            <View key={k as string}><Text style={{ fontSize: 18, fontWeight: '800', color: k === 'Abandoned' && (v as number) > 0 ? RED : colors.text }}>{v as number}</Text><Text style={{ fontSize: 10.5, color: colors.textSecondary }}>{(k as string).toUpperCase()}</Text></View>
          ))}
          <View><Text style={{ fontSize: 18, fontWeight: '800', color: (s.stats.abandon_rate || 0) >= 0.025 ? RED : colors.text }}>{pct(s.stats.abandon_rate)}</Text><Text style={{ fontSize: 10.5, color: colors.textSecondary }}>30D ABANDON</Text></View>
        </View>
        {s.status === 'ended' && <TouchableOpacity onPress={() => router.replace('/dialer' as any)} style={{ height: 46, borderRadius: 14, borderWidth: 1, borderColor: GOLD, alignItems: 'center', justifyContent: 'center' }} {...tid('session-back')}><Text style={{ fontSize: 14.5, fontWeight: '800', color: GOLD }}>Back to campaigns</Text></TouchableOpacity>}
      </ScrollView>
      <DispositionSheet visible={dispo} onClose={() => setDispo(false)} colors={colors} sessionId={s.id} attempt={a || null} lead={lead || null} dispositions={s.dispositions} onDone={load} />
    </SafeAreaView>
  );
}
