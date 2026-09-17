import React, { useEffect, useRef, useState } from 'react';
import { View, Text, Modal, ScrollView, TouchableOpacity, TextInput, ActivityIndicator, KeyboardAvoidingView, Platform } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import api from '../../services/api';
import { useThemeStore } from '../../store/themeStore';
import { useToast } from '../common/Toast';
import { CallRecordingPlayer } from '../CallRecordingPlayer';
import { AnswerText, type Citation } from './AnswerText';
import { showAlert } from '../../services/alert';
import { liveSupported, LIVE_UNSUPPORTED_TITLE, LIVE_UNSUPPORTED_BODY } from '../../hooks/useLiveJessi';
import { useLiveJessiLauncher } from '../jessi/LiveJessiProvider';
import { useLiveConfig } from '../jessi/useLiveConfig';

const GOLD = '#C9A962';
const tid = (id: string) => ({ testID: id, dataSet: { testid: id } as any });

type Msg = { id: string; role: 'user' | 'assistant'; content: string; citations?: Citation[]; follow_ups?: string[]; created_at: string };
type Overview = { contact: { id: string; name: string; first_name: string; photo?: string | null }; stats: any; starters: string[]; sessions: { id: string; title: string; updated_at: string; message_count: number }[] };

// "Ask Jessi about this customer": grounded chat over every text, call, voice note, event and task for one contact.
export const AskJessiSheet = ({ visible, onClose, contactId }: { visible: boolean; onClose: () => void; contactId: string }) => {
  const { colors } = useThemeStore();
  const { showToast } = useToast();
  const router = useRouter();
  const [ov, setOv] = useState<Overview | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [q, setQ] = useState('');
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const [player, setPlayer] = useState<{ url: string; label: string; seek?: number | null } | null>(null);
  const [showHistory, setShowHistory] = useState(false);
  const [drafting, setDrafting] = useState<string | null>(null);
  const [draftPreview, setDraftPreview] = useState<{ text: string; conversation_id: string | null } | null>(null);
  const jessi = useLiveJessiLauncher();
  const { config: liveCfg } = useLiveConfig();
  const canTalk = !!liveCfg?.available && !!liveCfg?.configured;
  const talk = () => {
    if (!liveSupported()) { showAlert(LIVE_UNSUPPORTED_TITLE, `${LIVE_UNSUPPORTED_BODY} Type your question below in the meantime.`); return; }
    onClose();
    jessi.open({ options: { mode: 'assistant', contactId }, title: `Talk about ${ov?.contact.first_name || 'this customer'}` });
  };
  const scrollRef = useRef<ScrollView>(null);
  const seekRef = useRef<((ms: number) => void) | null>(null);

  useEffect(() => {
    if (!visible || !contactId) return;
    setLoading(true); setPlayer(null); setShowHistory(false);
    api.get(`/contact-ask/${contactId}`).then(async res => {
      setOv(res.data);
      const last = res.data.sessions?.[0];
      if (last) {
        const s = await api.get(`/contact-ask/${contactId}/sessions/${last.id}`);
        setSessionId(last.id); setMsgs(s.data.messages || []);
      } else { setSessionId(null); setMsgs([]); }
    }).catch((e: any) => showToast(e?.response?.data?.detail || 'Could not load this customer', 'error')).finally(() => setLoading(false));
  }, [visible, contactId]);

  useEffect(() => { setTimeout(() => scrollRef.current?.scrollToEnd({ animated: true }), 80); }, [msgs.length, busy]);

  const ask = async (question: string) => {
    const text = question.trim();
    if (!text || busy) return;
    setQ('');
    setMsgs(m => [...m, { id: `tmp-${Date.now()}`, role: 'user', content: text, created_at: new Date().toISOString() }]);
    setBusy(true);
    try {
      const res = await api.post(`/contact-ask/${contactId}/ask`, { question: text, session_id: sessionId });
      setSessionId(res.data.session_id);
      setMsgs(m => [...m.filter(x => !x.id.startsWith('tmp-')), res.data.user_message, res.data.message]);
    } catch (e: any) {
      setMsgs(m => m.filter(x => !x.id.startsWith('tmp-')));
      setQ(text);
      showToast(e?.response?.data?.detail || 'Jessi could not answer, try again', 'error');
    } finally { setBusy(false); }
  };

  const draft = async (m: Msg) => {
    setDrafting(m.id);
    try {
      const prev = [...msgs].reverse().find(x => x.role === 'user' && x.created_at <= m.created_at);
      const res = await api.post(`/contact-ask/${contactId}/draft`, { answer: m.content, question: prev?.content || '' });
      setDraftPreview(res.data);
    } catch (e: any) { showToast(e?.response?.data?.detail || 'Could not write a text', 'error'); }
    finally { setDrafting(null); }
  };
  const sendDraft = () => {
    if (!draftPreview) return;
    const { text, conversation_id } = draftPreview;
    setDraftPreview(null);
    if (!conversation_id) { showToast('No text thread with this customer yet. Start one from the contact and paste the draft.', 'info'); return; }
    onClose();
    router.push(`/thread/${conversation_id}?prefill=${encodeURIComponent(text)}` as any);
  };

  const openSession = async (id: string) => {
    try { const s = await api.get(`/contact-ask/${contactId}/sessions/${id}`); setSessionId(id); setMsgs(s.data.messages || []); setShowHistory(false); }
    catch { showToast('Could not open that chat', 'error'); }
  };
  const newChat = () => { setSessionId(null); setMsgs([]); setShowHistory(false); setPlayer(null); };

  const onCite = (c: Citation) => {
    if (c.kind === 'text' && c.conversation_id) {
      onClose();
      router.push(`/thread/${c.conversation_id}?jumpToMsg=${c.message_id}` as any);
      return;
    }
    if (c.kind === 'call') {
      if (!c.has_recording || !c.call_sid) { showToast(c.snippet ? `No recording. ${c.snippet}` : 'No recording saved for this call', 'info'); return; }
      setPlayer({ url: `${api.defaults.baseURL}/calls/recording/${c.call_sid}`, label: `${c.label}${c.seek_seconds != null ? ` · ${Math.floor(c.seek_seconds / 60)}:${String(c.seek_seconds % 60).padStart(2, '0')}` : ''}`, seek: c.seek_seconds });
      setTimeout(() => { if (c.seek_seconds != null) seekRef.current?.(c.seek_seconds * 1000); }, 900);
      return;
    }
    if (c.kind === 'voice_note' && c.audio_url) { setPlayer({ url: c.audio_url, label: c.label, seek: null }); return; }
    showToast(c.snippet ? `${c.label}: ${c.snippet}` : c.label, 'info');
  };

  const first = ov?.contact.first_name || 'this customer';
  const st = ov?.stats;

  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={onClose}>
      <View style={{ flex: 1, backgroundColor: '#000000AA', justifyContent: 'flex-end' }}>
        <TouchableOpacity style={{ height: 40 }} onPress={onClose} activeOpacity={1} />
        <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={{ flex: 1 }}>
          <View style={{ flex: 1, backgroundColor: colors.bg, borderTopLeftRadius: 24, borderTopRightRadius: 24, overflow: 'hidden' }} {...tid('ask-jessi-sheet')}>
            <View style={{ flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingTop: 14, paddingBottom: 10, gap: 10, borderBottomWidth: 1, borderBottomColor: colors.border }}>
              <View style={{ width: 36, height: 36, borderRadius: 18, backgroundColor: GOLD + '22', alignItems: 'center', justifyContent: 'center' }}><Ionicons name="sparkles" size={18} color={GOLD} /></View>
              <View style={{ flex: 1 }}>
                <Text style={{ fontSize: 17, fontWeight: '800', color: colors.text }} numberOfLines={1} {...tid('ask-title')}>Ask Jessi about {first}</Text>
                {st && <Text style={{ fontSize: 12, color: colors.textSecondary }} {...tid('ask-stats')}>{st.texts} texts · {st.calls} call{st.calls === 1 ? '' : 's'} · {st.voice_notes} voice note{st.voice_notes === 1 ? '' : 's'}{st.conversations ? ` · ${st.conversations} recorded` : ''}{st.events ? ` · ${st.events} events` : ''}</Text>}
              </View>
              {canTalk && (
                <TouchableOpacity onPress={talk} hitSlop={8} style={{ flexDirection: 'row', alignItems: 'center', gap: 5, paddingHorizontal: 11, paddingVertical: 7, borderRadius: 16, backgroundColor: GOLD }} {...tid('ask-talk-live')}>
                  <Ionicons name="mic" size={15} color="#111" /><Text style={{ fontSize: 12.5, fontWeight: '800', color: '#111' }}>Talk</Text>
                </TouchableOpacity>
              )}
              {(ov?.sessions?.length || 0) > 0 && (
                <TouchableOpacity onPress={() => setShowHistory(h => !h)} hitSlop={8} style={{ padding: 6 }} {...tid('ask-history')}><Ionicons name="time-outline" size={22} color={colors.textSecondary} /></TouchableOpacity>
              )}
              {msgs.length > 0 && (
                <TouchableOpacity onPress={newChat} hitSlop={8} style={{ padding: 6 }} {...tid('ask-new-chat')}><Ionicons name="create-outline" size={22} color={GOLD} /></TouchableOpacity>
              )}
              <TouchableOpacity onPress={onClose} hitSlop={8} style={{ padding: 6 }} {...tid('ask-close')}><Ionicons name="close" size={26} color={colors.text} /></TouchableOpacity>
            </View>

            {showHistory && ov && (
              <View style={{ backgroundColor: colors.card, borderBottomWidth: 1, borderBottomColor: colors.border, paddingVertical: 6 }} {...tid('ask-history-list')}>
                {ov.sessions.map(s => (
                  <TouchableOpacity key={s.id} onPress={() => openSession(s.id)} style={{ paddingHorizontal: 16, paddingVertical: 9, flexDirection: 'row', alignItems: 'center', gap: 10 }} {...tid(`ask-session-${s.id}`)}>
                    <Ionicons name="chatbubble-ellipses-outline" size={15} color={s.id === sessionId ? GOLD : colors.textSecondary} />
                    <Text style={{ flex: 1, fontSize: 14, color: colors.text }} numberOfLines={1}>{s.title}</Text>
                    <Text style={{ fontSize: 11, color: colors.textSecondary }}>{s.message_count / 2 | 0} Q</Text>
                  </TouchableOpacity>
                ))}
              </View>
            )}

            <ScrollView ref={scrollRef} style={{ flex: 1 }} contentContainerStyle={{ padding: 16, gap: 12, paddingBottom: 24 }} keyboardShouldPersistTaps="handled" {...tid('ask-messages')}>
              {loading && <ActivityIndicator color={GOLD} style={{ marginTop: 20 }} />}
              {!loading && msgs.length === 0 && ov && (
                <View style={{ gap: 10 }} {...tid('ask-starters')}>
                  <Text style={{ fontSize: 14, color: colors.textSecondary, lineHeight: 20 }}>
                    I've read every text, call transcript and voice note with {first}. Ask me anything about the relationship and I'll point you to the exact moment.
                  </Text>
                  {canTalk && (
                    <TouchableOpacity onPress={talk} style={{ backgroundColor: GOLD, borderRadius: 14, padding: 12, flexDirection: 'row', alignItems: 'center', gap: 10 }} {...tid('ask-talk-live-starter')}>
                      <View style={{ width: 30, height: 30, borderRadius: 15, backgroundColor: '#111', alignItems: 'center', justifyContent: 'center' }}><Ionicons name="mic" size={15} color={GOLD} /></View>
                      <View style={{ flex: 1 }}>
                        <Text style={{ fontSize: 14, fontWeight: '800', color: '#111' }}>Talk it through with Jessi</Text>
                        <Text style={{ fontSize: 11.5, color: '#111', opacity: 0.75 }}>Live voice. She already knows this is {first}.</Text>
                      </View>
                      <Ionicons name="arrow-forward" size={14} color="#111" />
                    </TouchableOpacity>
                  )}
                  {ov.starters.map(s0 => (
                    <TouchableOpacity key={s0} onPress={() => ask(s0)} style={{ backgroundColor: colors.card, borderRadius: 14, padding: 12, borderWidth: 1, borderColor: colors.border, flexDirection: 'row', alignItems: 'center', gap: 10 }} {...tid('ask-starter')}>
                      <Ionicons name="sparkles-outline" size={15} color={GOLD} />
                      <Text style={{ flex: 1, fontSize: 14, color: colors.text }}>{s0}</Text>
                      <Ionicons name="arrow-forward" size={14} color={colors.textSecondary} />
                    </TouchableOpacity>
                  ))}
                  {st && st.texts + st.calls + st.voice_notes === 0 && <Text style={{ fontSize: 12, color: colors.textSecondary, fontStyle: 'italic' }}>No touchpoints recorded yet, so answers will be limited to the profile.</Text>}
                </View>
              )}
              {msgs.map(m => m.role === 'user' ? (
                <View key={m.id} style={{ alignSelf: 'flex-end', maxWidth: '85%', backgroundColor: GOLD, borderRadius: 18, borderBottomRightRadius: 6, paddingHorizontal: 14, paddingVertical: 10 }} {...tid('ask-user-msg')}>
                  <Text style={{ fontSize: 15, color: '#111', lineHeight: 21 }}>{m.content}</Text>
                </View>
              ) : (
                <View key={m.id} style={{ alignSelf: 'flex-start', maxWidth: '94%', gap: 8 }} {...tid('ask-ai-msg')}>
                  <View style={{ backgroundColor: colors.card, borderRadius: 18, borderBottomLeftRadius: 6, paddingHorizontal: 14, paddingVertical: 12, borderWidth: 1, borderColor: colors.border }}>
                    <AnswerText content={m.content} citations={m.citations || []} colors={colors} onCite={onCite} />
                  </View>
                  <TouchableOpacity onPress={() => draft(m)} disabled={drafting === m.id} activeOpacity={0.8}
                    style={{ alignSelf: 'flex-start', flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 12, paddingVertical: 7, borderRadius: 14, backgroundColor: GOLD }}
                    {...tid('ask-draft-text')}>
                    {drafting === m.id ? <ActivityIndicator size="small" color="#111" /> : <Ionicons name="chatbubble-ellipses" size={14} color="#111" />}
                    <Text style={{ fontSize: 12.5, fontWeight: '800', color: '#111' }}>{drafting === m.id ? 'Writing your text…' : 'Turn this into a text'}</Text>
                  </TouchableOpacity>
                  {!!m.follow_ups?.length && (
                    <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>
                      {m.follow_ups.map(raw => raw.replace(/\s*\[[TCVEK]\d+(?:@[\d:]+)?\]/g, '').trim()).filter(Boolean).map(f => (
                        <TouchableOpacity key={f} onPress={() => ask(f)} style={{ paddingHorizontal: 11, paddingVertical: 7, borderRadius: 14, borderWidth: 1, borderColor: GOLD + '77', backgroundColor: GOLD + '12' }} {...tid('ask-follow-up')}>
                          <Text style={{ fontSize: 12.5, color: colors.text }}>{f}</Text>
                        </TouchableOpacity>
                      ))}
                    </View>
                  )}
                </View>
              ))}
              {busy && (
                <View style={{ alignSelf: 'flex-start', flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: colors.card, borderRadius: 18, paddingHorizontal: 14, paddingVertical: 10, borderWidth: 1, borderColor: colors.border }} {...tid('ask-thinking')}>
                  <ActivityIndicator size="small" color={GOLD} /><Text style={{ fontSize: 13, color: colors.textSecondary }}>Reading every touchpoint…</Text>
                </View>
              )}
            </ScrollView>

            {draftPreview && (
              <View style={{ marginHorizontal: 12, marginBottom: 6, backgroundColor: colors.card, borderRadius: 16, padding: 14, borderWidth: 1, borderColor: GOLD, gap: 10 }} {...tid('ask-draft-preview')}>
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                  <Ionicons name="chatbubble-ellipses" size={16} color={GOLD} />
                  <Text style={{ flex: 1, fontSize: 12, fontWeight: '800', color: GOLD, letterSpacing: 0.5 }}>TEXT TO {first.toUpperCase()}</Text>
                  <TouchableOpacity onPress={() => setDraftPreview(null)} hitSlop={8} {...tid('ask-draft-dismiss')}><Ionicons name="close" size={18} color={colors.textSecondary} /></TouchableOpacity>
                </View>
                <TextInput value={draftPreview.text} onChangeText={t => setDraftPreview(p => (p ? { ...p, text: t } : p))} multiline
                  style={{ fontSize: 15, color: colors.text, lineHeight: 21, backgroundColor: colors.bg, borderRadius: 12, padding: 10, minHeight: 60, maxHeight: 140, borderWidth: 1, borderColor: colors.border }} {...tid('ask-draft-text-input')} />
                <TouchableOpacity onPress={sendDraft} style={{ height: 44, borderRadius: 12, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 8 }} {...tid('ask-draft-open-thread')}>
                  <Ionicons name="send" size={16} color="#111" /><Text style={{ fontSize: 14, fontWeight: '800', color: '#111' }}>{draftPreview.conversation_id ? 'Open thread with this text' : 'Copy to a new thread'}</Text>
                </TouchableOpacity>
              </View>
            )}
            {player && (
              <View style={{ marginHorizontal: 12, marginBottom: 6, backgroundColor: colors.card, borderRadius: 14, padding: 10, borderWidth: 1, borderColor: GOLD + '66' }} {...tid('ask-player')}>
                <View style={{ flexDirection: 'row', alignItems: 'center', marginBottom: 4 }}>
                  <Ionicons name="play-circle" size={14} color={GOLD} /><Text style={{ flex: 1, fontSize: 12, fontWeight: '700', color: colors.text, marginLeft: 6 }} numberOfLines={1}>{player.label}</Text>
                  <TouchableOpacity onPress={() => setPlayer(null)} hitSlop={8} {...tid('ask-player-close')}><Ionicons name="close" size={18} color={colors.textSecondary} /></TouchableOpacity>
                </View>
                <CallRecordingPlayer url={player.url} tint={GOLD} textColor={colors.text} subColor={colors.textSecondary} trackColor={colors.border} seekControl={seekRef} />
              </View>
            )}

            <View style={{ flexDirection: 'row', alignItems: 'flex-end', gap: 8, paddingHorizontal: 12, paddingTop: 8, paddingBottom: Platform.OS === 'ios' ? 24 : 12, borderTopWidth: 1, borderTopColor: colors.border, backgroundColor: colors.bg }}>
              <TextInput value={q} onChangeText={setQ} placeholder={`Ask about ${first}…`} placeholderTextColor={colors.textSecondary} multiline maxLength={600}
                onSubmitEditing={() => ask(q)} blurOnSubmit returnKeyType="send"
                style={{ flex: 1, minHeight: 44, maxHeight: 120, backgroundColor: colors.card, borderRadius: 22, paddingHorizontal: 16, paddingTop: 12, paddingBottom: 12, color: colors.text, fontSize: 15, borderWidth: 1, borderColor: colors.border }}
                {...tid('ask-input')} />
              <TouchableOpacity onPress={() => ask(q)} disabled={!q.trim() || busy} style={{ width: 44, height: 44, borderRadius: 22, backgroundColor: q.trim() && !busy ? GOLD : colors.card, alignItems: 'center', justifyContent: 'center' }} {...tid('ask-send')}>
                <Ionicons name="arrow-up" size={22} color={q.trim() && !busy ? '#111' : colors.textSecondary} />
              </TouchableOpacity>
            </View>
          </View>
        </KeyboardAvoidingView>
      </View>
    </Modal>
  );
};
