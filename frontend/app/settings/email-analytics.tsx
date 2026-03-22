import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ScrollView,
  ActivityIndicator,
  RefreshControl,
  Dimensions,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import * as Haptics from 'expo-haptics';
import { emailAPI } from '../../services/api';
import { useAuthStore } from '../../store/authStore';
import { format } from 'date-fns';

import { useThemeStore } from '../../store/themeStore';
const { width: SCREEN_WIDTH } = Dimensions.get('window');

interface EmailLog {
  _id: string;
  recipient_email: string;
  recipient_name?: string;
  subject: string;
  status: 'sent' | 'delivered' | 'opened' | 'clicked' | 'bounced' | 'failed';
  sent_at?: string;
  opened_at?: string;
  clicked_at?: string;
  resend_id?: string;
}

interface AnalyticsData {
  total_sent: number;
  total_delivered: number;
  total_opened: number;
  total_clicked: number;
  total_bounced: number;
  open_rate: number;
  click_rate: number;
  logs: EmailLog[];
}

const STATUS_CONFIG: Record<string, { color: string; icon: string; label: string }> = {
  sent: { color: '#007AFF', icon: 'paper-plane', label: 'Sent' },
  delivered: { color: '#34C759', icon: 'checkmark-circle', label: 'Delivered' },
  opened: { color: '#5856D6', icon: 'eye', label: 'Opened' },
  clicked: { color: '#FF9500', icon: 'finger-print', label: 'Clicked' },
  bounced: { color: '#FF3B30', icon: 'close-circle', label: 'Bounced' },
  failed: { color: '#FF3B30', icon: 'alert-circle', label: 'Failed' },
};

