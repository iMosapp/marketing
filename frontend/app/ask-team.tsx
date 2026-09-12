import React, { useCallback, useEffect, useRef, useState } from 'react';
import { View, Text, ScrollView, TouchableOpacity, TextInput, ActivityIndicator, KeyboardAvoidingView, Platform, Image } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useLocalSearchParams } from 'expo-router';
import api from '../services/api';
import { useThemeStore } from '../store/themeStore';
import { useToast } from '../components/common/Toast';
import { ScreenHeader } from '../components/common/ScreenHeader';
import { CallRecordingPlayer } from '../components/CallRecordingPlayer';
import { AnswerText, type Citation } from '../components/ask/AnswerText';

const GOLD = '#C9A962';
const DAYS = [7, 14, 30];
const tid = (id: string) => ({ testID: id, dataSet: { testid: id } as any });

type Msg = { id: string; role: 'user' | 'assistant'; content: string; citations?: Citation[]; follow_ups?: string[]; created_at: string };
type Rep = { id: string; name: string; photo?: string | null };
type Overview = { stats: { days: number; reps: number; threads: number; waiting: number; calls: number; open_tasks: number }; reps: Rep[]; starters: string[]; sessions: { id: string; title: string; updated_at: string; message_count: number }[] };

const RepChip = ({ rep, active, onPress, colors }: { rep: Rep | null; active: boolean; onPress: () => void; colors: any }) => (
  <TouchableOpacity onPress={onPress} style={{ flexDirection: 'row', alignItems: 'center', gap: 6, paddingLeft: rep ? 4 : 12, paddingRight: 12, height: 32, borderRadius: 16, backgroundColor: active ? GOLD + '22' : colors.card, borderWidth: 1, borderColor: active ? GOLD : colors.border }}
    {...tid(`team-ask-rep-${rep ? rep.id : 'all'}`)}>
    {rep ? (rep.photo ? <Image source={{ uri: rep.photo }} style={{ width: 24, height: 24, borderRadius: 12 }} /> : (
      <View style={{ width: 24, height: 24, borderRadius: 12, backgroundColor: GOLD + '33', alignItems: 'center', justifyContent: 'center' }}><Text style={{ fontSize: 11, fontWeight: '800', color: GOLD }}>{(rep.name || '?')[0]}</Text></View>
    )) : <Ionicons name="people" size={14} color={active ? GOLD : colors.textSecondary} />}
    <Text style={{ fontSize: 12.5, fontWeight: '700', color: active ? GOLD : colors.text }}>{rep ? rep.name.split(' ')[0] : 'Whole team'}</Text>
  </TouchableOpacity>
);

