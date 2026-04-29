import React, { useState, useEffect, useCallback } from 'react';
import {
  View, Text, TouchableOpacity, StyleSheet, ScrollView,
  ActivityIndicator, RefreshControl, TextInput,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import api from '../../services/api';
import { showSimpleAlert } from '../../services/alert';
import { useThemeStore } from '../../store/themeStore';
import { useAuthStore } from '../../store/authStore';

const STATUS_CONFIG: Record<string, { label: string; color: string }> = {
  queued:     { label: 'Queued',     color: '#FF9500' },
  sent:       { label: 'Sent',       color: '#34C759' },
  sent_mock:  { label: 'Sent (Mock)',color: '#007AFF' },
  failed:     { label: 'Failed',     color: '#FF3B30' },
};

const FILTERS = ['all', 'queued', 'sent', 'failed'];

export default function LeadIntakeDashboard() {
  const { colors } = useThemeStore();
  const s = getS(colors);
  const router = useRouter();
  const { user } = useAuthStore();

  const [leads, setLeads]         = useState<any[]>([]);
  const [loading, setLoading]     = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [filter, setFilter]       = useState('all');
  const [retrying, setRetrying]   = useState<string | null>(null);

  // Stats
  const total   = leads.length;
  const queued  = leads.filter(l => l.status === 'queued').length;
  const sent    = leads.filter(l => l.status?.startsWith('sent')).length;
  const failed  = leads.filter(l => l.status === 'failed').length;
  const afterHours = leads.filter(l => l.is_after_hours && l.status === 'queued').length;

  const loadLeads = useCallback(async () => {
    try {
      const params = filter !== 'all' ? `?status=${filter}&limit=100` : '?limit=100';
      const res = await api.get(`/leads/${params}`);
      setLeads(Array.isArray(res.data) ? res.data : []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [filter]);

  useEffect(() => { loadLeads(); }, [filter]);

  const handleRetry = async (leadId: string) => {
    setRetrying(leadId);
    try {
      await api.post(`/leads/${leadId}/retry`);
      showSimpleAlert('Re-queued', 'Lead will be sent within 30 seconds.');
      loadLeads();
    } catch { showSimpleAlert('Error', 'Failed to retry.'); }
    finally { setRetrying(null); }
  };

  const formatTime = (iso?: string) => {
    if (!iso) return '—';
    const d = new Date(iso);
    return d.toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
  };

  const timeUntil = (iso?: string) => {
    if (!iso) return '';
    const diff = (new Date(iso).getTime() - Date.now()) / 1000;
    if (diff <= 0) return 'sending now';
    if (diff < 60) return `${Math.round(diff)}s`;
    if (diff < 3600) return `${Math.round(diff / 60)}m`;
    const h = Math.floor(diff / 3600);
    const m = Math.round((diff % 3600) / 60);
    return `${h}h ${m}m`;
  };

  return (
    <SafeAreaView style={s.container} edges={['top']}>
      {/* Header */}
      <View style={s.header}>
        <TouchableOpacity onPress={() => router.back()} style={s.backBtn}>
          <Ionicons name="arrow-back" size={22} color={colors.text} />
        </TouchableOpacity>
        <Text style={s.headerTitle}>Internet Leads</Text>
        <TouchableOpacity onPress={() => router.push('/admin/lead-sources' as any)} style={s.configBtn}>
          <Ionicons name="settings-outline" size={22} color={colors.textSecondary} />
        </TouchableOpacity>
      </View>

      {/* Stats bar */}
      <View style={s.statsRow}>
        <StatPill label="Total"       value={total}      color={colors.text} />
        <StatPill label="Queued"      value={queued}     color="#FF9500" />
        <StatPill label="After-Hours" value={afterHours} color="#AF52DE" />
        <StatPill label="Sent"        value={sent}       color="#34C759" />
        <StatPill label="Failed"      value={failed}     color="#FF3B30" />
      </View>

      {/* Filter pills */}
      <ScrollView horizontal showsHorizontalScrollIndicator={false}
        style={s.filterBar} contentContainerStyle={{ paddingHorizontal: 16, gap: 8, paddingVertical: 8 }}>
        {FILTERS.map(f => (
          <TouchableOpacity key={f} style={[s.pill, filter === f && s.pillActive]} onPress={() => setFilter(f)}>
            <Text style={[s.pillText, filter === f && s.pillTextActive]}>
              {f.charAt(0).toUpperCase() + f.slice(1)}
            </Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      <ScrollView
        style={{ flex: 1 }}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); loadLeads(); }} tintColor="#C9A962" />}
        contentContainerStyle={{ padding: 16, paddingBottom: 48 }}
      >
        {loading ? (
          <ActivityIndicator color="#C9A962" style={{ marginTop: 40 }} />
        ) : leads.length === 0 ? (
          <View style={s.empty}>
            <Ionicons name="flash-outline" size={56} color={colors.textSecondary} />
            <Text style={s.emptyTitle}>No leads yet</Text>
            <Text style={s.emptySub}>
              Configure a lead source and paste your ADF webhook URL into Cars.com or AutoTrader.
            </Text>
            <TouchableOpacity style={s.setupBtn} onPress={() => router.push('/admin/lead-sources' as any)}>
              <Ionicons name="settings-outline" size={16} color="#000" />
              <Text style={s.setupBtnText}>Set Up Lead Sources</Text>
            </TouchableOpacity>
          </View>
        ) : (
          leads.map(lead => {
            const sc = STATUS_CONFIG[lead.status] || { label: lead.status, color: colors.textSecondary };
            const isAfterH = lead.is_after_hours && lead.status === 'queued';
            return (
              <View key={lead.id} style={s.card}>
                {/* Row 1: name + status */}
                <View style={s.cardRow}>
                  <View style={{ flex: 1 }}>
                    <Text style={s.cardName}>{lead.full_name || 'Unknown'}</Text>
                    <Text style={s.cardSource}>{lead.source_name} · {formatTime(lead.received_at)}</Text>
                  </View>
                  <View style={[s.statusBadge, { backgroundColor: sc.color + '20' }]}>
                    <Text style={[s.statusText, { color: sc.color }]}>{sc.label}</Text>
                  </View>
                </View>

                {/* Row 2: contact info */}
                <View style={s.infoRow}>
                  {lead.phone ? <InfoChip icon="call" text={lead.phone} colors={colors} /> : null}
                  {lead.email ? <InfoChip icon="mail" text={lead.email} colors={colors} /> : null}
                </View>

                {/* Vehicle interest */}
                {lead.vehicle_interest ? (
                  <View style={s.vehicleRow}>
                    <Ionicons name="car" size={14} color="#C9A962" />
                    <Text style={s.vehicleText}>{lead.vehicle_interest}</Text>
                  </View>
                ) : null}

                {/* After-hours timing */}
                {isAfterH && lead.scheduled_send_at ? (
                  <View style={s.afterHoursBadge}>
                    <Ionicons name="moon" size={13} color="#AF52DE" />
                    <Text style={s.afterHoursText}>
                      After-hours — sends in {timeUntil(lead.scheduled_send_at)} ({formatTime(lead.scheduled_send_at)})
                    </Text>
                  </View>
                ) : null}

                {/* Draft message preview */}
                {lead.draft_message ? (
                  <View style={s.draftBox}>
                    <Text style={s.draftLabel}>AI Draft</Text>
                    <Text style={s.draftText} numberOfLines={2}>{lead.draft_message}</Text>
                  </View>
                ) : null}

                {/* Actions */}
                <View style={s.actionRow}>
                  {lead.contact_id ? (
                    <TouchableOpacity style={s.actionBtn}
                      onPress={() => router.push(`/contact/${lead.contact_id}` as any)}>
                      <Ionicons name="person" size={14} color="#007AFF" />
                      <Text style={[s.actionBtnText, { color: '#007AFF' }]}>View Contact</Text>
                    </TouchableOpacity>
                  ) : null}
                  {lead.conversation_id ? (
                    <TouchableOpacity style={s.actionBtn}
                      onPress={() => router.push(`/thread/${lead.conversation_id}` as any)}>
                      <Ionicons name="chatbubble" size={14} color="#34C759" />
                      <Text style={[s.actionBtnText, { color: '#34C759' }]}>Open Inbox</Text>
                    </TouchableOpacity>
                  ) : null}
                  {lead.status === 'failed' ? (
                    <TouchableOpacity style={[s.actionBtn, { backgroundColor: '#FF3B3015', borderColor: '#FF3B30' }]}
                      onPress={() => handleRetry(lead.id)} disabled={retrying === lead.id}>
                      {retrying === lead.id
                        ? <ActivityIndicator size="small" color="#FF3B30" />
                        : <><Ionicons name="refresh" size={14} color="#FF3B30" />
                           <Text style={[s.actionBtnText, { color: '#FF3B30' }]}>Retry</Text></>}
                    </TouchableOpacity>
                  ) : null}
                </View>
              </View>
            );
          })
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

function StatPill({ label, value, color }: { label: string; value: number; color: string }) {
  const { colors } = useThemeStore();
  return (
    <View style={{ alignItems: 'center', flex: 1 }}>
      <Text style={{ fontSize: 22, fontWeight: '800', color }}>{value}</Text>
      <Text style={{ fontSize: 11, color: colors.textSecondary, marginTop: 1 }}>{label}</Text>
    </View>
  );
}

function InfoChip({ icon, text, colors }: { icon: string; text: string; colors: any }) {
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4, marginRight: 12 }}>
      <Ionicons name={icon as any} size={13} color={colors.textSecondary} />
      <Text style={{ fontSize: 13, color: colors.textSecondary }}>{text}</Text>
    </View>
  );
}

const getS = (colors: any) => StyleSheet.create({
  container:      { flex: 1, backgroundColor: colors.bg },
  header:         { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: colors.border },
  backBtn:        { width: 36, height: 36, borderRadius: 18, backgroundColor: colors.card, alignItems: 'center', justifyContent: 'center' },
  configBtn:      { width: 36, height: 36, borderRadius: 18, backgroundColor: colors.card, alignItems: 'center', justifyContent: 'center' },
  headerTitle:    { fontSize: 18, fontWeight: '700', color: colors.text },
  statsRow:       { flexDirection: 'row', paddingVertical: 14, paddingHorizontal: 8, borderBottomWidth: 1, borderBottomColor: colors.border, backgroundColor: colors.card },
  filterBar:      { maxHeight: 50, borderBottomWidth: 1, borderBottomColor: colors.border },
  pill:           { paddingHorizontal: 16, paddingVertical: 7, borderRadius: 20, backgroundColor: colors.card },
  pillActive:     { backgroundColor: '#C9A962' },
  pillText:       { fontSize: 14, fontWeight: '500', color: colors.textSecondary },
  pillTextActive: { color: '#000', fontWeight: '700' },

  // Card
  card:           { backgroundColor: colors.card, borderRadius: 14, padding: 14, marginBottom: 10, borderWidth: 1, borderColor: colors.border },
  cardRow:        { flexDirection: 'row', alignItems: 'flex-start', marginBottom: 8 },
  cardName:       { fontSize: 17, fontWeight: '700', color: colors.text },
  cardSource:     { fontSize: 13, color: colors.textSecondary, marginTop: 2 },
  statusBadge:    { borderRadius: 8, paddingHorizontal: 10, paddingVertical: 4 },
  statusText:     { fontSize: 12, fontWeight: '700' },
  infoRow:        { flexDirection: 'row', flexWrap: 'wrap', marginBottom: 6 },
  vehicleRow:     { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 6 },
  vehicleText:    { fontSize: 13, color: '#C9A962', fontWeight: '600' },
  afterHoursBadge:{ flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: '#AF52DE18', borderRadius: 8, paddingHorizontal: 10, paddingVertical: 6, marginBottom: 8 },
  afterHoursText: { fontSize: 13, color: '#AF52DE', fontWeight: '500' },
  draftBox:       { backgroundColor: colors.bg, borderRadius: 8, padding: 10, marginBottom: 8, borderLeftWidth: 3, borderLeftColor: '#C9A962' },
  draftLabel:     { fontSize: 10, fontWeight: '700', color: '#C9A962', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 3 },
  draftText:      { fontSize: 13, color: colors.text, lineHeight: 18 },
  actionRow:      { flexDirection: 'row', gap: 8, flexWrap: 'wrap', marginTop: 4 },
  actionBtn:      { flexDirection: 'row', alignItems: 'center', gap: 5, backgroundColor: colors.bg, borderRadius: 8, paddingHorizontal: 10, paddingVertical: 6, borderWidth: 1, borderColor: colors.border },
  actionBtnText:  { fontSize: 13, fontWeight: '600' },

  // Empty
  empty:          { alignItems: 'center', paddingTop: 60 },
  emptyTitle:     { fontSize: 20, fontWeight: '700', color: colors.text, marginTop: 16 },
  emptySub:       { fontSize: 14, color: colors.textSecondary, textAlign: 'center', marginTop: 8, maxWidth: 300, lineHeight: 20 },
  setupBtn:       { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: '#C9A962', borderRadius: 12, paddingHorizontal: 20, paddingVertical: 13, marginTop: 24 },
  setupBtnText:   { fontSize: 15, fontWeight: '700', color: '#000' },
});
