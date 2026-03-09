import React, { useState, useEffect } from 'react';
import {
  View, Text, ScrollView, ActivityIndicator, TouchableOpacity,
  Image, StyleSheet,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import api from '../../services/api';
import { useAuthStore } from '../../store/authStore';

const colors = {
  bg: '#000000',
  card: '#1C1C1E',
  surface: '#2C2C2E',
  text: '#FFFFFF',
  textSecondary: '#8E8E93',
  gold: '#C9A962',
  green: '#34C759',
  red: '#FF3B30',
  blue: '#007AFF',
};

function formatTimeAgo(iso: string) {
  if (!iso) return '';
  const d = new Date(iso);
  const now = new Date();
  const mins = Math.floor((now.getTime() - d.getTime()) / 60000);
  if (mins < 1) return 'Just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days < 7) return `${days}d ago`;
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

export default function CrmDashboard() {
  const router = useRouter();
  const { user } = useAuthStore();
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!user?._id) return;
    (async () => {
      try {
        const res = await api.get(`/crm/adoption-dashboard/${user._id}`);
        setData(res.data);
      } catch (e) {
        console.error('Failed to load CRM dashboard:', e);
      } finally {
        setLoading(false);
      }
    })();
  }, [user]);

  if (loading) {
    return (
      <View style={s.loadingWrap}>
        <ActivityIndicator size="large" color={colors.gold} />
      </View>
    );
  }

  if (!data) {
    return (
      <View style={s.loadingWrap}>
        <Ionicons name="alert-circle-outline" size={40} color={colors.red} />
        <Text style={s.emptyText}>Failed to load dashboard</Text>
      </View>
    );
  }

  const { total_contacts, total_linked, total_not_linked, overall_pct, members, recent_activity } = data;

  return (
    <ScrollView style={s.page} data-testid="crm-adoption-dashboard">
      {/* Header */}
      <View style={s.header}>
        <TouchableOpacity onPress={() => router.back()} style={s.backBtn} data-testid="crm-dash-back">
          <Ionicons name="chevron-back" size={24} color={colors.text} />
        </TouchableOpacity>
        <Text style={s.title}>CRM Adoption</Text>
        <View style={{ width: 32 }} />
      </View>

      {/* Overall Progress */}
      <View style={s.overallCard} data-testid="crm-overall-stats">
        <View style={s.overallTop}>
          <View style={s.overallStat}>
            <Text style={s.overallNum}>{total_linked}</Text>
            <Text style={s.overallLabel}>Linked</Text>
          </View>
          <View style={s.overallCenter}>
            <Text style={s.overallPct}>{overall_pct}%</Text>
            <Text style={s.overallLabel}>Adoption</Text>
          </View>
          <View style={s.overallStat}>
            <Text style={[s.overallNum, { color: total_not_linked > 0 ? colors.red : colors.green }]}>
              {total_not_linked}
            </Text>
            <Text style={s.overallLabel}>Not Linked</Text>
          </View>
        </View>

        {/* Progress Bar */}
        <View style={s.progressTrack}>
          <View style={[s.progressFill, { width: `${Math.min(overall_pct, 100)}%` }]} />
        </View>
        <Text style={s.progressSubtext}>{total_linked} of {total_contacts} contacts have CRM links</Text>
      </View>

      {/* Team Breakdown */}
      <View style={s.section}>
        <Text style={s.sectionTitle}>Team Breakdown</Text>
        {members.map((m: any, idx: number) => (
          <View key={m.user_id} style={s.memberRow} data-testid={`crm-member-${idx}`}>
            <View style={s.memberLeft}>
              <View style={s.rankBadge}>
                <Text style={s.rankText}>#{idx + 1}</Text>
              </View>
              {m.photo ? (
                <Image source={{ uri: m.photo }} style={s.memberAvatar} />
              ) : (
                <View style={s.memberAvatarPlaceholder}>
                  <Text style={s.memberInitials}>
                    {(m.name || '?').split(' ').map((w: string) => w[0]).join('').slice(0, 2).toUpperCase()}
                  </Text>
                </View>
              )}
              <View style={s.memberInfo}>
                <Text style={s.memberName}>{m.name}</Text>
                <Text style={s.memberTitle}>{m.title || m.role || ''}</Text>
              </View>
            </View>
            <View style={s.memberRight}>
              <View style={s.memberProgressWrap}>
                <View style={s.memberProgressTrack}>
                  <View style={[
                    s.memberProgressFill,
                    {
                      width: `${Math.min(m.pct, 100)}%`,
                      backgroundColor: m.pct >= 75 ? colors.green : m.pct >= 40 ? colors.gold : colors.red,
                    }
                  ]} />
                </View>
                <Text style={[
                  s.memberPct,
                  { color: m.pct >= 75 ? colors.green : m.pct >= 40 ? colors.gold : colors.red }
                ]}>{m.pct}%</Text>
              </View>
              <Text style={s.memberStats}>{m.crm_linked}/{m.total_contacts} linked</Text>
            </View>
          </View>
        ))}
        {members.length === 0 && (
          <Text style={s.emptyText}>No team members found</Text>
        )}
      </View>

      {/* Recent Activity */}
      <View style={s.section}>
        <Text style={s.sectionTitle}>Recent Links Copied</Text>
        {recent_activity && recent_activity.length > 0 ? (
          recent_activity.map((r: any, idx: number) => (
            <View key={idx} style={s.recentRow}>
              <View style={s.recentDot}>
                <Ionicons name="link-outline" size={14} color={colors.gold} />
              </View>
              <View style={s.recentContent}>
                <Text style={s.recentName}>{r.contact_name}</Text>
                <Text style={s.recentSub}>by {r.salesperson}</Text>
              </View>
              <Text style={s.recentTime}>{formatTimeAgo(r.copied_at)}</Text>
            </View>
          ))
        ) : (
          <View style={s.emptyCard}>
            <Ionicons name="link-outline" size={32} color="#444" />
            <Text style={s.emptyText}>No CRM links copied yet</Text>
            <Text style={s.emptySubtext}>Links will show here as your team copies them</Text>
          </View>
        )}
      </View>

      <View style={{ height: 40 }} />
    </ScrollView>
  );
}

