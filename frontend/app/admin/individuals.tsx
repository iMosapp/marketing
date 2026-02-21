import React, { useState, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  FlatList,
  ActivityIndicator,
  RefreshControl,
  TextInput,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import { format } from 'date-fns';
import api from '../../services/api';

interface Individual {
  _id: string;
  name: string;
  email: string;
  phone?: string;
  title?: string;
  is_active: boolean;
  created_at?: string;
  last_login?: string;
  subscription_status?: string;
}

export default function IndividualsScreen() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [individuals, setIndividuals] = useState<Individual[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [filter, setFilter] = useState<'all' | 'active' | 'inactive'>('all');

  useFocusEffect(
    useCallback(() => {
      loadIndividuals();
    }, [])
  );

  const loadIndividuals = async () => {
    try {
      setLoading(true);
      const response = await api.get('/admin/individuals');
      setIndividuals(response.data);
    } catch (error) {
      console.error('Failed to load individuals:', error);
    } finally {
      setLoading(false);
    }
  };

  const onRefresh = async () => {
    setRefreshing(true);
    await loadIndividuals();
    setRefreshing(false);
  };

  const filteredIndividuals = individuals.filter((individual) => {
    // Filter by status
    if (filter === 'active' && !individual.is_active) return false;
    if (filter === 'inactive' && individual.is_active) return false;
    
    // Filter by search query
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      return (
        individual.name?.toLowerCase().includes(query) ||
        individual.email?.toLowerCase().includes(query) ||
        individual.phone?.includes(query)
      );
    }
    
    return true;
  });

  const renderIndividual = ({ item }: { item: Individual }) => (
    <TouchableOpacity
      style={styles.individualCard}
      onPress={() => router.push(`/admin/users/${item._id}`)}
      data-testid={`individual-${item._id}`}
    >
      <View style={styles.individualAvatar}>
        <Text style={styles.avatarText}>
          {item.name?.charAt(0)?.toUpperCase() || 'I'}
        </Text>
      </View>
      
      <View style={styles.individualInfo}>
        <Text style={styles.individualName}>{item.name || 'Unnamed'}</Text>
        <Text style={styles.individualEmail}>{item.email}</Text>
        {item.title && (
          <Text style={styles.individualTitle}>{item.title}</Text>
        )}
      </View>
      
      <View style={styles.individualMeta}>
        <View style={[
          styles.statusBadge,
          item.is_active ? styles.activeBadge : styles.inactiveBadge
        ]}>
          <Text style={[
            styles.statusText,
            item.is_active ? styles.activeText : styles.inactiveText
          ]}>
            {item.is_active ? 'Active' : 'Inactive'}
          </Text>
        </View>
        {item.subscription_status && (
          <Text style={styles.subscriptionText}>
            {item.subscription_status}
          </Text>
        )}
      </View>
      
      <Ionicons name="chevron-forward" size={20} color="#8E8E93" />
    </TouchableOpacity>
  );

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#AF52DE" />
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
        <Text style={styles.title}>Individuals</Text>
        <View style={{ width: 28 }} />
      </View>

      {/* Search Bar */}
      <View style={styles.searchContainer}>
        <Ionicons name="search" size={18} color="#8E8E93" />
        <TextInput
          style={styles.searchInput}
          placeholder="Search by name, email, or phone..."
          placeholderTextColor="#8E8E93"
          value={searchQuery}
          onChangeText={setSearchQuery}
        />
        {searchQuery ? (
          <TouchableOpacity onPress={() => setSearchQuery('')}>
            <Ionicons name="close-circle" size={18} color="#8E8E93" />
          </TouchableOpacity>
        ) : null}
      </View>

      {/* Filter Pills */}
      <View style={styles.filterContainer}>
        {(['all', 'active', 'inactive'] as const).map((f) => (
          <TouchableOpacity
            key={f}
            style={[styles.filterPill, filter === f && styles.filterPillActive]}
            onPress={() => setFilter(f)}
          >
            <Text style={[styles.filterText, filter === f && styles.filterTextActive]}>
              {f.charAt(0).toUpperCase() + f.slice(1)}
            </Text>
          </TouchableOpacity>
        ))}
        <View style={styles.countBadge}>
          <Text style={styles.countText}>{filteredIndividuals.length}</Text>
        </View>
      </View>

      {/* List */}
      <FlatList
        data={filteredIndividuals}
        renderItem={renderIndividual}
        keyExtractor={(item) => item._id}
        contentContainerStyle={styles.listContent}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#AF52DE" />
        }
        ListEmptyComponent={
          <View style={styles.emptyContainer}>
            <Ionicons name="person-outline" size={48} color="#8E8E93" />
            <Text style={styles.emptyText}>No individuals found</Text>
            <Text style={styles.emptySubtext}>
              Individual/sole proprietor accounts will appear here
            </Text>
          </View>
        }
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
  },
  title: {
    fontSize: 17,
    fontWeight: '600',
    color: '#FFF',
  },
  searchContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1C1C1E',
    borderRadius: 10,
    marginHorizontal: 16,
    marginTop: 12,
    paddingHorizontal: 12,
    height: 40,
    gap: 8,
  },
  searchInput: {
    flex: 1,
    color: '#FFF',
    fontSize: 15,
  },
  filterContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 12,
    gap: 8,
  },
  filterPill: {
    paddingHorizontal: 14,
    paddingVertical: 6,
    borderRadius: 16,
    backgroundColor: '#1C1C1E',
  },
  filterPillActive: {
    backgroundColor: '#AF52DE',
  },
  filterText: {
    fontSize: 13,
    fontWeight: '500',
    color: '#8E8E93',
  },
  filterTextActive: {
    color: '#FFF',
  },
  countBadge: {
    marginLeft: 'auto',
    backgroundColor: '#2C2C2E',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 10,
  },
  countText: {
    fontSize: 13,
    fontWeight: '600',
    color: '#AF52DE',
  },
  listContent: {
    padding: 16,
  },
  individualCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 14,
    marginBottom: 8,
  },
  individualAvatar: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: '#AF52DE',
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarText: {
    fontSize: 18,
    fontWeight: '600',
    color: '#FFF',
  },
  individualInfo: {
    flex: 1,
    marginLeft: 12,
  },
  individualName: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFF',
  },
  individualEmail: {
    fontSize: 13,
    color: '#8E8E93',
    marginTop: 2,
  },
  individualTitle: {
    fontSize: 12,
    color: '#AF52DE',
    marginTop: 2,
  },
  individualMeta: {
    alignItems: 'flex-end',
    marginRight: 8,
  },
  statusBadge: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 8,
  },
  activeBadge: {
    backgroundColor: '#34C75930',
  },
  inactiveBadge: {
    backgroundColor: '#FF3B3030',
  },
  statusText: {
    fontSize: 11,
    fontWeight: '600',
  },
  activeText: {
    color: '#34C759',
  },
  inactiveText: {
    color: '#FF3B30',
  },
  subscriptionText: {
    fontSize: 10,
    color: '#8E8E93',
    marginTop: 4,
  },
  emptyContainer: {
    alignItems: 'center',
    paddingVertical: 60,
  },
  emptyText: {
    fontSize: 17,
    fontWeight: '600',
    color: '#FFF',
    marginTop: 16,
  },
  emptySubtext: {
    fontSize: 14,
    color: '#8E8E93',
    marginTop: 8,
    textAlign: 'center',
  },
});
