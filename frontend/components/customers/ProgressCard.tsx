import React from 'react';
import { Text, TouchableOpacity, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

const STEP_SHORT: Record<string, string> = { profile: 'Profile', card: 'Card', contact: 'Contact', share: 'Share', memo: 'Memo' };
const STEP_ORDER = ['profile', 'card', 'contact', 'share', 'memo'];
const CATEGORY_COLOR: Record<string, string> = { problem: '#FF3B30', bug: '#FF3B30', question: '#007AFF', suggestion: '#FF9500', other: '#8E8E93' };

const fmt = (iso?: string | null) => (iso ? new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' }) : '');
const ago = (iso?: string | null) => {
  if (!iso) return 'No activity yet';
  const d = Math.floor((Date.now() - new Date(iso).getTime()) / 86400000);
  if (d <= 0) return 'Active today';
  if (d === 1) return 'Active yesterday';
  return `Last active ${d} days ago`;
};

/** Founder view of one pilot customer: setup progress, last sign of life, attention flags and what they reported. */
export function ProgressCard({ row, colors, onOpenIssues }: { row: any; colors: any; onOpenIssues?: () => void }) {
  const p = row.progress;
  const attention: string[] = row.attention || [];
  const issues: any[] = row.issues || [];
  return (
    <View style={{ gap: 12 }} data-testid="customer-progress-card">
      <Text style={{ fontSize: 13, fontWeight: '700', color: '#8E8E93', letterSpacing: 1.2 }}>PROGRESS & ACTIVITY</Text>
      <View style={{ backgroundColor: colors.card, borderRadius: 12, borderWidth: 1, borderColor: colors.border, padding: 14, gap: 12 }}>
        <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
          <Text style={{ fontSize: 15, fontWeight: '700', color: colors.text }} data-testid="customer-progress">
            {p ? (p.complete ? 'Setup complete' : `Setup ${p.done}/${p.total}`) : 'Owner has not signed in yet'}
          </Text>
          <Text style={{ fontSize: 13, color: colors.textSecondary }} data-testid="customer-last-activity">{ago(row.last_activity)}</Text>
        </View>
        {p ? (
          <View style={{ flexDirection: 'row', gap: 6 }}>
            {STEP_ORDER.map((k) => {
              const done = !!p.steps?.[k]?.done;
              return (
                <View key={k} style={{ flex: 1, alignItems: 'center', gap: 4 }} data-testid={`customer-progress-step-${k}`}>
                  <View style={{ height: 6, alignSelf: 'stretch', borderRadius: 3, backgroundColor: done ? '#34C759' : colors.border }} />
                  <Text style={{ fontSize: 11, color: done ? colors.text : colors.textSecondary, fontWeight: done ? '700' : '500' }}>{STEP_SHORT[k]}</Text>
                </View>
              );
            })}
          </View>
        ) : null}
        {row.engagement ? (
          <View style={{ gap: 3 }} data-testid="customer-engagement">
            <Text style={{ fontSize: 11, fontWeight: '800', letterSpacing: 1.2, color: '#8E8E93' }}>ENGAGEMENT</Text>
            <Text style={{ fontSize: 13, color: colors.text }} data-testid="customer-engagement-week">
              Last 7 days: {row.engagement.contacts.week} contacts · {row.engagement.shares.week} card shares · {row.engagement.memos.week} memos · {row.engagement.texts.week} texts · {row.engagement.people.active_week} of {row.engagement.people.total} people signed in
            </Text>
            <Text style={{ fontSize: 12.5, color: colors.textSecondary }} data-testid="customer-engagement-total">
              All time: {row.engagement.contacts.total} contacts · {row.engagement.shares.total} shares · {row.engagement.memos.total} memos · {row.engagement.texts.total} texts
            </Text>
          </View>
        ) : null}
        {attention.length ? (
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }} data-testid="customer-attention">
            {attention.map((a) => (
              <View key={a} style={{ flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 8, paddingVertical: 4, borderRadius: 8, backgroundColor: 'rgba(255,149,0,0.14)' }}>
                <Ionicons name="alert-circle" size={13} color="#FF9500" />
                <Text style={{ fontSize: 12, fontWeight: '600', color: '#FF9500' }}>{a}</Text>
              </View>
            ))}
          </View>
        ) : (
          <Text style={{ fontSize: 12.5, color: colors.textSecondary }} data-testid="customer-attention-none">Nothing needs your attention right now.</Text>
        )}
      </View>

      <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
        <Text style={{ fontSize: 13, fontWeight: '700', color: '#8E8E93', letterSpacing: 1.2 }}>QUESTIONS & PROBLEMS{row.issues_open ? ` · ${row.issues_open} OPEN` : ''}</Text>
        {onOpenIssues && issues.length ? (
          <TouchableOpacity onPress={onOpenIssues} data-testid="customer-issues-open-all"><Text style={{ fontSize: 13, fontWeight: '600', color: '#C9A962' }}>Manage</Text></TouchableOpacity>
        ) : null}
      </View>
      {issues.length ? (
        <View style={{ gap: 6 }} data-testid="customer-issues">
          {issues.map((it) => {
            const color = CATEGORY_COLOR[it.category] || '#8E8E93';
            const open = it.status === 'open' || it.status === 'in_progress';
            return (
              <View key={it.id} style={{ backgroundColor: colors.card, borderRadius: 12, borderWidth: 1, borderColor: colors.border, padding: 12, gap: 6, opacity: open ? 1 : 0.65 }} data-testid={`customer-issue-${it.id}`}>
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                  <View style={{ paddingHorizontal: 7, paddingVertical: 2, borderRadius: 6, backgroundColor: `${color}22` }}>
                    <Text style={{ fontSize: 11, fontWeight: '700', color, textTransform: 'capitalize' }}>{it.category || 'other'}</Text>
                  </View>
                  <Text style={{ fontSize: 12, color: colors.textSecondary, flex: 1 }} numberOfLines={1}>{it.user_name}{it.screen ? ` · ${it.screen}` : ''} · {fmt(it.created_at)}</Text>
                  <Text style={{ fontSize: 11, fontWeight: '700', color: open ? '#FF9500' : '#34C759', textTransform: 'uppercase' }}>{(it.status || 'open').replace('_', ' ')}</Text>
                </View>
                <Text style={{ fontSize: 14, color: colors.text, lineHeight: 19 }}>{it.description}</Text>
              </View>
            );
          })}
        </View>
      ) : (
        <Text style={{ fontSize: 13, color: colors.textSecondary }} data-testid="customer-issues-none">Nothing reported yet.</Text>
      )}
    </View>
  );
}
