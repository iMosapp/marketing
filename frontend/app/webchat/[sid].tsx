import React, { useCallback, useEffect, useRef, useState } from 'react';
import { View, Text, ScrollView, TextInput, TouchableOpacity, ActivityIndicator, KeyboardAvoidingView, Platform } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useLocalSearchParams } from 'expo-router';
import api from '../../services/api';
import { useAuthStore } from '../../store/authStore';
import { useThemeStore } from '../../store/themeStore';
import { useToast } from '../../components/common/Toast';
import { showConfirm } from '../../services/alert';
import { ScreenHeader } from '../../components/common/ScreenHeader';
import { GOLD, tid, errText } from '../../components/inbox/ownership';
import { inputStyle } from '../../components/inbox/InboxEditorParts';
import { ChatBubbles } from '../../components/webchat/ChatBubbles';
import { ChatStatusBar } from '../../components/webchat/ChatStatusBar';

const POLL_MS = 2500;

// A rep watching (or running) one live website chat. Typing a message is the same as "Jump in".
export default function WebChatScreen() {
  const { sid } = useLocalSearchParams<{ sid: string }>();
  const { user } = useAuthStore();
  const { colors } = useThemeStore();
  const { showToast } = useToast();
  const [chat, setChat] = useState<any>(null);
  const [text, setText] = useState('');
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const scroll = useRef<ScrollView>(null);
  const count = useRef(0);

  const load = useCallback(async () => {
    try { const d = (await api.get(`/widgets/chats/${sid}`)).data; setChat(d); setError(''); }
    catch (e: any) { setError(errText(e, 'Could not load this chat')); }
  }, [sid]);
  useEffect(() => { load(); const t = setInterval(load, POLL_MS); return () => clearInterval(t); }, [load]);
  useEffect(() => { const n = chat?.messages?.length || 0; if (n !== count.current) { count.current = n; setTimeout(() => scroll.current?.scrollToEnd({ animated: true }), 50); } }, [chat?.messages?.length]);

  const act = async (what: string, call: () => Promise<any>) => {
    setBusy(what);
    try { const d = await call(); setChat((c: any) => ({ ...c, ...d.data })); }
    catch (e: any) { showToast(errText(e), 'error', 3000); }
    finally { setBusy(''); }
  };
  const send = async () => {
    const t = text.trim();
    if (!t) return;
    setText('');
    await act('send', () => api.post(`/widgets/chats/${sid}/message`, { text: t }));
  };
  const end = () => showConfirm('End this chat?', 'The visitor sees "Chat ended" and can start a fresh one with Jessi.', () => act('end', () => api.post(`/widgets/chats/${sid}/end`)), undefined, 'End chat');

  if (!chat) return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      <ScreenHeader title="Web chat" testID="webchat-header" />
      {error ? <Text style={{ margin: 24, textAlign: 'center', color: colors.textSecondary }} {...tid('webchat-error')}>{error}</Text> : <ActivityIndicator style={{ marginTop: 60 }} color={GOLD} />}
    </SafeAreaView>
  );
  const closed = chat.status === 'closed';
  const mine = chat.mode === 'human' && String(chat.rep_user_id) === String(user?._id);
  const where = chat.host ? `${chat.host}${chat.title ? ` · ${chat.title}` : ''}` : 'website';
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      <ScreenHeader title={chat.name || 'Website visitor'} subtitle={`${where}${closed ? '' : chat.visitor_here ? ' · on the page now' : ' · left the page'}`} testID="webchat-header" />
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <ChatStatusBar chat={chat} meId={String(user?._id || '')} colors={colors} busy={busy}
          onJoin={() => act('join', () => api.post(`/widgets/chats/${sid}/join`))}
          onLeave={() => act('leave', () => api.post(`/widgets/chats/${sid}/leave`))}
          onEnd={end}
          onSaveLead={(name, phone) => act('lead', () => api.post(`/widgets/chats/${sid}/lead`, { name, phone }))} />
        <ScrollView ref={scroll} style={{ flex: 1 }} contentContainerStyle={{ paddingBottom: 12 }} onContentSizeChange={() => scroll.current?.scrollToEnd({ animated: false })}>
          <ChatBubbles messages={chat.messages || []} colors={colors} meId={String(user?._id || '')} />
          {!closed && !chat.visitor_here ? <Text style={{ textAlign: 'center', fontSize: 12, color: colors.textSecondary, paddingHorizontal: 20 }} {...tid('webchat-visitor-away')}>The visitor closed the page. If you have their number, the Text thread is the way to reach them.</Text> : null}
        </ScrollView>
        {!closed ? (
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, padding: 10, borderTopWidth: 1, borderTopColor: colors.border, backgroundColor: colors.card }}>
            <TextInput value={text} onChangeText={setText} placeholder={mine ? 'Message the visitor' : 'Type to jump in and reply yourself'} placeholderTextColor={colors.textSecondary}
              onSubmitEditing={send} blurOnSubmit={false} style={[inputStyle(colors), { flex: 1 }]} {...tid('webchat-input')} />
            <TouchableOpacity onPress={send} disabled={!text.trim() || busy === 'send'} style={{ width: 46, height: 46, borderRadius: 23, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center', opacity: !text.trim() || busy === 'send' ? 0.5 : 1 }} {...tid('webchat-send')}>
              {busy === 'send' ? <ActivityIndicator color="#111" /> : <Ionicons name="arrow-up" size={22} color="#111" />}
            </TouchableOpacity>
          </View>
        ) : null}
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
