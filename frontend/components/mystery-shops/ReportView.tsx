import React, { useState } from 'react';
import { View, Text, TouchableOpacity, Platform, Linking } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { CallDetailSheet } from './CallsTab';
import { Label, Stat, Bar, StatusChip, deptLabel, fmtWhen, scoreColor, GOLD, RED, GREEN, AMBER, tid } from './shared';

export type Criterion = { text: string; critical: boolean; passed: number; total: number; pass_pct: number; department: string; department_label?: string };

export type Report = {
  client: { id: string; name: string; brand: string; city: string; state: string; contact_name: string }; month: string; month_label: string; generated_at: string;
  summary: { completed: number; planned: number; scheduled: number; unreachable: number; avg_score: number | null; avg_adherence: number | null; people_shopped: number; needs_training: number };
  by_department: Record<string, { label?: string; planned: number; scheduled: number; completed: number; unreachable: number; avg_score: number | null; people?: number; criteria?: Criterion[] }>;
  people: { key?: string; target_id?: string; name: string; department: string; department_label?: string; title: string; shops: number; completed: number; unreachable: number; avg_score: number | null; avg_adherence: number | null; best: number | null; worst: number | null; critical_misses: number; needs_training: boolean; last_shop: string | null; coaching: string[] }[];
  criteria: Criterion[];
  coaching_themes: { text: string; count: number }[];
  calls: any[];
  report_url?: string;
};

