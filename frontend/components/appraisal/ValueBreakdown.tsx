import React from 'react';
import { View, Text } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { GOLD, tid } from '../inbox/ownership';
import { money } from './shared';

export const SOURCE_COLORS: Record<string, string> = { 'MARKET DATA': '#30B0C7', 'BOOK VALUE': '#AF52DE', "I'M ON SOCIAL CALCULATION": GOLD, MANUAL: '#8E8E93', CUSTOMER: '#FF9500', 'MANAGER-APPROVED VALUE': '#34C759' };
export const SourceTagSmall = ({ source }: { source: string }) => {
  const c = SOURCE_COLORS[source] || '#8E8E93';
  return <View style={{ backgroundColor: c + '22', borderRadius: 6, paddingHorizontal: 6, paddingVertical: 2 }}><Text style={{ fontSize: 9.5, fontWeight: '800', color: c, letterSpacing: 0.3 }}>{source}</Text></View>;
};
const signed = (n: number) => (n < 0 ? `-${money(Math.abs(n))}` : n > 0 ? `+${money(n)}` : money(0));

type Props = { colors: any; output: any; marketRetail?: number | null; marketLabel?: string | null; approvedValue?: number | null; approvedBy?: string | null; approvedPending?: boolean; showReferences?: boolean };

// Three numbers, three labels, never blended: MARKET VALUE (what the data says) · SUGGESTED ACV (the dealership's rules) · MANAGER-APPROVED VALUE (the real trade number).
export const ThreeNumbers = ({ colors, marketRetail, marketLabel, suggested, low, high, approved, approvedBy, pending }: { colors: any; marketRetail?: number | null; marketLabel?: string | null; suggested?: number | null; low?: number | null; high?: number | null; approved?: number | null; approvedBy?: string | null; pending?: boolean }) => {
  const Tile = ({ label, value, sub, color, testId, strong }: { label: string; value: string; sub?: string; color: string; testId: string; strong?: boolean }) => (
    <View style={{ flex: 1, flexShrink: 1, minWidth: 0, borderRadius: 14, paddingVertical: 12, paddingHorizontal: 10, backgroundColor: strong ? color + '1A' : colors.card, borderWidth: 1, borderColor: strong ? color : colors.border, gap: 3 }} {...tid(testId)}>
      <Text style={{ fontSize: 9.5, fontWeight: '800', color, letterSpacing: 0.6 }} numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.8}>{label}</Text>
      <Text style={{ fontSize: value.length > 8 ? 16 : 19, fontWeight: '800', color: colors.text, fontVariant: ['tabular-nums'] }} numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.6}>{value}</Text>
      {sub ? <Text style={{ fontSize: 10.5, color: colors.textSecondary, lineHeight: 13 }} numberOfLines={2}>{sub}</Text> : null}
    </View>
  );
  return (
    <View style={{ flexDirection: 'row', gap: 8 }} {...tid('three-numbers')}>
      <Tile label="MARKET VALUE" value={marketRetail ? money(marketRetail) : '—'} sub={marketRetail ? (marketLabel || 'Market data') : 'No market pull'} color={SOURCE_COLORS['MARKET DATA']} testId="num-market" />
      <Tile label="SUGGESTED ACV" value={suggested != null ? money(suggested) : '—'} sub={suggested != null && low != null ? `${money(low)} to ${money(high)}` : 'Manager sets it'} color={GOLD} testId="num-suggested" />
      <Tile label="APPROVED" value={approved != null ? money(approved) : pending ? 'Waiting' : '—'} sub={approved != null ? (approvedBy ? `by ${approvedBy}` : 'Approved') : pending ? 'At the desk' : 'Not submitted'} color={SOURCE_COLORS['MANAGER-APPROVED VALUE']} testId="num-approved" strong={approved != null} />
    </View>
  );
};

// Every reference the desk should see side by side; decision inputs, never averaged.
export const ReferencesCard = ({ colors, output: o }: { colors: any; output: any }) => {
  const refs = (o?.valuation_sources || []).filter((s: any) => s.key !== o?.basis?.key);
  if (!refs.length) return null;
  return (
    <View style={{ borderRadius: 16, paddingHorizontal: 14, paddingVertical: 6, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border }} {...tid('references-card')}>
      <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.6, paddingVertical: 8 }}>OTHER REFERENCES · SIDE BY SIDE, NEVER AVERAGED</Text>
      {refs.map((s: any) => (
        <View key={s.key} style={{ flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 7, borderTopWidth: 1, borderTopColor: colors.border }} {...tid(`reference-${s.key.replace(':', '-')}`)}>
          <SourceTagSmall source={s.source} />
          <View style={{ flex: 1, minWidth: 0 }}>
            <Text style={{ fontSize: 13, fontWeight: '600', color: colors.text }} numberOfLines={1}>{s.label}</Text>
            {s.note ? <Text style={{ fontSize: 10.5, color: colors.textSecondary }} numberOfLines={1}>{s.note}</Text> : null}
          </View>
          <Text style={{ fontSize: 14, fontWeight: '800', color: colors.text, fontVariant: ['tabular-nums'] }}>{money(s.amount)}</Text>
        </View>
      ))}
    </View>
  );
};

