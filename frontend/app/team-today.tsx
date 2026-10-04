// Team Today: a manager's morning digest. Every rep on the store and who each of them should be working today, with one-tap nudges.
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { View, Text, TouchableOpacity, ScrollView, ActivityIndicator, RefreshControl, Platform } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useThemeStore } from '../store/themeStore';
import { Avatar } from '../components/Avatar';
import { ScreenHeader } from '../components/common/ScreenHeader';
import { useToast } from '../components/common/Toast';
import { showAlert } from '../services/alert';
import { liveSupported, LIVE_UNSUPPORTED_TITLE, LIVE_UNSUPPORTED_BODY } from '../hooks/useLiveJessi';
import { useLiveJessiLauncher } from '../components/jessi/LiveJessiProvider';
import { useLiveConfig } from '../components/jessi/useLiveConfig';
import api from '../services/api';

const GOLD = '#C9A962';
const tid = (id: string) => ({ testID: id, dataSet: { testid: id } as any });
const KIND: Record<string, { icon: any; color: string; label: string }> = {
  reply: { icon: 'chatbubble-ellipses', color: '#FF453A', label: 'Waiting on a reply' },
  task: { icon: 'alarm', color: '#FF9F0A', label: 'Overdue' },
  my3: { icon: 'star', color: GOLD, label: 'One of their 3' },
  hot: { icon: 'flame', color: '#FF6B35', label: 'Hot' },
};

type Stop = { contact_id: string | null; name: string; first: string; kind: string; label: string; why: string };
type Rep = { user_id: string; name: string; first: string; role: string; photo?: string | null; total: number; counts: Record<string, number>; stops: Stop[] };
type Digest = { reps: Rep[]; rep_count: number; total: number; waiting: number; spoken: string };

