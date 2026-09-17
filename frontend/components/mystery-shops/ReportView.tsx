import React, { useMemo, useState } from 'react';
import { View, Text, TouchableOpacity, Platform, Linking, ScrollView } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { CallDetailSheet } from './CallsTab';
import { PersonDetailSheet } from './PersonDetailSheet';
import { Label, Stat, Bar, StatusChip, deptLabel, scoreColor, channelIcon, channelKey, channelLabel, GOLD, RED, GREEN, AMBER, tid , replyDur } from './shared';
import { makeT, fmtWhenL, type Lang } from './i18n';

export type Criterion = { text: string; critical: boolean; passed: number; total: number; pass_pct: number; department: string; department_label?: string };
type Theme = { text: string; count: number };
export type LeaderRow = { rank: number; key: string; target_id: string; name: string; title?: string; avg_score: number; completed: number; best: number | null; critical_misses: number; prev_avg: number | null; delta: number | null; badges: { key: string; label: string; detail: string }[] };
const MEDAL = ['#C9A962', '#A8A9AD', '#CD7F32'];

export type Report = {
  client: { id: string; name: string; brand: string; city: string; state: string; contact_name: string; locale?: string; language?: string }; month: string; month_label: string; prev_month_label?: string; language?: string; generated_at: string;
  summary: { completed: number; planned: number; scheduled: number; unreachable: number; avg_score: number | null; avg_adherence: number | null; people_shopped: number; needs_training: number; text_shops?: number; text_no_reply?: number; avg_first_reply_s?: number | null; email_shops?: number; email_no_reply?: number; avg_first_email_reply_s?: number | null };
  by_department: Record<string, { label?: string; planned: number; planned_calls?: number; planned_texts?: number; scheduled: number; completed: number; unreachable: number; avg_score: number | null; people?: number; criteria?: Criterion[]; coaching_themes?: Theme[]; leaderboard?: LeaderRow[] }>;
  people: { key?: string; target_id?: string; name: string; department: string; department_label?: string; title: string; shops: number; completed: number; unreachable: number; avg_score: number | null; avg_adherence: number | null; best: number | null; worst: number | null; critical_misses: number; needs_training: boolean; last_shop: string | null; coaching: string[] }[];
  criteria: Criterion[];
  coaching_themes: Theme[];
  calls: any[];
  report_url?: string;
};

const avg = (vals: (number | null | undefined)[]) => { const v = vals.filter((x): x is number => typeof x === 'number'); return v.length ? Math.round(v.reduce((a, b) => a + b, 0) / v.length) : null; };

// Pass rate per criterion and coaching counts for any set of completed calls (the server does the same per department; this lets any filter combo compare).
const criteriaFrom = (done: any[], labelOf: (d: string) => string): Criterion[] => {
  const m = new Map<string, Criterion>();
  for (const c of done) for (const r of c.results || []) {
    if (r.passed == null) continue;
    const d = c.department || 'sales';
    const k = `${d}|${r.text || r.criterion_id}`;
    const cur = m.get(k) || { text: r.text || r.criterion_id, critical: !!r.critical, passed: 0, total: 0, pass_pct: 0, department: d, department_label: labelOf(d) };
    cur.total += 1; cur.passed += r.passed ? 1 : 0; m.set(k, cur);
  }
  return [...m.values()].map(c => ({ ...c, pass_pct: Math.round(100 * c.passed / c.total) })).sort((a, b) => a.pass_pct - b.pass_pct || b.total - a.total);
};
const themesFrom = (done: any[]): Theme[] => {
  const m = new Map<string, number>();
  for (const c of done) for (const tip of (c.coaching || []).slice(0, 3)) { const k = String(tip).trim().replace(/\.$/, ''); m.set(k, (m.get(k) || 0) + 1); }
  return [...m.entries()].map(([text, count]) => ({ text, count })).sort((a, b) => b.count - a.count).slice(0, 6);
};
// People rows rebuilt from a filtered set of shops (the server's rows mix every channel, so a "Texts only" view needs its own).
const peopleFrom = (calls: any[], base: Report['people']): Report['people'] => {
  const m = new Map<string, any>();
  for (const c of calls) {
    const dept = c.department || 'sales';
    const k = `${c.target_id}:${dept}`;
    const b = base.find(p => p.key === k) || base.find(p => p.name === c.target_name && p.department === dept);
    const p = m.get(k) || { key: k, target_id: c.target_id, name: c.target_name, department: dept, title: b?.title || '', shops: 0, completed: 0, unreachable: 0, scores: [] as number[], critical_misses: 0, needs_training: false, last_shop: null, avg_adherence: null, worst: null, coaching: [] as string[] };
    p.shops += 1;
    if (c.status === 'completed') { p.completed += 1; if (typeof c.score_pct === 'number') p.scores.push(c.score_pct); p.critical_misses += (c.critical_misses || []).length; p.coaching.push(...(c.coaching || []).slice(0, 2)); p.last_shop = c.ended_at || p.last_shop; }
    else if (c.status === 'unreachable') p.unreachable += 1;
    m.set(k, p);
  }
  return [...m.values()].map(p => { const a = avg(p.scores); return { ...p, avg_score: a, best: p.scores.length ? Math.max(...p.scores) : null, needs_training: !!(p.completed && ((a != null && a < 70) || p.critical_misses >= 2)), coaching: p.coaching.slice(0, 3) }; })
    .sort((a, b) => (a.avg_score == null ? 1 : 0) - (b.avg_score == null ? 1 : 0) || (b.avg_score || 0) - (a.avg_score || 0));
};
const CH_KEYS = ['call', 'text', 'email'] as const;

