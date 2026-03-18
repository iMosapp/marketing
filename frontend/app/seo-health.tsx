import React, { useState, useCallback } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  ScrollView,
  StyleSheet,
  ActivityIndicator,
  RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import api from '../services/api';
import { useAuthStore } from '../store/authStore';
import { useThemeStore } from '../store/themeStore';

const FACTOR_ICONS: Record<string, string> = {
  profile: 'person-circle',
  reviews: 'star',
  distribution: 'share-social',
  visibility: 'search',
  freshness: 'flash',
};

const FACTOR_COLORS: Record<string, string> = {
  profile: '#007AFF',
  reviews: '#FFD60A',
  distribution: '#AF52DE',
  visibility: '#34C759',
  freshness: '#FF9500',
};

interface Factor {
  score: number;
  max: number;
  label: string;
  checks?: Record<string, boolean>;
  details?: Record<string, any>;
}

interface Tip {
  tip: string;
  points: number;
}

interface TeamMember {
  user_id: string;
  name: string;
  title: string;
  score: number;
  grade: string;
  review_count: number;
  card_visits: number;
}

interface HealthData {
  total_score: number;
  grade: string;
  grade_color: string;
  factors: Record<string, Factor>;
  tips: Tip[];
  user_name: string;
}

export default function SEOHealthScreen() {
  const router = useRouter();
  const { user } = useAuthStore();
  const { theme } = useThemeStore();
  const isDark = theme === 'dark';
  const [data, setData] = useState<HealthData | null>(null);
  const [team, setTeam] = useState<TeamMember[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [tab, setTab] = useState<'my' | 'team'>('my');

  const isManager = user?.role === 'super_admin' || user?.role === 'admin' || user?.role === 'store_manager';

  const fetchData = useCallback(async () => {
    if (!user?._id) return;
    try {
      const res = await api.get(`/seo/health-score/${user._id}`);
      setData(res.data);
      if (isManager && user?.store_id) {
        const teamRes = await api.get(`/seo/health-score/team/${user.store_id}`);
        setTeam(teamRes.data.team || []);
      }
    } catch (e) {
      console.error('SEO health fetch error:', e);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [user?._id, user?.store_id, isManager]);

  useFocusEffect(
    useCallback(() => {
      setLoading(true);
      fetchData();
    }, [fetchData])
  );

  const onRefresh = () => {
    setRefreshing(true);
    fetchData();
  };

  const bg = isDark ? '#000' : '#F2F2F7';
  const cardBg = isDark ? '#1C1C1E' : '#FFF';
  const textPrimary = isDark ? '#FFF' : '#000';
  const textSecondary = isDark ? '#8E8E93' : '#6C6C70';
  const border = isDark ? '#2C2C2E' : '#E5E5EA';

  if (loading) {
    return (
      <SafeAreaView style={[styles.container, { backgroundColor: bg }]}>
        <View style={styles.header}>
          <TouchableOpacity onPress={() => router.back()} data-testid="seo-health-back-btn">
            <Ionicons name="chevron-back" size={28} color={textPrimary} />
          </TouchableOpacity>
          <Text style={[styles.headerTitle, { color: textPrimary }]}>SEO Health</Text>
          <View style={{ width: 28 }} />
        </View>
        <View style={styles.loadingWrap}>
          <ActivityIndicator size="large" color="#007AFF" />
        </View>
      </SafeAreaView>
    );
  }

  if (!data) return null;

  const scoreAngle = (data.total_score / 100) * 360;

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: bg }]} data-testid="seo-health-screen">
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} data-testid="seo-health-back-btn">
          <Ionicons name="chevron-back" size={28} color={textPrimary} />
        </TouchableOpacity>
        <Text style={[styles.headerTitle, { color: textPrimary }]}>SEO Health</Text>
        <View style={{ width: 28 }} />
      </View>

      {isManager && (
        <View style={[styles.tabRow, { borderBottomColor: border }]}>
          {['my', 'team'].map((t) => (
            <TouchableOpacity
              key={t}
              style={[styles.tabBtn, tab === t && styles.tabActive]}
              onPress={() => setTab(t as 'my' | 'team')}
              data-testid={`seo-tab-${t}`}
            >
              <Text style={[styles.tabText, { color: tab === t ? '#007AFF' : textSecondary }]}>
                {t === 'my' ? 'My Score' : 'Team'}
              </Text>
            </TouchableOpacity>
          ))}
        </View>
      )}

      <ScrollView
        contentContainerStyle={styles.scroll}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
      >
        {tab === 'my' ? (
          <>
            {/* Score Circle */}
            <View style={[styles.scoreCard, { backgroundColor: cardBg }]} data-testid="seo-score-card">
              <View style={styles.scoreCircleWrap}>
                <View style={[styles.scoreCircle, { borderColor: data.grade_color }]}>
                  <Text style={[styles.scoreNum, { color: data.grade_color }]}>{data.total_score}</Text>
                  <Text style={[styles.scoreOf, { color: textSecondary }]}>/ 100</Text>
                </View>
              </View>
              <Text style={[styles.gradeText, { color: data.grade_color }]} data-testid="seo-grade">{data.grade}</Text>
              <Text style={[styles.gradeSubtext, { color: textSecondary }]}>
                {data.total_score >= 80
                  ? "Your SEO presence is outstanding!"
                  : data.total_score >= 60
                  ? "Good foundation. A few improvements will make a big difference."
                  : data.total_score >= 40
                  ? "You're on the right track. Focus on the tips below to grow."
                  : "Let's build your online presence. Start with the quick wins below."}
              </Text>
            </View>

            {/* Factor Breakdown */}
            <Text style={[styles.sectionTitle, { color: textPrimary }]}>Score Breakdown</Text>
            {Object.entries(data.factors).map(([key, factor]) => (
              <View key={key} style={[styles.factorCard, { backgroundColor: cardBg }]} data-testid={`seo-factor-${key}`}>
                <View style={styles.factorHeader}>
                  <View style={[styles.factorIcon, { backgroundColor: FACTOR_COLORS[key] + '20' }]}>
                    <Ionicons name={FACTOR_ICONS[key] as any} size={20} color={FACTOR_COLORS[key]} />
                  </View>
                  <View style={styles.factorInfo}>
                    <Text style={[styles.factorLabel, { color: textPrimary }]}>{factor.label}</Text>
                    <Text style={[styles.factorScore, { color: textSecondary }]}>{factor.score} / {factor.max}</Text>
                  </View>
                </View>
                <View style={[styles.progressBg, { backgroundColor: border }]}>
                  <View
                    style={[
                      styles.progressFill,
                      {
                        backgroundColor: FACTOR_COLORS[key],
                        width: `${(factor.score / factor.max) * 100}%`,
                      },
                    ]}
                  />
                </View>
                {/* Checklist for profile */}
                {factor.checks && (
                  <View style={styles.checklist}>
                    {Object.entries(factor.checks).map(([ck, val]) => (
                      <View key={ck} style={styles.checkRow}>
                        <Ionicons
                          name={val ? 'checkmark-circle' : 'close-circle'}
                          size={16}
                          color={val ? '#34C759' : '#FF3B30'}
                        />
                        <Text style={[styles.checkLabel, { color: textSecondary }]}>
                          {ck.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
                        </Text>
                      </View>
                    ))}
                  </View>
                )}
                {/* Details for other factors */}
                {factor.details && (
                  <View style={styles.detailsRow}>
                    {Object.entries(factor.details).map(([dk, dv]) => {
                      if (typeof dv === 'boolean') {
                        return (
                          <View key={dk} style={styles.detailChip}>
                            <Ionicons name={dv ? 'checkmark-circle' : 'close-circle'} size={12} color={dv ? '#34C759' : '#FF3B30'} />
                            <Text style={[styles.detailText, { color: textSecondary }]}>{dk.replace(/_/g, ' ')}</Text>
                          </View>
                        );
                      }
                      return (
                        <View key={dk} style={[styles.detailChip, { backgroundColor: isDark ? '#2C2C2E' : '#F2F2F7' }]}>
                          <Text style={[styles.detailValue, { color: textPrimary }]}>{dv}</Text>
                          <Text style={[styles.detailText, { color: textSecondary }]}>{dk.replace(/_/g, ' ')}</Text>
                        </View>
                      );
                    })}
                  </View>
                )}
              </View>
            ))}

            {/* Tips */}
            {data.tips.length > 0 && (
              <>
                <Text style={[styles.sectionTitle, { color: textPrimary }]}>Quick Wins</Text>
                <View style={[styles.tipsCard, { backgroundColor: cardBg }]} data-testid="seo-tips-card">
                  {data.tips.map((tip, i) => (
                    <View key={i} style={[styles.tipRow, i < data.tips.length - 1 && { borderBottomWidth: 1, borderBottomColor: border }]}>
                      <View style={styles.tipBadge}>
                        <Text style={styles.tipBadgeText}>+{tip.points}</Text>
                      </View>
                      <Text style={[styles.tipText, { color: textPrimary }]}>{tip.tip}</Text>
                    </View>
                  ))}
                </View>
              </>
            )}
          </>
        ) : (
          <>
            {/* Team Leaderboard */}
            <Text style={[styles.sectionTitle, { color: textPrimary }]}>Team SEO Rankings</Text>
            {team.length === 0 ? (
              <View style={[styles.emptyCard, { backgroundColor: cardBg }]}>
                <Text style={{ color: textSecondary }}>No team members found</Text>
              </View>
            ) : (
              team.map((m, i) => (
                <View key={m.user_id} style={[styles.teamRow, { backgroundColor: cardBg }]} data-testid={`team-member-${i}`}>
                  <View style={styles.teamRank}>
                    <Text style={[styles.teamRankNum, { color: i < 3 ? '#FFD60A' : textSecondary }]}>#{i + 1}</Text>
                  </View>
                  <View style={styles.teamInfo}>
                    <Text style={[styles.teamName, { color: textPrimary }]}>{m.name}</Text>
                    <Text style={[styles.teamTitle, { color: textSecondary }]}>{m.title || 'Team Member'}</Text>
                  </View>
                  <View style={styles.teamScoreWrap}>
                    <Text style={[styles.teamScoreNum, {
                      color: m.score >= 80 ? '#34C759' : m.score >= 60 ? '#007AFF' : m.score >= 40 ? '#FF9500' : '#FF3B30'
                    }]}>{m.score}</Text>
                    <Text style={[styles.teamGrade, { color: textSecondary }]}>{m.grade}</Text>
                  </View>
                </View>
              ))
            )}
          </>
        )}

        <View style={{ height: 40 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 12 },
  headerTitle: { fontSize: 18, fontWeight: '700' },
  loadingWrap: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  tabRow: { flexDirection: 'row', borderBottomWidth: 1, marginHorizontal: 16 },
  tabBtn: { flex: 1, alignItems: 'center', paddingVertical: 10 },
  tabActive: { borderBottomWidth: 2, borderBottomColor: '#007AFF' },
  tabText: { fontSize: 15, fontWeight: '600' },
  scroll: { padding: 16 },
  // Score Card
  scoreCard: { borderRadius: 20, padding: 28, alignItems: 'center', marginBottom: 20 },
  scoreCircleWrap: { marginBottom: 12 },
  scoreCircle: { width: 120, height: 120, borderRadius: 60, borderWidth: 6, justifyContent: 'center', alignItems: 'center' },
  scoreNum: { fontSize: 40, fontWeight: '900' },
  scoreOf: { fontSize: 14, fontWeight: '500', marginTop: -4 },
  gradeText: { fontSize: 20, fontWeight: '800', marginBottom: 4 },
  gradeSubtext: { fontSize: 14, textAlign: 'center', lineHeight: 20 },
  // Factors
  sectionTitle: { fontSize: 17, fontWeight: '700', marginBottom: 12, marginTop: 4 },
  factorCard: { borderRadius: 14, padding: 16, marginBottom: 10 },
  factorHeader: { flexDirection: 'row', alignItems: 'center', marginBottom: 10 },
  factorIcon: { width: 36, height: 36, borderRadius: 10, justifyContent: 'center', alignItems: 'center', marginRight: 12 },
  factorInfo: { flex: 1, flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  factorLabel: { fontSize: 15, fontWeight: '600' },
  factorScore: { fontSize: 14, fontWeight: '600' },
  progressBg: { height: 6, borderRadius: 3, overflow: 'hidden' },
  progressFill: { height: 6, borderRadius: 3 },
  // Checklist
  checklist: { marginTop: 10, flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  checkRow: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingRight: 12 },
  checkLabel: { fontSize: 12 },
  // Details
  detailsRow: { marginTop: 10, flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  detailChip: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 10, paddingVertical: 5, borderRadius: 8 },
  detailValue: { fontSize: 14, fontWeight: '700' },
  detailText: { fontSize: 11 },
  // Tips
  tipsCard: { borderRadius: 14, overflow: 'hidden' },
  tipRow: { flexDirection: 'row', alignItems: 'center', padding: 14, gap: 12 },
  tipBadge: { backgroundColor: '#34C75920', paddingHorizontal: 8, paddingVertical: 3, borderRadius: 8, minWidth: 38, alignItems: 'center' },
  tipBadgeText: { color: '#34C759', fontWeight: '800', fontSize: 13 },
  tipText: { fontSize: 14, flex: 1, lineHeight: 19 },
  // Team
  teamRow: { borderRadius: 14, padding: 14, marginBottom: 8, flexDirection: 'row', alignItems: 'center' },
  teamRank: { width: 36, alignItems: 'center' },
  teamRankNum: { fontSize: 16, fontWeight: '800' },
  teamInfo: { flex: 1, marginLeft: 8 },
  teamName: { fontSize: 15, fontWeight: '600' },
  teamTitle: { fontSize: 12, marginTop: 1 },
  teamScoreWrap: { alignItems: 'flex-end' },
  teamScoreNum: { fontSize: 22, fontWeight: '900' },
  teamGrade: { fontSize: 11 },
  emptyCard: { borderRadius: 14, padding: 24, alignItems: 'center' },
});
