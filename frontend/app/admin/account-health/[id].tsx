import React, { useState, useEffect } from 'react';
import {
  View, Text, TouchableOpacity, StyleSheet, ScrollView, ActivityIndicator,
  TextInput, Modal,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { useThemeStore } from '../../../store/themeStore';
import { useToast } from '../../../components/common/Toast';
import api from '../../../services/api';

type Metrics = {
  total_contacts: number; new_contacts: number; total_messages: number;
  messages_30d: number; total_tasks: number; completed_tasks: number;
  active_campaigns: number; total_campaigns: number; enrollments: number;
  enrollments_30d: number; total_touchpoints: number; touchpoints_30d: number;
  event_breakdown: Record<string, number>; short_urls_created: number;
  link_clicks_30d: number; cards_shared: number; days_since_login: number;
  last_login: string | null;
};

type HealthReport = {
  user: any; organization: string; store: string;
  metrics: Metrics; health: { score: number; grade: string; color: string };
  recent_events: any[]; period_days: number;
};

const MetricTile = ({ icon, label, value, sub, color }: any) => {
  const colors = useThemeStore((s) => s.colors);
  return (
    <View style={[tileStyles.tile, { backgroundColor: colors.card, borderColor: colors.surface }]} data-testid={`metric-tile-${label.toLowerCase().replace(/\s/g, '-')}`}>
      <Ionicons name={icon} size={18} color={color} />
      <Text style={[tileStyles.value, { color: colors.text }]}>{value}</Text>
      <Text style={[tileStyles.label, { color: colors.textSecondary }]}>{label}</Text>
      {sub ? <Text style={[tileStyles.sub, { color }]}>{sub}</Text> : null}
    </View>
  );
};

const tileStyles = StyleSheet.create({
  tile: { flex: 1, minWidth: 100, alignItems: 'center', padding: 14, borderRadius: 12, borderWidth: 1, gap: 2 },
  value: { fontSize: 22, fontWeight: '800', marginTop: 4 },
  label: { fontSize: 11, fontWeight: '600' },
  sub: { fontSize: 10, fontWeight: '600', marginTop: 2 },
});

export default function AccountHealthDetail() {
  const router = useRouter();
  const { id } = useLocalSearchParams<{ id: string }>();
  const colors = useThemeStore((s) => s.colors);
  const { showToast } = useToast();
  const [report, setReport] = useState<HealthReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [period, setPeriod] = useState(30);
  const [showSendModal, setShowSendModal] = useState(false);
  const [sendEmail, setSendEmail] = useState('');
  const [sendName, setSendName] = useState('');
  const [sendNote, setSendNote] = useState('');
  const [sending, setSending] = useState(false);

  useEffect(() => { load(); }, [id, period]);

  const load = async () => {
    setLoading(true);
    try {
      const res = await api.get(`/account-health/user/${id}?period=${period}`);
      setReport(res.data);
      // Pre-fill email from user data
      if (res.data?.user?.email) setSendEmail(res.data.user.email);
      if (res.data?.user?.name) setSendName(res.data.user.name);
    } catch (e) {
      console.error('Failed to load:', e);
    }
    setLoading(false);
  };

  const handleSendReport = async () => {
    if (!sendEmail.trim()) {
      showToast('Please enter a recipient email', 'error');
      return;
    }
    setSending(true);
    try {
      await api.post(`/account-health/user/${id}/send-report`, {
        recipient_email: sendEmail.trim(),
        recipient_name: sendName.trim(),
        note: sendNote.trim(),
        period,
      });
      showToast('Health report sent!', 'success');
      setShowSendModal(false);
      setSendNote('');
    } catch (e: any) {
      showToast(e?.response?.data?.detail || 'Failed to send report', 'error');
    }
    setSending(false);
  };

  if (loading) {
    return (
      <SafeAreaView style={[styles.safe, { backgroundColor: colors.bg }]}>
        <ActivityIndicator size="large" color="#007AFF" style={{ marginTop: 40 }} />
      </SafeAreaView>
    );
  }

  if (!report) {
    return (
      <SafeAreaView style={[styles.safe, { backgroundColor: colors.bg }]}>
        <View style={{ padding: 20 }}>
          <Text style={{ color: colors.text }}>Account not found</Text>
        </View>
      </SafeAreaView>
    );
  }

  const { user, metrics, health } = report;
  const m = metrics;

  return (
    <SafeAreaView style={[styles.safe, { backgroundColor: colors.bg }]}>
      <ScrollView style={styles.scroll} contentContainerStyle={styles.content}>
        {/* Header */}
        <View style={styles.header}>
          <View style={styles.headerTopRow}>
            <TouchableOpacity onPress={() => router.back()} style={styles.backBtn} data-testid="back-btn">
              <Ionicons name="arrow-back" size={22} color={colors.text} />
            </TouchableOpacity>
            <View style={{ flex: 1 }}>
              <Text style={[styles.title, { color: colors.text }]} numberOfLines={2}>{user.name || user.email}</Text>
              <Text style={[styles.subtitle, { color: colors.textSecondary }]} numberOfLines={2}>
                {user.role} {report.organization ? `at ${report.organization}` : ''} {report.store ? `/ ${report.store}` : ''}
              </Text>
            </View>
          </View>
          <View style={styles.headerActions}>
            <TouchableOpacity
              onPress={() => setShowSendModal(true)}
              style={[styles.sendBtn, { backgroundColor: '#C9A96218', borderColor: '#C9A962' }]}
              data-testid="send-report-btn"
            >
              <Ionicons name="paper-plane" size={14} color="#C9A962" />
              <Text style={{ fontSize: 12, fontWeight: '600', color: '#C9A962' }}>Send Report</Text>
            </TouchableOpacity>
            <View style={styles.periodRow}>
              {[30, 90].map(p => (
                <TouchableOpacity key={p} onPress={() => setPeriod(p)}
                  style={[styles.periodBtn, { backgroundColor: period === p ? '#007AFF' : colors.card, borderColor: period === p ? '#007AFF' : colors.surface }]}>
                  <Text style={{ fontSize: 11, fontWeight: '600', color: period === p ? '#FFF' : colors.textSecondary }}>{p}d</Text>
                </TouchableOpacity>
              ))}
            </View>
          </View>
        </View>

        {/* Health Score Banner */}
        <View style={[styles.healthBanner, { backgroundColor: `${health.color}12`, borderColor: `${health.color}30` }]}>
          <View style={[styles.healthCircle, { backgroundColor: health.color }]}>
            <Text style={styles.healthScoreText}>{health.score}</Text>
          </View>
          <View style={{ flex: 1 }}>
            <Text style={[styles.healthGrade, { color: health.color }]}>{health.grade}</Text>
            <Text style={[styles.healthSub, { color: colors.textSecondary }]}>
              {health.score >= 70 ? 'This account is actively using the platform' :
               health.score >= 40 ? 'This account shows declining engagement' :
               'This account needs immediate attention'}
            </Text>
          </View>
          <View style={{ alignItems: 'flex-end' }}>
            <Text style={[styles.loginLabel, { color: colors.textSecondary }]}>Last Login</Text>
            <Text style={[styles.loginValue, { color: m.days_since_login <= 7 ? '#34C759' : m.days_since_login <= 30 ? '#FF9500' : '#FF3B30' }]}>
              {m.days_since_login <= 0 ? 'Today' : m.days_since_login >= 999 ? 'Never' : `${m.days_since_login}d ago`}
            </Text>
          </View>
        </View>

        {/* Key Metrics Grid */}
        <Text style={[styles.sectionTitle, { color: colors.text }]}>Key Metrics ({period} days)</Text>
        <View style={styles.metricsGrid}>
          <MetricTile icon="people" label="Total Contacts" value={m.total_contacts} sub={m.new_contacts > 0 ? `+${m.new_contacts} new` : null} color="#007AFF" />
          <MetricTile icon="chatbubble" label="Messages Sent" value={m.messages_30d} sub={`${m.total_messages} total`} color="#5856D6" />
          <MetricTile icon="pulse" label="Touchpoints" value={m.touchpoints_30d} sub={`${m.total_touchpoints} total`} color="#FF9500" />
        </View>
        <View style={[styles.metricsGrid, { marginTop: 8 }]}>
          <MetricTile icon="megaphone" label="Active Campaigns" value={m.active_campaigns} sub={`${m.total_campaigns} total`} color="#34C759" />
          <MetricTile icon="person-add" label="Enrollments" value={m.enrollments_30d} sub={`${m.enrollments} total`} color="#AF52DE" />
          <MetricTile icon="checkmark-done" label="Tasks Done" value={m.completed_tasks} sub={`of ${m.total_tasks}`} color="#00C7BE" />
        </View>
        <View style={[styles.metricsGrid, { marginTop: 8 }]}>
          <MetricTile icon="link" label="Links Created" value={m.short_urls_created} color="#FF2D55" />
          <MetricTile icon="finger-print" label="Link Clicks" value={m.link_clicks_30d} color="#FFCC00" />
          <MetricTile icon="card" label="Cards Shared" value={m.cards_shared} color="#007AFF" />
        </View>

        {/* Touchpoint Breakdown */}
        {Object.keys(m.event_breakdown).length > 0 && (
          <>
            <Text style={[styles.sectionTitle, { color: colors.text, marginTop: 20 }]}>Touchpoint Breakdown</Text>
            <View style={[styles.breakdownCard, { backgroundColor: colors.card, borderColor: colors.surface }]}>
              {Object.entries(m.event_breakdown)
                .sort(([, a], [, b]) => (b as number) - (a as number))
                .map(([type, count]) => (
                  <View key={type} style={[styles.breakdownRow, { borderBottomColor: colors.surface }]}>
                    <Text style={[styles.breakdownType, { color: colors.text }]}>{type.replace(/_/g, ' ')}</Text>
                    <View style={[styles.breakdownBar, { backgroundColor: colors.surface }]}>
                      <View style={[styles.breakdownFill, { width: `${Math.min(100, ((count as number) / Math.max(...Object.values(m.event_breakdown) as number[])) * 100)}%`, backgroundColor: '#007AFF' }]} />
                    </View>
                    <Text style={[styles.breakdownCount, { color: colors.text }]}>{count as number}</Text>
                  </View>
                ))}
            </View>
          </>
        )}

        {/* Recent Activity */}
        {report.recent_events.length > 0 && (
          <>
            <Text style={[styles.sectionTitle, { color: colors.text, marginTop: 20 }]}>Recent Activity</Text>
            <View style={[styles.timelineCard, { backgroundColor: colors.card, borderColor: colors.surface }]}>
              {report.recent_events.map((ev, i) => (
                <View key={i} style={[styles.timelineRow, i < report.recent_events.length - 1 && { borderBottomWidth: 1, borderBottomColor: colors.surface }]}>
                  <View style={[styles.timelineDot, { backgroundColor: '#007AFF20' }]}>
                    <Ionicons name="pulse" size={12} color="#007AFF" />
                  </View>
                  <View style={{ flex: 1 }}>
                    <Text style={[styles.timelineType, { color: colors.text }]}>{(ev.event_type || '').replace(/_/g, ' ')}</Text>
                    <Text style={[styles.timelineDetail, { color: colors.textSecondary }]}>
                      {ev.contact_name || ''} {ev.timestamp ? `- ${new Date(ev.timestamp).toLocaleDateString()}` : ''}
                    </Text>
                  </View>
                </View>
              ))}
            </View>
          </>
        )}

        {/* Account Info */}
        <Text style={[styles.sectionTitle, { color: colors.text, marginTop: 20 }]}>Account Info</Text>
        <View style={[styles.infoCard, { backgroundColor: colors.card, borderColor: colors.surface }]}>
          {[
            { label: 'Email', value: user.email },
            { label: 'Role', value: user.role },
            { label: 'Organization', value: report.organization || 'None' },
            { label: 'Store', value: report.store || 'None' },
            { label: 'Created', value: user.created_at ? new Date(user.created_at).toLocaleDateString() : 'Unknown' },
            { label: 'TOS Accepted', value: user.tos_accepted ? 'Yes' : 'No' },
          ].map((item, i) => (
            <View key={i} style={[styles.infoRow, i < 5 && { borderBottomWidth: 1, borderBottomColor: colors.surface }]}>
              <Text style={[styles.infoLabel, { color: colors.textSecondary }]}>{item.label}</Text>
              <Text style={[styles.infoValue, { color: colors.text }]}>{item.value}</Text>
            </View>
          ))}
        </View>

        <View style={{ height: 40 }} />
      </ScrollView>

      {/* Send Report Modal */}
      <Modal visible={showSendModal} transparent animationType="fade" onRequestClose={() => setShowSendModal(false)}>
        <View style={styles.modalOverlay}>
          <View style={[styles.modalContent, { backgroundColor: colors.card, borderColor: colors.surface }]}>
            <View style={styles.modalHeader}>
              <Ionicons name="paper-plane" size={20} color="#C9A962" />
              <Text style={[styles.modalTitle, { color: colors.text }]}>Send Health Report</Text>
              <TouchableOpacity onPress={() => setShowSendModal(false)} data-testid="close-send-modal-btn">
                <Ionicons name="close" size={22} color={colors.textSecondary} />
              </TouchableOpacity>
            </View>

            <Text style={[styles.modalDesc, { color: colors.textSecondary }]}>
              Email a comprehensive {period}-day health snapshot for {user.name || user.email}
            </Text>

            <Text style={[styles.inputLabel, { color: colors.textSecondary }]}>Recipient Email *</Text>
            <TextInput
              value={sendEmail}
              onChangeText={setSendEmail}
              placeholder="email@example.com"
              placeholderTextColor="#666"
              keyboardType="email-address"
              autoCapitalize="none"
              style={[styles.input, { backgroundColor: colors.bg, color: colors.text, borderColor: colors.surface }]}
              data-testid="send-report-email-input"
            />

            <Text style={[styles.inputLabel, { color: colors.textSecondary }]}>Recipient Name</Text>
            <TextInput
              value={sendName}
              onChangeText={setSendName}
              placeholder="Name (optional)"
              placeholderTextColor="#666"
              style={[styles.input, { backgroundColor: colors.bg, color: colors.text, borderColor: colors.surface }]}
              data-testid="send-report-name-input"
            />

            <Text style={[styles.inputLabel, { color: colors.textSecondary }]}>Personal Note</Text>
            <TextInput
              value={sendNote}
              onChangeText={setSendNote}
              placeholder="Add a personal message (optional)..."
              placeholderTextColor="#666"
              multiline
              numberOfLines={3}
              style={[styles.input, styles.textarea, { backgroundColor: colors.bg, color: colors.text, borderColor: colors.surface }]}
              data-testid="send-report-note-input"
            />

            <View style={styles.modalActions}>
              <TouchableOpacity
                onPress={() => setShowSendModal(false)}
                style={[styles.cancelBtn, { borderColor: colors.surface }]}
                data-testid="cancel-send-report-btn"
              >
                <Text style={{ color: colors.textSecondary, fontWeight: '600', fontSize: 14 }}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity
                onPress={handleSendReport}
                disabled={sending}
                style={[styles.sendReportBtn, sending && { opacity: 0.6 }]}
                data-testid="confirm-send-report-btn"
              >
                {sending ? (
                  <ActivityIndicator size="small" color="#FFF" />
                ) : (
                  <Ionicons name="paper-plane" size={14} color="#FFF" />
                )}
                <Text style={{ color: '#FFF', fontWeight: '700', fontSize: 14 }}>{sending ? 'Sending...' : 'Send Report'}</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  scroll: { flex: 1 },
  content: { padding: 16, maxWidth: 800, alignSelf: 'center' as any, width: '100%' },
  header: { marginBottom: 16 },
  headerTopRow: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  headerActions: { flexDirection: 'row', alignItems: 'center', gap: 10, marginTop: 12, marginLeft: 48 },
  backBtn: { width: 36, height: 36, borderRadius: 18, alignItems: 'center', justifyContent: 'center' },
  title: { fontSize: 20, fontWeight: '700' },
  subtitle: { fontSize: 12, marginTop: 2 },
  sendBtn: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 12, paddingVertical: 7, borderRadius: 8, borderWidth: 1 },
  periodRow: { flexDirection: 'row', gap: 6 },
  periodBtn: { paddingHorizontal: 10, paddingVertical: 5, borderRadius: 8, borderWidth: 1 },
  healthBanner: { flexDirection: 'row', alignItems: 'center', gap: 14, padding: 16, borderRadius: 16, borderWidth: 1.5, marginBottom: 20 },
  healthCircle: { width: 52, height: 52, borderRadius: 26, alignItems: 'center', justifyContent: 'center' },
  healthScoreText: { color: '#FFF', fontSize: 18, fontWeight: '900' },
  healthGrade: { fontSize: 18, fontWeight: '800' },
  healthSub: { fontSize: 12, marginTop: 2, lineHeight: 17 },
  loginLabel: { fontSize: 10 },
  loginValue: { fontSize: 14, fontWeight: '700', marginTop: 2 },
  sectionTitle: { fontSize: 15, fontWeight: '700', marginBottom: 10 },
  metricsGrid: { flexDirection: 'row', gap: 8 },
  breakdownCard: { borderRadius: 12, borderWidth: 1, padding: 12 },
  breakdownRow: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 8, borderBottomWidth: 1 },
  breakdownType: { width: 120, fontSize: 12, fontWeight: '600', textTransform: 'capitalize' },
  breakdownBar: { flex: 1, height: 8, borderRadius: 4, overflow: 'hidden' },
  breakdownFill: { height: '100%', borderRadius: 4 },
  breakdownCount: { fontSize: 13, fontWeight: '700', width: 40, textAlign: 'right' },
  timelineCard: { borderRadius: 12, borderWidth: 1, overflow: 'hidden' },
  timelineRow: { flexDirection: 'row', alignItems: 'center', gap: 10, padding: 12 },
  timelineDot: { width: 26, height: 26, borderRadius: 13, alignItems: 'center', justifyContent: 'center' },
  timelineType: { fontSize: 13, fontWeight: '600', textTransform: 'capitalize' },
  timelineDetail: { fontSize: 11, marginTop: 1 },
  infoCard: { borderRadius: 12, borderWidth: 1, overflow: 'hidden' },
  infoRow: { flexDirection: 'row', justifyContent: 'space-between', padding: 12 },
  infoLabel: { fontSize: 13 },
  infoValue: { fontSize: 13, fontWeight: '600' },
  // Modal styles
  modalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.5)', justifyContent: 'center', alignItems: 'center', padding: 20 },
  modalContent: { width: '100%', maxWidth: 460, borderRadius: 16, borderWidth: 1, padding: 24 },
  modalHeader: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 8 },
  modalTitle: { flex: 1, fontSize: 18, fontWeight: '700' },
  modalDesc: { fontSize: 13, marginBottom: 16, lineHeight: 18 },
  inputLabel: { fontSize: 11, fontWeight: '600', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 4, marginTop: 8 },
  input: { fontSize: 14, paddingHorizontal: 12, paddingVertical: 10, borderRadius: 8, borderWidth: 1 },
  textarea: { minHeight: 70, textAlignVertical: 'top' },
  modalActions: { flexDirection: 'row', gap: 10, marginTop: 20 },
  cancelBtn: { flex: 1, paddingVertical: 12, borderRadius: 10, borderWidth: 1, alignItems: 'center' },
  sendReportBtn: { flex: 1, flexDirection: 'row', gap: 6, paddingVertical: 12, borderRadius: 10, backgroundColor: '#C9A962', alignItems: 'center', justifyContent: 'center' },
});
