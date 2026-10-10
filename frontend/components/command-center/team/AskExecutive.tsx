import React, { useCallback, useEffect, useRef, useState } from 'react';
import { View, Text, TouchableOpacity, ActivityIndicator, Platform, ScrollView } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import api from '../../../services/api';
import { showConfirm } from '../../../services/alert';
import { useToast } from '../../common/Toast';
import VoiceTextInput from '../../VoiceTextInput';
import { useLiveJessiLauncher } from '../../jessi/LiveJessiProvider';
import { liveSupported } from '../../../hooks/useLiveJessi';
import { Empty } from '../CcShell';
import { MessageBubble, StarterChips, ThreadRow, FactsLine, suggestionTitle, suggestionBody } from '../AdvisorChat';
import { Monogram } from './Roster';
import { GOLD, detail, bounceIfPrivate, tid, execColor, execShort, type Conversation, type Executive, type Suggestion } from '../shared';

type Args = { execs: Executive[]; colors: any; wide: boolean; initialKey?: string; initialThread?: string; onConvene: (question: string, threadId: string) => void };
const ADVISOR = 'strategic_advisor';

// ASK AN EXECUTIVE: one thread, one or more executives; the founder picks who answers each turn. Reuses the Advisor's threads, so Phase 2 history lives on.
export const useAsk = ({ execs, colors, wide, initialKey, initialThread, onConvene }: Args) => {
  const { showToast } = useToast();
  const router = useRouter();
  const live = useLiveJessiLauncher();
  const [threads, setThreads] = useState<Conversation[] | null>(null);
  const [convo, setConvo] = useState<Conversation | null>(null);
  const [key, setKey] = useState(initialKey || ADVISOR);
  const [starters, setStarters] = useState<string[]>([]);
  const [facts, setFacts] = useState<string[]>([]);
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const [showThreads, setShowThreads] = useState(false);
  const pending = useRef('');
  const talking = execs.filter(e => !e.is_orchestrator && e.enabled);
  const current = execs.find(e => e.key === key);

  const loadThreads = useCallback(async () => {
    try { const r = await api.get('/command-center/team/threads'); setThreads(r.data.threads); return r.data.threads as Conversation[]; }
    catch (e: any) { if (bounceIfPrivate(e, router)) return []; showToast(detail(e, 'Could not load'), 'error'); return []; }
  }, []);
  const openThread = async (id: string) => {
    setShowThreads(false);
    try { const c = (await api.get(`/command-center/team/threads/${id}`)).data; setConvo(c); setKey(c.agent_keys?.[0] || ADVISOR); } catch (e: any) { showToast(detail(e, 'Could not open'), 'error'); }
  };
  useEffect(() => { api.get(`/command-center/team/starters?agent_key=${key}`).then(r => { setStarters(r.data.questions); setFacts(r.data.facts); }).catch(() => {}); }, [key]);
  useEffect(() => { loadThreads().then(list => { if (initialThread) openThread(initialThread); else if (!initialKey && list?.length) openThread(list[0].id); }); }, [loadThreads]);
  useEffect(() => { if (initialKey) { setKey(initialKey); setConvo(null); } }, [initialKey]);

  const newThread = async (k = key) => { const c = (await api.post('/command-center/team/threads', { agent_key: k })).data; setConvo(c); setKey(k); setShowThreads(false); loadThreads(); return c as Conversation; };
  const send = async (q?: string) => {
    const t = (q || text).trim();
    if (!t || busy) return;
    setBusy(true); pending.current = t; setText('');
    try {
      const c = convo || await newThread();
      const r = (await api.post(`/command-center/team/threads/${c.id}/messages`, { text: t, agent_key: key }, { timeout: 120000 })).data;
      setConvo(r.conversation); loadThreads();
      if (r.budget?.warning) showToast(`Soft budget warning: $${r.budget.spent.toFixed(2)} of $${r.budget.soft.toFixed(2)} used this month`, 'warning', 5000);
    } catch (e: any) { setText(t); showToast(detail(e, `The ${current?.short || 'executive'} could not answer`), 'error', 6000); }
    finally { setBusy(false); pending.current = ''; }
  };
  const pick = async (k: string) => {
    if (convo && !(convo.agent_keys || [ADVISOR]).includes(k)) {
      try { setConvo((await api.post(`/command-center/team/threads/${convo.id}/participants`, { agent_key: k })).data); loadThreads(); showToast(`${execShort(execs, k)} joined this conversation`); } catch (e: any) { showToast(detail(e, 'Could not bring them in'), 'error'); return; }
    }
    setKey(k);
  };
  const apply = (s: Suggestion) => showConfirm(suggestionTitle(s), `${suggestionBody(s)}\n\nThis changes the Command Center now.`, async () => {
    try {
      if (s.kind === 'set_next_action') await api.put('/command-center/next-action', { text: s.text, why: s.why || 'Executive recommendation, confirmed by the founder' });
      else await api.patch(`/command-center/ideas/${s.idea_id}`, { status: s.kind === 'park_idea' ? 'parked' : 'evaluating' });
      showToast('Applied');
    } catch (e: any) { showToast(detail(e, 'Could not apply'), 'error'); }
  }, undefined, 'Confirm');
  const talk = (k = key) => {
    if (!liveSupported()) { showToast('Live voice needs the iPhone build or a desktop browser with a microphone.', 'error', 5000); return; }
    const e = execs.find(x => x.key === k);
    live.open({ options: { mode: 'advisor', overrides: { conversation_id: convo?.id, agent_key: k } }, title: e?.title || 'Strategic Advisor', hint: `Talk it through with the ${e?.short || 'Advisor'}. Every turn lands in this conversation.`, onClose: () => { loadThreads().then(list => { if (convo?.id) openThread(convo.id); else if (list?.length) openThread(list[0].id); }); } });
  };
  const archive = () => convo && showConfirm('Archive this conversation?', 'It leaves the list but stays on record.', async () => { await api.patch(`/command-center/team/threads/${convo.id}`, { archived: true }); const list = await loadThreads(); if (list?.length) openThread(list[0].id); else setConvo(null); }, undefined, 'Archive');
  const convene = () => {
    const founder = (convo?.messages || []).filter(m => m.role === 'founder');
    onConvene(founder.length ? founder[founder.length - 1].text : convo?.title || '', convo?.id || '');
  };
  const lastBring = [...(convo?.messages || [])].reverse().find(m => m.role !== 'founder')?.bring_in;

  const Threads = (
    <View style={{ gap: 8, width: wide ? 280 : undefined }} {...tid('cc-threads')}>
      <TouchableOpacity onPress={() => newThread()} style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, height: 40, borderRadius: 20, backgroundColor: GOLD }} {...tid('cc-thread-new')}>
        <Ionicons name="add" size={18} color="#1C1C1E" /><Text style={{ fontSize: 13.5, fontWeight: '800', color: '#1C1C1E' }}>New with the {current?.short || 'Advisor'}</Text>
      </TouchableOpacity>
      {(threads || []).map(c => <ThreadRow key={c.id} c={c} active={c.id === convo?.id} colors={colors} onPress={() => openThread(c.id)} />)}
      {threads && !threads.length && <Empty t="No conversations yet. Pick an executive and ask the first question." colors={colors} testID="cc-threads-empty" />}
    </View>
  );
  const Picker = (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ flexGrow: 0, height: 36 }} contentContainerStyle={{ gap: 8, alignItems: 'center' }} {...tid('cc-exec-picker')}>
      {talking.map(e => {
        const inThread = (convo?.agent_keys || []).includes(e.key);
        const active = e.key === key;
        return (
          <TouchableOpacity key={e.key} onPress={() => pick(e.key)} style={{ flexDirection: 'row', alignItems: 'center', gap: 6, paddingLeft: 4, paddingRight: 12, height: 36, borderRadius: 18, backgroundColor: active ? e.color + '26' : colors.card, borderWidth: 1.5, borderColor: active ? e.color : inThread ? e.color + '66' : colors.border }} {...tid(`cc-pick-${e.key}`)}>
            <Monogram e={e} size={28} /><Text style={{ fontSize: 12.5, fontWeight: '800', color: active ? e.color : colors.text }}>{e.short}</Text>
            {!inThread && !!convo && <Ionicons name="add" size={12} color={colors.textSecondary} />}
          </TouchableOpacity>
        );
      })}
    </ScrollView>
  );
  const Chat = (
    <View style={{ flex: 1, gap: 14 }} {...tid('cc-chat')}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
        {!wide && <TouchableOpacity onPress={() => setShowThreads(v => !v)} style={{ flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 10, height: 32, borderRadius: 16, borderWidth: 1, borderColor: colors.border }} {...tid('cc-threads-toggle')}><Ionicons name="list" size={14} color={colors.textSecondary} /><Text style={{ fontSize: 12.5, fontWeight: '700', color: colors.textSecondary }}>{threads?.length || 0}</Text></TouchableOpacity>}
        <Text style={{ flex: 1, fontSize: 15, fontWeight: '800', color: colors.text }} numberOfLines={1} {...tid('cc-thread-title')}>{convo?.title || `New conversation with the ${current?.short || 'Advisor'}`}</Text>
        <TouchableOpacity onPress={() => talk()} style={{ flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 12, height: 34, borderRadius: 17, backgroundColor: GOLD }} {...tid('cc-advisor-talk')}><Ionicons name="mic" size={15} color="#1C1C1E" /><Text style={{ fontSize: 12.5, fontWeight: '800', color: '#1C1C1E' }}>Talk live</Text></TouchableOpacity>
        {!!convo?.message_count && <TouchableOpacity onPress={convene} style={{ padding: 6 }} {...tid('cc-thread-convene')}><Ionicons name="people" size={19} color={GOLD} /></TouchableOpacity>}
        {!!convo?.message_count && <TouchableOpacity onPress={archive} style={{ padding: 6 }} {...tid('cc-thread-archive')}><Ionicons name="archive-outline" size={18} color={colors.textSecondary} /></TouchableOpacity>}
      </View>
      {Picker}
      {!wide && showThreads && Threads}
      {!convo?.messages?.length && !busy && <StarterChips questions={starters} colors={colors} onPick={send} />}
      <View style={{ gap: 14 }}>
        {(convo?.messages || []).map((m, i) => <MessageBubble key={i} m={m} colors={colors} onApply={apply} label={m.role === 'founder' ? undefined : execShort(execs, m.agent_key || ADVISOR)} color={execColor(execs, m.agent_key || ADVISOR)} />)}
        {!busy && lastBring?.agent_key && talking.some(e => e.key === lastBring.agent_key) && (
          <TouchableOpacity onPress={() => pick(lastBring.agent_key)} style={{ alignSelf: 'flex-start', flexDirection: 'row', alignItems: 'center', gap: 8, padding: 10, paddingRight: 14, borderRadius: 14, borderWidth: 1, borderColor: execColor(execs, lastBring.agent_key), backgroundColor: execColor(execs, lastBring.agent_key) + '14' }} {...tid('cc-bring-in')}>
            <Ionicons name="person-add" size={15} color={execColor(execs, lastBring.agent_key)} />
            <View><Text style={{ fontSize: 13, fontWeight: '800', color: colors.text }}>Bring in the {execShort(execs, lastBring.agent_key)}</Text><Text style={{ fontSize: 12, color: colors.textSecondary }}>{lastBring.why}</Text></View>
          </TouchableOpacity>
        )}
        {busy && (
          <View style={{ gap: 10 }}>
            <View style={{ alignSelf: 'flex-end', maxWidth: '92%', borderRadius: 16, borderTopRightRadius: 4, padding: 12, backgroundColor: GOLD }}><Text style={{ fontSize: 15, lineHeight: 22, color: '#1C1C1E' }}>{pending.current}</Text></View>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }} {...tid('cc-advisor-thinking')}><ActivityIndicator color={current?.color || GOLD} size="small" /><Text style={{ fontSize: 12.5, color: colors.textSecondary }}>The {current?.short || 'Advisor'} is reading the Command Center and company knowledge. Usually 5 to 40 seconds.</Text></View>
          </View>
        )}
      </View>
      {!!convo?.messages?.length && <FactsLine facts={(convo.messages[convo.messages.length - 1] as any).facts_used || facts} colors={colors} />}
    </View>
  );
  const Composer = (
    <View style={{ position: 'absolute', left: 0, right: 0, bottom: 0, padding: 12, paddingBottom: Platform.OS === 'web' ? 12 : 24, backgroundColor: colors.bg, borderTopWidth: 1, borderTopColor: colors.border, alignItems: 'center' }} {...tid('cc-composer')}>
      <View style={{ flexDirection: 'row', alignItems: 'flex-end', gap: 8, width: wide ? 1100 : '100%' }}>
        <View style={{ flex: 1 }}><VoiceTextInput value={text} onChangeText={setText} placeholder={`Ask the ${current?.short || 'Advisor'}, or tap the mic`} showVoice voiceAppend voiceColor={current?.color || GOLD} multiline onSubmitEditing={() => send()} blurOnSubmit testID="cc-advisor-input" /></View>
        <TouchableOpacity onPress={() => send()} disabled={!text.trim() || busy} style={{ width: 44, height: 44, borderRadius: 22, backgroundColor: text.trim() && !busy ? (current?.color || GOLD) : colors.border, alignItems: 'center', justifyContent: 'center' }} {...tid('cc-advisor-send')}>
          <Ionicons name="arrow-up" size={20} color={text.trim() && !busy ? '#1C1C1E' : colors.textSecondary} />
        </TouchableOpacity>
      </View>
    </View>
  );
  return { Threads, Chat, Composer, loading: threads === null, talk };
};
