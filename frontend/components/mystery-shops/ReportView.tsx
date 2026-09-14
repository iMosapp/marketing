import React, { useMemo, useState } from 'react';
import { View, Text, TouchableOpacity, Platform, Linking, ScrollView } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { CallDetailSheet } from './CallsTab';
import { PersonDetailSheet } from './PersonDetailSheet';
import { Label, Stat, Bar, StatusChip, deptLabel, fmtWhen, scoreColor, GOLD, RED, GREEN, AMBER, tid } from './shared';

export type Criterion = { text: string; critical: boolean; passed: number; total: number; pass_pct: number; department: string; department_label?: string };
type Theme = { text: string; count: number };
export type LeaderRow = { rank: number; key: string; target_id: string; name: string; title?: string; avg_score: number; completed: number; best: number | null; critical_misses: number; prev_avg: number | null; delta: number | null; badges: { key: string; label: string; detail: string }[] };
const MEDAL = ['#C9A962', '#A8A9AD', '#CD7F32'];

export type Report = {
  client: { id: string; name: string; brand: string; city: string; state: string; contact_name: string }; month: string; month_label: string; prev_month_label?: string; generated_at: string;
  summary: { completed: number; planned: number; scheduled: number; unreachable: number; avg_score: number | null; avg_adherence: number | null; people_shopped: number; needs_training: number };
  by_department: Record<string, { label?: string; planned: number; scheduled: number; completed: number; unreachable: number; avg_score: number | null; people?: number; criteria?: Criterion[]; coaching_themes?: Theme[]; leaderboard?: LeaderRow[] }>;
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

// Ranked rows for one department: medals for the top three, badges for top score / most improved / most shops. Tap a name for their history.
const Leaderboard = ({ dept, label, rows, prevLabel, colors, onPerson }: { dept: string; label: string; rows: LeaderRow[]; prevLabel?: string; colors: any; onPerson?: (id: string, name: string) => void }) => (
  <View style={{ gap: 8 }} {...tid(`report-leaderboard-${dept}`)}>
    <Label t={`${label.toUpperCase()} LEADERBOARD`} colors={colors} />
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
              {r.completed} shop{r.completed === 1 ? '' : 's'}{r.best != null ? ` · best ${r.best}%` : ''} · {r.delta != null ? <Text style={{ fontWeight: '800', color: r.delta > 0 ? GREEN : r.delta < 0 ? RED : colors.textSecondary }}>{r.delta > 0 ? '+' : ''}{r.delta} vs {prevLabel || 'last month'}</Text> : <Text>new this month</Text>}
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

// One report body for the admin tab and the client's no-login page. personPath decides which endpoint the tap-a-name sheet uses.
export const ReportView = ({ report, colors, compact, personPath }: { report: Report; colors: any; compact?: boolean; personPath?: (targetId: string) => string }) => {
  const [open, setOpen] = useState<any>(null);
  const [person, setPerson] = useState<{ id: string; name: string } | null>(null);
  const [dept, setDept] = useState('all');
  const [agent, setAgent] = useState('all');
  const labelOf = (d: string) => report.by_department[d]?.label || deptLabel(d);
  const filtered = !!(dept !== 'all' || agent !== 'all');

  const v = useMemo(() => {
    const inDept = (d?: string) => dept === 'all' || (d || 'sales') === dept;
    const calls = report.calls.filter(c => inDept(c.department) && (agent === 'all' || c.target_name === agent));
    const done = calls.filter(c => c.status === 'completed');
    const people = report.people.filter(p => inDept(p.department) && (agent === 'all' || p.name === agent));
    // the line to compare against: everyone in the same department scope, all agents
    const storeDone = report.calls.filter(c => c.status === 'completed' && inDept(c.department));
    const storeAvg = avg(storeDone.map(c => c.score_pct));
    const myAvg = avg(done.map(c => c.score_pct));
    const critGroups: { key: string; title: string; rows: Criterion[]; shops: number }[] = [];
    const themeGroups: { key: string; title: string; rows: Theme[] }[] = [];
    if (!filtered) {
      for (const [d, x] of Object.entries(report.by_department)) {
        if (x.criteria?.length) critGroups.push({ key: d, title: `WHAT ${labelOf(d).toUpperCase()} MISSES MOST`, rows: x.criteria, shops: x.completed });
        if (x.coaching_themes?.length) themeGroups.push({ key: d, title: `COACHING THEMES FOR THE NEXT ${labelOf(d).toUpperCase()} MEETING`, rows: x.coaching_themes });
      }
      if (!critGroups.length && report.criteria.length) critGroups.push({ key: 'all', title: 'WHAT THE WHOLE TEAM MISSES MOST', rows: report.criteria, shops: report.summary.completed });
      if (!themeGroups.length && report.coaching_themes.length) themeGroups.push({ key: 'all', title: 'COACHING THEMES FOR THE NEXT MEETING', rows: report.coaching_themes });
    } else {
      const who = agent !== 'all' ? agent.toUpperCase() : labelOf(dept).toUpperCase();
      const rows = criteriaFrom(done, labelOf);
      const depts = [...new Set(rows.map(r => r.department))];
      for (const d of depts) {
        const dr = rows.filter(r => r.department === d);
        const n = done.filter(c => (c.department || 'sales') === d).length;
        critGroups.push({ key: d, title: `WHAT ${who} MISSES MOST${depts.length > 1 ? ` · ${labelOf(d).toUpperCase()}` : ''}`, rows: dr, shops: n });
      }
      const th = themesFrom(done);
      if (th.length) themeGroups.push({ key: 'filtered', title: agent !== 'all' ? `COACH ${who} ON` : `COACHING THEMES FOR THE NEXT ${who} MEETING`, rows: th });
    }
    return { calls, done, people, storeAvg, myAvg, critGroups, themeGroups, needsTraining: people.filter(p => p.needs_training).length, peopleShopped: new Set(people.filter(p => p.completed).map(p => p.target_id || p.name)).size };
  }, [report, dept, agent]);

  const deptItems = [{ key: 'all', label: 'All departments' }, ...Object.entries(report.by_department).filter(([, x]) => x.completed || x.scheduled || x.planned || x.unreachable).map(([d, x]) => ({ key: d, label: labelOf(d), count: x.completed }))];
  const agentItems = [{ key: 'all', label: 'Everyone' }, ...[...new Set(report.people.filter(p => dept === 'all' || p.department === dept).map(p => p.name))].sort().map(n => ({ key: n, label: n, count: report.calls.filter(c => c.target_name === n && c.status === 'completed' && (dept === 'all' || (c.department || 'sales') === dept)).length }))];
  const s = report.summary;
  const planned = dept === 'all' ? s.planned : report.by_department[dept]?.planned || 0;
  const delta = v.myAvg != null && v.storeAvg != null ? v.myAvg - v.storeAvg : null;

  return (
    <View style={{ gap: 18 }} {...tid('shop-report')}>
      {(deptItems.length > 2 || agentItems.length > 2) && (
        <View style={{ gap: 8 }} {...tid('report-filters')}>
          {deptItems.length > 2 && <ChipRow items={deptItems} value={dept} onChange={k => { setDept(k); if (k !== 'all' && agent !== 'all' && !report.people.some(p => p.name === agent && p.department === k)) setAgent('all'); }} colors={colors} testPrefix="report-filter-dept" />}
          {agentItems.length > 2 && <ChipRow items={agentItems} value={agent} onChange={setAgent} colors={colors} testPrefix="report-filter-agent" />}
          {filtered && (
            <TouchableOpacity onPress={() => { setDept('all'); setAgent('all'); }} style={{ alignSelf: 'flex-start', flexDirection: 'row', alignItems: 'center', gap: 4 }} {...tid('report-filter-clear')}>
              <Ionicons name="close-circle" size={14} color={GOLD} />
              <Text style={{ fontSize: 12.5, fontWeight: '800', color: GOLD }}>Show everything</Text>
            </TouchableOpacity>
          )}
        </View>
      )}

      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 10 }}>
        <Stat label="Shops completed" value={`${filtered ? v.done.length : s.completed}${planned && agent === 'all' ? ` of ${planned}` : ''}`} colors={colors} testID="report-stat-completed" />
        <Stat label={agent !== 'all' ? `${agent}'s average` : 'Average score'} value={(filtered ? v.myAvg : s.avg_score) != null ? `${filtered ? v.myAvg : s.avg_score}%` : '–'} colors={colors} tone={scoreColor(filtered ? v.myAvg : s.avg_score)} testID="report-stat-avg" />
        {agent !== 'all' ? (
          <Stat label={`${dept === 'all' ? 'Store' : labelOf(dept)} average`} value={v.storeAvg != null ? `${v.storeAvg}%${delta != null ? `  ${delta >= 0 ? '+' : ''}${delta}` : ''}` : '–'} colors={colors} tone={delta == null ? undefined : delta >= 0 ? GREEN : RED} testID="report-stat-store" />
        ) : (
          <Stat label="People shopped" value={String(filtered ? v.peopleShopped : s.people_shopped)} colors={colors} testID="report-stat-people" />
        )}
        <Stat label="Need training" value={String(filtered ? v.needsTraining : s.needs_training)} colors={colors} tone={(filtered ? v.needsTraining : s.needs_training) ? RED : GREEN} testID="report-stat-training" />
      </View>
      {agent !== 'all' && delta != null && (
        <Text style={{ fontSize: 13, fontWeight: '700', color: delta >= 0 ? GREEN : RED, marginTop: -8 }} {...tid('report-compare-line')}>
          <Ionicons name={delta >= 0 ? 'trending-up' : 'trending-down'} size={13} color={delta >= 0 ? GREEN : RED} /> {agent} is {Math.abs(delta)} point{Math.abs(delta) === 1 ? '' : 's'} {delta >= 0 ? 'above' : 'below'} the {dept === 'all' ? 'store' : labelOf(dept).toLowerCase()} line{delta === 0 ? ' (right on it)' : ''}
        </Text>
      )}

      {dept === 'all' && agent === 'all' && (
        <View style={{ flexDirection: 'row', gap: 10, flexWrap: 'wrap' }}>
          {Object.entries(report.by_department).map(([d, x]) => (
            <TouchableOpacity key={d} onPress={() => setDept(d)} style={{ flex: 1, minWidth: 150, backgroundColor: colors.card, borderRadius: 14, padding: 12, borderWidth: 1, borderColor: colors.border, gap: 4 }} {...tid(`report-dept-${d}`)}>
              <Text style={{ fontSize: 12, fontWeight: '800', color: GOLD }}>{labelOf(d).toUpperCase()}</Text>
              <Text style={{ fontSize: 14, color: colors.text }}>{x.completed} done{x.planned ? ` of ${x.planned}` : ''}{x.scheduled ? ` · ${x.scheduled} coming` : ''}{x.unreachable ? ` · ${x.unreachable} unreachable` : ''}</Text>
              <Text style={{ fontSize: 13, fontWeight: '700', color: scoreColor(x.avg_score) }}>{x.avg_score != null ? `Avg ${x.avg_score}%` : 'No scores yet'}</Text>
            </TouchableOpacity>
          ))}
        </View>
      )}

      {agent === 'all' && Object.entries(report.by_department).filter(([d, x]) => (dept === 'all' || d === dept) && x.leaderboard?.length).map(([d, x]) => (
        <Leaderboard key={d} dept={d} label={labelOf(d)} rows={x.leaderboard!} prevLabel={report.prev_month_label} colors={colors} onPerson={personPath ? (id, name) => setPerson({ id, name }) : undefined} />
      ))}

      <View style={{ gap: 8 }}>
        <Label t={agent !== 'all' ? `${agent.toUpperCase()} THIS MONTH` : 'WHO DID WELL, WHO NEEDS ANOTHER LOOK'} colors={colors} />
        {v.people.length === 0 && <Text style={{ fontSize: 13.5, color: colors.textSecondary }}>{filtered ? 'No shops match this filter.' : 'No one has been shopped this month yet.'}</Text>}
        {v.people.map((p, i) => {
          const line = avg(report.calls.filter(c => c.status === 'completed' && (c.department || 'sales') === p.department).map(c => c.score_pct));
          const d = p.avg_score != null && line != null ? p.avg_score - line : null;
          return (
            <TouchableOpacity key={p.key || i} disabled={!personPath || !p.target_id} onPress={() => p.target_id && setPerson({ id: p.target_id, name: p.name })} style={{ backgroundColor: colors.card, borderRadius: 14, borderWidth: 1, borderColor: p.needs_training ? RED + '88' : colors.border, padding: 12, gap: 6 }} {...tid(`report-person-${i}`)}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
                <View style={{ flex: 1 }}>
                  <Text style={{ fontSize: 15, fontWeight: '800', color: colors.text }}>{p.name} <Text style={{ fontSize: 12, fontWeight: '600', color: colors.textSecondary }}>· {labelOf(p.department)}{p.title ? ` · ${p.title}` : ''}</Text>{!!personPath && !!p.target_id && <Text style={{ fontSize: 12, color: GOLD }}>  <Ionicons name="chevron-forward" size={11} color={GOLD} /> history</Text>}</Text>
                  <Text style={{ fontSize: 12.5, color: colors.textSecondary }}>{p.completed} shop{p.completed === 1 ? '' : 's'}{p.unreachable ? `, ${p.unreachable} unreachable` : ''}{p.best != null ? ` · best ${p.best}%` : ''}{p.critical_misses ? ` · ${p.critical_misses} critical miss${p.critical_misses === 1 ? '' : 'es'}` : ''}</Text>
                </View>
                <View style={{ alignItems: 'flex-end', gap: 2 }}>
                  <Text style={{ fontSize: 22, fontWeight: '800', color: scoreColor(p.avg_score) }}>{p.avg_score != null ? `${p.avg_score}%` : '–'}</Text>
                  {d != null && d !== 0 ? <Text style={{ fontSize: 10.5, fontWeight: '800', color: d > 0 ? GREEN : RED }} {...tid(`report-person-${i}-vs`)}>{d > 0 ? '+' : ''}{d} VS {labelOf(p.department).toUpperCase()}</Text>
                    : <Text style={{ fontSize: 10.5, fontWeight: '800', color: p.needs_training ? RED : p.completed ? GREEN : colors.textSecondary }}>{p.needs_training ? 'NEEDS TRAINING' : p.completed ? (d === 0 ? 'ON THE LINE' : 'ON TRACK') : p.unreachable ? 'UNREACHABLE' : 'SCHEDULED'}</Text>}
                </View>
              </View>
              {p.coaching.length > 0 && <Text style={{ fontSize: 12.5, color: colors.textSecondary, lineHeight: 17 }} numberOfLines={compact ? 2 : 4}>Coach on: {p.coaching.join(' · ')}</Text>}
            </TouchableOpacity>
          );
        })}
      </View>

      {v.critGroups.map(sec => (
        <View key={sec.key} style={{ gap: 8 }} {...tid(`report-misses-${sec.key}`)}>
          <Label t={`${sec.title}${sec.shops ? ` · ${sec.shops} SHOP${sec.shops === 1 ? '' : 'S'}` : ''}`} colors={colors} />
          {sec.rows.slice(0, compact ? 6 : 12).map((c, i) => (
            <View key={i} style={{ gap: 4 }} {...tid(`report-criterion-${sec.key}-${i}`)}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                <Text style={{ flex: 1, fontSize: 13, color: colors.text }}>{c.text}{c.critical ? ' (critical)' : ''}</Text>
                <Text style={{ fontSize: 11.5, color: colors.textSecondary }}>{c.passed} of {c.total}</Text>
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
        <Label t={`${filtered ? 'MATCHING SHOPS' : 'EVERY SHOP'} · ${v.done.length} COMPLETED`} colors={colors} />
        {v.calls.filter(c => c.status !== 'scheduled' || !compact).map((c, i) => (
          <TouchableOpacity key={c.id || i} onPress={() => setOpen(c)} style={{ backgroundColor: colors.card, borderRadius: 14, borderWidth: 1, borderColor: colors.border, padding: 12, gap: 4 }} {...tid(`report-call-${i}`)}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
              <View style={{ flex: 1 }}>
                <Text style={{ fontSize: 14.5, fontWeight: '800', color: colors.text }}>{c.target_name} <Text style={{ fontSize: 12, fontWeight: '600', color: colors.textSecondary }}>· {labelOf(c.department || 'sales')}</Text></Text>
                <Text style={{ fontSize: 12.5, color: colors.textSecondary }} numberOfLines={1}>{c.script_title} · {fmtWhen(c.ended_at || c.scheduled_for)}</Text>
              </View>
              {c.status === 'completed' ? <Text style={{ fontSize: 18, fontWeight: '800', color: scoreColor(c.score_pct) }}>{c.score_pct != null ? `${c.score_pct}%` : '–'}</Text> : <StatusChip status={c.status} colors={colors} />}
            </View>
            {!!c.summary && <Text style={{ fontSize: 12.5, color: colors.textSecondary, lineHeight: 17 }} numberOfLines={2}>{c.summary}</Text>}
            {!!c.recording_url && <Text style={{ fontSize: 11.5, fontWeight: '700', color: GOLD }}><Ionicons name="play" size={10} color={GOLD} /> Recording, transcript and coaching inside</Text>}
          </TouchableOpacity>
        ))}
      </View>
      <CallDetailSheet id={open?.id || null} onClose={() => setOpen(null)} colors={colors} publicData={open ? { ...open, evaluation: open.results?.length || open.summary ? { summary: open.summary, critical_misses: open.critical_misses, coaching: open.coaching, wins: open.wins, results: open.results, scorecard_name: undefined } : null } : undefined} />
      {!!personPath && <PersonDetailSheet targetId={person?.id || null} name={person?.name} path={personPath} onClose={() => setPerson(null)} colors={colors} />}
    </View>
  );
};

export const openUrl = (url: string) => (Platform.OS === 'web' ? window.open(url, '_blank') : Linking.openURL(url));
