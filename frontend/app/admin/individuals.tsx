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

import { useThemeStore } from '../../store/themeStore';
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
  const { colors } = useThemeStore();
  const styles = getStyles(colors);
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [individuals, setIndividuals] = useState<Individual[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [filter, setFilter] = useState<'all' | 'active' | 'inactive'>('all');
  const [showAddModal, setShowAddModal] = useState(false);
  const [creating, setCreating] = useState(false);
  const [newIndividual, setNewIndividual] = useState({ name: '', email: '', phone: '', title: '' });

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

  const handleCreate = async () => {
    if (!newIndividual.name.trim() || !newIndividual.email.trim()) return;
    try {
      setCreating(true);
      await api.post('/admin/individuals', newIndividual);
      setShowAddModal(false);
      setNewIndividual({ name: '', email: '', phone: '', title: '' });
      await loadIndividuals();
    } catch (error: any) {
      alert(error.response?.data?.detail || 'Failed to create individual');
    } finally {
      setCreating(false);
    }
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
      
      <Ionicons name="chevron-forward" size={20} color={colors.textSecondary} />
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
        <TouchableOpacity onPress={() => setShowAddModal(true)} data-testid="add-individual-btn">
          <Ionicons name="add-circle" size={28} color="#AF52DE" />
        </TouchableOpacity>
      </View>

      {/* Search Bar */}
      <View style={styles.searchContainer}>
        <Ionicons name="search" size={18} color={colors.textSecondary} />
        <TextInput
          style={styles.searchInput}
          placeholder="Search by name, email, or phone..."
          placeholderTextColor={colors.textSecondary}
          value={searchQuery}
          onChangeText={setSearchQuery}
        />
        {searchQuery ? (
          <TouchableOpacity onPress={() => setSearchQuery('')}>
            <Ionicons name="close-circle" size={18} color={colors.textSecondary} />
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
            <Ionicons name="person-outline" size={48} color={colors.textSecondary} />
            <Text style={styles.emptyText}>No individuals found</Text>
            <Text style={styles.emptySubtext}>
              Individual/sole proprietor accounts will appear here
            </Text>
          </View>
        }
      />

      {/* Add Individual Modal */}
      {showAddModal && (
        <View style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(0,0,0,0.6)', justifyContent: 'center', padding: 24, zIndex: 100 }}>
          <View style={{ backgroundColor: colors.card, borderRadius: 16, padding: 20 }}>
            <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
              <Text style={{ fontSize: 19, fontWeight: '700', color: colors.text }}>Add Individual</Text>
              <TouchableOpacity onPress={() => setShowAddModal(false)} data-testid="close-add-modal">
                <Ionicons name="close-circle" size={28} color={colors.textSecondary} />
              </TouchableOpacity>
            </View>
            <Text style={{ fontSize: 14, color: colors.textSecondary, marginBottom: 16 }}>
              Create an independent user account (not under any organization). This is for salespeople who pay for the tool themselves.
            </Text>
            {[
              { key: 'name', label: 'Full Name *', placeholder: 'John Smith' },
              { key: 'email', label: 'Email *', placeholder: 'john@example.com', keyboardType: 'email-address' },
              { key: 'phone', label: 'Phone', placeholder: '(801) 555-1234', keyboardType: 'phone-pad' },
              { key: 'title', label: 'Title', placeholder: 'Sales Associate' },
            ].map(({ key, label, placeholder, keyboardType }) => (
              <View key={key} style={{ marginBottom: 12 }}>
                <Text style={{ fontSize: 15, fontWeight: '600', color: colors.textSecondary, marginBottom: 4 }}>{label}</Text>
                <TextInput
                  style={{ backgroundColor: colors.bg, color: colors.text, borderRadius: 10, paddingHorizontal: 14, height: 44, fontSize: 17 }}
                  placeholder={placeholder}
                  placeholderTextColor={colors.textSecondary}
                  value={(newIndividual as any)[key]}
                  onChangeText={(v) => setNewIndividual(prev => ({ ...prev, [key]: v }))}
                  keyboardType={(keyboardType as any) || 'default'}
                  autoCapitalize={key === 'email' ? 'none' : 'words'}
                  data-testid={`add-individual-${key}`}
                />
              </View>
            ))}
            <Text style={{ fontSize: 13, color: colors.textSecondary, marginBottom: 16 }}>
              A temporary password will be generated. Share it with the user so they can log in.
            </Text>
            <TouchableOpacity
              style={{ backgroundColor: '#AF52DE', borderRadius: 12, height: 48, alignItems: 'center', justifyContent: 'center', opacity: (!newIndividual.name.trim() || !newIndividual.email.trim() || creating) ? 0.5 : 1 }}
              onPress={handleCreate}
              disabled={!newIndividual.name.trim() || !newIndividual.email.trim() || creating}
              data-testid="create-individual-submit"
            >
              <Text style={{ color: '#fff', fontSize: 18, fontWeight: '600' }}>
                {creating ? 'Creating...' : 'Create Individual'}
              </Text>
            </TouchableOpacity>
          </View>
        </View>
      )}
    </SafeAreaView>
  );
}

const getStyles = (colors: any) => StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.bg,
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
    borderBottomColor: colors.card,
  },
  backButton: {
    padding: 4,
  },
  title: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
  },
  searchContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.card,
    borderRadius: 10,
    marginHorizontal: 16,
    marginTop: 12,
    paddingHorizontal: 12,
    height: 40,
    gap: 8,
  },
  searchInput: {
    flex: 1,
    color: colors.text,
    fontSize: 17,
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
    backgroundColor: colors.card,
  },
  filterPillActive: {
    backgroundColor: '#AF52DE',
  },
  filterText: {
    fontSize: 15,
    fontWeight: '500',
    color: colors.textSecondary,
  },
  filterTextActive: {
    color: colors.text,
  },
  countBadge: {
    marginLeft: 'auto',
    backgroundColor: colors.surface,
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 10,
  },
  countText: {
    fontSize: 15,
    fontWeight: '600',
    color: '#AF52DE',
  },
  listContent: {
    padding: 16,
  },
  individualCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.card,
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
    fontSize: 19,
    fontWeight: '600',
    color: colors.text,
  },
  individualInfo: {
    flex: 1,
    marginLeft: 12,
  },
  individualName: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
  },
  individualEmail: {
    fontSize: 15,
    color: colors.textSecondary,
    marginTop: 2,
  },
  individualTitle: {
    fontSize: 14,
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
    fontSize: 13,
    fontWeight: '600',
  },
  activeText: {
    color: '#34C759',
  },
  inactiveText: {
    color: '#FF3B30',
  },
  subscriptionText: {
    fontSize: 12,
    color: colors.textSecondary,
    marginTop: 4,
  },
  emptyContainer: {
    alignItems: 'center',
    paddingVertical: 60,
  },
  emptyText: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
    marginTop: 16,
  },
  emptySubtext: {
    fontSize: 16,
    color: colors.textSecondary,
    marginTop: 8,
    textAlign: 'center',
  },
});
