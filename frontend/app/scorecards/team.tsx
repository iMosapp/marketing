import React, { useCallback, useState } from 'react';
import { View, Text, ScrollView, TouchableOpacity, ActivityIndicator, RefreshControl, Image } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import api from '../../services/api';
import { useThemeStore } from '../../store/themeStore';
import { useToast } from '../../components/common/Toast';
import { ScreenHeader } from '../../components/common/ScreenHeader';
import { ScoreRing } from '../../components/scorecards/ScoreRing';
import { EvaluationSheet } from '../../components/scorecards/EvaluationSheet';
import { GOLD, RED, GREEN, tid, scoreTone, fmtWhen, type Evaluation, type Scorecard } from '../../components/scorecards/shared';

type Team = {
  days: number; calls: number; avg_score: number | null; critical_misses: number;
  reps: { user_id: string; name: string; photo?: string | null; count: number; avg_score: number | null; critical_misses: number; last_call_at: string | null; weakest: string | null }[];
  criteria: { id: string; text: string; critical: boolean; pass_rate: number | null; graded: number }[];
  heatmap: Record<string, Record<string, number | null>>; alerts: Evaluation[]; muted_reps: string[];
};
const DAYS = [7, 30, 90];
type Seg = 'board' | 'heat' | 'alerts';

