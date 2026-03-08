import React, { useState, useEffect, useCallback } from 'react';
import { View, Text, TouchableOpacity, ScrollView, RefreshControl, StyleSheet, ActivityIndicator } from 'react-native';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import api from '../services/api';
import { useAuthStore } from '../store/authStore';

interface Suggestion {
  message: string;
  approach: string;
  best_time_reason: string;
}

interface OutreachRecord {
  _id: string;
  contact_id: string;
  contact_name: string;
  suggestions: Suggestion[];
  status: string;
  accepted_index?: number | null;
  scheduled_for: string;
  created_at: string;
}

interface PendingSend {
  _id: string;
  contact_id: string;
  contact_name: string;
  campaign_name: string;
  step: number;
  channel: string;
  message: string;
  relationship_brief?: string;
  ai_generated?: boolean;
  step_context?: string;
  status: string;
}

interface RelBrief {
  relationship_health: string;
  engagement_score: number;
  response_pattern: string;
  last_interaction_days: number | null;
  milestones: string[];
  human_summary: string;
  days_since_sale?: number | null;
}

function formatTime(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
  } catch {
    return '';
  }
}

const healthColors: Record<string, string> = {
  strong: '#34C759',
  warm: '#FF9500',
  cooling: '#FF6B35',
  cold: '#8E8E93',
  unknown: '#555',
};

function HealthBadge({ health }: { health: string }) {
  const color = healthColors[health] || '#555';
  return (
    <View style={[styles.healthBadge, { borderColor: color }]}>
      <View style={[styles.healthDot, { backgroundColor: color }]} />
      <Text style={[styles.healthText, { color }]}>{health.toUpperCase()}</Text>
    </View>
  );
}

function RelBriefCard({ brief, contactId }: { brief: RelBrief; contactId: string }) {
  return (
    <View style={styles.briefCard} data-testid={`rel-brief-${contactId}`}>
      <View style={styles.briefHeader}>
        <Ionicons name="analytics" size={14} color="#C9A962" />
        <Text style={styles.briefTitle}>Relationship Intelligence</Text>
        <HealthBadge health={brief.relationship_health} />
      </View>
      <View style={styles.briefMetrics}>
        <View style={styles.briefMetric}>
          <Text style={styles.briefMetricValue}>{brief.engagement_score}</Text>
          <Text style={styles.briefMetricLabel}>Engagement</Text>
        </View>
        <View style={styles.briefMetric}>
          <Text style={styles.briefMetricValue}>
            {brief.last_interaction_days !== null ? (brief.last_interaction_days === 0 ? 'Today' : `${brief.last_interaction_days}d`) : '--'}
          </Text>
          <Text style={styles.briefMetricLabel}>Last Contact</Text>
        </View>
        <View style={styles.briefMetric}>
          <Text style={styles.briefMetricValue}>{brief.response_pattern.replace('_', ' ').split(' ')[0]}</Text>
          <Text style={styles.briefMetricLabel}>Response</Text>
        </View>
        {brief.days_since_sale != null && (
          <View style={styles.briefMetric}>
            <Text style={styles.briefMetricValue}>{brief.days_since_sale}d</Text>
            <Text style={styles.briefMetricLabel}>Since Sale</Text>
          </View>
        )}
      </View>
      {brief.milestones.length > 0 && (
        <Text style={styles.briefMilestone}>{brief.milestones[brief.milestones.length - 1]}</Text>
      )}
    </View>
  );
}

