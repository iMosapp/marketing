import React, { useState, useCallback } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
  ActivityIndicator,
  RefreshControl,
  Image,
  Modal,
  FlatList,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useLocalSearchParams, useRouter, useFocusEffect } from 'expo-router';
import api from '../../../services/api';
import { showSimpleAlert, showConfirm } from '../../../services/alert';
import { useAuthStore } from '../../../store/authStore';

interface UserDetail {
  _id: string;
  name: string;
  email: string;
  phone?: string;
  role: string;
  is_active: boolean;
  status?: string;
  title?: string;
  bio?: string;
  photo_url?: string;
  organization_id?: string;
  store_ids?: string[];
  twilio_phone_number?: string;
  ai_persona?: any;
  created_at?: string;
  last_login?: string;
  social_links?: Record<string, string>;
}

interface StoreInfo {
  _id: string;
  name: string;
  city?: string;
  state?: string;
}

interface OrgInfo {
  _id: string;
  name: string;
}

interface ProfileCompleteness {
  photo: boolean;
  bio: boolean;
  title: boolean;
  phone: boolean;
  ai_persona: boolean;
  social_links: boolean;
  percentage: number;
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
  store_manager: 'Store Manager',
  user: 'Sales Rep',
};

const AVAILABLE_ROLES = [
  { value: 'user', label: 'Sales Rep', color: '#007AFF' },
  { value: 'store_manager', label: 'Store Manager', color: '#34C759' },
  { value: 'org_admin', label: 'Org Admin', color: '#FF9500' },
];

