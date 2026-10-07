import React from 'react';
import { View, Text } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { GOLD, tid } from '../inbox/ownership';
import { money, miles } from './shared';
import { CONF_COLORS } from './MarketSnapshotCard';

const when = (iso?: string) => (iso ? new Date(iso).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }) : '');
const dash = 'not provided';

const Row = ({ colors, label, value, sub, testId }: { colors: any; label: string; value: string; sub?: string; testId: string }) => (
  <View style={{ flexDirection: 'row', alignItems: 'flex-start', justifyContent: 'space-between', gap: 8, paddingVertical: 5, borderBottomWidth: 1, borderBottomColor: colors.border + '66' }} {...tid(testId)}>
    <Text style={{ fontSize: 11.5, fontWeight: '700', color: colors.textSecondary, flex: 1 }}>{label}</Text>
    <View style={{ alignItems: 'flex-end', flexShrink: 1, maxWidth: '58%' }}>
      <Text style={{ fontSize: 13, fontWeight: '800', color: value === dash ? colors.textSecondary : colors.text, fontVariant: ['tabular-nums'], textAlign: 'right' }}>{value}</Text>
      {sub ? <Text style={{ fontSize: 10.5, color: colors.textSecondary, textAlign: 'right' }}>{sub}</Text> : null}
    </View>
  </View>
);

// One provider, one column. Every number is that provider's own; nothing here is blended with the other column.
export const ProviderCard = ({ colors, card }: { colors: any; card: any }) => {
  const ok = card.status === 'ok';
  const conf = card.confidence || {};
  const range = card.price_range;
  const statusColor = ok ? '#34C759' : card.status === 'not_configured' ? colors.textSecondary : '#FF3B30';
  return (
    <View style={{ flex: 1, minWidth: 250, borderRadius: 16, padding: 12, backgroundColor: colors.card, borderWidth: 1.5, borderColor: ok ? colors.border : statusColor + '88', gap: 2 }} {...tid(`provider-card-${card.provider}`)}>
      <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 6 }}>
        <Text style={{ fontSize: 13, fontWeight: '900', letterSpacing: 0.8, color: colors.text }}>{String(card.label || card.provider).toUpperCase()}</Text>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }} {...tid(`provider-status-${card.provider}`)}>
          <Ionicons name={ok ? (card.live ? 'shield-checkmark' : 'flask') : card.status === 'not_configured' ? 'key-outline' : 'alert-circle'} size={13} color={statusColor} />
          <Text style={{ fontSize: 10.5, fontWeight: '800', color: statusColor }}>{ok ? (card.live ? 'LIVE' : 'DEV DATA') : card.status === 'not_configured' ? 'NO KEY' : card.status === 'quota' ? 'QUOTA' : 'FAILED'}{card.cached ? ' · cached' : ''}</Text>
        </View>
      </View>
      {!ok ? <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 6 }} {...tid(`provider-error-${card.provider}`)}>{card.error || 'No answer'}</Text> : (
        <>
          <Text style={{ fontSize: 26, fontWeight: '800', color: colors.text, fontVariant: ['tabular-nums'], marginTop: 4 }} {...tid(`provider-retail-${card.provider}`)}>{card.estimated_retail ? money(card.estimated_retail) : '—'}</Text>
          <Text style={{ fontSize: 11, color: colors.textSecondary, marginBottom: 6 }}>{card.retail_label || 'Estimated retail'}</Text>
          <Row colors={colors} testId={`provider-wholesale-${card.provider}`} label="Wholesale" value={card.estimated_wholesale ? money(card.estimated_wholesale) : dash} />
          <Row colors={colors} testId={`provider-tradein-${card.provider}`} label="Trade-in" value={card.estimated_trade_in ? money(card.estimated_trade_in) : dash} sub={card.estimated_trade_in ? `${card.label} ${String(card.trade_in_source || '').replace('vinaudit_', '')} value` : undefined} />
          <Row colors={colors} testId={`provider-median-${card.provider}`} label="Comparable median" value={card.comps_median ? money(card.comps_median) : dash} />
          <Row colors={colors} testId={`provider-average-${card.provider}`} label="Comparable average" value={card.comps_average ? money(card.comps_average) : dash} />
          <Row colors={colors} testId={`provider-range-${card.provider}`} label="Price range" value={range ? `${money(range.low)}–${money(range.high)}` : dash} sub={card.price_range_basis || undefined} />
          <Row colors={colors} testId={`provider-count-${card.provider}`} label="Comparable count" value={card.comps_count != null ? String(card.comps_count) : dash} sub={card.comps_kind} />
          <Row colors={colors} testId={`provider-mileage-${card.provider}`} label="Mileage" value={card.mileage != null ? miles(card.mileage) : card.mileage_used != null ? miles(card.mileage_used) : dash} sub={card.mileage == null && card.mileage_used != null ? 'provider average, none given' : card.avg_miles ? `market avg ${miles(card.avg_miles)}` : undefined} />
          <Row colors={colors} testId={`provider-zip-${card.provider}`} label="ZIP / location" value={card.zip_applies ? `${card.zip} · ${card.radius} mi` : 'national (no ZIP input)'} />
          <Row colors={colors} testId={`provider-confidence-${card.provider}`} label="Confidence" value={conf.level ? String(conf.level).toUpperCase() : dash} sub={card.provider_certainty != null ? `provider certainty ${card.provider_certainty}%` : conf.score != null ? `score ${conf.score}` : undefined} />
          <Row colors={colors} testId={`provider-time-${card.provider}`} label="Provider timestamp" value={when(card.fetched_at)} sub={card.response_ms != null ? `${card.response_ms} ms · ${card.calls || 0} call${card.calls === 1 ? '' : 's'}${card.lookup_id ? ` · ${card.lookup_id}` : ''}` : undefined} />
          {conf.level ? <View style={{ height: 3, borderRadius: 2, backgroundColor: (CONF_COLORS[conf.level] || colors.border) + '66', marginTop: 8 }} /> : null}
        </>
      )}
    </View>
  );
};