// Ranked rows for one department: medals for the top three, badges for top score / most improved / most shops. Tap a name for their history.
const Leaderboard = ({ dept, label, rows, prevLabel, colors, onPerson, lang }: { dept: string; label: string; rows: LeaderRow[]; prevLabel?: string; colors: any; onPerson?: (id: string, name: string) => void; lang: Lang }) => {
  const tr = makeT(lang);
  return (
    <View style={{ gap: 8 }} {...tid(`report-leaderboard-${dept}`)}>
      <Label t={tr('rep.leaderboard', { dept: label.toUpperCase() })} colors={colors} />
      {rows.map(r => {
        const medal = r.rank <= 3 ? MEDAL[r.rank - 1] : null;
        return (
          <TouchableOpacity key={r.key} disabled={!onPerson} onPress={() => onPerson?.(r.target_id, r.name)} style={{ backgroundColor: colors.card, borderRadius: 14, borderWidth: 1, borderColor: r.rank === 1 ? GOLD : colors.border, padding: 12, flexDirection: 'row', alignItems: 'center', gap: 12 }} {...tid(`report-leader-${dept}-${r.rank}`)}>
            <View style={{ width: 34, height: 34, borderRadius: 17, backgroundColor: medal ? medal + '22' : colors.surface, borderWidth: medal ? 2 : 0, borderColor: medal || 'transparent', alignItems: 'center', justifyContent: 'center' }}>
              {medal ? <Ionicons name="trophy" size={16} color={medal} /> : <Text style={{ fontSize: 13, fontWeight: '800', color: colors.textSecondary }}>{r.rank}</Text>}
            </View>
            <View style={{ flex: 1, gap: 3 }}>
              <Text style={{ fontSize: 15, fontWeight: '800', color: colors.text }}>{r.name}{r.title ? <Text style={{ fontSize: 12, fontWeight: '600', color: colors.textSecondary }}> · {r.title}</Text> : null}</Text>
              <Text style={{ fontSize: 12.5, color: colors.textSecondary }}>
                {r.completed === 1 ? tr('rep.shops_1') : tr('rep.shops_n', { n: r.completed })}{r.best != null ? ` · ${tr('rep.best', { v: r.best })}` : ''} · {r.delta != null ? <Text style={{ fontWeight: '800', color: r.delta > 0 ? GREEN : r.delta < 0 ? RED : colors.textSecondary }}>{tr('rep.vs', { d: `${r.delta > 0 ? '+' : ''}${r.delta}`, prev: prevLabel || tr('rep.last_month') })}</Text> : <Text>{tr('rep.new')}</Text>}
              </Text>
              {r.badges.length > 0 && (
                <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 5, marginTop: 2 }}>
                  {r.badges.map(b => (
                    <View key={b.key} style={{ flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 8, paddingVertical: 3, borderRadius: 8, backgroundColor: GOLD + '22' }} {...tid(`report-leader-${dept}-${r.rank}-badge-${b.key}`)}>
                      <Ionicons name={b.key === 'top_score' ? 'star' : b.key === 'most_improved' ? 'trending-up' : 'flame'} size={11} color={GOLD} />
                      <Text style={{ fontSize: 10.5, fontWeight: '800', color: GOLD }}>{b.label.toUpperCase()}</Text>
                      <Text style={{ fontSize: 10.5, fontWeight: '600', color: colors.textSecondary }}>{b.detail}</Text>
                    </View>
                  ))}
                </View>
              )}
            </View>
            <Text style={{ fontSize: 22, fontWeight: '800', color: scoreColor(r.avg_score) }}>{r.avg_score}%</Text>
          </TouchableOpacity>
        );
      })}
    </View>
  );
};

