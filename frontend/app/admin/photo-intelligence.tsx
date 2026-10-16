import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, ScrollView, ActivityIndicator, RefreshControl, Alert, Platform } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import api from '../../services/api';
import { useThemeStore } from '../../store/themeStore';
import { useAuthStore } from '../../store/authStore';
import { ScreenHeader } from '../../components/common/ScreenHeader';
import { RED, tid } from '../../components/voice-pilot/shared';
import { PhotoSettings, Scope, Usage, Segmented } from '../../components/photo-intel/shared';
import { ControlsCard } from '../../components/photo-intel/ControlsCard';
import { TotalsCard, TrendCard, BreakdownCard } from '../../components/photo-intel/UsageCards';

const RANGES = [{ key: '1', label: '24 hours' }, { key: '7', label: '7 days' }, { key: '30', label: '30 days' }, { key: '90', label: '90 days' }];

const confirm = (msg: string) => new Promise<boolean>(res => {
  if (Platform.OS === 'web') return res(window.confirm(msg));
  Alert.alert('Are you sure?', msg, [{ text: 'Cancel', style: 'cancel', onPress: () => res(false) }, { text: 'Yes', onPress: () => res(true) }]);
});

// Photo Intelligence: Jessi Photo Replies / Automatic Photo Intelligence rollout, emergency pause, usage and estimated cost. Super admin only.
export default function PhotoIntelligence() {
  const router = useRouter();
  const { colors } = useThemeStore();
  const me = useAuthStore(st => st.user);
  const [s, setS] = useState<PhotoSettings | null>(null);
  const [u, setU] = useState<Usage | null>(null);
  const [days, setDays] = useState('30');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async (d = days) => {
    try {
      const [a, b] = await Promise.all([api.get('/jessi-vision/settings'), api.get(`/jessi-vision/usage?days=${d}`)]);
      setS(a.data); setU(b.data); setError('');
    } catch (e: any) { setError(e?.response?.data?.detail || 'Could not load Photo Intelligence'); }
  }, [days]);
  useEffect(() => {
    if (me && me.role !== 'super_admin') { router.replace('/(tabs)/more' as any); return; }
    load();
  }, [load, me, router]);

  const act = async (fn: () => Promise<any>) => {
    setBusy(true); setError('');
    try { const r = await fn(); setS(r.data); } catch (e: any) { setError(e?.response?.data?.detail || 'That did not work'); } finally { setBusy(false); }
  };
  const onScope = async (cap: 'replies' | 'intelligence', v: Scope) => {
    if (v === 'all' && !(await confirm(`Turn ${cap === 'replies' ? 'Jessi Photo Replies' : 'Automatic Photo Intelligence'} on for EVERY organization?`))) return;
    act(() => api.put('/jessi-vision/settings', { [cap]: v }));
  };
  const onPause = async (v: boolean) => {
    if (v && !(await confirm('Pause all photo analysis now? Photos keep arriving and are saved, but none are read.'))) return;
    act(() => api.put('/jessi-vision/settings', { paused: v }));
  };
  const pickRange = (d: string) => { setDays(d); setU(null); load(d); };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']} {...tid('photo-intel-screen')}>
      <ScreenHeader title="Photo Intelligence" subtitle="Jessi reads customer photos" onBack={() => router.back()} testID="photo-intel-header" />
      <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 60, maxWidth: 820, width: '100%', alignSelf: 'center' }}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={async () => { setRefreshing(true); await load(); setRefreshing(false); }} tintColor={colors.textSecondary} />}>
        {!!error && <Text style={{ color: RED, fontSize: 13, marginBottom: 12 }} {...tid('photo-intel-error')}>{error}</Text>}
        {!s && !error && <View style={{ paddingVertical: 40, alignItems: 'center' }}><ActivityIndicator color={colors.textSecondary} /></View>}
        {s && <ControlsCard s={s} busy={busy} onScope={onScope} onPause={onPause}
          onAddMine={() => act(() => api.post('/jessi-vision/test-orgs/mine'))} onRemove={id => act(() => api.delete(`/jessi-vision/test-orgs/${id}`))} />}
        {s && (
          <View style={{ marginBottom: 14 }}>
            <Segmented value={days} options={RANGES} onChange={pickRange} testID="photo-intel-range" />
          </View>
        )}
        {s && !u && !error && <View style={{ paddingVertical: 30, alignItems: 'center' }}><ActivityIndicator color={colors.textSecondary} /></View>}
        {u && <TotalsCard u={u} />}
        {u && <TrendCard u={u} />}
        {u && <BreakdownCard u={u} />}
      </ScrollView>
    </SafeAreaView>
  );
}