export default function TeamTodayScreen() {
  const { colors } = useThemeStore();
  const router = useRouter();
  const { rep: repParam } = useLocalSearchParams<{ rep?: string }>();
  const { showToast } = useToast();
  const { config } = useLiveConfig();
  const jessi = useLiveJessiLauncher();
  const [data, setData] = useState<Digest | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [err, setErr] = useState('');
  const [open, setOpen] = useState<Record<string, boolean>>({});
  const [nudging, setNudging] = useState<string | null>(null);

  const load = useCallback(async (soft = false) => {
    soft ? setRefreshing(true) : setLoading(true);
    setErr('');
    try {
      const r = await api.get('/team-today', { timeout: 45000 });
      setData(r.data);
      if (typeof repParam === 'string' && repParam) {
        const hit = (r.data.reps as Rep[]).find(x => x.first.toLowerCase() === repParam.toLowerCase() || x.name.toLowerCase() === repParam.toLowerCase());
        if (hit) setOpen({ [hit.user_id]: true });
      }
    } catch (e: any) {
      setErr(e?.response?.status === 403 ? 'Team Today is for store managers.' : (e?.response?.data?.detail || 'Could not load your team right now.'));
    } finally { setLoading(false); setRefreshing(false); }
  }, [repParam]);
  useEffect(() => { load(); }, [load]);

  const nudge = async (rep: Rep, s: Stop) => {
    if (!s.contact_id) return;
    const key = `${rep.user_id}:${s.contact_id}`;
    setNudging(key);
    try {
      await api.post('/team-today/nudge', { rep_user_id: rep.user_id, contact_id: s.contact_id, note: s.why });
      showToast(`${rep.first} has ${s.name} at the top of their list, with a push.`, 'success');
    } catch (e: any) {
      showToast(e?.response?.data?.detail || 'Could not send that nudge.', 'error');
    } finally { setNudging(null); }
  };

  const hear = () => {
    if (!liveSupported()) {
      showAlert(LIVE_UNSUPPORTED_TITLE, `${LIVE_UNSUPPORTED_BODY} Opening the typed Ask Jessi instead.`, [{ text: 'OK', onPress: () => router.push('/ask-team' as any) }]);
      return;
    }
    jessi.open({ options: { mode: 'assistant', overrides: { team_today: true } }, title: 'Your team with Jessi', hint: 'Jessi reads the team digest. Say a rep\'s name for their full list, or "tell Bud to call Sarah" to nudge.' });
  };

  const busy = useMemo(() => (data?.reps || []).filter(r => r.total), [data]);
  const idle = useMemo(() => (data?.reps || []).filter(r => !r.total), [data]);
  const canHear = !!config?.available && !!config?.configured;

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']} {...tid('team-today-screen')}>
      <ScreenHeader title="Team Today" subtitle="Who each rep should be working right now" testID="team-today-header"
        right={canHear ? (
          <TouchableOpacity onPress={hear} style={{ flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: `${GOLD}22`, borderWidth: 1, borderColor: `${GOLD}66`, borderRadius: 16, paddingHorizontal: 10, paddingVertical: 6 }} {...tid('team-today-hear-btn')}>
            <Ionicons name="mic" size={14} color={GOLD} /><Text style={{ fontSize: 12, fontWeight: '800', color: GOLD }}>{jessi.active ? 'Jessi is on' : 'Hear it'}</Text>
          </TouchableOpacity>
        ) : undefined} />
      {loading ? <ActivityIndicator color={GOLD} style={{ marginTop: 40 }} /> : err ? (
        <Text style={{ margin: 20, color: '#FF453A', fontSize: 14 }} {...tid('team-today-error')}>{err}</Text>
      ) : (
        <ScrollView contentContainerStyle={{ padding: 14, paddingBottom: 60, gap: 12 }} refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => load(true)} tintColor={GOLD} />}>
          <View style={{ flexDirection: 'row', gap: 10 }} {...tid('team-today-summary')}>
            {[{ n: data?.total || 0, l: 'follow-ups' }, { n: busy.length, l: `of ${data?.rep_count || 0} reps busy` }, { n: data?.waiting || 0, l: 'waiting on reply' }].map((m, i) => (
              <View key={i} style={{ flex: 1, backgroundColor: colors.card, borderRadius: 14, borderWidth: 1, borderColor: colors.border, padding: 12 }}>
                <Text style={{ fontSize: 22, fontWeight: '800', color: i === 2 && m.n ? '#FF453A' : GOLD }}>{m.n}</Text>
                <Text style={{ fontSize: 11.5, color: colors.textSecondary, fontWeight: '600' }}>{m.l}</Text>
              </View>
            ))}
          </View>
          {!data?.reps.length && <Text style={{ color: colors.textSecondary, fontSize: 14, lineHeight: 20 }} {...tid('team-today-empty')}>No salespeople are assigned to your store yet. Add them under Team Members and Jessi will walk you through their day every morning.</Text>}
          {busy.map(rep => {
            const expanded = open[rep.user_id] ?? busy.length <= 3;
            const shown = expanded ? rep.stops : rep.stops.slice(0, 2);
            return (
              <View key={rep.user_id} style={{ backgroundColor: colors.card, borderRadius: 16, borderWidth: 1, borderColor: rep.counts.reply ? '#FF453A66' : colors.border, padding: 14, gap: 10 }} {...tid(`team-today-rep-${rep.user_id}`)}>
                <TouchableOpacity onPress={() => setOpen(o => ({ ...o, [rep.user_id]: !expanded }))} style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }} {...tid(`team-today-rep-toggle-${rep.user_id}`)}>
                  <Avatar photo={rep.photo || undefined} name={rep.name} sizePx={38} />
                  <View style={{ flex: 1 }}>
                    <Text style={{ fontSize: 15.5, fontWeight: '800', color: colors.text }}>{rep.name}</Text>
                    <Text style={{ fontSize: 12, color: colors.textSecondary }}>
                      {rep.total} to work{rep.counts.reply ? ` · ${rep.counts.reply} waiting on a reply` : ''}{rep.counts.task ? ` · ${rep.counts.task} overdue` : ''}
                    </Text>
                  </View>
                  <Ionicons name={expanded ? 'chevron-up' : 'chevron-down'} size={18} color={colors.textTertiary} />
                </TouchableOpacity>
                {shown.map((s, i) => {
                  const k = KIND[s.kind] || { icon: 'ellipse', color: colors.textSecondary, label: s.label };
                  const key = `${rep.user_id}:${s.contact_id}`;
                  return (
                    <View key={`${s.contact_id || i}`} style={{ flexDirection: 'row', alignItems: 'flex-start', gap: 10, borderTopWidth: 1, borderTopColor: colors.border, paddingTop: 10 }} {...tid(`team-today-stop-${rep.user_id}-${s.contact_id}`)}>
                      <Ionicons name={k.icon} size={16} color={k.color} style={{ marginTop: 2 }} />
                      <TouchableOpacity style={{ flex: 1 }} onPress={() => s.contact_id && router.push(`/contact/${s.contact_id}` as any)} {...tid(`team-today-open-${s.contact_id}`)}>
                        <Text style={{ fontSize: 14, fontWeight: '700', color: colors.text }}>{s.name} <Text style={{ fontSize: 11, fontWeight: '800', color: k.color }}>· {k.label}</Text></Text>
                        <Text style={{ fontSize: 12.5, color: colors.textSecondary, lineHeight: 17 }}>{s.why}</Text>
                      </TouchableOpacity>
                      {!!s.contact_id && (
                        <TouchableOpacity onPress={() => nudge(rep, s)} disabled={nudging === key} style={{ flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: `${GOLD}22`, borderRadius: 12, paddingHorizontal: 10, paddingVertical: 6, opacity: nudging === key ? 0.5 : 1 }} {...tid(`team-today-nudge-${rep.user_id}-${s.contact_id}`)}>
                          <Ionicons name="notifications" size={12} color={GOLD} /><Text style={{ fontSize: 11.5, fontWeight: '800', color: GOLD }}>Nudge {rep.first}</Text>
                        </TouchableOpacity>
                      )}
                    </View>
                  );
                })}
                {!expanded && rep.stops.length > 2 && <Text style={{ fontSize: 12, fontWeight: '700', color: GOLD }}>{rep.stops.length - 2} more…</Text>}
              </View>
            );
          })}
          {!!idle.length && (
            <View style={{ backgroundColor: colors.card, borderRadius: 16, borderWidth: 1, borderColor: colors.border, padding: 14, gap: 6 }} {...tid('team-today-idle')}>
              <Text style={{ fontSize: 12, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.5 }}>CAUGHT UP</Text>
              <Text style={{ fontSize: 13.5, color: colors.text, lineHeight: 19 }}>{idle.map(r => r.first).join(', ')}</Text>
            </View>
          )}
        </ScrollView>
      )}
    </SafeAreaView>
  );
}
