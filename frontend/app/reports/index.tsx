import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  RefreshControl,
  Dimensions,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import api from '../../services/api';
import { useAuthStore } from '../../store/authStore';

const { width } = Dimensions.get('window');

export default function ReportsScreen() {
  const router = useRouter();
  const { user } = useAuthStore();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [period, setPeriod] = useState(30);
  const [overview, setOverview] = useState<any>(null);
  const [error, setError] = useState('');

  const isManager = ['super_admin', 'org_admin', 'store_manager'].includes(user?.role || '');

  const loadData = useCallback(async () => {
    try {
      setError('');
      const response = await api.get(`/reports/overview?days=${period}`);
      setOverview(response.data);
    } catch (err: any) {
      console.error('Failed to load reports:', err);
      setError('Failed to load reports');
    } finally {
      setLoading(false);
    }
  }, [period]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const onRefresh = async () => {
    setRefreshing(true);
    await loadData();
    setRefreshing(false);
  };

  const StatCard = ({ icon, label, value, color, subValue }: any) => (
    <View style={[styles.statCard, { borderLeftColor: color }]}>
      <View style={[styles.statIcon, { backgroundColor: `${color}20` }]}>
        <Ionicons name={icon} size={24} color={color} />
      </View>
      <View style={styles.statContent}>
        <Text style={styles.statValue}>{value?.toLocaleString() || 0}</Text>
        <Text style={styles.statLabel}>{label}</Text>
        {subValue && <Text style={styles.statSubValue}>{subValue}</Text>}
      </View>
    </View>
  );

  const ReportCard = ({ title, icon, color, onPress, description }: any) => (
    <TouchableOpacity style={styles.reportCard} onPress={onPress}>
      <View style={[styles.reportIcon, { backgroundColor: `${color}20` }]}>
        <Ionicons name={icon} size={28} color={color} />
      </View>
      <View style={styles.reportContent}>
        <Text style={styles.reportTitle}>{title}</Text>
        <Text style={styles.reportDescription}>{description}</Text>
      </View>
      <Ionicons name="chevron-forward" size={20} color="#8E8E93" />
    </TouchableOpacity>
  );

  const getScopeLabel = () => {
    switch (overview?.scope) {
      case 'organization': return 'Organization';
      case 'store': return 'Account';
      case 'personal': return 'Personal';
      default: return '';
    }
  };

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#007AFF" />
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="chevron-back" size={28} color="#007AFF" />
        </TouchableOpacity>
        <View>
          <Text style={styles.title}>Reports</Text>
          <Text style={styles.subtitle}>{getScopeLabel()} View</Text>
        </View>
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

      <ScrollView
        contentContainerStyle={styles.scrollContent}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#007AFF" />
        }
      >
        {error ? (
          <View style={styles.errorContainer}>
            <Ionicons name="alert-circle" size={48} color="#FF3B30" />
            <Text style={styles.errorText}>{error}</Text>
            <TouchableOpacity style={styles.retryButton} onPress={loadData}>
              <Text style={styles.retryText}>Retry</Text>
            </TouchableOpacity>
          </View>
        ) : (
          <>
            {/* Comprehensive Dashboard Link */}
            <TouchableOpacity
              style={{
                flexDirection: 'row', alignItems: 'center', gap: 12,
                backgroundColor: '#007AFF15', borderRadius: 14, padding: 16,
                marginBottom: 16, borderWidth: 1, borderColor: '#007AFF30',
              }}
              onPress={() => router.push('/analytics')}
              data-testid="analytics-dashboard-link"
            >
              <View style={{ width: 40, height: 40, borderRadius: 12, backgroundColor: '#007AFF20', alignItems: 'center', justifyContent: 'center' }}>
                <Ionicons name="bar-chart" size={22} color="#007AFF" />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={{ fontSize: 15, fontWeight: '700', color: '#FFF' }}>Comprehensive Analytics</Text>
                <Text style={{ fontSize: 12, color: '#8E8E93', marginTop: 2 }}>KPIs, trends, charts, team & store breakdown</Text>
              </View>
              <Ionicons name="chevron-forward" size={18} color="#007AFF" />
            </TouchableOpacity>

            {/* Summary Stats */}
            <Text style={styles.sectionTitle}>Summary</Text>
            <View style={styles.statsGrid}>
              <StatCard
                icon="chatbubbles"
                label="Messages"
                value={overview?.summary?.total_messages}
                color="#007AFF"
              />
              <StatCard
                icon="people"
                label="New Contacts"
                value={overview?.summary?.new_contacts}
                color="#34C759"
              />
              <StatCard
                icon="megaphone"
                label="Campaigns"
                value={overview?.summary?.campaigns_sent}
                color="#FF9500"
              />
              <StatCard
                icon="sparkles"
                label="AI Automation"
                value={`${overview?.summary?.ai_automation_rate || 0}%`}
                color="#AF52DE"
              />
            </View>

            {/* Messaging Breakdown */}
            <Text style={styles.sectionTitle}>Messaging</Text>
            <View style={styles.breakdownCard}>
              <View style={styles.breakdownRow}>
                <View style={styles.breakdownItem}>
                  <Ionicons name="chatbubble" size={20} color="#34C759" />
                  <Text style={styles.breakdownValue}>{overview?.messaging?.sms_sent || 0}</Text>
                  <Text style={styles.breakdownLabel}>SMS Sent</Text>
                </View>
                <View style={styles.breakdownDivider} />
                <View style={styles.breakdownItem}>
                  <Ionicons name="mail" size={20} color="#007AFF" />
                  <Text style={styles.breakdownValue}>{overview?.messaging?.emails_sent || 0}</Text>
                  <Text style={styles.breakdownLabel}>Emails</Text>
                </View>
                <View style={styles.breakdownDivider} />
                <View style={styles.breakdownItem}>
                  <Ionicons name="sparkles" size={20} color="#AF52DE" />
                  <Text style={styles.breakdownValue}>{overview?.messaging?.ai_handled || 0}</Text>
                  <Text style={styles.breakdownLabel}>AI Handled</Text>
                </View>
              </View>
            </View>

            {/* Campaign Stats */}
            <Text style={styles.sectionTitle}>Broadcasts</Text>
            <View style={styles.breakdownCard}>
              <View style={styles.breakdownRow}>
                <View style={styles.breakdownItem}>
                  <Ionicons name="megaphone" size={20} color="#FF9500" />
                  <Text style={styles.breakdownValue}>{overview?.campaigns?.total_campaigns || 0}</Text>
                  <Text style={styles.breakdownLabel}>Campaigns</Text>
                </View>
                <View style={styles.breakdownDivider} />
                <View style={styles.breakdownItem}>
                  <Ionicons name="people" size={20} color="#5AC8FA" />
                  <Text style={styles.breakdownValue}>{overview?.campaigns?.total_recipients || 0}</Text>
                  <Text style={styles.breakdownLabel}>Recipients</Text>
                </View>
                <View style={styles.breakdownDivider} />
                <View style={styles.breakdownItem}>
                  <Ionicons name="checkmark-circle" size={20} color="#34C759" />
                  <Text style={styles.breakdownValue}>{overview?.campaigns?.delivery_rate || 0}%</Text>
                  <Text style={styles.breakdownLabel}>Delivered</Text>
                </View>
              </View>
            </View>

            {/* Team Stats (managers only) */}
            {isManager && overview?.team && (
              <>
                <Text style={styles.sectionTitle}>Team</Text>
                <View style={styles.breakdownCard}>
                  <View style={styles.breakdownRow}>
                    <View style={styles.breakdownItem}>
                      <Ionicons name="people" size={20} color="#007AFF" />
                      <Text style={styles.breakdownValue}>{overview?.team?.total_members || 0}</Text>
                      <Text style={styles.breakdownLabel}>Members</Text>
                    </View>
                    <View style={styles.breakdownDivider} />
                    <View style={styles.breakdownItem}>
                      <Ionicons name="pulse" size={20} color="#34C759" />
                      <Text style={styles.breakdownValue}>{overview?.team?.active_members || 0}</Text>
                      <Text style={styles.breakdownLabel}>Active</Text>
                    </View>
                  </View>
                </View>
              </>
            )}

            {/* Detailed Reports */}
            <Text style={styles.sectionTitle}>Detailed Reports</Text>
            
            <ReportCard
              title="Messaging Analytics"
              icon="chatbubbles-outline"
              color="#007AFF"
              description="Daily SMS and email breakdown"
              onPress={() => router.push('/reports/messaging')}
            />
            
            <ReportCard
              title="Campaign Performance"
              icon="megaphone-outline"
              color="#FF9500"
              description="Broadcast stats and delivery rates"
              onPress={() => router.push('/reports/campaigns')}
            />
            
            {isManager && (
              <ReportCard
                title="Team Performance"
                icon="people-outline"
                color="#5AC8FA"
                description="Individual member statistics"
                onPress={() => router.push('/reports/team')}
              />
            )}
            
            <ReportCard
              title="My Performance"
              icon="person-outline"
              color="#34C759"
              description="Your personal stats and activity"
              onPress={() => router.push('/reports/personal')}
            />

            <View style={{ height: 40 }} />
          </>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#000',
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#2C2C2E',
  },
  backButton: {
    padding: 4,
  },
  title: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#FFF',
    textAlign: 'center',
  },
  subtitle: {
    fontSize: 12,
    color: '#8E8E93',
    textAlign: 'center',
  },
  periodSelector: {
    flexDirection: 'row',
    padding: 16,
    gap: 8,
  },
  periodButton: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 20,
    backgroundColor: '#1C1C1E',
  },
  periodButtonActive: {
    backgroundColor: '#007AFF',
  },
  periodText: {
    color: '#8E8E93',
    fontWeight: '600',
  },
  periodTextActive: {
    color: '#FFF',
  },
  scrollContent: {
    padding: 16,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: '#FFF',
    marginBottom: 12,
    marginTop: 8,
  },
  statsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 12,
    marginBottom: 16,
  },
  statCard: {
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 16,
    width: (width - 44) / 2,
    borderLeftWidth: 3,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  statIcon: {
    width: 44,
    height: 44,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
  },
  statContent: {
    flex: 1,
  },
  statValue: {
    fontSize: 20,
    fontWeight: '700',
    color: '#FFF',
  },
  statLabel: {
    fontSize: 12,
    color: '#8E8E93',
    marginTop: 2,
  },
  statSubValue: {
    fontSize: 11,
    color: '#8E8E93',
    marginTop: 2,
  },
  breakdownCard: {
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 16,
    marginBottom: 16,
  },
  breakdownRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  breakdownItem: {
    flex: 1,
    alignItems: 'center',
  },
  breakdownDivider: {
    width: 1,
    height: 40,
    backgroundColor: '#2C2C2E',
  },
  breakdownValue: {
    fontSize: 20,
    fontWeight: '700',
    color: '#FFF',
    marginTop: 8,
  },
  breakdownLabel: {
    fontSize: 11,
    color: '#8E8E93',
    marginTop: 4,
  },
  reportCard: {
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 16,
    marginBottom: 10,
    flexDirection: 'row',
    alignItems: 'center',
  },
  reportIcon: {
    width: 48,
    height: 48,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 14,
  },
  reportContent: {
    flex: 1,
  },
  reportTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFF',
  },
  reportDescription: {
    fontSize: 13,
    color: '#8E8E93',
    marginTop: 2,
  },
  errorContainer: {
    alignItems: 'center',
    paddingVertical: 48,
  },
  errorText: {
    color: '#8E8E93',
    fontSize: 16,
    marginTop: 16,
  },
  retryButton: {
    marginTop: 16,
    paddingHorizontal: 24,
    paddingVertical: 12,
    backgroundColor: '#007AFF',
    borderRadius: 12,
  },
  retryText: {
    color: '#FFF',
    fontWeight: '600',
  },
});
