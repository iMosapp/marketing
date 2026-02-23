import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  FlatList,
  ActivityIndicator,
  RefreshControl,
  Modal,
  ScrollView,
  KeyboardAvoidingView,
  Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import api, { adminAPI } from '../../services/api';
import { showAlert, showSimpleAlert, showConfirm } from '../../services/alert';
import { WebSafeButton } from '../../components/WebSafeButton';

export default function StoresScreen() {
  const router = useRouter();
  
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [stores, setStores] = useState<any[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [showSearch, setShowSearch] = useState(false);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [creating, setCreating] = useState(false);
  
  const [newStore, setNewStore] = useState({
    name: '',
    phone: '',
    address: '',
    city: '',
    state: '',
    country: 'US',
    organization_id: '',
  });
  
  useFocusEffect(
    useCallback(() => {
      loadStores();
    }, [])
  );
  
  const loadStores = async () => {
    try {
      setLoading(true);
      // Load all stores across all organizations
      const response = await api.get('/admin/stores');
      setStores(response.data);
    } catch (error) {
      console.error('Failed to load stores:', error);
    } finally {
      setLoading(false);
    }
  };
  
  const onRefresh = async () => {
    setRefreshing(true);
    await loadStores();
    setRefreshing(false);
  };
  
  const handleCreateStore = async () => {
    if (!newStore.name) {
      showSimpleAlert('Error', 'Store name is required');
      return;
    }
    
    setCreating(true);
    try {
      await adminAPI.createStore(newStore);
      showSimpleAlert('Success', 'Store created successfully');
      setShowCreateModal(false);
      setNewStore({
        name: '',
        phone: '',
        address: '',
        city: '',
        state: '',
        country: 'US',
        organization_id: '',
      });
      loadStores();
    } catch (error: any) {
      const message = error?.response?.data?.detail || 'Failed to create store';
      showSimpleAlert('Error', message);
    } finally {
      setCreating(false);
    }
  };
  
  const handleDeleteStore = (store: any) => {
    showConfirm(
      'Delete Store',
      `Are you sure you want to delete "${store.name}"? Users will be unassigned from this store.`,
      async () => {
        try {
          await adminAPI.deleteStore(store._id);
          loadStores();
        } catch (error) {
          showSimpleAlert('Error', 'Failed to delete store');
        }
      },
      undefined,
      'Delete',
      'Cancel'
    );
  };
  
  const handleToggleStoreActive = (store: any) => {
    const newStatus = !store.active;
    showConfirm(
      newStatus ? 'Activate Store' : 'Deactivate Store',
      `Are you sure you want to ${newStatus ? 'activate' : 'deactivate'} "${store.name}"?`,
      async () => {
        try {
          await api.put(`/admin/stores/${store._id}`, { active: newStatus });
          loadStores();
          showSimpleAlert('Success', `Store ${newStatus ? 'activated' : 'deactivated'}`);
        } catch (error) {
          showSimpleAlert('Error', 'Failed to update store status');
        }
      },
      undefined,
      newStatus ? 'Activate' : 'Deactivate',
      'Cancel'
    );
  };

  // Separate active and inactive stores
  const activeStores = stores.filter(s => s.active !== false);
  const inactiveStores = stores.filter(s => s.active === false);

  // Filter stores based on search query
  const filterStores = (storeList: any[]) => {
    if (!searchQuery.trim()) return storeList;
    const query = searchQuery.toLowerCase();
    return storeList.filter((store) =>
      store.name?.toLowerCase().includes(query) ||
      store.city?.toLowerCase().includes(query) ||
      store.state?.toLowerCase().includes(query) ||
      store.organization_name?.toLowerCase().includes(query)
    );
  };

  const filteredActiveStores = filterStores(activeStores);
  const filteredInactiveStores = filterStores(inactiveStores);
  const totalFiltered = filteredActiveStores.length + filteredInactiveStores.length;

  const renderStore = ({ item }: { item: any }) => (
    <TouchableOpacity 
      style={[styles.storeCard, item.active === false && styles.inactiveCard]}
      onPress={() => router.push(`/admin/stores/${item._id}`)}
    >
      <View style={styles.storeCardContent}>
        <View style={[styles.storeIcon, { backgroundColor: item.active !== false ? '#34C75920' : '#8E8E9320' }]}>
          <Ionicons name="storefront" size={24} color={item.active !== false ? "#34C759" : "#8E8E93"} />
        </View>
        <View style={styles.storeInfo}>
          <View style={styles.storeNameRow}>
            <Text style={[styles.storeName, item.active === false && styles.inactiveText]}>{item.name}</Text>
            <View style={[styles.statusDot, { backgroundColor: item.active !== false ? '#34C759' : '#FF3B30' }]} />
          </View>
          <Text style={styles.storeLocation}>
            {item.city || 'N/A'}, {item.state || 'N/A'}
          </Text>
          {item.organization_name && (
            <Text style={styles.orgNameLabel}>{item.organization_name}</Text>
          )}
        </View>
        <View style={styles.storeActions}>
          <TouchableOpacity 
            style={styles.actionButton}
            onPress={(e) => {
              e.stopPropagation();
              handleToggleStoreActive(item);
            }}
          >
            <Ionicons name={item.active !== false ? "pause-circle-outline" : "play-circle-outline"} size={22} color="#8E8E93" />
          </TouchableOpacity>
          <TouchableOpacity 
            style={styles.actionButton}
            onPress={(e) => {
              e.stopPropagation();
              handleDeleteStore(item);
            }}
          >
            <Ionicons name="trash-outline" size={20} color="#FF3B30" />
          </TouchableOpacity>
        </View>
      </View>
    </TouchableOpacity>
  );

  const renderSectionHeader = (title: string, count: number) => (
    <View style={styles.sectionHeader}>
      <Text style={styles.sectionTitle}>{title}</Text>
      <Text style={styles.sectionCount}>{count}</Text>
    </View>
  );
  
  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="chevron-back" size={28} color="#007AFF" />
        </TouchableOpacity>
        <Text style={styles.title}>Stores</Text>
        <View style={styles.headerActions}>
          <TouchableOpacity onPress={() => setShowSearch(!showSearch)} style={styles.searchButton}>
            <Ionicons name="search" size={24} color="#007AFF" />
          </TouchableOpacity>
          <TouchableOpacity 
            onPress={() => setShowCreateModal(true)} 
            style={styles.addButton}
          >
            <Ionicons name="add-circle" size={32} color="#007AFF" />
          </TouchableOpacity>
        </View>
      </View>
      
      {/* Search Bar */}
      {showSearch && (
        <View style={styles.searchContainer}>
          <View style={styles.searchBar}>
            <Ionicons name="search" size={20} color="#8E8E93" />
            <TextInput
              style={styles.searchInput}
              placeholder="Search by name, city, organization..."
              placeholderTextColor="#8E8E93"
              value={searchQuery}
              onChangeText={setSearchQuery}
              autoCapitalize="none"
              autoCorrect={false}
              autoFocus
            />
            {searchQuery.length > 0 && (
              <TouchableOpacity onPress={() => setSearchQuery('')}>
                <Ionicons name="close-circle" size={20} color="#8E8E93" />
              </TouchableOpacity>
            )}
          </View>
          {searchQuery && (
            <Text style={styles.searchResultCount}>
              {totalFiltered} result{totalFiltered !== 1 ? 's' : ''}
            </Text>
          )}
        </View>
      )}
      
      {/* List */}
      {loading ? (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#007AFF" />
        </View>
      ) : (
        <FlatList
          data={[
            { type: 'header', title: 'Active Stores', count: filteredActiveStores.length },
            ...filteredActiveStores.map(s => ({ type: 'store', ...s })),
            ...(filteredInactiveStores.length > 0 ? [
              { type: 'divider' },
              { type: 'header', title: 'Inactive Stores', count: filteredInactiveStores.length },
              ...filteredInactiveStores.map(s => ({ type: 'store', ...s })),
            ] : []),
          ]}
          renderItem={({ item }) => {
            if (item.type === 'header') {
              return renderSectionHeader(item.title, item.count);
            }
            if (item.type === 'divider') {
              return <View style={styles.sectionDivider} />;
            }
            return renderStore({ item });
          }}
          keyExtractor={(item, index) => item._id || `section-${index}`}
          contentContainerStyle={styles.listContent}
          refreshControl={
            <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#007AFF" />
          }
          ListEmptyComponent={() => (
            <View style={styles.emptyContainer}>
              <Ionicons name="storefront-outline" size={64} color="#2C2C2E" />
              <Text style={styles.emptyText}>No stores yet</Text>
              <TouchableOpacity 
                style={styles.createButton}
                onPress={() => setShowCreateModal(true)}
              >
                <Text style={styles.createButtonText}>Add Store</Text>
              </TouchableOpacity>
            </View>
          )}
        />
      )}
      
      {/* Create Modal */}
      <Modal
        visible={showCreateModal}
        animationType="slide"
        presentationStyle="pageSheet"
      >
        <SafeAreaView style={styles.modalContainer}>
          <View style={styles.modalHeader}>
            <WebSafeButton
              onPress={() => setShowCreateModal(false)}
              variant="ghost"
              testID="modal-cancel"
            >
              <Text style={styles.modalCancel}>Cancel</Text>
            </WebSafeButton>
            <Text style={styles.modalTitle}>New Store</Text>
            <WebSafeButton
              onPress={handleCreateStore}
              disabled={creating}
              loading={creating}
              variant="ghost"
              testID="modal-create"
            >
              <Text style={styles.modalSave}>Create</Text>
            </WebSafeButton>
          </View>
          
          <ScrollView style={styles.modalContent}>
            <Text style={styles.inputLabel}>Store Name *</Text>
            <TextInput
              style={styles.input}
              placeholder="e.g., Ken Garff Honda Downtown"
              placeholderTextColor="#8E8E93"
              value={newStore.name}
              onChangeText={(text) => setNewStore({ ...newStore, name: text })}
            />
            
            <Text style={styles.inputLabel}>Phone</Text>
            <TextInput
              style={styles.input}
              placeholder="+1 (555) 123-4567"
              placeholderTextColor="#8E8E93"
              value={newStore.phone}
              onChangeText={(text) => setNewStore({ ...newStore, phone: text })}
              keyboardType="phone-pad"
            />
            
            <Text style={styles.inputLabel}>Address</Text>
            <TextInput
              style={styles.input}
              placeholder="123 Main St"
              placeholderTextColor="#8E8E93"
              value={newStore.address}
              onChangeText={(text) => setNewStore({ ...newStore, address: text })}
            />
            
            <View style={styles.row}>
              <View style={styles.halfInput}>
                <Text style={styles.inputLabel}>City</Text>
                <TextInput
                  style={styles.input}
                  placeholder="Salt Lake City"
                  placeholderTextColor="#8E8E93"
                  value={newStore.city}
                  onChangeText={(text) => setNewStore({ ...newStore, city: text })}
                />
              </View>
              <View style={styles.halfInput}>
                <Text style={styles.inputLabel}>State</Text>
                <TextInput
                  style={styles.input}
                  placeholder="UT"
                  placeholderTextColor="#8E8E93"
                  value={newStore.state}
                  onChangeText={(text) => setNewStore({ ...newStore, state: text })}
                  maxLength={2}
                  autoCapitalize="characters"
                />
              </View>
            </View>
          </ScrollView>
        </SafeAreaView>
      </Modal>
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
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#2C2C2E',
  },
  backButton: {
    padding: 4,
  },
  title: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#FFF',
  },
  addButton: {
    padding: 4,
  },
  orgSelector: {
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#2C2C2E',
  },
  orgScroll: {
    paddingHorizontal: 16,
  },
  orgChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: '#1C1C1E',
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: 20,
    marginRight: 8,
  },
  orgChipActive: {
    backgroundColor: '#007AFF',
  },
  orgText: {
    fontSize: 14,
    color: '#8E8E93',
  },
  orgTextActive: {
    color: '#FFF',
    fontWeight: '600',
  },
  listContent: {
    padding: 16,
  },
  storeCard: {
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 14,
    marginBottom: 10,
  },
  storeCardContent: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  storeHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 12,
  },
  storeIcon: {
    width: 44,
    height: 44,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  storeInfo: {
    flex: 1,
  },
  storeNameRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  storeName: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFF',
  },
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  storeLocation: {
    fontSize: 13,
    color: '#8E8E93',
    marginTop: 2,
  },
  orgNameLabel: {
    fontSize: 12,
    color: '#007AFF',
    marginTop: 2,
  },
  storeActions: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  actionButton: {
    padding: 8,
  },
  deleteButton: {
    padding: 8,
  },
  storeStats: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  statusBadge: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 8,
  },
  statusText: {
    fontSize: 12,
    fontWeight: '600',
  },
  emptyContainer: {
    alignItems: 'center',
    paddingVertical: 48,
  },
  emptyText: {
    fontSize: 18,
    color: '#8E8E93',
    marginTop: 16,
    marginBottom: 24,
  },
  createButton: {
    backgroundColor: '#007AFF',
    paddingHorizontal: 24,
    paddingVertical: 12,
    borderRadius: 12,
  },
  createButtonText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFF',
  },
  // Modal styles
  modalContainer: {
    flex: 1,
    backgroundColor: '#000',
  },
  modalHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#2C2C2E',
  },
  modalCancel: {
    fontSize: 17,
    color: '#007AFF',
  },
  modalTitle: {
    fontSize: 17,
    fontWeight: '600',
    color: '#FFF',
  },
  modalSave: {
    fontSize: 17,
    fontWeight: '600',
    color: '#007AFF',
  },
  modalContent: {
    padding: 16,
  },
  inputLabel: {
    fontSize: 13,
    fontWeight: '600',
    color: '#8E8E93',
    marginBottom: 8,
    marginTop: 16,
  },
  input: {
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 16,
    fontSize: 16,
    color: '#FFF',
    borderWidth: 1,
    borderColor: '#2C2C2E',
  },
  row: {
    flexDirection: 'row',
    gap: 12,
  },
  halfInput: {
    flex: 1,
  },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 12,
    paddingHorizontal: 4,
    marginTop: 8,
  },
  sectionTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: '#8E8E93',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  sectionCount: {
    fontSize: 14,
    fontWeight: '600',
    color: '#8E8E93',
  },
  sectionDivider: {
    height: 1,
    backgroundColor: '#2C2C2E',
    marginVertical: 24,
    marginHorizontal: 16,
  },
  inactiveCard: {
    opacity: 0.6,
    backgroundColor: '#1A1A1A',
  },
  inactiveText: {
    color: '#8E8E93',
  },
});
