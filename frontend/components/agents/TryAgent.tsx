import React, { useRef, useState } from 'react';
import { View, Text, TextInput, TouchableOpacity, ActivityIndicator, ScrollView } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { GOLD, tid, errText } from '../inbox/ownership';
import { Section, Label, Hint, inputStyle } from '../inbox/InboxEditorParts';
import { Chips } from '../widget/parts';
import { AgentAvatar } from './AgentPicker';

type Msg = { role: 'customer' | 'agent'; text: string };
type Props = { agentId: string; agent: { name: string; avatar_color: string }; colors: any; showToast: (m: string, t?: any, d?: number) => void };

const OPENERS: Record<string, string[]> = {
  sms: ['Hey, is the blue Tacoma still available? What is the best price?', 'Can I get my car in for an oil change this week?', 'Who is this?'],
  webchat: ['What are your hours?', 'How much does it cost?', 'Can I talk to a real person?'],
};

// Practice conversation with an agent before deploying it. Stateless on the server: the transcript lives here.
export const TryAgent = ({ agentId, agent, colors, showToast }: Props) => {
  const [channel, setChannel] = useState<'sms' | 'webchat'>('sms');
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const scroll = useRef<ScrollView>(null);

  const send = async (line?: string) => {
    const t = (line ?? text).trim();
    if (!t || busy) return;
    const next: Msg[] = [...msgs, { role: 'customer', text: t }];
    setMsgs(next); setText(''); setBusy(true);
    try {
      const r = await api.post(`/agents/${agentId}/try`, { channel, messages: next });
      setMsgs([...next, { role: 'agent', text: r.data.reply }]);
      setTimeout(() => scroll.current?.scrollToEnd({ animated: true }), 50);
    } catch (e: any) { showToast(errText(e, 'The agent did not answer'), 'error', 3500); setMsgs(msgs); }
    finally { setBusy(false); }
  };

  return (
    <Section colors={colors} testId="agent-try">
      <Label colors={colors}>Try {agent.name || 'the agent'}</Label>
      <Hint colors={colors}>You play the customer. Nothing is sent to anyone; this is how the agent will sound once deployed.</Hint>
      <Chips options={[{ value: 'sms', label: 'Text message', icon: 'chatbubble-outline' }, { value: 'webchat', label: 'Website chat', icon: 'globe-outline' }]} value={channel} onChange={v => { setChannel(v as any); setMsgs([]); }} colors={colors} testId="agent-try-channel" />
      <View style={{ minHeight: 160, maxHeight: 380, marginTop: 10, borderRadius: 12, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border }}>
        <ScrollView ref={scroll} contentContainerStyle={{ padding: 12, gap: 8 }} {...tid('agent-try-transcript')}>
          {msgs.length === 0 ? (
            <View style={{ gap: 6 }}>
              <Text style={{ fontSize: 12, color: colors.textSecondary }}>Start with one of these, or type your own:</Text>
              {OPENERS[channel].map(o => (
                <TouchableOpacity key={o} onPress={() => send(o)} style={{ alignSelf: 'flex-start', paddingHorizontal: 12, paddingVertical: 8, borderRadius: 14, borderWidth: 1, borderColor: GOLD + '88' }} {...tid('agent-try-opener')}>
                  <Text style={{ fontSize: 13, color: colors.text }}>{o}</Text>
                </TouchableOpacity>
              ))}
            </View>
          ) : null}
          {msgs.map((m, i) => (
            <View key={i} style={{ flexDirection: 'row', justifyContent: m.role === 'customer' ? 'flex-end' : 'flex-start', gap: 8, alignItems: 'flex-end' }} {...tid(`agent-try-msg-${i}`)}>
              {m.role === 'agent' ? <AgentAvatar agent={agent} size={26} /> : null}
              <View style={{ maxWidth: '80%', padding: 10, borderRadius: 14, backgroundColor: m.role === 'customer' ? GOLD : colors.card, borderWidth: m.role === 'customer' ? 0 : 1, borderColor: colors.border }}>
                <Text style={{ fontSize: 14, lineHeight: 19, color: m.role === 'customer' ? '#111' : colors.text }}>{m.text}</Text>
              </View>
            </View>
          ))}
          {busy ? <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}><AgentAvatar agent={agent} size={26} /><ActivityIndicator color={GOLD} /></View> : null}
        </ScrollView>
      </View>
      <View style={{ flexDirection: 'row', gap: 8, marginTop: 10 }}>
        <TextInput value={text} onChangeText={setText} placeholder={channel === 'sms' ? 'Text like a customer…' : 'Ask like a website visitor…'} placeholderTextColor={colors.textSecondary} onSubmitEditing={() => send()} style={[inputStyle(colors), { flex: 1 }]} {...tid('agent-try-input')} />
        <TouchableOpacity onPress={() => send()} disabled={busy || !text.trim()} style={{ width: 46, height: 46, borderRadius: 12, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center', opacity: busy || !text.trim() ? 0.5 : 1 }} {...tid('agent-try-send')}>
          <Ionicons name="send" size={18} color="#111" />
        </TouchableOpacity>
      </View>
      {msgs.length ? <TouchableOpacity onPress={() => setMsgs([])} style={{ alignSelf: 'flex-start', marginTop: 8 }} {...tid('agent-try-reset')}><Text style={{ fontSize: 12, fontWeight: '700', color: colors.textSecondary }}>Start over</Text></TouchableOpacity> : null}
    </Section>
  );
};
