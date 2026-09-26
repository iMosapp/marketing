import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, ScrollView } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import api from '../../services/api';
import { GOLD, tid, timeAgo } from './ownership';

const POLL_MS = 10000;

// Web chats happening right now on the store's website. Sits above the Inbox list; hidden when there are none.
export const LiveChatsStrip = ({ colors }: { colors: any }) => {
  const router = useRouter();
  const [chats, setChats] = useState<any[]>([]);
  const [me, setMe] = useState('');
  const load = useCallback(async () => {
    try { const d = (await api.get('/widgets/chats/live')).data; setChats(d.chats || []); setMe(d.me || ''); } catch {}
  }, []);
  useEffect(() => { load(); const t = setInterval(load, POLL_MS); return () => clearInterval(t); }, [load]);
  if (!chats.length) return null;
  return (
    <View style={{ paddingTop: 8, paddingBottom: 4 }} {...tid('live-chats-strip')}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 16, marginBottom: 6 }}>
        <View style={{ width: 8, height: 8, borderRadius: 4, backgroundColor: '#34C759' }} />
        <Text style={{ fontSize: 12, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.6 }}>LIVE ON YOUR WEBSITE · {chats.length}</Text>
      </View>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ paddingHorizontal: 12, gap: 8 }}>
        {chats.map(c => {
          const mine = c.mode === 'human' && String(c.rep_user_id) === me;
          const who = c.mode === 'human' ? (mine ? 'You' : c.agent || 'Teammate') : 'Jessi';
          return (
            <TouchableOpacity key={c.sid} onPress={() => router.push(`/webchat/${c.sid}` as any)} activeOpacity={0.8}
              style={{ width: 230, padding: 12, borderRadius: 14, backgroundColor: colors.surface, borderWidth: 1, borderColor: mine && c.rep_unread ? GOLD : colors.border, gap: 4 }} {...tid(`live-chat-${c.sid}`)}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                <Ionicons name={c.mode === 'human' ? 'person' : 'sparkles'} size={13} color={c.mode === 'human' ? GOLD : colors.textSecondary} />
                <Text style={{ flex: 1, fontSize: 13, fontWeight: '800', color: colors.text }} numberOfLines={1}>{c.name}{c.booked ? ' · booked' : ''}</Text>
                {c.rep_unread ? <View style={{ minWidth: 18, height: 18, borderRadius: 9, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 5 }}><Text style={{ fontSize: 11, fontWeight: '800', color: '#111' }}>{c.rep_unread}</Text></View> : null}
              </View>
              <Text style={{ fontSize: 12, color: colors.text }} numberOfLines={2}>{c.last ? `"${c.last}"` : 'Just opened the chat'}</Text>
              <Text style={{ fontSize: 11, color: colors.textSecondary }} numberOfLines={1}>{who} answering · {c.host || 'website'} · {c.visitor_here ? 'here now' : timeAgo(c.at)}</Text>
            </TouchableOpacity>
          );
        })}
      </ScrollView>
    </View>
  );
};
