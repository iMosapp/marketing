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

function formatTime(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
  } catch {
    return '';
  }
}

export default function AIOutreachPage() {
  const user = useAuthStore((s: any) => s.user);
  const router = useRouter();
  const [records, setRecords] = useState<OutreachRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [accepting, setAccepting] = useState<string | null>(null);
  const [tab, setTab] = useState<'pending' | 'accepted' | 'dismissed'>('pending');
  const [stats, setStats] = useState({ pending: 0, accepted: 0, dismissed: 0, total: 0 });

  const load = useCallback(async () => {
    if (!user?._id) return;
    setLoading(true);
    try {
      const [sugRes, statsRes] = await Promise.all([
        api.get(`/ai-outreach/suggestions/${user._id}?status=${tab}`),
        api.get(`/ai-outreach/stats/${user._id}`),
      ]);
      setRecords(sugRes.data.suggestions || []);
      setStats(statsRes.data);
    } catch (e) {
      console.error('Failed to load AI outreach:', e);
    } finally {
      setLoading(false);
    }
  }, [user?._id, tab]);

  useEffect(() => { load(); }, [load]);

  const handleAccept = async (recordId: string, index: number) => {
    setAccepting(`${recordId}-${index}`);
    try {
      await api.post(`/ai-outreach/suggestions/${recordId}/accept`, { suggestion_index: index });
      load();
    } catch (e) {
      console.error('Failed to accept suggestion:', e);
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

  return (
    <ScrollView
      style={styles.container}
      refreshControl={<RefreshControl refreshing={loading} onRefresh={load} tintColor="#C9A962" />}
    >
      {/* Header */}
      <View style={styles.header} data-testid="ai-outreach-header">
        <TouchableOpacity onPress={() => router.back()} style={styles.backBtn} data-testid="ai-outreach-back-btn">
          <Ionicons name="arrow-back" size={24} color="#FFF" />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={styles.title}>AI Follow-ups</Text>
          <Text style={styles.subtitle}>
            Smart suggestions when you close a deal
          </Text>
        </View>
        <View style={styles.statsBadge} data-testid="ai-outreach-pending-badge">
          <Ionicons name="sparkles" size={16} color="#AF52DE" />
          <Text style={styles.statsText}>{stats.pending} pending</Text>
        </View>
      </View>

      {/* How it works */}
      <View style={styles.infoCard} data-testid="ai-outreach-info-card">
        <Ionicons name="information-circle" size={20} color="#C9A962" />
        <Text style={styles.infoText}>
          When you tag a customer as "Sold", AI analyzes their history and crafts 2 personalized follow-up messages. Pick one and it becomes a scheduled task for tomorrow morning.
        </Text>
      </View>

      {/* Tabs */}
      <View style={styles.tabRow} data-testid="ai-outreach-tabs">
        {(['pending', 'accepted', 'dismissed'] as const).map((t) => (
          <TouchableOpacity
            key={t}
            style={[styles.tab, tab === t && styles.tabActive]}
            onPress={() => setTab(t)}
            data-testid={`ai-outreach-tab-${t}`}
          >
            <Text style={[styles.tabText, tab === t && styles.tabTextActive]}>
              {t.charAt(0).toUpperCase() + t.slice(1)} ({t === 'pending' ? stats.pending : t === 'accepted' ? stats.accepted : stats.dismissed})
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* Content */}
      {loading ? (
        <ActivityIndicator size="large" color="#C9A962" style={{ marginTop: 40 }} />
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
        records.map((record) => (
          <View key={record._id} style={styles.card} data-testid={`ai-outreach-card-${record._id}`}>
            {/* Card Header */}
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

            {/* Suggestions */}
            {record.suggestions.map((sug, i) => (
              <View
                key={i}
                style={[
                  styles.suggestionCard,
                  record.status === 'accepted' && record.accepted_index === i && styles.suggestionChosen,
                ]}
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
                <Text style={styles.messageText}>"{sug.message}"</Text>
                <Text style={styles.reasonText}>{sug.best_time_reason}</Text>

                {/* Accept button only for pending */}
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

            {/* Dismiss button for pending */}
            {record.status === 'pending' && (
              <TouchableOpacity
                style={styles.dismissBtn}
                onPress={() => handleDismiss(record._id)}
                data-testid={`dismiss-btn-${record._id}`}
              >
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
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 20,
    paddingTop: 60,
    gap: 12,
  },
  backBtn: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: 'rgba(255,255,255,0.1)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  title: { color: '#FFF', fontSize: 22, fontWeight: '700' },
  subtitle: { color: '#8E8E93', fontSize: 13, marginTop: 2 },
  statsBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    backgroundColor: 'rgba(175,82,222,0.15)',
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 12,
  },
  statsText: { color: '#AF52DE', fontSize: 12, fontWeight: '600' },
  infoCard: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 10,
    marginHorizontal: 16,
    marginBottom: 16,
    padding: 14,
    backgroundColor: 'rgba(201,169,98,0.08)',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: 'rgba(201,169,98,0.2)',
  },
  infoText: { color: '#AAA', fontSize: 13, lineHeight: 18, flex: 1 },
  tabRow: {
    flexDirection: 'row',
    marginHorizontal: 16,
    marginBottom: 16,
    backgroundColor: '#1A1A1A',
    borderRadius: 10,
    padding: 3,
  },
  tab: {
    flex: 1,
    paddingVertical: 8,
    alignItems: 'center',
    borderRadius: 8,
  },
  tabActive: { backgroundColor: '#333' },
  tabText: { color: '#8E8E93', fontSize: 12, fontWeight: '600' },
  tabTextActive: { color: '#FFF' },
  emptyState: {
    alignItems: 'center',
    paddingVertical: 60,
    gap: 12,
  },
  emptyTitle: { color: '#888', fontSize: 16, fontWeight: '600' },
  emptySubtitle: { color: '#555', fontSize: 13, textAlign: 'center', paddingHorizontal: 40 },
  card: {
    marginHorizontal: 16,
    marginBottom: 16,
    backgroundColor: '#111',
    borderRadius: 14,
    borderWidth: 1,
    borderColor: '#222',
    overflow: 'hidden',
  },
  cardHeader: { padding: 16, borderBottomWidth: 1, borderBottomColor: '#1A1A1A' },
  contactRow: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  avatar: {
    width: 36,
    height: 36,
    borderRadius: 10,
    backgroundColor: '#AF52DE',
    justifyContent: 'center',
    alignItems: 'center',
  },
  contactName: { color: '#FFF', fontSize: 15, fontWeight: '600' },
  cardTime: { color: '#8E8E93', fontSize: 12, marginTop: 2 },
  statusBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 8,
  },
  statusText: { fontSize: 11, fontWeight: '600' },
  suggestionCard: {
    margin: 12,
    padding: 14,
    backgroundColor: '#1A1A1A',
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#2A2A2A',
  },
  suggestionChosen: {
    borderColor: 'rgba(52,199,89,0.4)',
    backgroundColor: 'rgba(52,199,89,0.05)',
  },
  suggestionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  approachBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    backgroundColor: 'rgba(201,169,98,0.12)',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
  },
  approachText: { color: '#C9A962', fontSize: 11, fontWeight: '600' },
  messageText: {
    color: '#E0E0E0',
    fontSize: 14,
    lineHeight: 20,
    fontStyle: 'italic',
    marginBottom: 6,
  },
  reasonText: { color: '#666', fontSize: 11, lineHeight: 15 },
  acceptBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    marginTop: 10,
    paddingVertical: 10,
    backgroundColor: '#C9A962',
    borderRadius: 8,
  },
  acceptBtnText: { color: '#000', fontSize: 13, fontWeight: '700' },
  dismissBtn: {
    alignItems: 'center',
    paddingVertical: 12,
    borderTopWidth: 1,
    borderTopColor: '#1A1A1A',
  },
  dismissText: { color: '#8E8E93', fontSize: 13 },
});
