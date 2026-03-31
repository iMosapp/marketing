import React, { useState, useCallback } from 'react';
import {
  View,
  Text,
  TextInput,
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
import { useToast } from '../../../components/common/Toast';
import { useAuthStore } from '../../../store/authStore';

import { useThemeStore } from '../../../store/themeStore';
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
  // Deletion tracking
  deleted_at?: string;
  deletion_source?: string;
  deletion_reason?: string;
  previous_status?: string;
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
  store_manager: 'Account Manager',
  user: 'Sales Rep',
};

// Helpers with fallbacks for unknown/legacy roles
const getRoleColor = (role: string) => ROLE_COLORS[role] || '#8E8E93';
const getRoleLabel = (role: string) => ROLE_LABELS[role] || role;

const AVAILABLE_ROLES = [
  { value: 'user', label: 'Sales Rep', color: '#007AFF' },
  { value: 'store_manager', label: 'Account Manager', color: '#34C759' },
  { value: 'org_admin', label: 'Org Admin', color: '#FF9500' },
];

export default function UserDetailScreen() {
  const { colors } = useThemeStore();
  const styles = getStyles(colors);
  const router = useRouter();
  const { id } = useLocalSearchParams();
  const { showToast } = useToast();
  
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
  // Contact info inline editing
  const [editingContactField, setEditingContactField] = useState<'phone' | 'email' | null>(null);
  const [contactEditValue, setContactEditValue] = useState('');
  const contactSavingRef = React.useRef(false); // Prevents double-save from onSubmitEditing + onBlur

  const saveContactField = async (field: 'phone' | 'email', value: string) => {
    if (contactSavingRef.current) return;
    const trimmed = value.trim();
    if (!trimmed) { setEditingContactField(null); return; } // Don't save empty value
    contactSavingRef.current = true;
    try {
      const payload = field === 'email'
        ? { email: trimmed.toLowerCase() }
        : { phone: trimmed };
      await adminAPI.updateUser(user!._id, payload);
      setUser((prev: any) => prev ? { ...prev, ...payload } : prev);
      setEditingContactField(null);
      showToast(`${field === 'email' ? 'Email' : 'Phone'} updated ✓`);
    } catch (e: any) {
      // Show the actual backend error message so we can debug
      const detail = e?.response?.data?.detail;
      const status = e?.response?.status;
      const msg = typeof detail === 'string' ? detail
        : detail ? JSON.stringify(detail)
        : `Failed to update ${field}${status ? ` (HTTP ${status})` : ''}: ${e?.message || 'unknown'}`;
      showSimpleAlert('Error', msg);
      setEditingContactField(null);
    } finally {
      contactSavingRef.current = false;
    }
  };
  
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
            router.replace('/(tabs)/home');
          } else {
            showSimpleAlert('Error', 'Impersonation returned unsuccessful response');
          }
        } catch (error: any) {
          console.error('[Impersonate] error:', {
            message: error?.message,
            status: error?.response?.status,
            data: error?.response?.data,
            code: error?.code,
          });
          const detail = error?.response?.data?.detail || error?.message || 'Unknown error';
          showSimpleAlert('Error', `Failed to impersonate user: ${detail}`);
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
    const currentlyActive = user.is_active !== false;
    const newStatus = !currentlyActive;
    const contactWarning = !newStatus
      ? '\n\nImportant: If this user uploaded or downloaded personal contacts into the app, those contacts will NOT remain with the organization or store. Personal contacts belong to the user.'
      : '';
    showConfirm(
      newStatus ? 'Activate User' : 'Deactivate User',
      `Are you sure you want to ${newStatus ? 'activate' : 'deactivate'} ${user.name}?${contactWarning}`,
      async () => {
        try {
          await api.put(`/admin/users/${id}`, { is_active: newStatus });
          loadUserData();
          showToast(`User ${newStatus ? 'activated' : 'deactivated'}`);
        } catch (error) {
          showSimpleAlert('Error', 'Failed to update user status');
        }
      }
    );
  };

  const handleReactivateUser = () => {
    if (!user) return;
    showConfirm(
      'Reactivate User',
      `Are you sure you want to reactivate ${user.name}? They will be able to log in and access the system again.`,
      async () => {
        setActionLoading(true);
        try {
          await api.put(`/admin/users/${id}/reactivate`);
          loadUserData();
          showToast('${user.name} has been reactivated');
        } catch (error: any) {
          showSimpleAlert('Error', error.response?.data?.detail || 'Failed to reactivate user');
        } finally {
          setActionLoading(false);
        }
      }
    );
  };
  
  const handleChangeOrganization = async (newOrgId: string) => {
    if (!user) return;
    setActionLoading(true);
    try {
      await api.put(`/admin/hierarchy/users/${id}/change-organization`, { organization_id: newOrgId });
      showToast('User moved to new organization');
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
      showToast('User assigned to store');
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
          showToast('User removed from store');
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
      showToast('Role updated');
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
      'Deactivate User',
      `Deactivate "${user.name}"? They will be soft-deleted with a 6-month grace period.`,
      async () => {
        setActionLoading(true);
        try {
          await api.delete(`/admin/users/${id}`);
          showToast('User deactivated');
          router.back();
        } catch (error: any) {
          showSimpleAlert('Error', error.response?.data?.detail || 'Failed to deactivate user');
        } finally {
          setActionLoading(false);
        }
      },
      undefined,
      'Deactivate',
      'Cancel'
    );
  };

  const handleHardDelete = () => {
    if (!user) return;
    showConfirm(
      'Permanently Delete',
      `This will PERMANENTLY remove "${user.name}" from the system. Their contacts will be kept but unassigned. This cannot be undone.`,
      async () => {
        setActionLoading(true);
        try {
          await api.delete(`/admin/users/${id}/hard`);
          showToast('User permanently deleted');
          router.back();
        } catch (error: any) {
          showSimpleAlert('Error', error.response?.data?.detail || 'Failed to delete user');
        } finally {
          setActionLoading(false);
        }
      },
      undefined,
      'Delete Forever',
      'Cancel'
    );
  };
  
  const renderCompletenessItem = (label: string, completed: boolean, icon: string) => (
    <View style={styles.completenessItem} key={label}>
      <Ionicons 
        name={completed ? "checkmark-circle" : "ellipse-outline"} 
        size={20} 
        color={completed ? "#34C759" : colors.textSecondary} 
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
                <View style={[styles.roleBadge, { backgroundColor: getRoleColor(user.role) + '20' }]}>
                  <Text style={[styles.roleBadgeText, { color: getRoleColor(user.role) }]}>
                    {getRoleLabel(user.role)}
                  </Text>
                </View>
                {/* Only show edit pencil for non-super-admin targets */}
                {user.role !== 'super_admin' && (
                <TouchableOpacity 
                  style={styles.changeRoleButton}
                  onPress={() => setShowRoleModal(true)}
                  data-testid="change-role-btn"
                >
                  <Ionicons name="pencil" size={14} color="#007AFF" />
                </TouchableOpacity>
                )}
              </View>
            </View>
          </View>
          
          {/* Status Toggle */}
          <View style={styles.statusRow}>
            <Text style={styles.statusLabel}>Account Status</Text>
            <TouchableOpacity 
              style={[styles.statusBadge, { backgroundColor: user.is_active !== false ? '#34C75920' : '#FF3B3020' }]}
              onPress={handleToggleActive}
            >
              <View style={[styles.statusDot, { backgroundColor: user.is_active !== false ? '#34C759' : '#FF3B30' }]} />
              <Text style={[styles.statusText, { color: user.is_active !== false ? '#34C759' : '#FF3B30' }]}>
                {user.is_active !== false ? 'Active' : 'Inactive'}
              </Text>
            </TouchableOpacity>
          </View>
          
          {/* Inactive User Banner with Reactivate */}
          {user.is_active === false && (
            <View style={styles.inactiveBanner}>
              <View style={styles.inactiveBannerHeader}>
                <Ionicons name="person-remove" size={24} color="#FF9500" />
                <Text style={styles.inactiveBannerTitle}>User Deactivated</Text>
              </View>
              {user.deletion_source && (
                <View style={styles.deletionInfo}>
                  <Text style={styles.deletionSource}>
                    Deleted by: {user.deletion_source}
                  </Text>
                  {user.deleted_at && (
                    <Text style={styles.deletionDate}>
                      on {new Date(user.deleted_at).toLocaleDateString()} at {new Date(user.deleted_at).toLocaleTimeString()}
                    </Text>
                  )}
                </View>
              )}
              <TouchableOpacity 
                style={styles.reactivateButton}
                onPress={handleReactivateUser}
                disabled={actionLoading}
                data-testid="reactivate-user-btn"
              >
                {actionLoading ? (
                  <ActivityIndicator size="small" color={colors.text} />
                ) : (
                  <>
                    <Ionicons name="refresh" size={18} color={colors.text} />
                    <Text style={styles.reactivateButtonText}>Reactivate User</Text>
                  </>
                )}
              </TouchableOpacity>
            </View>
          )}
          
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
              <ActivityIndicator size="small" color={colors.text} />
            ) : (
              <>
                <Ionicons name="person-circle-outline" size={20} color={colors.text} />
                <Text style={styles.impersonateButtonText}>Impersonate User</Text>
              </>
            )}
          </TouchableOpacity>

          {/* Manage Permissions Button */}
          <TouchableOpacity 
            style={[styles.impersonateButton, { marginTop: 8, borderColor: '#FF950040' }]}
            onPress={() => router.push(`/admin/users/permissions/${id}` as any)}
            data-testid="manage-permissions-btn"
          >
            <Ionicons name="toggle-outline" size={20} color="#FF9500" />
            <Text style={[styles.impersonateButtonText, { color: '#FF9500' }]}>Manage Permissions</Text>
          </TouchableOpacity>

          {/* Reset Password Button */}
          <TouchableOpacity 
            style={[styles.impersonateButton, { marginTop: 8, borderColor: '#FF3B3040' }]}
            onPress={() => {
              showConfirm(
                'Reset Password',
                `Reset password for ${user.name}? A new temporary password will be generated.`,
                async () => {
                  try {
                    const tempPassword = Math.random().toString(36).slice(-8) + 'A1!';
                    await api.put(`/admin/users/${id}/reset-password`, { new_password: tempPassword });
                    showSimpleAlert('Password Reset', `New temporary password:\n\n${tempPassword}\n\nPlease share this with ${user.name} securely.`);
                  } catch (error: any) {
                    showSimpleAlert('Error', error.response?.data?.detail || 'Failed to reset password');
                  }
                }
              );
            }}
            data-testid="reset-password-btn"
          >
            <Ionicons name="key-outline" size={20} color="#FF3B30" />
            <Text style={[styles.impersonateButtonText, { color: '#FF3B30' }]}>Reset Password</Text>
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
            {/* Email row — tap pencil to edit */}
            {editingContactField === 'email' ? (
              <View style={[styles.infoRow, { gap: 8 }]}>
                <Ionicons name="mail-outline" size={18} color={colors.textSecondary} />
                <TextInput
                  style={{ flex: 1, color: colors.text, fontSize: 15, borderBottomWidth: 1, borderBottomColor: '#C9A962', paddingVertical: 4 }}
                  value={contactEditValue}
                  onChangeText={setContactEditValue}
                  keyboardType="email-address"
                  autoCapitalize="none"
                  autoFocus
                  returnKeyType="done"
                  onSubmitEditing={() => saveContactField('email', contactEditValue)}
                  onBlur={() => saveContactField('email', contactEditValue)}
                />
                <TouchableOpacity onPress={() => setEditingContactField(null)}><Ionicons name="close-circle" size={20} color={colors.textSecondary} /></TouchableOpacity>
              </View>
            ) : (
              <TouchableOpacity style={styles.infoRow} onPress={() => { setEditingContactField('email'); setContactEditValue(user.email); }}>
                <Ionicons name="mail-outline" size={18} color={colors.textSecondary} />
                <Text style={[styles.infoText, { flex: 1 }]}>{user.email}</Text>
                <Ionicons name="pencil-outline" size={14} color={colors.textTertiary} />
              </TouchableOpacity>
            )}

            {/* Phone row — tap pencil to edit */}
            {editingContactField === 'phone' ? (
              <View style={[styles.infoRow, { gap: 8 }]}>
                <Ionicons name="call-outline" size={18} color={colors.textSecondary} />
                <TextInput
                  style={{ flex: 1, color: colors.text, fontSize: 15, borderBottomWidth: 1, borderBottomColor: '#C9A962', paddingVertical: 4 }}
                  value={contactEditValue}
                  onChangeText={setContactEditValue}
                  keyboardType="phone-pad"
                  autoFocus
                  returnKeyType="done"
                  onSubmitEditing={() => saveContactField('phone', contactEditValue)}
                  onBlur={() => saveContactField('phone', contactEditValue)}
                />
                <TouchableOpacity onPress={() => setEditingContactField(null)}><Ionicons name="close-circle" size={20} color={colors.textSecondary} /></TouchableOpacity>
              </View>
            ) : (
              <TouchableOpacity style={styles.infoRow} onPress={() => { setEditingContactField('phone'); setContactEditValue(user.phone || user.twilio_phone_number || ''); }}>
                <Ionicons name="call-outline" size={18} color={colors.textSecondary} />
                <Text style={[styles.infoText, { flex: 1 }]}>{user.phone || user.twilio_phone_number || 'Tap to add phone'}</Text>
                {user.twilio_phone_number && (<View style={styles.twilioTag}><Text style={styles.twilioTagText}>i'M On Social</Text></View>)}
                <Ionicons name="pencil-outline" size={14} color={colors.textTertiary} />
              </TouchableOpacity>
            )}
            {user.created_at && (
              <View style={styles.infoRow}>
                <Ionicons name="calendar-outline" size={18} color={colors.textSecondary} />
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
              <Ionicons name="chevron-forward" size={20} color={colors.textSecondary} />
            </TouchableOpacity>
          ) : (
            <View style={styles.emptyState}>
              <Ionicons name="business-outline" size={40} color={colors.textSecondary} />
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
              <Ionicons name="storefront-outline" size={40} color={colors.textSecondary} />
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
            <Ionicons name="chevron-forward" size={20} color={colors.textSecondary} />
          </TouchableOpacity>
          
          <TouchableOpacity 
            style={[styles.actionButton, { borderBottomWidth: 0 }]}
            onPress={() => router.push(`/thread/${user._id}`)}
          >
            <Ionicons name="chatbubbles-outline" size={20} color="#007AFF" />
            <Text style={styles.actionText}>View Conversations</Text>
            <Ionicons name="chevron-forward" size={20} color={colors.textSecondary} />
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
            data-testid="deactivate-user-btn"
          >
            <Ionicons name="close-circle-outline" size={20} color="#FF9500" />
            <Text style={[styles.deleteButtonText, { color: '#FF9500' }]}>Deactivate User</Text>
          </TouchableOpacity>
          
          <TouchableOpacity 
            style={[styles.deleteButton, { marginTop: 10 }]}
            onPress={handleHardDelete}
            disabled={actionLoading}
            data-testid="hard-delete-user-btn"
          >
            <Ionicons name="trash-outline" size={20} color="#FF3B30" />
            <Text style={styles.deleteButtonText}>Permanently Delete</Text>
          </TouchableOpacity>
          
          <Text style={styles.dangerWarning}>
            Deactivate keeps the user in the system (recoverable). Permanently Delete removes them entirely — contacts are kept but unassigned.
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
              <Ionicons name="storefront-outline" size={48} color={colors.textSecondary} />
              <Text style={styles.emptyModalText}>No available accounts</Text>
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
                      {item.org_name ? `${item.org_name} · ` : ''}{[item.city, item.state].filter(Boolean).join(', ') || 'No location'}
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

          {/* Current role banner — shown when role isn't in the selectable list */}
          {!AVAILABLE_ROLES.find(r => r.value === user?.role) && user?.role && (
            <View style={{ flexDirection: 'row', alignItems: 'center', margin: 16, padding: 12, borderRadius: 10, backgroundColor: getRoleColor(user.role) + '20', borderWidth: 1, borderColor: getRoleColor(user.role) + '40' }}>
              <Ionicons name="information-circle" size={18} color={getRoleColor(user.role)} style={{ marginRight: 8 }} />
              <Text style={{ fontSize: 15, color: getRoleColor(user.role), fontWeight: '600' }}>
                Current role: {getRoleLabel(user.role)} — select a new role below
              </Text>
            </View>
          )}
          
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
                  <Ionicons name="chevron-forward" size={20} color={colors.textSecondary} />
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
              <Ionicons name="business-outline" size={48} color={colors.textSecondary} />
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
                      <Ionicons name="chevron-forward" size={20} color={colors.textSecondary} />
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
  errorContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  errorText: {
    color: colors.text,
    fontSize: 18,
    marginTop: 12,
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
    flex: 1,
    textAlign: 'center',
  },
  content: {
    flex: 1,
    padding: 16,
  },
  // Profile Card
  profileCard: {
    backgroundColor: colors.card,
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
    color: colors.text,
  },
  userTitle: {
    fontSize: 16,
    color: colors.textSecondary,
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
    fontSize: 14,
    fontWeight: '600',
  },
  changeRoleButton: {
    marginLeft: 8,
    padding: 10,
  },
  statusRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingTop: 16,
    borderTopWidth: 1,
    borderTopColor: colors.surface,
  },
  statusLabel: {
    fontSize: 16,
    color: colors.textSecondary,
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
    fontSize: 15,
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
    fontSize: 16,
    fontWeight: '500',
    marginLeft: 8,
  },
  // Inactive User Banner
  inactiveBanner: {
    backgroundColor: '#FF3B3015',
    borderRadius: 12,
    padding: 16,
    marginTop: 16,
    borderWidth: 1,
    borderColor: '#FF3B3030',
  },
  inactiveBannerHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 12,
  },
  inactiveBannerTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: '#FF9500',
    marginLeft: 10,
  },
  deletionInfo: {
    backgroundColor: '#00000030',
    borderRadius: 8,
    padding: 12,
    marginBottom: 12,
  },
  deletionSource: {
    fontSize: 16,
    fontWeight: '500',
    color: '#FF9500',
  },
  deletionDate: {
    fontSize: 14,
    color: colors.textSecondary,
    marginTop: 4,
  },
  reactivateButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#34C759',
    borderRadius: 10,
    paddingVertical: 12,
    gap: 8,
  },
  reactivateButtonText: {
    color: colors.text,
    fontSize: 17,
    fontWeight: '600',
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
    color: colors.text,
    fontSize: 18,
    fontWeight: '600',
  },
  // Sections
  section: {
    backgroundColor: colors.card,
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
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
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
    fontSize: 15,
    fontWeight: '700',
  },
  progressBar: {
    height: 6,
    backgroundColor: colors.surface,
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
    borderBottomColor: colors.surface,
  },
  completenessLabel: {
    fontSize: 16,
    color: colors.text,
    marginLeft: 10,
    flex: 1,
  },
  incompleteLabelText: {
    color: colors.textSecondary,
  },
  missingBadge: {
    backgroundColor: '#FF3B3020',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
  },
  missingText: {
    fontSize: 13,
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
    fontSize: 16,
    color: colors.text,
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
    fontSize: 12,
    color: '#007AFF',
    fontWeight: '600',
  },
  // Organization
  orgCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
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
    fontSize: 18,
    fontWeight: '500',
    color: colors.text,
    marginLeft: 12,
  },
  // Stores
  emptyState: {
    alignItems: 'center',
    paddingVertical: 24,
  },
  emptyText: {
    color: colors.textSecondary,
    fontSize: 16,
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
    color: colors.text,
    fontSize: 16,
    fontWeight: '600',
  },
  storeCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
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
    fontSize: 17,
    fontWeight: '500',
    color: colors.text,
  },
  storeLocation: {
    fontSize: 15,
    color: colors.textSecondary,
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
    borderBottomColor: colors.surface,
  },
  actionText: {
    flex: 1,
    fontSize: 17,
    color: colors.text,
    marginLeft: 12,
  },
  // Modal
  modalContainer: {
    flex: 1,
    backgroundColor: colors.bg,
  },
  modalHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 14,
    borderBottomWidth: 1,
    borderBottomColor: colors.card,
  },
  cancelText: {
    fontSize: 18,
    color: '#007AFF',
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
  },
  storeList: {
    padding: 16,
  },
  storeOption: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.card,
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
    color: colors.text,
    fontSize: 19,
    fontWeight: '600',
    marginTop: 16,
  },
  emptyModalSubtext: {
    color: colors.textSecondary,
    fontSize: 16,
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
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 16,
    marginBottom: 8,
  },
  roleOptionSelected: {
    backgroundColor: colors.surface,
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
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
  },
  roleDescription: {
    fontSize: 14,
    color: colors.textSecondary,
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
    fontSize: 15,
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
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 16,
    marginBottom: 8,
  },
  orgOptionSelected: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: '#34C759',
  },
  orgOptionInfo: {
    flex: 1,
    marginLeft: 12,
  },
  orgOptionName: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
  },
  currentOrgLabel: {
    fontSize: 14,
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
    fontSize: 18,
    fontWeight: '600',
  },
  dangerWarning: {
    color: colors.textSecondary,
    fontSize: 14,
    textAlign: 'center',
    marginTop: 12,
    lineHeight: 18,
  },
});