// One report body for the admin tab and the client's no-login page.
export const ReportView = ({ report, colors, compact }: { report: Report; colors: any; compact?: boolean }) => {
  const [open, setOpen] = useState<any>(null);
  const s = report.summary;
  const done = report.calls.filter(c => c.status === 'completed');
  return (
    <View style={{ gap: 18 }} {...tid('shop-report')}>
      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 10 }}>
        <Stat label="Shops completed" value={`${s.completed}${s.planned ? ` of ${s.planned}` : ''}`} colors={colors} testID="report-stat-completed" />
        <Stat label="Average score" value={s.avg_score != null ? `${s.avg_score}%` : '–'} colors={colors} tone={scoreColor(s.avg_score)} testID="report-stat-avg" />
        <Stat label="People shopped" value={String(s.people_shopped)} colors={colors} testID="report-stat-people" />
        <Stat label="Need training" value={String(s.needs_training)} colors={colors} tone={s.needs_training ? RED : GREEN} testID="report-stat-training" />
      </View>
      <View style={{ flexDirection: 'row', gap: 10, flexWrap: 'wrap' }}>
        {Object.entries(report.by_department).map(([d, x]) => (
          <View key={d} style={{ flex: 1, minWidth: 150, backgroundColor: colors.card, borderRadius: 14, padding: 12, borderWidth: 1, borderColor: colors.border, gap: 4 }} {...tid(`report-dept-${d}`)}>
            <Text style={{ fontSize: 12, fontWeight: '800', color: GOLD }}>{(x.label || deptLabel(d)).toUpperCase()}</Text>
            <Text style={{ fontSize: 14, color: colors.text }}>{x.completed} done{x.planned ? ` of ${x.planned}` : ''}{x.scheduled ? ` · ${x.scheduled} coming` : ''}{x.unreachable ? ` · ${x.unreachable} unreachable` : ''}</Text>
            <Text style={{ fontSize: 13, fontWeight: '700', color: scoreColor(x.avg_score) }}>{x.avg_score != null ? `Avg ${x.avg_score}%` : 'No scores yet'}</Text>
          </View>
        ))}
      </View>

      <View style={{ gap: 8 }}>
        <Label t="WHO DID WELL, WHO NEEDS ANOTHER LOOK" colors={colors} />
        {report.people.length === 0 && <Text style={{ fontSize: 13.5, color: colors.textSecondary }}>No one has been shopped this month yet.</Text>}
        {report.people.map((p, i) => (
          <View key={p.key || i} style={{ backgroundColor: colors.card, borderRadius: 14, borderWidth: 1, borderColor: p.needs_training ? RED + '88' : colors.border, padding: 12, gap: 6 }} {...tid(`report-person-${i}`)}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
              <View style={{ flex: 1 }}>
                <Text style={{ fontSize: 15, fontWeight: '800', color: colors.text }}>{p.name} <Text style={{ fontSize: 12, fontWeight: '600', color: colors.textSecondary }}>· {report.by_department[p.department]?.label || deptLabel(p.department)}{p.title ? ` · ${p.title}` : ''}</Text></Text>
                <Text style={{ fontSize: 12.5, color: colors.textSecondary }}>{p.completed} shop{p.completed === 1 ? '' : 's'}{p.unreachable ? `, ${p.unreachable} unreachable` : ''}{p.best != null ? ` · best ${p.best}%` : ''}{p.critical_misses ? ` · ${p.critical_misses} critical miss${p.critical_misses === 1 ? '' : 'es'}` : ''}</Text>
              </View>
              <View style={{ alignItems: 'flex-end', gap: 2 }}>
                <Text style={{ fontSize: 22, fontWeight: '800', color: scoreColor(p.avg_score) }}>{p.avg_score != null ? `${p.avg_score}%` : '–'}</Text>
                <Text style={{ fontSize: 10.5, fontWeight: '800', color: p.needs_training ? RED : p.completed ? GREEN : colors.textSecondary }}>{p.needs_training ? 'NEEDS TRAINING' : p.completed ? 'ON TRACK' : p.unreachable ? 'UNREACHABLE' : 'SCHEDULED'}</Text>
              </View>
            </View>
            {p.coaching.length > 0 && <Text style={{ fontSize: 12.5, color: colors.textSecondary, lineHeight: 17 }} numberOfLines={compact ? 2 : 4}>Coach on: {p.coaching.join(' · ')}</Text>}
          </View>
        ))}
      </View>

      {report.criteria.length > 0 && (() => {
        const groups = Object.entries(report.by_department).filter(([, x]) => (x.criteria || []).length > 0);
        const sections = groups.length ? groups.map(([d, x]) => ({ key: d, title: `WHAT ${(x.label || deptLabel(d)).toUpperCase()} MISSES MOST${x.completed ? ` · ${x.completed} SHOP${x.completed === 1 ? '' : 'S'}` : ''}`, rows: x.criteria || [] }))
          : [{ key: 'all', title: 'WHAT THE WHOLE TEAM MISSES MOST', rows: report.criteria }];
        return sections.map(sec => (
          <View key={sec.key} style={{ gap: 8 }} {...tid(`report-misses-${sec.key}`)}>
            <Label t={sec.title} colors={colors} />
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
        ));
      })()}

      {report.coaching_themes.length > 0 && (
        <View style={{ gap: 6 }}>
          <Label t="COACHING THEMES FOR THE NEXT MEETING" colors={colors} />
          {report.coaching_themes.map((t, i) => <Text key={i} style={{ fontSize: 13.5, color: colors.text, lineHeight: 19 }}>• {t.text}</Text>)}
        </View>
      )}

      <View style={{ gap: 8 }}>
        <Label t={`EVERY SHOP · ${done.length} COMPLETED`} colors={colors} />
        {report.calls.filter(c => c.status !== 'scheduled' || !compact).map((c, i) => (
          <TouchableOpacity key={c.id || i} onPress={() => setOpen(c)} style={{ backgroundColor: colors.card, borderRadius: 14, borderWidth: 1, borderColor: colors.border, padding: 12, gap: 4 }} {...tid(`report-call-${i}`)}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
              <View style={{ flex: 1 }}>
                <Text style={{ fontSize: 14.5, fontWeight: '800', color: colors.text }}>{c.target_name}</Text>
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
    </View>
  );
};

export const openUrl = (url: string) => (Platform.OS === 'web' ? window.open(url, '_blank') : Linking.openURL(url));
