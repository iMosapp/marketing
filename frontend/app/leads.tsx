import React, { useState, useCallback } from 'react';
import {
  View, Text, TouchableOpacity, ScrollView, ActivityIndicator, RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import { Image } from 'expo-image';
import { useThemeStore } from '../store/themeStore';
import { useAuthStore } from '../store/authStore';
import { resolvePhotoUrl } from '../utils/photoUrl';
import api from '../services/api';

const ACCENT = '#AF52DE';

const STATUS_META: Record<string, { label: string; color: string }> = {
  queued: { label: 'QUEUED', color: '#FF9500' },
  sent: { label: 'SENT', color: '#007AFF' },
  failed: { label: 'FAILED', color: '#FF3B30' },
};

function timeAgo(iso: string) {
  try {
    const diffMin = Math.floor((Date.now() - new Date(iso).getTime()) / 60000);
    if (diffMin < 1) return 'now';
    if (diffMin < 60) return `${diffMin}m ago`;
    const hrs = Math.floor(diffMin / 60);
    if (hrs < 24) return `${hrs}h ago`;
    const days = Math.floor(hrs / 24);
    if (days < 7) return `${days}d ago`;
    return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  } catch { return ''; }
}

const fmtPrice = (p: any) => (p || p === 0) ? `$${Number(p).toLocaleString('en-US', { maximumFractionDigits: 0 })}` : '';

const fmtDuration = (s: number | null | undefined) => {
  if (s == null) return '—';
  if (s < 60) return `${Math.max(1, Math.round(s))}s`;
  if (s < 3600) return `${Math.round(s / 60)}m`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ${Math.round((s % 3600) / 60)}m`;
  return `${Math.floor(s / 86400)}d`;
};

const speedColor = (s: number) => (s < 300 ? '#34C759' : s < 3600 ? '#FF9500' : '#FF3B30');

export default function LeadsDashboard() {
  const { colors } = useThemeStore();
  const { user } = useAuthStore();
  const router = useRouter();

  const [tab, setTab] = useState<'leads' | 'roi' | 'speed'>('leads');
  const [leads, setLeads] = useState<any[]>([]);
  const [roi, setRoi] = useState<any>(null);
  const [speed, setSpeed] = useState<any>(null);
  const [roiDays, setRoiDays] = useState(90);
  const [statusFilter, setStatusFilter] = useState('all');
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchData = useCallback(async () => {
    if (!user?._id) { setLoading(false); return; }
    try {
      const storeParam = user.store_id ? `store_id=${user.store_id}&` : '';
      const statusParam = statusFilter !== 'all' ? `status=${statusFilter}&` : '';
      const [leadsRes, roiRes, speedRes] = await Promise.all([
        api.get(`/leads/?${storeParam}${statusParam}limit=100`),
        api.get(`/leads/analytics/sources?${storeParam}days=${roiDays}`),
        api.get(`/leads/analytics/response-times?${storeParam}days=${roiDays}`),
      ]);
      setLeads(leadsRes.data || []);
      setRoi(roiRes.data || null);
      setSpeed(speedRes.data || null);
    } catch (e) {
      console.error('Leads fetch failed:', e);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [user?._id, user?.store_id, statusFilter, roiDays]);

  useFocusEffect(useCallback(() => { fetchData(); }, [fetchData]));

  const FILTERS = [
    { key: 'all', label: 'All' },
    { key: 'queued', label: 'Queued' },
    { key: 'sent', label: 'Sent' },
    { key: 'failed', label: 'Failed' },
  ];

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      {/* Header */}
      <View style={{ flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 12, gap: 12 }}>
        <TouchableOpacity onPress={() => router.back()} data-testid="leads-back-btn">
          <Ionicons name="chevron-back" size={26} color={colors.text} />
        </TouchableOpacity>
        <Text style={{ fontSize: 20, fontWeight: '800', color: colors.text, flex: 1 }} numberOfLines={1} maxFontSizeMultiplier={1.15}>Internet Leads</Text>
      </View>

      {/* Tabs */}
      <View style={{ flexDirection: 'row', alignSelf: 'center', backgroundColor: colors.card, borderRadius: 10, padding: 3, marginBottom: 10 }}>
        {([['leads', 'Leads', 'people-outline'], ['roi', 'Source ROI', 'trending-up-outline'], ['speed', 'Speed', 'stopwatch-outline']] as const).map(([k, label, icon]) => (
          <TouchableOpacity
            key={k}
            onPress={() => setTab(k)}
            style={{
              flexDirection: 'row', alignItems: 'center', gap: 6,
              paddingVertical: 7, paddingHorizontal: 16, borderRadius: 8,
              backgroundColor: tab === k ? colors.bg : 'transparent',
            }}
            data-testid={`leads-tab-${k}`}
          >
            <Ionicons name={icon as any} size={15} color={tab === k ? colors.text : colors.textSecondary} />
            <Text style={{ fontSize: 14, fontWeight: '600', color: tab === k ? colors.text : colors.textSecondary }} numberOfLines={1} maxFontSizeMultiplier={1.15}>{label}</Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* Filters row */}
      {tab === 'leads' ? (
        <View style={{ flexDirection: 'row', gap: 8, paddingHorizontal: 16, marginBottom: 10 }}>
          {FILTERS.map(f => {
            const active = statusFilter === f.key;
            return (
              <TouchableOpacity
                key={f.key}
                style={{ paddingHorizontal: 14, height: 32, borderRadius: 16, justifyContent: 'center', backgroundColor: active ? ACCENT : colors.card }}
                onPress={() => setStatusFilter(f.key)}
                data-testid={`leads-filter-${f.key}`}
              >
                <Text style={{ fontSize: 13, fontWeight: '600', color: active ? '#FFF' : colors.textSecondary }} numberOfLines={1}>{f.label}</Text>
              </TouchableOpacity>
            );
          })}
        </View>
      ) : (
        <View style={{ flexDirection: 'row', gap: 8, paddingHorizontal: 16, marginBottom: 10 }}>
          {[30, 90, 365].map(d => {
            const active = roiDays === d;
            return (
              <TouchableOpacity
                key={d}
                style={{ paddingHorizontal: 14, height: 32, borderRadius: 16, justifyContent: 'center', backgroundColor: active ? ACCENT : colors.card }}
                onPress={() => setRoiDays(d)}
                data-testid={`roi-days-${d}`}
              >
                <Text style={{ fontSize: 13, fontWeight: '600', color: active ? '#FFF' : colors.textSecondary }}>{d === 365 ? '1 Year' : `${d} Days`}</Text>
              </TouchableOpacity>
            );
          })}
        </View>
      )}

      {loading ? (
        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}>
          <ActivityIndicator size="large" color={ACCENT} />
        </View>
      ) : (
        <ScrollView
          style={{ flex: 1 }}
          contentContainerStyle={{ padding: 16, paddingBottom: 40, gap: 10 }}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); fetchData(); }} tintColor={colors.textSecondary} />}
        >
          {tab === 'leads' ? (
            leads.length === 0 ? (
              <View style={{ alignItems: 'center', paddingTop: 50 }}>
                <Ionicons name="globe-outline" size={44} color={colors.textSecondary} />
                <Text style={{ fontSize: 16, fontWeight: '600', color: colors.text, marginTop: 12 }}>No internet leads yet</Text>
                <Text style={{ fontSize: 14, color: colors.textSecondary, textAlign: 'center', marginTop: 6, paddingHorizontal: 32 }}>
                  Connect a lead provider in Admin → Lead Sources and new leads will appear here automatically.
                </Text>
              </View>
            ) : (
              leads.map((l: any) => {
                const st = STATUS_META[l.status] || STATUS_META.queued;
                const mi = l.matched_inventory;
                return (
                  <TouchableOpacity
                    key={l.id}
                    style={{ backgroundColor: colors.card, borderRadius: 12, padding: 14 }}
                    onPress={() => l.conversation_id && router.push(`/thread/${l.conversation_id}` as any)}
                    activeOpacity={0.7}
                    data-testid={`lead-card-${l.id}`}
                  >
                    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                      <Text style={{ fontSize: 16, fontWeight: '700', color: colors.text, flex: 1 }} numberOfLines={1}>{l.full_name || 'Unknown'}</Text>
                      <Text style={{ fontSize: 12, color: colors.textSecondary }}>{timeAgo(l.received_at)}</Text>
                    </View>
                    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 6, flexWrap: 'wrap' }}>
                      <View style={{ backgroundColor: `${ACCENT}18`, paddingVertical: 3, paddingHorizontal: 8, borderRadius: 6 }}>
                        <Text style={{ fontSize: 11, fontWeight: '700', color: ACCENT }} numberOfLines={1}>{l.source_name || 'Lead'}</Text>
                      </View>
                      <View style={{ backgroundColor: `${st.color}18`, paddingVertical: 3, paddingHorizontal: 8, borderRadius: 6 }}>
                        <Text style={{ fontSize: 11, fontWeight: '700', color: st.color }}>{st.label}</Text>
                      </View>
                      {l.first_response_seconds != null && (
                        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 3, backgroundColor: `${speedColor(l.first_response_seconds)}18`, paddingVertical: 3, paddingHorizontal: 8, borderRadius: 6 }} data-testid={`lead-speed-badge-${l.id}`}>
                          <Ionicons name="flash" size={10} color={speedColor(l.first_response_seconds)} />
                          <Text style={{ fontSize: 11, fontWeight: '700', color: speedColor(l.first_response_seconds) }}>Replied in {fmtDuration(l.first_response_seconds)}</Text>
                        </View>
                      )}
                      {l.has_reply && (
                        <View style={{ backgroundColor: '#34C75918', paddingVertical: 3, paddingHorizontal: 8, borderRadius: 6 }}>
                          <Text style={{ fontSize: 11, fontWeight: '700', color: '#34C759' }}>REPLIED</Text>
                        </View>
                      )}
                    </View>
                    {!!l.vehicle_interest && (
                      <Text style={{ fontSize: 13, color: colors.textSecondary, marginTop: 6 }} numberOfLines={1}>
                        Interested in: {l.vehicle_interest}
                      </Text>
                    )}
                    {mi && (
                      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, marginTop: 8, backgroundColor: '#34C75910', borderRadius: 10, padding: 8 }}>
                        {mi.photo_url ? (
                          <Image source={{ uri: resolvePhotoUrl(mi.photo_url) || '' }} style={{ width: 44, height: 44, borderRadius: 8, backgroundColor: colors.surface }} contentFit="cover" />
                        ) : (
                          <View style={{ width: 44, height: 44, borderRadius: 8, backgroundColor: colors.surface, alignItems: 'center', justifyContent: 'center' }}>
                            <Ionicons name="car-sport" size={20} color="#34C759" />
                          </View>
                        )}
                        <View style={{ flex: 1 }}>
                          <Text style={{ fontSize: 13, fontWeight: '700', color: colors.text }} numberOfLines={1}>In stock: {mi.name}</Text>
                          <Text style={{ fontSize: 12, color: colors.textSecondary }} numberOfLines={1}>
                            {[mi.color, fmtPrice(mi.price), mi.stock_number ? `Stock #${mi.stock_number}` : ''].filter(Boolean).join(' · ')}
                          </Text>
                        </View>
                      </View>
                    )}
                  </TouchableOpacity>
                );
              })
            )
          ) : tab === 'speed' ? (
            /* ─── Speed to Lead tab ─── */
            !speed || (speed.overall?.measured === 0 && speed.overall?.unanswered === 0) ? (
              <View style={{ alignItems: 'center', paddingTop: 50 }}>
                <Ionicons name="stopwatch-outline" size={44} color={colors.textSecondary} />
                <Text style={{ fontSize: 16, fontWeight: '600', color: colors.text, marginTop: 12 }}>No response data yet</Text>
                <Text style={{ fontSize: 14, color: colors.textSecondary, textAlign: 'center', marginTop: 6, paddingHorizontal: 32 }}>
                  Once reps start replying to internet leads, you'll see who answers fastest here.
                </Text>
              </View>
            ) : (
              <>
                {/* Overall stats */}
                <View style={{ flexDirection: 'row', gap: 8 }} data-testid="speed-overall-stats">
                  {[
                    { label: 'TEAM AVG', val: fmtDuration(speed.overall.avg_seconds), color: speed.overall.avg_seconds != null ? speedColor(speed.overall.avg_seconds) : colors.text },
                    { label: 'MEASURED', val: String(speed.overall.measured), color: '#007AFF' },
                    { label: 'NO REPLY YET', val: String(speed.overall.unanswered), color: '#FF9500' },
                  ].map(s => (
                    <View key={s.label} style={{ flex: 1, alignItems: 'center', backgroundColor: colors.card, borderRadius: 12, paddingVertical: 12 }}>
                      <Text style={{ fontSize: 20, fontWeight: '800', color: s.color }} numberOfLines={1}>{s.val}</Text>
                      <Text style={{ fontSize: 10, fontWeight: '600', color: colors.textSecondary, letterSpacing: 0.5 }} numberOfLines={1}>{s.label}</Text>
                    </View>
                  ))}
                </View>

                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: `${ACCENT}12`, borderRadius: 10, padding: 10 }}>
                  <Ionicons name="flash" size={15} color={ACCENT} />
                  <Text style={{ fontSize: 13, color: colors.textSecondary, flex: 1 }} maxFontSizeMultiplier={1.15}>
                    Time from lead arrival to the first human rep reply. Under 5 minutes wins deals.
                  </Text>
                </View>

                {/* Rep leaderboard */}
                {speed.reps.map((r: any, i: number) => {
                  const rankColors = ['#C9A962', '#A8A8A8', '#CD7F32'];
                  const rankColor = rankColors[i] || colors.textSecondary;
                  return (
                    <View key={r.user_id} style={{ flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: colors.card, borderRadius: 12, padding: 14 }} data-testid={`speed-rep-${r.user_id}`}>
                      <View style={{ width: 32, height: 32, borderRadius: 16, alignItems: 'center', justifyContent: 'center', backgroundColor: `${rankColor}22` }}>
                        <Text style={{ fontSize: 14, fontWeight: '800', color: rankColor }}>{i + 1}</Text>
                      </View>
                      <View style={{ flex: 1 }}>
                        <Text style={{ fontSize: 15, fontWeight: '700', color: colors.text }} numberOfLines={1}>{r.name}</Text>
                        <Text style={{ fontSize: 12, color: colors.textSecondary }} numberOfLines={1}>
                          {r.count} lead{r.count !== 1 ? 's' : ''} · fastest {fmtDuration(r.fastest_seconds)}
                        </Text>
                      </View>
                      <View style={{ alignItems: 'flex-end' }}>
                        <Text style={{ fontSize: 17, fontWeight: '800', color: speedColor(r.avg_seconds) }}>{fmtDuration(r.avg_seconds)}</Text>
                        <Text style={{ fontSize: 10, fontWeight: '600', color: colors.textSecondary, letterSpacing: 0.4 }}>AVG RESPONSE</Text>
                      </View>
                    </View>
                  );
                })}
              </>
            )
          ) : (
            /* ─── Source ROI tab ─── */
            !roi || roi.sources.length === 0 ? (
              <View style={{ alignItems: 'center', paddingTop: 50 }}>
                <Ionicons name="trending-up-outline" size={44} color={colors.textSecondary} />
                <Text style={{ fontSize: 16, fontWeight: '600', color: colors.text, marginTop: 12 }}>No lead data yet</Text>
                <Text style={{ fontSize: 14, color: colors.textSecondary, textAlign: 'center', marginTop: 6, paddingHorizontal: 32 }}>
                  Once leads start arriving, you'll see which sources actually turn into conversations and sales.
                </Text>
              </View>
            ) : (
              <>
                {/* Totals */}
                <View style={{ flexDirection: 'row', gap: 8 }}>
                  {[
                    { label: 'LEADS', val: roi.totals.leads, color: ACCENT },
                    { label: 'REPLIED', val: roi.totals.replied, color: '#007AFF' },
                    { label: 'SOLD', val: roi.totals.sold, color: '#34C759' },
                  ].map(s => (
                    <View key={s.label} style={{ flex: 1, alignItems: 'center', backgroundColor: colors.card, borderRadius: 12, paddingVertical: 12 }}>
                      <Text style={{ fontSize: 22, fontWeight: '800', color: s.color }}>{s.val}</Text>
                      <Text style={{ fontSize: 11, fontWeight: '600', color: colors.textSecondary, letterSpacing: 0.5 }} numberOfLines={1}>{s.label}</Text>
                    </View>
                  ))}
                </View>

                {roi.sources.map((s: any) => (
                  <View key={s.source_name} style={{ backgroundColor: colors.card, borderRadius: 12, padding: 14 }} data-testid={`roi-source-${s.source_name}`}>
                    <View style={{ flexDirection: 'row', alignItems: 'center' }}>
                      <Text style={{ fontSize: 15, fontWeight: '700', color: colors.text, flex: 1 }} numberOfLines={1}>{s.source_name}</Text>
                      <Text style={{ fontSize: 13, color: colors.textSecondary }}>{s.leads} lead{s.leads !== 1 ? 's' : ''}</Text>
                    </View>
                    {/* Reply rate bar */}
                    <View style={{ marginTop: 10 }}>
                      <View style={{ flexDirection: 'row', justifyContent: 'space-between', marginBottom: 3 }}>
                        <Text style={{ fontSize: 12, color: colors.textSecondary }}>Replied</Text>
                        <Text style={{ fontSize: 12, fontWeight: '700', color: '#007AFF' }}>{s.replied} ({s.reply_rate}%)</Text>
                      </View>
                      <View style={{ height: 6, borderRadius: 3, backgroundColor: colors.surface, overflow: 'hidden' }}>
                        <View style={{ width: `${Math.min(s.reply_rate, 100)}%`, height: 6, backgroundColor: '#007AFF' }} />
                      </View>
                    </View>
                    {/* Sold rate bar */}
                    <View style={{ marginTop: 8 }}>
                      <View style={{ flexDirection: 'row', justifyContent: 'space-between', marginBottom: 3 }}>
                        <Text style={{ fontSize: 12, color: colors.textSecondary }}>Sold</Text>
                        <Text style={{ fontSize: 12, fontWeight: '700', color: '#34C759' }}>{s.sold} ({s.sold_rate}%)</Text>
                      </View>
                      <View style={{ height: 6, borderRadius: 3, backgroundColor: colors.surface, overflow: 'hidden' }}>
                        <View style={{ width: `${Math.min(s.sold_rate, 100)}%`, height: 6, backgroundColor: '#34C759' }} />
                      </View>
                    </View>
                    {(s.cost_per_sale != null || s.cost_per_lead != null) && (
                      <View style={{ flexDirection: 'row', gap: 8, marginTop: 10 }}>
                        {s.cost_per_sale != null && (
                          <View style={{ flex: 1, backgroundColor: '#34C75912', borderRadius: 8, padding: 8, alignItems: 'center' }}>
                            <Text style={{ fontSize: 15, fontWeight: '800', color: '#34C759' }}>{fmtPrice(s.cost_per_sale)}</Text>
                            <Text style={{ fontSize: 10, fontWeight: '600', color: colors.textSecondary, letterSpacing: 0.4 }}>PER SALE</Text>
                          </View>
                        )}
                        {s.cost_per_lead != null && (
                          <View style={{ flex: 1, backgroundColor: `${ACCENT}12`, borderRadius: 8, padding: 8, alignItems: 'center' }}>
                            <Text style={{ fontSize: 15, fontWeight: '800', color: ACCENT }}>{fmtPrice(s.cost_per_lead)}</Text>
                            <Text style={{ fontSize: 10, fontWeight: '600', color: colors.textSecondary, letterSpacing: 0.4 }}>PER LEAD</Text>
                          </View>
                        )}
                        {s.period_cost != null && (
                          <View style={{ flex: 1, backgroundColor: colors.surface, borderRadius: 8, padding: 8, alignItems: 'center' }}>
                            <Text style={{ fontSize: 15, fontWeight: '800', color: colors.text }}>{fmtPrice(s.period_cost)}</Text>
                            <Text style={{ fontSize: 10, fontWeight: '600', color: colors.textSecondary, letterSpacing: 0.4 }}>SPENT</Text>
                          </View>
                        )}
                      </View>
                    )}
                    {s.monthly_cost == null && (
                      <Text style={{ fontSize: 11, color: colors.textSecondary, marginTop: 8 }}>
                        Set a monthly cost on this source (Admin → Lead Sources) to see cost per sale
                      </Text>
                    )}
                    {s.failed > 0 && (
                      <Text style={{ fontSize: 12, color: '#FF3B30', marginTop: 8 }}>{s.failed} failed to send</Text>
                    )}
                  </View>
                ))}
              </>
            )
          )}
        </ScrollView>
      )}
    </SafeAreaView>
  );
}
