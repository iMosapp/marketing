import React, { useState, useEffect, useCallback } from 'react';
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
import { useThemeStore } from '../../store/themeStore';
import { ScreenHeader, HeaderIconButton } from '../../components/common/ScreenHeader';
import { FS, EYEBROW } from '../../constants/typography';
import { format } from 'date-fns';

const { width: SCREEN_WIDTH } = Dimensions.get('window');
const tid = (id: string) => ({ testID: id, dataSet: { testid: id } as any });
const GOLD = '#C9A962';

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

// Sent is the brand gold; the rest are status category colors.
const STATUS_CONFIG: Record<string, { color: string; icon: string; label: string }> = {
  sent: { color: GOLD, icon: 'paper-plane', label: 'Sent' },
  delivered: { color: '#34C759', icon: 'checkmark-circle', label: 'Delivered' },
  opened: { color: '#5856D6', icon: 'eye', label: 'Opened' },
  clicked: { color: '#FF9500', icon: 'finger-print', label: 'Clicked' },
  bounced: { color: '#FF3B30', icon: 'close-circle', label: 'Bounced' },
  failed: { color: '#FF3B30', icon: 'alert-circle', label: 'Failed' },
};

type Range = '7d' | '30d' | '90d' | 'all';
const RANGES: { id: Range; label: string; days?: number }[] = [
  { id: '7d', label: '7 days', days: 7 },
  { id: '30d', label: '30 days', days: 30 },
  { id: '90d', label: '90 days', days: 90 },
  { id: 'all', label: 'All time' },
];

const EMPTY: AnalyticsData = { total_sent: 0, total_delivered: 0, total_opened: 0, total_clicked: 0, total_bounced: 0, open_rate: 0, click_rate: 0, logs: [] };

