import React, { useState } from 'react';
import { View, Text, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { GOLD, tid } from '../inbox/ownership';
import { Chip, money, miles } from './shared';

export const CONF_COLORS: Record<string, string> = { high: '#34C759', medium: '#FF9500', low: '#FF3B30' };
const when = (iso?: string) => (iso ? new Date(iso).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }) : '');

// Live vs development data. Never shown without one of the two.
export const ProviderBadge = ({ live, badge, testId }: { live: boolean; badge: string; testId?: string }) => (
  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, alignSelf: 'flex-start', borderRadius: 8, paddingHorizontal: 9, paddingVertical: 4, backgroundColor: live ? '#34C75922' : '#FF950022', borderWidth: 1, borderColor: live ? '#34C759' : '#FF9500' }} {...tid(testId || 'market-provider-badge')}>
    <Ionicons name={live ? 'shield-checkmark' : 'flask'} size={12} color={live ? '#34C759' : '#FF9500'} />
    <Text style={{ fontSize: 10.5, fontWeight: '900', letterSpacing: 0.6, color: live ? '#34C759' : '#FF9500' }}>{badge}</Text>
  </View>
);

const Tile = ({ label, value, sub, colors, testId }: { label: string; value: string; sub?: string; colors: any; testId: string }) => (
  <View style={{ flex: 1, minWidth: 96, borderRadius: 12, padding: 10, backgroundColor: colors.bg, borderWidth: 1, borderColor: colors.border, gap: 2 }} {...tid(testId)}>
    <Text style={{ fontSize: 10, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.5 }}>{label}</Text>
    <Text style={{ fontSize: 16, fontWeight: '800', color: colors.text }} numberOfLines={1}>{value}</Text>
    {sub ? <Text style={{ fontSize: 11, color: colors.textSecondary }} numberOfLines={2}>{sub}</Text> : null}
  </View>
);

type Props = { colors: any; snapshot: any; mileage?: number | null; historyCount: number };

// MARKET DATA only. Every number here came from the provider or is a plain statistic of what it returned; the dealership's number is MVP4.
export const MarketSnapshotCard = ({ colors, snapshot, mileage, historyCount }: Props) => {
  const [showWhy, setShowWhy] = useState(false);
  const r = snapshot.result || {};
  const conf = r.confidence || {};
  const cc = CONF_COLORS[conf.level] || colors.textSecondary;
  const range = r.price_range;
  return (
    <View style={{ borderRadius: 18, padding: 16, backgroundColor: colors.card, borderWidth: 1.5, borderColor: snapshot.live ? colors.border : '#FF9500', gap: 12 }} {...tid('market-snapshot')}>
      <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
        <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.8 }}>MARKET DATA</Text>
        <ProviderBadge live={!!snapshot.live} badge={snapshot.badge} />
      </View>
      <View style={{ flexDirection: 'row', alignItems: 'flex-end', gap: 10 }}>
        <View style={{ flex: 1 }}>
          <Text style={{ fontSize: 12.5, color: colors.textSecondary }}>Estimated retail</Text>
          <Text style={{ fontSize: 32, fontWeight: '800', color: colors.text, fontVariant: ['tabular-nums'] }} {...tid('market-retail')}>{r.estimated_retail ? money(r.estimated_retail) : '—'}</Text>
          {r.retail_label ? <Text style={{ fontSize: 11.5, color: colors.textSecondary }} {...tid('market-retail-source')}>{r.retail_label}</Text> : null}
        </View>
        {conf.level ? <Chip label={`${String(conf.level).toUpperCase()} CONFIDENCE`} color={cc} testId="market-confidence" icon="pulse" /> : null}
      </View>
      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
        <Tile colors={colors} testId="market-range" label="ASKING RANGE" value={range ? `${money(range.low)}–${money(range.high)}` : '—'} sub={r.price_range_basis ? `Middle half of ${r.price_range_basis}` : undefined} />
        <Tile colors={colors} testId="market-listings" label={r.comps_kind === 'sales records' ? 'SALES RECORDS' : 'LISTINGS'} value={r.listing_count != null ? String(r.listing_count) : '—'} sub={r.comps_kind === 'sales records' ? `${snapshot.provider_label} national by VIN · no listings` : `${r.comps_used || 0} priced comps · ${snapshot.requested?.radius || 100} mi of ${snapshot.requested?.zip}`} />
        <Tile colors={colors} testId="market-dom" label="DAYS ON MARKET" value={r.avg_dom != null ? `${r.avg_dom} avg` : '—'} sub={r.median_dom != null ? `${r.median_dom} median` : undefined} />
      </View>
      <View style={{ gap: 4 }}>
        <Text style={{ fontSize: 12.5, color: colors.text }} {...tid('market-wholesale')}>
          <Text style={{ fontWeight: '800' }}>Wholesale: </Text>
          {r.estimated_wholesale ? `${money(r.estimated_wholesale)} (${snapshot.live ? snapshot.provider_label : 'development data'})` : `not provided by ${snapshot.provider_label}. Add MMR or Black Book below.`}
        </Text>
        {r.estimated_trade_in ? (
          <Text style={{ fontSize: 12.5, color: colors.text }} {...tid('market-trade-in')}>
            <Text style={{ fontWeight: '800' }}>Trade-in ({snapshot.provider_label}): </Text>{money(r.estimated_trade_in)} · reference only, not the dealership's number
          </Text>
        ) : null}
        {r.avg_miles != null ? (
          <Text style={{ fontSize: 12.5, color: colors.text }} {...tid('market-mileage')}>
            <Text style={{ fontWeight: '800' }}>Mileage: </Text>{mileage != null ? `your trade ${miles(mileage)} · ` : ''}market avg {miles(r.avg_miles)}
            {r.mileage_vs_market != null ? ` (${Math.abs(r.mileage_vs_market).toLocaleString()} ${r.mileage_vs_market <= 0 ? 'under' : 'over'})` : ''}
          </Text>
        ) : null}
        {r.msrp ? <Text style={{ fontSize: 12.5, color: colors.text }}><Text style={{ fontWeight: '800' }}>Original MSRP: </Text>{money(r.msrp)}</Text> : null}
      </View>
      <TouchableOpacity onPress={() => setShowWhy(v => !v)} style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }} {...tid('market-confidence-toggle')}>
        <Ionicons name={showWhy ? 'chevron-up' : 'chevron-down'} size={14} color={GOLD} />
        <Text style={{ fontSize: 12.5, fontWeight: '700', color: GOLD }}>{showWhy ? 'Hide' : 'Why this confidence'}</Text>
      </TouchableOpacity>
      {showWhy ? (
        <View style={{ gap: 3 }} {...tid('market-confidence-reasons')}>
          {(conf.reasons || []).map((w: string, i: number) => <Text key={i} style={{ fontSize: 12.5, color: colors.textSecondary }}>• {w}</Text>)}
          {(r.notes || []).map((w: string, i: number) => <Text key={`n${i}`} style={{ fontSize: 12, color: '#FF9500' }}>• {w}</Text>)}
        </View>
      ) : null}
      <Text style={{ fontSize: 11, color: colors.textSecondary }} {...tid('market-fetched')}>
        Pulled {when(snapshot.fetched_at)}{snapshot.fetched_by_name ? ` by ${snapshot.fetched_by_name}` : ''}{historyCount > 1 ? ` · snapshot ${historyCount} of ${historyCount} (older ones are kept)` : ''}
      </Text>
    </View>
  );
};
