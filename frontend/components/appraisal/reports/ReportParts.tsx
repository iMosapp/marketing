import React from 'react';
import { View, Text, ScrollView, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { GOLD, tid } from '../../inbox/ownership';
import { money, miles } from '../shared';

export const fmtS = (s?: number | null) => (s == null ? '—' : s < 60 ? `${s}s` : s < 3600 ? `${Math.round(s / 60)} min` : s < 86400 ? `${(s / 3600).toFixed(1)} h` : `${(s / 86400).toFixed(1)} d`);
const pct = (v?: number | null) => (v == null ? '—' : `${v}%`);

export const StatTiles = ({ colors, counts, averages, rates }: { colors: any; counts: any; averages: any; rates: any }) => {
  const tiles = [
    { k: 'started', label: 'Started', v: String(counts.started ?? 0), c: GOLD }, { k: 'submitted', label: 'Submitted', v: String(counts.submitted ?? 0), c: GOLD },
    { k: 'approved', label: 'Approved', v: String(counts.approved ?? 0), sub: `${pct(rates.approval)} of submitted`, c: '#34C759' }, { k: 'declined', label: 'Declined', v: String(counts.declined ?? 0), c: '#FF3B30' },
    { k: 'presented', label: 'Presented', v: String(counts.presented ?? 0), c: GOLD }, { k: 'accepted', label: 'Accepted', v: String(counts.accepted ?? 0), sub: `${pct(rates.acceptance)} of presented`, c: '#34C759' },
    { k: 'wants_more', label: 'Wants more', v: String(counts.wants_more ?? 0), c: '#FF9500' }, { k: 'thinking', label: 'Thinking', v: String(counts.thinking ?? 0), c: '#30B0C7' },
    { k: 'not_trading', label: 'Not trading', v: String(counts.not_trading ?? 0), c: '#8E8E93' }, { k: 'trade_confirmed', label: 'Trades confirmed', v: String(counts.trade_confirmed ?? 0), sub: `${pct(rates.confirmed_trade)} of accepted`, c: GOLD },
    { k: 'reappraisals', label: 'Reappraisals', v: String(counts.reappraisals ?? 0), c: '#30B0C7' }, { k: 'waiting_now', label: 'Waiting now', v: String(counts.waiting_now ?? 0), c: '#FF9500' },
    { k: 'avg_suggested', label: 'Avg suggested ACV', v: averages.suggested_acv != null ? money(averages.suggested_acv) : '—', c: GOLD },
    { k: 'avg_approved', label: 'Avg approved', v: averages.approved_value != null ? money(averages.approved_value) : '—', c: '#34C759' },
    { k: 'avg_adjustment', label: 'Avg manager change', v: averages.manager_adjustment != null ? `${averages.manager_adjustment >= 0 ? '+' : '-'}${money(Math.abs(averages.manager_adjustment))}` : '—', sub: averages.manager_adjustment_abs != null ? `${money(averages.manager_adjustment_abs)} either way` : undefined, c: '#FF9500' },
    { k: 'avg_gap', label: 'Avg customer gap', v: averages.expectation_gap != null ? money(averages.expectation_gap) : '—', sub: 'wanted minus offered', c: '#FF9500' },
    { k: 'avg_response', label: 'Avg desk response', v: fmtS(averages.manager_response_s), sub: 'submit to first decision', c: '#30B0C7' },
  ];
  return (
    <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }} {...tid('report-tiles')}>
      {tiles.map(t => (
        <View key={t.k} style={{ width: '31%', flexGrow: 1, borderRadius: 14, padding: 12, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, gap: 2 }} {...tid(`tile-${t.k}`)}>
          <Text style={{ fontSize: 9.5, fontWeight: '800', color: t.c, letterSpacing: 0.5 }} numberOfLines={1}>{t.label.toUpperCase()}</Text>
          <Text style={{ fontSize: 20, fontWeight: '800', color: colors.text, fontVariant: ['tabular-nums'] }} numberOfLines={1} {...tid(`tile-${t.k}-value`)}>{t.v}</Text>
          {t.sub ? <Text style={{ fontSize: 10.5, color: colors.textSecondary }} numberOfLines={1}>{t.sub}</Text> : null}
        </View>
      ))}
    </View>
  );
};

