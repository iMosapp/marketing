import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, ScrollView } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import { useThemeStore } from '../../store/themeStore';
import api, { messagesAPI } from '../../services/api';
import { fmtWait } from '../inbox/LeadsQueuePanel';
import { noteLeadQueueCount } from '../../utils/leadChime';
import { GOLD, RED, RADIUS, SPACE, TYPE, tid, tint } from '../ui/tokens';

const AMBER = '#FF9500';
type Chip = { key: string; icon: string; color: string; label: string; onPress: () => void };

/** One strip for everything waiting on the rep: leads, replies, hot threads, failed AI sends. Hidden when nothing needs you. */
export function NeedsYouStrip({ userId, hot }: { userId: string; hot: number }) {
  const router = useRouter();
  const { colors } = useThemeStore();
  const [leads, setLeads] = useState<any>(null);
  const [replies, setReplies] = useState(0);
  const [health, setHealth] = useState<any>(null);
  const [fetchedAt, setFetchedAt] = useState(Date.now());
  const [now, setNow] = useState(Date.now());

  const load = useCallback(() => {
    if (!userId) return;
    api.get(`/leads/queue/${userId}/summary`).then(r => { setLeads(r.data); setFetchedAt(Date.now()); noteLeadQueueCount(r.data?.waiting); }).catch(() => {});
    messagesAPI.getConversations(userId).then((all: any[]) => {
      const open = (all || []).filter(c => c.status !== 'closed' && c.status !== 'archived');
      setReplies(open.filter(c => c.needs_assistance || c.status === 'paused' || c.unread).length);
    }).catch(() => {});
    api.get(`/home/reply-health/${userId}`).then(r => setHealth(r.data)).catch(() => {});
  }, [userId]);

  useFocusEffect(useCallback(() => {
    load();
    const t = setInterval(load, 30000);
    return () => clearInterval(t);
  }, [load]));
  useEffect(() => { const t = setInterval(() => setNow(Date.now()), 15000); return () => clearInterval(t); }, []);

  const queue: number = leads?.waiting || 0;
  const mine: number = leads?.mine_waiting || 0;
  const leadCount = queue + mine;
  const failed: number = health?.failed || 0;
  const total = leadCount + replies + hot + failed;
  if (total === 0) return null;

  const drift = Math.floor((now - fetchedAt) / 1000);
  const oldest = Math.max(leads?.oldest?.waiting_seconds ?? 0, leads?.mine_oldest?.waiting_seconds ?? 0) + drift;
  const chips: Chip[] = [];
  if (leadCount > 0) chips.push({
    key: 'leads', icon: 'flame', color: RED,
    label: `${leadCount} lead${leadCount === 1 ? '' : 's'} waiting · ${fmtWait(oldest)}`,
    onPress: () => queue > 0
      ? router.push({ pathname: '/(tabs)/inbox', params: { segment: 'leads', t: String(Date.now()) } } as any)
      : router.push(`/thread/${leads.mine_oldest.conversation_id}` as any),
  });
  if (hot > 0) chips.push({ key: 'hot', icon: 'trending-up', color: RED, label: `${hot} hot`, onPress: () => router.push('/(tabs)/inbox?tab=hot' as any) });
  if (replies > 0) chips.push({ key: 'replies', icon: 'chatbubble-ellipses', color: GOLD, label: `${replies} need${replies === 1 ? 's' : ''} a reply`, onPress: () => router.push('/(tabs)/inbox?tab=needs_you' as any) });
  if (failed > 0) chips.push({
    key: 'failed', icon: 'warning', color: AMBER, label: `${failed} AI repl${failed === 1 ? 'y' : 'ies'} didn't send`,
    onPress: () => router.push((health.conversation_id ? `/thread/${health.conversation_id}` : '/(tabs)/inbox') as any),
  });
  const urgent = leadCount + hot + failed > 0;
  const accent = urgent ? RED : GOLD;

  return (
    <View style={{ marginHorizontal: SPACE.lg, marginBottom: SPACE.md, borderRadius: RADIUS.lg, backgroundColor: tint(accent, 0.08), borderWidth: 1, borderColor: tint(accent, 0.35), paddingVertical: SPACE.md }} {...tid('needs-you-strip')}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: SPACE.lg, marginBottom: SPACE.sm }}>
        <Ionicons name="alert-circle" size={14} color={accent} />
        <Text style={{ fontSize: TYPE.caption, fontWeight: '800', color: accent, letterSpacing: 0.8 }} {...tid('needs-you-title')}>NEEDS YOU · {total}</Text>
        <View style={{ flex: 1 }} />
        <TouchableOpacity onPress={() => router.push('/(tabs)/inbox?tab=needs_you' as any)} hitSlop={8} {...tid('needs-you-open-inbox')}>
          <Text style={{ fontSize: TYPE.caption, fontWeight: '700', color: colors.textSecondary }}>Open Inbox →</Text>
        </TouchableOpacity>
      </View>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ paddingHorizontal: SPACE.lg, gap: SPACE.sm }}>
        {chips.map(c => (
          <TouchableOpacity key={c.key} onPress={c.onPress} activeOpacity={0.8}
            style={{ flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 12, height: 34, borderRadius: 17, backgroundColor: tint(c.color, 0.16), borderWidth: 1, borderColor: tint(c.color, 0.45) }}
            {...tid(`needs-you-${c.key}`)}>
            <Ionicons name={c.icon as any} size={14} color={c.color} />
            <Text style={{ fontSize: TYPE.sub, fontWeight: '700', color: c.color }} numberOfLines={1}>{c.label}</Text>
          </TouchableOpacity>
        ))}
      </ScrollView>
    </View>
  );
}
