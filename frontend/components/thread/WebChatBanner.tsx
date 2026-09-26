import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import api from '../../services/api';
import { GOLD, tid } from '../inbox/ownership';

// Inbox thread of a web-chat lead: while the visitor still has the chat window open, offer to jump in there instead of texting.
export const WebChatBanner = ({ conversationId, colors }: { conversationId?: string | null; colors: any }) => {
  const router = useRouter();
  const [chat, setChat] = useState<any>(null);
  const load = useCallback(async () => {
    if (!conversationId) return;
    try { setChat((await api.get(`/widgets/chats/by-conversation/${conversationId}`)).data.chat); } catch {}
  }, [conversationId]);
  useEffect(() => { load(); const t = setInterval(load, 15000); return () => clearInterval(t); }, [load]);
  if (!chat) return null;
  const who = chat.mode === 'human' ? `${chat.agent || 'A teammate'} is in the chat` : 'Jessi is answering';
  return (
    <TouchableOpacity onPress={() => router.push(`/webchat/${chat.sid}` as any)} activeOpacity={0.8}
      style={{ flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: '#34C75914', borderTopWidth: 1, borderTopColor: '#34C75935', paddingHorizontal: 16, paddingVertical: 10 }} {...tid('webchat-thread-banner')}>
      <Ionicons name="chatbubbles" size={16} color="#34C759" />
      <View style={{ flex: 1 }}>
        <Text style={{ fontSize: 13, fontWeight: '700', color: colors.text }}>{chat.visitor_here ? 'Still on your website right now' : 'Was on your website a moment ago'}</Text>
        <Text style={{ fontSize: 12, color: colors.textSecondary }} numberOfLines={1}>{who}{chat.last ? ` · "${chat.last}"` : ''}</Text>
      </View>
      <View style={{ backgroundColor: GOLD, borderRadius: 8, paddingHorizontal: 12, paddingVertical: 6 }}><Text style={{ fontSize: 12, fontWeight: '800', color: '#111' }}>Jump in</Text></View>
    </TouchableOpacity>
  );
};
