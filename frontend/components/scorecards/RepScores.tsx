import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, ScrollView, TouchableOpacity, ActivityIndicator, RefreshControl, Image, Switch } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useFocusEffect } from 'expo-router';
import api from '../../services/api';
import { useThemeStore } from '../../store/themeStore';
import { useToast } from '../common/Toast';
import { ScreenHeader } from '../common/ScreenHeader';
import { ScoreRing } from './ScoreRing';
import { EvaluationSheet } from './EvaluationSheet';
import { GOLD, GREEN, RED, tid, scoreTone, fmtDur, fmtWhen, type Evaluation, type RepStats } from './shared';

const DAYS = [7, 30, 90];

// One rep's call scores: average + trend, weakest criteria, every graded call. Used for "My Call Scores" and the manager's rep drilldown.
export const RepScores = ({ userId, mine, openId }: { userId?: string; mine: boolean; openId?: string | null }) => {
  const { colors } = useThemeStore();
  const { showToast } = useToast();
  const [days, setDays] = useState(30);
  const [data, setData] = useState<{ user: any; stats: RepStats; evaluations: Evaluation[]; can_manage?: boolean; muted?: boolean } | null>(null);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState<string | null>(openId || null);

  const load = useCallback(async () => {
    try {
      const res = await api.get(mine ? `/scorecards/evaluations/mine?days=${days}` : `/scorecards/rep/${userId}?days=${days}`);
      setData(res.data);
    } catch (e: any) { showToast(e?.response?.data?.detail || 'Could not load scores', 'error'); }
    finally { setLoading(false); }
  }, [days, userId, mine]);
  useFocusEffect(useCallback(() => { load(); }, [load]));
  useEffect(() => { if (openId) setOpen(openId); }, [openId]);

  const toggleMute = async (muted: boolean) => {
    try { await api.put('/scorecards/alerts/mute', { rep_id: userId, muted }); setData(d => (d ? { ...d, muted } : d)); showToast(muted ? 'Alerts muted for this rep' : 'Alerts back on', 'success'); }
    catch (e: any) { showToast(e?.response?.data?.detail || 'Could not update', 'error'); }
  };

  const s = data?.stats;
  const delta = s && s.avg_score != null && s.prev_avg != null ? s.avg_score - s.prev_avg : null;
  const weak = (s?.criteria || []).filter(c => c.pass_rate != null && c.pass_rate < 80).slice(0, 5);
  const maxTrend = Math.max(1, ...(s?.trend || []).map(t => t.avg || 0));
  const first = (data?.user?.name || 'Rep').split(' ')[0];

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      <ScreenHeader title={mine ? 'My Call Scores' : `${first}'s Call Scores`} subtitle={s ? `${s.count} graded call${s.count === 1 ? '' : 's'} · last ${days} days` : undefined} testID="rep-scores-header" />
      {loading && !data ? <ActivityIndicator style={{ marginTop: 60 }} color={GOLD} /> : (
        <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 60, gap: 14 }} refreshControl={<RefreshControl refreshing={false} onRefresh={load} tintColor={GOLD} />}>
          <View style={{ flexDirection: 'row', backgroundColor: colors.surface, borderRadius: 12, padding: 4, gap: 4 }}>
            {DAYS.map(d => (
              <TouchableOpacity key={d} onPress={() => setDays(d)} style={{ flex: 1, paddingVertical: 9, borderRadius: 9, alignItems: 'center', backgroundColor: days === d ? GOLD : 'transparent' }} {...tid(`rep-scores-days-${d}`)}>
                <Text style={{ fontSize: 13, fontWeight: '800', color: days === d ? '#111' : colors.textSecondary }}>{d} days</Text>
              </TouchableOpacity>
            ))}
          </View>

          <View style={{ backgroundColor: colors.card, borderRadius: 18, padding: 16, borderWidth: 1, borderColor: colors.border, flexDirection: 'row', alignItems: 'center', gap: 16 }} {...tid('rep-scores-summary')}>
            <ScoreRing pct={s?.avg_score} size={92} stroke={9} label="AVERAGE" colors={colors} testID="rep-scores-avg" />
            <View style={{ flex: 1, gap: 8 }}>
              {!mine && data?.user && (
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                  {data.user.photo ? <Image source={{ uri: data.user.photo }} style={{ width: 28, height: 28, borderRadius: 14 }} /> : <View style={{ width: 28, height: 28, borderRadius: 14, backgroundColor: GOLD + '33', alignItems: 'center', justifyContent: 'center' }}><Text style={{ fontSize: 12, fontWeight: '800', color: GOLD }}>{first[0]}</Text></View>}
                  <Text style={{ fontSize: 15, fontWeight: '800', color: colors.text }}>{data.user.name}</Text>
                </View>
              )}
              {delta != null ? (
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 5 }}>
                  <Ionicons name={delta >= 0 ? 'trending-up' : 'trending-down'} size={16} color={delta >= 0 ? GREEN : RED} />
                  <Text style={{ fontSize: 13, fontWeight: '700', color: delta >= 0 ? GREEN : RED }} {...tid('rep-scores-delta')}>{delta >= 0 ? '+' : ''}{delta} pts vs previous {days} days</Text>
                </View>
              ) : <Text style={{ fontSize: 13, color: colors.textSecondary }}>{s?.count ? 'No earlier period to compare yet' : 'No graded calls yet. Scores land a minute after each recorded call.'}</Text>}
              <View style={{ flexDirection: 'row', gap: 14 }}>
                <View><Text style={{ fontSize: 18, fontWeight: '800', color: colors.text }}>{s?.clean_calls ?? 0}</Text><Text style={{ fontSize: 10, fontWeight: '700', color: colors.textSecondary, letterSpacing: 0.4 }}>CLEAN CALLS</Text></View>
                <View><Text style={{ fontSize: 18, fontWeight: '800', color: s?.critical_misses ? RED : colors.text }} {...tid('rep-scores-misses')}>{s?.critical_misses ?? 0}</Text><Text style={{ fontSize: 10, fontWeight: '700', color: colors.textSecondary, letterSpacing: 0.4 }}>CRITICAL MISSES</Text></View>
              </View>
            </View>
          </View>

          {!mine && data?.can_manage && (
            <View style={{ backgroundColor: colors.card, borderRadius: 14, padding: 12, borderWidth: 1, borderColor: colors.border, flexDirection: 'row', alignItems: 'center', gap: 12 }}>
              <Ionicons name={data.muted ? 'notifications-off-outline' : 'notifications-outline'} size={20} color={data.muted ? colors.textSecondary : GOLD} />
              <View style={{ flex: 1 }}><Text style={{ fontSize: 14, fontWeight: '700', color: colors.text }}>Alert me on {first}'s critical misses</Text><Text style={{ fontSize: 12, color: colors.textSecondary }}>Only affects your alerts, not other managers.</Text></View>
              <Switch value={!data.muted} onValueChange={v => toggleMute(!v)} trackColor={{ true: GOLD }} {...tid('rep-scores-alert-toggle')} />
            </View>
          )}

          {(s?.trend?.length || 0) > 1 && (
            <View style={{ backgroundColor: colors.card, borderRadius: 16, padding: 14, borderWidth: 1, borderColor: colors.border }} {...tid('rep-scores-trend')}>
              <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 1, marginBottom: 10 }}>WEEK BY WEEK</Text>
              <View style={{ flexDirection: 'row', alignItems: 'flex-end', gap: 8, height: 90 }}>
                {s!.trend.map(t => (
                  <View key={t.week_start} style={{ flex: 1, alignItems: 'center', gap: 4 }}>
                    <Text style={{ fontSize: 11, fontWeight: '800', color: scoreTone(t.avg) }}>{t.avg ?? '--'}</Text>
                    <View style={{ width: '70%', height: Math.max(4, 60 * ((t.avg || 0) / maxTrend)), borderRadius: 6, backgroundColor: scoreTone(t.avg) }} />
                    <Text style={{ fontSize: 9, color: colors.textSecondary }}>{t.label}</Text>
                  </View>
                ))}
              </View>
            </View>
          )}

          {weak.length > 0 && (
            <View style={{ backgroundColor: colors.card, borderRadius: 16, padding: 14, borderWidth: 1, borderColor: colors.border, gap: 10 }} {...tid('rep-scores-weak')}>
              <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 1 }}>{mine ? 'WORK ON THIS' : `COACH ${first.toUpperCase()} ON THIS`}</Text>
              {weak.map(c => (
                <View key={c.id} style={{ gap: 4 }}>
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                    <Text style={{ flex: 1, fontSize: 13, fontWeight: '600', color: colors.text }}>{c.text}{c.critical ? <Text style={{ color: RED, fontSize: 10, fontWeight: '800' }}>  CRITICAL</Text> : null}</Text>
                    <Text style={{ fontSize: 13, fontWeight: '800', color: scoreTone(c.pass_rate) }}>{c.pass_rate}%</Text>
                  </View>
                  <View style={{ height: 6, borderRadius: 3, backgroundColor: colors.surface, overflow: 'hidden' }}><View style={{ width: `${c.pass_rate}%`, height: 6, backgroundColor: scoreTone(c.pass_rate) }} /></View>
                </View>
              ))}
            </View>
          )}

          <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 1, marginTop: 4 }}>GRADED CALLS</Text>
          {data?.evaluations.length === 0 && (
            <View style={{ backgroundColor: colors.card, borderRadius: 16, padding: 20, alignItems: 'center', gap: 8, borderWidth: 1, borderColor: colors.border }} {...tid('rep-scores-empty')}>
              <Ionicons name="call-outline" size={30} color={GOLD} />
              <Text style={{ fontSize: 14, fontWeight: '700', color: colors.text }}>No graded calls in this window</Text>
              <Text style={{ fontSize: 12, color: colors.textSecondary, textAlign: 'center' }}>Recorded calls over 30 seconds are graded automatically against the scorecard that applies.</Text>
            </View>
          )}
          {data?.evaluations.map(ev => {
            const tone = scoreTone(ev.score_pct);
            return (
              <TouchableOpacity key={ev.id} onPress={() => setOpen(ev.id)} activeOpacity={0.8} style={{ backgroundColor: colors.card, borderRadius: 14, padding: 12, borderWidth: 1, borderColor: colors.border, flexDirection: 'row', alignItems: 'center', gap: 12 }} {...tid(`rep-scores-eval-${ev.id}`)}>
                <View style={{ width: 46, height: 46, borderRadius: 23, borderWidth: 3, borderColor: tone, alignItems: 'center', justifyContent: 'center' }}><Text style={{ fontSize: 13, fontWeight: '800', color: colors.text }}>{ev.score_pct ?? '--'}</Text></View>
                <View style={{ flex: 1 }}>
                  <Text style={{ fontSize: 14, fontWeight: '700', color: colors.text }} numberOfLines={1}>{ev.contact_name || 'Unknown caller'}</Text>
                  <Text style={{ fontSize: 12, color: colors.textSecondary, marginTop: 2 }}>{ev.direction === 'inbound' ? 'Inbound' : 'Outbound'} · {fmtDur(ev.duration_s)} · {fmtWhen(ev.call_at)} · {ev.scorecard_name}</Text>
                  {ev.critical_misses.length > 0 && <Text style={{ fontSize: 11, fontWeight: '700', color: RED, marginTop: 3 }}>Missed: {ev.results.filter(r => ev.critical_misses.includes(r.criterion_id)).map(r => r.text).join(', ')}</Text>}
                </View>
                <Ionicons name="chevron-forward" size={16} color={colors.textSecondary} />
              </TouchableOpacity>
            );
          })}
        </ScrollView>
      )}
      <EvaluationSheet visible={!!open} evaluationId={open} onClose={() => setOpen(null)} onChanged={() => load()} />
    </SafeAreaView>
  );
};
