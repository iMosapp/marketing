/**
 * One user's Jessi onboarding: stage + whose move, actions (Resend, Message, Call, Pause, Mark step, Reset),
 * the SMS thread, the write-up + transcript, the step timeline and the event log.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, ScrollView, TouchableOpacity, ActivityIndicator, TextInput, Modal, Image, Linking } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useThemeStore } from '../../../store/themeStore';
import { ScreenHeader, HeaderIconButton } from '../../../components/common/ScreenHeader';
import api from '../../../services/api';
import { showConfirm, showSimpleAlert } from '../../../services/alert';
import { Card } from '../../../components/ui/Row';
import { Section } from '../../../components/ui/Section';
import { PrimaryButton } from '../../../components/ui/PrimaryButton';
import { GOLD, RED, SPACE, TYPE, tid, tint } from '../../../components/ui/tokens';
import { resolvePhotoUrl } from '../../../utils/photoUrl';
import { OnbRow, STAGE_LABEL, WaitingPill, initials, prettyPhone, when } from '../../../components/onboarding-jessi/shared';
import { EventLog, SmsThread, StepTimeline, WriteUpCard } from '../../../components/onboarding-jessi/DetailParts';

export default function JessiOnboardingDetail() {
  const { userId } = useLocalSearchParams<{ userId: string }>();
  const { colors } = useThemeStore();
  const router = useRouter();
  const [d, setD] = useState<OnbRow | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState('');
  const [msg, setMsg] = useState('');
  const [markOpen, setMarkOpen] = useState(false);

  const load = useCallback(async () => {
    try { const r = await api.get(`/admin/onboarding-jessi/${userId}`); setD(r.data); setError(''); }
    catch (e: any) { setError(e?.response?.data?.detail || 'Could not load'); }
  }, [userId]);
  useEffect(() => { load(); const t = setInterval(load, 10000); return () => clearInterval(t); }, [load]);

  const act = async (key: string, path: string, body?: any, ok?: string) => {
    setBusy(key);
    try { const r = await api.post(`/admin/onboarding-jessi/${userId}/${path}`, body || {}); if (r.data?.state || r.data?.ok !== undefined) setD(prev => (r.data?.state ? r.data : prev)); if (ok) showSimpleAlert(ok); await load(); }
    catch (e: any) { showSimpleAlert('Could not do that', e?.response?.data?.detail || 'Try again in a minute'); }
    finally { setBusy(''); }
  };
  const send = async () => {
    const t = msg.trim();
    if (!t) return;
    setMsg('');
    await act('message', 'message', { text: t });
  };

  if (error) return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}><ScreenHeader title="Jessi Onboarding" /><Text style={{ color: colors.textSecondary, padding: SPACE.xl, textAlign: 'center' }} {...tid('jessi-onb-detail-error')}>{error}</Text></SafeAreaView>
  );
  if (!d) return <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}><ScreenHeader title="Jessi Onboarding" /><ActivityIndicator color={GOLD} style={{ marginTop: 40 }} /></SafeAreaView>;

  const u = d.user || {};
  const photo = resolvePhotoUrl(u.photo_url || d.photo_url || null);
  const canCall = d.state_index <= (d.states.indexOf('INTERVIEW_STARTED'));
  const later = d.states.filter((_, i) => i > d.state_index && i <= d.states.indexOf('ACCOUNT_ACTIVATED'));

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']} {...tid('jessi-onb-detail')}>
      <ScreenHeader title={d.name || d.first_name} subtitle={prettyPhone(d.phone)}
        right={<HeaderIconButton icon="person-outline" onPress={() => router.push(`/admin/users/${userId}` as any)} testID="jessi-onb-open-user" />} />
      <ScrollView contentContainerStyle={{ paddingTop: SPACE.lg, paddingBottom: 80 }} keyboardShouldPersistTaps="handled">
        <View style={{ marginHorizontal: SPACE.lg, marginBottom: SPACE.xl }}>
          <Card testID="jessi-onb-stage">
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: SPACE.md, padding: SPACE.lg }}>
              {photo ? <Image source={{ uri: photo }} style={{ width: 56, height: 56, borderRadius: 28 }} {...tid('jessi-onb-photo')} /> : (
                <View style={{ width: 56, height: 56, borderRadius: 28, backgroundColor: tint(GOLD, 0.16), alignItems: 'center', justifyContent: 'center' }}><Text style={{ fontSize: 18, fontWeight: '800', color: GOLD }}>{initials(d.name)}</Text></View>
              )}
              <View style={{ flex: 1 }}>
                <Text style={{ fontSize: TYPE.section, fontWeight: '800', color: colors.text }} {...tid('jessi-onb-stage-label')}>{STAGE_LABEL[d.state] || d.state}</Text>
                <Text style={{ fontSize: TYPE.sub, color: colors.textSecondary, marginTop: 2 }} {...tid('jessi-onb-next')}>Next: {d.next}</Text>
                <Text style={{ fontSize: TYPE.caption, color: colors.textTertiary, marginTop: 2 }}>{u.email || d.facts?.email || 'No email yet'}{u.title ? ` · ${u.title}` : ''}</Text>
              </View>
              <WaitingPill who={d.waiting_on} testID="jessi-onb-waiting" />
            </View>
            <View style={{ height: 4, marginHorizontal: SPACE.lg, marginBottom: SPACE.lg, borderRadius: 2, backgroundColor: tint(colors.text, 0.08), overflow: 'hidden' }}>
              <View style={{ width: `${Math.max(4, (d.state_index / (d.states.length - 1)) * 100)}%`, height: 4, backgroundColor: GOLD }} />
            </View>
            <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8, paddingHorizontal: SPACE.lg, paddingBottom: SPACE.lg }}>
              <PrimaryButton size="sm" variant="soft" icon="refresh" label="Resend" loading={busy === 'resend'} onPress={() => act('resend', 'resend', undefined, 'Sent again')} testID="jessi-onb-action-resend" />
              {canCall && <PrimaryButton size="sm" variant="soft" icon="call" label="Call now" loading={busy === 'call'} onPress={() => showConfirm('Ring them now?', `Jessi calls ${prettyPhone(d.phone)} for the setup interview.`, () => act('call', 'call', undefined, 'Jessi is calling them'))} testID="jessi-onb-action-call" />}
              <PrimaryButton size="sm" variant="soft" icon={d.paused ? 'play' : 'pause'} color={d.paused ? GOLD : RED} label={d.paused ? 'Resume' : 'Pause'} loading={busy === 'pause'} onPress={() => act('pause', d.paused ? 'pause?resume=true' : 'pause')} testID="jessi-onb-action-pause" />
              {later.length > 0 && <PrimaryButton size="sm" variant="outline" icon="checkmark-done" label="Mark step" onPress={() => setMarkOpen(true)} testID="jessi-onb-action-mark" />}
              <PrimaryButton size="sm" variant="outline" color={RED} icon="trash" label="Reset" loading={busy === 'reset'} onPress={() => showConfirm('Start over?', 'Wipes every step and Jessi texts the intro again.', () => act('reset', 'reset'), undefined, 'Reset')} testID="jessi-onb-action-reset" />
            </View>
            {!!d.activation_url && (
              <TouchableOpacity onPress={() => Linking.openURL(d.activation_url!)} style={{ flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: SPACE.lg, paddingBottom: SPACE.lg }} {...tid('jessi-onb-activation-link')}>
                <Ionicons name="link" size={14} color={GOLD} /><Text style={{ fontSize: TYPE.caption, color: GOLD, fontWeight: '700' }} numberOfLines={1}>{d.activation_url}</Text>
              </TouchableOpacity>
            )}
          </Card>
        </View>

        <Section title="Texts" subtitle={`From ${prettyPhone(d.from_number)}${d.reminders?.count ? ` · ${d.reminders.count} nudge${d.reminders.count > 1 ? 's' : ''} sent` : ''}`} testID="jessi-onb-texts">
          <Card>
            <SmsThread thread={d.thread || []} />
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, padding: SPACE.md, borderTopWidth: 0.5, borderTopColor: colors.border }}>
              <TextInput value={msg} onChangeText={setMsg} placeholder="Text them as Jessi…" placeholderTextColor={colors.textTertiary} multiline
                style={{ flex: 1, minHeight: 40, maxHeight: 120, paddingHorizontal: 12, paddingVertical: 9, borderRadius: 14, backgroundColor: colors.surface, color: colors.text, fontSize: TYPE.body }} {...tid('jessi-onb-msg-input')} />
              <TouchableOpacity onPress={send} disabled={!msg.trim() || busy === 'message'} style={{ width: 40, height: 40, borderRadius: 20, backgroundColor: msg.trim() ? GOLD : colors.surface, alignItems: 'center', justifyContent: 'center' }} {...tid('jessi-onb-msg-send')}>
                {busy === 'message' ? <ActivityIndicator size="small" color="#000" /> : <Ionicons name="arrow-up" size={20} color={msg.trim() ? '#000' : colors.textTertiary} />}
              </TouchableOpacity>
            </View>
          </Card>
        </Section>

        <Section title="What Jessi learned" testID="jessi-onb-learned">
          <Card><WriteUpCard summary={d.summary_text} confirmed={d.summary_confirmed} interview={d.interview} awaitingEmail={d.awaiting_email} /></Card>
        </Section>

        <Section title="Steps" subtitle={`Started ${when(d.created_at)}`} testID="jessi-onb-steps">
          <Card><View style={{ padding: SPACE.lg }}><StepTimeline states={d.states} steps={d.steps} current={d.state} paused={d.paused} /></View><EventLog events={d.events || []} /></Card>
        </Section>
      </ScrollView>

      <Modal visible={markOpen} transparent animationType="fade" onRequestClose={() => setMarkOpen(false)}>
        <TouchableOpacity activeOpacity={1} onPress={() => setMarkOpen(false)} style={{ flex: 1, backgroundColor: 'rgba(0,0,0,0.6)', justifyContent: 'flex-end' }}>
          <View style={{ backgroundColor: colors.bg, borderTopLeftRadius: 22, borderTopRightRadius: 22, padding: SPACE.lg, paddingBottom: 36 }} {...tid('jessi-onb-mark-sheet')}>
            <Text style={{ fontSize: TYPE.section, fontWeight: '800', color: colors.text, marginBottom: 4 }}>Mark a step done</Text>
            <Text style={{ fontSize: TYPE.sub, color: colors.textSecondary, marginBottom: SPACE.md }}>Use this when something happened off-line. Jessi still sends whatever naturally follows.</Text>
            {later.map(s => (
              <TouchableOpacity key={s} onPress={() => { setMarkOpen(false); act('mark', `mark/${s}`); }} style={{ paddingVertical: 13, borderBottomWidth: 0.5, borderBottomColor: colors.border }} {...tid(`jessi-onb-mark-${s}`)}>
                <Text style={{ fontSize: TYPE.body, color: colors.text }}>{STAGE_LABEL[s]}</Text>
              </TouchableOpacity>
            ))}
          </View>
        </TouchableOpacity>
      </Modal>
    </SafeAreaView>
  );
}
