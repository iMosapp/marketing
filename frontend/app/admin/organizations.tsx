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
  KeyboardAvoidingView,
  Platform,
  ScrollView,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import api, { adminAPI } from '../../services/api';
import { showAlert, showSimpleAlert, showConfirm } from '../../services/alert';
import { WebSafeButton } from '../../components/WebSafeButton';

export default function OrganizationsScreen() {
  const router = useRouter();
  
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [organizations, setOrganizations] = useState<any[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [showSearch, setShowSearch] = useState(false);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [creating, setCreating] = useState(false);
  const [newOrg, setNewOrg] = useState({
    name: '',
    account_type: 'organization',
    admin_email: '',
    admin_phone: '',
    city: '',
    state: '',
    country: 'US',
  });
  
  useFocusEffect(
    useCallback(() => {
      loadOrganizations();
    }, [])
  );
  
  const loadOrganizations = async () => {
    try {
      setLoading(true);
      // Use hierarchy overview endpoint to get counts
      const response = await api.get('/admin/hierarchy/overview');
      setOrganizations(response.data.organizations);
    } catch (error) {
      console.error('Failed to load organizations:', error);
    } finally {
      setLoading(false);
    }
  };
  
  const onRefresh = async () => {
    setRefreshing(true);
    await loadOrganizations();
    setRefreshing(false);
  };
  
  const handleCreateOrg = async () => {
    if (!newOrg.name || !newOrg.admin_email) {
      showSimpleAlert('Error', 'Name and admin email are required');
      return;
    }
    
    setCreating(true);
    try {
      await adminAPI.createOrganization(newOrg);
      showSimpleAlert('Success', 'Organization created successfully');
      setShowCreateModal(false);
      setNewOrg({
        name: '',
        account_type: 'organization',
        admin_email: '',
        admin_phone: '',
        city: '',
        state: '',
        country: 'US',
      });
      loadOrganizations();
    } catch (error: any) {
      const message = error?.response?.data?.detail || 'Failed to create organization';
      showSimpleAlert('Error', message);
    } finally {
      setCreating(false);
    }
  };
  
  const handleDeleteOrg = (org: any) => {
    showConfirm(
      'Delete Organization',
      `Are you sure you want to delete "${org.name}"? This will also delete all stores and user associations.`,
      async () => {
        try {
          await adminAPI.deleteOrganization(org._id);
          loadOrganizations();
        } catch (error) {
          showSimpleAlert('Error', 'Failed to delete organization');
        }
      },
      undefined,
      'Delete',
      'Cancel'
    );
  };
  
  const handleToggleActive = (org: any) => {
    const newStatus = !org.active;
    showConfirm(
      newStatus ? 'Activate Organization' : 'Deactivate Organization',
      `Are you sure you want to ${newStatus ? 'activate' : 'deactivate'} "${org.name}"?`,
      async () => {
        try {
          await api.put(`/admin/organizations/${org._id}`, { active: newStatus });
          loadOrganizations();
          showSimpleAlert('Success', `Organization ${newStatus ? 'activated' : 'deactivated'}`);
        } catch (error) {
          showSimpleAlert('Error', 'Failed to update organization status');
        }
      },
      undefined,
      newStatus ? 'Activate' : 'Deactivate',
      'Cancel'
    );
  };

  // Filter organizations based on search query
  const filteredOrganizations = organizations.filter((org) => {
    if (!searchQuery.trim()) return true;
    const query = searchQuery.toLowerCase();
    return (
      org.name?.toLowerCase().includes(query) ||
      org.admin_email?.toLowerCase().includes(query) ||
      org.city?.toLowerCase().includes(query) ||
      org.state?.toLowerCase().includes(query)
    );
  });
  
  const renderOrganization = ({ item }: { item: any }) => (
    <TouchableOpacity 
      style={styles.orgCard}
      onPress={() => router.push(`/admin/organizations/${item._id}`)}
    >
      <View style={styles.orgHeader}>
        <View style={[styles.orgIcon, { backgroundColor: item.account_type === 'independent' ? '#FF950020' : '#007AFF20' }]}>
          <Ionicons 
            name={item.account_type === 'independent' ? 'person' : 'business'} 
            size={24} 
            color={item.account_type === 'independent' ? '#FF9500' : '#007AFF'} 
          />
        </View>
        <View style={styles.orgInfo}>
          <Text style={styles.orgName}>{item.name}</Text>
          <Text style={styles.orgType}>
            {item.account_type === 'independent' ? 'Independent' : 'Organization'}
          </Text>
        </View>
        <TouchableOpacity 
          onPress={() => handleDeleteOrg(item)}
          style={styles.deleteButton}
        >
          <Ionicons name="trash-outline" size={20} color="#FF3B30" />
        </TouchableOpacity>
      </View>
      
      <View style={styles.orgStats}>
        <View style={styles.statItem}>
          <Ionicons name="storefront-outline" size={16} color="#8E8E93" />
          <Text style={styles.statText}>{item.store_count || 0} stores</Text>
        </View>
        <View style={styles.statItem}>
          <Ionicons name="people-outline" size={16} color="#8E8E93" />
          <Text style={styles.statText}>{item.user_count || 0} users</Text>
        </View>
        <View style={styles.statItem}>
          <Ionicons name="location-outline" size={16} color="#8E8E93" />
          <Text style={styles.statText}>{item.city || 'N/A'}, {item.state || 'N/A'}</Text>
        </View>
      </View>
      
      <View style={styles.orgFooter}>
        <TouchableOpacity 
          style={[styles.statusBadge, { backgroundColor: item.active ? '#34C75920' : '#FF3B3020' }]}
          onPress={() => handleToggleActive(item)}
        >
          <Text style={[styles.statusText, { color: item.active ? '#34C759' : '#FF3B30' }]}>
            {item.active ? 'Active' : 'Inactive'}
          </Text>
        </TouchableOpacity>
        <View style={[styles.statusBadge, { backgroundColor: '#8E8E9320' }]}>
          <Text style={[styles.statusText, { color: '#8E8E93' }]}>
            10DLC: {item.ten_dlc_status || 'Pending'}
          </Text>
        </View>
      </View>
    </TouchableOpacity>
  );
  
  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="chevron-back" size={28} color="#007AFF" />
        </TouchableOpacity>
        <Text style={styles.title}>Organizations</Text>
        <View style={styles.headerActions}>
          <TouchableOpacity onPress={() => setShowSearch(!showSearch)} style={styles.searchButton}>
            <Ionicons name="search" size={24} color="#007AFF" />
          </TouchableOpacity>
          <TouchableOpacity onPress={() => setShowCreateModal(true)} style={styles.addButton}>
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
              placeholder="Search by name, email, city..."
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
              {filteredOrganizations.length} result{filteredOrganizations.length !== 1 ? 's' : ''}
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
          data={filteredOrganizations}
          renderItem={renderOrganization}
          keyExtractor={(item) => item._id}
          contentContainerStyle={styles.listContent}
          refreshControl={
            <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#007AFF" />
          }
          ListEmptyComponent={() => (
            <View style={styles.emptyContainer}>
              <Ionicons name="business-outline" size={64} color="#2C2C2E" />
              <Text style={styles.emptyText}>
                {searchQuery ? 'No organizations found' : 'No organizations yet'}
              </Text>
              {searchQuery ? (
                <Text style={styles.emptySubtext}>Try a different search term</Text>
              ) : (
                <TouchableOpacity 
                  style={styles.createButton}
                  onPress={() => setShowCreateModal(true)}
                >
                  <Text style={styles.createButtonText}>Create Organization</Text>
                </TouchableOpacity>
              )}
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
        <KeyboardAvoidingView 
          behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
          style={{ flex: 1 }}
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
              <Text style={styles.modalTitle}>New Organization</Text>
              <WebSafeButton
                onPress={handleCreateOrg}
                disabled={creating}
                loading={creating}
                variant="ghost"
                testID="modal-create"
              >
                <Text style={styles.modalSave}>Create</Text>
              </WebSafeButton>
            </View>
            
            <ScrollView style={styles.modalContent} keyboardShouldPersistTaps="handled">
              {/* Account Type */}
              <Text style={styles.inputLabel}>Account Type</Text>
              <View style={styles.typeSelector}>
                <WebSafeButton
                  onPress={() => setNewOrg({ ...newOrg, account_type: 'organization' })}
                  variant={newOrg.account_type === 'organization' ? 'primary' : 'secondary'}
                  testID="org-type-organization"
                  style={{ flex: 1 }}
                >
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                    <Ionicons name="business" size={20} color="#FFF" />
                    <Text style={{ color: '#FFF', fontWeight: '600' }}>Organization</Text>
                  </View>
                </WebSafeButton>
                <WebSafeButton
                  onPress={() => setNewOrg({ ...newOrg, account_type: 'independent' })}
                  variant={newOrg.account_type === 'independent' ? 'primary' : 'secondary'}
                  testID="org-type-independent"
                  style={{ flex: 1 }}
                >
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                    <Ionicons name="person" size={20} color="#FFF" />
                    <Text style={{ color: '#FFF', fontWeight: '600' }}>Independent</Text>
                  </View>
                </WebSafeButton>
              </View>
              
              <Text style={styles.inputLabel}>{newOrg.account_type === 'independent' ? "Independent's Name *" : "Organization Name *"}</Text>
              <TextInput
                style={styles.input}
                placeholder={newOrg.account_type === 'independent' ? "e.g., John Smith" : "e.g., Ken Garff Auto Group"}
                placeholderTextColor="#8E8E93"
                value={newOrg.name}
                onChangeText={(text) => setNewOrg({ ...newOrg, name: text })}
              />
              
              <Text style={styles.inputLabel}>Admin Email *</Text>
              <TextInput
                style={styles.input}
                placeholder="admin@company.com"
                placeholderTextColor="#8E8E93"
                value={newOrg.admin_email}
                onChangeText={(text) => setNewOrg({ ...newOrg, admin_email: text })}
                keyboardType="email-address"
                autoCapitalize="none"
              />
              
              <Text style={styles.inputLabel}>Admin Phone</Text>
              <TextInput
                style={styles.input}
                placeholder="+1 (555) 123-4567"
                placeholderTextColor="#8E8E93"
                value={newOrg.admin_phone}
                onChangeText={(text) => setNewOrg({ ...newOrg, admin_phone: text })}
                keyboardType="phone-pad"
              />
              
              <View style={styles.row}>
                <View style={styles.halfInput}>
                  <Text style={styles.inputLabel}>City</Text>
                  <TextInput
                    style={styles.input}
                    placeholder="Salt Lake City"
                    placeholderTextColor="#8E8E93"
                    value={newOrg.city}
                    onChangeText={(text) => setNewOrg({ ...newOrg, city: text })}
                  />
                </View>
                <View style={styles.halfInput}>
                  <Text style={styles.inputLabel}>State</Text>
                  <TextInput
                    style={styles.input}
                    placeholder="UT"
                    placeholderTextColor="#8E8E93"
                    value={newOrg.state}
                    onChangeText={(text) => setNewOrg({ ...newOrg, state: text })}
                    maxLength={2}
                    autoCapitalize="characters"
                  />
                </View>
              </View>
              <View style={{ height: 50 }} />
            </ScrollView>
          </SafeAreaView>
        </KeyboardAvoidingView>
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
  headerActions: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  searchButton: {
    padding: 4,
  },
  searchContainer: {
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#2C2C2E',
  },
  searchBar: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1C1C1E',
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 10,
    gap: 8,
  },
  searchInput: {
    flex: 1,
    fontSize: 16,
    color: '#FFF',
  },
  searchResultCount: {
    fontSize: 13,
    color: '#8E8E93',
    marginTop: 8,
    marginLeft: 4,
  },
  emptySubtext: {
    fontSize: 14,
    color: '#6E6E73',
    marginTop: 8,
  },
  listContent: {
    padding: 16,
  },
  orgCard: {
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: '#2C2C2E',
  },
  orgHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 12,
  },
  orgIcon: {
    width: 48,
    height: 48,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  orgInfo: {
    flex: 1,
  },
  orgName: {
    fontSize: 17,
    fontWeight: '600',
    color: '#FFF',
  },
  orgType: {
    fontSize: 13,
    color: '#8E8E93',
    marginTop: 2,
  },
  deleteButton: {
    padding: 8,
  },
  orgStats: {
    flexDirection: 'row',
    gap: 16,
    marginBottom: 12,
  },
  statItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  statText: {
    fontSize: 13,
    color: '#8E8E93',
  },
  orgFooter: {
    flexDirection: 'row',
    gap: 8,
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
  typeSelector: {
    flexDirection: 'row',
    gap: 12,
  },
  typeButton: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 16,
    borderWidth: 1,
    borderColor: '#2C2C2E',
  },
  typeButtonActive: {
    backgroundColor: '#007AFF',
    borderColor: '#007AFF',
  },
  typeText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#8E8E93',
  },
  typeTextActive: {
    color: '#FFF',
  },
  row: {
    flexDirection: 'row',
    gap: 12,
  },
  halfInput: {
    flex: 1,
  },
});
