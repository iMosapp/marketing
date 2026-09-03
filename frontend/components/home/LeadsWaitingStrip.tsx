/**
 * LeadsWaitingStrip — Home strip covering BOTH the shared internet-lead queue and my own unanswered leads.
 * Queue leads → Inbox > Leads segment; only-mine → straight into the oldest thread. Refreshes on focus + 30s.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import api from '../../services/api';
import { fmtWait } from '../inbox/LeadsQueuePanel';
import { noteLeadQueueCount } from '../../utils/leadChime';

const HEAT: Record<string, string> = { green: '#34C759', amber: '#FF9F0A', red: '#FF3B30' };
const tid = (id: string) => ({ testID: id, dataSet: { testid: id } as any });

export function LeadsWaitingStrip({ userId }: { userId: string }) {
  const router = useRouter();
  const [data, setData] = useState<any>(null);
  const [fetchedAt, setFetchedAt] = useState(Date.now());
  const [now, setNow] = useState(Date.now());

  useFocusEffect(
    useCallback(() => {
      if (!userId) return;
      let alive = true;
      const load = () =>
        api.get(`/leads/queue/${userId}/summary`).then(r => { if (alive) { setData(r.data); setFetchedAt(Date.now()); noteLeadQueueCount(r.data?.waiting); } }).catch(() => {});
      load();
      const t = setInterval(load, 30000);
      return () => { alive = false; clearInterval(t); };
    }, [userId])
  );
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 15000);
    return () => clearInterval(t);
  }, []);

  if (!data) return null;
  const queue: number = data.waiting || 0;
  const mine: number = data.mine_waiting || 0;
  if (queue + mine === 0) return null;

  const drift = Math.floor((now - fetchedAt) / 1000);
  const oldestSecs = Math.max(data.oldest?.waiting_seconds ?? 0, data.mine_oldest?.waiting_seconds ?? 0) + drift;
  const color = HEAT[data.heat || 'green'];
  const names: string[] = [...(data.names || []), ...(data.mine_names || [])].slice(0, 3);

  let title: string;
  let sub: string;
  let cta: string;
  if (queue > 0) {
    title = `${queue + mine} lead${queue + mine === 1 ? '' : 's'} waiting · oldest ${fmtWait(oldestSecs)}`;
    sub = mine > 0 ? `${queue} unclaimed · ${mine} yours need${mine === 1 ? 's' : ''} a reply` : names.join(', ');
    cta = 'Claim';
  } else {
    title = mine === 1
      ? `${data.mine_oldest?.contact_name || 'Your lead'} is waiting ${fmtWait(oldestSecs)}`
      : `${mine} of your leads need a reply · oldest ${fmtWait(oldestSecs)}`;
    sub = mine === 1 ? 'Your lead · Tap to reply' : names.join(', ');
    cta = 'Reply';
  }

  const onPress = () => {
    if (queue > 0) router.push({ pathname: '/(tabs)/inbox', params: { segment: 'leads', t: String(Date.now()) } } as any);
    else router.push(`/thread/${data.mine_oldest.conversation_id}` as any);
  };

  return (
    <TouchableOpacity
      onPress={onPress}
      activeOpacity={0.8}
      style={{
        flexDirection: 'row', alignItems: 'center', gap: 10,
        marginHorizontal: 16, marginBottom: 12,
        paddingHorizontal: 14, paddingVertical: 12,
        borderRadius: 16, backgroundColor: `${color}16`,
        borderWidth: 1.5, borderColor: `${color}55`,
      }}
      {...tid('leads-waiting-strip')}
    >
      <View style={{ width: 38, height: 38, borderRadius: 19, backgroundColor: `${color}25`, alignItems: 'center', justifyContent: 'center' }}>
        <Ionicons name="flame" size={19} color={color} />
      </View>
      <View style={{ flex: 1 }}>
        <Text style={{ fontSize: 15, fontWeight: '800', color }} numberOfLines={1} {...tid('leads-waiting-title')}>{title}</Text>
        <Text style={{ fontSize: 12, color: '#8E8E93', marginTop: 1 }} numberOfLines={1} {...tid('leads-waiting-sub')}>{sub}</Text>
      </View>
      <View style={{ backgroundColor: color, borderRadius: 18, paddingHorizontal: 12, paddingVertical: 7 }}>
        <Text style={{ fontSize: 12, fontWeight: '800', color: '#FFF' }}>{cta}</Text>
      </View>
    </TouchableOpacity>
  );
}
