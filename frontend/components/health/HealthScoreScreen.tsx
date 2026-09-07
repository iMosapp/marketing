import React, { useState, useCallback } from 'react';
import { View, Text, TouchableOpacity, ScrollView, StyleSheet, ActivityIndicator, RefreshControl } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import api from '../../services/api';
import { useAuthStore } from '../../store/authStore';
import { useThemeStore } from '../../store/themeStore';
import { UniversalShareModal } from '../UniversalShareModal';
import { ScreenHeader, HeaderIconButton } from '../common/ScreenHeader';
import { FS, EYEBROW } from '../../constants/typography';

const tid = (id: string) => ({ testID: id, dataSet: { testid: id } as any });
const APP_URL = process.env.EXPO_PUBLIC_APP_URL || 'https://app.imonsocial.com';

interface Factor { score: number; max: number; label: string; checks?: Record<string, boolean>; details?: Record<string, any> }
interface Tip { tip: string; points: number; route?: string }
interface TeamMember { user_id: string; name: string; title: string; score: number; grade: string }
interface HealthData { total_score: number; grade: string; grade_color: string; factors: Record<string, Factor>; tips: Tip[]; user_name: string }

export interface HealthScreenConfig {
  kind: 'seo' | 'geo';
  title: string;
  guideRoute: string;
  factorIcons: Record<string, string>;
  factorColors: Record<string, string>;
  // Four messages, best score first.
  gradeCopy: [string, string, string, string];
  shareText: (score: number, grade: string, url: string) => string;
}

const scoreColor = (s: number) => (s >= 80 ? '#34C759' : s >= 60 ? '#C9A962' : s >= 40 ? '#FF9500' : '#FF3B30');