// Facts per salesperson / manager / make. No scores, no ranking words: counts and averages only.
export const BreakdownTable = ({ colors, title, rows, kind, testId }: { colors: any; title: string; rows: any[]; kind: 'rep' | 'manager' | 'make'; testId: string }) => {
  if (!rows?.length) return null;
  const cols = kind === 'manager' ? ['Decisions', 'Avg change', 'Response'] : ['Started', 'Approved', 'Accepted', 'Avg gap'];
  return (
    <View style={{ borderRadius: 16, padding: 14, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, gap: 8 }} {...tid(testId)}>
      <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.6 }}>{title.toUpperCase()}</Text>
      <ScrollView horizontal showsHorizontalScrollIndicator={false}>
        <View>
          <View style={{ flexDirection: 'row', paddingBottom: 6, borderBottomWidth: 1, borderBottomColor: colors.border }}>
            <Text style={{ width: 150, fontSize: 11, fontWeight: '800', color: colors.textSecondary }}>{kind === 'make' ? 'MAKE' : 'NAME'}</Text>
            {cols.map(c => <Text key={c} style={{ width: 92, fontSize: 11, fontWeight: '800', color: colors.textSecondary, textAlign: 'right' }}>{c.toUpperCase()}</Text>)}
          </View>
          {rows.map(r => (
            <View key={r.id} style={{ flexDirection: 'row', paddingVertical: 7, borderBottomWidth: 1, borderBottomColor: colors.border }} {...tid(`${testId}-row-${r.id}`)}>
              <Text style={{ width: 150, fontSize: 13, fontWeight: '700', color: colors.text }} numberOfLines={1}>{r.name}</Text>
              {kind === 'manager' ? (
                <>
                  <Cell colors={colors} v={String(r.decisions ?? r.approved ?? 0)} />
                  <Cell colors={colors} v={r.avg_adjustment != null ? `${r.avg_adjustment >= 0 ? '+' : '-'}${money(Math.abs(r.avg_adjustment))}` : '—'} />
                  <Cell colors={colors} v={fmtS(r.avg_response_s)} />
                </>
              ) : (
                <>
                  <Cell colors={colors} v={String(r.started)} />
                  <Cell colors={colors} v={`${r.approved}`} />
                  <Cell colors={colors} v={`${r.accepted}${r.acceptance != null ? ` (${r.acceptance}%)` : ''}`} />
                  <Cell colors={colors} v={r.avg_gap != null ? money(r.avg_gap) : '—'} />
                </>
              )}
            </View>
          ))}
        </View>
      </ScrollView>
    </View>
  );
};

const Cell = ({ colors, v }: { colors: any; v: string }) => <Text style={{ width: 92, fontSize: 13, color: colors.text, textAlign: 'right', fontVariant: ['tabular-nums'] }} numberOfLines={1}>{v}</Text>;

// Manager follow-up lists: facts and opportunities, each row opens the desk detail (or the vehicle for revisits).
export const FollowUpList = ({ colors, title, hint, items, kind, testId }: { colors: any; title: string; hint: string; items: any[]; kind: string; testId: string }) => {
  const router = useRouter();
  const ago = (s?: number | null) => (s == null ? '' : s < 3600 ? `${Math.max(1, Math.round(s / 60))} min` : s < 86400 ? `${Math.round(s / 3600)} h` : `${Math.round(s / 86400)} d`);
  return (
    <View style={{ borderRadius: 16, padding: 14, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, gap: 8 }} {...tid(testId)}>
      <Text style={{ fontSize: 14, fontWeight: '800', color: colors.text }}>{title} <Text style={{ color: colors.textSecondary }}>· {items.length}</Text></Text>
      <Text style={{ fontSize: 12, color: colors.textSecondary }}>{hint}</Text>
      {items.length === 0 ? <Text style={{ fontSize: 12.5, color: colors.textSecondary, fontStyle: 'italic' }}>Nothing here right now.</Text> : items.slice(0, 20).map((a: any) => (
        <TouchableOpacity key={a.id || a.vehicle_id} onPress={() => router.push((kind === 'revisit' ? `/vehicle/${a.vehicle_id}` : `/appraisal/desk/${a.id}`) as any)} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 6, borderTopWidth: 1, borderTopColor: colors.border }} {...tid(`${testId}-row-${a.id || a.vehicle_id}`)}>
          <View style={{ flex: 1 }}>
            <Text style={{ fontSize: 13.5, fontWeight: '700', color: colors.text }} numberOfLines={1}>{a.contact_name} · {a.vehicle_label}</Text>
            <Text style={{ fontSize: 12, color: colors.textSecondary }} numberOfLines={2}>
              {kind === 'waiting' ? `${ago(a.waiting_s)} waiting · ${a.user_name || ''}${a.suggested_acv ? ` · suggested ${money(a.suggested_acv)}` : ''}`
                : kind === 'gap' ? `Wanted ${money(a.customer_expected_value)} vs ${money(a.approved_value || a.suggested_acv)} · gap ${money(a.gap)} · ${a.outcome_label || a.status_label}`
                : kind === 'adjustment' ? `${a.approved_by_name || 'Desk'} ${a.manager_delta > 0 ? 'raised' : 'lowered'} by ${money(Math.abs(a.manager_delta))}${a.manager_delta_pct != null ? ` (${Math.abs(a.manager_delta_pct)}%)` : ''} to ${money(a.approved_value)}`
                : kind === 'revisit' ? a.title
                : `${a.outcome_label}${a.customer_expected_value ? ` · wanted ${money(a.customer_expected_value)}` : ''}${a.approved_value ? ` · offered ${money(a.approved_value)}` : ''}${a.mileage_confirmed != null ? ` · ${miles(a.mileage_confirmed)}` : ''} · ${a.user_name || ''}`}
            </Text>
          </View>
          <Ionicons name="chevron-forward" size={14} color={colors.textSecondary} />
        </TouchableOpacity>
      ))}
    </View>
  );
};
