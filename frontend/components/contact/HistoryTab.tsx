/**
 * HistoryTab — everything that ever happened with this contact, one timeline behind filter chips.
 * All / Texts / Tasks: the activity feed (events filtered upstream in [id].tsx). Calls: call logs with transcripts + scorecards. Memos: voice memos.
 */
import React from 'react';
import { View, Text, TouchableOpacity, ScrollView } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import FeedTab from './FeedTab';
import CallsTab from './CallsTab';
import MemosSection from './MemosSection';

const GOLD = '#C9A962';

export type HistoryFilter = 'all' | 'texts' | 'calls' | 'memos' | 'tasks';

export const HISTORY_FILTERS: { key: HistoryFilter; label: string; icon: string }[] = [
  { key: 'all', label: 'All', icon: 'time' },
  { key: 'texts', label: 'Texts', icon: 'chatbubble' },
  { key: 'calls', label: 'Calls', icon: 'call' },
  { key: 'memos', label: 'Memos', icon: 'mic' },
  { key: 'tasks', label: 'Tasks', icon: 'checkbox' },
];

export function matchesHistoryFilter(e: any, f: HistoryFilter): boolean {
  const t = String(e?.event_type || '');
  const c = String(e?.category || '');
  switch (f) {
    case 'texts':
      return c === 'message' || c === 'broadcast' || c === 'customer_activity' || t === 'customer_reply' || e?.direction === 'inbound'
        || t.includes('sms') || t.includes('email') || t.includes('message');
    case 'calls':
      return c === 'call' || t.startsWith('call') || t.includes('voicemail');
    case 'memos':
      return c === 'voice_note' || t.includes('voice_note');
    case 'tasks':
      return c === 'task' || t.startsWith('task') || t.includes('appointment');
    default:
      return true;
  }
}

export default function HistoryTab({ colors, filter, setFilter, feedProps, callsProps, memosProps }: any) {
  return (
    <View testID="history-tab" dataSet={{ testid: 'history-tab' } as any}>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ paddingHorizontal: 16, gap: 6, paddingTop: 12, paddingBottom: 12 }}>
        {HISTORY_FILTERS.map(f => {
          const on = filter === f.key;
          return (
            <TouchableOpacity
              key={f.key}
              onPress={() => setFilter(f.key)}
              activeOpacity={0.75}
              style={{ flexDirection: 'row', alignItems: 'center', gap: 5, paddingHorizontal: 10, height: 32, borderRadius: 16, borderWidth: 1, borderColor: on ? GOLD : colors.border, backgroundColor: on ? `${GOLD}22` : colors.card }}
              testID={`history-filter-${f.key}`} dataSet={{ testid: `history-filter-${f.key}` } as any}
            >
              <Ionicons name={f.icon as any} size={12} color={on ? GOLD : colors.textSecondary} />
              <Text style={{ fontSize: 12.5, fontWeight: '700', color: on ? GOLD : colors.textSecondary }}>{f.label}</Text>
            </TouchableOpacity>
          );
        })}
      </ScrollView>
      {filter === 'calls' ? <CallsTab {...callsProps} /> : filter === 'memos' ? <MemosSection {...memosProps} /> : <FeedTab {...feedProps} filter={filter} />}
    </View>
  );
}
