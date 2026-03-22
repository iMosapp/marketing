import React, { useState, useEffect, useCallback } from 'react';
import {
  View, Text, TouchableOpacity, ScrollView, RefreshControl,
  StyleSheet, ActivityIndicator, TextInput, Platform,
} from 'react-native';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { adminAPI } from '../../services/api';
import { useAuthStore } from '../../store/authStore';
import { WebModal } from '../../components/WebModal';
import { SafeAreaView } from 'react-native-safe-area-context';

const SIGNAL_ICONS: Record<string, { icon: string; color: string }> = {
  card_viewed: { icon: 'eye', color: '#007AFF' },
  card_downloaded: { icon: 'download', color: '#34C759' },
  card_shared: { icon: 'share-social', color: '#AF52DE' },
  digital_card_viewed: { icon: 'person-circle', color: '#007AFF' },
  review_link_clicked: { icon: 'star', color: '#FFD60A' },
  showcase_viewed: { icon: 'images', color: '#C9A962' },
  link_page_viewed: { icon: 'link', color: '#AF52DE' },
  contact_saved: { icon: 'person-add', color: '#34C759' },
  link_clicked: { icon: 'open', color: '#007AFF' },
};

function timeAgo(minutes: number): string {
  if (minutes < 1) return 'Just now';
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

export default function TeamEngagementPage() {
  const user = useAuthStore((s: any) => s.user);
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [hotLeads, setHotLeads] = useState<any[]>([]);
  const [alertLeads, setAlertLeads] = useState<any[]>([]);
  const [teamStats, setTeamStats] = useState<any[]>([]);
  const [period, setPeriod] = useState(48);
  const [tab, setTab] = useState<'alerts' | 'leads' | 'team'>('alerts');

  // Reassignment
  const [showReassign, setShowReassign] = useState(false);
  const [reassignLead, setReassignLead] = useState<any>(null);
  const [teamUsers, setTeamUsers] = useState<any[]>([]);
  const [loadingUsers, setLoadingUsers] = useState(false);
  const [userSearch, setUserSearch] = useState('');
  const [reassigning, setReassigning] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!user?._id) return;
    setLoading(true);
    try {
      const res = await api.get(`/engagement/team-hot-leads/${user._id}?hours=${period}`);
      setHotLeads(res.data.hot_leads || []);
      setAlertLeads(res.data.alert_leads || []);
      setTeamStats(res.data.team_stats || []);
    } catch (e) {
      console.error('Failed to load team engagement:', e);
    } finally {
      setLoading(false);
    }
  }, [user?._id, period]);

  useEffect(() => { load(); }, [load]);

  // Auto-refresh every 30s
  useEffect(() => {
    const iv = setInterval(load, 30000);
    return () => clearInterval(iv);
  }, [load]);

  const openReassign = async (lead: any) => {
    setReassignLead(lead);
    setShowReassign(true);
    setUserSearch('');
    if (!user?.organization_id) return;
    try {
      setLoadingUsers(true);
      const data = await adminAPI.listOrgUsers(user.organization_id);
      setTeamUsers(Array.isArray(data) ? data : data.users || []);
    } catch (err) {
      console.error('Failed to load users:', err);
    } finally {
      setLoadingUsers(false);
    }
  };

  const handleReassign = async (targetUser: any) => {
    if (!reassignLead) return;
    const msg = `Reassign "${reassignLead.contact_name}" from ${reassignLead.rep_name} to ${targetUser.name}?`;
    if (Platform.OS === 'web') {
      if (!window.confirm(msg)) return;
    }
    try {
      setReassigning(targetUser._id);
      await api.post('/engagement/reassign-lead', {
        contact_id: reassignLead.contact_id,
        new_user_id: targetUser._id,
      }, { headers: { 'X-User-ID': user._id } });
      setShowReassign(false);
      if (Platform.OS === 'web') window.alert(`Lead reassigned to ${targetUser.name}`);
      load(); // refresh data
    } catch (err: any) {
      const detail = err?.response?.data?.detail || 'Failed to reassign lead';
      if (Platform.OS === 'web') window.alert(detail);
    } finally {
      setReassigning(null);
    }
  };

  const filteredUsers = teamUsers.filter(u =>
    !userSearch || u.name?.toLowerCase().includes(userSearch.toLowerCase())
  );

  const totalTeamActivity = teamStats.reduce((s, t) => s + t.total_activity, 0);
  const totalEngagement = teamStats.reduce((s, t) => s + t.engagement_signals, 0);

  const renderLeadCard = (lead: any, idx: number, showAlert?: boolean) => {
    const iconInfo = SIGNAL_ICONS[lead.last_signal] || { icon: 'eye', color: '#007AFF' };
    return (
      <TouchableOpacity
        key={`${lead.contact_id || lead.contact_name}-${lead.user_id}-${idx}`}
        style={[s.leadCard, showAlert && s.alertCard]}
        onPress={() => lead.contact_id ? router.push(`/contact/${lead.contact_id}`) : null}
        data-testid={`team-lead-${idx}`}
      >
        <View style={[s.leadIcon, { backgroundColor: iconInfo.color + '20' }]}>
          <Ionicons name={iconInfo.icon as any} size={20} color={iconInfo.color} />
        </View>
        <View style={s.leadInfo}>
          <View style={s.leadNameRow}>
            <Text style={s.leadName}>{lead.contact_name}</Text>
            {lead.is_return_visit && (
              <View style={s.returnBadge}><Text style={s.returnText}>RETURN</Text></View>
            )}
          </View>
          <Text style={s.leadAction}>{lead.last_signal_label}</Text>
          <View style={s.repRow}>
            <Ionicons name="person" size={11} color="#888" />
            <Text style={s.repName}>{lead.rep_name}</Text>
            <Text style={s.leadTime}>{timeAgo(lead.minutes_ago)}</Text>
          </View>
          {lead.total_signals > 1 && (
            <Text style={s.leadMulti}>{lead.total_signals} interactions</Text>
          )}
        </View>
        <View style={s.leadRight}>
          <View style={[s.heatBadge, { backgroundColor: lead.heat_score >= 6 ? '#FF3B30' : lead.heat_score >= 3 ? '#FF9500' : '#555' }]}>
            <Ionicons name="flame" size={12} color="#FFF" />
            <Text style={s.heatText}>{lead.heat_score.toFixed(0)}</Text>
          </View>
          {lead.can_reassign && (
            <TouchableOpacity
              style={s.reassignBtn}
              onPress={(e) => { e.stopPropagation?.(); openReassign(lead); }}
              data-testid={`reassign-btn-${idx}`}
            >
              <Ionicons name="swap-horizontal" size={14} color="#C9A962" />
            </TouchableOpacity>
          )}
        </View>
      </TouchableOpacity>
    );
  };

  return (
    <SafeAreaView style={s.container} edges={['top']}>
      <ScrollView
        refreshControl={<RefreshControl refreshing={loading} onRefresh={load} tintColor="#C9A962" />}
      >
        {/* Header */}
        <View style={s.header} data-testid="team-engagement-header">
          <TouchableOpacity onPress={() => router.back()} style={s.backBtn} data-testid="back-button">
            <Ionicons name="arrow-back" size={24} color="#FFF" />
          </TouchableOpacity>
          <View style={{ flex: 1 }}>
            <Text style={s.title}>Team Engagement</Text>
            <Text style={s.subtitle}>Your team's hot leads at a glance</Text>
          </View>
          <TouchableOpacity onPress={load} style={s.refreshBtn} data-testid="refresh-btn">
            <Ionicons name="refresh" size={20} color="#C9A962" />
          </TouchableOpacity>
        </View>

        {/* Summary cards */}
        <View style={s.summaryRow} data-testid="summary-cards">
          <View style={[s.summaryCard, { borderColor: '#FF3B3040' }]}>
            <Ionicons name="flame" size={20} color="#FF3B30" />
            <Text style={s.summaryNum}>{hotLeads.length}</Text>
            <Text style={s.summaryLabel}>Hot Leads</Text>
          </View>
          <View style={[s.summaryCard, { borderColor: '#FF950040' }]}>
            <Ionicons name="alert-circle" size={20} color="#FF9500" />
            <Text style={s.summaryNum}>{alertLeads.length}</Text>
            <Text style={s.summaryLabel}>Alerts (3+)</Text>
          </View>
          <View style={[s.summaryCard, { borderColor: '#34C75940' }]}>
            <Ionicons name="pulse" size={20} color="#34C759" />
            <Text style={s.summaryNum}>{totalTeamActivity}</Text>
            <Text style={s.summaryLabel}>Actions</Text>
          </View>
          <View style={[s.summaryCard, { borderColor: '#007AFF40' }]}>
            <Ionicons name="eye" size={20} color="#007AFF" />
            <Text style={s.summaryNum}>{totalEngagement}</Text>
            <Text style={s.summaryLabel}>Signals</Text>
          </View>
        </View>

        {/* Period filter */}
        <View style={s.filterRow} data-testid="period-filter">
          {[24, 48, 168].map(h => (
            <TouchableOpacity
              key={h}
              style={[s.filterChip, period === h && s.filterActive]}
              onPress={() => setPeriod(h)}
              data-testid={`filter-${h}h`}
            >
              <Text style={[s.filterText, period === h && s.filterTextActive]}>
                {h === 24 ? 'Today' : h === 48 ? '48 Hours' : '7 Days'}
              </Text>
            </TouchableOpacity>
          ))}
        </View>

        {/* Tabs */}
        <View style={s.tabRow} data-testid="tab-row">
          {([
            { key: 'alerts', icon: 'alert-circle', label: 'Alerts', count: alertLeads.length, color: '#FF9500' },
            { key: 'leads', icon: 'flame', label: 'Hot Leads', count: hotLeads.length, color: '#FF3B30' },
            { key: 'team', icon: 'people', label: 'Team', count: teamStats.length, color: '#007AFF' },
          ] as const).map(t => (
            <TouchableOpacity
              key={t.key}
              style={[s.tab, tab === t.key && s.tabActive]}
              onPress={() => setTab(t.key)}
              data-testid={`tab-${t.key}`}
            >
              <Ionicons name={t.icon as any} size={15} color={tab === t.key ? t.color : '#666'} />
              <Text style={[s.tabText, tab === t.key && s.tabTextActive]}>{t.label}</Text>
              {t.count > 0 && (
                <View style={[s.tabBadge, { backgroundColor: t.color }]}>
                  <Text style={s.tabBadgeText}>{t.count}</Text>
                </View>
              )}
            </TouchableOpacity>
          ))}
        </View>

        {/* Content */}
        <View style={s.section}>
          {tab === 'alerts' && (
            alertLeads.length === 0 ? (
              <View style={s.emptyState} data-testid="empty-alerts">
                <Ionicons name="checkmark-circle-outline" size={48} color="#34C759" />
                <Text style={s.emptyTitle}>All clear</Text>
                <Text style={s.emptyText}>No contacts with 3+ interactions right now. Check back soon.</Text>
              </View>
            ) : (
              <>
                <Text style={s.sectionHint}>Contacts with 3+ interactions — high purchase intent</Text>
                {alertLeads.map((lead, i) => renderLeadCard(lead, i, true))}
              </>
            )
          )}

          {tab === 'leads' && (
            hotLeads.length === 0 ? (
              <View style={s.emptyState} data-testid="empty-leads">
                <Ionicons name="flame-outline" size={48} color="#555" />
                <Text style={s.emptyTitle}>No hot leads</Text>
                <Text style={s.emptyText}>When your team's customers engage, they'll appear here.</Text>
              </View>
            ) : (
              hotLeads.map((lead, i) => renderLeadCard(lead, i))
            )
          )}

          {tab === 'team' && (
            teamStats.length === 0 ? (
              <View style={s.emptyState} data-testid="empty-team">
                <Ionicons name="people-outline" size={48} color="#555" />
                <Text style={s.emptyTitle}>No team data</Text>
              </View>
            ) : (
              teamStats.map((rep, i) => (
                <View key={rep.user_id} style={s.repCard} data-testid={`rep-card-${i}`}>
                  <View style={s.repAvatar}>
                    <Text style={s.repInitial}>{(rep.name || '?')[0].toUpperCase()}</Text>
                  </View>
                  <View style={{ flex: 1 }}>
                    <Text style={s.repCardName}>{rep.name}</Text>
                    <View style={s.statsRow}>
                      <View style={s.stat}>
                        <Ionicons name="call" size={12} color="#34C759" />
                        <Text style={s.statNum}>{rep.calls}</Text>
                      </View>
                      <View style={s.stat}>
                        <Ionicons name="chatbubble" size={12} color="#007AFF" />
                        <Text style={s.statNum}>{rep.texts}</Text>
                      </View>
                      <View style={s.stat}>
                        <Ionicons name="mail" size={12} color="#AF52DE" />
                        <Text style={s.statNum}>{rep.emails}</Text>
                      </View>
                      <View style={s.stat}>
                        <Ionicons name="card" size={12} color="#C9A962" />
                        <Text style={s.statNum}>{rep.cards}</Text>
                      </View>
                    </View>
                  </View>
                  <View style={s.repRight}>
                    <Text style={s.repTotal}>{rep.total_activity}</Text>
                    <Text style={s.repTotalLabel}>actions</Text>
                    {rep.engagement_signals > 0 && (
                      <View style={s.signalBubble}>
                        <Ionicons name="eye" size={10} color="#007AFF" />
                        <Text style={s.signalBubbleText}>{rep.engagement_signals}</Text>
                      </View>
                    )}
                  </View>
                </View>
              ))
            )
          )}
        </View>

        <View style={{ height: 80 }} />
      </ScrollView>

      {/* Reassign Modal */}
      <WebModal visible={showReassign} animationType="slide" presentationStyle="pageSheet">
        <SafeAreaView style={s.modal}>
          <View style={s.modalHeader}>
            <TouchableOpacity onPress={() => setShowReassign(false)} data-testid="reassign-close-btn">
              <Ionicons name="close" size={24} color="#FFF" />
            </TouchableOpacity>
            <Text style={s.modalTitle}>Reassign Lead</Text>
            <View style={{ width: 24 }} />
          </View>
          {reassignLead && (
            <View style={s.reassignBanner}>
              <Ionicons name="swap-horizontal" size={18} color="#C9A962" />
              <Text style={s.reassignBannerText}>
                {reassignLead.contact_name} (currently: {reassignLead.rep_name})
              </Text>
            </View>
          )}
          <View style={s.searchRow}>
            <Ionicons name="search" size={18} color="#888" />
            <TextInput
              style={s.searchInput}
              value={userSearch}
              onChangeText={setUserSearch}
              placeholder="Search team members..."
              placeholderTextColor="#666"
              data-testid="reassign-search-input"
            />
          </View>
          {loadingUsers ? (
            <View style={s.centerLoader}><ActivityIndicator size="large" color="#C9A962" /></View>
          ) : (
            <ScrollView style={s.modalBody}>
              {filteredUsers.filter(u => u._id !== reassignLead?.user_id).map(u => (
                <TouchableOpacity
                  key={u._id}
                  style={s.userRow}
                  onPress={() => handleReassign(u)}
                  disabled={reassigning === u._id}
                  data-testid={`reassign-to-${u._id}`}
                >
                  <View style={s.userAvatar}>
                    <Text style={s.userInitial}>{(u.name || '?')[0].toUpperCase()}</Text>
                  </View>
                  <View style={{ flex: 1 }}>
                    <Text style={s.userName}>{u.name}</Text>
                    <Text style={s.userEmail}>{u.email}</Text>
                  </View>
                  {reassigning === u._id ? (
                    <ActivityIndicator size="small" color="#C9A962" />
                  ) : (
                    <Ionicons name="arrow-forward-circle" size={24} color="#C9A962" />
                  )}
                </TouchableOpacity>
              ))}
              <View style={{ height: 40 }} />
            </ScrollView>
          )}
        </SafeAreaView>
      </WebModal>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0A0A0A' },
  centerLoader: { flex: 1, justifyContent: 'center', alignItems: 'center', paddingTop: 60 },
  header: { flexDirection: 'row', alignItems: 'center', padding: 20, gap: 12 },
  backBtn: { width: 40, height: 40, borderRadius: 12, backgroundColor: '#1C1C1E', alignItems: 'center', justifyContent: 'center' },
  refreshBtn: { width: 40, height: 40, borderRadius: 12, backgroundColor: '#1C1C1E', alignItems: 'center', justifyContent: 'center' },
  title: { color: '#FFF', fontSize: 22, fontWeight: '700' },
  subtitle: { color: '#888', fontSize: 15, marginTop: 2 },

  summaryRow: { flexDirection: 'row', paddingHorizontal: 16, marginBottom: 12, gap: 8 },
  summaryCard: {
    flex: 1, backgroundColor: '#1C1C1E', borderRadius: 12, padding: 12,
    alignItems: 'center', gap: 4, borderWidth: 1,
  },
  summaryNum: { color: '#FFF', fontSize: 21, fontWeight: '700' },
  summaryLabel: { color: '#888', fontSize: 12, fontWeight: '600', textTransform: 'uppercase', letterSpacing: 0.3 },

  filterRow: { flexDirection: 'row', marginHorizontal: 20, marginBottom: 12, gap: 8 },
  filterChip: { paddingHorizontal: 14, paddingVertical: 6, borderRadius: 20, backgroundColor: '#1C1C1E' },
  filterActive: { backgroundColor: '#C9A962' },
  filterText: { color: '#888', fontSize: 15, fontWeight: '500' },
  filterTextActive: { color: '#000' },

  tabRow: { flexDirection: 'row', marginHorizontal: 20, marginBottom: 16, backgroundColor: '#1C1C1E', borderRadius: 12, padding: 4 },
  tab: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 5, paddingVertical: 10, borderRadius: 10 },
  tabActive: { backgroundColor: '#2C2C2E' },
  tabText: { color: '#666', fontSize: 15, fontWeight: '600' },
  tabTextActive: { color: '#FFF' },
  tabBadge: { borderRadius: 8, paddingHorizontal: 5, paddingVertical: 1, marginLeft: 3 },
  tabBadgeText: { color: '#FFF', fontSize: 12, fontWeight: '700' },

  section: { paddingHorizontal: 20 },
  sectionHint: { color: '#FF9500', fontSize: 14, fontWeight: '500', marginBottom: 10, fontStyle: 'italic' },

  leadCard: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#1C1C1E', borderRadius: 14, padding: 14, marginBottom: 10, gap: 12 },
  alertCard: { borderWidth: 1, borderColor: '#FF950040' },
  leadIcon: { width: 44, height: 44, borderRadius: 12, alignItems: 'center', justifyContent: 'center' },
  leadInfo: { flex: 1 },
  leadNameRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  leadName: { color: '#FFF', fontSize: 17, fontWeight: '600' },
  returnBadge: { backgroundColor: '#FF950020', paddingHorizontal: 6, paddingVertical: 2, borderRadius: 4 },
  returnText: { color: '#FF9500', fontSize: 9, fontWeight: '700', letterSpacing: 0.5 },
  leadAction: { color: '#AAA', fontSize: 15, marginTop: 2 },
  repRow: { flexDirection: 'row', alignItems: 'center', gap: 4, marginTop: 3 },
  repName: { color: '#C9A962', fontSize: 13, fontWeight: '500' },
  leadTime: { color: '#555', fontSize: 13, marginLeft: 4 },
  leadMulti: { color: '#C9A962', fontSize: 13, marginTop: 2, fontWeight: '500' },
  leadRight: { alignItems: 'center', gap: 6 },
  heatBadge: { flexDirection: 'row', alignItems: 'center', gap: 3, paddingHorizontal: 8, paddingVertical: 3, borderRadius: 10 },
  heatText: { color: '#FFF', fontSize: 13, fontWeight: '700' },
  reassignBtn: {
    width: 30, height: 30, borderRadius: 8, backgroundColor: '#C9A96218',
    alignItems: 'center', justifyContent: 'center',
  },

  // Rep cards
  repCard: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#1C1C1E', borderRadius: 14, padding: 14, marginBottom: 10, gap: 12 },
  repAvatar: { width: 42, height: 42, borderRadius: 11, backgroundColor: '#2C2C2E', alignItems: 'center', justifyContent: 'center' },
  repInitial: { color: '#FFF', fontSize: 19, fontWeight: '700' },
  repCardName: { color: '#FFF', fontSize: 17, fontWeight: '600', marginBottom: 4 },
  statsRow: { flexDirection: 'row', gap: 12 },
  stat: { flexDirection: 'row', alignItems: 'center', gap: 3 },
  statNum: { color: '#AAA', fontSize: 14, fontWeight: '600' },
  repRight: { alignItems: 'center' },
  repTotal: { color: '#FFF', fontSize: 19, fontWeight: '700' },
  repTotalLabel: { color: '#666', fontSize: 12, textTransform: 'uppercase' },
  signalBubble: { flexDirection: 'row', alignItems: 'center', gap: 3, backgroundColor: '#007AFF18', paddingHorizontal: 6, paddingVertical: 2, borderRadius: 8, marginTop: 4 },
  signalBubbleText: { color: '#007AFF', fontSize: 12, fontWeight: '700' },

  emptyState: { alignItems: 'center', paddingVertical: 60 },
  emptyTitle: { color: '#FFF', fontSize: 19, fontWeight: '600', marginTop: 16 },
  emptyText: { color: '#666', fontSize: 16, textAlign: 'center', marginTop: 8, paddingHorizontal: 40, lineHeight: 20 },

  // Modal
  modal: { flex: 1, backgroundColor: '#0A0A0A' },
  modalHeader: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: 16, paddingVertical: 12,
    borderBottomWidth: 1, borderBottomColor: '#1C1C1E',
  },
  modalTitle: { fontSize: 18, fontWeight: '600', color: '#FFF' },
  modalBody: { flex: 1, padding: 16 },
  reassignBanner: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    paddingHorizontal: 16, paddingVertical: 10, marginHorizontal: 16, marginTop: 8,
    borderRadius: 10, backgroundColor: '#C9A96218',
  },
  reassignBannerText: { color: '#C9A962', fontSize: 16, fontWeight: '500', flex: 1 },
  searchRow: {
    flexDirection: 'row', alignItems: 'center', backgroundColor: '#1C1C1E',
    borderRadius: 10, marginHorizontal: 16, marginVertical: 12, paddingHorizontal: 12, paddingVertical: 8, gap: 8,
  },
  searchInput: { flex: 1, fontSize: 17, color: '#FFF', padding: 4 },
  userRow: {
    flexDirection: 'row', alignItems: 'center', backgroundColor: '#1C1C1E',
    borderRadius: 12, padding: 14, marginBottom: 8, gap: 12,
  },
  userAvatar: { width: 40, height: 40, borderRadius: 10, backgroundColor: '#2C2C2E', alignItems: 'center', justifyContent: 'center' },
  userInitial: { color: '#FFF', fontSize: 18, fontWeight: '700' },
  userName: { fontSize: 17, fontWeight: '600', color: '#FFF' },
  userEmail: { fontSize: 14, color: '#888', marginTop: 2 },
});
