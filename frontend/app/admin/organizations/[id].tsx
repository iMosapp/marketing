import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useLocalSearchParams, useRouter, useFocusEffect } from 'expo-router';
import api from '../../../services/api';
import { showSimpleAlert, showConfirm } from '../../../services/alert';

interface Organization {
  _id: string;
  name: string;
  account_type: string;
  admin_email?: string;
  admin_phone?: string;
  city?: string;
  state?: string;
  active: boolean;
}

interface UserInfo {
  _id: string;
  name: string;
  email: string;
  role: string;
  is_active: boolean;
}

interface StoreInfo {
  _id: string;
  name: string;
  phone?: string;
  city?: string;
  state?: string;
  active: boolean;
  user_count: number;
  users: UserInfo[];
}

interface HierarchyData {
  organization: Organization;
  admins: UserInfo[];
  stores: StoreInfo[];
  unassigned_users: UserInfo[];
  stats: {
    total_stores: number;
    total_users: number;
    total_admins: number;
    unassigned_count: number;
  };
}

const ROLE_COLORS: Record<string, string> = {
  super_admin: '#FF3B30',
  org_admin: '#FF9500',
  store_manager: '#34C759',
  user: '#007AFF',
};

const ROLE_LABELS: Record<string, string> = {
  super_admin: 'Super Admin',
  org_admin: 'Org Admin',
  store_manager: 'Manager',
  user: 'Sales Rep',
};

