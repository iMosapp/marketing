import React, { useState } from 'react';
import { View, Text, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { GOLD, tid } from '../inbox/ownership';
import { Chip, money, miles } from './shared';

export const MATCH_COLORS: Record<string, string> = { exact: '#34C759', strong: '#30B0C7', close: '#FF9500', loose: '#8E8E93' };
const ORDER = ['exact', 'strong', 'close', 'loose'];
const FIRST = 8;

const CompRow = ({ c, colors }: { c: any; colors: any }) => {
  const [open, setOpen] = useState(false);
  const q = c.match?.quality || 'loose';
  const color = MATCH_COLORS[q];
  const title = [c.year, c.make, c.model, c.trim].filter(Boolean).join(' ');
  const line = [c.mileage != null ? miles(c.mileage) : null, c.distance_mi != null ? `${Math.round(c.distance_mi)} mi away` : null, c.dealer_name, c.dom != null ? `${c.dom} days listed` : null, c.is_certified ? 'CPO' : null].filter(Boolean).join(' · ');
  return (
    <TouchableOpacity onPress={() => setOpen(v => !v)} activeOpacity={0.8} style={{ paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: colors.border, gap: 5 }} {...tid(`comp-${c.id}`)}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
        <View style={{ flex: 1, gap: 4 }}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
            <Chip label={c.match?.label || 'MATCH'} color={color} testId={`comp-match-${c.id}`} />
            <Text style={{ fontSize: 10.5, fontWeight: '700', color: colors.textSecondary }}>{c.match?.score}/100</Text>
          </View>
          <Text style={{ fontSize: 14.5, fontWeight: '700', color: colors.text }} numberOfLines={1}>{title || c.heading || 'Listing'}</Text>
          <Text style={{ fontSize: 12, color: colors.textSecondary }} numberOfLines={2}>{line}</Text>
        </View>
        <Text style={{ fontSize: 17, fontWeight: '800', color: colors.text, fontVariant: ['tabular-nums'] }} {...tid(`comp-price-${c.id}`)}>{c.price ? money(c.price) : '—'}</Text>
        <Ionicons name={open ? 'chevron-up' : 'chevron-down'} size={14} color={colors.textSecondary} />
      </View>
      {open ? (
        <View style={{ gap: 2, paddingLeft: 4 }} {...tid(`comp-why-${c.id}`)}>
          {(c.match?.why || []).map((w: string, i: number) => <Text key={i} style={{ fontSize: 12, color: colors.textSecondary }}>• {w}</Text>)}
          {c.city || c.state ? <Text style={{ fontSize: 12, color: colors.textSecondary }}>• {[c.city, c.state].filter(Boolean).join(', ')}{c.exterior_color ? ` · ${c.exterior_color}` : ''}{c.dealer_type ? ` · ${c.dealer_type}` : ''}</Text> : null}
          {c.vin ? <Text style={{ fontSize: 11, color: colors.textSecondary }}>• VIN {c.vin}</Text> : null}
        </View>
      ) : null}
    </TouchableOpacity>
  );
};

type Props = { colors: any; comps: any[]; live: boolean };

// Best comparables first. Match quality is I'm On Social's own read (year, trim, mileage, distance, CPO), not the provider's.
export const ComparablesList = ({ colors, comps, live }: Props) => {
  const [filter, setFilter] = useState('all');
  const [all, setAll] = useState(false);
  const counts: Record<string, number> = { all: comps.length };
  ORDER.forEach(q => { counts[q] = comps.filter(c => c.match?.quality === q).length; });
  const shown = (filter === 'all' ? comps : comps.filter(c => c.match?.quality === filter));
  const list = all ? shown : shown.slice(0, FIRST);
  return (
    <View style={{ gap: 8 }} {...tid('comparables')}>
      <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
        <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 0.8 }}>COMPARABLES · {comps.length}</Text>
        <Text style={{ fontSize: 10.5, color: colors.textSecondary }}>{live ? 'Listings: provider · match quality: I\'m On Social' : 'Development listings · match quality: I\'m On Social'}</Text>
      </View>
      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>
        {['all', ...ORDER].filter(q => q === 'all' || counts[q] > 0).map(q => {
          const on = filter === q;
          const color = q === 'all' ? GOLD : MATCH_COLORS[q];
          return (
            <TouchableOpacity key={q} onPress={() => { setFilter(q); setAll(false); }} style={{ borderRadius: 9, paddingHorizontal: 10, paddingVertical: 6, backgroundColor: on ? color + '33' : colors.card, borderWidth: 1, borderColor: on ? color : colors.border }} {...tid(`comp-filter-${q}`)}>
              <Text style={{ fontSize: 11.5, fontWeight: '800', color: on ? color : colors.textSecondary }}>{q === 'all' ? 'All' : q[0].toUpperCase() + q.slice(1)} · {counts[q]}</Text>
            </TouchableOpacity>
          );
        })}
      </View>
      <View style={{ borderRadius: 16, paddingHorizontal: 14, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border }}>
        {list.length ? list.map(c => <CompRow key={c.id} c={c} colors={colors} />) : <Text style={{ paddingVertical: 14, fontSize: 13, color: colors.textSecondary }} {...tid('comps-empty')}>No comparables in this group.</Text>}
        {shown.length > FIRST ? (
          <TouchableOpacity onPress={() => setAll(v => !v)} style={{ paddingVertical: 12, alignItems: 'center' }} {...tid('comps-show-all')}>
            <Text style={{ fontSize: 13, fontWeight: '700', color: GOLD }}>{all ? 'Show fewer' : `Show all ${shown.length}`}</Text>
          </TouchableOpacity>
        ) : null}
      </View>
    </View>
  );
};
