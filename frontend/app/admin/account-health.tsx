import React, { useState, useEffect } from 'react';
import {
  View, Text, TouchableOpacity, StyleSheet, ScrollView, ActivityIndicator, TextInput,
  Modal,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useThemeStore } from '../../store/themeStore';
import { useToast } from '../../components/common/Toast';
import api from '../../services/api';

type HealthGrade = { score: number; grade: string; color: string };
type Account = {
  user_id: string; name: string; email: string; role: string;
  organization: string; store: string; contacts: number;
  messages_30d: number; touchpoints_30d: number; active_campaigns: number;
  days_since_login: number; health: HealthGrade; last_login: string;
};

const FILTERS = ['All', 'Critical', 'At Risk', 'Healthy'] as const;

export default function AccountHealthDashboard() {
  const router = useRouter();
  const colors = useThemeStore((s) => s.colors);
  const { showToast } = useToast();
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<typeof FILTERS[number]>('All');
  const [search, setSearch] = useState('');
  const [period, setPeriod] = useState(30);
  const [sendModal, setSendModal] = useState<Account | null>(null);
  const [sendEmail, setSendEmail] = useState('');
  const [sendNote, setSendNote] = useState('');
  const [sending, setSending] = useState(false);
  const [tab, setTab] = useState<'overview' | 'scheduled'>('overview');
  const [schedules, setSchedules] = useState<any[]>([]);
  const [schedLoading, setSchedLoading] = useState(false);
  const [showNewSched, setShowNewSched] = useState(false);
  const [schedScope, setSchedScope] = useState<'user' | 'org'>('user');
  const [schedTarget, setSchedTarget] = useState('');
  const [schedEmail, setSchedEmail] = useState('');
  const [schedName, setSchedName] = useState('');
  const [schedNote, setSchedNote] = useState('');
  const [creatingSched, setCreatingSched] = useState(false);

  useEffect(() => { load(); }, [period]);
  useEffect(() => { if (tab === 'scheduled') loadSchedules(); }, [tab]);

  const load = async () => {
    setLoading(true);
    try {
      const res = await api.get(`/account-health/overview?period=${period}`);
      setAccounts(res.data || []);
    } catch (e) {
      console.error('Failed to load account health:', e);
    }
    setLoading(false);
  };

  const filtered = accounts.filter(a => {
    if (filter !== 'All' && a.health.grade !== filter) return false;
    if (search) {
      const q = search.toLowerCase();
      return a.name.toLowerCase().includes(q) || a.email.toLowerCase().includes(q) || a.organization.toLowerCase().includes(q);
    }
    return true;
  });

  const stats = {
    total: accounts.length,
    healthy: accounts.filter(a => a.health.grade === 'Healthy').length,
    atRisk: accounts.filter(a => a.health.grade === 'At Risk').length,
    critical: accounts.filter(a => a.health.grade === 'Critical').length,
  };

  const openSendModal = (account: Account) => {
    setSendModal(account);
    setSendEmail(account.email);
    setSendNote('');
  };

  const handleSendReport = async () => {
    if (!sendModal || !sendEmail.trim()) {
      showToast('Please enter a recipient email', 'error');
      return;
    }
    setSending(true);
    try {
      await api.post(`/account-health/user/${sendModal.user_id}/send-report`, {
        recipient_email: sendEmail.trim(),
        recipient_name: sendModal.name,
        note: sendNote.trim(),
        period,
      });
      showToast('Health report sent!', 'success');
      setSendModal(null);
    } catch (e: any) {
      showToast(e?.response?.data?.detail || 'Failed to send report', 'error');
    }
    setSending(false);
  };

  const loadSchedules = async () => {
    setSchedLoading(true);
    try {
      const res = await api.get('/account-health/schedules');
      setSchedules(res.data || []);
    } catch { /* ignore */ }
    setSchedLoading(false);
  };

  const toggleSchedule = async (id: string, active: boolean) => {
    try {
      await api.put(`/account-health/schedules/${id}`, { active: !active });
      setSchedules(prev => prev.map(s => s.id === id ? { ...s, active: !active } : s));
      showToast(active ? 'Schedule paused' : 'Schedule activated', 'success');
    } catch {
      showToast('Failed to update schedule', 'error');
    }
  };

  const deleteSchedule = async (id: string) => {
    try {
      await api.delete(`/account-health/schedules/${id}`);
      setSchedules(prev => prev.filter(s => s.id !== id));
      showToast('Schedule deleted', 'success');
    } catch {
      showToast('Failed to delete', 'error');
    }
  };

  const createSchedule = async () => {
    if (!schedTarget.trim() || !schedEmail.trim()) {
      showToast('Please select an account and enter email', 'error');
      return;
    }
    setCreatingSched(true);
    try {
      const res = await api.post('/account-health/schedules', {
        scope: schedScope,
        target_id: schedTarget.trim(),
        target_name: schedName.trim(),
        recipient_email: schedEmail.trim(),
        note: schedNote.trim(),
      });
      setSchedules(prev => [res.data, ...prev]);
      setShowNewSched(false);
      setSchedTarget('');
      setSchedEmail('');
      setSchedName('');
      setSchedNote('');
      showToast('Monthly report scheduled!', 'success');
    } catch (e: any) {
      showToast(e?.response?.data?.detail || 'Failed to create schedule', 'error');
    }
    setCreatingSched(false);
  };

  const handleScheduleFromAccount = (a: Account) => {
    setSchedScope('user');
    setSchedTarget(a.user_id);
    setSchedEmail(a.email);
    setSchedName(a.name);
    setSchedNote('');
    setShowNewSched(true);
    setTab('scheduled');
  };

  return (
    <SafeAreaView style={[styles.safe, { backgroundColor: colors.bg }]}>
      <ScrollView style={styles.scroll} contentContainerStyle={styles.content}>
        {/* Header */}
        <View style={styles.header}>
          <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
            <Ionicons name="arrow-back" size={22} color={colors.text} />
          </TouchableOpacity>
          <View style={{ flex: 1 }}>
            <Text style={[styles.title, { color: colors.text }]}>Account Health</Text>
            <Text style={[styles.subtitle, { color: colors.textSecondary }]}>{stats.total} accounts tracked</Text>
          </View>
          {/* Period Toggle */}
          <View style={styles.periodRow}>
            {[30, 90].map(p => (
              <TouchableOpacity key={p} onPress={() => setPeriod(p)}
                style={[styles.periodBtn, period === p && { backgroundColor: '#007AFF', borderColor: '#007AFF' }, { borderColor: colors.surface, backgroundColor: colors.card }]}>
                <Text style={{ fontSize: 13, fontWeight: '600', color: period === p ? '#FFF' : colors.textSecondary }}>{p}d</Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>

        {/* Tab Bar */}
        <View style={[styles.tabBar, { borderColor: colors.surface }]}>
          <TouchableOpacity onPress={() => setTab('overview')} style={[styles.tabItem, tab === 'overview' && styles.tabItemActive]} data-testid="tab-overview">
            <Ionicons name="pulse" size={14} color={tab === 'overview' ? '#007AFF' : colors.textSecondary} />
            <Text style={{ fontSize: 15, fontWeight: '600', color: tab === 'overview' ? '#007AFF' : colors.textSecondary }}>Overview</Text>
          </TouchableOpacity>
          <TouchableOpacity onPress={() => setTab('scheduled')} style={[styles.tabItem, tab === 'scheduled' && styles.tabItemActive]} data-testid="tab-scheduled">
            <Ionicons name="calendar" size={14} color={tab === 'scheduled' ? '#C9A962' : colors.textSecondary} />
            <Text style={{ fontSize: 15, fontWeight: '600', color: tab === 'scheduled' ? '#C9A962' : colors.textSecondary }}>Scheduled Reports</Text>
            {schedules.filter(s => s.active).length > 0 && (
              <View style={{ backgroundColor: '#C9A962', borderRadius: 8, paddingHorizontal: 5, paddingVertical: 1 }}>
                <Text style={{ color: '#FFF', fontSize: 12, fontWeight: '700' }}>{schedules.filter(s => s.active).length}</Text>
              </View>
            )}
          </TouchableOpacity>
        </View>

        {tab === 'overview' && (
        <>
        {/* Summary Cards */}
        <View style={styles.summaryRow}>
          {[
            { label: 'Healthy', value: stats.healthy, color: '#34C759', icon: 'checkmark-circle' },
            { label: 'At Risk', value: stats.atRisk, color: '#FF9500', icon: 'warning' },
            { label: 'Critical', value: stats.critical, color: '#FF3B30', icon: 'alert-circle' },
          ].map(s => (
            <TouchableOpacity key={s.label} onPress={() => setFilter(filter === s.label ? 'All' : s.label as any)}
              style={[styles.summaryCard, { backgroundColor: colors.card, borderColor: filter === s.label ? s.color : colors.surface }]}>
              <Ionicons name={s.icon as any} size={20} color={s.color} />
              <Text style={[styles.summaryValue, { color: s.color }]}>{s.value}</Text>
              <Text style={[styles.summaryLabel, { color: colors.textSecondary }]}>{s.label}</Text>
            </TouchableOpacity>
          ))}
        </View>

        {/* Search */}
        <View style={[styles.searchBox, { backgroundColor: colors.card, borderColor: colors.surface }]}>
          <Ionicons name="search" size={16} color={colors.textSecondary} />
          <TextInput
            style={[styles.searchInput, { color: colors.text }]}
            placeholder="Search by name, email, or org..."
            placeholderTextColor={colors.textSecondary}
            value={search}
            onChangeText={setSearch}
          />
          {search ? (
            <TouchableOpacity onPress={() => setSearch('')}>
              <Ionicons name="close-circle" size={16} color={colors.textSecondary} />
            </TouchableOpacity>
          ) : null}
        </View>

        {/* Filter Pills */}
        <View style={styles.filterRow}>
          {FILTERS.map(f => (
            <TouchableOpacity key={f} onPress={() => setFilter(f)}
              style={[styles.filterPill, { backgroundColor: filter === f ? '#007AFF' : colors.card, borderColor: filter === f ? '#007AFF' : colors.surface }]}>
              <Text style={{ fontSize: 14, fontWeight: '600', color: filter === f ? '#FFF' : colors.textSecondary }}>{f}</Text>
            </TouchableOpacity>
          ))}
        </View>

        {/* Account List */}
        {loading ? (
          <ActivityIndicator size="large" color="#007AFF" style={{ marginTop: 40 }} />
        ) : filtered.length === 0 ? (
          <View style={styles.emptyState}>
            <Ionicons name="pulse" size={40} color={colors.textSecondary} />
            <Text style={[styles.emptyText, { color: colors.textSecondary }]}>No accounts match your filters</Text>
          </View>
        ) : (
          filtered.map((a) => (
            <TouchableOpacity key={a.user_id}
              style={[styles.accountRow, { backgroundColor: colors.card, borderColor: colors.surface }]}
              onPress={() => router.push(`/admin/account-health/${a.user_id}` as any)}
            >
              {/* Top row: Health dot + Name + Login badge */}
              <View style={styles.accountTopRow}>
                <View style={[styles.healthDot, { backgroundColor: a.health.color }]}>
                  <Text style={styles.healthScore}>{a.health.score}</Text>
                </View>
                <View style={styles.accountInfo}>
                  <Text style={[styles.accountName, { color: colors.text }]} numberOfLines={1}>{a.name}</Text>
                  <Text style={[styles.accountMeta, { color: colors.textSecondary }]} numberOfLines={1}>
                    {a.role} {a.organization ? `at ${a.organization}` : ''} {a.store ? `/ ${a.store}` : ''}
                  </Text>
                </View>
                <View style={[styles.loginBadge, {
                  backgroundColor: a.days_since_login <= 3 ? '#34C75915' : a.days_since_login <= 14 ? '#FF950015' : '#FF3B3015',
                }]}>
                  <Text style={{
                    fontSize: 12, fontWeight: '600',
                    color: a.days_since_login <= 3 ? '#34C759' : a.days_since_login <= 14 ? '#FF9500' : '#FF3B30',
                  }}>
                    {a.days_since_login <= 0 ? 'Today' : a.days_since_login >= 999 ? 'Never' : `${a.days_since_login}d ago`}
                  </Text>
                </View>
              </View>

              {/* Bottom row: Metrics + Actions */}
              <View style={styles.accountBottomRow}>
                <View style={styles.metricsRow}>
                  <View style={styles.metricItem}>
                    <Text style={[styles.metricValue, { color: colors.text }]}>{a.contacts}</Text>
                    <Text style={[styles.metricLabel, { color: colors.textSecondary }]}>contacts</Text>
                  </View>
                  <View style={styles.metricItem}>
                    <Text style={[styles.metricValue, { color: colors.text }]}>{a.messages_30d}</Text>
                    <Text style={[styles.metricLabel, { color: colors.textSecondary }]}>msgs</Text>
                  </View>
                  <View style={styles.metricItem}>
                    <Text style={[styles.metricValue, { color: colors.text }]}>{a.touchpoints_30d}</Text>
                    <Text style={[styles.metricLabel, { color: colors.textSecondary }]}>touches</Text>
                  </View>
                </View>
                <View style={styles.accountActions}>
                  <TouchableOpacity
                    onPress={(e) => { e.stopPropagation(); openSendModal(a); }}
                    style={styles.quickSendBtn}
                    data-testid={`send-report-${a.user_id}`}
                  >
                    <Ionicons name="paper-plane-outline" size={14} color="#C9A962" />
                  </TouchableOpacity>
                  <TouchableOpacity
                    onPress={(e) => { e.stopPropagation(); handleScheduleFromAccount(a); }}
                    style={styles.quickSendBtn}
                    data-testid={`schedule-${a.user_id}`}
                  >
                    <Ionicons name="calendar-outline" size={14} color="#007AFF" />
                  </TouchableOpacity>
                  <Ionicons name="chevron-forward" size={16} color={colors.textSecondary} />
                </View>
              </View>
            </TouchableOpacity>
          ))
        )}

        <View style={{ height: 40 }} />
        </>
        )}

        {tab === 'scheduled' && (
          <>
            {/* New Schedule Button */}
            <TouchableOpacity
              onPress={() => setShowNewSched(true)}
              style={[styles.newSchedBtn, { borderColor: '#C9A962' }]}
              data-testid="new-schedule-btn"
            >
              <Ionicons name="add-circle" size={18} color="#C9A962" />
              <Text style={{ color: '#C9A962', fontSize: 16, fontWeight: '600' }}>New Monthly Schedule</Text>
            </TouchableOpacity>

            <Text style={[styles.schedInfo, { color: colors.textSecondary }]}>
              Reports are automatically sent on the last day of each month.
            </Text>

            {/* New Schedule Form */}
            {showNewSched && (
              <View style={[styles.schedForm, { backgroundColor: colors.card, borderColor: colors.surface }]}>
                <Text style={[styles.schedFormTitle, { color: colors.text }]}>New Monthly Report</Text>

                <View style={styles.scopeRow}>
                  {(['user', 'org'] as const).map(s => (
                    <TouchableOpacity key={s} onPress={() => setSchedScope(s)}
                      style={[styles.scopeBtn, { backgroundColor: schedScope === s ? (s === 'user' ? '#007AFF' : '#AF52DE') : colors.surface, borderColor: schedScope === s ? (s === 'user' ? '#007AFF' : '#AF52DE') : colors.surface }]}
                      data-testid={`scope-${s}-btn`}
                    >
                      <Ionicons name={s === 'user' ? 'person' : 'business'} size={14} color={schedScope === s ? '#FFF' : colors.textSecondary} />
                      <Text style={{ color: schedScope === s ? '#FFF' : colors.textSecondary, fontSize: 14, fontWeight: '600' }}>{s === 'user' ? 'Individual' : 'Organization'}</Text>
                    </TouchableOpacity>
                  ))}
                </View>

                <Text style={[styles.inputLabel, { color: colors.textSecondary }]}>{schedScope === 'user' ? 'User' : 'Organization'} ID *</Text>
                <TextInput
                  value={schedTarget}
                  onChangeText={setSchedTarget}
                  placeholder={schedScope === 'user' ? 'Select from accounts above, or paste user ID' : 'Paste organization ID'}
                  placeholderTextColor="#666"
                  style={[styles.modalInput, { backgroundColor: colors.bg, color: colors.text, borderColor: colors.surface }]}
                  data-testid="sched-target-input"
                />

                {/* Quick-pick from loaded accounts */}
                {schedScope === 'user' && accounts.length > 0 && !schedTarget && (
                  <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginTop: 6, marginBottom: 4 }}>
                    {accounts.slice(0, 10).map(a => (
                      <TouchableOpacity key={a.user_id} onPress={() => { setSchedTarget(a.user_id); setSchedEmail(a.email); setSchedName(a.name); }}
                        style={[styles.quickPick, { backgroundColor: colors.surface }]}
                        data-testid={`quick-pick-${a.user_id}`}
                      >
                        <View style={[styles.miniDot, { backgroundColor: a.health.color }]}>
                          <Text style={{ color: '#FFF', fontSize: 8, fontWeight: '800' }}>{a.health.score}</Text>
                        </View>
                        <Text style={{ color: colors.text, fontSize: 13 }} numberOfLines={1}>{a.name}</Text>
                      </TouchableOpacity>
                    ))}
                  </ScrollView>
                )}

                <Text style={[styles.inputLabel, { color: colors.textSecondary }]}>Recipient Email *</Text>
                <TextInput
                  value={schedEmail}
                  onChangeText={setSchedEmail}
                  placeholder="email@example.com"
                  placeholderTextColor="#666"
                  keyboardType="email-address"
                  autoCapitalize="none"
                  style={[styles.modalInput, { backgroundColor: colors.bg, color: colors.text, borderColor: colors.surface }]}
                  data-testid="sched-email-input"
                />

                <Text style={[styles.inputLabel, { color: colors.textSecondary }]}>Note (included in email)</Text>
                <TextInput
                  value={schedNote}
                  onChangeText={setSchedNote}
                  placeholder="Optional message..."
                  placeholderTextColor="#666"
                  style={[styles.modalInput, { backgroundColor: colors.bg, color: colors.text, borderColor: colors.surface }]}
                  data-testid="sched-note-input"
                />

                <View style={{ flexDirection: 'row', gap: 10, marginTop: 14 }}>
                  <TouchableOpacity onPress={() => setShowNewSched(false)} style={[styles.cancelBtn, { borderColor: colors.surface }]} data-testid="cancel-new-sched-btn">
                    <Text style={{ color: colors.textSecondary, fontWeight: '600', fontSize: 16 }}>Cancel</Text>
                  </TouchableOpacity>
                  <TouchableOpacity onPress={createSchedule} disabled={creatingSched} style={[styles.sendReportBtn, creatingSched && { opacity: 0.6 }]} data-testid="create-schedule-btn">
                    {creatingSched ? <ActivityIndicator size="small" color="#FFF" /> : <Ionicons name="calendar-outline" size={14} color="#FFF" />}
                    <Text style={{ color: '#FFF', fontWeight: '700', fontSize: 16 }}>{creatingSched ? 'Creating...' : 'Schedule'}</Text>
                  </TouchableOpacity>
                </View>
              </View>
            )}

            {/* Schedules List */}
            {schedLoading ? (
              <ActivityIndicator size="large" color="#C9A962" style={{ marginTop: 30 }} />
            ) : schedules.length === 0 ? (
              <View style={styles.emptyState}>
                <Ionicons name="calendar-outline" size={40} color={colors.textSecondary} />
                <Text style={[styles.emptyText, { color: colors.textSecondary }]}>No scheduled reports yet</Text>
                <Text style={{ color: colors.textSecondary, fontSize: 14, textAlign: 'center', lineHeight: 18 }}>
                  Create a monthly schedule to automatically send health snapshots to account contacts on the last day of each month.
                </Text>
              </View>
            ) : (
              schedules.map((s) => (
                <View key={s.id} style={[styles.schedRow, { backgroundColor: colors.card, borderColor: colors.surface, opacity: s.active ? 1 : 0.5 }]} data-testid={`schedule-${s.id}`}>
                  <View style={[styles.schedIcon, { backgroundColor: s.scope === 'user' ? '#007AFF20' : '#AF52DE20' }]}>
                    <Ionicons name={s.scope === 'user' ? 'person' : 'business'} size={16} color={s.scope === 'user' ? '#007AFF' : '#AF52DE'} />
                  </View>
                  <View style={{ flex: 1 }}>
                    <Text style={[styles.accountName, { color: colors.text }]}>{s.target_name || s.target_id}</Text>
                    <Text style={{ fontSize: 13, color: colors.textSecondary, marginTop: 2 }}>
                      {s.recipient_email} {s.note ? `— "${s.note}"` : ''}
                    </Text>
                    <Text style={{ fontSize: 12, color: '#888', marginTop: 2 }}>
                      Monthly &bull; {s.last_sent_at ? `Last sent: ${new Date(s.last_sent_at).toLocaleDateString()}` : 'Not yet sent'}
                    </Text>
                  </View>
                  <TouchableOpacity onPress={() => toggleSchedule(s.id, s.active)} style={{ padding: 8 }} data-testid={`toggle-schedule-${s.id}`}>
                    <Ionicons name={s.active ? 'toggle' : 'toggle-outline'} size={28} color={s.active ? '#34C759' : '#888'} />
                  </TouchableOpacity>
                  <TouchableOpacity onPress={() => deleteSchedule(s.id)} style={{ padding: 8 }} data-testid={`delete-schedule-${s.id}`}>
                    <Ionicons name="trash-outline" size={18} color="#FF3B30" />
                  </TouchableOpacity>
                </View>
              ))
            )}

            <View style={{ height: 40 }} />
          </>
        )}
      </ScrollView>

      {/* Send Report Modal */}
      {sendModal && (
        <Modal visible={!!sendModal} transparent animationType="fade" onRequestClose={() => setSendModal(null)}>
          <View style={styles.modalOverlay}>
            <View style={[styles.modalContent, { backgroundColor: colors.card, borderColor: colors.surface }]}>
              <View style={styles.modalHeader}>
                <Ionicons name="paper-plane" size={20} color="#C9A962" />
                <Text style={[styles.modalTitle, { color: colors.text }]}>Send Health Report</Text>
                <TouchableOpacity onPress={() => setSendModal(null)} data-testid="close-send-modal-btn">
                  <Ionicons name="close" size={22} color={colors.textSecondary} />
                </TouchableOpacity>
              </View>

              <Text style={[styles.modalDesc, { color: colors.textSecondary }]}>
                Email a {period}-day health snapshot for {sendModal.name}
              </Text>

              <Text style={[styles.inputLabel, { color: colors.textSecondary }]}>Recipient Email *</Text>
              <TextInput
                value={sendEmail}
                onChangeText={setSendEmail}
                placeholder="email@example.com"
                placeholderTextColor="#666"
                keyboardType="email-address"
                autoCapitalize="none"
                style={[styles.modalInput, { backgroundColor: colors.bg, color: colors.text, borderColor: colors.surface }]}
                data-testid="send-report-email-input"
              />

              <Text style={[styles.inputLabel, { color: colors.textSecondary }]}>Personal Note</Text>
              <TextInput
                value={sendNote}
                onChangeText={setSendNote}
                placeholder="Add a personal message (optional)..."
                placeholderTextColor="#666"
                multiline
                numberOfLines={3}
                style={[styles.modalInput, styles.textarea, { backgroundColor: colors.bg, color: colors.text, borderColor: colors.surface }]}
                data-testid="send-report-note-input"
              />

              <View style={styles.modalActions}>
                <TouchableOpacity onPress={() => setSendModal(null)} style={[styles.cancelBtn, { borderColor: colors.surface }]} data-testid="cancel-send-report-btn">
                  <Text style={{ color: colors.textSecondary, fontWeight: '600', fontSize: 16 }}>Cancel</Text>
                </TouchableOpacity>
                <TouchableOpacity onPress={handleSendReport} disabled={sending} style={[styles.sendReportBtn, sending && { opacity: 0.6 }]} data-testid="confirm-send-report-btn">
                  {sending ? <ActivityIndicator size="small" color="#FFF" /> : <Ionicons name="paper-plane" size={14} color="#FFF" />}
                  <Text style={{ color: '#FFF', fontWeight: '700', fontSize: 16 }}>{sending ? 'Sending...' : 'Send Report'}</Text>
                </TouchableOpacity>
              </View>
            </View>
          </View>
        </Modal>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  scroll: { flex: 1 },
  content: { padding: 16, maxWidth: 900, alignSelf: 'center' as any, width: '100%' },
  header: { flexDirection: 'row', alignItems: 'center', gap: 12, marginBottom: 16 },
  backBtn: { width: 36, height: 36, borderRadius: 18, alignItems: 'center', justifyContent: 'center' },
  title: { fontSize: 22, fontWeight: '700' },
  subtitle: { fontSize: 15, marginTop: 2 },
  periodRow: { flexDirection: 'row', gap: 6 },
  periodBtn: { paddingHorizontal: 10, paddingVertical: 5, borderRadius: 8, borderWidth: 1 },
  summaryRow: { flexDirection: 'row', gap: 10, marginBottom: 16 },
  summaryCard: { flex: 1, alignItems: 'center', padding: 14, borderRadius: 14, borderWidth: 1.5, gap: 4 },
  summaryValue: { fontSize: 22, fontWeight: '800' },
  summaryLabel: { fontSize: 13, fontWeight: '600' },
  searchBox: { flexDirection: 'row', alignItems: 'center', gap: 8, padding: 10, borderRadius: 10, borderWidth: 1, marginBottom: 10 },
  searchInput: { flex: 1, fontSize: 16 },
  filterRow: { flexDirection: 'row', gap: 6, marginBottom: 14 },
  filterPill: { paddingHorizontal: 14, paddingVertical: 6, borderRadius: 20, borderWidth: 1 },
  emptyState: { alignItems: 'center', paddingVertical: 40, gap: 10 },
  emptyText: { fontSize: 16 },
  accountRow: { padding: 12, borderRadius: 12, borderWidth: 1, marginBottom: 6 },
  accountTopRow: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  accountInfo: { flex: 1, minWidth: 0 },
  accountBottomRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginTop: 10, paddingTop: 10, borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: 'rgba(255,255,255,0.08)' },
  accountActions: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  healthDot: { width: 38, height: 38, borderRadius: 19, alignItems: 'center', justifyContent: 'center' },
  healthScore: { color: '#FFF', fontSize: 14, fontWeight: '800' },
  accountName: { fontSize: 16, fontWeight: '600' },
  accountMeta: { fontSize: 13, marginTop: 2 },
  metricsRow: { flexDirection: 'row', gap: 12 },
  metricItem: { alignItems: 'center' },
  metricValue: { fontSize: 16, fontWeight: '700' },
  metricLabel: { fontSize: 9, marginTop: 1 },
  loginBadge: { paddingHorizontal: 8, paddingVertical: 4, borderRadius: 8 },
  quickSendBtn: { width: 30, height: 30, borderRadius: 15, alignItems: 'center', justifyContent: 'center' },
  // Modal styles
  modalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.5)', justifyContent: 'center', alignItems: 'center', padding: 20 },
  modalContent: { width: '100%', maxWidth: 460, borderRadius: 16, borderWidth: 1, padding: 24 },
  modalHeader: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 8 },
  modalTitle: { flex: 1, fontSize: 19, fontWeight: '700' },
  modalDesc: { fontSize: 15, marginBottom: 16, lineHeight: 18 },
  inputLabel: { fontSize: 13, fontWeight: '600', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 4, marginTop: 8 },
  modalInput: { fontSize: 16, paddingHorizontal: 12, paddingVertical: 10, borderRadius: 8, borderWidth: 1 },
  textarea: { minHeight: 70, textAlignVertical: 'top' },
  modalActions: { flexDirection: 'row', gap: 10, marginTop: 20 },
  cancelBtn: { flex: 1, paddingVertical: 12, borderRadius: 10, borderWidth: 1, alignItems: 'center' },
  sendReportBtn: { flex: 1, flexDirection: 'row', gap: 6, paddingVertical: 12, borderRadius: 10, backgroundColor: '#C9A962', alignItems: 'center', justifyContent: 'center' },
  // Tab bar
  tabBar: { flexDirection: 'row', borderBottomWidth: 1, marginBottom: 14, gap: 4 },
  tabItem: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingVertical: 10, paddingHorizontal: 12, borderBottomWidth: 2, borderBottomColor: 'transparent' },
  tabItemActive: { borderBottomColor: '#007AFF' },
  // Scheduled reports
  newSchedBtn: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 12, paddingHorizontal: 16, borderRadius: 10, borderWidth: 1, borderStyle: 'dashed', marginBottom: 10 },
  schedInfo: { fontSize: 14, marginBottom: 14, lineHeight: 17 },
  schedForm: { borderRadius: 12, borderWidth: 1, padding: 16, marginBottom: 14 },
  schedFormTitle: { fontSize: 17, fontWeight: '700', marginBottom: 12 },
  scopeRow: { flexDirection: 'row', gap: 8, marginBottom: 10 },
  scopeBtn: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 14, paddingVertical: 8, borderRadius: 8, borderWidth: 1 },
  quickPick: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 10, paddingVertical: 6, borderRadius: 8, marginRight: 6 },
  miniDot: { width: 20, height: 20, borderRadius: 10, alignItems: 'center', justifyContent: 'center' },
  schedRow: { flexDirection: 'row', alignItems: 'center', gap: 12, padding: 12, borderRadius: 12, borderWidth: 1, marginBottom: 6 },
  schedIcon: { width: 36, height: 36, borderRadius: 18, alignItems: 'center', justifyContent: 'center' },
});
