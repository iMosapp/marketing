/**
 * Review Management Center
 * ─────────────────────────────────────────────────────────────────
 * Tab 1: PENDING    — internal reviews awaiting approval
 * Tab 2: PUBLISHED  — approved reviews + which pages they're on
 * Tab 3: ONLINE CLICKS — attribution log when customers click review links
 */
import React, { useState, useCallback } from 'react';
import {
  View, Text, StyleSheet, TouchableOpacity, ScrollView,
  ActivityIndicator, RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import { useAuthStore } from '../../store/authStore';
import { useThemeStore } from '../../store/themeStore';
import api from '../../services/api';
import { showAlert } from '../../services/alert';

type Tab = 'pending' | 'published' | 'clicks';

const PAGE_OPTIONS = [
  { key: 'digital_card',  label: 'Digital Card',  icon: 'card-outline' },
  { key: 'landing_page',  label: 'Landing Page',  icon: 'globe-outline' },
  { key: 'link_page',     label: 'Link Page',     icon: 'link-outline' },
  { key: 'showcase',      label: 'Showcase',      icon: 'images-outline' },
];

function Stars({ rating, size = 14 }: { rating: number; size?: number }) {
  return (
    <View style={{ flexDirection: 'row', gap: 2 }}>
      {[1,2,3,4,5].map(i => (
        <Ionicons key={i} name="star" size={size}
          color={i <= rating ? '#FFD60A' : '#3A3A3C'} />
      ))}
    </View>
  );
}

export default function ReviewManagementScreen() {
  const { colors } = useThemeStore();
  const s = styles(colors);
  const router = useRouter();
  const { user } = useAuthStore();
  const [tab, setTab] = useState<Tab>('pending');
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [processing, setProcessing] = useState<string | null>(null);

  // Data
  const [pending, setPending]     = useState<any[]>([]);
  const [published, setPublished] = useState<any[]>([]);
  const [clicks, setClicks]       = useState<any[]>([]);
  const [summary, setSummary]     = useState<any>({});

  useFocusEffect(useCallback(() => { loadAll(); }, [user?._id]));

  const loadAll = async () => {
    if (!user?._id) return;
    setLoading(true);
    try {
      const [pendRes, attrRes] = await Promise.all([
        api.get(`/p/reviews/pending/${user._id}`),
        api.get(`/review/attribution/${user._id}`),
      ]);
      setPending(pendRes.data || []);
      const attr = attrRes.data || {};
      setPublished((attr.internal_reviews || []).filter((r: any) => r.approved));
      setClicks(attr.online_clicks || []);
      setSummary(attr.summary || {});
    } catch (e) {
      console.error('Review load error', e);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const approve = async (reviewId: string, pages: string[]) => {
    setProcessing(reviewId);
    try {
      await api.patch(`/review/reviews/${reviewId}/publish`, { pages });
      setPending(p => p.filter(r => r.id !== reviewId));
      await loadAll(); // refresh published tab
    } catch { showAlert('Error', 'Failed to approve review'); }
    setProcessing(null);
  };

  const reject = async (reviewId: string) => {
    showAlert('Reject Review', 'Remove this review? This cannot be undone.', async () => {
      setProcessing(reviewId);
      try {
        await api.post(`/p/reviews/reject/${reviewId}`);
        setPending(p => p.filter(r => r.id !== reviewId));
      } catch { showAlert('Error', 'Failed to reject review'); }
      setProcessing(null);
    });
  };

  const togglePage = async (reviewId: string, currentPages: string[], pageKey: string) => {
    const newPages = currentPages.includes(pageKey)
      ? currentPages.filter(p => p !== pageKey)
      : [...currentPages, pageKey];
    try {
      await api.patch(`/review/reviews/${reviewId}/publish`, { pages: newPages });
      setPublished(prev => prev.map(r =>
        r.id === reviewId ? { ...r, publish_to: newPages } : r
      ));
    } catch { showAlert('Error', 'Failed to update review'); }
  };

  const fmtDate = (iso: string) => {
    if (!iso) return '';
    const d = new Date(iso);
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
  };

  // ── RENDER ──────────────────────────────────────────────────────────────────
  const renderPending = () => (
    pending.length === 0
      ? <View style={s.empty}>
          <Ionicons name="checkmark-circle" size={56} color={colors.textTertiary} />
          <Text style={s.emptyTitle}>All caught up!</Text>
          <Text style={s.emptyBody}>No reviews waiting for approval.</Text>
        </View>
      : pending.map((r) => (
        <View key={r.id} style={s.card}>
          <View style={s.cardHeader}>
            <View style={{ flex: 1 }}>
              <Text style={s.customerName}>{r.customer_name || 'Anonymous'}</Text>
              {r.customer_phone ? <Text style={s.meta}>{r.customer_phone}</Text> : null}
              <Text style={s.meta}>{fmtDate(r.created_at)}</Text>
            </View>
            <Stars rating={r.rating} size={16} />
          </View>
          {r.text ? <Text style={s.reviewText}>"{r.text}"</Text> : null}

          <Text style={s.publishLabel}>Publish to:</Text>
          <View style={s.pageRow}>
            {PAGE_OPTIONS.map(p => (
              <TouchableOpacity
                key={p.key}
                style={[s.pageChip, { borderColor: '#C9A96260', backgroundColor: colors.surface }]}
                onPress={() => approve(r.id, [p.key])}
              >
                <Ionicons name={p.icon as any} size={14} color={colors.textSecondary} />
                <Text style={[s.pageChipText, { color: colors.textSecondary }]}>{p.label}</Text>
              </TouchableOpacity>
            ))}
            <TouchableOpacity
              style={[s.pageChip, { borderColor: '#C9A962', backgroundColor: '#C9A96220' }]}
              onPress={() => approve(r.id, PAGE_OPTIONS.map(p => p.key))}
            >
              <Ionicons name="globe" size={14} color="#C9A962" />
              <Text style={[s.pageChipText, { color: '#C9A962' }]}>All Pages</Text>
            </TouchableOpacity>
          </View>

          <View style={s.btnRow}>
            <TouchableOpacity style={s.rejectBtn} onPress={() => reject(r.id)}
              disabled={processing === r.id}>
              <Ionicons name="trash-outline" size={18} color="#FF3B30" />
              <Text style={s.rejectTxt}>Remove</Text>
            </TouchableOpacity>
            {processing === r.id && <ActivityIndicator size="small" color="#C9A962" />}
          </View>
        </View>
      ))
  );

  const renderPublished = () => (
    published.length === 0
      ? <View style={s.empty}>
          <Ionicons name="star" size={56} color={colors.textTertiary} />
          <Text style={s.emptyTitle}>No published reviews yet</Text>
          <Text style={s.emptyBody}>Approve pending reviews to publish them.</Text>
        </View>
      : published.map((r) => {
        const pages: string[] = Array.isArray(r.publish_to)
          ? r.publish_to
          : r.publish_to
          ? [r.publish_to]
          : PAGE_OPTIONS.map(p => p.key); // legacy: show everywhere

        return (
          <View key={r.id || r._id} style={s.card}>
            <View style={s.cardHeader}>
              <View style={{ flex: 1 }}>
                <Text style={s.customerName}>{r.customer_name || 'Anonymous'}</Text>
                <Text style={s.meta}>{fmtDate(r.created_at)}</Text>
              </View>
              <Stars rating={r.rating} size={14} />
            </View>
            {(r.text_review || r.text)
              ? <Text style={s.reviewText}>"{r.text_review || r.text}"</Text>
              : null}

            <Text style={s.publishLabel}>Visible on:</Text>
            <View style={s.pageRow}>
              {PAGE_OPTIONS.map(p => {
                const active = pages.includes(p.key);
                return (
                  <TouchableOpacity key={p.key}
                    style={[s.pageChip, active
                      ? { borderColor: '#34C759', backgroundColor: '#34C75920' }
                      : { borderColor: colors.border, backgroundColor: colors.surface }
                    ]}
                    onPress={() => togglePage(r.id || r._id, pages, p.key)}
                  >
                    <Ionicons name={p.icon as any} size={13}
                      color={active ? '#34C759' : colors.textTertiary} />
                    <Text style={[s.pageChipText,
                      { color: active ? '#34C759' : colors.textTertiary }
                    ]}>{p.label}</Text>
                  </TouchableOpacity>
                );
              })}
            </View>
          </View>
        );
      })
  );

  const renderClicks = () => (
    clicks.length === 0
      ? <View style={s.empty}>
          <Ionicons name="open" size={56} color={colors.textTertiary} />
          <Text style={s.emptyTitle}>No clicks recorded yet</Text>
          <Text style={s.emptyBody}>When customers click your Google, Facebook, or Yelp review links, they'll appear here with attribution.</Text>
        </View>
      : clicks.map((c, i) => (
        <View key={c.id || i} style={[s.card, { paddingVertical: 12 }]}>
          <View style={s.cardHeader}>
            <View style={[s.platformBadge, { backgroundColor: platformColor(c.platform) + '20' }]}>
              <Ionicons name={platformIcon(c.platform) as any} size={18}
                color={platformColor(c.platform)} />
            </View>
            <View style={{ flex: 1, marginLeft: 10 }}>
              <Text style={s.customerName}>
                {c.customer_name || 'Anonymous'} clicked {platformLabel(c.platform)}
              </Text>
              {c.customer_phone
                ? <Text style={s.meta}>{c.customer_phone}</Text>
                : null}
              <Text style={s.meta}>{fmtDate(c.created_at)}</Text>
            </View>
          </View>
        </View>
      ))
  );

  const TABS: { key: Tab; label: string; count?: number }[] = [
    { key: 'pending',   label: 'Pending',   count: pending.length },
    { key: 'published', label: 'Published', count: published.length },
    { key: 'clicks',    label: 'Clicks',    count: clicks.length },
  ];

  return (
    <SafeAreaView style={s.container} edges={['top']}>
      {/* Header */}
      <View style={s.header}>
        <TouchableOpacity onPress={() => router.back()} style={s.back}>
          <Ionicons name="chevron-back" size={28} color="#007AFF" />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={s.title}>Review Center</Text>
          <Text style={s.subtitle}>
            {summary.total_internal || 0} reviews · {summary.total_clicks || 0} link clicks
          </Text>
        </View>
      </View>

      {/* Tabs */}
      <View style={s.tabBar}>
        {TABS.map(t => (
          <TouchableOpacity key={t.key} style={[s.tabBtn, tab === t.key && s.tabBtnActive]}
            onPress={() => setTab(t.key)}>
            <Text style={[s.tabTxt, tab === t.key && s.tabTxtActive]}>{t.label}</Text>
            {(t.count || 0) > 0 && (
              <View style={[s.tabBadge, { backgroundColor: tab === t.key ? '#C9A962' : colors.surface }]}>
                <Text style={[s.tabBadgeTxt, { color: tab === t.key ? '#000' : colors.textSecondary }]}>
                  {t.count}
                </Text>
              </View>
            )}
          </TouchableOpacity>
        ))}
      </View>

      {loading
        ? <ActivityIndicator size="large" color="#C9A962" style={{ marginTop: 60 }} />
        : (
          <ScrollView
            contentContainerStyle={s.scroll}
            refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); loadAll(); }} />}
          >
            {tab === 'pending'   && renderPending()}
            {tab === 'published' && renderPublished()}
            {tab === 'clicks'    && renderClicks()}
          </ScrollView>
        )
      }
    </SafeAreaView>
  );
}

