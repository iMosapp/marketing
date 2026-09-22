/**
 * Jessi Onboarding dashboard: every user Jessi is walking in by text, where each one sits in the funnel, whose move it is.
 * Tap a row for the thread, timeline and actions.
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { View, Text, ScrollView, TouchableOpacity, ActivityIndicator, RefreshControl } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useThemeStore } from '../../../store/themeStore';
import { useAuthStore } from '../../../store/authStore';
import { ScreenHeader, HeaderIconButton } from '../../../components/common/ScreenHeader';
import api from '../../../services/api';
import { Card } from '../../../components/ui/Row';
import { EmptyState } from '../../../components/ui/EmptyState';
import { GOLD, SPACE, TYPE, tid, tint } from '../../../components/ui/tokens';
import { FUNNEL, OnbRow, WAITING, prettyPhone } from '../../../components/onboarding-jessi/shared';
import { FunnelStrip, OnboardingRow } from '../../../components/onboarding-jessi/OnboardingRow';

const FILTERS: { key: string; label: string }[] = [{ key: 'all', label: 'All' }, { key: 'them', label: 'Waiting on them' }, { key: 'jessi', label: "Jessi's move" }, { key: 'paused', label: 'Paused' }, { key: 'done', label: 'Done' }];

export default function JessiOnboardingList() {
  const { colors } = useThemeStore();
  const user = useAuthStore(s => s.user);
  const router = useRouter();
  const [data, setData] = useState<{ rows: OnbRow[]; counts: Record<string, number>; sender: { name: string; number: string } | null } | null>(null);
  const [cfg, setCfg] = useState<{ available: boolean; default_on: boolean } | null>(null);
  const [error, setError] = useState('');
  const [refreshing, setRefreshing] = useState(false);
  const [filter, setFilter] = useState('all');
  const [bucket, setBucket] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [l, c] = await Promise.all([api.get('/admin/onboarding-jessi'), api.get('/admin/onboarding-jessi/config')]);
      setData(l.data); setCfg(c.data); setError('');
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Could not load onboarding');
    }
  }, []);
  useEffect(() => { load(); const t = setInterval(load, 20000); return () => clearInterval(t); }, [load]);

  const rows = useMemo(() => {
    let r = data?.rows || [];
    if (bucket) { const st = FUNNEL.find(b => b.key === bucket)?.states || []; r = r.filter(x => st.includes(x.state)); }
    if (filter !== 'all') r = r.filter(x => x.waiting_on === filter);
    return r;
  }, [data, filter, bucket]);
  const openCount = (data?.rows || []).filter(r => r.waiting_on !== 'done').length;

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']} {...tid('jessi-onb-page')}>
      <ScreenHeader title="Jessi Onboarding" subtitle={data ? `${openCount} in progress` : undefined}
        right={<HeaderIconButton icon="person-add-outline" onPress={() => router.push('/admin/users' as any)} testID="jessi-onb-add" />} />
      {!data && !error ? <ActivityIndicator color={GOLD} style={{ marginTop: 40 }} /> : error ? (
        <Text style={{ color: colors.textSecondary, padding: SPACE.xl, textAlign: 'center' }} {...tid('jessi-onb-error')}>{error}</Text>
      ) : (
        <ScrollView contentContainerStyle={{ paddingTop: SPACE.lg, paddingBottom: 60 }} refreshControl={<RefreshControl refreshing={refreshing} onRefresh={async () => { setRefreshing(true); await load(); setRefreshing(false); }} tintColor={GOLD} />}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginHorizontal: SPACE.lg, marginBottom: SPACE.lg, padding: SPACE.md, borderRadius: 14, backgroundColor: tint(GOLD, 0.1), borderWidth: 1, borderColor: tint(GOLD, 0.35) }} {...tid('jessi-onb-sender')}>
            <Ionicons name="chatbubbles" size={18} color={GOLD} />
            <Text style={{ flex: 1, fontSize: TYPE.sub, color: colors.text }}>
              {data?.sender ? <>Jessi texts from <Text style={{ fontWeight: '800' }}>{prettyPhone(data.sender.number)}</Text> ({data.sender.name}'s number)</> : 'No onboarding number yet: give the sender account a work number.'}
              {cfg && !cfg.available ? '  ·  Not switched on for your account yet (Test Lab).' : ''}
            </Text>
          </View>

          <FunnelStrip counts={data?.counts || {}} buckets={FUNNEL} active={bucket} onPick={setBucket} />

          <ScrollView horizontal showsVerticalScrollIndicator={false} showsHorizontalScrollIndicator={false} contentContainerStyle={{ paddingHorizontal: SPACE.lg, gap: 8, marginBottom: SPACE.lg }}>
            {FILTERS.map(f => {
              const on = filter === f.key;
              const n = f.key === 'all' ? (data?.rows || []).length : (data?.rows || []).filter(x => x.waiting_on === f.key).length;
              const color = f.key === 'all' ? GOLD : WAITING[f.key]?.color || GOLD;
              return (
                <TouchableOpacity key={f.key} onPress={() => setFilter(f.key)} style={{ flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 12, height: 32, borderRadius: 16, backgroundColor: on ? tint(color, 0.18) : colors.card, borderWidth: 1, borderColor: on ? color : colors.border }} {...tid(`jessi-onb-filter-${f.key}`)}>
                  <Text style={{ fontSize: 13, fontWeight: '700', color: on ? color : n ? colors.text : colors.textTertiary }}>{f.label}</Text>
                  {n > 0 && <Text style={{ fontSize: 12, fontWeight: '800', color: on ? color : colors.textSecondary }}>{n}</Text>}
                </TouchableOpacity>
              );
            })}
          </ScrollView>

          <View style={{ marginHorizontal: SPACE.lg }}>
            {rows.length === 0 ? (
              <EmptyState icon={(data?.rows || []).length ? 'filter-outline' : 'chatbubbles-outline'} iconColor={GOLD} title={(data?.rows || []).length ? 'Nobody here with that filter' : 'Nobody is being onboarded by Jessi yet'}
                subtitle={(data?.rows || []).length ? 'Pick another stage or filter.' : 'Add a team member with just a name and mobile, switch on "Let Jessi onboard them by text", and she takes it from there.'}
                actionLabel={(data?.rows || []).length ? undefined : 'Add a team member'} onAction={() => router.push('/admin/users' as any)} testID="jessi-onb-empty" />
            ) : (
              <Card testID="jessi-onb-list">
                {rows.map((r, i) => <OnboardingRow key={r.id} row={r} first={i === 0} onPress={() => router.push(`/admin/onboarding-jessi/${r.user_id}` as any)} />)}
              </Card>
            )}
          </View>
          {user?.role === 'super_admin' && (
            <Text style={{ fontSize: TYPE.caption, color: colors.textTertiary, textAlign: 'center', marginTop: SPACE.xl, paddingHorizontal: SPACE.xl }}>
              Nudges go out 24 h, 72 h and 7 days after a step stalls, never between 9 PM and 8 AM Mountain. Refreshes every 20 s.
            </Text>
          )}
        </ScrollView>
      )}
    </SafeAreaView>
  );
}
