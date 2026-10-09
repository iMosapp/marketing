import React, { useCallback, useEffect, useRef, useState } from 'react';
import { View, Text, TouchableOpacity, ActivityIndicator, Platform, useWindowDimensions } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import api from '../../../services/api';
import { showConfirm } from '../../../services/alert';
import { useThemeStore } from '../../../store/themeStore';
import { useToast } from '../../../components/common/Toast';
import VoiceTextInput from '../../../components/VoiceTextInput';
import { useLiveJessiLauncher } from '../../../components/jessi/LiveJessiProvider';
import { liveSupported } from '../../../hooks/useLiveJessi';
import { CcShell, Empty } from '../../../components/command-center/CcShell';
import { MessageBubble, StarterChips, ThreadRow, FactsLine, suggestionTitle, suggestionBody } from '../../../components/command-center/AdvisorChat';
import { GOLD, detail, bounceIfPrivate, tid, type Conversation, type Suggestion } from '../../../components/command-center/shared';

// FOUNDER ADVISOR: a strategic operating partner that reads the live Command Center and only ever proposes; you confirm every change.
export default function FounderAdvisor() {
  const { colors } = useThemeStore();
  const { showToast } = useToast();
  const router = useRouter();
  const live = useLiveJessiLauncher();
  const { width } = useWindowDimensions();
  const wide = width >= 1024;
  const [threads, setThreads] = useState<Conversation[] | null>(null);
  const [convo, setConvo] = useState<Conversation | null>(null);
  const [starters, setStarters] = useState<string[]>([]);
  const [facts, setFacts] = useState<string[]>([]);
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const [showThreads, setShowThreads] = useState(false);
  const pending = useRef('');

  const loadThreads = useCallback(async () => {
    try {
      const [a, b] = await Promise.all([api.get('/command-center/advisor/conversations'), api.get('/command-center/advisor/suggestions')]);
      setThreads(a.data.conversations); setStarters(b.data.questions); setFacts(b.data.facts);
      return a.data.conversations as Conversation[];
    } catch (e: any) { if (bounceIfPrivate(e, router)) return []; showToast(detail(e, 'Could not load'), 'error'); return []; }
  }, []);
  const openThread = async (id: string) => { setShowThreads(false); try { setConvo((await api.get(`/command-center/advisor/conversations/${id}`)).data); } catch (e: any) { showToast(detail(e, 'Could not open'), 'error'); } };
  useEffect(() => { loadThreads().then(list => { if (list?.length) openThread(list[0].id); else setConvo(null); }); }, [loadThreads]);

  const newThread = async () => { const c = (await api.post('/command-center/advisor/conversations', {})).data; setConvo(c); setShowThreads(false); loadThreads(); return c as Conversation; };
  const send = async (q?: string) => {
    const t = (q || text).trim();
    if (!t || busy) return;
    setBusy(true); pending.current = t; setText('');
    try {
      const c = convo || await newThread();
      const r = (await api.post(`/command-center/advisor/conversations/${c.id}/messages`, { text: t }, { timeout: 90000 })).data;
      setConvo(r.conversation); loadThreads();
    } catch (e: any) { setText(t); showToast(detail(e, 'The advisor could not answer'), 'error', 6000); }
    finally { setBusy(false); pending.current = ''; }
  };
  const apply = (s: Suggestion) => showConfirm(suggestionTitle(s), `${suggestionBody(s)}\n\nThis changes the Command Center now.`, async () => {
    try {
      if (s.kind === 'set_next_action') await api.put('/command-center/next-action', { text: s.text, why: s.why || 'Advisor recommendation, confirmed by the founder' });
      else await api.patch(`/command-center/ideas/${s.idea_id}`, { status: s.kind === 'park_idea' ? 'parked' : 'evaluating' });
      showToast('Applied');
    } catch (e: any) { showToast(detail(e, 'Could not apply'), 'error'); }
  }, undefined, 'Confirm');
  const talk = () => {
    if (!liveSupported()) { showToast('Live voice needs the iPhone build or a desktop browser with a microphone.', 'error', 5000); return; }
    live.open({ options: { mode: 'advisor', overrides: { conversation_id: convo?.id } }, title: 'Founder Advisor', hint: 'Talk it through. Every turn lands in this conversation.', onClose: () => { loadThreads().then(list => { if (list?.length) openThread(convo?.id || list[0].id); }); } });
  };
  const archive = () => convo && showConfirm('Archive this conversation?', 'It leaves the list but stays on record.', async () => { await api.patch(`/command-center/advisor/conversations/${convo.id}`, { archived: true }); const list = await loadThreads(); if (list?.length) openThread(list[0].id); else setConvo(null); }, undefined, 'Archive');

  const Threads = (
    <View style={{ gap: 8, width: wide ? 280 : undefined }} {...tid('cc-threads')}>
      <TouchableOpacity onPress={newThread} style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, height: 40, borderRadius: 20, backgroundColor: GOLD }} {...tid('cc-thread-new')}>
        <Ionicons name="add" size={18} color="#1C1C1E" /><Text style={{ fontSize: 13.5, fontWeight: '800', color: '#1C1C1E' }}>New conversation</Text>
      </TouchableOpacity>
      {(threads || []).map(c => <ThreadRow key={c.id} c={c} active={c.id === convo?.id} colors={colors} onPress={() => openThread(c.id)} />)}
      {threads && !threads.length && <Empty t="No conversations yet. Ask the first question." colors={colors} testID="cc-threads-empty" />}
    </View>
  );
  const Chat = (
    <View style={{ flex: 1, gap: 14 }} {...tid('cc-chat')}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
        {!wide && <TouchableOpacity onPress={() => setShowThreads(v => !v)} style={{ flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 10, height: 32, borderRadius: 16, borderWidth: 1, borderColor: colors.border }} {...tid('cc-threads-toggle')}><Ionicons name="list" size={14} color={colors.textSecondary} /><Text style={{ fontSize: 12.5, fontWeight: '700', color: colors.textSecondary }}>{threads?.length || 0}</Text></TouchableOpacity>}
        <Text style={{ flex: 1, fontSize: 15, fontWeight: '800', color: colors.text }} numberOfLines={1} {...tid('cc-thread-title')}>{convo?.title || 'New conversation'}</Text>
        <TouchableOpacity onPress={talk} style={{ flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 12, height: 34, borderRadius: 17, backgroundColor: GOLD }} {...tid('cc-advisor-talk')}><Ionicons name="mic" size={15} color="#1C1C1E" /><Text style={{ fontSize: 12.5, fontWeight: '800', color: '#1C1C1E' }}>Talk live</Text></TouchableOpacity>
        {!!convo?.message_count && <TouchableOpacity onPress={archive} style={{ padding: 6 }} {...tid('cc-thread-archive')}><Ionicons name="archive-outline" size={18} color={colors.textSecondary} /></TouchableOpacity>}
      </View>
      {!wide && showThreads && Threads}
      {!convo?.messages?.length && !busy && <StarterChips questions={starters} colors={colors} onPick={send} />}
      <View style={{ gap: 14 }}>
        {(convo?.messages || []).map((m, i) => <MessageBubble key={i} m={m} colors={colors} onApply={apply} />)}
        {busy && (
          <View style={{ gap: 10 }}>
            <View style={{ alignSelf: 'flex-end', maxWidth: '92%', borderRadius: 16, borderTopRightRadius: 4, padding: 12, backgroundColor: GOLD }}><Text style={{ fontSize: 15, lineHeight: 22, color: '#1C1C1E' }}>{pending.current}</Text></View>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }} {...tid('cc-advisor-thinking')}><ActivityIndicator color={GOLD} size="small" /><Text style={{ fontSize: 12.5, color: colors.textSecondary }}>Reading the Command Center and thinking. Usually 5 to 30 seconds.</Text></View>
          </View>
        )}
      </View>
      {!!convo?.messages?.length && <FactsLine facts={(convo.messages[convo.messages.length - 1] as any).facts_used || facts} colors={colors} />}
    </View>
  );
  const Composer = (
    <View style={{ position: 'absolute', left: 0, right: 0, bottom: 0, padding: 12, paddingBottom: Platform.OS === 'web' ? 12 : 24, backgroundColor: colors.bg, borderTopWidth: 1, borderTopColor: colors.border, alignItems: 'center' }} {...tid('cc-composer')}>
      <View style={{ flexDirection: 'row', alignItems: 'flex-end', gap: 8, width: wide ? 1100 : '100%' }}>
        <View style={{ flex: 1 }}><VoiceTextInput value={text} onChangeText={setText} placeholder="Ask your advisor, or tap the mic" showVoice voiceAppend multiline onSubmitEditing={() => send()} blurOnSubmit testID="cc-advisor-input" /></View>
        <TouchableOpacity onPress={() => send()} disabled={!text.trim() || busy} style={{ width: 44, height: 44, borderRadius: 22, backgroundColor: text.trim() && !busy ? GOLD : colors.border, alignItems: 'center', justifyContent: 'center' }} {...tid('cc-advisor-send')}>
          <Ionicons name="arrow-up" size={20} color={text.trim() && !busy ? '#1C1C1E' : colors.textSecondary} />
        </TouchableOpacity>
      </View>
    </View>
  );
  return (
    <CcShell title="Founder Advisor" subtitle={facts.length ? facts.slice(0, 2).join(' · ') : undefined} loading={threads === null} footer={Composer}>
      {wide ? <View style={{ flexDirection: 'row', gap: 20 }}>{Threads}{Chat}</View> : Chat}
    </CcShell>
  );
}