export default function EmailAnalyticsPage() {
  const { colors } = useThemeStore();
  const styles = getStyles(colors);
  const router = useRouter();
  const { user } = useAuthStore();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [analytics, setAnalytics] = useState<AnalyticsData>({
    total_sent: 0,
    total_delivered: 0,
    total_opened: 0,
    total_clicked: 0,
    total_bounced: 0,
    open_rate: 0,
    click_rate: 0,
    logs: [],
  });
  const [timeRange, setTimeRange] = useState<'7d' | '30d' | '90d' | 'all'>('30d');

  useEffect(() => {
    if (user?._id) {
      loadAnalytics();
    } else {
      setLoading(false);
    }
  }, [user?._id, timeRange]);

  const loadAnalytics = async () => {
    if (!user?._id) return;
    try {
      const logs = await emailAPI.getLogs(user._id, 100);
      
      // Calculate analytics from logs
      const total_sent = logs.length;
      const total_delivered = logs.filter((l: EmailLog) => l.status !== 'failed' && l.status !== 'bounced').length;
      const total_opened = logs.filter((l: EmailLog) => l.status === 'opened' || l.status === 'clicked').length;
      const total_clicked = logs.filter((l: EmailLog) => l.status === 'clicked').length;
      const total_bounced = logs.filter((l: EmailLog) => l.status === 'bounced').length;
      
      const open_rate = total_delivered > 0 ? Math.round((total_opened / total_delivered) * 100) : 0;
      const click_rate = total_opened > 0 ? Math.round((total_clicked / total_opened) * 100) : 0;
      
      setAnalytics({
        total_sent,
        total_delivered,
        total_opened,
        total_clicked,
        total_bounced,
        open_rate,
        click_rate,
        logs,
      });
    } catch (error) {
      console.error('Error loading analytics:', error);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const onRefresh = async () => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    setRefreshing(true);
    await loadAnalytics();
  };

  const StatCard = ({ 
    icon, 
    value, 
    label, 
    color, 
    percentage 
  }: { 
    icon: string; 
    value: number; 
    label: string; 
    color: string;
    percentage?: number;
  }) => (
    <View style={[styles.statCard, { borderLeftColor: color }]}>
      <View style={[styles.statIconContainer, { backgroundColor: `${color}20` }]}>
        <Ionicons name={icon as any} size={20} color={color} />
      </View>
      <View style={styles.statContent}>
        <Text style={styles.statValue}>{value.toLocaleString()}</Text>
        <Text style={styles.statLabel}>{label}</Text>
      </View>
      {percentage !== undefined && (
        <View style={[styles.percentageBadge, { backgroundColor: `${color}20` }]}>
          <Text style={[styles.percentageText, { color }]}>{percentage}%</Text>
        </View>
      )}
    </View>
  );

  const RateCard = ({ 
    title, 
    rate, 
    color 
  }: { 
    title: string; 
    rate: number; 
    color: string; 
  }) => (
    <View style={styles.rateCard}>
      <Text style={styles.rateTitle}>{title}</Text>
      <View style={styles.rateBarContainer}>
        <View style={[styles.rateBar, { width: `${rate}%`, backgroundColor: color }]} />
      </View>
      <Text style={[styles.rateValue, { color }]}>{rate}%</Text>
    </View>
  );

  if (loading) {
    return (
      <SafeAreaView style={styles.container} edges={['top']}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#007AFF" />
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="chevron-back" size={28} color="#007AFF" />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Email Analytics</Text>
        <TouchableOpacity onPress={onRefresh} style={styles.refreshButton}>
          <Ionicons name="refresh" size={24} color="#007AFF" />
        </TouchableOpacity>
      </View>

      <ScrollView 
        contentContainerStyle={styles.content}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#007AFF" />
        }
      >
        {/* Time Range Selector */}
        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.timeRangeScroll}>
          <View style={styles.timeRangeContainer}>
            {[
              { id: '7d', label: '7 Days' },
              { id: '30d', label: '30 Days' },
              { id: '90d', label: '90 Days' },
              { id: 'all', label: 'All Time' },
            ].map((range) => (
              <TouchableOpacity
                key={range.id}
                style={[
                  styles.timeRangeButton,
                  timeRange === range.id && styles.timeRangeButtonActive,
                ]}
                onPress={() => {
                  Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
                  setTimeRange(range.id as any);
                }}
              >
                <Text style={[
                  styles.timeRangeText,
                  timeRange === range.id && styles.timeRangeTextActive,
                ]}>
                  {range.label}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
        </ScrollView>

        {/* Stats Grid */}
        <View style={styles.statsGrid}>
          <StatCard icon="paper-plane" value={analytics.total_sent} label="Emails Sent" color="#007AFF" />
          <StatCard icon="checkmark-circle" value={analytics.total_delivered} label="Delivered" color="#34C759" />
          <StatCard icon="eye" value={analytics.total_opened} label="Opened" color="#5856D6" />
          <StatCard icon="finger-print" value={analytics.total_clicked} label="Clicked" color="#FF9500" />
        </View>

        {/* Rate Cards */}
        <View style={styles.ratesSection}>
          <Text style={styles.sectionTitle}>Engagement Rates</Text>
          <RateCard title="Open Rate" rate={analytics.open_rate} color="#5856D6" />
          <RateCard title="Click Rate" rate={analytics.click_rate} color="#FF9500" />
        </View>

        {/* Recent Activity */}
        <View style={styles.activitySection}>
          <Text style={styles.sectionTitle}>Recent Activity</Text>
          
          {analytics.logs.length === 0 ? (
            <View style={styles.emptyActivity}>
              <Ionicons name="mail-outline" size={48} color={colors.surface} />
              <Text style={styles.emptyActivityText}>No emails sent yet</Text>
              <Text style={styles.emptyActivitySubtext}>
                Start sending emails to see analytics here
              </Text>
            </View>
          ) : (
            analytics.logs.slice(0, 20).map((log) => {
              const statusConfig = STATUS_CONFIG[log.status] || STATUS_CONFIG.sent;
              return (
                <View key={log._id} style={styles.activityItem}>
                  <View style={[styles.activityIcon, { backgroundColor: `${statusConfig.color}20` }]}>
                    <Ionicons name={statusConfig.icon as any} size={16} color={statusConfig.color} />
                  </View>
                  <View style={styles.activityContent}>
                    <Text style={styles.activityRecipient} numberOfLines={1}>
                      {log.recipient_name || log.recipient_email}
                    </Text>
                    <Text style={styles.activitySubject} numberOfLines={1}>
                      {log.subject}
                    </Text>
                  </View>
                  <View style={styles.activityMeta}>
                    <Text style={[styles.activityStatus, { color: statusConfig.color }]}>
                      {statusConfig.label}
                    </Text>
                    <Text style={styles.activityTime}>
                      {log.sent_at ? format(new Date(log.sent_at), 'MMM d, h:mm a') : '-'}
                    </Text>
                  </View>
                </View>
              );
            })
          )}
        </View>

        {/* Tips Section */}
        <View style={styles.tipsSection}>
          <Text style={styles.sectionTitle}>Tips to Improve</Text>
          
          <View style={styles.tipCard}>
            <View style={styles.tipIcon}>
              <Ionicons name="bulb" size={20} color="#FFD60A" />
            </View>
            <View style={styles.tipContent}>
              <Text style={styles.tipTitle}>Improve Open Rates</Text>
              <Text style={styles.tipText}>
                Use personalized subject lines with the recipient's name. 
                Keep subjects under 50 characters and create urgency.
              </Text>
            </View>
          </View>

          <View style={styles.tipCard}>
            <View style={styles.tipIcon}>
              <Ionicons name="finger-print" size={20} color="#FF9500" />
            </View>
            <View style={styles.tipContent}>
              <Text style={styles.tipTitle}>Boost Click Rates</Text>
              <Text style={styles.tipText}>
                Use clear call-to-action buttons. Place important links 
                above the fold and make buttons large and colorful.
              </Text>
            </View>
          </View>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const getStyles = (colors: any) => StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.bg,
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
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: colors.surface,
  },
  backButton: {
    padding: 4,
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
  },
  refreshButton: {
    padding: 4,
  },
  content: {
    padding: 16,
    paddingBottom: 40,
  },

  // Time Range
  timeRangeScroll: {
    marginBottom: 20,
    marginHorizontal: -16,
    paddingHorizontal: 16,
  },
  timeRangeContainer: {
    flexDirection: 'row',
    gap: 8,
  },
  timeRangeButton: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 20,
    backgroundColor: colors.card,
  },
  timeRangeButtonActive: {
    backgroundColor: '#007AFF',
  },
  timeRangeText: {
    fontSize: 16,
    fontWeight: '500',
    color: colors.textSecondary,
  },
  timeRangeTextActive: {
    color: colors.text,
  },

  // Stats Grid
  statsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 12,
    marginBottom: 24,
  },
  statCard: {
    flex: 1,
    minWidth: (SCREEN_WIDTH - 44) / 2,
    backgroundColor: colors.card,
    borderRadius: 16,
    padding: 16,
    borderLeftWidth: 4,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  statIconContainer: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: 'center',
    justifyContent: 'center',
  },
  statContent: {
    flex: 1,
  },
  statValue: {
    fontSize: 22,
    fontWeight: '700',
    color: colors.text,
  },
  statLabel: {
    fontSize: 14,
    color: colors.textSecondary,
    marginTop: 2,
  },
  percentageBadge: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 8,
  },
  percentageText: {
    fontSize: 14,
    fontWeight: '600',
  },

  // Rates Section
  ratesSection: {
    marginBottom: 24,
  },
  sectionTitle: {
    fontSize: 15,
    fontWeight: '700',
    color: colors.textSecondary,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: 12,
  },
  rateCard: {
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
  },
  rateTitle: {
    fontSize: 17,
    fontWeight: '600',
    color: colors.text,
    marginBottom: 12,
  },
  rateBarContainer: {
    height: 8,
    backgroundColor: colors.surface,
    borderRadius: 4,
    overflow: 'hidden',
    marginBottom: 8,
  },
  rateBar: {
    height: '100%',
    borderRadius: 4,
  },
  rateValue: {
    fontSize: 24,
    fontWeight: '700',
    textAlign: 'right',
  },

  // Activity Section
  activitySection: {
    marginBottom: 24,
  },
  emptyActivity: {
    backgroundColor: colors.card,
    borderRadius: 16,
    padding: 40,
    alignItems: 'center',
  },
  emptyActivityText: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
    marginTop: 16,
  },
  emptyActivitySubtext: {
    fontSize: 16,
    color: colors.textSecondary,
    marginTop: 8,
    textAlign: 'center',
  },
  activityItem: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 12,
    marginBottom: 8,
    gap: 12,
  },
  activityIcon: {
    width: 32,
    height: 32,
    borderRadius: 16,
    alignItems: 'center',
    justifyContent: 'center',
  },
  activityContent: {
    flex: 1,
  },
  activityRecipient: {
    fontSize: 17,
    fontWeight: '600',
    color: colors.text,
  },
  activitySubject: {
    fontSize: 15,
    color: colors.textSecondary,
    marginTop: 2,
  },
  activityMeta: {
    alignItems: 'flex-end',
  },
  activityStatus: {
    fontSize: 14,
    fontWeight: '600',
  },
  activityTime: {
    fontSize: 13,
    color: '#6E6E73',
    marginTop: 2,
  },

  // Tips Section
  tipsSection: {
    marginBottom: 24,
  },
  tipCard: {
    flexDirection: 'row',
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
    gap: 12,
  },
  tipIcon: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: colors.surface,
    alignItems: 'center',
    justifyContent: 'center',
  },
  tipContent: {
    flex: 1,
  },
  tipTitle: {
    fontSize: 17,
    fontWeight: '600',
    color: colors.text,
    marginBottom: 4,
  },
  tipText: {
    fontSize: 15,
    color: colors.textSecondary,
    lineHeight: 18,
  },
});
