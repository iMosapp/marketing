import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  Dimensions,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import api from '../../services/api';

import { useThemeStore } from '../../store/themeStore';
const { width } = Dimensions.get('window');

export default function PersonalReportScreen() {
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
      const response = await api.get(`/reports/personal?days=${period}`);
      setData(response.data);
    } catch (err) {
      console.error('Failed to load personal report:', err);
    } finally {
      setLoading(false);
    }
  };

  const maxActivity = Math.max(...(data?.activity?.daily_breakdown?.map((d: any) => d.messages) || [1]));

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="chevron-back" size={28} color="#007AFF" />
        </TouchableOpacity>
        <Text style={styles.title}>My Performance</Text>
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
          {/* User Info */}
          <View style={styles.userCard}>
            <View style={styles.userAvatar}>
              <Text style={styles.avatarText}>
                {data?.user?.name?.charAt(0)?.toUpperCase() || '?'}
              </Text>
            </View>
            <View>
              <Text style={styles.userName}>{data?.user?.name}</Text>
              <Text style={styles.userRole}>{data?.user?.role?.replace('_', ' ')}</Text>
            </View>
          </View>

          {/* Summary Stats */}
          <View style={styles.statsGrid}>
            <View style={[styles.statCard, { borderLeftColor: '#007AFF' }]}>
              <Ionicons name="chatbubbles" size={24} color="#007AFF" />
              <Text style={styles.statValue}>{data?.messaging?.total_messages || 0}</Text>
              <Text style={styles.statLabel}>Messages Sent</Text>
            </View>
            <View style={[styles.statCard, { borderLeftColor: '#34C759' }]}>
              <Ionicons name="trending-up" size={24} color="#34C759" />
              <Text style={styles.statValue}>{data?.messaging?.avg_per_day || 0}</Text>
              <Text style={styles.statLabel}>Avg/Day</Text>
            </View>
            <View style={[styles.statCard, { borderLeftColor: '#FF9500' }]}>
              <Ionicons name="person-add" size={24} color="#FF9500" />
              <Text style={styles.statValue}>{data?.contacts?.new_contacts || 0}</Text>
              <Text style={styles.statLabel}>New Contacts</Text>
            </View>
            <View style={[styles.statCard, { borderLeftColor: '#AF52DE' }]}>
              <Ionicons name="people" size={24} color="#AF52DE" />
              <Text style={styles.statValue}>{data?.contacts?.total_contacts || 0}</Text>
              <Text style={styles.statLabel}>Total Contacts</Text>
            </View>
          </View>

          {/* Messaging Breakdown */}
          <Text style={styles.sectionTitle}>Messaging Breakdown</Text>
          <View style={styles.breakdownCard}>
            <View style={styles.breakdownRow}>
              <View style={styles.breakdownItem}>
                <View style={[styles.breakdownIcon, { backgroundColor: '#34C75920' }]}>
                  <Ionicons name="chatbubble" size={20} color="#34C759" />
                </View>
                <Text style={styles.breakdownValue}>{data?.messaging?.sms_sent || 0}</Text>
                <Text style={styles.breakdownLabel}>SMS</Text>
              </View>
              <View style={styles.breakdownItem}>
                <View style={[styles.breakdownIcon, { backgroundColor: '#007AFF20' }]}>
                  <Ionicons name="mail" size={20} color="#007AFF" />
                </View>
                <Text style={styles.breakdownValue}>{data?.messaging?.emails_sent || 0}</Text>
                <Text style={styles.breakdownLabel}>Emails</Text>
              </View>
              <View style={styles.breakdownItem}>
                <View style={[styles.breakdownIcon, { backgroundColor: '#5AC8FA20' }]}>
                  <Ionicons name="chatbubbles" size={20} color="#5AC8FA" />
                </View>
                <Text style={styles.breakdownValue}>{data?.activity?.conversations_active || 0}</Text>
                <Text style={styles.breakdownLabel}>Conversations</Text>
              </View>
            </View>
          </View>

          {/* Activity Chart */}
          <Text style={styles.sectionTitle}>Recent Activity</Text>
          <View style={styles.chartCard}>
            <View style={styles.chartContainer}>
              {data?.activity?.daily_breakdown?.map((day: any, index: number) => (
                <View key={day.date} style={styles.chartColumn}>
                  <View style={styles.barWrapper}>
                    <View
                      style={[
                        styles.activityBar,
                        { height: Math.max((day.messages / maxActivity) * 80, 4) },
                      ]}
                    />
                  </View>
                  <Text style={styles.chartLabel}>
                    {new Date(day.date).getDate()}
                  </Text>
                </View>
              ))}
            </View>
            <View style={styles.chartFooter}>
              <Text style={styles.chartFooterText}>Messages per day (last 14 days)</Text>
            </View>
          </View>

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
  title: { fontSize: 19, fontWeight: 'bold', color: colors.text },
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
  userCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 16,
    marginBottom: 20,
    gap: 14,
  },
  userAvatar: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: '#007AFF20',
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarText: {
    fontSize: 24,
    fontWeight: '700',
    color: '#007AFF',
  },
  userName: {
    fontSize: 19,
    fontWeight: '700',
    color: colors.text,
  },
  userRole: {
    fontSize: 16,
    color: colors.textSecondary,
    textTransform: 'capitalize',
    marginTop: 2,
  },
  statsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
    marginBottom: 24,
  },
  statCard: {
    width: (width - 42) / 2,
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 16,
    borderLeftWidth: 3,
    alignItems: 'center',
  },
  statValue: {
    fontSize: 28,
    fontWeight: '700',
    color: colors.text,
    marginTop: 8,
  },
  statLabel: {
    fontSize: 14,
    color: colors.textSecondary,
    marginTop: 4,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: colors.text,
    marginBottom: 12,
  },
  breakdownCard: {
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 20,
    marginBottom: 24,
  },
  breakdownRow: {
    flexDirection: 'row',
    justifyContent: 'space-around',
  },
  breakdownItem: {
    alignItems: 'center',
  },
  breakdownIcon: {
    width: 44,
    height: 44,
    borderRadius: 22,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 8,
  },
  breakdownValue: {
    fontSize: 22,
    fontWeight: '700',
    color: colors.text,
  },
  breakdownLabel: {
    fontSize: 14,
    color: colors.textSecondary,
    marginTop: 4,
  },
  chartCard: {
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 16,
  },
  chartContainer: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-end',
    height: 100,
  },
  chartColumn: {
    flex: 1,
    alignItems: 'center',
  },
  barWrapper: {
    height: 80,
    justifyContent: 'flex-end',
  },
  activityBar: {
    width: 16,
    backgroundColor: '#007AFF',
    borderRadius: 4,
  },
  chartLabel: {
    fontSize: 12,
    color: colors.textSecondary,
    marginTop: 6,
  },
  chartFooter: {
    marginTop: 12,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: colors.surface,
    alignItems: 'center',
  },
  chartFooterText: {
    fontSize: 14,
    color: colors.textSecondary,
  },
});
