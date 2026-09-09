import React from 'react';
import { View, Text } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

export type FlowSummaryRow = { icon: string; text: string };
export type LeadFlow = {
  id: string; name: string; description: string; contact_mode: 'text_only' | 'text_and_call';
  call_attempts: { user_ids: string[]; delay_seconds: number; delivery?: 'call' | 'push' }[];
  notify_all_on_intake: boolean; intake_text: string; after_hours_text: string; intake_delay_seconds: number; no_answer_text: string;
  va_enabled: boolean; inquiry_context: string; after_hours_mode: 'text_and_ai' | 'ring_anyway'; text_window_start: string; text_window_end: string;
  caller_id_mode: 'rep' | 'store'; auto_call_on_claim: boolean; tags_on_claim: string[]; tags_on_no_answer: string[];
  exhausted_text_lead: boolean; exhausted_push_manager: boolean;
  sources: { id: string; name: string }[]; source_count: number; summary: FlowSummaryRow[]; updated_by_name?: string; template_key?: string;
};

const ICON_COLOR: Record<string, string> = { chatbubble: '#34C759', sparkles: '#C9A962', call: '#007AFF', notifications: '#5856D6', 'alert-circle': '#FF9500', moon: '#8E8E93', pricetag: '#FF2D55' };

// Plain-English step list shared by the library card and the Lead Source page.
export const LeadFlowSummary = ({ rows, colors, compact, testID }: { rows: FlowSummaryRow[]; colors: any; compact?: boolean; testID?: string }) => (
  <View style={{ gap: compact ? 4 : 8 }} testID={testID} dataSet={testID ? ({ testid: testID } as any) : undefined}>
    {rows.map((r, i) => (
      <View key={i} style={{ flexDirection: 'row', alignItems: 'flex-start', gap: 8 }}>
        <Ionicons name={r.icon as any} size={compact ? 13 : 15} color={ICON_COLOR[r.icon] || colors.textSecondary} style={{ marginTop: 2 }} />
        <Text style={{ flex: 1, fontSize: compact ? 12 : 13, color: colors.text, lineHeight: compact ? 16 : 18 }}>{r.text}</Text>
      </View>
    ))}
  </View>
);
