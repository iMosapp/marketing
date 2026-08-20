import React, { useState, useCallback } from 'react';
import {
  View, Text, TouchableOpacity, ScrollView, ActivityIndicator, RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import { useThemeStore } from '../../store/themeStore';
import { useAuthStore } from '../../store/authStore';
import api from '../../services/api';
import { showSimpleAlert } from '../../services/alert';

const FILTERS = [
  { key: 'all', label: 'All' },
  { key: 'open', label: 'Open' },
  { key: 'in_progress', label: 'In Progress' },
  { key: 'resolved', label: 'Resolved' },
];

const STATUS_META: Record<string, { label: string; color: string }> = {
  open: { label: 'OPEN', color: '#FF3B30' },
  in_progress: { label: 'IN PROGRESS', color: '#FF9500' },
  resolved: { label: 'RESOLVED', color: '#34C759' },
};

const CATEGORY_META: Record<string, { label: string; icon: string; color: string }> = {
  bug: { label: 'Bug', icon: 'bug-outline', color: '#FF3B30' },
  suggestion: { label: 'Suggestion', icon: 'bulb-outline', color: '#FF9500' },
  other: { label: 'Other', icon: 'chatbox-ellipses-outline', color: '#007AFF' },
};

function timeAgo(iso: string) {
  try {
    const diffMin = Math.floor((Date.now() - new Date(iso).getTime()) / 60000);
    if (diffMin < 1) return 'just now';
    if (diffMin < 60) return `${diffMin}m ago`;
    const hrs = Math.floor(diffMin / 60);
    if (hrs < 24) return `${hrs}h ago`;
    return `${Math.floor(hrs / 24)}d ago`;
  } catch { return iso; }
}

export default function AdminBugReportsPage() {
  const { colors } = useThemeStore();
  const { user } = useAuthStore();
  const router = useRouter();
  const [reports, setReports] = useState<any[]>([]);
  const [counts, setCounts] = useState<any>({});
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all');
  const [refreshing, setRefreshing] = useState(false);
  const [loadError, setLoadError] = useState(false);

  const isSuperAdmin = user?.role === 'super_admin';

  const fetchReports = useCallback(async () => {
    try {
      const res = await api.get(`/bug-reports?status=${filter}&limit=200`);
      setReports(res.data.reports || []);
      setCounts(res.data.counts || {});
      setLoadError(false);
    } catch (e) {
      console.error('Failed to fetch bug reports:', e);
      setLoadError(true);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [filter]);

  useFocusEffect(useCallback(() => { setLoading(true); fetchReports(); }, [fetchReports]));

  const setStatus = async (id: string, status: string) => {
    try {
      await api.patch(`/bug-reports/${id}/status`, { status });
      fetchReports();
    } catch {
      showSimpleAlert('Error', 'Could not update the report status. Please try again.');
    }
  };

  if (!isSuperAdmin) {
    return (
      <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', padding: 32 }} data-testid="bug-reports-access-denied">
          <Ionicons name="lock-closed" size={44} color="#FF9500" />
          <Text style={{ fontSize: 20, fontWeight: '700', color: colors.text, marginTop: 16 }}>Access Denied</Text>
          <Text style={{ fontSize: 15, color: colors.textSecondary, textAlign: 'center', marginTop: 8 }}>
            Bug reports are only visible to super admins.
          </Text>
          <TouchableOpacity
            style={{ backgroundColor: colors.card, borderRadius: 12, paddingVertical: 12, paddingHorizontal: 32, marginTop: 24 }}
            onPress={() => router.back()}
          >
            <Text style={{ fontSize: 16, fontWeight: '600', color: colors.text }}>Go Back</Text>
          </TouchableOpacity>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={['top']}>
      {/* Header */}
      <View style={{ flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 12, gap: 12 }}>
        <TouchableOpacity onPress={() => router.back()} data-testid="bug-reports-back-btn">
          <Ionicons name="chevron-back" size={26} color={colors.text} />
        </TouchableOpacity>
        <Text style={{ fontSize: 20, fontWeight: '800', color: colors.text, flex: 1 }} numberOfLines={1} maxFontSizeMultiplier={1.15}>Bug Reports</Text>
      </View>

      {/* Filters */}
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ maxHeight: 44 }} contentContainerStyle={{ paddingHorizontal: 16, gap: 8 }}>
        {FILTERS.map(f => {
          const active = filter === f.key;
          const count = f.key === 'all'
            ? (counts.open || 0) + (counts.in_progress || 0) + (counts.resolved || 0)
            : counts[f.key] || 0;
          return (
            <TouchableOpacity
              key={f.key}
              style={{
                paddingHorizontal: 14, height: 34, borderRadius: 17, justifyContent: 'center',
                backgroundColor: active ? '#007AFF' : colors.card,
              }}
              onPress={() => setFilter(f.key)}
              data-testid={`bug-filter-${f.key}`}
            >
              <Text style={{ fontSize: 14, fontWeight: '600', color: active ? '#FFF' : colors.textSecondary }} numberOfLines={1}>
                {f.label}{count > 0 ? ` (${count})` : ''}
              </Text>
            </TouchableOpacity>
          );
        })}
      </ScrollView>

      {loading ? (
        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}>
          <ActivityIndicator size="large" color="#007AFF" />
        </View>
      ) : (
        <ScrollView
          style={{ flex: 1 }}
          contentContainerStyle={{ padding: 16, paddingBottom: 40, gap: 12 }}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); fetchReports(); }} tintColor={colors.textSecondary} />}
        >
          {loadError ? (
            <View style={{ alignItems: 'center', paddingTop: 60 }} data-testid="bug-reports-error">
              <Ionicons name="cloud-offline-outline" size={44} color={colors.textSecondary} />
              <Text style={{ fontSize: 16, color: colors.textSecondary, marginTop: 10 }}>Could not load reports</Text>
              <TouchableOpacity
                style={{ backgroundColor: '#007AFF20', borderRadius: 10, paddingVertical: 10, paddingHorizontal: 24, marginTop: 16 }}
                onPress={() => { setLoading(true); fetchReports(); }}
                data-testid="bug-reports-retry-btn"
              >
                <Text style={{ fontSize: 15, fontWeight: '600', color: '#007AFF' }}>Retry</Text>
              </TouchableOpacity>
            </View>
          ) : reports.length === 0 ? (
            <View style={{ alignItems: 'center', paddingTop: 60 }}>
              <Ionicons name="checkmark-circle-outline" size={44} color={colors.textSecondary} />
              <Text style={{ fontSize: 16, color: colors.textSecondary, marginTop: 10 }}>No bug reports</Text>
            </View>
          ) : (
            reports.map((r: any) => {
              const st = STATUS_META[r.status] || STATUS_META.open;
              const cat = CATEGORY_META[r.category] || CATEGORY_META.other;
              return (
                <View key={r._id} style={{ backgroundColor: colors.card, borderRadius: 14, padding: 16 }} data-testid={`bug-report-${r._id}`}>
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: `${cat.color}18`, paddingVertical: 3, paddingHorizontal: 8, borderRadius: 6 }}>
                      <Ionicons name={cat.icon as any} size={12} color={cat.color} />
                      <Text style={{ fontSize: 11, fontWeight: '700', color: cat.color }}>{cat.label}</Text>
                    </View>
                    <View style={{ backgroundColor: `${st.color}18`, paddingVertical: 3, paddingHorizontal: 8, borderRadius: 6 }}>
                      <Text style={{ fontSize: 11, fontWeight: '700', color: st.color }}>{st.label}</Text>
                    </View>
                    <Text style={{ fontSize: 12, color: colors.textSecondary, marginLeft: 'auto' }}>{timeAgo(r.created_at)}</Text>
                  </View>
                  <Text style={{ fontSize: 15, color: colors.text, lineHeight: 21, marginBottom: 10 }}>{r.description}</Text>
                  <Text style={{ fontSize: 13, color: colors.textSecondary, marginBottom: 12 }}>
                    {r.user_name}{r.user_email ? ` · ${r.user_email}` : ''}{r.platform ? ` · ${r.platform}` : ''}
                  </Text>
                  <View style={{ flexDirection: 'row', gap: 8 }}>
                    {r.status === 'open' && (
                      <TouchableOpacity
                        style={{ backgroundColor: '#FF950020', paddingVertical: 8, paddingHorizontal: 16, borderRadius: 8 }}
                        onPress={() => setStatus(r._id, 'in_progress')}
                        data-testid={`bug-start-${r._id}`}
                      >
                        <Text style={{ fontSize: 13, fontWeight: '700', color: '#FF9500' }}>Start Working</Text>
                      </TouchableOpacity>
                    )}
                    {r.status !== 'resolved' && (
                      <TouchableOpacity
                        style={{ backgroundColor: '#34C75920', paddingVertical: 8, paddingHorizontal: 16, borderRadius: 8 }}
                        onPress={() => setStatus(r._id, 'resolved')}
                        data-testid={`bug-resolve-${r._id}`}
                      >
                        <Text style={{ fontSize: 13, fontWeight: '700', color: '#34C759' }}>Resolve</Text>
                      </TouchableOpacity>
                    )}
                    {r.status === 'resolved' && (
                      <TouchableOpacity
                        style={{ backgroundColor: '#FF3B3020', paddingVertical: 8, paddingHorizontal: 16, borderRadius: 8 }}
                        onPress={() => setStatus(r._id, 'open')}
                        data-testid={`bug-reopen-${r._id}`}
                      >
                        <Text style={{ fontSize: 13, fontWeight: '700', color: '#FF3B30' }}>Reopen</Text>
                      </TouchableOpacity>
                    )}
                  </View>
                </View>
              );
            })
          )}
        </ScrollView>
      )}
    </SafeAreaView>
  );
}
