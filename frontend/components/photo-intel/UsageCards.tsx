import React, { useState } from 'react';
import { View, Text } from 'react-native';
import { useThemeStore } from '../../store/themeStore';
import { Card, GOLD, RED, tid } from '../voice-pilot/shared';
import { Usage, Stat, money, pct, Segmented, Tile } from './shared';

export const TotalsCard = ({ u }: { u: Usage }) => {
  const { colors } = useThemeStore();
  const t = u.totals;
  return (
    <Card title={`LAST ${u.days} DAYS`} testID="photo-intel-totals">
      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
        <Tile label="PHOTOS RECEIVED" value={String(t.received)} testID="photo-intel-received" />
        <Tile label="ANALYZED" value={String(t.analyzed)} sub={`${t.successful} ok · ${t.failed} failed`} testID="photo-intel-analyzed" />
        <Tile label="REUSED (NO CHARGE)" value={String(t.reused)} sub={`${pct(t.reused, t.analyzed + t.reused)} of readings`} testID="photo-intel-reused" />
        <Tile label="COULD NOT OPEN" value={String(t.fetch_failed)} sub={t.paused ? `${t.paused} skipped while paused` : undefined} testID="photo-intel-fetch-failed" />
        <Tile label="EST. AI COST" value={money(t.est_cost_usd)} testID="photo-intel-cost" />
        <Tile label="AVG PER ANALYZED PHOTO" value={money(t.avg_cost_per_analyzed)} sub={t.avg_ms ? `${(t.avg_ms / 1000).toFixed(1)} s average` : undefined} testID="photo-intel-avg-cost" />
        <Tile label="ACTIVE REPS" value={String(t.active_reps)} testID="photo-intel-active-reps" />
        <Tile label="COST PER ACTIVE REP" value={money(t.cost_per_active_rep)} testID="photo-intel-cost-per-rep" />
      </View>
      {(u.monitoring.unattributed_rows > 0 || u.monitoring.duplicate_processing > 0) && (
        <Text style={{ color: RED, fontSize: 12.5, marginTop: 10 }} {...tid('photo-intel-monitoring')}>
          Check: {u.monitoring.unattributed_rows} photo(s) without an organization, {u.monitoring.duplicate_processing} processed twice.
        </Text>
      )}
      <Text style={{ fontSize: 11.5, color: colors.textSecondary, marginTop: 10, lineHeight: 16 }} {...tid('photo-intel-cost-method')}>{u.cost_method}</Text>
    </Card>
  );
};

export const TrendCard = ({ u }: { u: Usage }) => {
  const { colors } = useThemeStore();
  const max = Math.max(1, ...u.daily.map(d => d.received || 0), ...u.daily.map(d => d.analyzed || 0));
  return (
    <Card title="DAILY AND MONTHLY" testID="photo-intel-trend">
      <View style={{ flexDirection: 'row', alignItems: 'flex-end', height: 90, gap: 2 }} {...tid('photo-intel-daily-bars')}>
        {u.daily.map(d => (
          <View key={d.day} style={{ flex: 1, height: `${Math.max(2, ((d.received || d.analyzed || 0) / max) * 100)}%`, backgroundColor: (d.received || d.analyzed) ? GOLD : colors.border, borderRadius: 2 }} />
        ))}
      </View>
      <Text style={{ fontSize: 11.5, color: colors.textSecondary, marginTop: 4 }}>{u.daily[0]?.day} to {u.daily[u.daily.length - 1]?.day}, photos per day</Text>
      <View style={{ marginTop: 12 }}>
        {u.daily.filter(d => d.received || d.analyzed).slice(-7).reverse().map(d => <Line key={d.day} label={d.day} s={d as Stat} testID={`photo-intel-day-${d.day}`} />)}
      </View>
      <Text style={{ fontSize: 12, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.6, marginTop: 12, marginBottom: 4 }}>BY MONTH</Text>
      {u.monthly.length === 0 && <Text style={{ fontSize: 13, color: colors.textSecondary }}>No photos yet.</Text>}
      {u.monthly.slice().reverse().map(m => <Line key={m.month} label={m.month} s={m} testID={`photo-intel-month-${m.month}`} />)}
    </Card>
  );
};

const Line = ({ label, sub, s, testID }: { label: string; sub?: string; s: Stat; testID: string }) => {
  const { colors } = useThemeStore();
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', paddingVertical: 6, borderBottomWidth: 1, borderBottomColor: colors.border, gap: 8 }} {...tid(testID)}>
      <View style={{ flex: 1 }}>
        <Text style={{ fontSize: 13, color: colors.text, fontWeight: '700' }} numberOfLines={1}>{label}</Text>
        <Text style={{ fontSize: 11.5, color: colors.textSecondary }} numberOfLines={1}>
          {sub ? `${sub} · ` : ''}{s.received || 0} in · {s.analyzed || 0} analyzed · {s.reused || 0} reused · {s.failed || 0} failed{s.active_reps ? ` · ${s.active_reps} reps` : ''}
        </Text>
      </View>
      <Text style={{ fontSize: 13, color: colors.text, fontWeight: '800' }}>{money(s.est_cost_usd)}</Text>
    </View>
  );
};

const VIEWS = [{ key: 'orgs', label: 'Orgs' }, { key: 'stores', label: 'Locations' }, { key: 'reps', label: 'Reps' }, { key: 'source', label: 'Source' }];

export const BreakdownCard = ({ u }: { u: Usage }) => {
  const { colors } = useThemeStore();
  const [view, setView] = useState('orgs');
  const rows = view === 'orgs' ? u.organizations.map(r => ({ id: r.organization_id || 'none', label: r.name, sub: r.active_reps ? `${money(r.cost_per_active_rep)} per rep` : '', s: r }))
    : view === 'stores' ? u.stores.map(r => ({ id: r.store_id || 'none', label: r.name, sub: r.org_name, s: r }))
    : view === 'reps' ? u.reps.map(r => ({ id: r.user_id || 'none', label: r.name, sub: [r.org_name, r.store_name].filter(Boolean).join(' · '), s: r }))
    : [...u.by_source.map(r => ({ id: r.source, label: r.source === 'mms' ? 'Texted by customers' : r.source === 'upload' ? 'Uploaded by reps' : r.source, sub: '', s: r })),
       ...u.by_model.map(r => ({ id: r.model, label: `Model ${r.model}`, sub: '', s: r }))];
  return (
    <Card title="HIGHEST USAGE" testID="photo-intel-breakdown">
      <Segmented value={view} options={VIEWS} onChange={setView} testID="photo-intel-breakdown-view" />
      <View style={{ marginTop: 8 }}>
        {rows.length === 0 && <Text style={{ fontSize: 13, color: colors.textSecondary, paddingVertical: 8 }} {...tid('photo-intel-breakdown-empty')}>No photos in this range.</Text>}
        {rows.slice(0, 25).map((r, i) => <Line key={`${r.id}-${i}`} label={r.label} sub={r.sub} s={r.s} testID={`photo-intel-row-${view}-${i}`} />)}
      </View>
    </Card>
  );
};
