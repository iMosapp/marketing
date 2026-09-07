import React, { useState, useEffect, useCallback } from 'react';
import {
  View, Text, TouchableOpacity, ScrollView, ActivityIndicator,
} from 'react-native';
import { Image } from 'expo-image';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import { useAuthStore } from '../../store/authStore';
import { useThemeStore } from '../../store/themeStore';
import { ScreenHeader, HeaderIconButton } from '../../components/common/ScreenHeader';
import { FS } from '../../constants/typography';
import { showAlert } from '../../services/alert';
import api from '../../services/api';

const tid = (id: string) => ({ testID: id, dataSet: { testid: id } as any });

const TIERS = [
  { key: 'store', label: 'My Team', icon: 'people' },
  { key: 'org', label: 'My Org', icon: 'business' },
  { key: 'global', label: 'Global', icon: 'globe' },
];
const PERIODS = [
  { key: 'week', label: 'This Week' },
  { key: 'month', label: 'This Month' },
  { key: 'all', label: 'All Time' },
];

function getInitials(name: string) {
  const parts = (name || '?').split(' ').filter(Boolean);
  return (parts[0]?.[0] || '?').toUpperCase() + (parts[1]?.[0] || '').toUpperCase();
}

export default function LeaderboardScreen() {
  const { colors } = useThemeStore();
  const router = useRouter();
  const user = useAuthStore((s) => s.user);
  const [tier, setTier] = useState('store');
  const [period, setPeriod] = useState('month');
  const [category, setCategory] = useState('total');
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  const loadData = useCallback(async () => {
    if (!user?._id) return;
    setLoading(true);
    try {
      const res = await api.get(`/leaderboard/v2/${tier}/${user._id}`, { params: { period, category } });
      setData(res.data);
    } catch (e) { console.error(e); }
    setLoading(false);
  }, [user?._id, tier, period, category]);

  useFocusEffect(useCallback(() => { loadData(); }, [loadData]));

  const cats = data?.categories || {};
  const catKeys = ['total', ...Object.keys(cats)];
  const leaderboard = data?.leaderboard || [];
  const yourStats = data?.your_stats || {};
  const level = yourStats.level || {};
  const isGlobal = tier === 'global';

  // Top 3 for podium
  const top3 = leaderboard.slice(0, 3);
  const rest = leaderboard.slice(3);

  const isAdmin = user?.role === 'super_admin' || user?.role === 'org_admin';

  const sendPowerRankings = async () => {
    if (!user?._id) return;
    try {
      const res = await api.post('/admin/send-power-rankings', {}, { headers: { 'X-User-ID': user._id } });
      showAlert('Power Rankings sent', `${res.data.emails_sent} emails delivered.`);
    } catch (e: any) {
      showAlert('Could not send', e?.response?.data?.detail || 'Failed to send');
    }
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      <ScreenHeader
        title="Leaderboard"
        testID="leaderboard-header"
        right={isAdmin ? <HeaderIconButton icon="mail-outline" onPress={sendPowerRankings} testID="send-rankings-btn" /> : undefined}
      />

      <ScrollView style={{ flex: 1 }} contentContainerStyle={{ paddingBottom: 40 }} showsVerticalScrollIndicator={false}>
        {/* Tier Tabs */}
        <View style={{ flexDirection: 'row', gap: 6, paddingHorizontal: 16, paddingTop: 14, paddingBottom: 10 }}>
          {TIERS.map(t => (
            <TouchableOpacity
              key={t.key}
              onPress={() => setTier(t.key)}
              style={{
                flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6,
                paddingVertical: 9, borderRadius: 14, borderWidth: 1,
                backgroundColor: tier === t.key ? colors.accent : colors.card,
                borderColor: tier === t.key ? colors.accent : colors.border,
              }}
              {...tid(`tier-${t.key}`)}
            >
              <Ionicons name={t.icon as any} size={16} color={tier === t.key ? '#000' : colors.textSecondary} />
              <Text style={{ fontSize: FS.secondary, fontWeight: '700', color: tier === t.key ? '#000' : colors.textSecondary, flexShrink: 1 }} numberOfLines={1}>{t.label}</Text>
            </TouchableOpacity>
          ))}
        </View>

        {/* Period Pills */}
        <View style={{ flexDirection: 'row', gap: 6, paddingHorizontal: 16, paddingBottom: 14 }}>
          {PERIODS.map(p => (
            <TouchableOpacity
              key={p.key}
              onPress={() => setPeriod(p.key)}
              style={{
                paddingVertical: 6, paddingHorizontal: 14, borderRadius: 18, borderWidth: 1,
                backgroundColor: period === p.key ? 'rgba(201,169,98,0.12)' : colors.card,
                borderColor: period === p.key ? colors.accent : colors.border,
              }}
              {...tid(`period-${p.key}`)}
            >
              <Text style={{ fontSize: FS.secondary, fontWeight: '700', color: period === p.key ? colors.accent : colors.textSecondary }}>{p.label}</Text>
            </TouchableOpacity>
          ))}
        </View>

        {loading ? (
          <ActivityIndicator size="large" color={colors.accent} style={{ marginTop: 40 }} />
        ) : (
          <>
            {/* Your Rank Card */}
            {yourStats.rank && (
              <View style={{ marginHorizontal: 16, marginBottom: 14, backgroundColor: colors.card, borderRadius: 16, padding: 16, borderWidth: 1, borderColor: colors.border }} {...tid('your-rank-card')}>
                <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
                    <Text style={{ fontSize: FS.display, fontWeight: '800', color: colors.accent }}>#{yourStats.rank}</Text>
                    <View>
                      <Text style={{ fontSize: FS.nav, fontWeight: '700', color: colors.text }}>Your rank</Text>
                      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4, marginTop: 2 }}>
                        <Ionicons name={level.icon as any || 'shield-outline'} size={14} color={level.color || colors.accent} />
                        <Text style={{ fontSize: FS.body, fontWeight: '700', color: level.color || colors.accent }}>{level.title || 'Rookie'}</Text>
                      </View>
                    </View>
                  </View>
                  <View style={{ alignItems: 'flex-end' }}>
                    {yourStats.streak > 0 && (
                      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 3, backgroundColor: 'rgba(255,150,0,0.12)', paddingHorizontal: 8, paddingVertical: 3, borderRadius: 8 }}>
                        <Ionicons name="flame" size={14} color="#FF9500" />
                        <Text style={{ fontSize: FS.secondary, fontWeight: '700', color: '#FF9500' }}>{yourStats.streak}d streak</Text>
                      </View>
                    )}
                    <Text style={{ fontSize: FS.title, fontWeight: '800', color: colors.text, marginTop: 2 }}>{yourStats.scores?.total || 0}</Text>
                    <Text style={{ fontSize: FS.secondary, color: colors.textSecondary }}>total pts</Text>
                  </View>
                </View>

                {/* Level progress bar */}
                <View style={{ marginBottom: 10 }}>
                  <View style={{ backgroundColor: colors.border, borderRadius: 4, height: 6, overflow: 'hidden' }}>
                    <View style={{ height: '100%', backgroundColor: level.color || colors.accent, borderRadius: 4, width: `${level.progress_pct || 0}%` }} />
                  </View>
                  {level.next_level && (
                    <Text style={{ fontSize: FS.caption, color: colors.textTertiary, marginTop: 3, textAlign: 'right' }}>
                      {level.next_at ? level.next_at - (yourStats.scores?.total || 0) : 0} pts to {level.next_level}
                    </Text>
                  )}
                </View>

                {/* You vs Average */}
                <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingTop: 6, borderTopWidth: 1, borderTopColor: colors.border }}>
                  <Ionicons name={yourStats.vs_avg >= 0 ? 'trending-up' : 'trending-down'} size={16} color={yourStats.vs_avg >= 0 ? '#34C759' : '#FF3B30'} />
                  <Text style={{ fontSize: FS.body, color: yourStats.vs_avg >= 0 ? '#34C759' : '#FF3B30', fontWeight: '600' }}>
                    {yourStats.vs_avg >= 0 ? '+' : ''}{yourStats.vs_avg} vs team avg ({yourStats.team_avg})
                  </Text>
                </View>
              </View>
            )}

            {/* Category Filter */}
            <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ paddingHorizontal: 16, gap: 6, paddingBottom: 14 }}>
              {catKeys.map(k => {
                const active = category === k;
                const label = k === 'total' ? 'Total' : cats[k]?.label || k;
                return (
                  <TouchableOpacity
                    key={k}
                    onPress={() => setCategory(k)}
                    style={{
                      paddingVertical: 6, paddingHorizontal: 12, borderRadius: 18, borderWidth: 1,
                      backgroundColor: active ? 'rgba(201,169,98,0.12)' : colors.card,
                      borderColor: active ? colors.accent : colors.border,
                    }}
                    {...tid(`cat-${k}`)}
                  >
                    <Text style={{ fontSize: FS.secondary, fontWeight: '700', color: active ? colors.accent : colors.textSecondary }}>{label}</Text>
                  </TouchableOpacity>
                );
              })}
            </ScrollView>

            {/* Podium: top 3 */}
            {top3.length > 0 && (
              <View style={{ flexDirection: 'row', alignItems: 'flex-end', justifyContent: 'center', gap: 10, paddingHorizontal: 16, paddingBottom: 20, paddingTop: 8 }} {...tid('leaderboard-podium')}>
                {[top3[1], top3[0], top3[2]].map((entry, idx) => {
                  if (!entry) return <View key={idx} style={{ flex: 1 }} />;
                  const podiumOrder = [2, 1, 3][idx];
                  const height = podiumOrder === 1 ? 84 : podiumOrder === 2 ? 64 : 52;
                  const badgeColor = podiumOrder === 1 ? '#FFD700' : podiumOrder === 2 ? '#C0C0C0' : '#CD7F32';
                  const isYou = entry.user_id === user?._id || entry.is_you;
                  const displayName = isGlobal ? (entry.display_name || '???') : (entry.name || 'Unknown');
                  return (
                    <View key={entry.user_id || idx} style={{ flex: 1, alignItems: 'center' }}>
                      <View style={{ width: 48, height: 48, borderRadius: 14, backgroundColor: `${badgeColor}30`, alignItems: 'center', justifyContent: 'center', borderWidth: 2, borderColor: badgeColor, marginBottom: 6, overflow: 'hidden' }}>
                        {entry.photo ? (
                          <Image source={{ uri: entry.photo }} style={{ width: 44, height: 44, borderRadius: 12 }} contentFit="cover" cachePolicy="memory-disk" />
                        ) : (
                          <Text style={{ fontWeight: '800', fontSize: 18, color: badgeColor }}>{getInitials(displayName)}</Text>
                        )}
                      </View>
                      <Text style={{ fontSize: FS.secondary, fontWeight: '700', color: isYou ? colors.accent : colors.text, textAlign: 'center' }} numberOfLines={1}>
                        {isYou ? 'You' : displayName}
                      </Text>
                      <Text style={{ fontSize: 18, fontWeight: '800', color: badgeColor }}>{entry.sort_score || entry.scores?.total || 0}</Text>
                      <View style={{ width: '90%', height, backgroundColor: `${badgeColor}18`, borderTopLeftRadius: 10, borderTopRightRadius: 10, alignItems: 'center', justifyContent: 'flex-start', paddingTop: 6, marginTop: 4 }}>
                        <Text style={{ fontSize: FS.title, fontWeight: '800', color: badgeColor }}>#{podiumOrder}</Text>
                      </View>
                    </View>
                  );
                })}
              </View>
            )}

            {/* Ranked List */}
            {rest.map((entry: any, idx: number) => {
              const rank = entry.rank || idx + 4;
              const isYou = entry.user_id === user?._id || entry.is_you;
              const displayName = isGlobal ? (entry.display_name || '???') : (entry.name || 'Unknown');
              return (
                <View
                  key={entry.user_id || idx}
                  style={{
                    flexDirection: 'row', alignItems: 'center', gap: 12, marginHorizontal: 16, marginBottom: 8,
                    backgroundColor: isYou ? 'rgba(201,169,98,0.08)' : colors.card,
                    borderRadius: 16, padding: 12, paddingHorizontal: 14,
                    borderWidth: 1, borderColor: isYou ? 'rgba(201,169,98,0.3)' : colors.border,
                  }}
                  {...tid(`rank-${rank}`)}
                >
                  <Text style={{ fontSize: FS.heading, fontWeight: '700', color: colors.textSecondary, width: 28, textAlign: 'center' }}>#{rank}</Text>
                  <View style={{ width: 38, height: 38, borderRadius: 10, backgroundColor: isYou ? 'rgba(201,169,98,0.12)' : colors.surface, alignItems: 'center', justifyContent: 'center', overflow: 'hidden' }}>
                    {entry.photo ? (
                      <Image source={{ uri: entry.photo }} style={{ width: 34, height: 34, borderRadius: 8 }} contentFit="cover" cachePolicy="memory-disk" />
                    ) : (
                      <Text style={{ fontWeight: '700', fontSize: FS.body, color: isYou ? colors.accent : colors.textSecondary }}>{getInitials(displayName)}</Text>
                    )}
                  </View>
                  <View style={{ flex: 1, minWidth: 0 }}>
                    <Text style={{ fontSize: FS.heading, fontWeight: '700', color: isYou ? colors.accent : colors.text, flexShrink: 1 }} numberOfLines={1}>
                      {isYou ? `${displayName} (You)` : displayName}
                    </Text>
                    {tier === 'org' && entry.members && (
                      <Text style={{ fontSize: FS.secondary, color: colors.textSecondary }}>{entry.members} members</Text>
                    )}
                  </View>
                  <Text style={{ fontSize: 18, fontWeight: '700', color: colors.text }}>{entry.sort_score || entry.scores?.total || 0}</Text>
                </View>
              );
            })}

            {leaderboard.length === 0 && (
              <View style={{ alignItems: 'center', paddingVertical: 40, paddingHorizontal: 32 }} {...tid('leaderboard-empty')}>
                <Ionicons name="trophy-outline" size={48} color={colors.textTertiary} />
                <Text style={{ fontSize: FS.heading, fontWeight: '700', color: colors.text, marginTop: 12 }}>No rankings yet</Text>
                <Text style={{ fontSize: FS.body, color: colors.textSecondary, marginTop: 4, textAlign: 'center' }}>Complete touchpoints to earn points and climb the ranks.</Text>
                <TouchableOpacity onPress={() => router.push('/(tabs)/touchpoints' as any)} style={{ marginTop: 18, backgroundColor: colors.accent, borderRadius: 14, paddingHorizontal: 22, paddingVertical: 12 }} {...tid('leaderboard-open-touchpoints')}>
                  <Text style={{ fontSize: FS.heading, fontWeight: '700', color: '#000' }}>Open Touchpoints</Text>
                </TouchableOpacity>
              </View>
            )}
          </>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}
