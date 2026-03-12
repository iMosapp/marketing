import React, { useState, useEffect, useCallback } from 'react';
import {
  View, Text, ScrollView, TouchableOpacity, StyleSheet, ActivityIndicator,
  SafeAreaView, Image, Platform,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { leaderboardAPI } from '../../services/api';
import { useAuthStore } from '../../store/authStore';
import { useThemeStore } from '../../store/themeStore';
const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
const PERIODS = [
  { key: 'week', label: 'This Week' },
  { key: 'month', label: 'This Month' },
  { key: 'all', label: 'All Time' },
];
const LEVELS = [
  { key: 'store', label: 'My Store', icon: 'storefront' },
  { key: 'org', label: 'All Stores', icon: 'business' },
  { key: 'global', label: 'Global', icon: 'globe' },
];
const ALL_CATEGORIES = [
  { key: 'total', label: 'All', icon: 'trophy' },
  { key: 'digital_cards', label: 'Cards', icon: 'card' },
  { key: 'reviews', label: 'Reviews', icon: 'star' },
  { key: 'congrats', label: 'Congrats', icon: 'gift' },
  { key: 'emails', label: 'Emails', icon: 'mail' },
  { key: 'sms', label: 'SMS', icon: 'chatbubble' },
  { key: 'voice_notes', label: 'Notes', icon: 'mic' },
];

export default function LeaderboardPage() {
  const { colors } = useThemeStore();
  const s = getS(colors);
  const router = useRouter();
  const user = useAuthStore((state) => state.user);
  const [level, setLevel] = useState('store');
  const [category, setCategory] = useState('total');
  const [period, setPeriod] = useState('month');
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<Record<number, boolean>>({});

  const loadData = useCallback(async () => {
    if (!user?._id) return;
    setLoading(true);
    try {
      let result;
      if (level === 'store') result = await leaderboardAPI.getStore(user._id, undefined, undefined, category, period);
      else if (level === 'org') result = await leaderboardAPI.getOrg(user._id, undefined, undefined, category, period);
      else result = await leaderboardAPI.getGlobal(user._id, undefined, undefined, category, period);
      setData(result);
    } catch (e) {
      console.error('Leaderboard load error:', e);
    } finally {
      setLoading(false);
    }
  }, [user?._id, level, category, period]);

  useEffect(() => { loadData(); }, [loadData]);

  const getBadgeColor = (badge: string | null) => {
    if (badge === 'gold') return '#FFD700';
    if (badge === 'silver') return '#C0C0C0';
    if (badge === 'bronze') return '#CD7F32';
    return null;
  };

  const getBadgeIcon = (badge: string | null): string => {
    if (badge === 'gold') return 'medal';
    if (badge === 'silver') return 'medal-outline';
    if (badge === 'bronze') return 'ribbon';
    return '';
  };

  const renderEntry = (entry: any, index: number) => {
    const isExpanded = expanded[index];
    const badgeColor = getBadgeColor(entry.badge);
    const isYou = entry.user_id === user?._id;
    const displayName = level === 'global' ? (entry.display_name || `User #${entry.rank}`) : (entry.name || entry.store_name || 'Unknown');
    const scores = entry.scores || {};

    return (
      <View key={index} style={[s.card, isYou && s.cardYou]} data-testid={`lb-entry-${index}`}>
        <TouchableOpacity
          style={s.cardHeader}
          onPress={() => setExpanded(prev => ({ ...prev, [index]: !prev[index] }))}
          activeOpacity={0.7}
        >
          {/* Rank + Badge */}
          <View style={s.rankCol}>
            {badgeColor ? (
              <View style={[s.badge, { backgroundColor: badgeColor }]}>
                <Text style={s.badgeText}>{entry.rank}</Text>
              </View>
            ) : (
              <Text style={s.rankText}>{entry.rank}</Text>
            )}
          </View>

          {/* Avatar */}
          <View style={[s.avatar, { backgroundColor: badgeColor ? `${badgeColor}30` : colors.surface }]}>
            {entry.photo ? (
              <Image source={{ uri: entry.photo }} style={s.avatarImg} />
            ) : (
              <Text style={s.avatarText}>{displayName.charAt(0).toUpperCase()}</Text>
            )}
            {badgeColor && entry.rank === 1 && (
              <View style={s.crownWrap}>
                <Ionicons name="trophy" size={10} color="#FFD700" />
              </View>
            )}
          </View>

          {/* Name + role */}
          <View style={s.nameCol}>
            <Text style={s.entryName} numberOfLines={1}>
              {displayName} {isYou ? '(You)' : ''}
            </Text>
            {entry.role ? <Text style={s.entryRole}>{entry.role}</Text> : null}
            {level === 'org' && entry.members ? <Text style={s.entryRole}>{entry.members} members</Text> : null}
          </View>

          {/* Score  - shows category-specific score when filtered */}
          <View style={s.scoreCol}>
            <Text style={s.scoreNum}>
              {category === 'total' ? (scores.total ?? entry.sort_score ?? 0) : (scores[category] ?? entry.sort_score ?? 0)}
            </Text>
            <Text style={s.scoreLabel}>
              {category === 'total' ? 'TOTAL' : ALL_CATEGORIES.find(c => c.key === category)?.label?.toUpperCase() || 'TOTAL'}
            </Text>
          </View>

          <Ionicons name={isExpanded ? 'chevron-up' : 'chevron-down'} size={16} color={colors.textTertiary} />
        </TouchableOpacity>

        {/* Expanded stats */}
        {isExpanded && (
          <View style={s.statsRow}>
            {ALL_CATEGORIES.filter(c => c.key !== 'total').map(cat => (
              <View key={cat.key} style={s.statBox}>
                <Text style={s.statNum}>{scores[cat.key] ?? 0}</Text>
                <Text style={s.statLabel}>{cat.label}</Text>
              </View>
            ))}
          </View>
        )}
      </View>
    );
  };

  const summary = data?.team_summary;
  const leaderboard = data?.leaderboard || [];

  return (
    <SafeAreaView style={s.safe}>
      {/* Header */}
      <View style={s.header}>
        <TouchableOpacity onPress={() => router.back()} style={s.backBtn} data-testid="lb-back-btn">
          <Ionicons name="chevron-back" size={24} color={colors.text} />
        </TouchableOpacity>
        <View style={s.headerCenter}>
          <Ionicons name="trophy" size={20} color="#FFD700" />
          <Text style={s.headerTitle}>LEADERBOARD</Text>
        </View>
        <View style={s.membersBadge}>
          <Text style={s.membersText}>{data?.members || data?.stores || data?.total_users || 0}</Text>
        </View>
      </View>

      {/* Level Tabs */}
      <View style={s.levelRow}>
        {LEVELS.map(lv => (
          <TouchableOpacity
            key={lv.key}
            style={[s.levelTab, level === lv.key && s.levelTabActive]}
            onPress={() => { setLevel(lv.key); setExpanded({}); }}
            data-testid={`lb-level-${lv.key}`}
          >
            <Ionicons name={lv.icon as any} size={14} color={level === lv.key ? '#C9A962' : colors.textTertiary} />
            <Text style={[s.levelText, level === lv.key && s.levelTextActive]}>{lv.label}</Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* Period Selector */}
      <View style={s.monthRow}>
        {PERIODS.map(p => (
          <TouchableOpacity
            key={p.key}
            style={[s.periodTab, period === p.key && s.periodTabActive]}
            onPress={() => { setPeriod(p.key); setExpanded({}); }}
            data-testid={`lb-period-${p.key}`}
          >
            <Text style={[s.periodText, period === p.key && s.periodTextActive]}>{p.label}</Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* Category Pills */}
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={s.catScroll} contentContainerStyle={s.catRow}>
        {ALL_CATEGORIES.map(cat => (
          <TouchableOpacity
            key={cat.key}
            style={[s.catPill, category === cat.key && s.catPillActive]}
            onPress={() => { setCategory(cat.key); setExpanded({}); }}
            data-testid={`lb-cat-${cat.key}`}
          >
            <Ionicons name={cat.icon as any} size={14} color={category === cat.key ? '#000' : '#AEAEB2'} />
            <Text style={[s.catText, category === cat.key && s.catTextActive]}>{cat.label}</Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      {/* Leaderboard List */}
      <ScrollView style={s.list} contentContainerStyle={s.listContent}>
        {loading ? (
          <ActivityIndicator size="large" color="#C9A962" style={{ marginTop: 60 }} />
        ) : leaderboard.length === 0 ? (
          <View style={s.empty}>
            <Ionicons name="trophy-outline" size={48} color={colors.surface} />
            <Text style={s.emptyTitle}>No activity yet</Text>
            <Text style={s.emptySub}>Start sending cards and reviews to climb the leaderboard!</Text>
          </View>
        ) : (
          leaderboard.map((entry: any, i: number) => renderEntry(entry, i))
        )}
      </ScrollView>

      {/* Team Summary Footer */}
      {summary && !loading && (
        <View style={s.footer} data-testid="lb-team-summary">
          <View style={s.footerStat}>
            <Text style={s.footerNum}>{summary.team_total ?? summary.platform_total ?? 0}</Text>
            <Text style={s.footerLabel}>{level === 'global' ? 'PLATFORM' : 'TEAM'} TOTAL</Text>
          </View>
          <View style={s.footerDivider} />
          <View style={s.footerStat}>
            <Text style={s.footerNum}>{summary.members ?? summary.active_users ?? 0}</Text>
            <Text style={s.footerLabel}>{level === 'global' ? 'ACTIVE' : 'MEMBERS'}</Text>
          </View>
          <View style={s.footerDivider} />
          <View style={s.footerStat}>
            <Text style={s.footerNum}>{summary.avg_score ?? 0}</Text>
            <Text style={s.footerLabel}>AVG SCORE</Text>
          </View>
        </View>
      )}
    </SafeAreaView>
  );
}

const getS = (colors: any) => StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 12 },
  backBtn: { padding: 4 },
  headerCenter: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  headerTitle: { fontSize: 18, fontWeight: '800', color: colors.text, letterSpacing: 1.5 },
  membersBadge: { backgroundColor: '#007AFF', borderRadius: 12, paddingHorizontal: 10, paddingVertical: 3 },
  membersText: { fontSize: 12, fontWeight: '700', color: '#FFFFFF' },
  // Level tabs
  levelRow: { flexDirection: 'row', paddingHorizontal: 16, gap: 8, marginBottom: 12 },
  levelTab: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingVertical: 8, borderRadius: 10, backgroundColor: colors.card },
  levelTabActive: { backgroundColor: '#C9A96220', borderWidth: 1, borderColor: '#C9A96250' },
  levelText: { fontSize: 13, fontWeight: '600', color: colors.textSecondary },
  levelTextActive: { color: '#C9A962' },
  // Period tabs
  monthRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, marginBottom: 10, paddingHorizontal: 16 },
  periodTab: { flex: 1, alignItems: 'center', paddingVertical: 7, borderRadius: 8, backgroundColor: colors.card },
  periodTabActive: { backgroundColor: '#C9A96220', borderWidth: 1, borderColor: '#C9A96250' },
  periodText: { fontSize: 13, fontWeight: '600', color: colors.textSecondary },
  periodTextActive: { color: '#C9A962', fontWeight: '700' },
  // Category pills
  catScroll: { maxHeight: 44, marginBottom: 8 },
  catRow: { paddingHorizontal: 16, gap: 8 },
  catPill: { flexDirection: 'row', alignItems: 'center', gap: 5, paddingHorizontal: 12, paddingVertical: 7, borderRadius: 20, backgroundColor: colors.card },
  catPillActive: { backgroundColor: '#C9A962' },
  catText: { fontSize: 12, fontWeight: '600', color: colors.textSecondary },
  catTextActive: { color: colors.accentText },
  // List
  list: { flex: 1 },
  listContent: { paddingHorizontal: 16, paddingBottom: 20 },
  // Card
  card: { backgroundColor: colors.card, borderRadius: 14, marginBottom: 8, overflow: 'hidden' },
  cardYou: { borderWidth: 1, borderColor: '#C9A96250' },
  cardHeader: { flexDirection: 'row', alignItems: 'center', paddingVertical: 12, paddingHorizontal: 14, gap: 10 },
  rankCol: { width: 28, alignItems: 'center' },
  badge: { width: 24, height: 24, borderRadius: 12, justifyContent: 'center', alignItems: 'center' },
  badgeText: { fontSize: 12, fontWeight: '800', color: '#000000' },
  rankText: { fontSize: 14, fontWeight: '700', color: colors.textSecondary },
  avatar: { width: 40, height: 40, borderRadius: 10, justifyContent: 'center', alignItems: 'center', overflow: 'hidden' },
  avatarImg: { width: 40, height: 40, borderRadius: 10 },
  avatarText: { fontSize: 16, fontWeight: '700', color: colors.text },
  crownWrap: { position: 'absolute', top: -2, right: -2, backgroundColor: colors.card, borderRadius: 8, padding: 1 },
  nameCol: { flex: 1 },
  entryName: { fontSize: 14, fontWeight: '700', color: colors.text },
  entryRole: { fontSize: 11, color: colors.textSecondary },
  scoreCol: { alignItems: 'flex-end', marginRight: 4 },
  scoreNum: { fontSize: 20, fontWeight: '800', color: '#34C759' },
  scoreLabel: { fontSize: 9, fontWeight: '600', color: colors.textSecondary, letterSpacing: 1 },
  // Expanded stats
  statsRow: { flexDirection: 'row', flexWrap: 'wrap', paddingHorizontal: 14, paddingBottom: 12, gap: 6 },
  statBox: { backgroundColor: colors.surface, borderRadius: 8, paddingVertical: 6, paddingHorizontal: 10, alignItems: 'center', minWidth: 56 },
  statNum: { fontSize: 16, fontWeight: '800', color: colors.text },
  statLabel: { fontSize: 9, color: colors.textTertiary, marginTop: 2 },
  // Empty
  empty: { alignItems: 'center', paddingTop: 60, gap: 8 },
  emptyTitle: { fontSize: 18, fontWeight: '700', color: colors.borderLight },
  emptySub: { fontSize: 14, color: colors.textSecondary, textAlign: 'center', paddingHorizontal: 40 },
  // Footer
  footer: { flexDirection: 'row', backgroundColor: colors.card, borderTopWidth: 1, borderTopColor: colors.surface, paddingVertical: 12, paddingHorizontal: 16 },
  footerStat: { flex: 1, alignItems: 'center' },
  footerNum: { fontSize: 18, fontWeight: '800', color: '#34C759' },
  footerLabel: { fontSize: 9, fontWeight: '600', color: colors.textSecondary, letterSpacing: 0.5, marginTop: 2 },
  footerDivider: { width: 1, backgroundColor: colors.surface, marginVertical: 4 },
});