// The two provider observations side by side plus the gap between them. No combined value exists anywhere.
export const ProviderCompare = ({ colors, comparison }: { colors: any; comparison: any }) => {
  const d = comparison?.difference || {};
  const v = comparison?.vehicle || {};
  return (
    <View style={{ gap: 10 }} {...tid('provider-compare')}>
      <Text style={{ fontSize: 11.5, color: colors.textSecondary }} {...tid('provider-compare-vehicle')}>
        {[v.year, v.make, v.model, v.trim].filter(Boolean).join(' ')}{v.vin ? ` · ${v.vin}` : ''}{v.mileage != null ? ` · ${miles(v.mileage)}` : ''} · ZIP {comparison.zip} · {comparison.radius} mi · {when(comparison.created_at)}{comparison.by_name ? ` by ${comparison.by_name}` : ''}
      </Text>
      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 10 }}>
        {(comparison.providers || []).map((c: any) => <ProviderCard key={c.provider} colors={colors} card={c} />)}
      </View>
      <View style={{ borderRadius: 14, padding: 12, backgroundColor: GOLD + '14', borderWidth: 1, borderColor: GOLD + '66', gap: 4 }} {...tid('provider-difference')}>
        <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.8 }}>VALUE DIFFERENCE</Text>
        {d.available ? (
          <>
            <Text style={{ fontSize: 22, fontWeight: '800', color: colors.text, fontVariant: ['tabular-nums'] }} {...tid('provider-difference-dollars')}>{d.dollars > 0 ? '+' : d.dollars < 0 ? '−' : ''}{money(Math.abs(d.dollars))} <Text style={{ fontSize: 14, color: colors.textSecondary }}>({d.percent}%)</Text></Text>
            <Text style={{ fontSize: 12, color: colors.textSecondary }}>{d.higher === 'marketcheck' ? 'MarketCheck reads higher.' : d.higher === 'vinaudit' ? 'VinAudit reads higher.' : 'Both providers agree.'} {d.note}</Text>
          </>
        ) : <Text style={{ fontSize: 12.5, color: colors.textSecondary }}>{d.reason || 'Not available.'}</Text>}
      </View>
      <Text style={{ fontSize: 11, color: colors.textSecondary }}>{comparison.calls_total || 0} paid call{comparison.calls_total === 1 ? '' : 's'} used for this comparison.</Text>
    </View>
  );
};
