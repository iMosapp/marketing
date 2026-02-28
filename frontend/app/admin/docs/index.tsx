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
  operations: '#00C7BE',
  signed: '#34C759',
  security: '#FF3B30',
  company_policy: '#5856D6',
  legal: '#007AFF',
  training: '#34C759',
  integrations: '#FF9500',
};

const CATEGORY_ICONS: Record<string, string> = {
  operations: 'book',
  signed: 'checkmark-done-circle',
  security: 'shield-checkmark',
  company_policy: 'business',
  legal: 'document-text',
  training: 'school',
  integrations: 'git-network',
};

const CATEGORY_LABELS: Record<string, string> = {
  operations: 'Operations Manual',
  signed: 'Signed Documents',
  security: 'Cyber Security',
  company_policy: 'Company Policy',
  legal: 'Legal',
  training: 'Training',
  integrations: 'Integrations',
};

const CATEGORY_DESCRIPTIONS: Record<string, string> = {
  operations: 'Standard procedures & guidelines',
  signed: 'NDAs, agreements & contracts',
  security: 'Cybersecurity policies & protocols',
  company_policy: 'Internal policies & handbooks',
  legal: 'Legal documents & compliance',
  training: 'Training materials & resources',
  integrations: 'API docs & integration guides',
};

export default function DocsHubScreen() {
  const router = useRouter();
  const user = useAuthStore((state) => state.user);

  const [docs, setDocs] = useState<any[]>([]);
  const [signedDocs, setSignedDocs] = useState<any[]>([]);
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

      // If "Signed Documents" is selected, fetch from signed-documents endpoint
      if (selectedCategory === 'signed') {
        const signedRes = await api.get('/docs/signed-documents', { headers });
        setSignedDocs(signedRes.data);
        setDocs([]);
      } else {
        setSignedDocs([]);
        let url = '/docs/';
        const params: string[] = [];
        if (selectedCategory) params.push(`category=${selectedCategory}`);
        if (search) params.push(`search=${encodeURIComponent(search)}`);
        if (params.length) url += '?' + params.join('&');

        const docRes = await api.get(url, { headers });

        if (docRes.data.length === 0 && !selectedCategory && !search) {
          try {
            await api.post('/docs/seed', {}, { headers });
            const seededRes = await api.get('/docs/', { headers });
            setDocs(seededRes.data);
          } catch {
            setDocs([]);
          }
        } else {
          setDocs(docRes.data);
        }
      }
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
    const isRestricted = !!item.required_role;
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
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
            <Text style={styles.docTitle} numberOfLines={1}>{item.title}</Text>
            {isRestricted && (
              <View style={{ backgroundColor: '#FF3B3020', paddingHorizontal: 6, paddingVertical: 2, borderRadius: 4 }}>
                <Ionicons name="lock-closed" size={10} color="#FF3B30" />
              </View>
            )}
          </View>
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
    const count = groupedDocs[category]?.length || 0;
    return (
      <View style={styles.categoryCard} data-testid={`category-header-${category}`}>
        <View style={[styles.categoryCardIcon, { backgroundColor: color + '15' }]}>
          <Ionicons
            name={(CATEGORY_ICONS[category] || 'document') as any}
            size={22}
            color={color}
          />
        </View>
        <View style={styles.categoryCardContent}>
          <Text style={styles.categoryCardTitle}>
            {CATEGORY_LABELS[category] || category}
          </Text>
          <Text style={styles.categoryCardDescription}>
            {CATEGORY_DESCRIPTIONS[category] || `${count} document${count !== 1 ? 's' : ''}`}
          </Text>
        </View>
        <View style={[styles.categoryCardBadge, { backgroundColor: color + '20' }]}>
          <Text style={[styles.categoryCardBadgeText, { color }]}>{count}</Text>
        </View>
      </View>
    );
  };

  const TYPE_COLORS: Record<string, string> = {
    nda: '#007AFF',
    partner_agreement: '#5856D6',
    quote: '#FF9500',
    referral_agreement: '#00C7BE',
    contract: '#FF3B30',
  };

  const TYPE_ICONS: Record<string, string> = {
    nda: 'lock-closed',
    partner_agreement: 'handshake-outline',
    quote: 'receipt',
    referral_agreement: 'people',
    contract: 'document-attach',
  };

  const renderSignedDoc = (item: any) => {
    const color = TYPE_COLORS[item.type] || '#34C759';
    const fmt = (d: string) => d ? new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : '';
    return (
      <TouchableOpacity
        key={item.id}
        style={styles.docCard}
        onPress={() => router.push(item.link)}
      >
        <View style={[styles.docIcon, { backgroundColor: color + '20' }]}>
          <Ionicons name={(TYPE_ICONS[item.type] || 'document') as any} size={22} color={color} />
        </View>
        <View style={styles.docContent}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
            <Text style={styles.docTitle} numberOfLines={1}>{item.title}</Text>
          </View>
          <Text style={styles.docSummary} numberOfLines={1}>
            {item.counterparty_company ? `${item.counterparty} — ${item.counterparty_company}` : item.counterparty}
            {item.counterparty_email ? ` (${item.counterparty_email})` : ''}
          </Text>
          <View style={styles.docMeta}>
            <View style={[styles.versionBadge, { backgroundColor: '#34C75920' }]}>
              <Text style={[styles.versionText, { color: '#34C759' }]}>SIGNED</Text>
            </View>
            <View style={[styles.versionBadge, { backgroundColor: color + '20' }]}>
              <Text style={[styles.versionText, { color }]}>{item.type_label}</Text>
            </View>
            {item.signed_at && (
              <Text style={styles.metaText}>{fmt(item.signed_at)}</Text>
            )}
          </View>
        </View>
        <Ionicons name="chevron-forward" size={20} color="#8E8E93" />
      </TouchableOpacity>
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
        style={styles.filterScrollContainer}
        contentContainerStyle={styles.filterContainer}
      >
        <TouchableOpacity
          style={[
            styles.filterChip,
            selectedCategory === null && { backgroundColor: '#007AFF' },
          ]}
          onPress={() => setSelectedCategory(null)}
          data-testid="docs-filter-all"
        >
          <Text style={[styles.filterChipText, selectedCategory === null && styles.filterChipTextActive]}>
            All
          </Text>
        </TouchableOpacity>
        {categories.map((cat: any) => {
          const isActive = selectedCategory === cat.id;
          return (
            <TouchableOpacity
              key={cat.id}
              style={[
                styles.filterChip,
                isActive && { backgroundColor: CATEGORY_COLORS[cat.id] || '#007AFF' },
              ]}
              onPress={() => setSelectedCategory(isActive ? null : cat.id)}
              data-testid={`docs-filter-${cat.id}`}
            >
              <Ionicons
                name={cat.icon as any}
                size={14}
                color={isActive ? '#FFF' : CATEGORY_COLORS[cat.id] || '#8E8E93'}
              />
              <Text style={[
                styles.filterChipText,
                isActive && styles.filterChipTextActive,
              ]}>
                {cat.name}
              </Text>
            </TouchableOpacity>
          );
        })}
      </ScrollView>

      {/* Doc List */}
      {selectedCategory === 'signed' ? (
        <ScrollView
          contentContainerStyle={styles.listContent}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#007AFF" />}
        >
          {signedDocs.length === 0 ? (
            <View style={styles.emptyContainer}>
              <Ionicons name="checkmark-done-circle-outline" size={64} color="#2C2C2E" />
              <Text style={styles.emptyText}>No signed documents yet</Text>
              <Text style={styles.emptySubtext}>Signed NDAs, agreements, and quotes will appear here</Text>
            </View>
          ) : (
            <>
              <View style={styles.categoryHeader}>
                <View style={[styles.categoryIcon, { backgroundColor: '#34C75920' }]}>
                  <Ionicons name="checkmark-done-circle" size={16} color="#34C759" />
                </View>
                <Text style={styles.categoryTitle}>Signed Documents</Text>
                <Text style={styles.categoryCount}>{signedDocs.length}</Text>
              </View>
              {signedDocs.map(renderSignedDoc)}
            </>
          )}
        </ScrollView>
      ) : docs.length === 0 ? (
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
  filterScrollContainer: {
    marginBottom: 8,
    maxHeight: 44,
  },
  filterContainer: {
    paddingHorizontal: 16,
    flexDirection: 'row',
    alignItems: 'center',
  },
  filterChip: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'center',
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 20,
    backgroundColor: '#1C1C1E',
    gap: 6,
    marginRight: 8,
  },
  filterChipActive: {},
  filterChipText: { fontSize: 12, fontWeight: '600', color: '#8E8E93' },
  filterChipTextActive: { color: '#FFF' },
  listContent: { paddingHorizontal: 16, paddingBottom: 32 },
  // Modern category card header
  categoryCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1C1C1E',
    borderRadius: 14,
    padding: 16,
    marginTop: 12,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: '#2A2A2A',
  },
  categoryCardIcon: {
    width: 44,
    height: 44,
    borderRadius: 12,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 14,
  },
  categoryCardContent: {
    flex: 1,
  },
  categoryCardTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: '#FFF',
    marginBottom: 3,
    letterSpacing: 0.1,
  },
  categoryCardDescription: {
    fontSize: 12,
    color: '#8E8E93',
    lineHeight: 16,
  },
  categoryCardBadge: {
    minWidth: 28,
    height: 28,
    borderRadius: 14,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 8,
  },
  categoryCardBadgeText: {
    fontSize: 13,
    fontWeight: '700',
  },
  // Legacy category header styles (kept for signed docs section)
  categoryHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 8,
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
