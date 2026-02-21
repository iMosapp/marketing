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

const CATEGORY_LABELS: Record<string, string> = {
  getting_started: 'Getting Started',
  daily_operations: 'Daily Operations',
  customer_communication: 'Customer Communication',
  admin_tasks: 'Admin Tasks',
  troubleshooting: 'Troubleshooting',
  best_practices: 'Best Practices',
  policies: 'Policies & Guidelines',
  tools_features: 'Tools & Features',
};

const CATEGORY_ICONS: Record<string, string> = {
  getting_started: 'rocket',
  daily_operations: 'calendar',
  customer_communication: 'chatbubbles',
  admin_tasks: 'settings',
  troubleshooting: 'build',
  best_practices: 'star',
  policies: 'document-text',
  tools_features: 'apps',
};

const CATEGORY_COLORS: Record<string, string> = {
  getting_started: '#34C759',
  daily_operations: '#007AFF',
  customer_communication: '#FF9500',
  admin_tasks: '#5856D6',
  troubleshooting: '#FF3B30',
  best_practices: '#FFD60A',
  policies: '#8E8E93',
  tools_features: '#AF52DE',
};

export default function SOPListScreen() {
  const router = useRouter();
  const user = useAuthStore((state) => state.user);
  
  const [sops, setSops] = useState<any[]>([]);
  const [categories, setCategories] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [search, setSearch] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [requiredCount, setRequiredCount] = useState({ total: 0, completed: 0 });

  useFocusEffect(
    useCallback(() => {
      loadData();
    }, [selectedCategory, search])
  );

  const loadData = async () => {
    try {
      const headers = { 'X-User-ID': user?._id };
      
      // Load categories
      const catRes = await api.get('/sop/categories', { headers });
      setCategories(catRes.data);
      
      // Load SOPs
      let url = '/sop/';
      const params: string[] = [];
      if (selectedCategory) params.push(`category=${selectedCategory}`);
      if (search) params.push(`search=${encodeURIComponent(search)}`);
      if (params.length) url += '?' + params.join('&');
      
      const sopRes = await api.get(url, { headers });
      setSops(sopRes.data);
      
      // Load required reading count
      const reqRes = await api.get('/sop/required', { headers });
      setRequiredCount({
        total: reqRes.data.total,
        completed: reqRes.data.completed,
      });
      
    } catch (error) {
      console.error('Failed to load SOPs:', error);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const onRefresh = () => {
    setRefreshing(true);
    loadData();
  };

  const groupedSops = sops.reduce((acc: Record<string, any[]>, sop) => {
    const cat = sop.category || 'other';
    if (!acc[cat]) acc[cat] = [];
    acc[cat].push(sop);
    return acc;
  }, {});

  const renderSOP = ({ item }: { item: any }) => (
    <TouchableOpacity
      style={styles.sopCard}
      onPress={() => router.push(`/admin/sop/${item._id}`)}
      data-testid={`sop-item-${item._id}`}
    >
      <View style={styles.sopLeft}>
        <View style={[
          styles.sopIcon,
          { backgroundColor: (CATEGORY_COLORS[item.category] || '#8E8E93') + '20' }
        ]}>
          <Ionicons
            name={CATEGORY_ICONS[item.category] || 'document'}
            size={20}
            color={CATEGORY_COLORS[item.category] || '#8E8E93'}
          />
        </View>
      </View>
      
      <View style={styles.sopContent}>
        <View style={styles.sopHeader}>
          <Text style={styles.sopTitle} numberOfLines={1}>{item.title}</Text>
          {item.is_required_reading && (
            <View style={styles.requiredBadge}>
              <Text style={styles.requiredText}>Required</Text>
            </View>
          )}
        </View>
        <Text style={styles.sopSummary} numberOfLines={2}>{item.summary}</Text>
        <View style={styles.sopMeta}>
          {item.estimated_time && (
            <View style={styles.metaItem}>
              <Ionicons name="time-outline" size={12} color="#8E8E93" />
              <Text style={styles.metaText}>{item.estimated_time}</Text>
            </View>
          )}
          <View style={styles.metaItem}>
            <Ionicons name="list-outline" size={12} color="#8E8E93" />
            <Text style={styles.metaText}>{item.steps?.length || 0} steps</Text>
          </View>
          {item.is_completed && (
            <View style={styles.completedBadge}>
              <Ionicons name="checkmark-circle" size={14} color="#34C759" />
              <Text style={styles.completedText}>Completed</Text>
            </View>
          )}
        </View>
      </View>
      
      <Ionicons name="chevron-forward" size={20} color="#8E8E93" />
    </TouchableOpacity>
  );

  const renderCategoryHeader = (category: string) => (
    <View style={styles.categoryHeader}>
      <View style={[
        styles.categoryIcon,
        { backgroundColor: (CATEGORY_COLORS[category] || '#8E8E93') + '20' }
      ]}>
        <Ionicons
          name={CATEGORY_ICONS[category] || 'document'}
          size={16}
          color={CATEGORY_COLORS[category] || '#8E8E93'}
        />
      </View>
      <Text style={styles.categoryTitle}>
        {CATEGORY_LABELS[category] || category}
      </Text>
      <Text style={styles.categoryCount}>
        {groupedSops[category]?.length || 0}
      </Text>
    </View>
  );

  const renderCategoryFilter = () => (
    <ScrollView
      horizontal
      showsHorizontalScrollIndicator={false}
      contentContainerStyle={styles.filterContainer}
    >
      <TouchableOpacity
        style={[
          styles.filterChip,
          selectedCategory === null && styles.filterChipActive
        ]}
        onPress={() => setSelectedCategory(null)}
      >
        <Text style={[
          styles.filterChipText,
          selectedCategory === null && styles.filterChipTextActive
        ]}>
          All
        </Text>
      </TouchableOpacity>
      {categories.map((item: any) => (
        <TouchableOpacity
          key={item.id}
          style={[
            styles.filterChip,
            selectedCategory === item.id && styles.filterChipActive
          ]}
          onPress={() => setSelectedCategory(item.id)}
        >
          <Text style={[
            styles.filterChipText,
            selectedCategory === item.id && styles.filterChipTextActive
          ]}>
            {item.name}
          </Text>
        </TouchableOpacity>
      ))}
    </ScrollView>
  );

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
        <Text style={styles.headerTitle}>Training & SOPs</Text>
        <View style={{ width: 40 }} />
      </View>
      
      {/* Required Reading Progress */}
      {requiredCount.total > 0 && (
        <TouchableOpacity
          style={styles.requiredCard}
          onPress={() => router.push('/admin/sop/required')}
        >
          <View style={styles.requiredLeft}>
            <Ionicons name="school" size={24} color="#FF9500" />
            <View style={styles.requiredInfo}>
              <Text style={styles.requiredTitle}>Required Reading</Text>
              <Text style={styles.requiredProgress}>
                {requiredCount.completed} of {requiredCount.total} completed
              </Text>
            </View>
          </View>
          <View style={styles.progressBar}>
            <View
              style={[
                styles.progressFill,
                { width: `${(requiredCount.completed / requiredCount.total) * 100}%` }
              ]}
            />
          </View>
        </TouchableOpacity>
      )}
      
      {/* Search */}
      <View style={styles.searchContainer}>
        <Ionicons name="search" size={20} color="#8E8E93" />
        <TextInput
          style={styles.searchInput}
          placeholder="Search training materials..."
          placeholderTextColor="#8E8E93"
          value={search}
          onChangeText={setSearch}
        />
        {search.length > 0 && (
          <TouchableOpacity onPress={() => setSearch('')}>
            <Ionicons name="close-circle" size={20} color="#8E8E93" />
          </TouchableOpacity>
        )}
      </View>
      
      {/* Category Filter */}
      {renderCategoryFilter()}
      
      {/* SOP List */}
      <FlatList
        data={Object.keys(groupedSops)}
        renderItem={({ item: category }) => (
          <View>
            {renderCategoryHeader(category)}
            {groupedSops[category].map((sop: any) => (
              <View key={sop._id}>
                {renderSOP({ item: sop })}
              </View>
            ))}
          </View>
        )}
        keyExtractor={(item) => item}
        contentContainerStyle={styles.listContent}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#007AFF" />
        }
        ListEmptyComponent={() => (
          <View style={styles.emptyContainer}>
            <Ionicons name="document-text-outline" size={64} color="#2C2C2E" />
            <Text style={styles.emptyText}>No training materials found</Text>
          </View>
        )}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#000',
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#1C1C1E',
  },
  backButton: {
    padding: 4,
    width: 40,
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: '#FFF',
  },
  requiredCard: {
    margin: 16,
    marginBottom: 8,
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 16,
    borderWidth: 1,
    borderColor: '#FF950030',
  },
  requiredLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 12,
  },
  requiredInfo: {
    marginLeft: 12,
  },
  requiredTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFF',
  },
  requiredProgress: {
    fontSize: 13,
    color: '#8E8E93',
    marginTop: 2,
  },
  progressBar: {
    height: 6,
    backgroundColor: '#2C2C2E',
    borderRadius: 3,
  },
  progressFill: {
    height: 6,
    backgroundColor: '#FF9500',
    borderRadius: 3,
  },
  searchContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1C1C1E',
    margin: 16,
    marginTop: 8,
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
    paddingTop: 8,
    flexDirection: 'row',
    alignItems: 'center',
  },
  filterChip: {
    paddingHorizontal: 16,
    height: 36,
    backgroundColor: '#1C1C1E',
    borderRadius: 18,
    marginRight: 8,
    minWidth: 60,
    justifyContent: 'center',
    alignItems: 'center',
    flexDirection: 'row',
  },
  filterChipActive: {
    backgroundColor: '#007AFF',
  },
  filterChipText: {
    fontSize: 14,
    fontWeight: '500',
    color: '#8E8E93',
    textAlign: 'center',
  },
  filterChipTextActive: {
    color: '#FFF',
  },
  listContent: {
    paddingHorizontal: 16,
    paddingBottom: 32,
  },
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
    fontSize: 14,
    fontWeight: '600',
    color: '#8E8E93',
    marginLeft: 8,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  categoryCount: {
    fontSize: 13,
    color: '#6E6E73',
    marginLeft: 'auto',
  },
  sopCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 16,
    marginBottom: 8,
  },
  sopLeft: {
    marginRight: 12,
  },
  sopIcon: {
    width: 40,
    height: 40,
    borderRadius: 8,
    justifyContent: 'center',
    alignItems: 'center',
  },
  sopContent: {
    flex: 1,
  },
  sopHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 4,
  },
  sopTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFF',
    flex: 1,
  },
  requiredBadge: {
    backgroundColor: '#FF950030',
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 4,
    marginLeft: 8,
  },
  requiredText: {
    fontSize: 10,
    fontWeight: '600',
    color: '#FF9500',
    textTransform: 'uppercase',
  },
  sopSummary: {
    fontSize: 13,
    color: '#8E8E93',
    lineHeight: 18,
    marginBottom: 8,
  },
  sopMeta: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  metaItem: {
    flexDirection: 'row',
    alignItems: 'center',
    marginRight: 12,
  },
  metaText: {
    fontSize: 12,
    color: '#6E6E73',
    marginLeft: 4,
  },
  completedBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    marginLeft: 'auto',
  },
  completedText: {
    fontSize: 12,
    color: '#34C759',
    marginLeft: 4,
  },
  emptyContainer: {
    alignItems: 'center',
    paddingVertical: 60,
  },
  emptyText: {
    color: '#8E8E93',
    fontSize: 16,
    marginTop: 16,
  },
});
