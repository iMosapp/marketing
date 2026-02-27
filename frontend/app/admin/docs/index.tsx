import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  FlatList,
  ActivityIndicator,
  RefreshControl,
  TextInput,
  ScrollView,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import { useAuthStore } from '../../../store/authStore';
import api from '../../../services/api';

const CATEGORY_COLORS: Record<string, string> = {
  security: '#FF3B30',
  company_policy: '#5856D6',
  legal: '#007AFF',
  training: '#34C759',
  integrations: '#FF9500',
};

const CATEGORY_ICONS: Record<string, string> = {
  security: 'shield-checkmark',
  company_policy: 'business',
  legal: 'document-text',
  training: 'school',
  integrations: 'git-network',
};

const CATEGORY_LABELS: Record<string, string> = {
  security: 'Cyber Security',
  company_policy: 'Company Policy',
  legal: 'Legal',
  training: 'Training',
  integrations: 'Integrations',
};

export default function DocsHubScreen() {
  const router = useRouter();
  const user = useAuthStore((state) => state.user);

  const [docs, setDocs] = useState<any[]>([]);
  const [categories, setCategories] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [search, setSearch] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);

  useFocusEffect(
    useCallback(() => {
      loadData();
    }, [selectedCategory, search])
  );

  const loadData = async () => {
    try {
      const headers = { 'X-User-ID': user?._id };

      const catRes = await api.get('/docs/categories', { headers });
      setCategories(catRes.data);

      let url = '/docs/';
      const params: string[] = [];
      if (selectedCategory) params.push(`category=${selectedCategory}`);
      if (search) params.push(`search=${encodeURIComponent(search)}`);
      if (params.length) url += '?' + params.join('&');

      const docRes = await api.get(url, { headers });
      setDocs(docRes.data);
    } catch (error) {
      console.error('Failed to load docs:', error);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const seedDocs = async () => {
    try {
      const headers = { 'X-User-ID': user?._id };
      await api.post('/docs/seed', {}, { headers });
      loadData();
    } catch (error) {
      console.error('Failed to seed docs:', error);
    }
  };

  const onRefresh = () => {
    setRefreshing(true);
    loadData();
  };

  const groupedDocs = docs.reduce((acc: Record<string, any[]>, doc) => {
    const cat = doc.category || 'other';
    if (!acc[cat]) acc[cat] = [];
    acc[cat].push(doc);
    return acc;
  }, {});

  const renderDoc = ({ item }: { item: any }) => {
    const color = CATEGORY_COLORS[item.category] || '#8E8E93';
    return (
      <TouchableOpacity
        style={styles.docCard}
        onPress={() => router.push(`/admin/docs/${item._id}`)}
        data-testid={`doc-item-${item._id}`}
      >
        <View style={[styles.docIcon, { backgroundColor: color + '20' }]}>
          <Ionicons
            name={(item.icon || CATEGORY_ICONS[item.category] || 'document') as any}
            size={22}
            color={color}
          />
        </View>
        <View style={styles.docContent}>
          <Text style={styles.docTitle} numberOfLines={1}>{item.title}</Text>
          <Text style={styles.docSummary} numberOfLines={2}>{item.summary}</Text>
          <View style={styles.docMeta}>
            {item.version && (
              <View style={styles.versionBadge}>
                <Text style={styles.versionText}>v{item.version}</Text>
              </View>
            )}
            <Text style={styles.metaText}>
              {CATEGORY_LABELS[item.category] || item.category}
            </Text>
          </View>
        </View>
        <Ionicons name="chevron-forward" size={20} color="#8E8E93" />
      </TouchableOpacity>
    );
  };

  const renderCategoryHeader = (category: string) => {
    const color = CATEGORY_COLORS[category] || '#8E8E93';
    return (
      <View style={styles.categoryHeader}>
        <View style={[styles.categoryIcon, { backgroundColor: color + '20' }]}>
          <Ionicons
            name={(CATEGORY_ICONS[category] || 'document') as any}
            size={16}
            color={color}
          />
        </View>
        <Text style={styles.categoryTitle}>
          {CATEGORY_LABELS[category] || category}
        </Text>
        <Text style={styles.categoryCount}>
          {groupedDocs[category]?.length || 0}
        </Text>
      </View>
    );
  };

  if (loading) {
    return (
      <SafeAreaView style={styles.container} edges={['top']}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#007AFF" />
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="chevron-back" size={28} color="#007AFF" />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Company Docs</Text>
        <View style={{ width: 40 }} />
      </View>

      {/* Search */}
      <View style={styles.searchContainer}>
        <Ionicons name="search" size={20} color="#8E8E93" />
        <TextInput
          style={styles.searchInput}
          placeholder="Search documents..."
          placeholderTextColor="#8E8E93"
          value={search}
          onChangeText={setSearch}
          data-testid="docs-search-input"
        />
        {search.length > 0 && (
          <TouchableOpacity onPress={() => setSearch('')}>
            <Ionicons name="close-circle" size={20} color="#8E8E93" />
          </TouchableOpacity>
        )}
      </View>

      {/* Category Filter */}
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={styles.filterContainer}
      >
        <TouchableOpacity
          style={[styles.filterChip, selectedCategory === null && styles.filterChipActive]}
          onPress={() => setSelectedCategory(null)}
          data-testid="docs-filter-all"
        >
          <Text style={[styles.filterChipText, selectedCategory === null && styles.filterChipTextActive]}>
            All
          </Text>
        </TouchableOpacity>
        {categories.map((cat: any) => (
          <TouchableOpacity
            key={cat.id}
            style={[
              styles.filterChip,
              selectedCategory === cat.id && styles.filterChipActive,
              selectedCategory === cat.id && { backgroundColor: CATEGORY_COLORS[cat.id] || '#007AFF' },
            ]}
            onPress={() => setSelectedCategory(selectedCategory === cat.id ? null : cat.id)}
            data-testid={`docs-filter-${cat.id}`}
          >
            <Ionicons
              name={cat.icon as any}
              size={14}
              color={selectedCategory === cat.id ? '#FFF' : CATEGORY_COLORS[cat.id] || '#8E8E93'}
              style={{ marginRight: 6 }}
            />
            <Text style={[
              styles.filterChipText,
              selectedCategory === cat.id && styles.filterChipTextActive,
            ]}>
              {cat.name}
            </Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      {/* Doc List */}
      {docs.length === 0 ? (
        <View style={styles.emptyContainer}>
          <Ionicons name="folder-open-outline" size={64} color="#2C2C2E" />
          <Text style={styles.emptyText}>No documents found</Text>
          <Text style={styles.emptySubtext}>Seed initial documents to get started</Text>
          <TouchableOpacity style={styles.seedButton} onPress={seedDocs} data-testid="docs-seed-btn">
            <Ionicons name="add-circle" size={20} color="#000" />
            <Text style={styles.seedButtonText}>Load Documents</Text>
          </TouchableOpacity>
        </View>
      ) : (
        <FlatList
          data={Object.keys(groupedDocs)}
          renderItem={({ item: category }) => (
            <View>
              {renderCategoryHeader(category)}
              {groupedDocs[category].map((doc: any) => (
                <View key={doc._id}>
                  {renderDoc({ item: doc })}
                </View>
              ))}
            </View>
          )}
          keyExtractor={(item) => item}
          contentContainerStyle={styles.listContent}
          refreshControl={
            <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#007AFF" />
          }
        />
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#000' },
  loadingContainer: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#1C1C1E',
  },
  backButton: { padding: 4, width: 40 },
  headerTitle: { fontSize: 18, fontWeight: '600', color: '#FFF' },
  searchContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1C1C1E',
    margin: 16,
    marginBottom: 8,
    paddingHorizontal: 12,
    borderRadius: 10,
  },
  searchInput: {
    flex: 1,
    paddingVertical: 12,
    paddingHorizontal: 8,
    fontSize: 16,
    color: '#FFF',
  },
  filterContainer: {
    paddingHorizontal: 16,
    paddingBottom: 12,
    paddingTop: 4,
    flexDirection: 'row',
    alignItems: 'center',
  },
  filterChip: {
    paddingHorizontal: 18,
    paddingVertical: 10,
    backgroundColor: '#1C1C1E',
    borderRadius: 20,
    marginRight: 8,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
  },
  filterChipActive: { backgroundColor: '#007AFF' },
  filterChipText: { fontSize: 13, fontWeight: '500', color: '#8E8E93' },
  filterChipTextActive: { color: '#FFF' },
  listContent: { paddingHorizontal: 16, paddingBottom: 32 },
  categoryHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 20,
    marginBottom: 12,
  },
  categoryIcon: {
    width: 28,
    height: 28,
    borderRadius: 6,
    justifyContent: 'center',
    alignItems: 'center',
  },
  categoryTitle: {
    fontSize: 13,
    fontWeight: '600',
    color: '#8E8E93',
    marginLeft: 8,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  categoryCount: { fontSize: 13, color: '#6E6E73', marginLeft: 'auto' },
  docCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 16,
    marginBottom: 8,
  },
  docIcon: {
    width: 44,
    height: 44,
    borderRadius: 10,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 14,
  },
  docContent: { flex: 1 },
  docTitle: { fontSize: 16, fontWeight: '600', color: '#FFF', marginBottom: 4 },
  docSummary: { fontSize: 13, color: '#8E8E93', lineHeight: 18, marginBottom: 8 },
  docMeta: { flexDirection: 'row', alignItems: 'center' },
  versionBadge: {
    backgroundColor: '#007AFF20',
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 4,
    marginRight: 8,
  },
  versionText: { fontSize: 10, fontWeight: '600', color: '#007AFF' },
  metaText: { fontSize: 12, color: '#6E6E73' },
  emptyContainer: { flex: 1, alignItems: 'center', justifyContent: 'center', paddingBottom: 60 },
  emptyText: { color: '#8E8E93', fontSize: 18, fontWeight: '600', marginTop: 16 },
  emptySubtext: { color: '#6E6E73', fontSize: 14, marginTop: 6 },
  seedButton: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#007AFF',
    paddingHorizontal: 24,
    paddingVertical: 12,
    borderRadius: 10,
    marginTop: 20,
    gap: 8,
  },
  seedButtonText: { color: '#000', fontSize: 16, fontWeight: '600' },
});
