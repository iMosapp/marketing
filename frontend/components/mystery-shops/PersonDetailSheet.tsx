import React, { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { CallDetailSheet } from './CallsTab';
import { Sheet, Label, Stat, Bar, StatusChip, scoreColor, GOLD, RED, GREEN, tid } from './shared';
import { makeT, fmtWhenL, shortMonthYearL, type Lang, type Tr } from './i18n';

export type PersonHistory = {
  person: { target_id: string; name: string; title: string; department: string; department_label: string; active: boolean };
  summary: { shops: number; unreachable: number; avg_score: number | null; best: number | null; worst: number | null; critical_misses: number; trend_delta: number | null; needs_training: boolean; first_shop: string | null };
  departments: Record<string, { label: string; shops: number; avg_score: number | null; critical_misses: number }>;
  trend: { month: string; label: string; shops: number; unreachable: number; avg_score: number | null; store_avg_score?: number | null; by_department: Record<string, { label: string; shops: number; avg_score: number | null }> }[];
  shops: any[];
  coaching_themes: { text: string; count: number }[];
  store?: { avg_score: number | null; shops: number; people: number; by_department: Record<string, { label: string; avg_score: number | null; shops: number }> };
  vs_store?: number | null;
  vs_department?: Record<string, number>;
};

const Delta = ({ d, colors, what, testID, tr }: { d: number | null | undefined; colors: any; what: string; testID?: string; tr: Tr }) => (
  d == null ? null : (
    <Text style={{ fontSize: 12, fontWeight: '800', color: d > 0 ? GREEN : d < 0 ? RED : colors.textSecondary }} {...(testID ? tid(testID) : {})}>
      {d === 0 ? tr('per.on_line', { what }) : tr('per.vs_line', { d: `${d > 0 ? '+' : ''}${d}`, dir: d > 0 ? tr('rep.above') : tr('rep.below'), what })}
    </Text>
  )
);

// Rep bars with a thin store-average marker per month, so above/below the line is visible at a glance.
const TrendBars = ({ trend, colors, tr }: { trend: PersonHistory['trend']; colors: any; tr: Tr }) => (
  <View style={{ flexDirection: 'row', alignItems: 'flex-end', gap: 8, height: 118 }} {...tid('person-trend')}>
    {trend.map(t => {
      const h = t.avg_score == null ? 4 : Math.max(6, Math.round(78 * t.avg_score / 100));
      const sh = t.store_avg_score == null ? null : Math.max(2, Math.round(78 * t.store_avg_score / 100));
      return (
        <View key={t.month} style={{ flex: 1, alignItems: 'center', gap: 4 }} {...tid(`person-trend-${t.month}`)}>
          <Text style={{ fontSize: 11, fontWeight: '800', color: t.avg_score == null ? colors.textSecondary : scoreColor(t.avg_score) }}>{t.avg_score == null ? (t.unreachable ? tr('per.nr') : '–') : `${t.avg_score}%`}</Text>
          <View style={{ width: '70%', height: 78, justifyContent: 'flex-end', position: 'relative' }}>
            <View style={{ width: '100%', height: h, borderRadius: 4, backgroundColor: t.avg_score == null ? colors.border : scoreColor(t.avg_score) }} />
            {sh != null && <View style={{ position: 'absolute', left: -4, right: -4, bottom: sh, height: 2, backgroundColor: colors.text, opacity: 0.55, borderRadius: 1 }} {...tid(`person-trend-${t.month}-store`)} />}
          </View>
          <Text style={{ fontSize: 10, color: colors.textSecondary }}>{t.label.split(' ')[0]}</Text>
          <Text style={{ fontSize: 9.5, color: colors.textSecondary }}>{t.store_avg_score != null ? tr('per.store_v', { v: t.store_avg_score }) : t.shops ? (t.shops === 1 ? tr('per.shop_1') : tr('per.shop_n', { n: t.shops })) : ' '}</Text>
        </View>
      );
    })}
  </View>
);

// One rep across months: shops, transcript openings, trend. Same sheet for the admin tab and the GM's no-login page (path decides the endpoint, lang the language).
export const PersonDetailSheet = ({ targetId, name, path, onClose, colors, lang = 'en' }: { targetId: string | null; name?: string; path: (targetId: string) => string; onClose: () => void; colors: any; lang?: Lang }) => {
  const tr = makeT(lang);
  const [data, setData] = useState<PersonHistory | null>(null);
  const [error, setError] = useState('');
  const [open, setOpen] = useState<any>(null);
  useEffect(() => {
    setData(null); setError('');
    if (!targetId) return;
    api.get(path(targetId)).then(r => setData(r.data)).catch(() => setError(tr('per.error')));
  }, [targetId]);
  const s = data?.summary;
  const delta = s?.trend_delta;
  const shopsN = (n: number) => (n === 1 ? tr('per.shop_1') : tr('per.shop_n', { n }));
  return (
    <Sheet visible={!!targetId} onClose={onClose} title={data?.person.name || name || tr('per.title')} colors={colors} testID="person-detail-sheet">
      {error ? <Text style={{ fontSize: 14, color: RED }} {...tid('person-detail-error')}>{error}</Text> : !data || !s ? <ActivityIndicator color={GOLD} style={{ marginTop: 30 }} /> : (
        <View style={{ gap: 18 }}>
          <View style={{ gap: 4 }}>
            <Text style={{ fontSize: 13, color: colors.textSecondary }} {...tid('person-detail-sub')}>
              {Object.values(data.departments).map(d => d.label).join(' · ') || data.person.department_label}{data.person.title ? ` · ${data.person.title}` : ''}{s.first_shop ? ` · ${tr('per.since', { when: shortMonthYearL(s.first_shop, lang) })}` : ''}
            </Text>
            {delta != null && (
              <Text style={{ fontSize: 13, fontWeight: '700', color: delta >= 0 ? GREEN : RED }} {...tid('person-detail-delta')}>
                <Ionicons name={delta >= 0 ? 'trending-up' : 'trending-down'} size={13} color={delta >= 0 ? GREEN : RED} /> {tr('per.delta', { d: `${delta >= 0 ? '+' : ''}${delta}` })}
              </Text>
            )}
          </View>
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 10 }}>
            <Stat label={tr('per.shops')} value={`${s.shops}${s.unreachable ? ` · ${s.unreachable} ${tr('per.nr')}` : ''}`} colors={colors} testID="person-stat-shops" />
            <Stat label={tr('per.avg')} value={s.avg_score != null ? `${s.avg_score}%` : '–'} colors={colors} tone={scoreColor(s.avg_score)} testID="person-stat-avg" />
            {data.store?.avg_score != null && <Stat label={tr('per.store_avg', { n: data.store.people })} value={`${data.store.avg_score}%`} colors={colors} tone={data.vs_store == null ? undefined : data.vs_store >= 0 ? GREEN : RED} testID="person-stat-store" />}
            <Stat label={tr('per.range')} value={s.best != null ? `${s.best}% / ${s.worst}%` : '–'} colors={colors} testID="person-stat-range" />
            <Stat label={tr('per.crit')} value={String(s.critical_misses)} colors={colors} tone={s.critical_misses ? RED : GREEN} testID="person-stat-crit" />
          </View>
          <Delta d={data.vs_store} colors={colors} what={tr('per.store_line', { n: data.store?.shops || 0 })} testID="person-vs-store" tr={tr} />
          {Object.keys(data.departments).length > 0 && (
            <View style={{ flexDirection: 'row', gap: 10, flexWrap: 'wrap' }}>
              {Object.entries(data.departments).map(([d, x]) => (
                <View key={d} style={{ flex: 1, minWidth: 140, backgroundColor: colors.card, borderRadius: 12, padding: 10, borderWidth: 1, borderColor: colors.border, gap: 2 }} {...tid(`person-dept-${d}`)}>
                  <Text style={{ fontSize: 11, fontWeight: '800', color: GOLD }}>{x.label.toUpperCase()}</Text>
                  <Text style={{ fontSize: 13, color: colors.text }}>{shopsN(x.shops)}{x.critical_misses ? ` · ${tr('per.critical_n', { n: x.critical_misses })}` : ''}</Text>
                  <Text style={{ fontSize: 13, fontWeight: '800', color: scoreColor(x.avg_score) }}>{x.avg_score != null ? tr('per.avg_short', { v: x.avg_score }) : '–'}{data.store?.by_department?.[d]?.avg_score != null ? <Text style={{ fontSize: 11.5, fontWeight: '600', color: colors.textSecondary }}>  · {tr('per.line_v', { dept: x.label.toLowerCase(), v: data.store.by_department[d].avg_score })}</Text> : null}</Text>
                  <Delta d={data.vs_department?.[d]} colors={colors} what={tr('per.dept_line', { dept: x.label.toLowerCase() })} testID={`person-vs-dept-${d}`} tr={tr} />
                </View>
              ))}
            </View>
          )}
          <View style={{ gap: 8 }}>
            <Label t={tr('per.trend', { n: data.trend.length })} colors={colors} />
            <TrendBars trend={data.trend} colors={colors} tr={tr} />
          </View>
          {data.coaching_themes.length > 0 && (
            <View style={{ gap: 6 }}>
              <Label t={tr('per.keeps')} colors={colors} />
              {data.coaching_themes.map((t, i) => <Text key={i} style={{ fontSize: 13.5, color: colors.text, lineHeight: 19 }} {...tid(`person-theme-${i}`)}>• {t.text}{t.count > 1 ? ` (x${t.count})` : ''}</Text>)}
            </View>
          )}
          <View style={{ gap: 8 }}>
            <Label t={tr('per.every', { n: data.shops.length })} colors={colors} />
            {data.shops.length === 0 && <Text style={{ fontSize: 13.5, color: colors.textSecondary }}>{tr('per.none')}</Text>}
            {data.shops.map((c, i) => (
              <TouchableOpacity key={c.id || i} onPress={() => c.status === 'completed' && setOpen(c)} style={{ backgroundColor: colors.card, borderRadius: 14, borderWidth: 1, borderColor: colors.border, padding: 12, gap: 5 }} {...tid(`person-shop-${i}`)}>
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
                  <View style={{ flex: 1 }}>
                    <Text style={{ fontSize: 14, fontWeight: '800', color: colors.text }}>{c.department_label} <Text style={{ fontSize: 12.5, fontWeight: '600', color: colors.textSecondary }}>· {c.script_title}</Text></Text>
                    <Text style={{ fontSize: 12, color: colors.textSecondary }}>{fmtWhenL(c.ended_at || c.scheduled_for, lang)}{c.persona_name ? ` · ${tr('per.shopper', { name: c.persona_name })}` : ''}</Text>
                  </View>
                  {c.status === 'completed' ? <Text style={{ fontSize: 18, fontWeight: '800', color: scoreColor(c.score_pct) }}>{c.score_pct != null ? `${c.score_pct}%` : '–'}</Text> : <StatusChip status={c.status} colors={colors} lang={lang} />}
                </View>
                {c.status === 'completed' && c.score_pct != null && <Bar pct={c.score_pct} color={scoreColor(c.score_pct)} colors={colors} />}
                {!!c.snippet && (
                  <View style={{ backgroundColor: colors.surface || colors.bg, borderRadius: 10, padding: 8, borderLeftWidth: 3, borderLeftColor: GOLD }}>
                    <Text style={{ fontSize: 12, color: colors.text, lineHeight: 17, fontStyle: 'italic' }} numberOfLines={4} {...tid(`person-shop-${i}-snippet`)}>{c.snippet}</Text>
                  </View>
                )}
                {c.critical_misses?.length > 0 && <Text style={{ fontSize: 12, fontWeight: '700', color: RED }} numberOfLines={2}>{tr('per.critical_list', { items: c.critical_misses.join('; ') })}</Text>}
                {c.status === 'completed' && <Text style={{ fontSize: 11.5, fontWeight: '700', color: GOLD }}>{tr('per.inside')}</Text>}
              </TouchableOpacity>
            ))}
          </View>
          <CallDetailSheet id={open?.id || null} onClose={() => setOpen(null)} colors={colors} lang={lang} publicData={open ? { ...open, evaluation: open.results?.length || open.summary ? { summary: open.summary, critical_misses: open.critical_misses, coaching: open.coaching, wins: open.wins, results: open.results, scorecard_name: undefined } : null } : undefined} />
        </View>
      )}
    </Sheet>
  );
};