const s = StyleSheet.create({
  page: { flex: 1, backgroundColor: colors.bg },
  loadingWrap: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: colors.bg, minHeight: 400, gap: 12 },

  // Header
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingTop: 56, paddingBottom: 16 },
  backBtn: { width: 32, height: 32, justifyContent: 'center' },
  title: { fontSize: 20, fontWeight: '800', color: colors.text, letterSpacing: 0.5 },

  // Overall Card
  overallCard: { marginHorizontal: 16, backgroundColor: colors.card, borderRadius: 16, padding: 20, marginBottom: 20 },
  overallTop: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 },
  overallStat: { alignItems: 'center', flex: 1 },
  overallCenter: { alignItems: 'center', flex: 1 },
  overallNum: { fontSize: 28, fontWeight: '800', color: colors.text },
  overallPct: { fontSize: 36, fontWeight: '900', color: colors.gold },
  overallLabel: { fontSize: 12, color: colors.textSecondary, marginTop: 2, fontWeight: '600' },
  progressTrack: { height: 8, backgroundColor: colors.surface, borderRadius: 4, overflow: 'hidden' as const },
  progressFill: { height: '100%' as any, backgroundColor: colors.gold, borderRadius: 4 },
  progressSubtext: { fontSize: 12, color: colors.textSecondary, textAlign: 'center' as const, marginTop: 8 },

  // Section
  section: { marginHorizontal: 16, marginBottom: 20 },
  sectionTitle: { fontSize: 16, fontWeight: '700', color: colors.text, marginBottom: 12, letterSpacing: 0.5 },

  // Member Row
  memberRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', backgroundColor: colors.card, borderRadius: 12, padding: 14, marginBottom: 8 },
  memberLeft: { flexDirection: 'row', alignItems: 'center', flex: 1, gap: 10 },
  rankBadge: { width: 24, height: 24, borderRadius: 12, backgroundColor: colors.surface, justifyContent: 'center', alignItems: 'center' },
  rankText: { fontSize: 11, fontWeight: '700', color: colors.textSecondary },
  memberAvatar: { width: 36, height: 36, borderRadius: 18 },
  memberAvatarPlaceholder: { width: 36, height: 36, borderRadius: 18, backgroundColor: colors.surface, justifyContent: 'center', alignItems: 'center' },
  memberInitials: { fontSize: 14, fontWeight: '700', color: colors.textSecondary },
  memberInfo: { flex: 1 },
  memberName: { fontSize: 14, fontWeight: '700', color: colors.text },
  memberTitle: { fontSize: 11, color: colors.textSecondary },
  memberRight: { alignItems: 'flex-end', minWidth: 100 },
  memberProgressWrap: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  memberProgressTrack: { width: 60, height: 6, backgroundColor: colors.surface, borderRadius: 3, overflow: 'hidden' as const },
  memberProgressFill: { height: '100%' as any, borderRadius: 3 },
  memberPct: { fontSize: 13, fontWeight: '800', minWidth: 36, textAlign: 'right' as const },
  memberStats: { fontSize: 11, color: colors.textSecondary, marginTop: 2 },

  // Recent Activity
  recentRow: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: colors.surface },
  recentDot: { width: 28, height: 28, borderRadius: 14, backgroundColor: '#C9A96215', justifyContent: 'center', alignItems: 'center' },
  recentContent: { flex: 1 },
  recentName: { fontSize: 14, fontWeight: '600', color: colors.text },
  recentSub: { fontSize: 12, color: colors.textSecondary },
  recentTime: { fontSize: 11, color: colors.textSecondary },

  // Empty
  emptyCard: { alignItems: 'center', paddingVertical: 32, gap: 8, backgroundColor: colors.card, borderRadius: 12 },
  emptyText: { fontSize: 14, color: '#666' },
  emptySubtext: { fontSize: 12, color: '#444', textAlign: 'center' as const },
});
