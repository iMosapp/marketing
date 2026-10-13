import React, { useCallback, useEffect, useRef, useState } from 'react';
import { View, Text, ScrollView, ActivityIndicator, RefreshControl } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import api from '../../services/api';
import { useThemeStore } from '../../store/themeStore';
import { useAuthStore } from '../../store/authStore';
import { ScreenHeader } from '../../components/common/ScreenHeader';
import { RED, tid, PilotStatus } from '../../components/voice-pilot/shared';
import { PilotStatusCard } from '../../components/voice-pilot/PilotStatusCard';
import { PilotEnrollCard } from '../../components/voice-pilot/PilotEnrollCard';
import { PilotUsageCard } from '../../components/voice-pilot/PilotUsageCard';
import { PilotKillCard } from '../../components/voice-pilot/PilotKillCard';
import { PilotSessionsCard } from '../../components/voice-pilot/PilotSessionsCard';

const POLL_MS = 5000;

// Founder-facing Voice Pilot: enrol my own account in the voice spending controls, watch usage and spend, kill switch. Super admin only.
export default function VoicePilot() {
  const router = useRouter();
  const { colors } = useThemeStore();
  const me = useAuthStore(st => st.user);
  const [s, setS] = useState<PilotStatus | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const timer = useRef<any>(null);

  const load = useCallback(async () => {
    try { const r = await api.get('/voice-controls/pilot'); setS(r.data); setError(''); }
    catch (e: any) { setError(e?.response?.data?.detail || 'Could not load the pilot status'); }
  }, []);
  useEffect(() => {
    if (me && me.role !== 'super_admin') { router.replace('/(tabs)/more' as any); return; }
    load();
    timer.current = setInterval(load, POLL_MS);
    return () => { if (timer.current) clearInterval(timer.current); };
  }, [load, me, router]);

  const act = async (fn: () => Promise<any>) => {
    setBusy(true); setError('');
    try { const r = await fn(); if (r?.data?.org_id) setS(r.data); else await load(); }
    catch (e: any) { setError(e?.response?.data?.detail || 'That did not work'); }
    finally { setBusy(false); }
  };
  const enroll = (premium_min: number, backup_min: number, hard_usd: number) => act(() => api.post('/voice-controls/pilot/enroll', { premium_min, backup_min, hard_usd }));
  const kill = () => act(() => api.post('/voice-controls/pilot/kill'));
  const resume = () => act(() => api.post('/voice-controls/pilot/resume'));
  const leave = () => act(() => api.post('/voice-controls/pilot/leave'));

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']} {...tid('voice-pilot-screen')}>
      <ScreenHeader title="Voice Pilot" subtitle="Your account only" onBack={() => router.back()} testID="voice-pilot-header" />
      <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 60 }} refreshControl={<RefreshControl refreshing={refreshing} onRefresh={async () => { setRefreshing(true); await load(); setRefreshing(false); }} tintColor={colors.textSecondary} />}>
        {!!error && <Text style={{ color: RED, fontSize: 13, marginBottom: 12 }} {...tid('voice-pilot-error')}>{error}</Text>}
        {!s && !error && <View style={{ paddingVertical: 40, alignItems: 'center' }}><ActivityIndicator color={colors.textSecondary} /></View>}
        {s && (
          <>
            <PilotStatusCard s={s} />
            <PilotEnrollCard s={s} busy={busy} onEnroll={enroll} onLeave={leave} />
            {s.enrolled && <PilotKillCard s={s} busy={busy} onKill={kill} onResume={resume} />}
            <PilotUsageCard s={s} />
            <PilotSessionsCard s={s} />
          </>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}