// ── Helpers ──────────────────────────────────────────────────────────────────
function platformLabel(p: string) {
  return { google: 'Google', facebook: 'Facebook', yelp: 'Yelp', zillow: 'Zillow' }[p] || p;
}
function platformIcon(p: string): string {
  return { google: 'logo-google', facebook: 'logo-facebook', yelp: 'star', zillow: 'home' }[p] || 'open';
}
function platformColor(p: string): string {
  return { google: '#4285F4', facebook: '#1877F2', yelp: '#FF1A1A', zillow: '#006AFF' }[p] || '#8E8E93';
}

// ── Styles ────────────────────────────────────────────────────────────────────
const styles = (colors: any) => StyleSheet.create({
  container:   { flex: 1, backgroundColor: colors.bg },
  header:      { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 12 },
  back:        { marginRight: 8 },
  title:       { fontSize: 20, fontWeight: '800', color: colors.text },
  subtitle:    { fontSize: 13, color: colors.textSecondary, marginTop: 1 },
  tabBar:      { flexDirection: 'row', borderBottomWidth: 1, borderBottomColor: colors.border, paddingHorizontal: 16, gap: 6 },
  tabBtn:      { flexDirection: 'row', alignItems: 'center', paddingVertical: 12, paddingHorizontal: 4, gap: 6, borderBottomWidth: 2, borderBottomColor: 'transparent', marginBottom: -1 },
  tabBtnActive:{ borderBottomColor: '#C9A962' },
  tabTxt:      { fontSize: 15, fontWeight: '600', color: colors.textSecondary },
  tabTxtActive:{ color: '#C9A962' },
  tabBadge:    { borderRadius: 10, paddingHorizontal: 6, paddingVertical: 1 },
  tabBadgeTxt: { fontSize: 12, fontWeight: '700' },
  scroll:      { padding: 16, paddingBottom: 40 },
  card:        { backgroundColor: colors.card, borderRadius: 16, padding: 16, marginBottom: 12, borderWidth: 1, borderColor: colors.border },
  cardHeader:  { flexDirection: 'row', alignItems: 'flex-start', marginBottom: 8 },
  customerName:{ fontSize: 16, fontWeight: '700', color: colors.text },
  meta:        { fontSize: 13, color: colors.textTertiary, marginTop: 2 },
  reviewText:  { fontSize: 15, color: colors.text, fontStyle: 'italic', lineHeight: 22, marginBottom: 12 },
  publishLabel:{ fontSize: 12, fontWeight: '700', color: colors.textSecondary, textTransform: 'uppercase', letterSpacing: 0.8, marginBottom: 8 },
  pageRow:     { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginBottom: 10 },
  pageChip:    { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 10, paddingVertical: 6, borderRadius: 20, borderWidth: 1 },
  pageChipText:{ fontSize: 13, fontWeight: '500' },
  btnRow:      { flexDirection: 'row', alignItems: 'center', gap: 12, marginTop: 4 },
  rejectBtn:   { flexDirection: 'row', alignItems: 'center', gap: 4 },
  rejectTxt:   { fontSize: 14, color: '#FF3B30', fontWeight: '600' },
  platformBadge:{ width: 40, height: 40, borderRadius: 12, justifyContent: 'center', alignItems: 'center' },
  empty:       { alignItems: 'center', paddingTop: 60, gap: 10 },
  emptyTitle:  { fontSize: 18, fontWeight: '700', color: colors.text },
  emptyBody:   { fontSize: 15, color: colors.textSecondary, textAlign: 'center', maxWidth: 280 },
});
