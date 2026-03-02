import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  Platform,
  TextInput,
  Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import api from '../../services/api';
import { useAuthStore } from '../../store/authStore';

import { useThemeStore } from '../../store/themeStore';
type DatePreset = 'today' | 'this_week' | 'this_month' | 'last_month' | 'last_7' | 'last_30' | 'custom';

function getDateRange(preset: DatePreset): { start: string; end: string } {
  const now = new Date();
  const fmt = (d: Date) => d.toISOString().split('T')[0];
  const end = fmt(now);

  switch (preset) {
    case 'today':
      return { start: end, end };
    case 'this_week': {
      const d = new Date(now);
      d.setDate(d.getDate() - d.getDay());
      return { start: fmt(d), end };
    }
    case 'this_month': {
      const d = new Date(now.getFullYear(), now.getMonth(), 1);
      return { start: fmt(d), end };
    }
    case 'last_month': {
      const s = new Date(now.getFullYear(), now.getMonth() - 1, 1);
      const e = new Date(now.getFullYear(), now.getMonth(), 0);
      return { start: fmt(s), end: fmt(e) };
    }
    case 'last_7': {
      const d = new Date(now);
      d.setDate(d.getDate() - 7);
      return { start: fmt(d), end };
    }
    case 'last_30': {
      const d = new Date(now);
      d.setDate(d.getDate() - 30);
      return { start: fmt(d), end };
    }
    default:
      return { start: end, end };
  }
}

const PRESETS: { key: DatePreset; label: string }[] = [
  { key: 'today', label: 'Today' },
  { key: 'this_week', label: 'This Week' },
  { key: 'this_month', label: 'This Month' },
  { key: 'last_month', label: 'Last Month' },
  { key: 'last_7', label: 'Last 7 Days' },
  { key: 'last_30', label: 'Last 30 Days' },
];

interface Totals {
  sms_sent: number;
  sms_personal: number;
  emails_sent: number;
  digital_cards_sent: number;
  review_invites_sent: number;
  congrats_cards_sent: number;
  vcards_sent: number;
  new_contacts: number;
  calls: number;
  link_clicks: number;
  total_touchpoints: number;
}

interface UserStats extends Totals {
  user_id: string;
  name: string;
}