export function HealthScoreScreen({ config }: { config: HealthScreenConfig }) {
  const { kind, title } = config;
  const router = useRouter();
  const { user } = useAuthStore();
  const { colors } = useThemeStore();
  const [data, setData] = useState<HealthData | null>(null);
  const [team, setTeam] = useState<TeamMember[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [tab, setTab] = useState<'my' | 'team'>('my');
  const [error, setError] = useState(false);
  const [showShare, setShowShare] = useState(false);

  const isManager = user?.role === 'super_admin' || user?.role === 'admin' || user?.role === 'store_manager';

  const fetchData = useCallback(async () => {
    if (!user?._id) return;
    setError(false);
    try {
      const res = await api.get(`/${kind}/health-score/${user._id}`);
      if (res.data?.error) setError(true); else setData(res.data);
      if (isManager && user?.store_id) {
        try {
          const teamRes = await api.get(`/${kind}/health-score/team/${user.store_id}`);
          setTeam(teamRes.data.team || []);
        } catch {}
      }
    } catch (e) {
      console.error(`${kind} health fetch error:`, e);
      setError(true);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [user?._id, user?.store_id, isManager, kind]);

  useFocusEffect(useCallback(() => { setLoading(true); fetchData(); }, [fetchData]));

  const onRefresh = () => { setRefreshing(true); fetchData(); };
  const cardUrl = `${APP_URL}/card/${user?._id}`;
  const card = { backgroundColor: colors.card, borderColor: colors.border };

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: colors.bg }]} edges={['top']} {...tid(`${kind}-health-screen`)}>
      <ScreenHeader
        title={title}
        testID={`${kind}-health-header`}
        right={data ? <HeaderIconButton icon="share-outline" onPress={() => setShowShare(true)} testID={`${kind}-share-header-btn`} /> : undefined}
      />

      {loading ? (
        <View style={styles.center}><ActivityIndicator size="large" color={colors.accent} /></View>
      ) : !data ? (
        <View style={[styles.center, { padding: 32 }]} {...tid(`${kind}-health-error`)}>
          <Ionicons name="warning-outline" size={48} color={colors.textTertiary} />
          <Text style={{ color: colors.text, fontSize: FS.heading, fontWeight: '700', marginTop: 12, textAlign: 'center' }}>
            {error ? `Could not load your ${title} score` : 'No score yet'}
          </Text>
          <Text style={{ color: colors.textSecondary, fontSize: FS.body, marginTop: 6, textAlign: 'center' }}>Check your connection and try again.</Text>
          <TouchableOpacity onPress={() => { setLoading(true); fetchData(); }} style={[styles.primaryBtn, { backgroundColor: colors.accent }]} {...tid(`${kind}-retry-btn`)}>
            <Text style={styles.primaryBtnText}>Retry</Text>
          </TouchableOpacity>
        </View>
      ) : (
        <>
          {isManager && (
            <View style={[styles.tabRow, { borderBottomColor: colors.border }]}>
              {(['my', 'team'] as const).map((t) => (
                <TouchableOpacity
                  key={t}
                  style={[styles.tabBtn, tab === t && { borderBottomWidth: 2, borderBottomColor: colors.accent }]}
                  onPress={() => setTab(t)}
                  {...tid(`${kind}-tab-${t}`)}
                >
                  <Text style={[styles.tabText, { color: tab === t ? colors.accent : colors.textSecondary }]}>{t === 'my' ? 'My score' : 'Team'}</Text>
                </TouchableOpacity>
              ))}
            </View>
          )}

          <ScrollView contentContainerStyle={styles.scroll} refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.accent} />}>
            {tab === 'my' ? (
              <>
                <View style={[styles.scoreCard, card]} {...tid(`${kind}-score-card`)}>
                  <View style={[styles.scoreCircle, { borderColor: data.grade_color }]}>
                    <Text style={[styles.scoreNum, { color: data.grade_color }]}>{data.total_score}</Text>
                    <Text style={[styles.scoreOf, { color: colors.textSecondary }]}>/ 100</Text>
                  </View>
                  <Text style={[styles.gradeText, { color: data.grade_color }]} {...tid(`${kind}-grade`)}>{data.grade}</Text>
                  <Text style={[styles.gradeSubtext, { color: colors.textSecondary }]}>
                    {config.gradeCopy[data.total_score >= 80 ? 0 : data.total_score >= 60 ? 1 : data.total_score >= 40 ? 2 : 3]}
                  </Text>
                  <TouchableOpacity onPress={() => setShowShare(true)} style={[styles.shareBtn, { borderColor: data.grade_color }]} {...tid(`${kind}-share-score-btn`)}>
                    <Ionicons name="share-social-outline" size={16} color={data.grade_color} />
                    <Text style={[styles.shareBtnText, { color: data.grade_color }]}>Share my score</Text>
                  </TouchableOpacity>
                </View>

                <Text style={[styles.eyebrow, { color: colors.textSecondary }]}>Score breakdown</Text>
                {Object.entries(data.factors).map(([key, factor]) => {
                  const fc = config.factorColors[key] || colors.accent;
                  return (
                    <View key={key} style={[styles.factorCard, card]} {...tid(`${kind}-factor-${key}`)}>
                      <View style={styles.factorHeader}>
                        <View style={[styles.factorIcon, { backgroundColor: fc + '20' }]}>
                          <Ionicons name={(config.factorIcons[key] || 'analytics') as any} size={20} color={fc} />
                        </View>
                        <Text style={[styles.factorLabel, { color: colors.text }]} numberOfLines={2}>{factor.label}</Text>
                        <Text style={[styles.factorScore, { color: colors.textSecondary }]}>{factor.score} / {factor.max}</Text>
                      </View>
                      <View style={[styles.progressBg, { backgroundColor: colors.border }]}>
                        <View style={[styles.progressFill, { backgroundColor: fc, width: `${Math.min(100, (factor.score / Math.max(1, factor.max)) * 100)}%` }]} />
                      </View>
                      {factor.checks && (
                        <View style={styles.chips}>
                          {Object.entries(factor.checks).map(([ck, val]) => (
                            <View key={ck} style={styles.checkRow}>
                              <Ionicons name={val ? 'checkmark-circle' : 'close-circle'} size={16} color={val ? '#34C759' : '#FF3B30'} />
                              <Text style={[styles.checkLabel, { color: colors.textSecondary }]}>{ck.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}</Text>
                            </View>
                          ))}
                        </View>
                      )}
                      {factor.details && (
                        <View style={styles.chips}>
                          {Object.entries(factor.details).map(([dk, dv]) => (
                            <View key={dk} style={[styles.detailChip, typeof dv !== 'boolean' && { backgroundColor: colors.surface }]}>
                              {typeof dv === 'boolean'
                                ? <Ionicons name={dv ? 'checkmark-circle' : 'close-circle'} size={12} color={dv ? '#34C759' : '#FF3B30'} />
                                : <Text style={[styles.detailValue, { color: colors.text }]}>{String(dv)}</Text>}
                              <Text style={[styles.detailText, { color: colors.textSecondary }]}>{dk.replace(/_/g, ' ')}</Text>
                            </View>
                          ))}
                        </View>
                      )}
                    </View>
                  );
                })}

                <TouchableOpacity onPress={() => router.push(config.guideRoute as any)} style={[styles.guideBtn, card]} {...tid(`${kind}-guide-link`)}>
                  <View style={[styles.guideBtnIcon, { backgroundColor: 'rgba(201,169,98,0.15)' }]}>
                    <Ionicons name="book" size={20} color={colors.accent} />
                  </View>
                  <View style={{ flex: 1, minWidth: 0 }}>
                    <Text style={[styles.guideBtnTitle, { color: colors.text }]}>How to improve your score</Text>
                    <Text style={[styles.guideBtnSub, { color: colors.textSecondary }]}>Step-by-step guide with direct links</Text>
                  </View>
                  <Ionicons name="chevron-forward" size={18} color={colors.textTertiary} />
                </TouchableOpacity>

                {data.tips.length > 0 && (
                  <>
                    <Text style={[styles.eyebrow, { color: colors.textSecondary }]}>Quick wins</Text>
                    <View style={[styles.tipsCard, card]} {...tid(`${kind}-tips-card`)}>
                      {data.tips.map((tip, i) => (
                        <View key={i} style={[styles.tipRow, i < data.tips.length - 1 && { borderBottomWidth: 1, borderBottomColor: colors.border }]}>
                          <View style={styles.tipBadge}><Text style={styles.tipBadgeText}>+{tip.points}</Text></View>
                          <View style={{ flex: 1, minWidth: 0 }}>
                            <Text style={[styles.tipText, { color: colors.text }]}>{tip.tip}</Text>
                            {tip.route ? (
                              <TouchableOpacity style={styles.fixBtn} onPress={() => router.push(tip.route as any)} {...tid(`${kind}-tip-fix-${i}`)}>
                                <Text style={[styles.fixBtnText, { color: colors.accent }]}>Fix this</Text>
                                <Ionicons name="arrow-forward" size={12} color={colors.accent} />
                              </TouchableOpacity>
                            ) : null}
                          </View>
                        </View>
                      ))}
                    </View>
                  </>
                )}
              </>
            ) : (
              <>
                <Text style={[styles.eyebrow, { color: colors.textSecondary }]}>Team {title} rankings</Text>
                {team.length === 0 ? (
                  <View style={[styles.emptyCard, card]} {...tid(`${kind}-team-empty`)}>
                    <Ionicons name="people-outline" size={40} color={colors.textTertiary} />
                    <Text style={{ color: colors.text, fontSize: FS.heading, fontWeight: '700', marginTop: 10 }}>No team scores yet</Text>
                    <Text style={{ color: colors.textSecondary, fontSize: FS.body, marginTop: 4, textAlign: 'center' }}>Reps on your store show up here once they have a profile.</Text>
                    <TouchableOpacity onPress={() => router.push('/admin/users' as any)} style={[styles.primaryBtn, { backgroundColor: colors.accent }]} {...tid(`${kind}-team-manage`)}>
                      <Text style={styles.primaryBtnText}>Manage team</Text>
                    </TouchableOpacity>
                  </View>
                ) : (
                  team.map((m, i) => (
                    <View key={m.user_id} style={[styles.teamRow, card]} {...tid(`team-member-${i}`)}>
                      <Text style={[styles.teamRankNum, { color: i < 3 ? colors.accent : colors.textSecondary }]}>#{i + 1}</Text>
                      <View style={{ flex: 1, minWidth: 0, marginLeft: 8 }}>
                        <Text style={[styles.teamName, { color: colors.text }]} numberOfLines={1}>{m.name}</Text>
                        <Text style={[styles.teamTitle, { color: colors.textSecondary }]} numberOfLines={1}>{m.title || 'Team member'}</Text>
                      </View>
                      <View style={{ alignItems: 'flex-end' }}>
                        <Text style={[styles.teamScoreNum, { color: scoreColor(m.score) }]}>{m.score}</Text>
                        <Text style={[styles.teamGrade, { color: colors.textSecondary }]}>{m.grade}</Text>
                      </View>
                    </View>
                  ))
                )}
              </>
            )}
            <View style={{ height: 32 }} />
          </ScrollView>
        </>
      )}

      {data && (
        <UniversalShareModal
          visible={showShare}
          onClose={() => setShowShare(false)}
          title={`Share my ${title} score`}
          subtitle={`${data.total_score}/100 - ${data.grade}`}
          shareUrl={cardUrl}
          shareText={config.shareText(data.total_score, data.grade, cardUrl)}
          showPreview={true}
          previewUrl={cardUrl}
          showQR={true}
          userId={user?._id}
          eventType={`${kind}_score_shared`}
        />
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  primaryBtn: { marginTop: 18, paddingHorizontal: 22, paddingVertical: 12, borderRadius: 14 },
  primaryBtnText: { color: '#000', fontWeight: '700', fontSize: FS.heading },
  tabRow: { flexDirection: 'row', borderBottomWidth: 1, marginHorizontal: 16 },
  tabBtn: { flex: 1, alignItems: 'center', paddingVertical: 10 },
  tabText: { fontSize: FS.heading, fontWeight: '700' },
  scroll: { padding: 16 },
  eyebrow: { ...EYEBROW, marginBottom: 10, marginTop: 4 },
  scoreCard: { borderRadius: 16, borderWidth: 1, padding: 28, alignItems: 'center', marginBottom: 20 },
  scoreCircle: { width: 120, height: 120, borderRadius: 60, borderWidth: 6, justifyContent: 'center', alignItems: 'center', marginBottom: 12 },
  scoreNum: { fontSize: 40, fontWeight: '900' },
  scoreOf: { fontSize: FS.heading, fontWeight: '500', marginTop: -4 },
  gradeText: { fontSize: FS.title, fontWeight: '800', marginBottom: 4 },
  gradeSubtext: { fontSize: FS.body, textAlign: 'center', lineHeight: 20 },
  shareBtn: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 16, paddingHorizontal: 20, paddingVertical: 10, borderRadius: 20, borderWidth: 1.5 },
  shareBtnText: { fontSize: FS.heading, fontWeight: '700' },
  factorCard: { borderRadius: 16, borderWidth: 1, padding: 16, marginBottom: 10 },
  factorHeader: { flexDirection: 'row', alignItems: 'center', marginBottom: 10, gap: 8 },
  factorIcon: { width: 36, height: 36, borderRadius: 10, justifyContent: 'center', alignItems: 'center', marginRight: 4, flexShrink: 0 },
  factorLabel: { flex: 1, flexShrink: 1, fontSize: FS.heading, fontWeight: '700' },
  factorScore: { fontSize: FS.secondary, fontWeight: '700', flexShrink: 0 },
  progressBg: { height: 6, borderRadius: 3, overflow: 'hidden' },
  progressFill: { height: 6, borderRadius: 3 },
  chips: { marginTop: 10, flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  checkRow: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingRight: 8 },
  checkLabel: { fontSize: FS.secondary },
  detailChip: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 10, paddingVertical: 5, borderRadius: 8 },
  detailValue: { fontSize: FS.heading, fontWeight: '700' },
  detailText: { fontSize: FS.secondary },
  tipsCard: { borderRadius: 16, borderWidth: 1, overflow: 'hidden' },
  tipRow: { flexDirection: 'row', alignItems: 'center', padding: 14, gap: 12 },
  tipBadge: { backgroundColor: '#34C75920', paddingHorizontal: 8, paddingVertical: 3, borderRadius: 8, minWidth: 38, alignItems: 'center' },
  tipBadgeText: { color: '#34C759', fontWeight: '800', fontSize: FS.body },
  tipText: { fontSize: FS.body, lineHeight: 20 },
  fixBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 10, paddingVertical: 5, borderRadius: 8, backgroundColor: 'rgba(201,169,98,0.12)', alignSelf: 'flex-start', marginTop: 6 },
  fixBtnText: { fontSize: FS.secondary, fontWeight: '700' },
  guideBtn: { flexDirection: 'row', alignItems: 'center', gap: 12, padding: 14, borderRadius: 16, borderWidth: 1, marginBottom: 16 },
  guideBtnIcon: { width: 40, height: 40, borderRadius: 12, alignItems: 'center', justifyContent: 'center' },
  guideBtnTitle: { fontSize: FS.heading, fontWeight: '700' },
  guideBtnSub: { fontSize: FS.secondary, marginTop: 1 },
  teamRow: { borderRadius: 16, borderWidth: 1, padding: 14, marginBottom: 8, flexDirection: 'row', alignItems: 'center' },
  teamRankNum: { fontSize: 18, fontWeight: '800', width: 36, textAlign: 'center' },
  teamName: { fontSize: FS.heading, fontWeight: '700' },
  teamTitle: { fontSize: FS.secondary, marginTop: 1 },
  teamScoreNum: { fontSize: 22, fontWeight: '900' },
  teamGrade: { fontSize: FS.secondary },
  emptyCard: { borderRadius: 16, borderWidth: 1, padding: 28, alignItems: 'center' },
});
