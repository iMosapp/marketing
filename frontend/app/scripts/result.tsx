import React, { useCallback, useState } from 'react';
import { View, Text, ScrollView, TouchableOpacity, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect, useLocalSearchParams } from 'expo-router';
import api from '../../services/api';
import { useThemeStore } from '../../store/themeStore';
import { useToast } from '../../components/common/Toast';
import { ScreenHeader } from '../../components/common/ScreenHeader';
import { ScoreRing } from '../../components/scorecards/ScoreRing';
import { CriteriaChecklist } from '../../components/scorecards/CriteriaChecklist';
import { fmtDur } from '../../components/scorecards/shared';
import { GOLD, GREEN, RED, tid, type RoleplayResult, type Turn } from '../../components/scripts/shared';
import { SuccessPoints } from '../../components/scripts/ScriptParts';

type SessionOut = { session_id: string; status: string; script_title: string; script_id: string; persona: { name: string }; rep_name: string; turns: Turn[]; result: RoleplayResult | null };

export default function PracticeResult() {
  const router = useRouter();
  const { session } = useLocalSearchParams<{ session: string }>();
  const { colors } = useThemeStore();
  const { showToast } = useToast();
  const [data, setData] = useState<SessionOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [showTranscript, setShowTranscript] = useState(false);

  const load = useCallback(async () => {
    try {
      let res = await api.get(`/scripts/roleplay/${session}`);
      if (!res.data.result && ['active', 'ending'].includes(res.data.status)) {
        await api.post(`/scripts/roleplay/${session}/end`, {}, { timeout: 120000 });
        res = await api.get(`/scripts/roleplay/${session}`);
      }
      setData(res.data);
    } catch (e: any) { showToast(e?.response?.data?.detail || 'Could not load the result', 'error'); }
    finally { setLoading(false); }
  }, [session]);
  useFocusEffect(useCallback(() => { if (session) load(); }, [session, load]));

  const r = data?.result;
  const hits: Record<string, boolean> = {};
  (r?.adherence?.points || []).forEach(p => { hits[p.point] = p.hit; });
  const points = (r?.adherence?.points || []).map(p => p.point);
  const H = ({ t }: { t: string }) => <Text style={{ fontSize: 11, fontWeight: '800', color: colors.textSecondary, letterSpacing: 1, marginBottom: 8 }}>{t}</Text>;
  const headline = r?.score_pct == null && r?.adherence?.score_pct == null ? 'Too short to grade' : (r?.score_pct ?? r?.adherence?.score_pct ?? 0) >= 80 ? 'Strong call' : (r?.score_pct ?? r?.adherence?.score_pct ?? 0) >= 60 ? 'Solid, a few misses' : 'Room to grow';

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      <ScreenHeader title="Practice result" subtitle={data?.script_title} testID="practice-result-header" onBack={() => router.replace('/scripts' as any)} />
      {loading || !data ? <ActivityIndicator style={{ marginTop: 60 }} color={GOLD} /> : !r ? (
        <View style={{ padding: 30, alignItems: 'center', gap: 10 }} {...tid('practice-result-empty')}><Ionicons name="clipboard-outline" size={34} color={GOLD} /><Text style={{ color: colors.text, fontWeight: '700' }}>Nothing to grade yet</Text></View>
      ) : (
        <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 60, gap: 18 }}>
          <View style={{ backgroundColor: colors.card, borderRadius: 18, padding: 16, borderWidth: 1, borderColor: colors.border, gap: 14 }} {...tid('practice-result-card')}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 16 }}>
              <ScoreRing pct={r.score_pct} size={84} stroke={8} colors={colors} label={r.scorecard_name ? 'SCORECARD' : undefined} testID="practice-score-ring" />
              <ScoreRing pct={r.adherence?.score_pct} size={84} stroke={8} colors={colors} label="SCRIPT" testID="practice-adherence-ring" />
              <View style={{ flex: 1, gap: 6 }}>
                <Text style={{ fontSize: 17, fontWeight: '800', color: colors.text }} {...tid('practice-result-headline')}>{headline}</Text>
                <Text style={{ fontSize: 12, color: colors.textSecondary }}>With {data.persona?.name || 'the customer'} · {fmtDur(r.duration_s || 0)}{r.scorecard_name ? ` · ${r.scorecard_name}` : ''}</Text>
                {r.critical_misses.length > 0 ? (
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 5 }}><Ionicons name="alert-circle" size={15} color={RED} /><Text style={{ fontSize: 13, fontWeight: '700', color: RED }} {...tid('practice-critical-count')}>{r.critical_misses.length} critical miss{r.critical_misses.length === 1 ? '' : 'es'}</Text></View>
                ) : r.scorecard_name ? (
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 5 }}><Ionicons name="shield-checkmark" size={15} color={GREEN} /><Text style={{ fontSize: 13, fontWeight: '700', color: GREEN }}>No critical misses</Text></View>
                ) : null}
              </View>
            </View>
            {!!(r.summary || r.adherence?.summary) && <Text style={{ fontSize: 14.5, color: colors.text, lineHeight: 21 }} {...tid('practice-summary')}>{r.summary || r.adherence?.summary}</Text>}
          </View>

          {r.coaching.length > 0 && (
            <View style={{ backgroundColor: GOLD + '14', borderLeftWidth: 3, borderLeftColor: GOLD, borderRadius: 12, padding: 12, gap: 8 }} {...tid('practice-coaching')}>
              <Text style={{ fontSize: 11, fontWeight: '800', color: GOLD, letterSpacing: 1 }}>COACHING</Text>
              {r.coaching.map((c, i) => <View key={i} style={{ flexDirection: 'row', gap: 8 }}><Ionicons name="bulb" size={15} color={GOLD} style={{ marginTop: 3 }} /><Text style={{ flex: 1, fontSize: 14, color: colors.text, lineHeight: 20 }}>{c}</Text></View>)}
            </View>
          )}
          {r.wins.length > 0 && (
            <View><H t="WHAT WENT WELL" />{r.wins.map((w, i) => <View key={i} style={{ flexDirection: 'row', gap: 8, marginBottom: 6 }}><Ionicons name="checkmark-circle" size={16} color={GREEN} style={{ marginTop: 2 }} /><Text style={{ flex: 1, fontSize: 14, color: colors.text, lineHeight: 20 }}>{w}</Text></View>)}</View>
          )}
          {points.length > 0 && <View><H t="SCRIPT POINTS" /><SuccessPoints points={points} colors={colors} hits={hits} /></View>}
          {r.results.length > 0 && <View><H t={`SCORECARD · ${(r.scorecard_name || '').toUpperCase()}`} /><CriteriaChecklist results={r.results} colors={colors} canManage={false} /></View>}

          <View>
            <TouchableOpacity onPress={() => setShowTranscript(v => !v)} style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }} {...tid('practice-transcript-toggle')}>
              <Ionicons name={showTranscript ? 'chevron-down' : 'chevron-forward'} size={16} color={GOLD} /><Text style={{ fontSize: 14, fontWeight: '800', color: GOLD }}>{showTranscript ? 'Hide' : 'Read'} the call ({data.turns.length} lines)</Text>
            </TouchableOpacity>
            {showTranscript && (
              <View style={{ gap: 8, marginTop: 10 }} {...tid('practice-result-transcript')}>
                {data.turns.map((t, i) => (
                  <View key={i} style={{ flexDirection: 'row', justifyContent: t.role === 'rep' ? 'flex-end' : 'flex-start' }}>
                    <View style={{ maxWidth: '86%', backgroundColor: t.role === 'rep' ? GOLD : colors.card, borderRadius: 14, padding: 10, borderWidth: t.role === 'rep' ? 0 : 1, borderColor: colors.border }}>
                      <Text style={{ fontSize: 10, fontWeight: '800', color: t.role === 'rep' ? '#11111199' : colors.textSecondary, marginBottom: 2 }}>{t.role === 'rep' ? 'YOU' : (data.persona?.name || 'CUSTOMER').toUpperCase()}</Text>
                      <Text style={{ fontSize: 14, lineHeight: 20, color: t.role === 'rep' ? '#111' : colors.text }}>{t.text}</Text>
                    </View>
                  </View>
                ))}
              </View>
            )}
          </View>

          <View style={{ flexDirection: 'row', gap: 10, marginTop: 6 }}>
            <TouchableOpacity onPress={() => router.replace(`/scripts/${data.script_id}` as any)} style={{ flex: 1, height: 50, borderRadius: 14, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.card, alignItems: 'center', justifyContent: 'center' }} {...tid('practice-result-script')}>
              <Text style={{ fontSize: 14, fontWeight: '800', color: colors.text }}>Re-read the script</Text>
            </TouchableOpacity>
            <TouchableOpacity onPress={() => router.replace(`/scripts/practice?script=${data.script_id}` as any)} style={{ flex: 1, height: 50, borderRadius: 14, backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 8 }} {...tid('practice-result-again')}>
              <Ionicons name="refresh" size={18} color="#111" /><Text style={{ fontSize: 14, fontWeight: '800', color: '#111' }}>Run it again</Text>
            </TouchableOpacity>
          </View>
        </ScrollView>
      )}
    </SafeAreaView>
  );
}