export default function TeamCallScores() {
  const router = useRouter();
  const { colors } = useThemeStore();
  const { showToast } = useToast();
  const [days, setDays] = useState(30);
  const [cards, setCards] = useState<Scorecard[]>([]);
  const [cardId, setCardId] = useState<string | null>(null);
  const [data, setData] = useState<Team | null>(null);
  const [loading, setLoading] = useState(true);
  const [seg, setSeg] = useState<Seg>('board');
  const [open, setOpen] = useState<string | null>(null);
  const [forbidden, setForbidden] = useState(false);

  const load = useCallback(async () => {
    try {
      const [lib, team] = await Promise.all([api.get('/scorecards'), api.get(`/scorecards/team?days=${days}${cardId ? `&scorecard_id=${cardId}` : ''}`)]);
      setCards(lib.data.scorecards || []); setData(team.data);
    } catch (e: any) {
      if (e?.response?.status === 403) { setForbidden(true); showToast('Team Call Scores is for managers. Your own scores live under My Call Scores.', 'error'); }
      else showToast(e?.response?.data?.detail || 'Could not load team scores', 'error');
    }
    finally { setLoading(false); }
  }, [days, cardId]);
  useFocusEffect(useCallback(() => { load(); }, [load]));

  const heatTone = (v: number | null | undefined) => (v == null ? colors.surface : v >= 80 ? GREEN + '55' : v >= 60 ? '#FF950066' : RED + '66');
  const SegBtn = ({ k, l, badge }: { k: Seg; l: string; badge?: number }) => (
    <TouchableOpacity onPress={() => setSeg(k)} style={{ flex: 1, paddingVertical: 10, borderRadius: 9, alignItems: 'center', backgroundColor: seg === k ? GOLD : 'transparent', flexDirection: 'row', justifyContent: 'center', gap: 5 }} {...tid(`team-seg-${k}`)}>
      <Text style={{ fontSize: 13, fontWeight: '800', color: seg === k ? '#111' : colors.textSecondary }}>{l}</Text>
      {!!badge && <View style={{ backgroundColor: RED, borderRadius: 8, paddingHorizontal: 5, minWidth: 16, alignItems: 'center' }}><Text style={{ fontSize: 10, fontWeight: '800', color: '#fff' }}>{badge}</Text></View>}
    </TouchableOpacity>
  );

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      <ScreenHeader title="Team Call Scores" subtitle={data ? `${data.calls} graded call${data.calls === 1 ? '' : 's'} · last ${days} days` : undefined} testID="team-scores-header" />
      {forbidden ? (
        <View style={{ alignItems: 'center', padding: 32, gap: 10 }} {...tid('team-forbidden')}>
          <Ionicons name="lock-closed-outline" size={34} color={GOLD} />
          <Text style={{ fontSize: 16, fontWeight: '800', color: colors.text }}>Managers only</Text>
          <Text style={{ fontSize: 13, color: colors.textSecondary, textAlign: 'center' }}>Your own call scores are under My Call Scores.</Text>
          <TouchableOpacity onPress={() => router.replace('/scorecards/my' as any)} style={{ marginTop: 6, height: 42, paddingHorizontal: 18, borderRadius: 12, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center' }} {...tid('team-forbidden-mine')}>
            <Text style={{ fontSize: 14, fontWeight: '800', color: '#111' }}>My Call Scores</Text>
          </TouchableOpacity>
        </View>
      ) : loading && !data ? <ActivityIndicator style={{ marginTop: 60 }} color={GOLD} /> : (
        <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 60, gap: 14 }} refreshControl={<RefreshControl refreshing={false} onRefresh={load} tintColor={GOLD} />}>
          <View style={{ flexDirection: 'row', backgroundColor: colors.surface, borderRadius: 12, padding: 4, gap: 4 }}>
            {DAYS.map(d => (
              <TouchableOpacity key={d} onPress={() => setDays(d)} style={{ flex: 1, paddingVertical: 9, borderRadius: 9, alignItems: 'center', backgroundColor: days === d ? GOLD : 'transparent' }} {...tid(`team-days-${d}`)}>
                <Text style={{ fontSize: 13, fontWeight: '800', color: days === d ? '#111' : colors.textSecondary }}>{d} days</Text>
              </TouchableOpacity>
            ))}
          </View>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 6 }}>
            {[{ id: null, name: 'All scorecards' }, ...cards].map(c => (
              <TouchableOpacity key={c.id || 'all'} onPress={() => setCardId(c.id)} style={{ paddingHorizontal: 12, paddingVertical: 7, borderRadius: 16, backgroundColor: cardId === c.id ? GOLD + '22' : colors.card, borderWidth: 1, borderColor: cardId === c.id ? GOLD : colors.border }} {...tid(`team-card-${c.id || 'all'}`)}>
                <Text style={{ fontSize: 12, fontWeight: '700', color: cardId === c.id ? GOLD : colors.text }}>{c.name}</Text>
              </TouchableOpacity>
            ))}
          </ScrollView>

          <View style={{ backgroundColor: colors.card, borderRadius: 18, padding: 16, borderWidth: 1, borderColor: colors.border, flexDirection: 'row', alignItems: 'center', gap: 16 }} {...tid('team-summary')}>
            <ScoreRing pct={data?.avg_score} size={84} stroke={8} label="TEAM AVG" colors={colors} testID="team-avg" />
            <View style={{ flex: 1, flexDirection: 'row', gap: 14 }}>
              <View><Text style={{ fontSize: 22, fontWeight: '800', color: colors.text }}>{data?.calls ?? 0}</Text><Text style={{ fontSize: 10, fontWeight: '700', color: colors.textSecondary, letterSpacing: 0.4 }}>CALLS GRADED</Text></View>
              <View><Text style={{ fontSize: 22, fontWeight: '800', color: data?.critical_misses ? RED : colors.text }} {...tid('team-misses')}>{data?.critical_misses ?? 0}</Text><Text style={{ fontSize: 10, fontWeight: '700', color: colors.textSecondary, letterSpacing: 0.4 }}>CRITICAL MISSES</Text></View>
              <View><Text style={{ fontSize: 22, fontWeight: '800', color: colors.text }}>{data?.reps.length ?? 0}</Text><Text style={{ fontSize: 10, fontWeight: '700', color: colors.textSecondary, letterSpacing: 0.4 }}>REPS</Text></View>
            </View>
          </View>

          <View style={{ flexDirection: 'row', backgroundColor: colors.surface, borderRadius: 12, padding: 4, gap: 4 }}>
            <SegBtn k="board" l="Leaderboard" /><SegBtn k="heat" l="Who misses what" /><SegBtn k="alerts" l="Alerts" badge={data?.alerts.length} />
          </View>

          {seg === 'board' && (
            <View style={{ gap: 8 }} {...tid('team-leaderboard')}>
              {data?.reps.length === 0 && <Text style={{ fontSize: 13, color: colors.textSecondary, textAlign: 'center', padding: 20 }}>No graded calls yet in this window.</Text>}
              {data?.reps.map((r, i) => (
                <TouchableOpacity key={r.user_id} onPress={() => router.push(`/scorecards/rep/${r.user_id}` as any)} activeOpacity={0.8} style={{ backgroundColor: colors.card, borderRadius: 14, padding: 12, borderWidth: 1, borderColor: colors.border, flexDirection: 'row', alignItems: 'center', gap: 12 }} {...tid(`team-rep-${r.user_id}`)}>
                  <Text style={{ fontSize: 14, fontWeight: '800', color: i === 0 ? GOLD : colors.textSecondary, width: 22 }}>{i + 1}</Text>
                  {r.photo ? <Image source={{ uri: r.photo }} style={{ width: 40, height: 40, borderRadius: 20 }} /> : <View style={{ width: 40, height: 40, borderRadius: 20, backgroundColor: GOLD + '33', alignItems: 'center', justifyContent: 'center' }}><Text style={{ fontSize: 15, fontWeight: '800', color: GOLD }}>{r.name[0]}</Text></View>}
                  <View style={{ flex: 1 }}>
                    <Text style={{ fontSize: 15, fontWeight: '700', color: colors.text }}>{r.name}{data.muted_reps.includes(r.user_id) ? <Text style={{ fontSize: 11, color: colors.textSecondary }}>  muted</Text> : null}</Text>
                    <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 2 }}>{r.count} call{r.count === 1 ? '' : 's'}{r.critical_misses ? ` · ${r.critical_misses} critical miss${r.critical_misses === 1 ? '' : 'es'}` : ' · no critical misses'}</Text>
                    {r.weakest && <Text style={{ fontSize: 11, color: colors.textSecondary, marginTop: 2 }} numberOfLines={1}>Weakest: {r.weakest}</Text>}
                  </View>
                  <View style={{ alignItems: 'center' }}><Text style={{ fontSize: 20, fontWeight: '800', color: scoreTone(r.avg_score) }}>{r.avg_score ?? '--'}</Text><Text style={{ fontSize: 9, fontWeight: '700', color: colors.textSecondary }}>AVG</Text></View>
                  <Ionicons name="chevron-forward" size={16} color={colors.textSecondary} />
                </TouchableOpacity>
              ))}
            </View>
          )}

          {seg === 'heat' && (
            <View style={{ backgroundColor: colors.card, borderRadius: 16, padding: 12, borderWidth: 1, borderColor: colors.border }} {...tid('team-heatmap')}>
              {!cardId ? (
                <Text style={{ fontSize: 13, color: colors.textSecondary, textAlign: 'center', padding: 12, lineHeight: 18 }}>Pick one scorecard above to see which items each rep misses.</Text>
              ) : !data?.criteria.length ? (
                <Text style={{ fontSize: 13, color: colors.textSecondary, textAlign: 'center', padding: 12 }}>No graded calls on this scorecard yet.</Text>
              ) : (
                <ScrollView horizontal showsHorizontalScrollIndicator={false}>
                  <View>
                    <View style={{ flexDirection: 'row', alignItems: 'flex-end', gap: 4, marginBottom: 6 }}>
                      <View style={{ width: 92 }} />
                      {data.criteria.map(c => (
                        <View key={c.id} style={{ width: 54, alignItems: 'center' }}>
                          <Text style={{ fontSize: 9, fontWeight: '700', color: c.critical ? RED : colors.textSecondary, textAlign: 'center' }} numberOfLines={3}>{c.text}</Text>
                        </View>
                      ))}
                    </View>
                    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4, marginBottom: 6 }}>
                      <Text style={{ width: 92, fontSize: 11, fontWeight: '800', color: colors.text }}>Team</Text>
                      {data.criteria.map(c => (
                        <View key={c.id} style={{ width: 54, height: 34, borderRadius: 8, backgroundColor: heatTone(c.pass_rate), alignItems: 'center', justifyContent: 'center' }}>
                          <Text style={{ fontSize: 12, fontWeight: '800', color: colors.text }}>{c.pass_rate == null ? '--' : `${c.pass_rate}%`}</Text>
                        </View>
                      ))}
                    </View>
                    {data.reps.map(r => (
                      <TouchableOpacity key={r.user_id} onPress={() => router.push(`/scorecards/rep/${r.user_id}` as any)} style={{ flexDirection: 'row', alignItems: 'center', gap: 4, marginBottom: 4 }} {...tid(`team-heat-row-${r.user_id}`)}>
                        <Text style={{ width: 92, fontSize: 12, fontWeight: '600', color: colors.text }} numberOfLines={1}>{r.name.split(' ')[0]}</Text>
                        {data.criteria.map(c => {
                          const v = data.heatmap[r.user_id]?.[c.id];
                          return <View key={c.id} style={{ width: 54, height: 34, borderRadius: 8, backgroundColor: heatTone(v), alignItems: 'center', justifyContent: 'center' }}><Text style={{ fontSize: 12, fontWeight: '700', color: colors.text }}>{v == null ? '--' : `${v}%`}</Text></View>;
                        })}
                      </TouchableOpacity>
                    ))}
                  </View>
                </ScrollView>
              )}
            </View>
          )}

          {seg === 'alerts' && (
            <View style={{ gap: 8 }} {...tid('team-alerts')}>
              {data?.alerts.length === 0 && <View style={{ alignItems: 'center', padding: 20, gap: 8 }}><Ionicons name="shield-checkmark" size={30} color={GREEN} /><Text style={{ fontSize: 13, color: colors.textSecondary }}>No critical misses in this window. Nice.</Text></View>}
              {data?.alerts.map(ev => (
                <TouchableOpacity key={ev.id} onPress={() => setOpen(ev.id)} activeOpacity={0.8} style={{ backgroundColor: colors.card, borderRadius: 14, padding: 12, borderWidth: 1, borderColor: colors.border, borderLeftWidth: 3, borderLeftColor: RED, gap: 4 }} {...tid(`team-alert-${ev.id}`)}>
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                    <Ionicons name="alert-circle" size={18} color={RED} />
                    <Text style={{ flex: 1, fontSize: 14, fontWeight: '700', color: colors.text }}>{(ev.rep_name || 'Rep').split(' ')[0]} with {ev.contact_name || 'a customer'}</Text>
                    <Text style={{ fontSize: 13, fontWeight: '800', color: scoreTone(ev.score_pct) }}>{ev.score_pct}%</Text>
                  </View>
                  <Text style={{ fontSize: 12, color: RED, fontWeight: '600' }}>Missed: {ev.results.filter(r => ev.critical_misses.includes(r.criterion_id)).map(r => r.text).join(', ')}</Text>
                  <Text style={{ fontSize: 11, color: colors.textSecondary }}>{fmtWhen(ev.call_at)} · {ev.scorecard_name}</Text>
                </TouchableOpacity>
              ))}
            </View>
          )}
        </ScrollView>
      )}
      <EvaluationSheet visible={!!open} evaluationId={open} onClose={() => setOpen(null)} onChanged={() => load()} />
    </SafeAreaView>
  );
}