const ChipRow = ({ items, value, onChange, colors, testPrefix }: { items: { key: string; label: string; count?: number }[]; value: string; onChange: (k: string) => void; colors: any; testPrefix: string }) => (
  <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 6, paddingRight: 8 }}>
    {items.map(it => {
      const on = value === it.key;
      return (
        <TouchableOpacity key={it.key} onPress={() => onChange(it.key)} style={{ paddingHorizontal: 12, paddingVertical: 7, borderRadius: 16, backgroundColor: on ? GOLD : colors.card, borderWidth: 1, borderColor: on ? GOLD : colors.border }} {...tid(`${testPrefix}-${it.key.replace(/[^a-z0-9_-]/gi, '_')}`)}>
          <Text style={{ fontSize: 12.5, fontWeight: '800', color: on ? '#111' : colors.text }}>{it.label}{it.count != null ? <Text style={{ fontWeight: '600', color: on ? '#333' : colors.textSecondary }}> {it.count}</Text> : null}</Text>
        </TouchableOpacity>
      );
    })}
  </ScrollView>
);

// One report body for the admin tab and the client's no-login page. personPath decides which endpoint the tap-a-name sheet uses; lang = the client's language on the public page.
export const ReportView = ({ report, colors, compact, personPath, lang = 'en' }: { report: Report; colors: any; compact?: boolean; personPath?: (targetId: string) => string; lang?: Lang }) => {
  const tr = makeT(lang);
  const [open, setOpen] = useState<any>(null);
  const [person, setPerson] = useState<{ id: string; name: string } | null>(null);
  const [dept, setDept] = useState('all');
  const [agent, setAgent] = useState('all');
  const [channel, setChannel] = useState<'all' | 'call' | 'text' | 'email'>('all');
  const labelOf = (d: string) => report.by_department[d]?.label || deptLabel(d);
  const filtered = !!(dept !== 'all' || agent !== 'all' || channel !== 'all');

  const v = useMemo(() => {
    const inDept = (d?: string) => dept === 'all' || (d || 'sales') === dept;
    const inCh = (c: any) => channel === 'all' || channelKey(c) === channel;
    const calls = report.calls.filter(c => inDept(c.department) && inCh(c) && (agent === 'all' || c.target_name === agent));
    const done = calls.filter(c => c.status === 'completed');
    const people = channel === 'all' ? report.people.filter(p => inDept(p.department) && (agent === 'all' || p.name === agent)) : peopleFrom(calls, report.people);
    // the line to compare against: everyone in the same department (and channel) scope, all agents
    const storeDone = report.calls.filter(c => c.status === 'completed' && inDept(c.department) && inCh(c));
    const storeAvg = avg(storeDone.map(c => c.score_pct));
    const myAvg = avg(done.map(c => c.score_pct));
    const critGroups: { key: string; title: string; rows: Criterion[]; shops: number }[] = [];
    const themeGroups: { key: string; title: string; rows: Theme[] }[] = [];
    if (!filtered) {
      for (const [d, x] of Object.entries(report.by_department)) {
        if (x.criteria?.length) critGroups.push({ key: d, title: tr('rep.misses', { who: labelOf(d).toUpperCase() }), rows: x.criteria, shops: x.completed });
        if (x.coaching_themes?.length) themeGroups.push({ key: d, title: tr('rep.themes_dept', { who: labelOf(d).toUpperCase() }), rows: x.coaching_themes });
      }
      if (!critGroups.length && report.criteria.length) critGroups.push({ key: 'all', title: tr('rep.misses_team'), rows: report.criteria, shops: report.summary.completed });
      if (!themeGroups.length && report.coaching_themes.length) themeGroups.push({ key: 'all', title: tr('rep.themes'), rows: report.coaching_themes });
    } else {
      const who = agent !== 'all' ? agent.toUpperCase() : dept !== 'all' ? labelOf(dept).toUpperCase() : tr(`rep.${channel}s` as any).toUpperCase();
      const rows = criteriaFrom(done, labelOf);
      const depts = [...new Set(rows.map(r => r.department))];
      for (const d of depts) {
        const dr = rows.filter(r => r.department === d);
        const n = done.filter(c => (c.department || 'sales') === d).length;
        critGroups.push({ key: d, title: `${tr('rep.misses', { who })}${depts.length > 1 ? ` · ${labelOf(d).toUpperCase()}` : ''}`, rows: dr, shops: n });
      }
      const th = themesFrom(done);
      if (th.length) themeGroups.push({ key: 'filtered', title: agent !== 'all' ? tr('rep.coach_who', { who }) : tr('rep.themes_dept', { who }), rows: th });
    }
    return { calls, done, people, storeAvg, myAvg, critGroups, themeGroups, needsTraining: people.filter(p => p.needs_training).length, peopleShopped: new Set(people.filter(p => p.completed).map(p => p.target_id || p.name)).size };
  }, [report, dept, agent, channel, lang]);

  const deptItems = [{ key: 'all', label: tr('rep.all_depts') }, ...Object.entries(report.by_department).filter(([, x]) => x.completed || x.scheduled || x.planned || x.unreachable).map(([d, x]) => ({ key: d, label: labelOf(d), count: x.completed }))];
  const agentItems = [{ key: 'all', label: tr('rep.everyone') }, ...[...new Set(report.people.filter(p => dept === 'all' || p.department === dept).map(p => p.name))].sort().map(n => ({ key: n, label: n, count: report.calls.filter(c => c.target_name === n && c.status === 'completed' && (dept === 'all' || (c.department || 'sales') === dept)).length }))];
  // one bucket per channel that actually ran this month: count, average and (for threads) first-reply speed
  const mix = CH_KEYS.map(k => { const rows = report.calls.filter(c => channelKey(c) === k && (dept === 'all' || (c.department || 'sales') === dept)); const done = rows.filter(c => c.status === 'completed'); return { key: k, label: tr(`rep.${k}s` as any), total: rows.length, done: done.length, avg: avg(done.map(c => c.score_pct)), noReply: done.filter(c => c.text?.first_reply_s == null && k !== 'call').length, firstReply: avg(done.map(c => c.text?.first_reply_s).filter((x: any) => typeof x === 'number')) }; }).filter(m => m.total > 0);
  const chItems = [{ key: 'all', label: tr('rep.all_channels') }, ...mix.map(m => ({ key: m.key, label: m.label, count: m.done }))];
  const s = report.summary;
  const depScope = Object.entries(report.by_department).filter(([d]) => dept === 'all' || d === dept).map(([, x]) => x);
  const planned = channel === 'all' ? (dept === 'all' ? s.planned : report.by_department[dept]?.planned || 0) : depScope.reduce((n, x) => n + (channel === 'call' ? x.planned_calls || 0 : channel === 'text' ? x.planned_texts || 0 : 0), 0);
  const delta = v.myAvg != null && v.storeAvg != null ? v.myAvg - v.storeAvg : null;
  const shopsN = (n: number) => (n === 1 ? tr('rep.shops_1') : tr('rep.shops_n', { n }));
  const critN = (n: number) => (n === 1 ? tr('rep.crit_1') : tr('rep.crit_n', { n }));
  const storeWord = dept === 'all' ? tr('rep.store') : labelOf(dept);

  return (
    <View style={{ gap: 18 }} {...tid('shop-report')}>
      {(deptItems.length > 2 || agentItems.length > 2 || mix.length > 1) && (
        <View style={{ gap: 8 }} {...tid('report-filters')}>
          {mix.length > 1 && <ChipRow items={chItems} value={channel} onChange={k => setChannel(k as any)} colors={colors} testPrefix="report-filter-channel" />}
          {deptItems.length > 2 && <ChipRow items={deptItems} value={dept} onChange={k => { setDept(k); if (k !== 'all' && agent !== 'all' && !report.people.some(p => p.name === agent && p.department === k)) setAgent('all'); }} colors={colors} testPrefix="report-filter-dept" />}
          {agentItems.length > 2 && <ChipRow items={agentItems} value={agent} onChange={setAgent} colors={colors} testPrefix="report-filter-agent" />}
          {filtered && (
            <TouchableOpacity onPress={() => { setDept('all'); setAgent('all'); setChannel('all'); }} style={{ alignSelf: 'flex-start', flexDirection: 'row', alignItems: 'center', gap: 4 }} {...tid('report-filter-clear')}>
              <Ionicons name="close-circle" size={14} color={GOLD} />
              <Text style={{ fontSize: 12.5, fontWeight: '800', color: GOLD }}>{tr('rep.show_all')}</Text>
            </TouchableOpacity>
          )}
        </View>
      )}

      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 10 }}>
        <Stat label={tr('rep.completed')} value={planned && agent === 'all' ? tr('rep.of', { a: filtered ? v.done.length : s.completed, b: planned }) : String(filtered ? v.done.length : s.completed)} colors={colors} testID="report-stat-completed" />
        <Stat label={agent !== 'all' ? tr('rep.avg_of', { name: agent }) : tr('rep.avg')} value={(filtered ? v.myAvg : s.avg_score) != null ? `${filtered ? v.myAvg : s.avg_score}%` : '–'} colors={colors} tone={scoreColor(filtered ? v.myAvg : s.avg_score)} testID="report-stat-avg" />
        {agent !== 'all' ? (
          <Stat label={tr('rep.store_avg', { who: lang === 'nl' ? storeWord.toLowerCase() : storeWord })} value={v.storeAvg != null ? `${v.storeAvg}%${delta != null ? `  ${delta >= 0 ? '+' : ''}${delta}` : ''}` : '–'} colors={colors} tone={delta == null ? undefined : delta >= 0 ? GREEN : RED} testID="report-stat-store" />
        ) : (
          <Stat label={tr('rep.people')} value={String(filtered ? v.peopleShopped : s.people_shopped)} colors={colors} testID="report-stat-people" />
        )}
        <Stat label={tr('rep.need')} value={String(filtered ? v.needsTraining : s.needs_training)} colors={colors} tone={(filtered ? v.needsTraining : s.needs_training) ? RED : GREEN} testID="report-stat-training" />
        {!!s.text_shops && !filtered && <Stat label={tr('rep.text_reply')} value={`${s.avg_first_reply_s != null ? replyDur(s.avg_first_reply_s, lang) : '–'}${s.text_no_reply ? ` · ${tr('rep.text_noreply', { n: s.text_no_reply })}` : ''}`} colors={colors} tone={s.avg_first_reply_s == null ? undefined : s.avg_first_reply_s <= 300 ? GREEN : s.text_no_reply ? RED : GOLD} testID="report-stat-text" />}
        {!!s.email_shops && !filtered && <Stat label={tr('rep.email_reply')} value={`${s.avg_first_email_reply_s != null ? replyDur(s.avg_first_email_reply_s, lang) : '–'}${s.email_no_reply ? ` · ${tr('rep.text_noreply', { n: s.email_no_reply })}` : ''}`} colors={colors} tone={s.avg_first_email_reply_s == null ? undefined : s.avg_first_email_reply_s <= 1800 ? GREEN : s.email_no_reply ? RED : GOLD} testID="report-stat-email" />}
      </View>
      {mix.length > 1 && agent === 'all' && (
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginTop: -6 }} {...tid('report-channel-mix')}>
          {mix.map(m => {
            const on = channel === m.key;
            return (
              <TouchableOpacity key={m.key} onPress={() => setChannel(on ? 'all' : m.key)} style={{ flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 10, paddingVertical: 6, borderRadius: 12, backgroundColor: on ? GOLD + '22' : colors.card, borderWidth: 1, borderColor: on ? GOLD : colors.border }} {...tid(`report-mix-${m.key}`)}>
                <Ionicons name={channelIcon({ channel: m.key })} size={13} color={GOLD} />
                <Text style={{ fontSize: 12.5, fontWeight: '800', color: colors.text }}>{m.label} {m.done}</Text>
                <Text style={{ fontSize: 12.5, fontWeight: '800', color: scoreColor(m.avg) }}>{m.avg != null ? `${m.avg}%` : tr('rep.ch_none')}</Text>
                {m.key !== 'call' && m.done > 0 && <Text style={{ fontSize: 11.5, color: m.noReply ? RED : colors.textSecondary }}>· {m.firstReply != null ? tr('tx.first', { d: replyDur(m.firstReply, lang) }) : tr('tx.noreply')}{m.noReply ? ` · ${tr('rep.text_noreply', { n: m.noReply })}` : ''}</Text>}
              </TouchableOpacity>
            );
          })}
        </View>
      )}
      {agent !== 'all' && delta != null && (
        <Text style={{ fontSize: 13, fontWeight: '700', color: delta >= 0 ? GREEN : RED, marginTop: -8 }} {...tid('report-compare-line')}>
          <Ionicons name={delta >= 0 ? 'trending-up' : 'trending-down'} size={13} color={delta >= 0 ? GREEN : RED} /> {tr('rep.compare', { name: agent, n: Math.abs(delta), s: Math.abs(delta) === 1 ? '' : lang === 'nl' ? 'en' : 's', dir: delta >= 0 ? tr('rep.above') : tr('rep.below'), who: storeWord.toLowerCase(), exact: delta === 0 ? tr('rep.exact') : '' })}
        </Text>
      )}

      {dept === 'all' && agent === 'all' && channel === 'all' && (
        <View style={{ flexDirection: 'row', gap: 10, flexWrap: 'wrap' }}>
          {Object.entries(report.by_department).map(([d, x]) => (
            <TouchableOpacity key={d} onPress={() => setDept(d)} style={{ flex: 1, minWidth: 150, backgroundColor: colors.card, borderRadius: 14, padding: 12, borderWidth: 1, borderColor: colors.border, gap: 4 }} {...tid(`report-dept-${d}`)}>
              <Text style={{ fontSize: 12, fontWeight: '800', color: GOLD }}>{labelOf(d).toUpperCase()}</Text>
              <Text style={{ fontSize: 14, color: colors.text }}>{x.planned ? tr('rep.of', { a: x.completed, b: x.planned }) : tr('rep.done', { n: x.completed })}{x.scheduled ? ` · ${tr('rep.coming', { n: x.scheduled })}` : ''}{x.unreachable ? ` · ${tr('rep.unreachable_n', { n: x.unreachable })}` : ''}</Text>
              <Text style={{ fontSize: 13, fontWeight: '700', color: scoreColor(x.avg_score) }}>{x.avg_score != null ? tr('rep.avg_short', { v: x.avg_score }) : tr('rep.no_scores')}</Text>
            </TouchableOpacity>
          ))}
        </View>
      )}

      {agent === 'all' && channel === 'all' && Object.entries(report.by_department).filter(([d, x]) => (dept === 'all' || d === dept) && x.leaderboard?.length).map(([d, x]) => (
        <Leaderboard key={d} dept={d} label={labelOf(d)} rows={x.leaderboard!} prevLabel={report.prev_month_label} colors={colors} lang={lang} onPerson={personPath ? (id, name) => setPerson({ id, name }) : undefined} />
      ))}

      <View style={{ gap: 8 }}>
        <Label t={agent !== 'all' ? tr('rep.this_month', { name: agent.toUpperCase() }) : tr('rep.who')} colors={colors} />
        {v.people.length === 0 && <Text style={{ fontSize: 13.5, color: colors.textSecondary }}>{filtered ? tr('rep.no_match') : tr('rep.nobody')}</Text>}
        {v.people.map((p, i) => {
          const line = avg(report.calls.filter(c => c.status === 'completed' && (c.department || 'sales') === p.department).map(c => c.score_pct));
          const d = p.avg_score != null && line != null ? p.avg_score - line : null;
          return (
            <TouchableOpacity key={p.key || i} disabled={!personPath || !p.target_id} onPress={() => p.target_id && setPerson({ id: p.target_id, name: p.name })} style={{ backgroundColor: colors.card, borderRadius: 14, borderWidth: 1, borderColor: p.needs_training ? RED + '88' : colors.border, padding: 12, gap: 6 }} {...tid(`report-person-${i}`)}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
                <View style={{ flex: 1 }}>
                  <Text style={{ fontSize: 15, fontWeight: '800', color: colors.text }}>{p.name} <Text style={{ fontSize: 12, fontWeight: '600', color: colors.textSecondary }}>· {labelOf(p.department)}{p.title ? ` · ${p.title}` : ''}</Text>{!!personPath && !!p.target_id && <Text style={{ fontSize: 12, color: GOLD }}>  <Ionicons name="chevron-forward" size={11} color={GOLD} /> {tr('rep.history')}</Text>}</Text>
                  <Text style={{ fontSize: 12.5, color: colors.textSecondary }}>{shopsN(p.completed)}{p.unreachable ? `, ${tr('rep.unreachable_n', { n: p.unreachable })}` : ''}{p.best != null ? ` · ${tr('rep.best', { v: p.best })}` : ''}{p.critical_misses ? ` · ${critN(p.critical_misses)}` : ''}</Text>
                </View>
                <View style={{ alignItems: 'flex-end', gap: 2 }}>
                  <Text style={{ fontSize: 22, fontWeight: '800', color: scoreColor(p.avg_score) }}>{p.avg_score != null ? `${p.avg_score}%` : '–'}</Text>
                  {d != null && d !== 0 ? <Text style={{ fontSize: 10.5, fontWeight: '800', color: d > 0 ? GREEN : RED }} {...tid(`report-person-${i}-vs`)}>{tr('rep.vs_dept', { d: `${d > 0 ? '+' : ''}${d}`, dept: labelOf(p.department).toUpperCase() })}</Text>
                    : <Text style={{ fontSize: 10.5, fontWeight: '800', color: p.needs_training ? RED : p.completed ? GREEN : colors.textSecondary }}>{p.needs_training ? tr('rep.needs_training') : p.completed ? (d === 0 ? tr('rep.on_line') : tr('rep.on_track')) : p.unreachable ? tr('rep.unreachable') : tr('rep.scheduled')}</Text>}
                </View>
              </View>
              {p.coaching.length > 0 && <Text style={{ fontSize: 12.5, color: colors.textSecondary, lineHeight: 17 }} numberOfLines={compact ? 2 : 4}>{tr('rep.coach_on', { items: p.coaching.join(' · ') })}</Text>}
            </TouchableOpacity>
          );
        })}
      </View>

      {v.critGroups.map(sec => (
        <View key={sec.key} style={{ gap: 8 }} {...tid(`report-misses-${sec.key}`)}>
          <Label t={`${sec.title}${sec.shops ? ` · ${shopsN(sec.shops).toUpperCase()}` : ''}`} colors={colors} />
          {sec.rows.slice(0, compact ? 6 : 12).map((c, i) => (
            <View key={i} style={{ gap: 4 }} {...tid(`report-criterion-${sec.key}-${i}`)}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                <Text style={{ flex: 1, fontSize: 13, color: colors.text }}>{c.text}{c.critical ? tr('rep.critical') : ''}</Text>
                <Text style={{ fontSize: 11.5, color: colors.textSecondary }}>{tr('rep.x_of_y', { a: c.passed, b: c.total })}</Text>
                <Text style={{ fontSize: 13, fontWeight: '800', color: c.pass_pct < 60 ? RED : c.pass_pct < 85 ? AMBER : GREEN }}>{c.pass_pct}%</Text>
              </View>
              <Bar pct={c.pass_pct} color={c.pass_pct < 60 ? RED : c.pass_pct < 85 ? AMBER : GREEN} colors={colors} />
            </View>
          ))}
        </View>
      ))}

      {v.themeGroups.map(sec => (
        <View key={sec.key} style={{ gap: 6 }} {...tid(`report-themes-${sec.key}`)}>
          <Label t={sec.title} colors={colors} />
          {sec.rows.map((t, i) => <Text key={i} style={{ fontSize: 13.5, color: colors.text, lineHeight: 19 }}>• {t.text}{t.count > 1 ? ` (x${t.count})` : ''}</Text>)}
        </View>
      ))}

      <View style={{ gap: 8 }}>
        <Label t={`${filtered ? tr('rep.matching') : tr('rep.every')} · ${tr('rep.completed_n', { n: v.done.length })}`} colors={colors} />
        {v.calls.filter(c => c.status !== 'scheduled' || !compact).map((c, i) => (
          <TouchableOpacity key={c.id || i} onPress={() => setOpen(c)} style={{ backgroundColor: colors.card, borderRadius: 14, borderWidth: 1, borderColor: colors.border, padding: 12, gap: 4 }} {...tid(`report-call-${i}`)}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
              <View style={{ flex: 1 }}>
                <Text style={{ fontSize: 14.5, fontWeight: '800', color: colors.text }}><Ionicons name={channelIcon(c)} size={12} color={GOLD} /> {c.target_name} <Text style={{ fontSize: 12, fontWeight: '600', color: colors.textSecondary }}>· {channelLabel(c, lang)} · {labelOf(c.department || 'sales')}</Text></Text>
                <Text style={{ fontSize: 12.5, color: colors.textSecondary }} numberOfLines={1}>{c.script_title} · {fmtWhenL(c.ended_at || c.scheduled_for, lang)}</Text>
              </View>
              {c.status === 'completed' ? <Text style={{ fontSize: 18, fontWeight: '800', color: scoreColor(c.score_pct) }}>{c.score_pct != null ? `${c.score_pct}%` : '–'}</Text> : <StatusChip status={c.status} colors={colors} lang={lang} channel={c.channel} />}
            </View>
            {!!c.summary && <Text style={{ fontSize: 12.5, color: colors.textSecondary, lineHeight: 17 }} numberOfLines={2}>{c.summary}</Text>}
            {!!c.recording_url && <Text style={{ fontSize: 11.5, fontWeight: '700', color: GOLD }}><Ionicons name="play" size={10} color={GOLD} /> {tr('rep.inside')}</Text>}
            {(c.channel === 'text' || c.channel === 'email') && c.status === 'completed' && <Text style={{ fontSize: 11.5, fontWeight: '700', color: c.text?.first_reply_s == null ? RED : c.text.first_reply_s <= (c.channel === 'email' ? 1800 : 300) ? GREEN : GOLD }}>{c.text?.first_reply_s == null ? tr('tx.noreply') : tr('tx.first', { d: replyDur(c.text.first_reply_s, lang) })}<Text style={{ color: GOLD }}> · {tr('rep.thread_inside')}</Text></Text>}
          </TouchableOpacity>
        ))}
      </View>
      <CallDetailSheet id={open?.id || null} onClose={() => setOpen(null)} colors={colors} lang={lang} publicData={open ? { ...open, evaluation: open.results?.length || open.summary ? { summary: open.summary, critical_misses: open.critical_misses, coaching: open.coaching, wins: open.wins, results: open.results, scorecard_name: undefined } : null } : undefined} />
      {!!personPath && <PersonDetailSheet targetId={person?.id || null} name={person?.name} path={personPath} onClose={() => setPerson(null)} colors={colors} lang={lang} />}
    </View>
  );
};

export const openUrl = (url: string) => (Platform.OS === 'web' ? window.open(url, '_blank') : Linking.openURL(url));