// Manager view: ask Jessi across every rep's conversations and calls for the last N days.
export default function AskTeam() {
  const router = useRouter();
  const { colors } = useThemeStore();
  const { showToast } = useToast();
  const { rep } = useLocalSearchParams<{ rep?: string }>();
  const [repId, setRepId] = useState<string | null>(typeof rep === 'string' && rep ? rep : null);
  const [days, setDays] = useState(7);
  const [ov, setOv] = useState<Overview | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [q, setQ] = useState('');
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [forbidden, setForbidden] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [player, setPlayer] = useState<{ url: string; label: string } | null>(null);
  const scrollRef = useRef<ScrollView>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get(`/contact-ask/team/overview?days=${days}${repId ? `&rep_id=${repId}` : ''}`);
      setOv(res.data);
      const last = res.data.sessions?.[0];
      if (last) { const s = await api.get(`/contact-ask/team/sessions/${last.id}`); setSessionId(last.id); setMsgs(s.data.messages || []); }
      else { setSessionId(null); setMsgs([]); }
    } catch (e: any) {
      if (e?.response?.status === 403) setForbidden(true);
      else showToast(e?.response?.data?.detail || 'Could not load the team', 'error');
    } finally { setLoading(false); }
  }, [days, repId]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { setTimeout(() => scrollRef.current?.scrollToEnd({ animated: true }), 80); }, [msgs.length, busy]);

  const ask = async (question: string) => {
    const text = question.trim();
    if (!text || busy) return;
    setQ('');
    setMsgs(m => [...m, { id: `tmp-${Date.now()}`, role: 'user', content: text, created_at: new Date().toISOString() }]);
    setBusy(true);
    try {
      const res = await api.post('/contact-ask/team/ask', { question: text, session_id: sessionId, rep_id: repId, days });
      setSessionId(res.data.session_id);
      setMsgs(m => [...m.filter(x => !x.id.startsWith('tmp-')), res.data.user_message, res.data.message]);
      if (res.data.stats) setOv(o => (o ? { ...o, stats: res.data.stats } : o));
    } catch (e: any) {
      setMsgs(m => m.filter(x => !x.id.startsWith('tmp-')));
      setQ(text);
      showToast(e?.response?.data?.detail || 'Jessi could not answer, try again', 'error');
    } finally { setBusy(false); }
  };

  const openSession = async (id: string) => {
    try { const s = await api.get(`/contact-ask/team/sessions/${id}`); setSessionId(id); setMsgs(s.data.messages || []); setShowHistory(false); }
    catch { showToast('Could not open that chat', 'error'); }
  };
  const newChat = () => { setSessionId(null); setMsgs([]); setShowHistory(false); setPlayer(null); };

  const onCite = (c: Citation) => {
    if (c.kind === 'thread' && c.conversation_id) { router.push(`/thread/${c.conversation_id}` as any); return; }
    if (c.kind === 'call') {
      if (c.has_recording && c.call_sid) { setPlayer({ url: `${api.defaults.baseURL}/calls/recording/${c.call_sid}`, label: c.label }); return; }
      if (c.conversation_id) { router.push(`/thread/${c.conversation_id}` as any); return; }
    }
    showToast(c.snippet ? `${c.label}: ${c.snippet}` : c.label, 'info');
  };

  const st = ov?.stats;
  const scopeName = repId ? (ov?.reps.find(r => r.id === repId)?.name.split(' ')[0] || 'this rep') : 'the team';

  if (forbidden) {
    return (
      <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
        <ScreenHeader title="Ask Jessi about the team" testID="team-ask-header" />
        <View style={{ alignItems: 'center', padding: 32, gap: 10 }} {...tid('team-ask-forbidden')}>
          <Ionicons name="lock-closed-outline" size={34} color={GOLD} />
          <Text style={{ fontSize: 16, fontWeight: '800', color: colors.text }}>Managers only</Text>
          <Text style={{ fontSize: 13, color: colors.textSecondary, textAlign: 'center' }}>You can still ask Jessi about any one customer from their contact page or thread.</Text>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      <ScreenHeader title="Ask Jessi about the team" subtitle={st ? `${st.threads} thread${st.threads === 1 ? '' : 's'} · ${st.waiting} waiting · ${st.calls} call${st.calls === 1 ? '' : 's'} · ${days} days` : undefined} testID="team-ask-header"
        right={(
          <View style={{ flexDirection: 'row', gap: 2 }}>
            {(ov?.sessions?.length || 0) > 0 && <TouchableOpacity onPress={() => setShowHistory(h => !h)} hitSlop={8} style={{ padding: 6 }} {...tid('team-ask-history')}><Ionicons name="time-outline" size={22} color={colors.textSecondary} /></TouchableOpacity>}
            {msgs.length > 0 && <TouchableOpacity onPress={newChat} hitSlop={8} style={{ padding: 6 }} {...tid('team-ask-new-chat')}><Ionicons name="create-outline" size={22} color={GOLD} /></TouchableOpacity>}
          </View>
        )} />
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={{ flex: 1 }} keyboardVerticalOffset={90}>
        <View style={{ borderBottomWidth: 1, borderBottomColor: colors.border, paddingVertical: 8, gap: 8 }}>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ paddingHorizontal: 12, gap: 6 }} {...tid('team-ask-reps')}>
            <RepChip rep={null} active={!repId} onPress={() => setRepId(null)} colors={colors} />
            {(ov?.reps || []).map(r => <RepChip key={r.id} rep={r} active={repId === r.id} onPress={() => setRepId(r.id)} colors={colors} />)}
          </ScrollView>
          <View style={{ flexDirection: 'row', alignItems: 'center', paddingHorizontal: 12, gap: 6 }}>
            <Text style={{ fontSize: 11, fontWeight: '700', color: colors.textSecondary, letterSpacing: 0.5, marginRight: 4 }}>LAST</Text>
            {DAYS.map(d => (
              <TouchableOpacity key={d} onPress={() => setDays(d)} style={{ paddingHorizontal: 11, paddingVertical: 5, borderRadius: 12, backgroundColor: days === d ? GOLD : colors.card, borderWidth: 1, borderColor: days === d ? GOLD : colors.border }} {...tid(`team-ask-days-${d}`)}>
                <Text style={{ fontSize: 12, fontWeight: '800', color: days === d ? '#111' : colors.textSecondary }}>{d} days</Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>

        {showHistory && ov && (
          <View style={{ backgroundColor: colors.card, borderBottomWidth: 1, borderBottomColor: colors.border, paddingVertical: 6 }} {...tid('team-ask-history-list')}>
            {ov.sessions.map(s => (
              <TouchableOpacity key={s.id} onPress={() => openSession(s.id)} style={{ paddingHorizontal: 16, paddingVertical: 9, flexDirection: 'row', alignItems: 'center', gap: 10 }} {...tid(`team-ask-session-${s.id}`)}>
                <Ionicons name="chatbubble-ellipses-outline" size={15} color={s.id === sessionId ? GOLD : colors.textSecondary} />
                <Text style={{ flex: 1, fontSize: 14, color: colors.text }} numberOfLines={1}>{s.title}</Text>
                <Text style={{ fontSize: 11, color: colors.textSecondary }}>{s.message_count / 2 | 0} Q</Text>
              </TouchableOpacity>
            ))}
          </View>
        )}

        <ScrollView ref={scrollRef} style={{ flex: 1 }} contentContainerStyle={{ padding: 16, gap: 12, paddingBottom: 24 }} keyboardShouldPersistTaps="handled" {...tid('team-ask-messages')}>
          {loading && <ActivityIndicator color={GOLD} style={{ marginTop: 20 }} />}
          {!loading && msgs.length === 0 && ov && (
            <View style={{ gap: 10 }} {...tid('team-ask-starters')}>
              <Text style={{ fontSize: 14, color: colors.textSecondary, lineHeight: 20 }}>
                I've read every active conversation, recorded call and open task for {scopeName} from the last {days} days. Ask me who's waiting, what customers are saying, or what's slipping.
              </Text>
              {ov.starters.map(s0 => (
                <TouchableOpacity key={s0} onPress={() => ask(s0)} style={{ backgroundColor: colors.card, borderRadius: 14, padding: 12, borderWidth: 1, borderColor: colors.border, flexDirection: 'row', alignItems: 'center', gap: 10 }} {...tid('team-ask-starter')}>
                  <Ionicons name="sparkles-outline" size={15} color={GOLD} />
                  <Text style={{ flex: 1, fontSize: 14, color: colors.text }}>{s0}</Text>
                  <Ionicons name="arrow-forward" size={14} color={colors.textSecondary} />
                </TouchableOpacity>
              ))}
              {st && st.threads + st.calls === 0 && <Text style={{ fontSize: 12, color: colors.textSecondary, fontStyle: 'italic' }}>No conversations or calls in this window yet. Try a longer range.</Text>}
            </View>
          )}
          {msgs.map(m => m.role === 'user' ? (
            <View key={m.id} style={{ alignSelf: 'flex-end', maxWidth: '85%', backgroundColor: GOLD, borderRadius: 18, borderBottomRightRadius: 6, paddingHorizontal: 14, paddingVertical: 10 }} {...tid('team-ask-user-msg')}>
              <Text style={{ fontSize: 15, color: '#111', lineHeight: 21 }}>{m.content}</Text>
            </View>
          ) : (
            <View key={m.id} style={{ alignSelf: 'flex-start', maxWidth: '94%', gap: 8 }} {...tid('team-ask-ai-msg')}>
              <View style={{ backgroundColor: colors.card, borderRadius: 18, borderBottomLeftRadius: 6, paddingHorizontal: 14, paddingVertical: 12, borderWidth: 1, borderColor: colors.border }}>
                <AnswerText content={m.content} citations={m.citations || []} colors={colors} onCite={onCite} />
              </View>
              {!!m.follow_ups?.length && (
                <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>
                  {m.follow_ups.filter(Boolean).map(f => (
                    <TouchableOpacity key={f} onPress={() => ask(f)} style={{ paddingHorizontal: 11, paddingVertical: 7, borderRadius: 14, borderWidth: 1, borderColor: GOLD + '77', backgroundColor: GOLD + '12' }} {...tid('team-ask-follow-up')}>
                      <Text style={{ fontSize: 12.5, color: colors.text }}>{f}</Text>
                    </TouchableOpacity>
                  ))}
                </View>
              )}
            </View>
          ))}
          {busy && (
            <View style={{ alignSelf: 'flex-start', flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: colors.card, borderRadius: 18, paddingHorizontal: 14, paddingVertical: 10, borderWidth: 1, borderColor: colors.border }} {...tid('team-ask-thinking')}>
              <ActivityIndicator size="small" color={GOLD} /><Text style={{ fontSize: 13, color: colors.textSecondary }}>Reading every thread and call…</Text>
            </View>
          )}
        </ScrollView>

        {player && (
          <View style={{ marginHorizontal: 12, marginBottom: 6, backgroundColor: colors.card, borderRadius: 14, padding: 10, borderWidth: 1, borderColor: GOLD + '66' }} {...tid('team-ask-player')}>
            <View style={{ flexDirection: 'row', alignItems: 'center', marginBottom: 4 }}>
              <Ionicons name="play-circle" size={14} color={GOLD} /><Text style={{ flex: 1, fontSize: 12, fontWeight: '700', color: colors.text, marginLeft: 6 }} numberOfLines={1}>{player.label}</Text>
              <TouchableOpacity onPress={() => setPlayer(null)} hitSlop={8} {...tid('team-ask-player-close')}><Ionicons name="close" size={18} color={colors.textSecondary} /></TouchableOpacity>
            </View>
            <CallRecordingPlayer url={player.url} tint={GOLD} textColor={colors.text} subColor={colors.textSecondary} trackColor={colors.border} />
          </View>
        )}

        <View style={{ flexDirection: 'row', alignItems: 'flex-end', gap: 8, paddingHorizontal: 12, paddingTop: 8, paddingBottom: Platform.OS === 'ios' ? 24 : 12, borderTopWidth: 1, borderTopColor: colors.border, backgroundColor: colors.bg }}>
          <TextInput value={q} onChangeText={setQ} placeholder={`Ask about ${scopeName}…`} placeholderTextColor={colors.textSecondary} multiline maxLength={600}
            onSubmitEditing={() => ask(q)} blurOnSubmit returnKeyType="send"
            style={{ flex: 1, minHeight: 44, maxHeight: 120, backgroundColor: colors.card, borderRadius: 22, paddingHorizontal: 16, paddingTop: 12, paddingBottom: 12, color: colors.text, fontSize: 15, borderWidth: 1, borderColor: colors.border }}
            {...tid('team-ask-input')} />
          <TouchableOpacity onPress={() => ask(q)} disabled={!q.trim() || busy} style={{ width: 44, height: 44, borderRadius: 22, backgroundColor: q.trim() && !busy ? GOLD : colors.card, alignItems: 'center', justifyContent: 'center' }} {...tid('team-ask-send')}>
            <Ionicons name="arrow-up" size={22} color={q.trim() && !busy ? '#111' : colors.textSecondary} />
          </TouchableOpacity>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
