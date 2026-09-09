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
  stats?: FlowStats | null;
};

export type FlowStats = { days: number; leads: number; claimed: number; claimed_pct: number | null; median_claim_s: number | null; median_first_reply_s: number | null; replied: number; reply_pct: number | null; ladder_runs: number; no_answer: number; no_answer_pct: number | null };

const ICON_COLOR: Record<string, string> = { chatbubble: '#34C759', sparkles: '#C9A962', call: '#007AFF', notifications: '#5856D6', 'alert-circle': '#FF9500', moon: '#8E8E93', pricetag: '#FF2D55' };

export const fmtSecs = (s: number | null | undefined) => {
  if (s == null) return '--';
  if (s < 60) return `${s}s`;
  if (s < 3600) return `${Math.floor(s / 60)}m ${s % 60 ? `${s % 60}s` : ''}`.trim();
  return `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m`;
};

// "Which playbook actually wins leads": last-N-days scoreboard for one flow.
export const FlowStatsStrip = ({ stats, colors, testID }: { stats: FlowStats | null | undefined; colors: any; testID?: string }) => {
  if (!stats) return null;
  const empty = !stats.leads;
  const cells = [
    { label: 'LEADS', value: String(stats.leads), tone: colors.text },
    { label: 'CLAIMED', value: stats.claimed_pct == null ? '--' : `${stats.claimed_pct}%`, tone: stats.claimed_pct == null ? colors.textSecondary : stats.claimed_pct >= 80 ? '#34C759' : stats.claimed_pct >= 50 ? '#FF9500' : '#FF3B30' },
    { label: 'TO CLAIM', value: fmtSecs(stats.median_claim_s), tone: stats.median_claim_s == null ? colors.textSecondary : stats.median_claim_s <= 300 ? '#34C759' : stats.median_claim_s <= 900 ? '#FF9500' : '#FF3B30' },
    { label: 'REPLIED', value: stats.reply_pct == null ? '--' : `${stats.reply_pct}%`, tone: colors.text },
    { label: 'NO ANSWER', value: stats.no_answer_pct == null ? (stats.ladder_runs ? '0%' : '--') : `${stats.no_answer_pct}%`, tone: stats.no_answer_pct == null ? colors.textSecondary : stats.no_answer_pct <= 10 ? '#34C759' : stats.no_answer_pct <= 30 ? '#FF9500' : '#FF3B30' },
  ];
  return (
    <View testID={testID} dataSet={testID ? ({ testid: testID } as any) : undefined}>
      <Text style={{ fontSize: 10, fontWeight: '800', color: colors.textSecondary, letterSpacing: 1, marginBottom: 6 }}>LAST {stats.days} DAYS{empty ? ' · NO LEADS YET' : ''}</Text>
      <View style={{ flexDirection: 'row', gap: 6 }}>
        {cells.map(c => (
          <View key={c.label} style={{ flex: 1, alignItems: 'center', backgroundColor: colors.surface || colors.bg, borderRadius: 10, paddingVertical: 8, paddingHorizontal: 2, opacity: empty ? 0.5 : 1 }}>
            <Text style={{ fontSize: 14, fontWeight: '800', color: c.tone }} numberOfLines={1}>{empty && c.label !== 'LEADS' ? '--' : c.value}</Text>
            <Text style={{ fontSize: 9, fontWeight: '700', color: colors.textSecondary, letterSpacing: 0.3, marginTop: 2 }} numberOfLines={1}>{c.label}</Text>
          </View>
        ))}
      </View>
    </View>
  );
};

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
