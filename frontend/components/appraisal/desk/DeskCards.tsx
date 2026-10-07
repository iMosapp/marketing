import React, { useState } from 'react';
import { View, Text, TouchableOpacity, Image } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { GOLD, tid } from '../../inbox/ownership';
import { resolvePhotoUrl } from '../../../utils/photoUrl';
import { Chip, GRADE_COLORS, SEVERITY_COLORS, money, miles } from '../shared';
import { MarketSnapshotCard } from '../MarketSnapshotCard';
import { ComparablesList } from '../ComparablesList';

const when = (iso?: string) => (iso ? new Date(iso).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }) : '');
const whenDay = (iso?: string) => (iso ? new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' }) : '');

export const Card = ({ colors, title, children, testId, right }: { colors: any; title: string; children: React.ReactNode; testId: string; right?: React.ReactNode }) => (
  <View style={{ borderRadius: 16, padding: 14, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, gap: 8 }} {...tid(testId)}>
    <View style={{ flexDirection: 'row', alignItems: 'center' }}><Text style={{ flex: 1, fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.6 }}>{title}</Text>{right}</View>
    {children}
  </View>
);

// CUSTOMER WANTS: the number the customer named, and how far it sits from the suggested ACV / approved value. Reported, never computed into the value.
export const CustomerWantsCard = ({ colors, a }: { colors: any; a: any }) => {
  const cev = a.customer_expected_value;
  const ref = a.approved_value ?? a.suggested_acv;
  const gap = cev && ref != null ? cev - ref : null;
  return (
    <Card colors={colors} title="CUSTOMER WANTS" testId="desk-customer-wants">
      {cev ? (
        <View style={{ flexDirection: 'row', alignItems: 'flex-end', gap: 10 }}>
          <Text style={{ fontSize: 30, fontWeight: '800', color: '#FF9500', fontVariant: ['tabular-nums'] }} {...tid('desk-wants-amount')}>{money(cev)}</Text>
          {gap != null ? <Text style={{ fontSize: 13, fontWeight: '700', color: gap > 0 ? '#FF3B30' : '#34C759', paddingBottom: 6 }} {...tid('desk-wants-gap')}>{gap > 0 ? `${money(gap)} above` : gap < 0 ? `${money(-gap)} below` : 'exactly'} the {a.approved_value != null ? 'approved value' : 'suggested ACV'}</Text> : null}
        </View>
      ) : <Text style={{ fontSize: 15, fontWeight: '700', color: colors.text }} {...tid('desk-wants-none')}>{a.expectation_asked === false ? 'Customer has not named a number' : 'Not asked yet'}</Text>}
    </Card>
  );
};

// CONDITION: Jessi's grade (or the human override), the confirmed issues the rep stood behind, and what is still unreviewed.
export const ConditionCard = ({ colors, inspection }: { colors: any; inspection: any }) => {
  const r = inspection?.report;
  if (!inspection) return <Card colors={colors} title="CONDITION" testId="desk-condition"><Text style={{ fontSize: 14, color: colors.textSecondary }}>No inspection on this appraisal.</Text></Card>;
  const color = GRADE_COLORS[r?.final_overall] || colors.textSecondary;
  return (
    <Card colors={colors} title="CONDITION · AI VEHICLE INSPECTION" testId="desk-condition"
      right={r?.final_overall_label ? <Chip label={`${r.final_overall_label.toUpperCase()}${r.overridden ? ' · OVERRIDE' : ''}`} color={color} testId="desk-condition-grade" /> : <Chip label={(inspection.status || 'not run').toUpperCase()} color={colors.textSecondary} />}>
      {r?.reason ? <Text style={{ fontSize: 13, color: colors.text, lineHeight: 18 }}>{r.reason}</Text> : null}
      {r?.override?.reason ? <Text style={{ fontSize: 12, color: colors.textSecondary }}>Override by {r.override.by_name}: {r.override.reason}</Text> : null}
      {r?.confirmed?.length ? (
        <View style={{ gap: 3 }}>
          <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, marginTop: 4 }}>CONFIRMED ISSUES · {r.confirmed.length}</Text>
          {r.confirmed.map((f: any) => (
            <View key={f.id} style={{ flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 4 }} {...tid(`desk-issue-${f.id}`)}>
              <View style={{ width: 8, height: 8, borderRadius: 4, backgroundColor: SEVERITY_COLORS[f.severity] || colors.textSecondary }} />
              <Text style={{ flex: 1, fontSize: 13.5, color: colors.text }}><Text style={{ fontWeight: '800' }}>{f.location_label}</Text>  {f.severity_label} {f.subtype_label}</Text>
              {f.evidence?.[0]?.thumb_url ? <Image source={{ uri: resolvePhotoUrl(f.evidence[0].thumb_url) || '' }} style={{ width: 44, height: 34, borderRadius: 6 }} /> : null}
            </View>
          ))}
        </View>
      ) : r ? <Text style={{ fontSize: 13, color: colors.textSecondary }}>No confirmed issues.</Text> : null}
      {(r?.pending?.length || r?.possible?.length) ? <Text style={{ fontSize: 12, fontWeight: '700', color: '#FF9500' }} {...tid('desk-condition-unreviewed')}>{(r.pending?.length || 0) + (r.possible?.length || 0)} finding{((r.pending?.length || 0) + (r.possible?.length || 0)) > 1 ? 's' : ''} not reviewed by the rep yet.</Text> : null}
    </Card>
  );
};

