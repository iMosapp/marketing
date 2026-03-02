import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import api from '../../services/api';

import { useThemeStore } from '../../store/themeStore';
export default function TeamReportScreen() {
  const { colors } = useThemeStore();
  const styles = getStyles(colors);
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [period, setPeriod] = useState(30);
  const [data, setData] = useState<any>(null);

  useEffect(() => {
    loadData();
  }, [period]);

  const loadData = async () => {
    try {
      setLoading(true);
      const response = await api.get(`/reports/team?days=${period}`);
      setData(response.data);
    } catch (err) {
      console.error('Failed to load team report:', err);
    } finally {
      setLoading(false);
    }
  };

  const getRoleColor = (role: string) => {
    switch (role) {
      case 'super_admin': return '#FF3B30';
      case 'org_admin': return '#FF9500';
      case 'store_manager': return '#007AFF';
      default: return '#34C759';
    }
  };

  const getRoleLabel = (role: string) => {
    switch (role) {
      case 'super_admin': return 'Admin';
      case 'org_admin': return 'Org Admin';
      case 'store_manager': return 'Manager';
      default: return 'User';
    }
  };

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="chevron-back" size={28} color="#007AFF" />
        </TouchableOpacity>
        <Text style={styles.title}>Team Performance</Text>
        <View style={{ width: 40 }} />
      </View>

      {/* Period Selector */}
      <View style={styles.periodSelector}>
        {[7, 30, 90].map((days) => (
          <TouchableOpacity
            key={days}
            style={[styles.periodButton, period === days && styles.periodButtonActive]}
            onPress={() => setPeriod(days)}
          >
            <Text style={[styles.periodText, period === days && styles.periodTextActive]}>
              {days}D
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {loading ? (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#007AFF" />
        </View>
      ) : (
        <ScrollView contentContainerStyle={styles.scrollContent}>
          {/* Totals */}
          <View style={styles.totalsRow}>
            <View style={styles.totalCard}>
              <Ionicons name="people" size={24} color="#007AFF" />
              <Text style={styles.totalValue}>{data?.totals?.total_members || 0}</Text>
              <Text style={styles.totalLabel}>Team Members</Text>
            </View>
            <View style={styles.totalCard}>
              <Ionicons name="chatbubbles" size={24} color="#34C759" />
              <Text style={styles.totalValue}>{data?.totals?.total_messages || 0}</Text>
              <Text style={styles.totalLabel}>Total Messages</Text>
            </View>
            <View style={styles.totalCard}>
              <Ionicons name="person-add" size={24} color="#FF9500" />
              <Text style={styles.totalValue}>{data?.totals?.total_contacts || 0}</Text>
              <Text style={styles.totalLabel}>Contacts Added</Text>
            </View>
          </View>

          {/* Leaderboard */}
          <Text style={styles.sectionTitle}>Performance Ranking</Text>
          
          {data?.team_members?.map((member: any, index: number) => (
            <TouchableOpacity
              key={member._id}
              style={styles.memberCard}
              onPress={() => router.push(`/admin/users/${member._id}`)}
            >
              <View style={styles.rankBadge}>
                <Text style={[
                  styles.rankText,
                  index < 3 && { color: ['#FFD700', '#C0C0C0', '#CD7F32'][index] }
                ]}>
                  #{index + 1}
                </Text>
              </View>
              
              <View style={[styles.memberAvatar, { backgroundColor: `${getRoleColor(member.role)}20` }]}>
                <Text style={[styles.avatarText, { color: getRoleColor(member.role) }]}>
                  {member.name?.charAt(0)?.toUpperCase() || '?'}
                </Text>
              </View>
              
              <View style={styles.memberInfo}>
                <Text style={styles.memberName}>{member.name}</Text>
                <View style={styles.memberMeta}>
                  <View style={[styles.roleBadge, { backgroundColor: `${getRoleColor(member.role)}20` }]}>
                    <Text style={[styles.roleText, { color: getRoleColor(member.role) }]}>
                      {getRoleLabel(member.role)}
                    </Text>
                  </View>
                  {member.last_active && (
                    <Text style={styles.lastActive}>
                      Active {new Date(member.last_active).toLocaleDateString()}
                    </Text>
                  )}
                </View>
              </View>
              
              <View style={styles.memberStats}>
                <View style={styles.statColumn}>
                  <Text style={styles.statValue}>{member.messages_sent}</Text>
                  <Text style={styles.statLabel}>msgs</Text>
                </View>
                <View style={styles.statColumn}>
                  <Text style={styles.statValue}>{member.contacts_added}</Text>
                  <Text style={styles.statLabel}>contacts</Text>
                </View>
              </View>
            </TouchableOpacity>
          ))}

          <View style={{ height: 40 }} />
        </ScrollView>
      )}
    </SafeAreaView>
  );
}

const getStyles = (colors: any) => StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  loadingContainer: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: colors.surface,
  },
  backButton: { padding: 4 },
  title: { fontSize: 18, fontWeight: 'bold', color: colors.text },
  periodSelector: { flexDirection: 'row', padding: 16, gap: 8 },
  periodButton: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 20,
    backgroundColor: colors.card,
  },
  periodButtonActive: { backgroundColor: '#007AFF' },
  periodText: { color: colors.textSecondary, fontWeight: '600' },
  periodTextActive: { color: colors.text },
  scrollContent: { padding: 16 },
  totalsRow: { flexDirection: 'row', gap: 10, marginBottom: 24 },
  totalCard: {
    flex: 1,
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 14,
    alignItems: 'center',
  },
  totalValue: { fontSize: 22, fontWeight: '700', color: colors.text, marginTop: 8 },
  totalLabel: { fontSize: 11, color: colors.textSecondary, marginTop: 2 },
  sectionTitle: { fontSize: 16, fontWeight: '700', color: colors.text, marginBottom: 12 },
  memberCard: {
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 14,
    marginBottom: 10,
    flexDirection: 'row',
    alignItems: 'center',
  },
  rankBadge: {
    width: 32,
    alignItems: 'center',
  },
  rankText: {
    fontSize: 14,
    fontWeight: '700',
    color: colors.textSecondary,
  },
  memberAvatar: {
    width: 44,
    height: 44,
    borderRadius: 22,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  avatarText: {
    fontSize: 18,
    fontWeight: '700',
  },
  memberInfo: {
    flex: 1,
  },
  memberName: {
    fontSize: 15,
    fontWeight: '600',
    color: colors.text,
  },
  memberMeta: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginTop: 4,
  },
  roleBadge: {
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
  },
  roleText: {
    fontSize: 10,
    fontWeight: '600',
  },
  lastActive: {
    fontSize: 11,
    color: colors.textSecondary,
  },
  memberStats: {
    flexDirection: 'row',
    gap: 16,
  },
  statColumn: {
    alignItems: 'center',
  },
  statValue: {
    fontSize: 16,
    fontWeight: '700',
    color: colors.text,
  },
  statLabel: {
    fontSize: 10,
    color: colors.textSecondary,
  },
});
