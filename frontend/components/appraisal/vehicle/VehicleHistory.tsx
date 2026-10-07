import React from 'react';
import { View, Text, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { GOLD, tid } from '../../inbox/ownership';
import { money, miles } from '../shared';

const when = (iso?: string) => (iso ? new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' }) : '');
const STATUS_COLOR: Record<string, string> = { closed: GOLD, declined: '#FF3B30', approved: '#34C759', changed: '#34C759', presented: GOLD, submitted: '#FF9500', resubmitted: '#FF9500', needs_info: '#FF9500' };
const OUTCOME_COLOR: Record<string, string> = { accepted: '#34C759', wants_more: '#FF9500', thinking: '#30B0C7', not_trading: '#8E8E93', other: '#8E8E93' };

// Every appraisal on this vehicle, oldest first: the same normalized line Jessi reads (date · miles · market · suggested · offered · wanted · outcome).
export const AppraisalHistoryList = ({ colors, history }: { colors: any; history: any[] }) => {
  const router = useRouter();
  if (!history.length) return <Text style={{ fontSize: 13, color: colors.textSecondary, textAlign: 'center', paddingVertical: 20 }} {...tid('vehicle-history-empty')}>No appraisals on this vehicle yet.</Text>;
  return (
    <View style={{ gap: 0 }} {...tid('vehicle-history')}>
      {history.map((h, i) => {
        const c = h.outcome ? (OUTCOME_COLOR[h.outcome] || GOLD) : (STATUS_COLOR[h.status] || colors.textSecondary);
        const last = i === history.length - 1;
        return (
          <TouchableOpacity key={h.id} onPress={() => router.push(`/appraisal/${h.id}` as any)} activeOpacity={0.85} style={{ flexDirection: 'row', gap: 12 }} {...tid(`history-${h.id}`)}>
            <View style={{ width: 22, alignItems: 'center' }}>
              <View style={{ width: 12, height: 12, borderRadius: 6, backgroundColor: c, marginTop: 4 }} />
              {!last ? <View style={{ flex: 1, width: 2, backgroundColor: colors.border, marginVertical: 4 }} /> : null}
            </View>
            <View style={{ flex: 1, paddingBottom: last ? 0 : 16, gap: 4 }}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                <Text style={{ flex: 1, fontSize: 14, fontWeight: '800', color: colors.text }}>{when(h.date)}{h.is_reappraisal ? ' · Reappraisal' : i === 0 ? ' · First appraisal' : ''}</Text>
                <View style={{ backgroundColor: c + '22', borderRadius: 8, paddingHorizontal: 7, paddingVertical: 2 }} {...tid(`history-status-${h.id}`)}><Text style={{ fontSize: 10.5, fontWeight: '800', color: c }}>{h.outcome_label || h.status_label}</Text></View>
              </View>
              <Text style={{ fontSize: 12.5, color: colors.text, lineHeight: 18 }} {...tid(`history-line-${h.id}`)}>
                {[h.mileage != null ? miles(h.mileage) : null, h.condition_label ? `${h.condition_label} condition` : null, h.market_retail ? `Market ${money(h.market_retail)}${h.market_live === false ? ' (dev data)' : ''}` : null,
                  h.suggested_acv ? `Suggested ${money(h.suggested_acv)}` : null, h.approved_value ? `Offered ${money(h.approved_value)}${h.manager_delta ? ` (${h.manager_delta > 0 ? '+' : '-'}${money(Math.abs(h.manager_delta))})` : ''}` : null,
                  h.customer_expected_value ? `Wanted ${money(h.customer_expected_value)}` : null, h.expectation_gap ? `Gap ${money(h.expectation_gap)}` : null].filter(Boolean).join(' · ') || 'No numbers yet'}
              </Text>
              <Text style={{ fontSize: 11.5, color: colors.textSecondary }}>{[h.salesperson, h.approved_by_name ? `desk: ${h.approved_by_name}` : null, h.outcome_note ? `"${h.outcome_note.slice(0, 80)}"` : null, h.declined_reason ? `declined: ${h.declined_reason.slice(0, 80)}` : null].filter(Boolean).join(' · ')}</Text>
            </View>
            <Ionicons name="chevron-forward" size={16} color={colors.textSecondary} style={{ marginTop: 2 }} />
          </TouchableOpacity>
        );
      })}
    </View>
  );
};

// Oldest → newest numbers, plus plain-English change lines. Chart-ready points, list for now.
export const ValueHistoryCard = ({ colors, value }: { colors: any; value: any }) => {
  if (!value || (value.points || []).length < 2) return null;
  return (
    <View style={{ borderRadius: 16, padding: 14, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, gap: 8 }} {...tid('value-history')}>
      <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.6 }}>VALUE OVER TIME · {value.points.length} appraisals{value.span_days != null ? ` across ${value.span_days} days` : ''}</Text>
      {(value.changes || []).length === 0 ? <Text style={{ fontSize: 12.5, color: colors.textSecondary }}>Not enough comparable numbers yet.</Text> : value.changes.map((c: any) => {
        const up = c.delta > 0;
        const isMiles = c.key === 'mileage';
        const color = isMiles ? colors.textSecondary : up ? '#34C759' : c.delta < 0 ? '#FF3B30' : colors.textSecondary;
        return (
          <View key={c.key} style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }} {...tid(`value-change-${c.key}`)}>
            <Text style={{ flex: 1, fontSize: 13, color: colors.text }}>{c.label}</Text>
            <Text style={{ fontSize: 13, color: colors.textSecondary, fontVariant: ['tabular-nums'] }}>{isMiles ? miles(c.from) : money(c.from)} → {isMiles ? miles(c.to) : money(c.to)}</Text>
            <Text style={{ minWidth: 72, textAlign: 'right', fontSize: 13, fontWeight: '800', color, fontVariant: ['tabular-nums'] }}>{c.delta === 0 ? 'same' : `${up ? '+' : '-'}${isMiles ? miles(Math.abs(c.delta)) : money(Math.abs(c.delta))}${c.pct != null && !isMiles ? ` (${Math.abs(c.pct)}%)` : ''}`}</Text>
          </View>
        );
      })}
    </View>
  );
};