export default function EmailAnalyticsPage() {
  const { colors } = useThemeStore();
  const styles = getStyles(colors);
  const router = useRouter();
  const { user } = useAuthStore();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [allLogs, setAllLogs] = useState<EmailLog[]>([]);
  const [analytics, setAnalytics] = useState<AnalyticsData>(EMPTY);
  const [timeRange, setTimeRange] = useState<Range>('30d');

  const loadLogs = useCallback(async () => {
    if (!user?._id) { setLoading(false); return; }
    try {
      const logs = await emailAPI.getLogs(user._id, 100);
      setAllLogs(Array.isArray(logs) ? logs : []);
    } catch (error) {
      console.error('Error loading analytics:', error);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [user?._id]);

  useEffect(() => { loadLogs(); }, [loadLogs]);

  // The range filter is applied client-side so switching ranges is instant.
  useEffect(() => {
    const days = RANGES.find(r => r.id === timeRange)?.days;
    const cutoff = days ? Date.now() - days * 86400000 : 0;
    const logs = cutoff ? allLogs.filter(l => !l.sent_at || new Date(l.sent_at).getTime() >= cutoff) : allLogs;
    const total_sent = logs.length;
    const total_delivered = logs.filter(l => l.status !== 'failed' && l.status !== 'bounced').length;
    const total_opened = logs.filter(l => l.status === 'opened' || l.status === 'clicked').length;
    const total_clicked = logs.filter(l => l.status === 'clicked').length;
    const total_bounced = logs.filter(l => l.status === 'bounced').length;
    setAnalytics({
      total_sent, total_delivered, total_opened, total_clicked, total_bounced,
      open_rate: total_delivered > 0 ? Math.round((total_opened / total_delivered) * 100) : 0,
      click_rate: total_opened > 0 ? Math.round((total_clicked / total_opened) * 100) : 0,
      logs,
    });
  }, [allLogs, timeRange]);

  const onRefresh = async () => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    setRefreshing(true);
    await loadLogs();
  };

  const StatCard = ({ icon, value, label, color, testID }: { icon: string; value: number; label: string; color: string; testID: string }) => (
    <View style={[styles.statCard, { borderLeftColor: color }]} {...tid(testID)}>
      <View style={[styles.statIconContainer, { backgroundColor: `${color}20` }]}>
        <Ionicons name={icon as any} size={20} color={color} />
      </View>
      <View style={styles.statContent}>
        <Text style={styles.statValue}>{value.toLocaleString()}</Text>
        <Text style={styles.statLabel}>{label}</Text>
      </View>
    </View>
  );

  const RateCard = ({ title, rate, color }: { title: string; rate: number; color: string }) => (
    <View style={styles.rateCard}>
      <Text style={styles.rateTitle}>{title}</Text>
      <View style={styles.rateBarContainer}>
        <View style={[styles.rateBar, { width: `${rate}%`, backgroundColor: color }]} />
      </View>
      <Text style={[styles.rateValue, { color }]}>{rate}%</Text>
    </View>
  );

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <ScreenHeader
        title="Email Analytics"
        testID="email-analytics-header"
        right={<HeaderIconButton icon="refresh" onPress={onRefresh} testID="email-analytics-refresh" />}
      />

      {loading ? (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={colors.accent} />
        </View>
      ) : (
      <ScrollView 
        contentContainerStyle={styles.content}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.accent} />
        }
      >
        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.timeRangeScroll}>
          <View style={styles.timeRangeContainer}>
            {RANGES.map((range) => (
              <TouchableOpacity
                key={range.id}
                style={[
                  styles.timeRangeButton,
                  timeRange === range.id && styles.timeRangeButtonActive,
                ]}
                onPress={() => {
                  Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
                  setTimeRange(range.id);
                }}
                {...tid(`email-range-${range.id}`)}
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

        <View style={styles.statsGrid}>
          <StatCard icon="paper-plane" value={analytics.total_sent} label="Emails sent" color={STATUS_CONFIG.sent.color} testID="email-stat-sent" />
          <StatCard icon="checkmark-circle" value={analytics.total_delivered} label="Delivered" color={STATUS_CONFIG.delivered.color} testID="email-stat-delivered" />
          <StatCard icon="eye" value={analytics.total_opened} label="Opened" color={STATUS_CONFIG.opened.color} testID="email-stat-opened" />
          <StatCard icon="finger-print" value={analytics.total_clicked} label="Clicked" color={STATUS_CONFIG.clicked.color} testID="email-stat-clicked" />
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Engagement rates</Text>
          <RateCard title="Open rate" rate={analytics.open_rate} color={STATUS_CONFIG.opened.color} />
          <RateCard title="Click rate" rate={analytics.click_rate} color={STATUS_CONFIG.clicked.color} />
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Recent activity</Text>
          
          {analytics.logs.length === 0 ? (
            <View style={styles.emptyActivity} {...tid('email-analytics-empty')}>
              <Ionicons name="mail-outline" size={44} color={colors.textTertiary} />
              <Text style={styles.emptyActivityText}>{allLogs.length ? 'No emails in this range' : 'No emails sent yet'}</Text>
              <Text style={styles.emptyActivitySubtext}>
                {allLogs.length ? 'Try a longer time range.' : 'Emails you send from a contact show up here with opens and clicks.'}
              </Text>
              <TouchableOpacity
                onPress={() => allLogs.length ? setTimeRange('all') : router.push('/(tabs)/contacts' as any)}
                style={styles.emptyBtn}
                {...tid('email-analytics-empty-cta')}
              >
                <Text style={styles.emptyBtnText}>{allLogs.length ? 'Show all time' : 'Open contacts'}</Text>
              </TouchableOpacity>
            </View>
          ) : (
            analytics.logs.slice(0, 20).map((log) => {
              const statusConfig = STATUS_CONFIG[log.status] || STATUS_CONFIG.sent;
              return (
                <View key={log._id} style={styles.activityItem} {...tid(`email-log-${log._id}`)}>
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

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Tips to improve</Text>
          
          <View style={styles.tipCard}>
            <View style={styles.tipIcon}>
              <Ionicons name="bulb" size={20} color={GOLD} />
            </View>
            <View style={styles.tipContent}>
              <Text style={styles.tipTitle}>Improve open rates</Text>
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
              <Text style={styles.tipTitle}>Boost click rates</Text>
              <Text style={styles.tipText}>
                Use clear call-to-action buttons. Place important links 
                above the fold and make buttons large and colorful.
              </Text>
            </View>
          </View>
        </View>
      </ScrollView>
      )}
    </SafeAreaView>
  );
}

const getStyles = (colors: any) => StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  loadingContainer: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  content: { padding: 16, paddingBottom: 40 },

  timeRangeScroll: { marginBottom: 20, marginHorizontal: -16, paddingHorizontal: 16 },
  timeRangeContainer: { flexDirection: 'row', gap: 8, paddingRight: 16 },
  timeRangeButton: {
    paddingHorizontal: 14, paddingVertical: 8, borderRadius: 18,
    backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border,
  },
  timeRangeButtonActive: { backgroundColor: colors.accent, borderColor: colors.accent },
  timeRangeText: { fontSize: FS.secondary, fontWeight: '700', color: colors.textSecondary },
  timeRangeTextActive: { color: '#000' },

  statsGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 12, marginBottom: 24 },
  statCard: {
    flex: 1, minWidth: (SCREEN_WIDTH - 44) / 2, backgroundColor: colors.card, borderRadius: 16,
    padding: 16, borderWidth: 1, borderColor: colors.border, borderLeftWidth: 4,
    flexDirection: 'row', alignItems: 'center', gap: 12,
  },
  statIconContainer: { width: 40, height: 40, borderRadius: 20, alignItems: 'center', justifyContent: 'center' },
  statContent: { flex: 1, minWidth: 0 },
  statValue: { fontSize: FS.title, fontWeight: '700', color: colors.text },
  statLabel: { fontSize: FS.secondary, color: colors.textSecondary, marginTop: 2 },

  section: { marginBottom: 24 },
  sectionTitle: { ...EYEBROW, color: colors.textSecondary, marginBottom: 10 },
  rateCard: { backgroundColor: colors.card, borderRadius: 16, padding: 16, marginBottom: 12, borderWidth: 1, borderColor: colors.border },
  rateTitle: { fontSize: FS.heading, fontWeight: '700', color: colors.text, marginBottom: 12 },
  rateBarContainer: { height: 8, backgroundColor: colors.surface, borderRadius: 4, overflow: 'hidden', marginBottom: 8 },
  rateBar: { height: '100%', borderRadius: 4 },
  rateValue: { fontSize: 24, fontWeight: '700', textAlign: 'right' },

  emptyActivity: { backgroundColor: colors.card, borderRadius: 16, padding: 32, alignItems: 'center', borderWidth: 1, borderColor: colors.border },
  emptyActivityText: { fontSize: FS.heading, fontWeight: '700', color: colors.text, marginTop: 14, textAlign: 'center' },
  emptyActivitySubtext: { fontSize: FS.body, color: colors.textSecondary, marginTop: 6, textAlign: 'center' },
  emptyBtn: { marginTop: 16, paddingHorizontal: 18, paddingVertical: 10, borderRadius: 14, borderWidth: 1, borderColor: colors.accent },
  emptyBtnText: { fontSize: FS.body, fontWeight: '700', color: colors.accent },
  activityItem: {
    flexDirection: 'row', alignItems: 'center', backgroundColor: colors.card, borderRadius: 16,
    padding: 12, marginBottom: 8, gap: 12, borderWidth: 1, borderColor: colors.border,
  },
  activityIcon: { width: 32, height: 32, borderRadius: 16, alignItems: 'center', justifyContent: 'center' },
  activityContent: { flex: 1, minWidth: 0 },
  activityRecipient: { fontSize: FS.heading, fontWeight: '700', color: colors.text, flexShrink: 1 },
  activitySubject: { fontSize: FS.secondary, color: colors.textSecondary, marginTop: 2, flexShrink: 1 },
  activityMeta: { alignItems: 'flex-end', flexShrink: 0 },
  activityStatus: { fontSize: FS.secondary, fontWeight: '700' },
  activityTime: { fontSize: FS.caption, color: colors.textTertiary, marginTop: 2 },

  tipCard: { flexDirection: 'row', backgroundColor: colors.card, borderRadius: 16, padding: 16, marginBottom: 12, gap: 12, borderWidth: 1, borderColor: colors.border },
  tipIcon: { width: 40, height: 40, borderRadius: 20, backgroundColor: colors.surface, alignItems: 'center', justifyContent: 'center' },
  tipContent: { flex: 1 },
  tipTitle: { fontSize: FS.heading, fontWeight: '700', color: colors.text, marginBottom: 4 },
  tipText: { fontSize: FS.body, color: colors.textSecondary, lineHeight: 20 },
});
