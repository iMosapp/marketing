import React, { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { Label, scoreColor, GOLD, GREEN, RED, tid } from './shared';
import { makeT, type Lang } from './i18n';

type Row = { rank: number; key: string; target_id: string; name: string; title?: string; avg_score: number; completed: number; best: number | null; critical_misses: number; prev_avg: number | null; delta: number | null; badges: { key: string; label: string; detail: string }[] };
type Board = { department: string; label: string; rows: Row[] };
export type WeekBoard = { week_start: string; label: string; offset: number; is_current: boolean; prev_label: string; completed: number; people: number; avg_score: number | null; prev_avg_score: number | null; boards: Board[]; movers: { target_id: string; name: string; delta: number; avg_score: number; department_label: string }[] };
const MEDAL = ['#C9A962', '#A8A9AD', '#CD7F32'];

// Who is climbing this week: one ranked list per department (average first, then volume), each row with its move since last week.
// Same card on the admin People tab and the GM's no-login report; path decides the endpoint, refreshKey re-pulls after a shop finishes.
export const WeeklyLeaderboard = ({ path, colors, onPerson, lang = 'en', refreshKey }: { path: (offset: number) => string; colors: any; onPerson?: (id: string, name: string) => void; lang?: Lang; refreshKey?: string | number }) => {
  const tr = makeT(lang);
  const [offset, setOffset] = useState(0);
  const [d, setD] = useState<WeekBoard | null>(null);
  const [err, setErr] = useState(false);
  useEffect(() => { setErr(false); api.get(path(offset)).then(r => setD(r.data)).catch(() => setErr(true)); }, [offset, refreshKey]);
  const delta = d && d.avg_score != null && d.prev_avg_score != null ? d.avg_score - d.prev_avg_score : null;
  return (
    <View style={{ backgroundColor: colors.card, borderRadius: 16, borderWidth: 1, borderColor: GOLD + '66', padding: 14, gap: 12 }} {...tid('weekly-leaderboard')}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
        <Ionicons name="trophy" size={18} color={GOLD} />
        <View style={{ flex: 1 }}>
          <Label t={tr('lb.title')} colors={colors} />
          <Text style={{ fontSize: 14, fontWeight: '800', color: colors.text, marginTop: 2 }} {...tid('weekly-leaderboard-week')}>{d ? (d.is_current ? `${tr('lb.this_week')} · ${d.label}` : d.label) : ' '}</Text>
        </View>
        <TouchableOpacity onPress={() => setOffset(o => o - 1)} hitSlop={8} {...tid('weekly-leaderboard-prev')}><Ionicons name="chevron-back" size={22} color={GOLD} /></TouchableOpacity>
        <TouchableOpacity onPress={() => setOffset(o => Math.min(0, o + 1))} disabled={offset === 0} hitSlop={8} {...tid('weekly-leaderboard-next')}><Ionicons name="chevron-forward" size={22} color={offset === 0 ? colors.border : GOLD} /></TouchableOpacity>
      </View>
      {err ? <Text style={{ fontSize: 13, color: RED }} {...tid('weekly-leaderboard-error')}>{tr('lb.error')}</Text> : !d ? <ActivityIndicator color={GOLD} /> : (
        <>
          <Text style={{ fontSize: 12.5, color: colors.textSecondary }} {...tid('weekly-leaderboard-summary')}>
            {d.completed ? tr('lb.summary', { n: d.completed, v: d.avg_score ?? '–' }) : tr('lb.summary_none')}
            {delta != null && delta !== 0 ? <Text style={{ fontWeight: '800', color: delta > 0 ? GREEN : RED }}> · {tr('lb.vs', { d: `${delta > 0 ? '+' : ''}${delta}`, prev: d.prev_label })}</Text> : null}
          </Text>
          {d.boards.length === 0 && <Text style={{ fontSize: 13.5, color: colors.textSecondary, lineHeight: 19 }} {...tid('weekly-leaderboard-empty')}>{d.is_current ? tr('lb.empty_now') : tr('lb.empty_past')}</Text>}
          {d.movers.length > 0 && (
            <View style={{ flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', gap: 6 }} {...tid('weekly-leaderboard-movers')}>
              <Ionicons name="trending-up" size={14} color={GREEN} />
              <Text style={{ fontSize: 11, fontWeight: '800', color: GREEN, letterSpacing: 1 }}>{tr('lb.climbing')}</Text>
              {d.movers.map(m => (
                <TouchableOpacity key={m.target_id + m.department_label} disabled={!onPerson} onPress={() => onPerson?.(m.target_id, m.name)} style={{ paddingHorizontal: 9, paddingVertical: 4, borderRadius: 10, backgroundColor: GREEN + '1A' }} {...tid(`weekly-leaderboard-mover-${m.target_id}`)}>
                  <Text style={{ fontSize: 12, fontWeight: '800', color: colors.text }}>{m.name.split(' ')[0]} <Text style={{ color: GREEN }}>+{m.delta}</Text></Text>
                </TouchableOpacity>
              ))}
            </View>
          )}
          {d.boards.map(b => (
            <View key={b.department} style={{ gap: 6 }} {...tid(`weekly-leaderboard-${b.department}`)}>
              {d.boards.length > 1 && <Text style={{ fontSize: 11, fontWeight: '800', color: GOLD, letterSpacing: 1 }}>{b.label.toUpperCase()}</Text>}
              {b.rows.map(r => <BoardRow key={r.key} r={r} dept={b.department} prevLabel={d.prev_label} colors={colors} onPerson={onPerson} tr={tr} />)}
            </View>
          ))}
        </>
      )}
    </View>
  );
};

const BoardRow = ({ r, dept, prevLabel, colors, onPerson, tr }: { r: Row; dept: string; prevLabel: string; colors: any; onPerson?: (id: string, name: string) => void; tr: ReturnType<typeof makeT> }) => {
  const medal = r.rank <= 3 ? MEDAL[r.rank - 1] : null;
  return (
    <TouchableOpacity disabled={!onPerson} onPress={() => onPerson?.(r.target_id, r.name)} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 8, borderTopWidth: 1, borderTopColor: colors.border }} {...tid(`weekly-leader-${dept}-${r.rank}`)}>
      <View style={{ width: 30, height: 30, borderRadius: 15, backgroundColor: medal ? medal + '22' : colors.surface || colors.bg, borderWidth: medal ? 2 : 0, borderColor: medal || 'transparent', alignItems: 'center', justifyContent: 'center' }}>
        {medal ? <Ionicons name="trophy" size={14} color={medal} /> : <Text style={{ fontSize: 12, fontWeight: '800', color: colors.textSecondary }}>{r.rank}</Text>}
      </View>
      <View style={{ flex: 1 }}>
        <Text style={{ fontSize: 14.5, fontWeight: '800', color: colors.text }} numberOfLines={1}>{r.name}{r.title ? <Text style={{ fontSize: 12, fontWeight: '600', color: colors.textSecondary }}> · {r.title}</Text> : null}</Text>
        <Text style={{ fontSize: 12, color: colors.textSecondary }}>
          {r.completed === 1 ? tr('lb.shops_1') : tr('lb.shops_n', { n: r.completed })}{r.best != null && r.completed > 1 ? ` · ${tr('lb.best', { v: r.best })}` : ''} · {r.delta != null
            ? <Text style={{ fontWeight: '800', color: r.delta > 0 ? GREEN : r.delta < 0 ? RED : colors.textSecondary }} {...tid(`weekly-leader-${dept}-${r.rank}-delta`)}>{tr('lb.vs', { d: `${r.delta > 0 ? '+' : ''}${r.delta}`, prev: prevLabel })}</Text>
            : <Text>{tr('lb.new')}</Text>}
        </Text>
      </View>
      {r.delta != null && r.delta !== 0 && <Ionicons name={r.delta > 0 ? 'arrow-up' : 'arrow-down'} size={14} color={r.delta > 0 ? GREEN : RED} />}
      <Text style={{ fontSize: 20, fontWeight: '800', color: scoreColor(r.avg_score) }}>{r.avg_score}%</Text>
    </TouchableOpacity>
  );
};