// The whole story of a number: starting value, every rule that applied (and only those), the total, what needs a manager, and the other references side by side.
export const ValueBreakdown = ({ colors, output: o, marketRetail, marketLabel, approvedValue, approvedBy, approvedPending, showReferences = true }: Props) => {
  if (!o) return null;
  return (
    <View style={{ gap: 12 }} {...tid('value-breakdown')}>
      <ThreeNumbers colors={colors} marketRetail={marketRetail} marketLabel={marketLabel} suggested={o.suggested_acv} low={o.suggested_low} high={o.suggested_high} approved={approvedValue} approvedBy={approvedBy} pending={approvedPending} />
      <View style={{ borderRadius: 16, paddingHorizontal: 14, paddingVertical: 6, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border }} {...tid('breakdown-card')}>
        <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.6, paddingVertical: 8 }}>HOW WE GOT HERE</Text>
        {o.breakdown?.length ? o.breakdown.map((l: any, i: number) => (
          <View key={l.key + i} style={{ paddingVertical: 8, borderTopWidth: 1, borderTopColor: colors.border, gap: 3 }} {...tid(`breakdown-line-${l.key}`)}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
              <Text style={{ flex: 1, fontSize: 14, fontWeight: '700', color: colors.text }}>{l.label}</Text>
              <Text style={{ fontSize: 15, fontWeight: '800', color: l.key === 'basis' ? colors.text : l.amount < 0 ? '#FF3B30' : '#34C759', fontVariant: ['tabular-nums'] }}>{l.key === 'basis' ? money(l.amount) : signed(l.amount)}</Text>
            </View>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
              <SourceTagSmall source={l.source} />
              {l.reason ? <Text style={{ flex: 1, fontSize: 11.5, color: colors.textSecondary }} numberOfLines={2}>{l.reason}</Text> : null}
            </View>
            {l.items?.length ? (
              <View style={{ marginTop: 4, gap: 3, paddingLeft: 10, borderLeftWidth: 2, borderLeftColor: colors.border }} {...tid('breakdown-recon-items')}>
                {l.items.map((it: any) => (
                  <View key={it.finding_id} style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }} {...tid(`breakdown-item-${it.finding_id}`)}>
                    <Text style={{ flex: 1, fontSize: 12.5, color: colors.text }} numberOfLines={1}>{it.label}{it.by_name ? <Text style={{ color: colors.textSecondary }}>  · {it.by_name}</Text> : null}</Text>
                    <Text style={{ fontSize: 12.5, fontWeight: '800', color: '#FF3B30', fontVariant: ['tabular-nums'] }}>-{money(it.amount)}</Text>
                  </View>
                ))}
              </View>
            ) : null}
          </View>
        )) : <Text style={{ fontSize: 13, color: colors.textSecondary, paddingBottom: 10 }} {...tid('breakdown-empty')}>No starting value yet. Pull market data or add a book value, or the manager sets the number at the desk.</Text>}
        {o.suggested_acv != null ? (
          <View style={{ flexDirection: 'row', alignItems: 'center', paddingVertical: 10, borderTopWidth: 2, borderTopColor: GOLD }} {...tid('breakdown-total')}>
            <Text style={{ flex: 1, fontSize: 14, fontWeight: '800', color: GOLD }}>SUGGESTED ACV</Text>
            <Text style={{ fontSize: 18, fontWeight: '800', color: colors.text, fontVariant: ['tabular-nums'] }}>{money(o.suggested_acv)}</Text>
          </View>
        ) : null}
      </View>
      {o.review_reasons?.length ? (
        <View style={{ borderRadius: 14, padding: 12, backgroundColor: '#FF950018', borderWidth: 1, borderColor: '#FF950066', gap: 4 }} {...tid('review-reasons')}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}><Ionicons name="eye" size={14} color="#FF9500" /><Text style={{ fontSize: 11, fontWeight: '800', color: '#FF9500', letterSpacing: 0.6 }}>NEEDS A MANAGER'S EYES</Text></View>
          {o.review_reasons.map((r: string, i: number) => <Text key={i} style={{ fontSize: 13, color: colors.text }}>• {r}</Text>)}
        </View>
      ) : null}
      {o.warnings?.length ? (
        <View style={{ gap: 3 }} {...tid('calc-warnings')}>
          {o.warnings.map((w: string, i: number) => <Text key={i} style={{ fontSize: 12, color: colors.textSecondary, lineHeight: 17 }}>⚠︎ {w}</Text>)}
        </View>
      ) : null}
      {showReferences ? <ReferencesCard colors={colors} output={o} /> : null}
    </View>
  );
};
