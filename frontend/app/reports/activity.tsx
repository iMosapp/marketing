import React, { useState, useEffect, useCallback } from 'react';
import { showAlert } from '../../services/alert';
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  TextInput,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import api from '../../services/api';
import { useAuthStore } from '../../store/authStore';
import { useThemeStore } from '../../store/themeStore';
import { ScreenHeader, HeaderIconButton } from '../../components/common/ScreenHeader';
import { FS, EYEBROW } from '../../constants/typography';

const tid = (id: string) => ({ testID: id, dataSet: { testid: id } as any });
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
  { key: 'this_week', label: 'This week' },
  { key: 'this_month', label: 'This month' },
  { key: 'last_month', label: 'Last month' },
  { key: 'last_7', label: 'Last 7 days' },
  { key: 'last_30', label: 'Last 30 days' },
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
      showAlert('Sent', 'Report emailed successfully.');
    } catch (err) {
      showAlert('Error', 'Failed to send report email.');
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
      showAlert('Saved', schedFreq === 'none' ? 'Scheduled reports disabled.' : `You'll receive ${schedFreq} reports.`);
      setShowSchedule(false);
    } catch (err) {
      showAlert('Error', 'Failed to save preferences.');
    }
  };

  const maxDaily = Math.max(...dailyData.map(d => d.total || 0), 1);

  const StatCard = ({ value, label, color, icon }: { value: number; label: string; color: string; icon: string }) => (
    <View style={styles.statCard} {...tid(`stat-${label.toLowerCase().replace(/\s/g, '-')}`)}>
      <View style={[styles.statIcon, { backgroundColor: `${color}15` }]}>
        <Ionicons name={icon as any} size={18} color={color} />
      </View>
      <Text style={[styles.statValue, { color }]}>{value}</Text>
      <Text style={styles.statLabel}>{label}</Text>
    </View>
  );

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <ScreenHeader
        title="Activity Reports"
        testID="activity-reports-header"
        right={<HeaderIconButton icon={schedFreq !== 'none' ? 'timer' : 'timer-outline'} onPress={() => setShowSchedule(!showSchedule)} testID="report-schedule-btn" color={schedFreq !== 'none' ? colors.success : colors.accent} />}
      />

      <ScrollView style={styles.scroll} contentContainerStyle={styles.scrollContent}>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.presetRow} contentContainerStyle={styles.presetRowContent}>
          {PRESETS.map(p => (
            <TouchableOpacity
              key={p.key}
              style={[styles.presetBtn, preset === p.key && styles.presetBtnActive]}
              onPress={() => setPreset(p.key)}
              {...tid(`preset-${p.key}`)}
            >
              <Text style={[styles.presetText, preset === p.key && styles.presetTextActive]}>{p.label}</Text>
            </TouchableOpacity>
          ))}
        </ScrollView>

        {isManager && (
          <View style={styles.teamToggle}>
            <TouchableOpacity
              style={[styles.toggleBtn, !team && styles.toggleBtnActive]}
              onPress={() => setTeam(false)}
              {...tid('toggle-my-stats')}
            >
              <Text style={[styles.toggleText, !team && styles.toggleTextActive]}>My stats</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.toggleBtn, team && styles.toggleBtnActive]}
              onPress={() => setTeam(true)}
              {...tid('toggle-team-stats')}
            >
              <Text style={[styles.toggleText, team && styles.toggleTextActive]}>Team</Text>
            </TouchableOpacity>
          </View>
        )}

        {showSchedule && (
          <View style={styles.schedulePanel} {...tid('schedule-panel')}>
            <Text style={styles.schedulePanelTitle}>Scheduled reports</Text>
            <View style={styles.schedFreqRow}>
              {['none', 'daily', 'weekly', 'monthly'].map(f => (
                <TouchableOpacity
                  key={f}
                  style={[styles.schedFreqBtn, schedFreq === f && styles.schedFreqBtnActive]}
                  onPress={() => setSchedFreq(f)}
                  {...tid(`sched-freq-${f}`)}
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
                placeholderTextColor={colors.textTertiary}
                keyboardType="email-address"
                autoCapitalize="none"
                {...tid('sched-email-input')}
              />
            )}
            <TouchableOpacity style={styles.schedSaveBtn} onPress={saveSchedule} {...tid('sched-save-btn')}>
              <Text style={styles.schedSaveBtnText}>Save</Text>
            </TouchableOpacity>
          </View>
        )}

        {loading ? (
          <View style={styles.loadingContainer}>
            <ActivityIndicator size="large" color={colors.accent} />
          </View>
        ) : totals ? (
          <>
            <View style={styles.topStats}>
              <View style={styles.heroStat}>
                <Text style={styles.heroValue} {...tid('total-touchpoints')}>{totals.total_touchpoints}</Text>
                <Text style={styles.heroLabel}>Total touchpoints</Text>
              </View>
            </View>

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

            {dailyData.length > 0 && (
              <View style={styles.chartSection}>
                <Text style={styles.sectionTitle}>Daily activity</Text>
                <View style={styles.chartCard}>
                  <View style={styles.chart}>
                    {dailyData.slice(-14).map((day, i) => {
                      const height = Math.max((day.total / maxDaily) * 80, 3);
                      const label = new Date(day.date).toLocaleDateString('en-US', { weekday: 'short' });
                      return (
                        <View key={i} style={styles.chartBar}>
                          <Text style={styles.chartBarValue}>{day.total || ''}</Text>
                          <View style={[styles.chartBarFill, { height, backgroundColor: colors.accent }]} />
                          <Text style={styles.chartBarLabel}>{label}</Text>
                        </View>
                      );
                    })}
                  </View>
                </View>
              </View>
            )}

            {isTeamReport && perUser.length > 1 && (
              <View style={styles.teamSection}>
                <Text style={styles.sectionTitle}>Team breakdown</Text>
                {perUser.sort((a, b) => b.total_touchpoints - a.total_touchpoints).map((u, i) => (
                  <View key={u.user_id} style={styles.teamRow} {...tid(`team-row-${i}`)}>
                    <View style={styles.teamRank}>
                      <Text style={styles.teamRankText}>{i + 1}</Text>
                    </View>
                    <View style={styles.teamInfo}>
                      <Text style={styles.teamName} numberOfLines={1}>{u.name}</Text>
                      <Text style={styles.teamDetails}>
                        {u.sms_sent + u.sms_personal} SMS · {u.emails_sent} Email · {u.digital_cards_sent} Cards · {u.review_invites_sent} Reviews
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

            <TouchableOpacity
              style={styles.emailBtn}
              onPress={handleEmailReport}
              disabled={sendingEmail}
              {...tid('email-report-btn')}
            >
              {sendingEmail ? (
                <ActivityIndicator size="small" color="#000" />
              ) : (
                <>
                  <Ionicons name="mail-outline" size={18} color="#000" />
                  <Text style={styles.emailBtnText}>Email this report</Text>
                </>
              )}
            </TouchableOpacity>
          </>
        ) : (
          <View style={styles.emptyState} {...tid('report-empty')}>
            <Ionicons name="bar-chart-outline" size={48} color={colors.textTertiary} />
            <Text style={styles.emptyText}>No activity for this period</Text>
            <TouchableOpacity onPress={() => setPreset('last_30')} style={styles.emptyBtn} {...tid('report-empty-last-30')}>
              <Text style={styles.emptyBtnText}>Show last 30 days</Text>
            </TouchableOpacity>
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const getStyles = (colors: any) => StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  scroll: { flex: 1 },
  scrollContent: { paddingBottom: 40 },
  presetRow: { marginTop: 12 },
  presetRowContent: { paddingHorizontal: 16, gap: 8 },
  presetBtn: {
    paddingHorizontal: 14, paddingVertical: 8, borderRadius: 18,
    backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border,
  },
  presetBtnActive: { backgroundColor: colors.accent, borderColor: colors.accent },
  presetText: { fontSize: FS.secondary, fontWeight: '700', color: colors.textSecondary },
  presetTextActive: { color: '#000' },
  teamToggle: {
    flexDirection: 'row', marginHorizontal: 16, marginTop: 12,
    backgroundColor: colors.card, borderRadius: 14, padding: 3, borderWidth: 1, borderColor: colors.border,
  },
  toggleBtn: { flex: 1, paddingVertical: 8, borderRadius: 11, alignItems: 'center' },
  toggleBtnActive: { backgroundColor: colors.accent },
  toggleText: { fontSize: FS.body, fontWeight: '700', color: colors.textSecondary },
  toggleTextActive: { color: '#000' },
  schedulePanel: {
    marginHorizontal: 16, marginTop: 12, backgroundColor: colors.card,
    borderRadius: 16, padding: 16, borderWidth: 1, borderColor: colors.border,
  },
  schedulePanelTitle: { fontSize: FS.heading, fontWeight: '700', color: colors.text, marginBottom: 12 },
  schedFreqRow: { flexDirection: 'row', gap: 8 },
  schedFreqBtn: {
    flex: 1, paddingVertical: 8, borderRadius: 10, backgroundColor: colors.surface, alignItems: 'center',
  },
  schedFreqBtnActive: { backgroundColor: colors.accent },
  schedFreqText: { fontSize: FS.secondary, fontWeight: '700', color: colors.textSecondary },
  schedFreqTextActive: { color: '#000' },
  schedEmailInput: {
    marginTop: 12, backgroundColor: colors.surface, borderRadius: 10,
    paddingHorizontal: 12, paddingVertical: 10, color: colors.text, fontSize: FS.body,
  },
  schedSaveBtn: {
    marginTop: 12, backgroundColor: colors.accent, borderRadius: 14,
    paddingVertical: 12, alignItems: 'center',
  },
  schedSaveBtnText: { fontSize: FS.heading, fontWeight: '700', color: '#000' },
  loadingContainer: { flex: 1, justifyContent: 'center', alignItems: 'center', paddingTop: 80 },
  topStats: { alignItems: 'center', marginTop: 24 },
  heroStat: { alignItems: 'center' },
  heroValue: { fontSize: 48, fontWeight: '800', color: colors.accent },
  heroLabel: { fontSize: FS.heading, fontWeight: '600', color: colors.textSecondary, marginTop: 4 },
  statGrid: {
    flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'center',
    gap: 10, marginTop: 20, paddingHorizontal: 16,
  },
  statCard: {
    width: '22%', minWidth: 80, backgroundColor: colors.card, borderRadius: 16,
    padding: 12, alignItems: 'center', borderWidth: 1, borderColor: colors.border,
  },
  statIcon: { width: 32, height: 32, borderRadius: 8, alignItems: 'center', justifyContent: 'center', marginBottom: 6 },
  statValue: { fontSize: FS.title, fontWeight: '800' },
  statLabel: { fontSize: FS.caption, fontWeight: '600', color: colors.textSecondary, marginTop: 2, textAlign: 'center' },
  chartSection: { marginTop: 24, paddingHorizontal: 16 },
  sectionTitle: { ...EYEBROW, color: colors.textSecondary, marginBottom: 10 },
  chartCard: { backgroundColor: colors.card, borderRadius: 16, borderWidth: 1, borderColor: colors.border, padding: 12 },
  chart: { flexDirection: 'row', alignItems: 'flex-end', height: 120, gap: 2, justifyContent: 'space-between' },
  chartBar: { flex: 1, alignItems: 'center', justifyContent: 'flex-end' },
  chartBarFill: { width: '80%', borderRadius: 3, minHeight: 3 },
  chartBarValue: { fontSize: 9, color: colors.textSecondary, marginBottom: 2 },
  chartBarLabel: { fontSize: 9, color: colors.textTertiary, marginTop: 4 },
  teamSection: { marginTop: 24, paddingHorizontal: 16 },
  teamRow: {
    flexDirection: 'row', alignItems: 'center', backgroundColor: colors.card,
    borderRadius: 16, padding: 14, marginBottom: 8, borderWidth: 1, borderColor: colors.border,
  },
  teamRank: {
    width: 28, height: 28, borderRadius: 14, backgroundColor: colors.surface,
    alignItems: 'center', justifyContent: 'center', marginRight: 12,
  },
  teamRankText: { fontSize: FS.body, fontWeight: '700', color: colors.accent },
  teamInfo: { flex: 1, minWidth: 0 },
  teamName: { fontSize: FS.heading, fontWeight: '700', color: colors.text, flexShrink: 1 },
  teamDetails: { fontSize: FS.secondary, color: colors.textSecondary, marginTop: 3 },
  teamScore: { alignItems: 'center' },
  teamScoreValue: { fontSize: FS.title, fontWeight: '800', color: colors.accent },
  teamScoreLabel: { fontSize: FS.caption, color: colors.textSecondary },
  emailBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8,
    marginHorizontal: 16, marginTop: 28, backgroundColor: colors.accent,
    borderRadius: 28, paddingVertical: 14,
  },
  emailBtnText: { fontSize: FS.heading, fontWeight: '700', color: '#000' },
  emptyState: { alignItems: 'center', paddingTop: 80, paddingHorizontal: 32 },
  emptyText: { fontSize: FS.heading, fontWeight: '700', color: colors.text, marginTop: 12, textAlign: 'center' },
  emptyBtn: { marginTop: 16, paddingHorizontal: 18, paddingVertical: 10, borderRadius: 14, borderWidth: 1, borderColor: colors.accent },
  emptyBtnText: { fontSize: FS.body, fontWeight: '700', color: colors.accent },
});