export default function ActivityReportScreen() {
  const { colors } = useThemeStore();
  const styles = getStyles(colors);
  const router = useRouter();
  const { user } = useAuthStore();
  const [loading, setLoading] = useState(true);
  const [preset, setPreset] = useState<DatePreset>('this_week');
  const [team, setTeam] = useState(false);
  const [totals, setTotals] = useState<Totals | null>(null);
  const [perUser, setPerUser] = useState<UserStats[]>([]);
  const [isTeamReport, setIsTeamReport] = useState(false);
  const [sendingEmail, setSendingEmail] = useState(false);
  const [showSchedule, setShowSchedule] = useState(false);
  const [schedFreq, setSchedFreq] = useState('none');
  const [schedEmail, setSchedEmail] = useState('');
  const [dailyData, setDailyData] = useState<any[]>([]);

  const isManager = user?.role && ['super_admin', 'admin', 'manager', 'store_manager', 'org_admin'].includes(user.role);

  const loadReport = useCallback(async () => {
    if (!user?._id) return;
    try {
      setLoading(true);
      const { start, end } = getDateRange(preset);
      const res = await api.get(`/reports/activity/${user._id}?start_date=${start}&end_date=${end}&team=${team}`);
      setTotals(res.data.totals);
      setPerUser(res.data.per_user || []);
      setIsTeamReport(res.data.is_team_report);

      // Load daily breakdown for chart
      const dailyRes = await api.get(`/reports/activity-daily/${user._id}?start_date=${start}&end_date=${end}&team=${team}`);
      setDailyData(dailyRes.data.days || []);
    } catch (err) {
      console.error('Failed to load report:', err);
    } finally {
      setLoading(false);
    }
  }, [user?._id, preset, team]);

  useEffect(() => { loadReport(); }, [loadReport]);

  useEffect(() => {
    if (!user?._id) return;
    api.get(`/reports/preferences/${user._id}`).then(res => {
      setSchedFreq(res.data.frequency || 'none');
      setSchedEmail(res.data.email_to || user.email || '');
    }).catch(() => {});
  }, [user?._id]);

  const handleEmailReport = async () => {
    if (!user?._id) return;
    setSendingEmail(true);
    try {
      const { start, end } = getDateRange(preset);
      await api.post(`/reports/send-email/${user._id}?start_date=${start}&end_date=${end}&team=${team}`);
      Alert.alert('Sent!', 'Report emailed successfully.');
    } catch (err) {
      Alert.alert('Error', 'Failed to send report email.');
    } finally {
      setSendingEmail(false);
    }
  };

  const saveSchedule = async () => {
    if (!user?._id) return;
    try {
      await api.put(`/reports/preferences/${user._id}`, {
        frequency: schedFreq,
        email_enabled: schedFreq !== 'none',
        email_to: schedEmail || user?.email,
        day_of_week: 1,
        day_of_month: 1,
      });
      Alert.alert('Saved', schedFreq === 'none' ? 'Scheduled reports disabled.' : `You'll receive ${schedFreq} reports.`);
      setShowSchedule(false);
    } catch (err) {
      Alert.alert('Error', 'Failed to save preferences.');
    }
  };

  const maxDaily = Math.max(...dailyData.map(d => d.total || 0), 1);

  const StatCard = ({ value, label, color, icon }: { value: number; label: string; color: string; icon: string }) => (
    <View style={styles.statCard} data-testid={`stat-${label.toLowerCase().replace(/\s/g, '-')}`}>
      <View style={[styles.statIcon, { backgroundColor: `${color}15` }]}>
        <Ionicons name={icon as any} size={18} color={color} />
      </View>
      <Text style={[styles.statValue, { color }]}>{value}</Text>
      <Text style={styles.statLabel}>{label}</Text>
    </View>
  );

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} data-testid="report-back-btn">
          <Ionicons name="chevron-back" size={28} color="#007AFF" />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Activity Report</Text>
        <TouchableOpacity onPress={() => setShowSchedule(!showSchedule)} data-testid="report-schedule-btn">
          <Ionicons name="timer-outline" size={24} color={schedFreq !== 'none' ? '#34C759' : colors.textSecondary} />
        </TouchableOpacity>
      </View>

      <ScrollView style={styles.scroll} contentContainerStyle={styles.scrollContent}>
        {/* Date Presets */}
        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.presetRow} contentContainerStyle={styles.presetRowContent}>
          {PRESETS.map(p => (
            <TouchableOpacity
              key={p.key}
              style={[styles.presetBtn, preset === p.key && styles.presetBtnActive]}
              onPress={() => setPreset(p.key)}
              data-testid={`preset-${p.key}`}
            >
              <Text style={[styles.presetText, preset === p.key && styles.presetTextActive]}>{p.label}</Text>
            </TouchableOpacity>
          ))}
        </ScrollView>

        {/* Team Toggle */}
        {isManager && (
          <View style={styles.teamToggle}>
            <TouchableOpacity
              style={[styles.toggleBtn, !team && styles.toggleBtnActive]}
              onPress={() => setTeam(false)}
              data-testid="toggle-my-stats"
            >
              <Text style={[styles.toggleText, !team && styles.toggleTextActive]}>My Stats</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.toggleBtn, team && styles.toggleBtnActive]}
              onPress={() => setTeam(true)}
              data-testid="toggle-team-stats"
            >
              <Text style={[styles.toggleText, team && styles.toggleTextActive]}>Team</Text>
            </TouchableOpacity>
          </View>
        )}

        {/* Schedule Panel */}
        {showSchedule && (
          <View style={styles.schedulePanel} data-testid="schedule-panel">
            <Text style={styles.schedulePanelTitle}>Scheduled Reports</Text>
            <View style={styles.schedFreqRow}>
              {['none', 'daily', 'weekly', 'monthly'].map(f => (
                <TouchableOpacity
                  key={f}
                  style={[styles.schedFreqBtn, schedFreq === f && styles.schedFreqBtnActive]}
                  onPress={() => setSchedFreq(f)}
                >
                  <Text style={[styles.schedFreqText, schedFreq === f && styles.schedFreqTextActive]}>
                    {f === 'none' ? 'Off' : f.charAt(0).toUpperCase() + f.slice(1)}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>
            {schedFreq !== 'none' && (
              <TextInput
                style={styles.schedEmailInput}
                value={schedEmail}
                onChangeText={setSchedEmail}
                placeholder="Email address"
                placeholderTextColor="#6E6E73"
                keyboardType="email-address"
              />
            )}
            <TouchableOpacity style={styles.schedSaveBtn} onPress={saveSchedule}>
              <Text style={styles.schedSaveBtnText}>Save</Text>
            </TouchableOpacity>
          </View>
        )}

        {loading ? (
          <View style={styles.loadingContainer}>
            <ActivityIndicator size="large" color="#FFD60A" />
          </View>
        ) : totals ? (
          <>
            {/* Top Stats */}
            <View style={styles.topStats}>
              <View style={styles.heroStat}>
                <Text style={styles.heroValue}>{totals.total_touchpoints}</Text>
                <Text style={styles.heroLabel}>Total Touchpoints</Text>
              </View>
            </View>

            {/* Stat Grid */}
            <View style={styles.statGrid}>
              <StatCard value={totals.sms_sent + totals.sms_personal} label="SMS Sent" color="#007AFF" icon="chatbubble" />
              <StatCard value={totals.emails_sent} label="Emails" color="#AF52DE" icon="mail" />
              <StatCard value={totals.digital_cards_sent} label="Cards Shared" color="#32ADE6" icon="card" />
              <StatCard value={totals.review_invites_sent} label="Review Invites" color="#FFD60A" icon="star" />
              <StatCard value={totals.congrats_cards_sent} label="Congrats" color="#C9A962" icon="gift" />
              <StatCard value={totals.new_contacts} label="New Contacts" color="#34C759" icon="person-add" />
              <StatCard value={totals.calls} label="Calls" color="#FF9500" icon="call" />
              <StatCard value={totals.link_clicks} label="Link Clicks" color="#FF375F" icon="analytics" />
            </View>

            {/* Activity Chart */}
            {dailyData.length > 0 && (
              <View style={styles.chartSection}>
                <Text style={styles.sectionTitle}>Daily Activity</Text>
                <View style={styles.chart}>
                  {dailyData.slice(-14).map((day, i) => {
                    const height = Math.max((day.total / maxDaily) * 80, 3);
                    const label = new Date(day.date).toLocaleDateString('en-US', { weekday: 'short' });
                    return (
                      <View key={i} style={styles.chartBar}>
                        <Text style={styles.chartBarValue}>{day.total || ''}</Text>
                        <View style={[styles.chartBarFill, { height, backgroundColor: '#007AFF' }]} />
                        <Text style={styles.chartBarLabel}>{label}</Text>
                      </View>
                    );
                  })}
                </View>
              </View>
            )}

            {/* Team Breakdown */}
            {isTeamReport && perUser.length > 1 && (
              <View style={styles.teamSection}>
                <Text style={styles.sectionTitle}>Team Breakdown</Text>
                {perUser.sort((a, b) => b.total_touchpoints - a.total_touchpoints).map((u, i) => (
                  <View key={u.user_id} style={styles.teamRow} data-testid={`team-row-${i}`}>
                    <View style={styles.teamRank}>
                      <Text style={styles.teamRankText}>{i + 1}</Text>
                    </View>
                    <View style={styles.teamInfo}>
                      <Text style={styles.teamName}>{u.name}</Text>
                      <Text style={styles.teamDetails}>
                        {u.sms_sent + u.sms_personal} SMS  {u.emails_sent} Email  {u.digital_cards_sent} Cards  {u.review_invites_sent} Reviews
                      </Text>
                    </View>
                    <View style={styles.teamScore}>
                      <Text style={styles.teamScoreValue}>{u.total_touchpoints}</Text>
                      <Text style={styles.teamScoreLabel}>touch</Text>
                    </View>
                  </View>
                ))}
              </View>
            )}

            {/* Email Report Button */}
            <TouchableOpacity
              style={styles.emailBtn}
              onPress={handleEmailReport}
              disabled={sendingEmail}
              data-testid="email-report-btn"
            >
              {sendingEmail ? (
                <ActivityIndicator size="small" color={colors.text} />
              ) : (
                <>
                  <Ionicons name="mail-outline" size={18} color={colors.text} />
                  <Text style={styles.emailBtnText}>Email This Report</Text>
                </>
              )}
            </TouchableOpacity>
          </>
        ) : (
          <View style={styles.emptyState}>
            <Ionicons name="bar-chart-outline" size={48} color={colors.textSecondary} />
            <Text style={styles.emptyText}>No data for this period</Text>
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const getStyles = (colors: any) => StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  header: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: colors.card,
  },
  headerTitle: { fontSize: 18, fontWeight: '700', color: colors.text },
  scroll: { flex: 1 },
  scrollContent: { paddingBottom: 40 },
  presetRow: { marginTop: 12 },
  presetRowContent: { paddingHorizontal: 16, gap: 8 },
  presetBtn: {
    paddingHorizontal: 16, paddingVertical: 8, borderRadius: 20,
    backgroundColor: colors.card, marginRight: 8,
  },
  presetBtnActive: { backgroundColor: '#FFD60A' },
  presetText: { fontSize: 13, fontWeight: '600', color: colors.textSecondary },
  presetTextActive: { color: colors.text },
  teamToggle: {
    flexDirection: 'row', marginHorizontal: 16, marginTop: 12,
    backgroundColor: colors.card, borderRadius: 10, padding: 3,
  },
  toggleBtn: { flex: 1, paddingVertical: 8, borderRadius: 8, alignItems: 'center' },
  toggleBtnActive: { backgroundColor: colors.surface },
  toggleText: { fontSize: 14, fontWeight: '600', color: '#6E6E73' },
  toggleTextActive: { color: colors.text },
  schedulePanel: {
    marginHorizontal: 16, marginTop: 12, backgroundColor: colors.card,
    borderRadius: 12, padding: 16,
  },
  schedulePanelTitle: { fontSize: 15, fontWeight: '700', color: colors.text, marginBottom: 12 },
  schedFreqRow: { flexDirection: 'row', gap: 8 },
  schedFreqBtn: {
    flex: 1, paddingVertical: 8, borderRadius: 8, backgroundColor: colors.surface, alignItems: 'center',
  },
  schedFreqBtnActive: { backgroundColor: '#34C759' },
  schedFreqText: { fontSize: 12, fontWeight: '600', color: colors.textSecondary },
  schedFreqTextActive: { color: colors.text },
  schedEmailInput: {
    marginTop: 12, backgroundColor: colors.surface, borderRadius: 8,
    paddingHorizontal: 12, paddingVertical: 10, color: colors.text, fontSize: 14,
  },
  schedSaveBtn: {
    marginTop: 12, backgroundColor: '#34C759', borderRadius: 8,
    paddingVertical: 10, alignItems: 'center',
  },
  schedSaveBtnText: { fontSize: 14, fontWeight: '700', color: colors.text },
  loadingContainer: { flex: 1, justifyContent: 'center', alignItems: 'center', paddingTop: 80 },
  topStats: { alignItems: 'center', marginTop: 24 },
  heroStat: { alignItems: 'center' },
  heroValue: { fontSize: 48, fontWeight: '800', color: '#34C759' },
  heroLabel: { fontSize: 14, fontWeight: '600', color: colors.textSecondary, marginTop: 4 },
  statGrid: {
    flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'center',
    gap: 10, marginTop: 20, paddingHorizontal: 16,
  },
  statCard: {
    width: '22%', minWidth: 80, backgroundColor: colors.card, borderRadius: 12,
    padding: 12, alignItems: 'center',
  },
  statIcon: { width: 32, height: 32, borderRadius: 8, alignItems: 'center', justifyContent: 'center', marginBottom: 6 },
  statValue: { fontSize: 20, fontWeight: '800' },
  statLabel: { fontSize: 10, fontWeight: '600', color: colors.textSecondary, marginTop: 2, textAlign: 'center' },
  chartSection: { marginTop: 28, paddingHorizontal: 16 },
  sectionTitle: { fontSize: 16, fontWeight: '700', color: colors.text, marginBottom: 12 },
  chart: { flexDirection: 'row', alignItems: 'flex-end', height: 120, gap: 2, justifyContent: 'space-between' },
  chartBar: { flex: 1, alignItems: 'center', justifyContent: 'flex-end' },
  chartBarFill: { width: '80%', borderRadius: 3, minHeight: 3 },
  chartBarValue: { fontSize: 9, color: colors.textSecondary, marginBottom: 2 },
  chartBarLabel: { fontSize: 9, color: '#6E6E73', marginTop: 4 },
  teamSection: { marginTop: 28, paddingHorizontal: 16 },
  teamRow: {
    flexDirection: 'row', alignItems: 'center', backgroundColor: colors.card,
    borderRadius: 12, padding: 14, marginBottom: 8,
  },
  teamRank: {
    width: 28, height: 28, borderRadius: 14, backgroundColor: colors.surface,
    alignItems: 'center', justifyContent: 'center', marginRight: 12,
  },
  teamRankText: { fontSize: 13, fontWeight: '700', color: '#FFD60A' },
  teamInfo: { flex: 1 },
  teamName: { fontSize: 15, fontWeight: '600', color: colors.text },
  teamDetails: { fontSize: 11, color: colors.textSecondary, marginTop: 3 },
  teamScore: { alignItems: 'center' },
  teamScoreValue: { fontSize: 20, fontWeight: '800', color: '#34C759' },
  teamScoreLabel: { fontSize: 10, color: colors.textSecondary },
  emailBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8,
    marginHorizontal: 16, marginTop: 28, backgroundColor: '#007AFF',
    borderRadius: 12, paddingVertical: 14,
  },
  emailBtnText: { fontSize: 15, fontWeight: '600', color: colors.text },
  emptyState: { alignItems: 'center', paddingTop: 80 },
  emptyText: { fontSize: 16, color: colors.textSecondary, marginTop: 12 },
});
