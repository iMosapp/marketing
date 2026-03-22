import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  View,
  Text,
  TextInput,
  FlatList,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useAuthStore } from '../store/authStore';
import { useThemeStore } from '../store/themeStore';
import { searchAPI } from '../services/api';

interface SearchResult {
  id: string;
  type: 'contact' | 'conversation' | 'campaign';
  title: string;
  subtitle: string;
  icon: string;
  color: string;
  match_field?: string;
  tags?: string[];
  unread?: boolean;
  ai_outcome?: string;
  active?: boolean;
}

interface SearchResults {
  query: string;
  contacts: SearchResult[];
  conversations: SearchResult[];
  campaigns: SearchResult[];
  total_count: number;
}

export default function SearchScreen() {
  const { colors } = useThemeStore();
  const styles = getStyles(colors);
  const router = useRouter();
  const { user } = useAuthStore();
  const [results, setResults] = useState<SearchResults | null>(null);
  const [loading, setLoading] = useState(false);
  const [recentSearches, setRecentSearches] = useState<string[]>([]);
  const [activeFilter, setActiveFilter] = useState<'all' | 'contacts' | 'conversations' | 'campaigns'>('all');
  const searchTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const performSearch = useCallback(async (searchQuery: string) => {
    if (!user?._id || !searchQuery.trim()) {
      setResults(null);
      setLoading(false);
      return;
    }

    setLoading(true);

    try {
      // Use backend search API
      const types = activeFilter === 'all' ? undefined : [activeFilter];
      const searchResults = await searchAPI.globalSearch(user._id, searchQuery, types, 15);
      setResults(searchResults);
    } catch (error) {
      console.error('Search error:', error);
      setResults(null);
    } finally {
      setLoading(false);
    }
  }, [user?._id, activeFilter]);

  // Debounced search effect
  useEffect(() => {
    if (searchTimeoutRef.current) {
      clearTimeout(searchTimeoutRef.current);
    }

    if (query.trim()) {
      searchTimeoutRef.current = setTimeout(() => {
        performSearch(query);
      }, 300);
    } else {
      setResults(null);
    }

    return () => {
      if (searchTimeoutRef.current) {
        clearTimeout(searchTimeoutRef.current);
      }
    };
  }, [query, performSearch]);

  // Re-search when filter changes
  useEffect(() => {
    if (query.trim()) {
      performSearch(query);
    }
  }, [activeFilter]);

  const handleResultPress = (result: SearchResult) => {
    // Save to recent searches
    if (query.trim()) {
      setRecentSearches(prev => {
        const updated = [query, ...prev.filter(s => s !== query)].slice(0, 5);
        return updated;
      });
    }

    switch (result.type) {
      case 'contact':
        router.push(`/contact/${result.id}`);
        break;
      case 'conversation':
        router.push({
          pathname: `/thread/${result.id}`,
          params: {
            contact_name: result.name || result.title || '',
            contact_phone: result.phone || '',
            contact_email: result.email || '',
          }
        });
        break;
      case 'campaign':
        router.push(`/campaigns/${result.id}`);
        break;
    }
  };

  const handleRecentSearch = (searchTerm: string) => {
    setQuery(searchTerm);
  };

  const clearRecentSearches = () => {
    setRecentSearches([]);
  };

  const getAllResults = (): SearchResult[] => {
    if (!results) return [];
    
    if (activeFilter === 'all') {
      return [...results.contacts, ...results.conversations, ...results.campaigns];
    }
    
    return results[activeFilter] || [];
  };

  const renderResult = ({ item }: { item: SearchResult }) => (
    <TouchableOpacity
      style={styles.resultItem}
      onPress={() => handleResultPress(item)}
      data-testid={`search-result-${item.type}-${item.id}`}
    >
      <View style={[styles.resultIcon, { backgroundColor: item.color + '20' }]}>
        <Ionicons name={item.icon as any} size={22} color={item.color} />
        {item.unread && (
          <View style={styles.unreadDot} />
        )}
      </View>
      <View style={styles.resultContent}>
        <View style={styles.resultTitleRow}>
          <Text style={styles.resultTitle} numberOfLines={1}>{item.title}</Text>
          {item.ai_outcome && (
            <View style={[styles.aiTag, { backgroundColor: '#34C75920' }]}>
              <Ionicons name="sparkles" size={10} color="#34C759" />
              <Text style={styles.aiTagText}>AI</Text>
            </View>
          )}
        </View>
        <Text style={styles.resultSubtitle} numberOfLines={1}>
          {item.subtitle}
        </Text>
        {item.match_field && item.match_field !== 'first_name' && item.match_field !== 'last_name' && item.match_field !== 'name' && (
          <Text style={styles.matchField}>
            Found in: {item.match_field.replace('_', ' ')}
          </Text>
        )}
        {item.tags && item.tags.length > 0 && (
          <View style={styles.tagRow}>
            {item.tags.slice(0, 3).map((tag, index) => (
              <View key={index} style={styles.tagChip}>
                <Text style={styles.tagChipText}>{tag}</Text>
              </View>
            ))}
          </View>
        )}
      </View>
      <View style={styles.resultType}>
        <Text style={[styles.resultTypeText, { color: item.color }]}>
          {item.type.charAt(0).toUpperCase() + item.type.slice(1)}
        </Text>
      </View>
    </TouchableOpacity>
  );

  const renderFilterBar = () => (
    <View style={styles.filterBar}>
      {(['all', 'contacts', 'conversations', 'campaigns'] as const).map((filter) => (
        <TouchableOpacity
          key={filter}
          style={[
            styles.filterChip,
            activeFilter === filter && styles.filterChipActive,
          ]}
          onPress={() => setActiveFilter(filter)}
          data-testid={`search-filter-${filter}`}
        >
          <Text style={[
            styles.filterChipText,
            activeFilter === filter && styles.filterChipTextActive,
          ]}>
            {filter.charAt(0).toUpperCase() + filter.slice(1)}
          </Text>
          {results && filter !== 'all' && (
            <Text style={[
              styles.filterCount,
              activeFilter === filter && styles.filterCountActive,
            ]}>
              {results[filter]?.length || 0}
            </Text>
          )}
        </TouchableOpacity>
      ))}
    </View>
  );

  const renderHeader = () => (
    <>
      {query.trim() && renderFilterBar()}
      {!query && recentSearches.length > 0 && (
        <View style={styles.recentSection}>
          <View style={styles.recentHeader}>
            <Text style={styles.recentTitle}>Recent Searches</Text>
            <TouchableOpacity onPress={clearRecentSearches}>
              <Text style={styles.clearButton}>Clear</Text>
            </TouchableOpacity>
          </View>
          {recentSearches.map((search, index) => (
            <TouchableOpacity
              key={index}
              style={styles.recentItem}
              onPress={() => handleRecentSearch(search)}
            >
              <Ionicons name="time-outline" size={18} color={colors.textSecondary} />
              <Text style={styles.recentText}>{search}</Text>
            </TouchableOpacity>
          ))}
        </View>
      )}
      {!query && (
        <View style={styles.suggestionsSection}>
          <Text style={styles.suggestionsTitle}>Quick Actions</Text>
          <View style={styles.quickActions}>
            <TouchableOpacity
              style={styles.quickAction}
              onPress={() => router.push('/contact/new')}
              data-testid="quick-action-add-contact"
            >
              <View style={[styles.quickIcon, { backgroundColor: '#007AFF20' }]}>
                <Ionicons name="person-add" size={22} color="#007AFF" />
              </View>
              <Text style={styles.quickText}>Add Contact</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={styles.quickAction}
              onPress={() => router.push('/campaigns/new')}
              data-testid="quick-action-new-campaign"
            >
              <View style={[styles.quickIcon, { backgroundColor: '#FF950020' }]}>
                <Ionicons name="megaphone" size={22} color="#FF9500" />
              </View>
              <Text style={styles.quickText}>New Campaign</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={styles.quickAction}
              onPress={() => router.push('/tasks')}
              data-testid="quick-action-view-tasks"
            >
              <View style={[styles.quickIcon, { backgroundColor: '#34C75920' }]}>
                <Ionicons name="checkmark-done" size={22} color="#34C759" />
              </View>
              <Text style={styles.quickText}>View Tasks</Text>
            </TouchableOpacity>
          </View>
        </View>
      )}
    </>
  );

  const allResults = getAllResults();

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: colors.bg }]} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity style={styles.backButton} onPress={() => router.back()} data-testid="search-back-btn">
          <Ionicons name="chevron-back" size={28} color="#007AFF" />
        </TouchableOpacity>
        <View style={styles.searchContainer}>
          <Ionicons name="search" size={20} color={colors.textSecondary} />
          <TextInput
            style={styles.searchInput}
            placeholder="Search contacts, messages, campaigns..."
            placeholderTextColor={colors.textSecondary}
            value={query}
            onChangeText={setQuery}
            autoFocus
            returnKeyType="search"
            data-testid="search-input"
          />
          {query.length > 0 && (
            <TouchableOpacity onPress={() => setQuery('')} data-testid="search-clear-btn">
              <Ionicons name="close-circle" size={20} color={colors.textSecondary} />
            </TouchableOpacity>
          )}
        </View>
      </View>

      {/* Results */}
      {loading ? (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#007AFF" />
          <Text style={styles.loadingText}>Searching...</Text>
        </View>
      ) : (
        <FlatList
          data={allResults}
          keyExtractor={(item) => `${item.type}-${item.id}`}
          renderItem={renderResult}
          ListHeaderComponent={renderHeader}
          ListEmptyComponent={
            query ? (
              <View style={styles.emptyContainer}>
                <Ionicons name="search-outline" size={48} color={colors.textSecondary} />
                <Text style={styles.emptyText}>No results found</Text>
                <Text style={styles.emptySubtext}>
                  Try a different search term or filter
                </Text>
              </View>
            ) : null
          }
          ListFooterComponent={
            results && results.total_count > 0 ? (
              <View style={styles.footer}>
                <Text style={styles.footerText}>
                  {results.total_count} result{results.total_count !== 1 ? 's' : ''} found
                </Text>
              </View>
            ) : null
          }
          contentContainerStyle={styles.listContent}
        />
      )}
    </SafeAreaView>
  );
}

