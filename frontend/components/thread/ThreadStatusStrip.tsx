import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import api from '../../services/api';
import { GOLD, tid } from '../inbox/ownership';
import { LeadCallTimeline, LeadSummary } from '../LeadCallTimeline';
import { waitInfo } from '../LeadWaitTimer';

const FRESH_MS = 24 * 3600 * 1000;

type Item = { key: string; tone: string; icon: any; title: string; sub?: string; muted?: boolean; action?: { label: string; onPress: () => void } };
type Props = {
  conversationId: string | null; isInternetLead: boolean; closed: boolean; kbOpen: boolean; colors: any;
  leadWait: { receivedAt: string; sourceName?: string } | null; onReply: () => void;
};

// One row above the messages: the single most urgent live thing (visitor on the site, lead waiting, ring ladder), chevron for the rest.
export const ThreadStatusStrip = ({ conversationId, isInternetLead, closed, kbOpen, colors, leadWait, onReply }: Props) => {
  const router = useRouter();
  const [chat, setChat] = useState<any>(null);
  const [lead, setLead] = useState<LeadSummary | null>(null);
  const [expanded, setExpanded] = useState(false);
  const [, setTick] = useState(0);

  const loadChat = useCallback(async () => {
    if (!conversationId || closed) return;
    try { setChat((await api.get(`/widgets/chats/by-conversation/${conversationId}`)).data.chat); } catch {}
  }, [conversationId, closed]);
  useEffect(() => { loadChat(); const t = setInterval(loadChat, 15000); return () => clearInterval(t); }, [loadChat]);
  useEffect(() => { if (!leadWait) return; const t = setInterval(() => setTick(x => x + 1), 15000); return () => clearInterval(t); }, [leadWait]);

  const items: Item[] = [];
  if (chat && !closed) {
    const who = chat.mode === 'human' ? `${chat.agent || 'A teammate'} is in the chat` : 'Jessi is answering';
    items.push({ key: 'webchat', tone: '#34C759', icon: 'chatbubbles', title: chat.visitor_here ? 'On your website right now' : 'Was on your website a moment ago',
      sub: `${who}${chat.last ? ` · "${chat.last}"` : ''}`, action: { label: 'Jump in', onPress: () => router.push(`/webchat/${chat.sid}` as any) } });
  }
  if (leadWait && !closed) {
    const w = waitInfo(leadWait.receivedAt);
    items.push({ key: 'wait', tone: w.color, icon: 'flame', title: `New lead · waiting ${w.label}`, sub: `Reply now to win the deal${leadWait.sourceName ? ` · ${leadWait.sourceName}` : ''}`, action: { label: 'Reply', onPress: onReply } });
  }
  if (lead) {
    const fresh = !lead.receivedAt || Date.now() - new Date(lead.receivedAt).getTime() < FRESH_MS;
    if (lead.urgent || fresh) items.push({ key: 'lead', tone: lead.tone, icon: lead.hasJob ? 'call' : 'chatbubbles-outline', title: lead.title, sub: lead.sub, muted: !lead.urgent });
  }

  const show = !kbOpen && !closed && items.length > 0;
  const top = items[0];
  const rest = items.slice(1).filter(i => i.key !== 'lead');
  const more = items.length - 1;
  const canExpand = items.length > 1 || !!lead;
  const open = show && expanded;
  const row = (i: Item, header?: boolean) => (
    <View key={i.key} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, marginHorizontal: 12, marginBottom: header ? 4 : 6, marginTop: header ? 6 : 0, paddingLeft: 12, paddingRight: 8, paddingVertical: header && !expanded ? 0 : 10, minHeight: 44, borderRadius: 14, backgroundColor: i.muted ? colors.surface : i.tone + '14', borderWidth: 1, borderColor: i.muted ? colors.border : i.tone + '45' }} {...tid(`thread-status-row-${i.key}`)}>
      <Ionicons name={i.icon} size={16} color={i.muted ? colors.textSecondary : i.tone} />
      <TouchableOpacity onPress={() => (header && canExpand ? setExpanded(e => !e) : i.action?.onPress())} activeOpacity={0.7} style={{ flex: 1, minWidth: 0 }} {...tid(header ? 'thread-status-main' : `thread-status-open-${i.key}`)}>
        <Text style={{ fontSize: 13.5, fontWeight: '700', color: i.muted ? colors.textSecondary : colors.text }} numberOfLines={1}>{i.title}</Text>
        {expanded && i.sub ? <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 1 }} numberOfLines={1}>{i.sub}</Text> : null}
      </TouchableOpacity>
      {i.action ? (
        <TouchableOpacity onPress={i.action.onPress} activeOpacity={0.8} style={{ backgroundColor: GOLD, borderRadius: 8, paddingHorizontal: 11, paddingVertical: 6 }} {...tid(`thread-status-action-${i.key}`)}>
          <Text style={{ fontSize: 12, fontWeight: '800', color: '#111' }}>{i.action.label}</Text>
        </TouchableOpacity>
      ) : null}
      {header && canExpand ? (
        <TouchableOpacity onPress={() => setExpanded(e => !e)} hitSlop={8} style={{ flexDirection: 'row', alignItems: 'center', gap: 2, padding: 4 }} {...tid('thread-status-toggle')}>
          {more > 0 && !expanded ? <Text style={{ fontSize: 11.5, fontWeight: '800', color: colors.textSecondary }}>+{more}</Text> : null}
          <Ionicons name={expanded ? 'chevron-up' : 'chevron-down'} size={16} color={colors.textSecondary} />
        </TouchableOpacity>
      ) : null}
    </View>
  );

  // The timeline always renders in the same slot (last child) so it never remounts and refetches when the strip appears or empties.
  return (
    <View {...tid('thread-status-strip')}>
      {show && !(open && top.key === 'lead') ? row(top, true) : null}
      {open ? <View {...tid('thread-status-details')}>{rest.map(i => row(i))}</View> : null}
      {isInternetLead && conversationId ? (
        <LeadCallTimeline conversationId={conversationId} colors={colors} headless={!open} forceOpen={open} onToggle={() => setExpanded(false)} onSummary={setLead} />
      ) : null}
    </View>
  );
};