export default function UserDetailScreen() {
  const router = useRouter();
  const { id } = useLocalSearchParams();
  
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [user, setUser] = useState<UserDetail | null>(null);
  const [organization, setOrganization] = useState<OrgInfo | null>(null);
  const [stores, setStores] = useState<StoreInfo[]>([]);
  const [availableStores, setAvailableStores] = useState<StoreInfo[]>([]);
  const [allOrganizations, setAllOrganizations] = useState<OrgInfo[]>([]);
  const [completeness, setCompleteness] = useState<ProfileCompleteness | null>(null);
  const [showStoreModal, setShowStoreModal] = useState(false);
  const [showRoleModal, setShowRoleModal] = useState(false);
  const [showOrgModal, setShowOrgModal] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [impersonating, setImpersonating] = useState(false);
  
  const { startImpersonation } = useAuthStore();
  
  useFocusEffect(
    useCallback(() => {
      loadUserData();
      loadAllOrganizations();
    }, [id])
  );
  
  const handleImpersonate = async () => {
    if (!user) return;
    
    showConfirm(
      'Impersonate User',
      `You will be logged in as ${user.name}. You can edit their profile and settings. Tap "Exit Impersonation" in the More menu to return to your admin account.`,
      async () => {
        setImpersonating(true);
        try {
          const response = await api.post(`/admin/users/${id}/impersonate`);
          if (response.data.success) {
            await startImpersonation(response.data.user, response.data.token);
            router.replace('/(tabs)/inbox');
          }
        } catch (error) {
          showSimpleAlert('Error', 'Failed to impersonate user');
        } finally {
          setImpersonating(false);
        }
      }
    );
  };
  
  const loadUserData = async () => {
    try {
      setLoading(true);
      const response = await api.get(`/admin/users/${id}/detail`);
      const data = response.data;
      
      if (!data || !data.user) {
        throw new Error('Invalid response from server');
      }
      
      setUser(data.user);
      setOrganization(data.organization || null);
      setStores(data.stores || []);
      setAvailableStores(data.available_stores || []);
      
      // Calculate profile completeness
      const u = data.user;
      const hasSocialLinks = u.social_links && Object.values(u.social_links).some((v: any) => v);
      const checks = {
        photo: !!u.photo_url,
        bio: !!u.bio && u.bio.length > 10,
        title: !!u.title,
        phone: !!u.phone || !!u.twilio_phone_number,
        ai_persona: !!u.ai_persona?.instructions,
        social_links: hasSocialLinks,
      };
      const completed = Object.values(checks).filter(Boolean).length;
      setCompleteness({
        ...checks,
        percentage: Math.round((completed / 6) * 100),
      });
    } catch (error: any) {
      console.error('Failed to load user:', error);
      const errorMessage = error.response?.data?.detail || error.message || 'Failed to load user details';
      showSimpleAlert('Error', errorMessage);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };
  
  const loadAllOrganizations = async () => {
    try {
      const response = await api.get('/admin/organizations');
      setAllOrganizations(response.data);
    } catch (error) {
      console.error('Failed to load organizations:', error);
    }
  };
  
  const onRefresh = () => {
    setRefreshing(true);
    loadUserData();
  };
  
  const handleToggleActive = () => {
    if (!user) return;
    const newStatus = !user.is_active;
    showConfirm(
      newStatus ? 'Activate User' : 'Deactivate User',
      `Are you sure you want to ${newStatus ? 'activate' : 'deactivate'} ${user.name}?`,
      async () => {
        try {
          await api.put(`/admin/users/${id}`, { is_active: newStatus });
          loadUserData();
          showSimpleAlert('Success', `User ${newStatus ? 'activated' : 'deactivated'}`);
        } catch (error) {
          showSimpleAlert('Error', 'Failed to update user status');
        }
      }
    );
  };
  
  const handleChangeOrganization = async (newOrgId: string) => {
    if (!user) return;
    setActionLoading(true);
    try {
      await api.put(`/admin/hierarchy/users/${id}/change-organization`, { organization_id: newOrgId });
      showSimpleAlert('Success', 'User moved to new organization');
      setShowOrgModal(false);
      loadUserData();
    } catch (error: any) {
      showSimpleAlert('Error', error.response?.data?.detail || 'Failed to change organization');
    } finally {
      setActionLoading(false);
    }
  };
  
  const handleAssignStore = async (storeId: string) => {
    setActionLoading(true);
    try {
      await api.put(`/admin/hierarchy/users/${id}/assign-store`, { store_id: storeId });
      showSimpleAlert('Success', 'User assigned to store');
      setShowStoreModal(false);
      loadUserData();
    } catch (error) {
      showSimpleAlert('Error', 'Failed to assign user to store');
    } finally {
      setActionLoading(false);
    }
  };
  
  const handleRemoveFromStore = (store: StoreInfo) => {
    showConfirm(
      'Remove from Store',
      `Remove ${user?.name} from ${store.name}?`,
      async () => {
        try {
          await api.put(`/admin/hierarchy/users/${id}/remove-store`, { store_id: store._id });
          showSimpleAlert('Success', 'User removed from store');
          loadUserData();
        } catch (error) {
          showSimpleAlert('Error', 'Failed to remove user from store');
        }
      }
    );
  };
  
  const handleChangeRole = async (newRole: string) => {
    setActionLoading(true);
    try {
      await api.put(`/admin/hierarchy/users/${id}/role`, { role: newRole });
      showSimpleAlert('Success', 'Role updated');
      setShowRoleModal(false);
      loadUserData();
    } catch (error) {
      showSimpleAlert('Error', 'Failed to update role');
    } finally {
      setActionLoading(false);
    }
  };
  
  const handleDeleteUser = () => {
    if (!user) return;
    showConfirm(
      'Delete User',
      `Are you sure you want to permanently delete "${user.name}"? This action cannot be undone. All their data, conversations, and contacts will be removed.`,
      async () => {
        setActionLoading(true);
        try {
          await api.delete(`/admin/users/${id}`);
          showSimpleAlert('Success', 'User deleted');
          router.back();
        } catch (error: any) {
          showSimpleAlert('Error', error.response?.data?.detail || 'Failed to delete user');
        } finally {
          setActionLoading(false);
        }
      },
      undefined,
      'Delete',
      'Cancel'
    );
  };
  
  const renderCompletenessItem = (label: string, completed: boolean, icon: string) => (
    <View style={styles.completenessItem} key={label}>
      <Ionicons 
        name={completed ? "checkmark-circle" : "ellipse-outline"} 
        size={20} 
        color={completed ? "#34C759" : "#8E8E93"} 
      />
      <Text style={[styles.completenessLabel, !completed && styles.incompleteLabelText]}>
        {label}
      </Text>
      {!completed && (
        <View style={styles.missingBadge}>
          <Text style={styles.missingText}>Missing</Text>
        </View>
      )}
    </View>
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
  
  if (!user) {
    return (
      <SafeAreaView style={styles.container} edges={['top']}>
        <View style={styles.header}>
          <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
            <Ionicons name="chevron-back" size={28} color="#007AFF" />
          </TouchableOpacity>
          <Text style={styles.title}>User</Text>
          <View style={{ width: 40 }} />
        </View>
        <View style={styles.errorContainer}>
          <Ionicons name="alert-circle" size={48} color="#FF3B30" />
          <Text style={styles.errorText}>User not found</Text>
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
        <Text style={styles.title} numberOfLines={1}>User Details</Text>
        <View style={{ width: 40 }} />
      </View>
      
      <ScrollView 
        style={styles.content}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#007AFF" />
        }
      >
        {/* User Profile Card */}
        <View style={styles.profileCard}>
          <View style={styles.profileHeader}>
            {user.photo_url ? (
              <Image source={{ uri: user.photo_url }} style={styles.avatar} />
            ) : (
              <View style={[styles.avatarPlaceholder, { backgroundColor: ROLE_COLORS[user.role] + '30' }]}>
                <Text style={[styles.avatarInitials, { color: ROLE_COLORS[user.role] }]}>
                  {user.name?.split(' ').map(n => n[0]).join('').substring(0, 2) || '?'}
                </Text>
              </View>
            )}
            <View style={styles.profileInfo}>
              <Text style={styles.userName}>{user.name}</Text>
              <Text style={styles.userTitle}>{user.title || 'No title set'}</Text>
              <View style={styles.roleBadgeContainer}>
                <View style={[styles.roleBadge, { backgroundColor: ROLE_COLORS[user.role] + '20' }]}>
                  <Text style={[styles.roleBadgeText, { color: ROLE_COLORS[user.role] }]}>
                    {ROLE_LABELS[user.role] || user.role}
                  </Text>
                </View>
                <TouchableOpacity 
                  style={styles.changeRoleButton}
                  onPress={() => setShowRoleModal(true)}
                >
                  <Ionicons name="pencil" size={14} color="#007AFF" />
                </TouchableOpacity>
              </View>
            </View>
          </View>
          
          {/* Status Toggle */}
          <View style={styles.statusRow}>
            <Text style={styles.statusLabel}>Account Status</Text>
            <TouchableOpacity 
              style={[styles.statusBadge, { backgroundColor: user.is_active ? '#34C75920' : '#FF3B3020' }]}
              onPress={handleToggleActive}
            >
              <View style={[styles.statusDot, { backgroundColor: user.is_active ? '#34C759' : '#FF3B30' }]} />
              <Text style={[styles.statusText, { color: user.is_active ? '#34C759' : '#FF3B30' }]}>
                {user.is_active ? 'Active' : 'Inactive'}
              </Text>
            </TouchableOpacity>
          </View>
          
          {/* Pending Status */}
          {user.status === 'pending' && (
            <View style={styles.pendingBanner}>
              <Ionicons name="time" size={20} color="#FF9500" />
              <Text style={styles.pendingText}>Pending Approval</Text>
            </View>
          )}
          
          {/* Impersonate Button */}
          <TouchableOpacity 
            style={styles.impersonateButton}
            onPress={handleImpersonate}
            disabled={impersonating}
          >
            {impersonating ? (
              <ActivityIndicator size="small" color="#FFF" />
            ) : (
              <>
                <Ionicons name="person-circle-outline" size={20} color="#FFF" />
                <Text style={styles.impersonateButtonText}>Impersonate User</Text>
              </>
            )}
          </TouchableOpacity>
        </View>
        
        {/* Profile Completeness */}
        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <Ionicons name="clipboard-outline" size={20} color="#007AFF" />
            <Text style={styles.sectionTitle}>Profile Completeness</Text>
            <View style={[styles.percentBadge, { 
              backgroundColor: completeness && completeness.percentage >= 80 ? '#34C75920' : '#FF950020' 
            }]}>
              <Text style={[styles.percentText, { 
                color: completeness && completeness.percentage >= 80 ? '#34C759' : '#FF9500' 
              }]}>
                {completeness?.percentage || 0}%
              </Text>
            </View>
          </View>
          
          <View style={styles.progressBar}>
            <View style={[styles.progressFill, { 
              width: `${completeness?.percentage || 0}%`,
              backgroundColor: completeness && completeness.percentage >= 80 ? '#34C759' : '#FF9500'
            }]} />
          </View>
          
          <View style={styles.completenessGrid}>
            {completeness && (
              <>
                {renderCompletenessItem('Profile Photo', completeness.photo, 'camera')}
                {renderCompletenessItem('Job Title', completeness.title, 'briefcase')}
                {renderCompletenessItem('Bio / About', completeness.bio, 'document-text')}
                {renderCompletenessItem('Phone Number', completeness.phone, 'call')}
                {renderCompletenessItem('AI Assistant', completeness.ai_persona, 'sparkles')}
                {renderCompletenessItem('Social Links', completeness.social_links, 'share-social')}
              </>
            )}
          </View>
        </View>
        
        {/* Contact Info */}
        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <Ionicons name="person-outline" size={20} color="#007AFF" />
            <Text style={styles.sectionTitle}>Contact Information</Text>
          </View>
          
          <View style={styles.infoCard}>
            <View style={styles.infoRow}>
              <Ionicons name="mail-outline" size={18} color="#8E8E93" />
              <Text style={styles.infoText}>{user.email}</Text>
            </View>
            {(user.phone || user.twilio_phone_number) && (
              <View style={styles.infoRow}>
                <Ionicons name="call-outline" size={18} color="#8E8E93" />
                <Text style={styles.infoText}>{user.phone || user.twilio_phone_number}</Text>
                {user.twilio_phone_number && (
                  <View style={styles.twilioTag}>
                    <Text style={styles.twilioTagText}>MVPLine</Text>
                  </View>
                )}
              </View>
            )}
            {user.created_at && (
              <View style={styles.infoRow}>
                <Ionicons name="calendar-outline" size={18} color="#8E8E93" />
                <Text style={styles.infoText}>
                  Joined {new Date(user.created_at).toLocaleDateString()}
                </Text>
              </View>
            )}
          </View>
        </View>
        
        {/* Organization */}
        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <Ionicons name="business-outline" size={20} color="#FF9500" />
            <Text style={styles.sectionTitle}>Organization</Text>
            <TouchableOpacity 
              style={styles.changeOrgButton}
              onPress={() => setShowOrgModal(true)}
              data-testid="change-org-btn"
            >
              <Ionicons name="swap-horizontal" size={18} color="#007AFF" />
              <Text style={styles.changeOrgText}>Change</Text>
            </TouchableOpacity>
          </View>
          
          {organization ? (
            <TouchableOpacity 
              style={styles.orgCard}
              onPress={() => router.push(`/admin/organizations/${organization._id}`)}
            >
              <View style={styles.orgIcon}>
                <Ionicons name="business" size={24} color="#FF9500" />
              </View>
              <Text style={styles.orgName}>{organization.name}</Text>
              <Ionicons name="chevron-forward" size={20} color="#8E8E93" />
            </TouchableOpacity>
          ) : (
            <View style={styles.emptyState}>
              <Ionicons name="business-outline" size={40} color="#8E8E93" />
              <Text style={styles.emptyText}>No organization assigned</Text>
              <TouchableOpacity 
                style={styles.assignButton}
                onPress={() => setShowOrgModal(true)}
              >
                <Text style={styles.assignButtonText}>Assign to Organization</Text>
              </TouchableOpacity>
            </View>
          )}
        </View>
        
        {/* Assigned Stores */}
        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <Ionicons name="storefront-outline" size={20} color="#34C759" />
            <Text style={styles.sectionTitle}>Assigned Stores ({stores.length})</Text>
            <TouchableOpacity 
              style={styles.addButton}
              onPress={() => setShowStoreModal(true)}
            >
              <Ionicons name="add-circle" size={24} color="#007AFF" />
            </TouchableOpacity>
          </View>
          
          {stores.length === 0 ? (
            <View style={styles.emptyState}>
              <Ionicons name="storefront-outline" size={40} color="#8E8E93" />
              <Text style={styles.emptyText}>Not assigned to any store</Text>
              <TouchableOpacity 
                style={styles.assignButton}
                onPress={() => setShowStoreModal(true)}
              >
                <Text style={styles.assignButtonText}>Assign to Store</Text>
              </TouchableOpacity>
            </View>
          ) : (
            stores.map(store => (
              <TouchableOpacity 
                key={store._id}
                style={styles.storeCard}
                onPress={() => router.push(`/admin/stores/${store._id}`)}
              >
                <View style={styles.storeIcon}>
                  <Ionicons name="storefront" size={20} color="#34C759" />
                </View>
                <View style={styles.storeInfo}>
                  <Text style={styles.storeName}>{store.name}</Text>
                  <Text style={styles.storeLocation}>
                    {[store.city, store.state].filter(Boolean).join(', ') || 'No location'}
                  </Text>
                </View>
                <TouchableOpacity 
                  style={styles.removeButton}
                  onPress={() => handleRemoveFromStore(store)}
                >
                  <Ionicons name="close-circle" size={22} color="#FF3B30" />
                </TouchableOpacity>
              </TouchableOpacity>
            ))
          )}
        </View>
        
        {/* Quick Actions */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Quick Actions</Text>
          
          <TouchableOpacity 
            style={styles.actionButton}
            onPress={() => router.push(`/card/${user._id}`)}
          >
            <Ionicons name="card-outline" size={20} color="#007AFF" />
            <Text style={styles.actionText}>View Digital Business Card</Text>
            <Ionicons name="chevron-forward" size={20} color="#8E8E93" />
          </TouchableOpacity>
          
          <TouchableOpacity 
            style={[styles.actionButton, { borderBottomWidth: 0 }]}
            onPress={() => router.push(`/thread/${user._id}`)}
          >
            <Ionicons name="chatbubbles-outline" size={20} color="#007AFF" />
            <Text style={styles.actionText}>View Conversations</Text>
            <Ionicons name="chevron-forward" size={20} color="#8E8E93" />
          </TouchableOpacity>
        </View>
        
        {/* Danger Zone */}
        <View style={[styles.section, styles.dangerSection]}>
          <View style={styles.sectionHeader}>
            <Ionicons name="warning-outline" size={20} color="#FF3B30" />
            <Text style={[styles.sectionTitle, { color: '#FF3B30' }]}>Danger Zone</Text>
          </View>
          
          <TouchableOpacity 
            style={styles.deleteButton}
            onPress={handleDeleteUser}
            disabled={actionLoading}
          >
            <Ionicons name="trash-outline" size={20} color="#FF3B30" />
            <Text style={styles.deleteButtonText}>Delete User</Text>
          </TouchableOpacity>
          
          <Text style={styles.dangerWarning}>
            This will permanently delete the user and all their data. This action cannot be undone.
          </Text>
        </View>
        
        <View style={{ height: 40 }} />
      </ScrollView>
      
      {/* Assign to Store Modal */}
      <Modal
        visible={showStoreModal}
        animationType="slide"
        presentationStyle="pageSheet"
        onRequestClose={() => setShowStoreModal(false)}
      >
        <SafeAreaView style={styles.modalContainer}>
          <View style={styles.modalHeader}>
            <TouchableOpacity onPress={() => setShowStoreModal(false)}>
              <Text style={styles.cancelText}>Cancel</Text>
            </TouchableOpacity>
            <Text style={styles.modalTitle}>Assign to Store</Text>
            <View style={{ width: 60 }} />
          </View>
          
          {availableStores.length === 0 ? (
            <View style={styles.emptyModalState}>
              <Ionicons name="storefront-outline" size={48} color="#8E8E93" />
              <Text style={styles.emptyModalText}>No available stores</Text>
              <Text style={styles.emptyModalSubtext}>
                User is already assigned to all stores in their organization
              </Text>
            </View>
          ) : (
            <FlatList
              data={availableStores}
              keyExtractor={(item) => item._id}
              renderItem={({ item }) => (
                <TouchableOpacity 
                  style={styles.storeOption}
                  onPress={() => handleAssignStore(item._id)}
                  disabled={actionLoading}
                >
                  <View style={styles.storeIcon}>
                    <Ionicons name="storefront" size={20} color="#34C759" />
                  </View>
                  <View style={styles.storeInfo}>
                    <Text style={styles.storeName}>{item.name}</Text>
                    <Text style={styles.storeLocation}>
                      {[item.city, item.state].filter(Boolean).join(', ') || 'No location'}
                    </Text>
                  </View>
                  {actionLoading ? (
                    <ActivityIndicator size="small" color="#007AFF" />
                  ) : (
                    <Ionicons name="add-circle" size={24} color="#007AFF" />
                  )}
                </TouchableOpacity>
              )}
              contentContainerStyle={styles.storeList}
            />
          )}
        </SafeAreaView>
      </Modal>
      
      {/* Change Role Modal */}
      <Modal
        visible={showRoleModal}
        animationType="slide"
        presentationStyle="pageSheet"
        onRequestClose={() => setShowRoleModal(false)}
      >
        <SafeAreaView style={styles.modalContainer}>
          <View style={styles.modalHeader}>
            <TouchableOpacity onPress={() => setShowRoleModal(false)}>
              <Text style={styles.cancelText}>Cancel</Text>
            </TouchableOpacity>
            <Text style={styles.modalTitle}>Change Role</Text>
            <View style={{ width: 60 }} />
          </View>
          
          <FlatList
            data={AVAILABLE_ROLES}
            keyExtractor={(item) => item.value}
            renderItem={({ item }) => (
              <TouchableOpacity 
                style={[
                  styles.roleOption,
                  user?.role === item.value && styles.roleOptionSelected
                ]}
                onPress={() => handleChangeRole(item.value)}
                disabled={actionLoading || user?.role === item.value}
              >
                <View style={[styles.roleIcon, { backgroundColor: item.color + '20' }]}>
                  <Ionicons 
                    name={item.value === 'org_admin' ? 'shield' : item.value === 'store_manager' ? 'storefront' : 'person'} 
                    size={20} 
                    color={item.color} 
                  />
                </View>
                <View style={styles.roleInfo}>
                  <Text style={styles.roleLabel}>{item.label}</Text>
                  <Text style={styles.roleDescription}>
                    {item.value === 'org_admin' && 'Full access to manage organization'}
                    {item.value === 'store_manager' && 'Manage assigned stores and users'}
                    {item.value === 'user' && 'Basic access to assigned stores'}
                  </Text>
                </View>
                {user?.role === item.value ? (
                  <Ionicons name="checkmark-circle" size={24} color="#34C759" />
                ) : actionLoading ? (
                  <ActivityIndicator size="small" color="#007AFF" />
                ) : (
                  <Ionicons name="chevron-forward" size={20} color="#8E8E93" />
                )}
              </TouchableOpacity>
            )}
            contentContainerStyle={styles.roleList}
          />
        </SafeAreaView>
      </Modal>
      
      {/* Change Organization Modal */}
      <Modal
        visible={showOrgModal}
        animationType="slide"
        presentationStyle="pageSheet"
        onRequestClose={() => setShowOrgModal(false)}
      >
        <SafeAreaView style={styles.modalContainer}>
          <View style={styles.modalHeader}>
            <TouchableOpacity onPress={() => setShowOrgModal(false)}>
              <Text style={styles.cancelText}>Cancel</Text>
            </TouchableOpacity>
            <Text style={styles.modalTitle}>Change Organization</Text>
            <View style={{ width: 60 }} />
          </View>
          
          {allOrganizations.length === 0 ? (
            <View style={styles.emptyModalState}>
              <Ionicons name="business-outline" size={48} color="#8E8E93" />
              <Text style={styles.emptyModalText}>No organizations available</Text>
            </View>
          ) : (
            <FlatList
              data={allOrganizations}
              keyExtractor={(item) => item._id}
              renderItem={({ item }) => {
                const isCurrentOrg = item._id === organization?._id;
                return (
                  <TouchableOpacity 
                    style={[
                      styles.orgOption,
                      isCurrentOrg && styles.orgOptionSelected
                    ]}
                    onPress={() => handleChangeOrganization(item._id)}
                    disabled={actionLoading || isCurrentOrg}
                  >
                    <View style={[styles.orgIcon, { backgroundColor: isCurrentOrg ? '#34C75920' : '#FF950020' }]}>
                      <Ionicons name="business" size={24} color={isCurrentOrg ? '#34C759' : '#FF9500'} />
                    </View>
                    <View style={styles.orgOptionInfo}>
                      <Text style={styles.orgOptionName}>{item.name}</Text>
                      {isCurrentOrg && (
                        <Text style={styles.currentOrgLabel}>Current organization</Text>
                      )}
                    </View>
                    {isCurrentOrg ? (
                      <Ionicons name="checkmark-circle" size={24} color="#34C759" />
                    ) : actionLoading ? (
                      <ActivityIndicator size="small" color="#007AFF" />
                    ) : (
                      <Ionicons name="chevron-forward" size={20} color="#8E8E93" />
                    )}
                  </TouchableOpacity>
                );
              }}
              contentContainerStyle={styles.orgList}
            />
          )}
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
  errorContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  errorText: {
    color: '#FFF',
    fontSize: 16,
    marginTop: 12,
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
    flex: 1,
    textAlign: 'center',
  },
  content: {
    flex: 1,
    padding: 16,
  },
  // Profile Card
  profileCard: {
    backgroundColor: '#1C1C1E',
    borderRadius: 16,
    padding: 20,
    marginBottom: 16,
  },
  profileHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 16,
  },
  avatar: {
    width: 72,
    height: 72,
    borderRadius: 36,
  },
  avatarPlaceholder: {
    width: 72,
    height: 72,
    borderRadius: 36,
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarInitials: {
    fontSize: 28,
    fontWeight: '600',
  },
  profileInfo: {
    flex: 1,
    marginLeft: 16,
  },
  userName: {
    fontSize: 22,
    fontWeight: '700',
    color: '#FFF',
  },
  userTitle: {
    fontSize: 14,
    color: '#8E8E93',
    marginTop: 2,
  },
  roleBadgeContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 8,
  },
  roleBadge: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
  },
  roleBadgeText: {
    fontSize: 12,
    fontWeight: '600',
  },
  changeRoleButton: {
    marginLeft: 8,
    padding: 4,
  },
  statusRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingTop: 16,
    borderTopWidth: 1,
    borderTopColor: '#2C2C2E',
  },
  statusLabel: {
    fontSize: 14,
    color: '#8E8E93',
  },
  statusBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 12,
  },
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginRight: 6,
  },
  statusText: {
    fontSize: 13,
    fontWeight: '600',
  },
  pendingBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#FF950020',
    paddingVertical: 10,
    borderRadius: 8,
    marginTop: 16,
  },
  pendingText: {
    color: '#FF9500',
    fontSize: 14,
    fontWeight: '500',
    marginLeft: 8,
  },
  impersonateButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#5856D6',
    borderRadius: 12,
    paddingVertical: 14,
    marginTop: 16,
    gap: 8,
  },
  impersonateButtonText: {
    color: '#FFF',
    fontSize: 16,
    fontWeight: '600',
  },
  // Sections
  section: {
    backgroundColor: '#1C1C1E',
    borderRadius: 16,
    padding: 16,
    marginBottom: 16,
  },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 12,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFF',
    marginLeft: 8,
    flex: 1,
  },
  addButton: {
    padding: 4,
  },
  // Profile Completeness
  percentBadge: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
  },
  percentText: {
    fontSize: 13,
    fontWeight: '700',
  },
  progressBar: {
    height: 6,
    backgroundColor: '#2C2C2E',
    borderRadius: 3,
    marginBottom: 16,
    overflow: 'hidden',
  },
  progressFill: {
    height: '100%',
    borderRadius: 3,
  },
  completenessGrid: {
    gap: 8,
  },
  completenessItem: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: '#2C2C2E',
  },
  completenessLabel: {
    fontSize: 14,
    color: '#FFF',
    marginLeft: 10,
    flex: 1,
  },
  incompleteLabelText: {
    color: '#8E8E93',
  },
  missingBadge: {
    backgroundColor: '#FF3B3020',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
  },
  missingText: {
    fontSize: 11,
    color: '#FF3B30',
    fontWeight: '500',
  },
  // Contact Info
  infoCard: {
    gap: 12,
  },
  infoRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  infoText: {
    fontSize: 14,
    color: '#FFF',
    marginLeft: 10,
    flex: 1,
  },
  twilioTag: {
    backgroundColor: '#007AFF20',
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
  },
  twilioTagText: {
    fontSize: 10,
    color: '#007AFF',
    fontWeight: '600',
  },
  // Organization
  orgCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#2C2C2E',
    borderRadius: 12,
    padding: 14,
  },
  orgIcon: {
    width: 40,
    height: 40,
    borderRadius: 8,
    backgroundColor: '#FF950020',
    alignItems: 'center',
    justifyContent: 'center',
  },
  orgName: {
    flex: 1,
    fontSize: 16,
    fontWeight: '500',
    color: '#FFF',
    marginLeft: 12,
  },
  // Stores
  emptyState: {
    alignItems: 'center',
    paddingVertical: 24,
  },
  emptyText: {
    color: '#8E8E93',
    fontSize: 14,
    marginTop: 8,
  },
  assignButton: {
    marginTop: 12,
    backgroundColor: '#007AFF',
    paddingHorizontal: 20,
    paddingVertical: 10,
    borderRadius: 20,
  },
  assignButtonText: {
    color: '#FFF',
    fontSize: 14,
    fontWeight: '600',
  },
  storeCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#2C2C2E',
    borderRadius: 12,
    padding: 14,
    marginBottom: 8,
  },
  storeIcon: {
    width: 40,
    height: 40,
    borderRadius: 8,
    backgroundColor: '#34C75920',
    alignItems: 'center',
    justifyContent: 'center',
  },
  storeInfo: {
    flex: 1,
    marginLeft: 12,
  },
  storeName: {
    fontSize: 15,
    fontWeight: '500',
    color: '#FFF',
  },
  storeLocation: {
    fontSize: 13,
    color: '#8E8E93',
    marginTop: 2,
  },
  removeButton: {
    padding: 4,
  },
  // Actions
  actionButton: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 14,
    borderBottomWidth: 1,
    borderBottomColor: '#2C2C2E',
  },
  actionText: {
    flex: 1,
    fontSize: 15,
    color: '#FFF',
    marginLeft: 12,
  },
  // Modal
  modalContainer: {
    flex: 1,
    backgroundColor: '#000',
  },
  modalHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 14,
    borderBottomWidth: 1,
    borderBottomColor: '#1C1C1E',
  },
  cancelText: {
    fontSize: 16,
    color: '#007AFF',
  },
  modalTitle: {
    fontSize: 17,
    fontWeight: '600',
    color: '#FFF',
  },
  storeList: {
    padding: 16,
  },
  storeOption: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 14,
    marginBottom: 8,
  },
  emptyModalState: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 40,
  },
  emptyModalText: {
    color: '#FFF',
    fontSize: 18,
    fontWeight: '600',
    marginTop: 16,
  },
  emptyModalSubtext: {
    color: '#8E8E93',
    fontSize: 14,
    textAlign: 'center',
    marginTop: 8,
  },
  // Role Modal
  roleList: {
    padding: 16,
  },
  roleOption: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 16,
    marginBottom: 8,
  },
  roleOptionSelected: {
    backgroundColor: '#2C2C2E',
    borderWidth: 1,
    borderColor: '#34C759',
  },
  roleIcon: {
    width: 44,
    height: 44,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
  },
  roleInfo: {
    flex: 1,
    marginLeft: 12,
  },
  roleLabel: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFF',
  },
  roleDescription: {
    fontSize: 12,
    color: '#8E8E93',
    marginTop: 2,
  },
  // Change Org Button
  changeOrgButton: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#007AFF20',
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 12,
    gap: 4,
  },
  changeOrgText: {
    fontSize: 13,
    fontWeight: '600',
    color: '#007AFF',
  },
  // Org Modal
  orgList: {
    padding: 16,
  },
  orgOption: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1C1C1E',
    borderRadius: 12,
    padding: 16,
    marginBottom: 8,
  },
  orgOptionSelected: {
    backgroundColor: '#2C2C2E',
    borderWidth: 1,
    borderColor: '#34C759',
  },
  orgOptionInfo: {
    flex: 1,
    marginLeft: 12,
  },
  orgOptionName: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFF',
  },
  currentOrgLabel: {
    fontSize: 12,
    color: '#34C759',
    marginTop: 2,
  },
  // Danger Zone
  dangerSection: {
    borderWidth: 1,
    borderColor: '#FF3B3040',
    backgroundColor: '#FF3B3010',
  },
  deleteButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#FF3B3020',
    borderRadius: 12,
    padding: 16,
    gap: 8,
  },
  deleteButtonText: {
    color: '#FF3B30',
    fontSize: 16,
    fontWeight: '600',
  },
  dangerWarning: {
    color: '#8E8E93',
    fontSize: 12,
    textAlign: 'center',
    marginTop: 12,
    lineHeight: 18,
  },
});