export default function AIOutreachPage() {
  const user = useAuthStore((s: any) => s.user);
  const router = useRouter();
  const [records, setRecords] = useState<OutreachRecord[]>([]);
  const [pendingSends, setPendingSends] = useState<PendingSend[]>([]);
  const [loading, setLoading] = useState(true);
  const [accepting, setAccepting] = useState<string | null>(null);
  const [tab, setTab] = useState<'campaign' | 'pending' | 'accepted' | 'dismissed'>('campaign');
  const [stats, setStats] = useState({ pending: 0, accepted: 0, dismissed: 0, total: 0 });
  const [briefs, setBriefs] = useState<Record<string, RelBrief>>({});
  const [loadingBrief, setLoadingBrief] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!user?._id) return;
    setLoading(true);
    try {
      const statusFilter = tab === 'campaign' ? 'pending' : tab;
      const calls: Promise<any>[] = [
        api.get(`/ai-outreach/suggestions/${user._id}?status=${statusFilter}`),
        api.get(`/ai-outreach/stats/${user._id}`),
      ];
      if (tab === 'campaign') {
        calls.push(api.get(`/campaigns/${user._id}/pending-sends`));
      }
      const results = await Promise.all(calls);
      setRecords(results[0].data.suggestions || []);
      setStats(results[1].data);
      if (tab === 'campaign' && results[2]) {
        setPendingSends(results[2].data || []);
      }
    } catch (e) {
      console.error('Failed to load AI outreach:', e);
    } finally {
      setLoading(false);
    }
  }, [user?._id, tab]);

  useEffect(() => { load(); }, [load]);

  const loadBrief = async (contactId: string) => {
    if (briefs[contactId] || !user?._id) return;
    setLoadingBrief(contactId);
    try {
      const res = await api.get(`/ai-outreach/relationship-brief/${user._id}/${contactId}`);
      setBriefs((prev) => ({ ...prev, [contactId]: res.data }));
    } catch (e) {
      console.error('Brief failed:', e);
    } finally {
      setLoadingBrief(null);
    }
  };

  const handleAccept = async (recordId: string, index: number) => {
    setAccepting(`${recordId}-${index}`);
    try {
      await api.post(`/ai-outreach/suggestions/${recordId}/accept`, { suggestion_index: index });
      load();
    } catch (e) {
      console.error('Failed to accept:', e);
    } finally {
      setAccepting(null);
    }
  };

  const handleDismiss = async (recordId: string) => {
    try {
      await api.post(`/ai-outreach/suggestions/${recordId}/dismiss`);
      load();
    } catch (e) {
      console.error('Failed to dismiss:', e);
    }
  };

  const handleCompleteSend = async (sendId: string) => {
    try {
      await api.post(`/campaigns/${user._id}/pending-sends/${sendId}/complete`);
      load();
    } catch (e) {
      console.error('Complete failed:', e);
    }
  };

  const tabs = [
    { key: 'campaign' as const, label: 'Campaign', count: pendingSends.length },
    { key: 'pending' as const, label: 'AI Suggestions', count: stats.pending },
    { key: 'accepted' as const, label: 'Accepted', count: stats.accepted },
    { key: 'dismissed' as const, label: 'Dismissed', count: stats.dismissed },
  ];

  return (
    <ScrollView style={styles.container} refreshControl={<RefreshControl refreshing={loading} onRefresh={load} tintColor="#C9A962" />}>
      {/* Header */}
      <View style={styles.header} data-testid="ai-outreach-header">
        <TouchableOpacity onPress={() => router.back()} style={styles.backBtn} data-testid="ai-outreach-back-btn">
          <Ionicons name="arrow-back" size={24} color="#FFF" />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={styles.title}>AI Outreach</Text>
          <Text style={styles.subtitle}>Relationship-powered follow-ups</Text>
        </View>
        <View style={styles.statsBadge} data-testid="ai-outreach-pending-badge">
          <Ionicons name="sparkles" size={16} color="#AF52DE" />
          <Text style={styles.statsText}>{stats.pending + pendingSends.length} active</Text>
        </View>
      </View>

      {/* How it works */}
      <View style={styles.infoCard} data-testid="ai-outreach-info-card">
        <Ionicons name="flash" size={18} color="#C9A962" />
        <Text style={styles.infoText}>
          Every message is crafted using real relationship data — engagement signals, conversation history, and milestone context. Tag a customer "Sold" and the AI builds a personalized follow-up journey.
        </Text>
      </View>

      {/* Tabs */}
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.tabScroll}>
        <View style={styles.tabRow} data-testid="ai-outreach-tabs">
          {tabs.map((t) => (
            <TouchableOpacity
              key={t.key}
              style={[styles.tab, tab === t.key && styles.tabActive]}
              onPress={() => setTab(t.key)}
              data-testid={`ai-outreach-tab-${t.key}`}
            >
              <Text style={[styles.tabText, tab === t.key && styles.tabTextActive]}>
                {t.label} ({t.count})
              </Text>
            </TouchableOpacity>
          ))}
        </View>
      </ScrollView>

      {/* Content */}
      {loading ? (
        <ActivityIndicator size="large" color="#C9A962" style={{ marginTop: 40 }} />
      ) : tab === 'campaign' ? (
        /* CAMPAIGN PENDING SENDS — The Magic View */
        pendingSends.length === 0 ? (
          <View style={styles.emptyState} data-testid="ai-outreach-empty">
            <Ionicons name="rocket" size={48} color="#555" />
            <Text style={styles.emptyTitle}>No campaign messages pending</Text>
            <Text style={styles.emptySubtitle}>When you tag a contact as "Sold", they'll automatically enter a personalized follow-up journey.</Text>
          </View>
        ) : (
          pendingSends.map((ps) => (
            <View key={ps._id} style={styles.card} data-testid={`campaign-send-${ps._id}`}>
              <View style={styles.cardHeader}>
                <View style={styles.contactRow}>
                  <View style={[styles.avatar, { backgroundColor: '#34C759' }]}>
                    <Ionicons name="person" size={18} color="#FFF" />
                  </View>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.contactName}>{ps.contact_name}</Text>
                    <Text style={styles.cardTime}>
                      {ps.campaign_name} — Step {ps.step}
                    </Text>
                  </View>
                  {ps.ai_generated && (
                    <View style={styles.aiBadge}>
                      <Ionicons name="sparkles" size={12} color="#AF52DE" />
                      <Text style={styles.aiBadgeText}>AI</Text>
                    </View>
                  )}
                  <View style={[styles.channelBadge, { backgroundColor: ps.channel === 'email' ? 'rgba(0,122,255,0.12)' : 'rgba(52,199,89,0.12)' }]}>
                    <Ionicons name={ps.channel === 'email' ? 'mail' : 'chatbubble'} size={12} color={ps.channel === 'email' ? '#007AFF' : '#34C759'} />
                    <Text style={{ color: ps.channel === 'email' ? '#007AFF' : '#34C759', fontSize: 10, fontWeight: '600' }}>{ps.channel.toUpperCase()}</Text>
                  </View>
                </View>
              </View>

              {/* Relationship Brief */}
              {briefs[ps.contact_id] ? (
                <RelBriefCard brief={briefs[ps.contact_id]} contactId={ps.contact_id} />
              ) : ps.relationship_brief ? (
                <View style={styles.inlineBrief}>
                  <Ionicons name="analytics" size={12} color="#C9A962" />
                  <Text style={styles.inlineBriefText}>{ps.relationship_brief}</Text>
                  <TouchableOpacity onPress={() => loadBrief(ps.contact_id)} data-testid={`load-brief-${ps.contact_id}`}>
                    <Text style={styles.expandLink}>Details</Text>
                  </TouchableOpacity>
                </View>
              ) : (
                <TouchableOpacity style={styles.inlineBrief} onPress={() => loadBrief(ps.contact_id)} data-testid={`load-brief-${ps.contact_id}`}>
                  <Ionicons name="analytics-outline" size={12} color="#666" />
                  <Text style={styles.inlineBriefText}>Tap to load relationship intelligence</Text>
                  {loadingBrief === ps.contact_id && <ActivityIndicator size="small" color="#C9A962" />}
                </TouchableOpacity>
              )}

              {/* Step Context */}
              {ps.step_context && (
                <View style={styles.contextRow}>
                  <Ionicons name="bulb" size={12} color="#FF9500" />
                  <Text style={styles.contextText}>{ps.step_context}</Text>
                </View>
              )}

              {/* Message */}
              <View style={styles.messageBox}>
                <Text style={styles.messageLabel}>Message to send:</Text>
                <Text style={styles.messageContent}>"{ps.message}"</Text>
              </View>

              {/* Actions */}
              <View style={styles.actionRow}>
                <TouchableOpacity
                  style={styles.sendBtn}
                  onPress={() => handleCompleteSend(ps._id)}
                  data-testid={`complete-send-${ps._id}`}
                >
                  <Ionicons name="send" size={14} color="#000" />
                  <Text style={styles.sendBtnText}>Mark as Sent</Text>
                </TouchableOpacity>
                <TouchableOpacity
                  style={styles.copyBtn}
                  onPress={() => {
                    if (typeof navigator !== 'undefined' && navigator.clipboard) {
                      navigator.clipboard.writeText(ps.message);
                    }
                  }}
                  data-testid={`copy-msg-${ps._id}`}
                >
                  <Ionicons name="copy" size={14} color="#C9A962" />
                  <Text style={styles.copyBtnText}>Copy</Text>
                </TouchableOpacity>
              </View>
            </View>
          ))
        )
      ) : records.length === 0 ? (
        <View style={styles.emptyState} data-testid="ai-outreach-empty">
          <Ionicons name={tab === 'pending' ? 'sparkles' : tab === 'accepted' ? 'checkmark-circle' : 'close-circle'} size={48} color="#555" />
          <Text style={styles.emptyTitle}>
            {tab === 'pending' ? 'No pending suggestions' : tab === 'accepted' ? 'No accepted suggestions yet' : 'Nothing dismissed'}
          </Text>
          <Text style={styles.emptySubtitle}>
            {tab === 'pending' ? 'Tag a customer as "Sold" to generate AI follow-ups!' : 'Your history will appear here.'}
          </Text>
        </View>
      ) : (
        /* AI SUGGESTIONS VIEW */
        records.map((record) => (
          <View key={record._id} style={styles.card} data-testid={`ai-outreach-card-${record._id}`}>
            <View style={styles.cardHeader}>
              <View style={styles.contactRow}>
                <View style={styles.avatar}>
                  <Ionicons name="person" size={18} color="#FFF" />
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={styles.contactName}>{record.contact_name}</Text>
                  <Text style={styles.cardTime}>
                    {record.status === 'pending' ? `Scheduled for ${formatTime(record.scheduled_for)}` : `Created ${formatTime(record.created_at)}`}
                  </Text>
                </View>
                {record.status === 'accepted' && (
                  <View style={[styles.statusBadge, { backgroundColor: 'rgba(52,199,89,0.15)' }]}>
                    <Ionicons name="checkmark-circle" size={14} color="#34C759" />
                    <Text style={[styles.statusText, { color: '#34C759' }]}>Accepted</Text>
                  </View>
                )}
                {record.status === 'dismissed' && (
                  <View style={[styles.statusBadge, { backgroundColor: 'rgba(142,142,147,0.15)' }]}>
                    <Ionicons name="close-circle" size={14} color="#8E8E93" />
                    <Text style={[styles.statusText, { color: '#8E8E93' }]}>Dismissed</Text>
                  </View>
                )}
              </View>
            </View>

            {/* Inline relationship brief */}
            {briefs[record.contact_id] ? (
              <RelBriefCard brief={briefs[record.contact_id]} contactId={record.contact_id} />
            ) : (
              <TouchableOpacity style={styles.inlineBrief} onPress={() => loadBrief(record.contact_id)} data-testid={`load-brief-${record.contact_id}`}>
                <Ionicons name="analytics-outline" size={12} color="#666" />
                <Text style={styles.inlineBriefText}>Tap to view relationship intelligence</Text>
                {loadingBrief === record.contact_id && <ActivityIndicator size="small" color="#C9A962" />}
              </TouchableOpacity>
            )}

            {record.suggestions.map((sug, i) => (
              <View
                key={i}
                style={[styles.suggestionCard, record.status === 'accepted' && record.accepted_index === i && styles.suggestionChosen]}
                data-testid={`suggestion-${record._id}-${i}`}
              >
                <View style={styles.suggestionHeader}>
                  <View style={styles.approachBadge}>
                    <Ionicons name="bulb" size={12} color="#C9A962" />
                    <Text style={styles.approachText}>{sug.approach}</Text>
                  </View>
                  {record.status === 'accepted' && record.accepted_index === i && (
                    <Ionicons name="checkmark-circle" size={16} color="#34C759" />
                  )}
                </View>
                <Text style={styles.msgText}>"{sug.message}"</Text>
                <Text style={styles.reasonText}>{sug.best_time_reason}</Text>
                {record.status === 'pending' && (
                  <TouchableOpacity
                    style={styles.acceptBtn}
                    onPress={() => handleAccept(record._id, i)}
                    disabled={accepting !== null}
                    data-testid={`accept-btn-${record._id}-${i}`}
                  >
                    {accepting === `${record._id}-${i}` ? (
                      <ActivityIndicator size="small" color="#000" />
                    ) : (
                      <>
                        <Ionicons name="checkmark" size={16} color="#000" />
                        <Text style={styles.acceptBtnText}>Use This Message</Text>
                      </>
                    )}
                  </TouchableOpacity>
                )}
              </View>
            ))}
            {record.status === 'pending' && (
              <TouchableOpacity style={styles.dismissBtn} onPress={() => handleDismiss(record._id)} data-testid={`dismiss-btn-${record._id}`}>
                <Text style={styles.dismissText}>Dismiss</Text>
              </TouchableOpacity>
            )}
          </View>
        ))
      )}
      <View style={{ height: 100 }} />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#000' },
  header: { flexDirection: 'row', alignItems: 'center', padding: 20, paddingTop: 60, gap: 12 },
  backBtn: { width: 40, height: 40, borderRadius: 20, backgroundColor: 'rgba(255,255,255,0.1)', justifyContent: 'center', alignItems: 'center' },
  title: { color: '#FFF', fontSize: 22, fontWeight: '700' },
  subtitle: { color: '#8E8E93', fontSize: 13, marginTop: 2 },
  statsBadge: { flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: 'rgba(175,82,222,0.15)', paddingHorizontal: 10, paddingVertical: 6, borderRadius: 12 },
  statsText: { color: '#AF52DE', fontSize: 12, fontWeight: '600' },
  infoCard: { flexDirection: 'row', alignItems: 'flex-start', gap: 10, marginHorizontal: 16, marginBottom: 16, padding: 14, backgroundColor: 'rgba(201,169,98,0.08)', borderRadius: 12, borderWidth: 1, borderColor: 'rgba(201,169,98,0.2)' },
  infoText: { color: '#AAA', fontSize: 13, lineHeight: 18, flex: 1 },
  tabScroll: { marginBottom: 16, paddingHorizontal: 16 },
  tabRow: { flexDirection: 'row', backgroundColor: '#1A1A1A', borderRadius: 10, padding: 3, gap: 2 },
  tab: { paddingVertical: 8, paddingHorizontal: 14, borderRadius: 8 },
  tabActive: { backgroundColor: '#333' },
  tabText: { color: '#8E8E93', fontSize: 12, fontWeight: '600' },
  tabTextActive: { color: '#FFF' },
  emptyState: { alignItems: 'center', paddingVertical: 60, gap: 12 },
  emptyTitle: { color: '#888', fontSize: 16, fontWeight: '600' },
  emptySubtitle: { color: '#555', fontSize: 13, textAlign: 'center', paddingHorizontal: 40 },
  card: { marginHorizontal: 16, marginBottom: 16, backgroundColor: '#111', borderRadius: 14, borderWidth: 1, borderColor: '#222', overflow: 'hidden' },
  cardHeader: { padding: 16, borderBottomWidth: 1, borderBottomColor: '#1A1A1A' },
  contactRow: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  avatar: { width: 36, height: 36, borderRadius: 10, backgroundColor: '#AF52DE', justifyContent: 'center', alignItems: 'center' },
  contactName: { color: '#FFF', fontSize: 15, fontWeight: '600' },
  cardTime: { color: '#8E8E93', fontSize: 12, marginTop: 2 },
  aiBadge: { flexDirection: 'row', alignItems: 'center', gap: 3, backgroundColor: 'rgba(175,82,222,0.15)', paddingHorizontal: 7, paddingVertical: 3, borderRadius: 6 },
  aiBadgeText: { color: '#AF52DE', fontSize: 10, fontWeight: '700' },
  channelBadge: { flexDirection: 'row', alignItems: 'center', gap: 3, paddingHorizontal: 7, paddingVertical: 3, borderRadius: 6 },
  statusBadge: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 8, paddingVertical: 4, borderRadius: 8 },
  statusText: { fontSize: 11, fontWeight: '600' },
  // Relationship Brief
  briefCard: { margin: 12, marginBottom: 4, padding: 12, backgroundColor: '#0D0D0D', borderRadius: 10, borderWidth: 1, borderColor: 'rgba(201,169,98,0.15)' },
  briefHeader: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 10 },
  briefTitle: { color: '#C9A962', fontSize: 11, fontWeight: '700', flex: 1, textTransform: 'uppercase', letterSpacing: 0.5 },
  briefMetrics: { flexDirection: 'row', gap: 16, marginBottom: 6 },
  briefMetric: { alignItems: 'center' },
  briefMetricValue: { color: '#FFF', fontSize: 15, fontWeight: '700' },
  briefMetricLabel: { color: '#666', fontSize: 9, marginTop: 2, textTransform: 'uppercase' },
  briefMilestone: { color: '#8E8E93', fontSize: 11, marginTop: 4, fontStyle: 'italic' },
  healthBadge: { flexDirection: 'row', alignItems: 'center', gap: 4, borderWidth: 1, paddingHorizontal: 6, paddingVertical: 2, borderRadius: 6 },
  healthDot: { width: 6, height: 6, borderRadius: 3 },
  healthText: { fontSize: 9, fontWeight: '700', letterSpacing: 0.5 },
  // Inline Brief
  inlineBrief: { flexDirection: 'row', alignItems: 'center', gap: 6, marginHorizontal: 12, marginTop: 8, marginBottom: 4, padding: 8, backgroundColor: '#0D0D0D', borderRadius: 8 },
  inlineBriefText: { color: '#666', fontSize: 11, flex: 1 },
  expandLink: { color: '#C9A962', fontSize: 11, fontWeight: '600' },
  // Context
  contextRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 6, marginHorizontal: 12, marginTop: 8, padding: 8, backgroundColor: 'rgba(255,149,0,0.06)', borderRadius: 8 },
  contextText: { color: '#999', fontSize: 11, lineHeight: 15, flex: 1 },
  // Message
  messageBox: { margin: 12, padding: 12, backgroundColor: '#1A1A1A', borderRadius: 10, borderWidth: 1, borderColor: '#2A2A2A' },
  messageLabel: { color: '#666', fontSize: 10, marginBottom: 6, textTransform: 'uppercase', letterSpacing: 0.5 },
  messageContent: { color: '#E0E0E0', fontSize: 14, lineHeight: 20, fontStyle: 'italic' },
  // Actions
  actionRow: { flexDirection: 'row', gap: 8, margin: 12, marginTop: 4 },
  sendBtn: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingVertical: 10, backgroundColor: '#C9A962', borderRadius: 8 },
  sendBtnText: { color: '#000', fontSize: 13, fontWeight: '700' },
  copyBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 4, paddingVertical: 10, paddingHorizontal: 16, backgroundColor: 'rgba(201,169,98,0.1)', borderRadius: 8, borderWidth: 1, borderColor: 'rgba(201,169,98,0.3)' },
  copyBtnText: { color: '#C9A962', fontSize: 13, fontWeight: '600' },
  // Suggestions
  suggestionCard: { margin: 12, marginBottom: 4, padding: 14, backgroundColor: '#1A1A1A', borderRadius: 10, borderWidth: 1, borderColor: '#2A2A2A' },
  suggestionChosen: { borderColor: 'rgba(52,199,89,0.4)', backgroundColor: 'rgba(52,199,89,0.05)' },
  suggestionHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 },
  approachBadge: { flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: 'rgba(201,169,98,0.12)', paddingHorizontal: 8, paddingVertical: 3, borderRadius: 6 },
  approachText: { color: '#C9A962', fontSize: 11, fontWeight: '600' },
  msgText: { color: '#E0E0E0', fontSize: 14, lineHeight: 20, fontStyle: 'italic', marginBottom: 6 },
  reasonText: { color: '#666', fontSize: 11, lineHeight: 15 },
  acceptBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, marginTop: 10, paddingVertical: 10, backgroundColor: '#C9A962', borderRadius: 8 },
  acceptBtnText: { color: '#000', fontSize: 13, fontWeight: '700' },
  dismissBtn: { alignItems: 'center', paddingVertical: 12, borderTopWidth: 1, borderTopColor: '#1A1A1A' },
  dismissText: { color: '#8E8E93', fontSize: 13 },
});