// MARKET: the snapshot card + comps list the rep saw, plus the book values, labelled by source.
export const MarketCard = ({ colors, market, mileage }: { colors: any; market: any; mileage?: number | null }) => {
  const [open, setOpen] = useState(false);
  if (!market?.snapshot) return <Card colors={colors} title="MARKET DATA" testId="desk-market"><Text style={{ fontSize: 14, color: colors.textSecondary }}>No market pull on this appraisal.</Text>{market?.book_values?.length ? <Books colors={colors} rows={market.book_values} /> : null}</Card>;
  return (
    <View style={{ gap: 10 }} {...tid('desk-market')}>
      <MarketSnapshotCard colors={colors} snapshot={market.snapshot} mileage={mileage} historyCount={market.history?.length || 1} />
      {market.book_values?.length ? <Card colors={colors} title="BOOK VALUES" testId="desk-book-values"><Books colors={colors} rows={market.book_values} /></Card> : null}
      <TouchableOpacity onPress={() => setOpen(v => !v)} style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, height: 40 }} {...tid('desk-comps-toggle')}>
        <Text style={{ fontSize: 13, fontWeight: '800', color: GOLD }}>{open ? 'Hide' : 'Show'} {market.comparables?.length || 0} comparables</Text><Ionicons name={open ? 'chevron-up' : 'chevron-down'} size={14} color={GOLD} />
      </TouchableOpacity>
      {open ? <ComparablesList colors={colors} comps={market.comparables || []} live={!!market.provider?.live} /> : null}
    </View>
  );
};

const Books = ({ colors, rows }: { colors: any; rows: any[] }) => (
  <View>
    {rows.map((b: any) => (
      <View key={b.id} style={{ flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 6 }} {...tid(`desk-book-${b.id}`)}>
        <Text style={{ flex: 1, fontSize: 13.5, fontWeight: '700', color: colors.text }}>{b.source_label} <Text style={{ fontWeight: '400', color: colors.textSecondary }}>{b.value_type_label}{b.entered_by_name ? ` · ${b.entered_by_name}` : ''}</Text></Text>
        <Text style={{ fontSize: 14, fontWeight: '800', color: colors.text, fontVariant: ['tabular-nums'] }}>{money(b.value)}</Text>
      </View>
    ))}
  </View>
);