const getStyles = (colors: any) => StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: undefined,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: colors.card,
  },
  backButton: {
    marginRight: 8,
  },
  searchContainer: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: undefined,
    borderRadius: 10,
    paddingHorizontal: 12,
    height: 40,
    gap: 8,
  },
  searchInput: {
    flex: 1,
    fontSize: 18,
    color: undefined,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    gap: 12,
  },
  loadingText: {
    fontSize: 16,
    color: undefined,
  },
  listContent: {
    padding: 16,
  },
  filterBar: {
    flexDirection: 'row',
    marginBottom: 16,
    gap: 8,
  },
  filterChip: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: undefined,
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 16,
    gap: 4,
  },
  filterChipActive: {
    backgroundColor: '#007AFF',
  },
  filterChipText: {
    fontSize: 15,
    color: undefined,
    fontWeight: '500',
  },
  filterChipTextActive: {
    color: undefined,
  },
  filterCount: {
    fontSize: 13,
    color: '#6E6E73',
    backgroundColor: colors.surface,
    paddingHorizontal: 6,
    paddingVertical: 1,
    borderRadius: 8,
  },
  filterCountActive: {
    color: undefined,
    backgroundColor: 'rgba(255,255,255,0.2)',
  },
  resultItem: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: undefined,
    borderRadius: 12,
    padding: 12,
    marginBottom: 8,
  },
  resultIcon: {
    width: 44,
    height: 44,
    borderRadius: 22,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
    position: 'relative',
  },
  unreadDot: {
    position: 'absolute',
    top: 0,
    right: 0,
    width: 12,
    height: 12,
    borderRadius: 6,
    backgroundColor: '#007AFF',
    borderWidth: 2,
    borderColor: colors.card,
  },
  resultContent: {
    flex: 1,
  },
  resultTitleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  resultTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: undefined,
    flex: 1,
  },
  aiTag: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 8,
    gap: 3,
  },
  aiTagText: {
    fontSize: 12,
    fontWeight: '700',
    color: '#34C759',
  },
  resultSubtitle: {
    fontSize: 16,
    color: undefined,
    marginTop: 2,
  },
  matchField: {
    fontSize: 13,
    color: '#6E6E73',
    marginTop: 4,
    fontStyle: 'italic',
  },
  tagRow: {
    flexDirection: 'row',
    marginTop: 6,
    gap: 4,
  },
  tagChip: {
    backgroundColor: colors.surface,
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 8,
  },
  tagChipText: {
    fontSize: 12,
    color: undefined,
  },
  resultType: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    backgroundColor: colors.surface,
    borderRadius: 6,
  },
  resultTypeText: {
    fontSize: 13,
    fontWeight: '600',
  },
  emptyContainer: {
    alignItems: 'center',
    paddingTop: 60,
  },
  emptyText: {
    fontSize: 19,
    fontWeight: '600',
    color: undefined,
    marginTop: 16,
  },
  emptySubtext: {
    fontSize: 16,
    color: undefined,
    marginTop: 4,
  },
  footer: {
    alignItems: 'center',
    paddingVertical: 16,
  },
  footerText: {
    fontSize: 15,
    color: '#6E6E73',
  },
  recentSection: {
    marginBottom: 24,
  },
  recentHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  recentTitle: {
    fontSize: 17,
    fontWeight: '600',
    color: undefined,
  },
  clearButton: {
    fontSize: 16,
    color: '#007AFF',
  },
  recentItem: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 10,
    gap: 12,
  },
  recentText: {
    fontSize: 18,
    color: undefined,
  },
  suggestionsSection: {
    marginBottom: 24,
  },
  suggestionsTitle: {
    fontSize: 17,
    fontWeight: '600',
    color: undefined,
    marginBottom: 12,
  },
  quickActions: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  quickAction: {
    alignItems: 'center',
    flex: 1,
  },
  quickIcon: {
    width: 56,
    height: 56,
    borderRadius: 16,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 8,
  },
  quickText: {
    fontSize: 14,
    color: undefined,
    textAlign: 'center',
  },
});
