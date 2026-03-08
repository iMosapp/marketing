import React, { useState, useEffect, useCallback } from 'react';
import { View, Text, TouchableOpacity, ScrollView, RefreshControl, StyleSheet, Linking } from 'react-native';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { useAuthStore } from '../../store/authStore';

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

function HeatBadge({ score }: { score: number }) {
  let emoji = '';
  let bg = '#333';
  if (score >= 6) { emoji = 'flame'; bg = '#FF3B30'; }
  else if (score >= 3) { emoji = 'flame'; bg = '#FF9500'; }
  else { emoji = 'thermometer'; bg = '#555'; }
  return (
    <View style={[styles.heatBadge, { backgroundColor: bg }]} data-testid="heat-badge">
      <Ionicons name={emoji as any} size={12} color="#FFF" />
      <Text style={styles.heatText}>{score.toFixed(0)}</Text>
    </View>
  );
}

export default function HotLeadsPage() {
  const user = useAuthStore((s: any) => s.user);
  const router = useRouter();
  const [hotLeads, setHotLeads] = useState<any[]>([]);
  const [signals, setSignals] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<'leads' | 'feed'>('leads');
  const [period, setPeriod] = useState(48);

  const load = useCallback(async () => {
    if (!user?._id) return;
    setLoading(true);
    try {
      const [leadsRes, sigRes] = await Promise.all([
        api.get(`/engagement/hot-leads/${user._id}?hours=${period}`),
        api.get(`/engagement/signals/${user._id}?limit=50`),
      ]);
      setHotLeads(leadsRes.data.hot_leads || []);
      setSignals(sigRes.data.signals || []);
    } catch (e) {
      console.error('Failed to load engagement data:', e);
    } finally {
      setLoading(false);
    }
  }, [user?._id, period]);

  useEffect(() => { load(); }, [load]);

  // Auto-refresh every 30 seconds
  useEffect(() => {
    const interval = setInterval(load, 30000);
    return () => clearInterval(interval);
  }, [load]);

  return (
    <ScrollView
      style={styles.container}
      refreshControl={<RefreshControl refreshing={loading} onRefresh={load} tintColor="#C9A962" />}
    >
      {/* Header */}
      <View style={styles.header} data-testid="hot-leads-header">
        <TouchableOpacity onPress={() => router.back()} style={styles.backBtn} data-testid="back-button">
          <Ionicons name="arrow-back" size={24} color="#FFF" />
        </TouchableOpacity>
        <View>
          <Text style={styles.title}>Engagement Intelligence</Text>
          <Text style={styles.subtitle}>Know when customers are thinking about you</Text>
        </View>
      </View>

      {/* Tabs */}
      <View style={styles.tabRow} data-testid="tab-row">
        <TouchableOpacity
          style={[styles.tab, tab === 'leads' && styles.tabActive]}
          onPress={() => setTab('leads')}
          data-testid="tab-hot-leads"
        >
          <Ionicons name="flame" size={16} color={tab === 'leads' ? '#FF3B30' : '#888'} />
          <Text style={[styles.tabText, tab === 'leads' && styles.tabTextActive]}>Hot Leads</Text>
          {hotLeads.length > 0 && (
            <View style={styles.badge}><Text style={styles.badgeText}>{hotLeads.length}</Text></View>
          )}
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.tab, tab === 'feed' && styles.tabActive]}
          onPress={() => setTab('feed')}
          data-testid="tab-activity-feed"
        >
          <Ionicons name="pulse" size={16} color={tab === 'feed' ? '#007AFF' : '#888'} />
          <Text style={[styles.tabText, tab === 'feed' && styles.tabTextActive]}>Activity Feed</Text>
        </TouchableOpacity>
      </View>

      {/* Period filter */}
      <View style={styles.filterRow} data-testid="period-filter">
        {[24, 48, 168].map(h => (
          <TouchableOpacity
            key={h}
            style={[styles.filterChip, period === h && styles.filterActive]}
            onPress={() => setPeriod(h)}
            data-testid={`filter-${h}h`}
          >
            <Text style={[styles.filterText, period === h && styles.filterTextActive]}>
              {h === 24 ? 'Today' : h === 48 ? '48 Hours' : '7 Days'}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* Content */}
      {tab === 'leads' ? (
        <View style={styles.section}>
          {hotLeads.length === 0 ? (
            <View style={styles.emptyState} data-testid="empty-state">
              <Ionicons name="flame-outline" size={48} color="#555" />
              <Text style={styles.emptyTitle}>No hot leads yet</Text>
              <Text style={styles.emptyText}>
                When customers view your cards, click your links, or check out your reviews, they'll appear here instantly.
              </Text>
            </View>
          ) : (
            hotLeads.map((lead, i) => {
              const iconInfo = SIGNAL_ICONS[lead.last_signal] || { icon: 'eye', color: '#007AFF' };
              return (
                <TouchableOpacity
                  key={`${lead.contact_id || lead.contact_name}-${i}`}
                  style={[styles.leadCard, i === 0 && styles.leadCardHot]}
                  onPress={() => lead.contact_id ? router.push(`/contact/${lead.contact_id}`) : null}
                  data-testid={`hot-lead-${i}`}
                >
                  <View style={[styles.leadIcon, { backgroundColor: iconInfo.color + '20' }]}>
                    <Ionicons name={iconInfo.icon as any} size={20} color={iconInfo.color} />
                  </View>
                  <View style={styles.leadInfo}>
                    <View style={styles.leadNameRow}>
                      <Text style={styles.leadName}>{lead.contact_name}</Text>
                      {lead.is_return_visit && (
                        <View style={styles.returnBadge} data-testid="return-visit-badge">
                          <Text style={styles.returnText}>RETURN VISIT</Text>
                        </View>
                      )}
                    </View>
                    <Text style={styles.leadAction}>{lead.last_signal_label}</Text>
                    <Text style={styles.leadTime}>{timeAgo(lead.minutes_ago)}</Text>
                    {lead.total_signals > 1 && (
                      <Text style={styles.leadMulti}>{lead.total_signals} total interactions</Text>
                    )}
                  </View>
                  <View style={styles.leadRight}>
                    <HeatBadge score={lead.heat_score} />
                    {lead.phone && (
                      <TouchableOpacity
                        style={styles.quickText}
                        onPress={(e) => {
                          e.stopPropagation?.();
                          Linking.openURL(`sms:${lead.phone}`);
                        }}
                        data-testid={`quick-text-${i}`}
                      >
                        <Ionicons name="chatbubble" size={14} color="#34C759" />
                      </TouchableOpacity>
                    )}
                  </View>
                </TouchableOpacity>
              );
            })
          )}
        </View>
      ) : (
        <View style={styles.section}>
          {signals.length === 0 ? (
            <View style={styles.emptyState} data-testid="empty-feed">
              <Ionicons name="pulse-outline" size={48} color="#555" />
              <Text style={styles.emptyTitle}>No activity yet</Text>
              <Text style={styles.emptyText}>Real-time engagement signals will appear here.</Text>
            </View>
          ) : (
            signals.map((sig, i) => {
              const iconInfo = SIGNAL_ICONS[sig.signal_type] || { icon: 'eye', color: '#007AFF' };
              return (
                <View key={`sig-${i}`} style={styles.signalRow} data-testid={`signal-${i}`}>
                  <View style={[styles.signalDot, { backgroundColor: iconInfo.color }]} />
                  <View style={styles.signalIcon}>
                    <Ionicons name={iconInfo.icon as any} size={16} color={iconInfo.color} />
                  </View>
                  <View style={styles.signalInfo}>
                    <Text style={styles.signalName}>{sig.contact_name || 'Someone'}</Text>
                    <Text style={styles.signalLabel}>{sig.label}</Text>
                  </View>
                  <View style={styles.signalMeta}>
                    {sig.is_return_visit && (
                      <Ionicons name="refresh" size={12} color="#FF9500" style={{ marginRight: 4 }} />
                    )}
                    <Text style={styles.signalTime}>
                      {sig.created_at ? timeAgo(Math.round((Date.now() - new Date(sig.created_at).getTime()) / 60000)) : ''}
                    </Text>
                  </View>
                </View>
              );
            })
          )}
        </View>
      )}

      <View style={{ height: 80 }} />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0A0A0A' },
  header: { flexDirection: 'row', alignItems: 'center', padding: 20, paddingTop: 56, gap: 12 },
  backBtn: { width: 40, height: 40, borderRadius: 12, backgroundColor: '#1C1C1E', alignItems: 'center', justifyContent: 'center' },
  title: { color: '#FFF', fontSize: 22, fontWeight: '700' },
  subtitle: { color: '#888', fontSize: 13, marginTop: 2 },

  tabRow: { flexDirection: 'row', marginHorizontal: 20, marginBottom: 12, backgroundColor: '#1C1C1E', borderRadius: 12, padding: 4 },
  tab: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingVertical: 10, borderRadius: 10 },
  tabActive: { backgroundColor: '#2C2C2E' },
  tabText: { color: '#888', fontSize: 14, fontWeight: '600' },
  tabTextActive: { color: '#FFF' },
  badge: { backgroundColor: '#FF3B30', borderRadius: 10, paddingHorizontal: 6, paddingVertical: 1, marginLeft: 4 },
  badgeText: { color: '#FFF', fontSize: 11, fontWeight: '700' },

  filterRow: { flexDirection: 'row', marginHorizontal: 20, marginBottom: 16, gap: 8 },
  filterChip: { paddingHorizontal: 14, paddingVertical: 6, borderRadius: 20, backgroundColor: '#1C1C1E' },
  filterActive: { backgroundColor: '#C9A962' },
  filterText: { color: '#888', fontSize: 13, fontWeight: '500' },
  filterTextActive: { color: '#000' },

  section: { paddingHorizontal: 20 },

  leadCard: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#1C1C1E', borderRadius: 14, padding: 14, marginBottom: 10, gap: 12 },
  leadCardHot: { borderWidth: 1, borderColor: '#FF3B3040' },
  leadIcon: { width: 44, height: 44, borderRadius: 12, alignItems: 'center', justifyContent: 'center' },
  leadInfo: { flex: 1 },
  leadNameRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  leadName: { color: '#FFF', fontSize: 15, fontWeight: '600' },
  returnBadge: { backgroundColor: '#FF950020', paddingHorizontal: 6, paddingVertical: 2, borderRadius: 4 },
  returnText: { color: '#FF9500', fontSize: 9, fontWeight: '700', letterSpacing: 0.5 },
  leadAction: { color: '#AAA', fontSize: 13, marginTop: 2 },
  leadTime: { color: '#666', fontSize: 12, marginTop: 1 },
  leadMulti: { color: '#C9A962', fontSize: 11, marginTop: 2, fontWeight: '500' },
  leadRight: { alignItems: 'center', gap: 8 },
  heatBadge: { flexDirection: 'row', alignItems: 'center', gap: 3, paddingHorizontal: 8, paddingVertical: 3, borderRadius: 10 },
  heatText: { color: '#FFF', fontSize: 11, fontWeight: '700' },
  quickText: { width: 32, height: 32, borderRadius: 16, backgroundColor: '#34C75920', alignItems: 'center', justifyContent: 'center' },

  signalRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: '#1C1C1E', gap: 10 },
  signalDot: { width: 6, height: 6, borderRadius: 3 },
  signalIcon: { width: 32, height: 32, borderRadius: 8, backgroundColor: '#1C1C1E', alignItems: 'center', justifyContent: 'center' },
  signalInfo: { flex: 1 },
  signalName: { color: '#FFF', fontSize: 14, fontWeight: '600' },
  signalLabel: { color: '#888', fontSize: 12, marginTop: 1 },
  signalMeta: { flexDirection: 'row', alignItems: 'center' },
  signalTime: { color: '#555', fontSize: 11 },

  emptyState: { alignItems: 'center', paddingVertical: 60 },
  emptyTitle: { color: '#FFF', fontSize: 18, fontWeight: '600', marginTop: 16 },
  emptyText: { color: '#666', fontSize: 14, textAlign: 'center', marginTop: 8, paddingHorizontal: 40, lineHeight: 20 },
});
