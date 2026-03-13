import React, { useState, useEffect, useCallback } from 'react';
import {
  View, Text, TouchableOpacity, StyleSheet, ScrollView,
  ActivityIndicator, TextInput, RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import api from '../../services/api';
import { useThemeStore } from '../../store/themeStore';

interface SOP {
  id: string;
  title: string;
  summary: string;
  department: string;
  category: string;
  difficulty: string;
  estimated_time?: string;
  is_required_reading: boolean;
  steps: any[];
  tags: string[];
}

const DEPARTMENTS = [
  { key: 'all', label: 'All', icon: 'apps' },
  { key: 'sales', label: 'Sales', icon: 'trending-up' },
  { key: 'support', label: 'Support', icon: 'headset' },
  { key: 'onboarding', label: 'Onboarding', icon: 'rocket' },
  { key: 'admin', label: 'Admin', icon: 'settings' },
  { key: 'management', label: 'Management', icon: 'people' },
];

const DIFFICULTY_COLORS: Record<string, string> = {
  beginner: '#34C759',
  intermediate: '#FF9500',
  advanced: '#FF3B30',
};

export default function SOPsPage() {
  const { colors } = useThemeStore();
  const router = useRouter();
  const [sops, setSOPs] = useState<SOP[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [search, setSearch] = useState('');
  const [department, setDepartment] = useState('all');
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const fetchSOPs = useCallback(async () => {
    try {
      const params: Record<string, string> = {};
      if (department !== 'all') params.department = department;
      if (search) params.search = search;
      const query = new URLSearchParams(params).toString();
      const res = await api.get(`/sop${query ? `?${query}` : ''}`);
      setSOPs(Array.isArray(res.data) ? res.data : []);
    } catch {
      setSOPs([]);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [department, search]);

  useEffect(() => { fetchSOPs(); }, [fetchSOPs]);

  const onRefresh = () => { setRefreshing(true); fetchSOPs(); };

  return (
    <SafeAreaView style={[s.container, { backgroundColor: colors.background }]} edges={['top']}>
      <View style={s.header}>
        <TouchableOpacity onPress={() => router.back()} data-testid="sops-back-btn">
          <Ionicons name="chevron-back" size={24} color={colors.text} />
        </TouchableOpacity>
        <Text style={[s.headerTitle, { color: colors.text }]}>SOPs & Guides</Text>
        <View style={{ width: 24 }} />
      </View>

      {/* Search */}
      <View style={[s.searchBar, { backgroundColor: colors.surface }]}>
        <Ionicons name="search" size={18} color={colors.textSecondary} />
        <TextInput
          style={[s.searchInput, { color: colors.text }]}
          placeholder="Search SOPs..."
          placeholderTextColor={colors.textSecondary}
          value={search}
          onChangeText={setSearch}
          onSubmitEditing={fetchSOPs}
          data-testid="sops-search-input"
        />
        {search ? (
          <TouchableOpacity onPress={() => { setSearch(''); }}>
            <Ionicons name="close-circle" size={18} color={colors.textSecondary} />
          </TouchableOpacity>
        ) : null}
      </View>

      {/* Department Filter */}
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={s.filterRow} contentContainerStyle={s.filterContent}>
        {DEPARTMENTS.map(d => (
          <TouchableOpacity
            key={d.key}
            style={[s.filterChip, department === d.key && { backgroundColor: colors.primary || '#007AFF' }]}
            onPress={() => setDepartment(d.key)}
            data-testid={`dept-filter-${d.key}`}
          >
            <Ionicons name={d.icon as any} size={14} color={department === d.key ? '#fff' : colors.textSecondary} />
            <Text style={[s.filterText, { color: department === d.key ? '#fff' : colors.textSecondary }]}>{d.label}</Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      {loading ? (
        <View style={s.center}><ActivityIndicator size="large" color={colors.primary || '#007AFF'} /></View>
      ) : (
        <ScrollView
          style={s.list}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.textSecondary} />}
        >
          {sops.length === 0 ? (
            <View style={s.empty}>
              <Ionicons name="document-text-outline" size={48} color={colors.textTertiary} />
              <Text style={[s.emptyTitle, { color: colors.textSecondary }]}>No SOPs found</Text>
              <Text style={[s.emptySubtitle, { color: colors.textTertiary }]}>
                {search ? 'Try a different search term' : 'SOPs will appear here as they are created'}
              </Text>
            </View>
          ) : (
            sops.map(sop => {
              const isExpanded = expandedId === sop.id;
              return (
                <TouchableOpacity
                  key={sop.id}
                  style={[s.sopCard, { backgroundColor: colors.card }]}
                  onPress={() => setExpandedId(isExpanded ? null : sop.id)}
                  activeOpacity={0.7}
                  data-testid={`sop-card-${sop.id}`}
                >
                  <View style={s.sopHeader}>
                    <View style={s.sopMeta}>
                      {sop.is_required_reading && (
                        <View style={s.requiredBadge}>
                          <Text style={s.requiredText}>Required</Text>
                        </View>
                      )}
                      <View style={[s.diffBadge, { backgroundColor: `${DIFFICULTY_COLORS[sop.difficulty] || '#999'}20` }]}>
                        <Text style={[s.diffText, { color: DIFFICULTY_COLORS[sop.difficulty] || '#999' }]}>
                          {sop.difficulty}
                        </Text>
                      </View>
                      {sop.estimated_time && (
                        <Text style={[s.timeText, { color: colors.textTertiary }]}>
                          <Ionicons name="time-outline" size={12} /> {sop.estimated_time}
                        </Text>
                      )}
                    </View>
                    <Text style={[s.sopTitle, { color: colors.text }]}>{sop.title}</Text>
                    <Text style={[s.sopSummary, { color: colors.textSecondary }]} numberOfLines={isExpanded ? undefined : 2}>
                      {sop.summary}
                    </Text>
                  </View>

                  {isExpanded && sop.steps?.length > 0 && (
                    <View style={s.stepsSection}>
                      <Text style={[s.stepsTitle, { color: colors.text }]}>Steps</Text>
                      {sop.steps.map((step: any, i: number) => (
                        <View key={i} style={s.stepRow}>
                          <View style={[s.stepNumber, { backgroundColor: `${colors.primary || '#007AFF'}20` }]}>
                            <Text style={[s.stepNumText, { color: colors.primary || '#007AFF' }]}>{i + 1}</Text>
                          </View>
                          <View style={s.stepContent}>
                            <Text style={[s.stepTitle, { color: colors.text }]}>{step.title}</Text>
                            <Text style={[s.stepDesc, { color: colors.textSecondary }]}>{step.description}</Text>
                            {step.tip && (
                              <View style={[s.tipBox, { backgroundColor: '#34C75915' }]}>
                                <Ionicons name="bulb-outline" size={14} color="#34C759" />
                                <Text style={[s.tipText, { color: '#34C759' }]}>{step.tip}</Text>
                              </View>
                            )}
                          </View>
                        </View>
                      ))}
                    </View>
                  )}

                  <View style={s.sopFooter}>
                    {sop.tags?.length > 0 && (
                      <View style={s.tagRow}>
                        {sop.tags.slice(0, 3).map(tag => (
                          <View key={tag} style={[s.tag, { backgroundColor: `${colors.textTertiary}20` }]}>
                            <Text style={[s.tagText, { color: colors.textTertiary }]}>{tag}</Text>
                          </View>
                        ))}
                      </View>
                    )}
                    <Ionicons name={isExpanded ? 'chevron-up' : 'chevron-down'} size={18} color={colors.textSecondary} />
                  </View>
                </TouchableOpacity>
              );
            })
          )}
          <View style={{ height: 40 }} />
        </ScrollView>
      )}
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1 },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 12 },
  headerTitle: { fontSize: 18, fontWeight: '700' },
  searchBar: { flexDirection: 'row', alignItems: 'center', marginHorizontal: 16, borderRadius: 10, paddingHorizontal: 12, paddingVertical: 10, gap: 8, marginBottom: 8 },
  searchInput: { flex: 1, fontSize: 15 },
  filterRow: { maxHeight: 44, marginBottom: 8 },
  filterContent: { paddingHorizontal: 16, gap: 8 },
  filterChip: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 12, paddingVertical: 6, borderRadius: 20, backgroundColor: '#ffffff10' },
  filterText: { fontSize: 13, fontWeight: '500' },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  list: { flex: 1, paddingHorizontal: 16 },
  empty: { alignItems: 'center', paddingTop: 80, gap: 8 },
  emptyTitle: { fontSize: 16, fontWeight: '600' },
  emptySubtitle: { fontSize: 14, textAlign: 'center', maxWidth: 280 },
  sopCard: { borderRadius: 12, padding: 16, marginBottom: 10 },
  sopHeader: {},
  sopMeta: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 6 },
  requiredBadge: { backgroundColor: '#FF3B3020', paddingHorizontal: 8, paddingVertical: 2, borderRadius: 4 },
  requiredText: { fontSize: 11, fontWeight: '600', color: '#FF3B30' },
  diffBadge: { paddingHorizontal: 8, paddingVertical: 2, borderRadius: 4 },
  diffText: { fontSize: 11, fontWeight: '600', textTransform: 'capitalize' as any },
  timeText: { fontSize: 12 },
  sopTitle: { fontSize: 16, fontWeight: '600', marginBottom: 4 },
  sopSummary: { fontSize: 14, lineHeight: 20 },
  stepsSection: { marginTop: 12, paddingTop: 12, borderTopWidth: 1, borderTopColor: '#ffffff10' },
  stepsTitle: { fontSize: 14, fontWeight: '600', marginBottom: 10 },
  stepRow: { flexDirection: 'row', gap: 10, marginBottom: 12 },
  stepNumber: { width: 28, height: 28, borderRadius: 14, alignItems: 'center', justifyContent: 'center' },
  stepNumText: { fontSize: 13, fontWeight: '700' },
  stepContent: { flex: 1 },
  stepTitle: { fontSize: 14, fontWeight: '600', marginBottom: 2 },
  stepDesc: { fontSize: 13, lineHeight: 18 },
  tipBox: { flexDirection: 'row', alignItems: 'center', gap: 6, padding: 8, borderRadius: 8, marginTop: 6 },
  tipText: { fontSize: 12, flex: 1 },
  sopFooter: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: 10 },
  tagRow: { flexDirection: 'row', gap: 6 },
  tag: { paddingHorizontal: 8, paddingVertical: 2, borderRadius: 4 },
  tagText: { fontSize: 11 },
});