export default function OrganizationDetailScreen() {
  const router = useRouter();
  const { id } = useLocalSearchParams();
  
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [hierarchy, setHierarchy] = useState<HierarchyData | null>(null);
  const [editMode, setEditMode] = useState(false);
  const [editedOrg, setEditedOrg] = useState<Partial<Organization>>({});
  const [expandedStores, setExpandedStores] = useState<Set<string>>(new Set());
  
  // Link existing account/user
  const [showLinkStore, setShowLinkStore] = useState(false);
  const [availableStores, setAvailableStores] = useState<any[]>([]);
  const [loadingStores, setLoadingStores] = useState(false);
  const [showLinkUser, setShowLinkUser] = useState(false);
  const [availableUsers, setAvailableUsers] = useState<any[]>([]);
  const [loadingUsers, setLoadingUsers] = useState(false);
  const [linkSearch, setLinkSearch] = useState('');
  
  useFocusEffect(
    useCallback(() => {
      loadHierarchy();
    }, [id])
  );
  
  const loadHierarchy = async () => {
    try {
      setLoading(true);
      const response = await api.get(`/admin/hierarchy/organization/${id}`);
      setHierarchy(response.data);
      setEditedOrg(response.data.organization);
    } catch (error) {
      console.error('Failed to load organization:', error);
      showSimpleAlert('Error', 'Failed to load organization details');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };
  
  const onRefresh = () => {
    setRefreshing(true);
    loadHierarchy();
  };
  
  const toggleStoreExpanded = (storeId: string) => {
    const newExpanded = new Set(expandedStores);
    if (newExpanded.has(storeId)) {
      newExpanded.delete(storeId);
    } else {
      newExpanded.add(storeId);
    }
    setExpandedStores(newExpanded);
  };
  
  const handleSave = async () => {
    setSaving(true);
    try {
      await api.put(`/admin/organizations/${id}`, editedOrg);
      showSimpleAlert('Success', 'Organization updated successfully');
      loadHierarchy();
      setEditMode(false);
    } catch (error) {
      showSimpleAlert('Error', 'Failed to update organization');
    } finally {
      setSaving(false);
    }
  };
  
  const handleToggleActive = () => {
    if (!hierarchy) return;
    const newStatus = !hierarchy.organization.active;
    showConfirm(
      newStatus ? 'Activate Organization' : 'Deactivate Organization',
      `Are you sure you want to ${newStatus ? 'activate' : 'deactivate'} this organization?`,
      async () => {
        try {
          await api.put(`/admin/organizations/${id}`, { active: newStatus });
          loadHierarchy();
          showSimpleAlert('Success', `Organization ${newStatus ? 'activated' : 'deactivated'}`);
        } catch (error) {
          showSimpleAlert('Error', 'Failed to update organization status');
        }
      }
    );
  };
  
  const handleToggleUserActive = (user: UserInfo) => {
    const newStatus = !user.is_active;
    showConfirm(
      newStatus ? 'Activate User' : 'Deactivate User',
      `Are you sure you want to ${newStatus ? 'activate' : 'deactivate'} ${user.name}?`,
      async () => {
        try {
          await api.put(`/admin/users/${user._id}`, { is_active: newStatus });
          loadHierarchy();
        } catch (error) {
          showSimpleAlert('Error', 'Failed to update user status');
        }
      }
    );
  };
  
  const handleToggleStoreActive = (store: StoreInfo) => {
    const newStatus = !store.active;
    showConfirm(
      newStatus ? 'Activate Account' : 'Deactivate Account',
      `Are you sure you want to ${newStatus ? 'activate' : 'deactivate'} ${store.name}?`,
      async () => {
        try {
          await api.put(`/admin/stores/${store._id}`, { active: newStatus });
          loadHierarchy();
        } catch (error) {
          showSimpleAlert('Error', 'Failed to update account status');
        }
      }
    );
  };
  
  const renderUserBadge = (user: UserInfo, small = false) => (
    <TouchableOpacity 
      key={user._id} 
      style={[styles.userBadge, small && styles.userBadgeSmall]}
      onPress={() => router.push(`/admin/users/${user._id}`)}
      data-testid={`user-badge-${user._id}`}
    >
      <View style={[styles.userBadgeAvatar, { backgroundColor: ROLE_COLORS[user.role] + '30' }]}>
        <Text style={[styles.userBadgeInitials, { color: ROLE_COLORS[user.role] }]}>
          {user.name?.split(' ').map(n => n[0]).join('').substring(0, 2) || '?'}
        </Text>
      </View>
      <View style={styles.userBadgeInfo}>
        <Text style={styles.userBadgeName} numberOfLines={1}>{user.name}</Text>
        <Text style={styles.userBadgeRole}>{ROLE_LABELS[user.role] || user.role}</Text>
      </View>
      <TouchableOpacity 
        style={[styles.userStatusDot, { backgroundColor: user.is_active ? '#34C759' : '#FF3B30' }]}
        onPress={(e) => {
          e.stopPropagation();
          handleToggleUserActive(user);
        }}
      />
      <Ionicons name="chevron-forward" size={16} color="#8E8E93" style={{ marginLeft: 4 }} />
    </TouchableOpacity>
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
  
  if (!hierarchy) {
    return (
      <SafeAreaView style={styles.container} edges={['top']}>
        <View style={styles.header}>
          <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
            <Ionicons name="chevron-back" size={28} color="#007AFF" />
          </TouchableOpacity>
          <Text style={styles.title}>Organization</Text>
          <View style={{ width: 40 }} />
        </View>
        <View style={styles.errorContainer}>
          <Ionicons name="alert-circle" size={48} color="#FF3B30" />
          <Text style={styles.errorText}>Organization not found</Text>
        </View>
      </SafeAreaView>
    );
  }
  
  const org = hierarchy.organization;
  
  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <KeyboardAvoidingView 
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={{ flex: 1 }}
      >
        {/* Header */}
        <View style={styles.header}>
          <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
            <Ionicons name="chevron-back" size={28} color="#007AFF" />
          </TouchableOpacity>
          <Text style={styles.title} numberOfLines={1}>{org.name}</Text>
          {editMode ? (
            <TouchableOpacity onPress={handleSave} disabled={saving}>
              {saving ? (
                <ActivityIndicator size="small" color="#007AFF" />
              ) : (
                <Text style={styles.saveButton}>Save</Text>
              )}
            </TouchableOpacity>
          ) : (
            <TouchableOpacity onPress={() => setEditMode(true)}>
              <Text style={styles.editButton}>Edit</Text>
            </TouchableOpacity>
          )}
        </View>
        
        <ScrollView 
          style={styles.content} 
          keyboardShouldPersistTaps="handled"
          refreshControl={
            <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#007AFF" />
          }
        >
          {/* Status Card */}
          <View style={styles.statusCard}>
            <View style={styles.statusRow}>
              <Text style={styles.statusLabel}>Status</Text>
              <TouchableOpacity 
                style={[styles.statusBadge, { backgroundColor: org.active ? '#34C75920' : '#FF3B3020' }]}
                onPress={handleToggleActive}
              >
                <View style={[styles.statusDot, { backgroundColor: org.active ? '#34C759' : '#FF3B30' }]} />
                <Text style={[styles.statusText, { color: org.active ? '#34C759' : '#FF3B30' }]}>
                  {org.active ? 'Active' : 'Inactive'}
                </Text>
              </TouchableOpacity>
            </View>
            <View style={styles.statsRow}>
              <View style={styles.statItem}>
                <Ionicons name="storefront" size={20} color="#007AFF" />
                <Text style={styles.statValue}>{hierarchy.stats.total_stores}</Text>
                <Text style={styles.statLabel}>Accounts</Text>
              </View>
              <View style={styles.statItem}>
                <Ionicons name="people" size={20} color="#007AFF" />
                <Text style={styles.statValue}>{hierarchy.stats.total_users}</Text>
                <Text style={styles.statLabel}>Users</Text>
              </View>
              <View style={styles.statItem}>
                <Ionicons name="shield" size={20} color="#FF9500" />
                <Text style={styles.statValue}>{hierarchy.stats.total_admins}</Text>
                <Text style={styles.statLabel}>Admins</Text>
              </View>
            </View>
          </View>
          
          {/* Stores Section - FIRST */}
          <View style={styles.section}>
            <View style={styles.sectionHeader}>
              <Ionicons name="storefront" size={20} color="#34C759" />
              <Text style={styles.sectionTitle}>Accounts ({hierarchy.stores.length})</Text>
              <TouchableOpacity 
                style={styles.addButton}
                onPress={() => router.push(`/admin/stores?org=${id}`)}
              >
                <Ionicons name="add-circle" size={24} color="#007AFF" />
              </TouchableOpacity>
            </View>
            
            {hierarchy.stores.length === 0 ? (
              <View style={styles.emptySection}>
                <Text style={styles.emptyText}>No accounts yet</Text>
                <TouchableOpacity 
                  style={styles.createButton}
                  onPress={() => router.push(`/admin/stores?org=${id}`)}
                >
                  <Text style={styles.createButtonText}>Create Account</Text>
                </TouchableOpacity>
              </View>
            ) : (
              hierarchy.stores.map(store => (
                <TouchableOpacity 
                  key={store._id} 
                  style={styles.storeCard}
                  onPress={() => router.push(`/admin/stores/${store._id}`)}
                >
                  <View style={styles.storeIcon}>
                    <Ionicons name="storefront" size={24} color="#34C759" />
                  </View>
                  <View style={styles.storeInfo}>
                    <Text style={styles.storeName}>{store.name}</Text>
                    <Text style={styles.storeLocation}>
                      {[store.city, store.state].filter(Boolean).join(', ') || 'No location'}
                    </Text>
                  </View>
                  <View style={styles.storeStats}>
                    <View style={styles.userCountBadge}>
                      <Ionicons name="people" size={14} color="#8E8E93" />
                      <Text style={styles.userCountText}>{store.user_count}</Text>
                    </View>
                    <View style={[styles.storeStatusBadge, { backgroundColor: store.active ? '#34C75920' : '#FF3B3020' }]}>
                      <Text style={[styles.storeStatusText, { color: store.active ? '#34C759' : '#FF3B30' }]}>
                        {store.active ? 'Active' : 'Inactive'}
                      </Text>
                    </View>
                  </View>
                  <Ionicons name="chevron-forward" size={20} color="#8E8E93" />
                </TouchableOpacity>
              ))
            )}
          </View>
          
          {/* Org Admins Section */}
          {hierarchy.admins.length > 0 && (
            <View style={styles.section}>
              <View style={styles.sectionHeader}>
                <Ionicons name="shield" size={20} color="#FF9500" />
                <Text style={styles.sectionTitle}>Admins ({hierarchy.admins.length})</Text>
              </View>
              <View style={styles.userList}>
                {hierarchy.admins.map(admin => renderUserBadge(admin))}
              </View>
            </View>
          )}
          
          {/* Store Managers Section */}
          {hierarchy.stores.some(s => s.users?.some(u => u.role === 'store_manager')) && (
            <View style={styles.section}>
              <View style={styles.sectionHeader}>
                <Ionicons name="briefcase" size={20} color="#34C759" />
                <Text style={styles.sectionTitle}>Managers</Text>
              </View>
              <View style={styles.userList}>
                {hierarchy.stores.flatMap(s => s.users?.filter(u => u.role === 'store_manager') || [])
                  .filter((user, index, self) => self.findIndex(u => u._id === user._id) === index)
                  .map(manager => renderUserBadge(manager))}
              </View>
            </View>
          )}
          
          {/* Sales Reps Section */}
          {hierarchy.stores.some(s => s.users?.some(u => u.role === 'user')) && (
            <View style={styles.section}>
              <View style={styles.sectionHeader}>
                <Ionicons name="people" size={20} color="#007AFF" />
                <Text style={styles.sectionTitle}>Sales Reps</Text>
              </View>
              <View style={styles.userList}>
                {hierarchy.stores.flatMap(s => s.users?.filter(u => u.role === 'user') || [])
                  .filter((user, index, self) => self.findIndex(u => u._id === user._id) === index)
                  .map(rep => renderUserBadge(rep))}
              </View>
            </View>
          )}
          
          {/* Unassigned Users Section */}
          {hierarchy.unassigned_users.length > 0 && (
            <View style={styles.section}>
              <View style={styles.sectionHeader}>
                <Ionicons name="person-add" size={20} color="#FF9500" />
                <Text style={styles.sectionTitle}>Unassigned Users ({hierarchy.unassigned_users.length})</Text>
              </View>
              <View style={styles.userList}>
                {hierarchy.unassigned_users.map(user => renderUserBadge(user))}
              </View>
              <Text style={styles.hintText}>These users are in the org but not assigned to any account</Text>
            </View>
          )}
          
          {/* Details Section (Collapsible Edit) */}
          {editMode && (
            <View style={styles.section}>
              <Text style={styles.sectionTitle}>Edit Organization Details</Text>
              
              <Text style={styles.inputLabel}>Name</Text>
              <TextInput
                style={styles.input}
                value={editedOrg.name}
                onChangeText={(text) => setEditedOrg({ ...editedOrg, name: text })}
                placeholder="Organization name"
                placeholderTextColor="#8E8E93"
              />
              
              <Text style={styles.inputLabel}>Admin Email</Text>
              <TextInput
                style={styles.input}
                value={editedOrg.admin_email}
                onChangeText={(text) => setEditedOrg({ ...editedOrg, admin_email: text })}
                placeholder="admin@company.com"
                placeholderTextColor="#8E8E93"
                keyboardType="email-address"
                autoCapitalize="none"
              />
              
              <Text style={styles.inputLabel}>Admin Phone</Text>
              <TextInput
                style={styles.input}
                value={editedOrg.admin_phone}
                onChangeText={(text) => setEditedOrg({ ...editedOrg, admin_phone: text })}
                placeholder="+1 (555) 123-4567"
                placeholderTextColor="#8E8E93"
                keyboardType="phone-pad"
              />
              
              <View style={styles.row}>
                <View style={styles.halfField}>
                  <Text style={styles.inputLabel}>City</Text>
                  <TextInput
                    style={styles.input}
                    value={editedOrg.city}
                    onChangeText={(text) => setEditedOrg({ ...editedOrg, city: text })}
                    placeholder="City"
                    placeholderTextColor="#8E8E93"
                  />
                </View>
                <View style={styles.halfField}>
                  <Text style={styles.inputLabel}>State</Text>
                  <TextInput
                    style={styles.input}
                    value={editedOrg.state}
                    onChangeText={(text) => setEditedOrg({ ...editedOrg, state: text })}
                    placeholder="State"
                    placeholderTextColor="#8E8E93"
                    maxLength={2}
                    autoCapitalize="characters"
                  />
                </View>
              </View>
              
              <TouchableOpacity 
                style={styles.cancelButton}
                onPress={() => {
                  setEditMode(false);
                  setEditedOrg(org);
                }}
              >
                <Text style={styles.cancelButtonText}>Cancel</Text>
              </TouchableOpacity>
            </View>
          )}
          
          {/* Quick Actions */}
          {!editMode && (
            <View style={styles.section}>
              <Text style={styles.sectionTitle}>Quick Actions</Text>
              
              <TouchableOpacity 
                style={styles.actionButton}
                onPress={() => router.push(`/admin/stores?org=${id}`)}
              >
                <Ionicons name="storefront" size={20} color="#007AFF" />
                <Text style={styles.actionText}>Manage All Stores</Text>
                <Ionicons name="chevron-forward" size={20} color="#8E8E93" />
              </TouchableOpacity>
              
              <TouchableOpacity 
                style={styles.actionButton}
                onPress={() => router.push(`/admin/users?org=${id}`)}
              >
                <Ionicons name="people" size={20} color="#007AFF" />
                <Text style={styles.actionText}>Manage All Users</Text>
                <Ionicons name="chevron-forward" size={20} color="#8E8E93" />
              </TouchableOpacity>
            </View>
          )}
          
          <View style={{ height: 50 }} />
        </ScrollView>
      </KeyboardAvoidingView>
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
  errorContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    gap: 12,
  },
  errorText: {
    fontSize: 16,
    color: '#8E8E93',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#2C2C2E',
  },
  backButton: {
    width: 40,
  },
  title: {
    fontSize: 17,
    fontWeight: '600',
    color: '#FFF',
    flex: 1,
    textAlign: 'center',
  },
  editButton: {
    fontSize: 17,
    color: '#007AFF',
  },
  saveButton: {
    fontSize: 17,
    color: '#007AFF',
    fontWeight: '600',
  },
  content: {
    flex: 1,
    padding: 16,
  },
  statusCard: {
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 16,
    marginBottom: 20,
  },
  statusRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
  },
  statusLabel: {
    fontSize: 15,
    color: '#8E8E93',
  },
  statusBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 6,
    paddingHorizontal: 12,
    borderRadius: 12,
    gap: 6,
  },
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  statusText: {
    fontSize: 14,
    fontWeight: '600',
  },
  statsRow: {
    flexDirection: 'row',
    justifyContent: 'space-around',
  },
  statItem: {
    alignItems: 'center',
    gap: 4,
  },
  statValue: {
    fontSize: 24,
    fontWeight: '700',
    color: '#FFF',
  },
  statLabel: {
    fontSize: 12,
    color: '#8E8E93',
  },
  section: {
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 16,
    marginBottom: 20,
  },
  sectionTitle: {
    fontSize: 13,
    fontWeight: '600',
    color: '#8E8E93',
    textTransform: 'uppercase',
    marginBottom: 16,
  },
  inputLabel: {
    fontSize: 13,
    color: '#8E8E93',
    marginBottom: 6,
    marginTop: 12,
  },
  input: {
    backgroundColor: '#2C2C2E',
    borderRadius: 8,
    padding: 12,
    fontSize: 16,
    color: '#FFF',
  },
  fieldValue: {
    fontSize: 16,
    color: '#FFF',
    paddingVertical: 8,
  },
  row: {
    flexDirection: 'row',
    gap: 12,
  },
  halfField: {
    flex: 1,
  },
  actionButton: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 14,
    borderBottomWidth: 1,
    borderBottomColor: '#2C2C2E',
    gap: 12,
  },
  actionText: {
    flex: 1,
    fontSize: 16,
    color: '#FFF',
  },
  cancelButton: {
    alignItems: 'center',
    paddingVertical: 14,
    marginTop: 8,
  },
  cancelButtonText: {
    fontSize: 16,
    color: '#FF3B30',
  },
  // Section Header
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 12,
  },
  addButton: {
    marginLeft: 'auto',
  },
  // User Badge
  userList: {
    gap: 8,
  },
  userBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#2C2C2E',
    borderRadius: 10,
    padding: 10,
    gap: 10,
  },
  userBadgeSmall: {
    padding: 8,
    marginBottom: 6,
  },
  userBadgeAvatar: {
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: 'center',
    justifyContent: 'center',
  },
  userBadgeInitials: {
    fontSize: 13,
    fontWeight: '700',
  },
  userBadgeInfo: {
    flex: 1,
  },
  userBadgeName: {
    fontSize: 14,
    fontWeight: '600',
    color: '#FFF',
  },
  userBadgeRole: {
    fontSize: 11,
    color: '#8E8E93',
    marginTop: 1,
  },
  userStatusDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
  },
  // Store Card
  storeCard: {
    backgroundColor: '#2C2C2E',
    borderRadius: 12,
    marginBottom: 8,
    overflow: 'hidden',
  },
  storeHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 12,
    gap: 10,
  },
  storeIcon: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: '#34C75920',
    alignItems: 'center',
    justifyContent: 'center',
  },
  storeInfo: {
    flex: 1,
  },
  storeName: {
    fontSize: 15,
    fontWeight: '600',
    color: '#FFF',
  },
  storeLocation: {
    fontSize: 12,
    color: '#8E8E93',
    marginTop: 2,
  },
  storeStats: {
    alignItems: 'flex-end',
    gap: 4,
  },
  userCountBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  userCountText: {
    fontSize: 13,
    color: '#8E8E93',
    fontWeight: '600',
  },
  storeStatusBadge: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 8,
  },
  storeStatusText: {
    fontSize: 10,
    fontWeight: '700',
  },
  storeUsers: {
    borderTopWidth: 1,
    borderTopColor: '#3C3C3E',
    padding: 12,
  },
  noUsersText: {
    color: '#8E8E93',
    fontSize: 13,
    fontStyle: 'italic',
    textAlign: 'center',
    paddingVertical: 8,
  },
  manageStoreButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 10,
    marginTop: 8,
    gap: 4,
  },
  manageStoreButtonText: {
    color: '#007AFF',
    fontSize: 14,
    fontWeight: '600',
  },
  // Empty section
  emptySection: {
    alignItems: 'center',
    paddingVertical: 20,
  },
  emptyText: {
    color: '#8E8E93',
    fontSize: 14,
    marginBottom: 12,
  },
  createButton: {
    backgroundColor: '#007AFF',
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 8,
  },
  createButtonText: {
    color: '#FFF',
    fontSize: 14,
    fontWeight: '600',
  },
  hintText: {
    fontSize: 12,
    color: '#8E8E93',
    fontStyle: 'italic',
    marginTop: 8,
    textAlign: 'center',
  },
});
