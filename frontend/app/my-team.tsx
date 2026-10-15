import React, { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, RefreshControl, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import api from '../services/api';
import { useThemeStore } from '../store/themeStore';
import { ScreenHeader } from '../components/common/ScreenHeader';
import { GOLD, GREEN, RADIUS, SPACE, TYPE, tid, tint } from '../components/ui/tokens';

const NUMBER_COLOR: Record<string, string> = { ready: GREEN, pending: '#FF9500', none: '#8E8E93' };
const ago = (iso?: string | null) => {
  if (!iso) return 'No activity yet';
  const d = Math.floor((Date.now() - new Date(iso).getTime()) / 86400000);
  return d <= 0 ? 'Active today' : d === 1 ? 'Active yesterday' : `Active ${d} days ago`;
};

function Stat({ label, value, colors, testID }: { label: string; value: number; colors: any; testID: string }) {
  return (
    <View style={{ flex: 1, alignItems: 'center' }} {...tid(testID)}>
      <Text style={{ fontSize: 18, fontWeight: '800', color: colors.text }}>{value}</Text>
      <Text style={{ fontSize: TYPE.caption, color: colors.textTertiary }}>{label}</Text>
    </View>
  );
}

function MemberRow({ m, colors }: { m: any; colors: any }) {
  const nc = NUMBER_COLOR[m.number?.status] || '#8E8E93';
  return (
    <View style={{ backgroundColor: colors.card, borderRadius: RADIUS.md, borderWidth: 1, borderColor: colors.border, padding: SPACE.md, gap: 10 }} {...tid(`my-team-member-${m.id}`)}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
        <View style={{ width: 38, height: 38, borderRadius: 19, alignItems: 'center', justifyContent: 'center', backgroundColor: tint(GOLD, 0.15) }}>
          <Text style={{ fontSize: 16, fontWeight: '800', color: GOLD }}>{(m.name || '?')[0]}</Text>
        </View>
        <View style={{ flex: 1 }}>
          <Text style={{ fontSize: TYPE.body, fontWeight: '700', color: colors.text }}>{m.name || 'Team member'}</Text>
          <Text style={{ fontSize: TYPE.caption, color: colors.textSecondary }}>{m.activated ? ago(m.last_activity) : 'Has not signed in yet'}</Text>
        </View>
        <Text style={{ fontSize: TYPE.caption, fontWeight: '800', color: colors.textSecondary }} {...tid(`my-team-setup-${m.id}`)}>Setup {m.setup?.done}/{m.setup?.total}</Text>
      </View>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
        <Ionicons name="chatbubble-ellipses-outline" size={14} color={nc} />
        <Text style={{ fontSize: TYPE.caption, fontWeight: '700', color: nc }} {...tid(`my-team-number-${m.id}`)}>{m.number?.label}{m.number?.last4 ? ` · ${m.number.last4}` : ''}</Text>
      </View>
      <View style={{ flexDirection: 'row', borderTopWidth: 1, borderTopColor: colors.border, paddingTop: 8 }}>
        <Stat label="contacts · 7d" value={m.week?.contacts || 0} colors={colors} testID={`my-team-contacts-${m.id}`} />
        <Stat label="cards shared" value={m.week?.cards_shared || 0} colors={colors} testID={`my-team-shares-${m.id}`} />
        <Stat label="texts sent" value={m.week?.texts_sent || 0} colors={colors} testID={`my-team-texts-${m.id}`} />
      </View>
    </View>
  );
}

/** My Team (owners and location managers): read-only setup, texting readiness and 7-day activity per team member. Scope is enforced by the server. */
export default function MyTeamScreen() {
  const { colors } = useThemeStore();
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState('');
  const [refreshing, setRefreshing] = useState(false);
  const load = useCallback(async () => {
    try { setData((await api.get('/team-view')).data); setError(''); }
    catch (e: any) { setError(e?.response?.data?.detail || 'Your team is not available right now.'); }
  }, []);
  useEffect(() => { load(); }, [load]);

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      <ScreenHeader title="My Team" subtitle={data ? `${data.count} team member${data.count === 1 ? '' : 's'} · ${data.scope === 'store' ? 'your location' : 'your organization'}` : 'Setup and activity'} testID="my-team-header" />
      <ScrollView contentContainerStyle={{ padding: SPACE.lg, gap: SPACE.md, maxWidth: 720, width: '100%', alignSelf: 'center' }}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={async () => { setRefreshing(true); await load(); setRefreshing(false); }} />}>
        {error ? <Text style={{ fontSize: TYPE.body, color: colors.textSecondary }} {...tid('my-team-error')}>{error}</Text> : null}
        {!data && !error ? <ActivityIndicator color={GOLD} /> : null}
        {data && data.members.length === 0 ? <Text style={{ fontSize: TYPE.body, color: colors.textSecondary }} {...tid('my-team-empty')}>No team members yet. Invite your team from More.</Text> : null}
        {data?.members.map((m: any) => <MemberRow key={m.id} m={m} colors={colors} />)}
        {data ? <Text style={{ fontSize: TYPE.caption, color: colors.textTertiary, lineHeight: 17 }}>Counts only. Message content is never shown here.</Text> : null}
      </ScrollView>
    </SafeAreaView>
  );
}