// REP NOTES + MEDIA + VEHICLE HISTORY + AUDIT TRAIL.
export const RepCard = ({ colors, a }: { colors: any; a: any }) => (
  <Card colors={colors} title={`FROM ${(a.user_name || 'THE SALESPERSON').toUpperCase()}`} testId="desk-rep">
    <Text style={{ fontSize: 13.5, color: a.notes ? colors.text : colors.textSecondary, lineHeight: 19 }} {...tid('desk-notes')}>{a.notes || 'No notes.'}</Text>
    <Text style={{ fontSize: 12, color: colors.textSecondary }}>{a.mode_label}{a.vin ? ` · VIN ${a.vin}` : ' · no VIN'}{a.stock_number ? ` · stock ${a.stock_number}` : ''}{a.mileage_confirmed != null ? ` · ${miles(a.mileage_confirmed)}` : ''}{a.mileage_detected != null && a.mileage_detected !== a.mileage_confirmed ? ` (Jessi read ${miles(a.mileage_detected)})` : ''}</Text>
    {a.media?.length ? (
      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>
        {a.media.slice(0, 12).map((m: any) => (
          <View key={m.id} style={{ width: 72, height: 54, borderRadius: 8, overflow: 'hidden', backgroundColor: colors.bg, borderWidth: 1, borderColor: colors.border, alignItems: 'center', justifyContent: 'center' }} {...tid(`desk-media-${m.id}`)}>
            {m.thumb_url ? <Image source={{ uri: resolvePhotoUrl(m.thumb_url) || '' }} style={{ width: '100%', height: '100%' }} resizeMode="cover" /> : <Ionicons name={m.kind === 'video' ? 'videocam' : 'image'} size={18} color={GOLD} />}
          </View>
        ))}
        {a.media.length > 12 ? <Text style={{ fontSize: 12, color: colors.textSecondary, alignSelf: 'center' }}>+{a.media.length - 12}</Text> : null}
      </View>
    ) : null}
  </Card>
);

export const HistoryCard = ({ colors, a }: { colors: any; a: any }) => {
  const prev = (a.history || []).filter((h: any) => h.id !== a.id);
  if (!prev.length) return null;
  return (
    <Card colors={colors} title="THIS VEHICLE BEFORE" testId="desk-history">
      {prev.map((h: any) => (
        <Text key={h.id} style={{ fontSize: 13, color: colors.text, paddingVertical: 3 }}>{whenDay(h.created_at)}{h.mileage_confirmed != null ? ` · ${miles(h.mileage_confirmed)}` : ''}{h.approved_value ? ` · offered ${money(h.approved_value)}` : h.suggested_acv ? ` · suggested ${money(h.suggested_acv)}` : ''}{h.customer_expected_value ? ` · wanted ${money(h.customer_expected_value)}` : ''}{h.outcome_label ? ` · ${h.outcome_label}` : ''}</Text>
      ))}
    </Card>
  );
};

export const ActivityCard = ({ colors, rows }: { colors: any; rows: any[] }) => {
  const [open, setOpen] = useState(false);
  if (!rows?.length) return null;
  const shown = open ? rows.slice().reverse() : rows.slice(-4).reverse();
  return (
    <Card colors={colors} title={`AUDIT TRAIL · ${rows.length}`} testId="desk-activity" right={rows.length > 4 ? <TouchableOpacity onPress={() => setOpen(v => !v)} {...tid('desk-activity-toggle')}><Text style={{ fontSize: 12, fontWeight: '800', color: GOLD }}>{open ? 'Less' : 'All'}</Text></TouchableOpacity> : undefined}>
      {shown.map((r: any) => (
        <View key={r.id} style={{ flexDirection: 'row', gap: 8, paddingVertical: 3 }}>
          <Text style={{ width: 92, fontSize: 11.5, color: colors.textSecondary }}>{when(r.created_at)}</Text>
          <Text style={{ flex: 1, fontSize: 12.5, color: colors.text }} numberOfLines={3}><Text style={{ fontWeight: '700' }}>{r.actor_name}</Text> {String(r.action || '').replace(/_/g, ' ')}{r.detail ? ` · ${r.detail}` : ''}</Text>
        </View>
      ))}
    </Card>
  );
};
