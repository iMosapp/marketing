import React, { useState, useCallback } from 'react';
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
  FlatList,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useLocalSearchParams, useRouter, useFocusEffect } from 'expo-router';
import api from '../../../services/api';
import { showSimpleAlert, showConfirm } from '../../../services/alert';
import { WebModal } from '../../../components/WebModal';

interface UserInfo {
  _id: string;
  name: string;
  email: string;
  phone?: string;
  role: string;
  is_active: boolean;
  store_ids: string[];
}

interface StoreData {
  store: {
    _id: string;
    name: string;
    organization_id?: string;
    phone?: string;
    address?: string;
    city?: string;
    state?: string;
    active: boolean;
  };
  organization?: {
    _id: string;
    name: string;
  };
  users: UserInfo[];
  available_users: UserInfo[];
  user_count: number;
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

export default function StoreDetailScreen() {
  const router = useRouter();
  const { id } = useLocalSearchParams();
  
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [data, setData] = useState<StoreData | null>(null);
  const [editMode, setEditMode] = useState(false);
  const [editedStore, setEditedStore] = useState<any>({});
  const [showAddUserModal, setShowAddUserModal] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  
  // Campaign Permissions State
  const [campaignSettings, setCampaignSettings] = useState({
    managers_can_edit: true,
    sales_can_edit: false,
  });
  const [savingCampaignSettings, setSavingCampaignSettings] = useState(false);
  
  // Congrats Card Template State
  const [showCongratsEditor, setShowCongratsEditor] = useState(false);
  const [congratsTemplate, setCongratsTemplate] = useState({
    headline: 'Thank You!',
    message: 'Thank you for choosing us, {customer_name}! We truly appreciate your business.',
    background_color: '#1A1A1A',
    accent_color: '#C9A962',
    text_color: '#FFFFFF',
  });
  const [savingTemplate, setSavingTemplate] = useState(false);
  
  const THEME_PRESETS = [
    { name: 'Luxury Gold', bg: '#1A1A1A', accent: '#C9A962', text: '#FFFFFF' },
    { name: 'Classic Blue', bg: '#0A1628', accent: '#3B82F6', text: '#FFFFFF' },
    { name: 'Fresh Green', bg: '#0F1F1A', accent: '#10B981', text: '#FFFFFF' },
    { name: 'Royal Purple', bg: '#1A0F28', accent: '#8B5CF6', text: '#FFFFFF' },
    { name: 'Bold Red', bg: '#1F0A0A', accent: '#EF4444', text: '#FFFFFF' },
    { name: 'Clean Light', bg: '#F8FAFC', accent: '#0F172A', text: '#1E293B' },
  ];
  
  useFocusEffect(
    useCallback(() => {
      loadStoreData();
    }, [id])
  );
  
  const loadStoreData = async () => {
    try {
      setLoading(true);
      const response = await api.get(`/admin/hierarchy/store/${id}`);
      setData(response.data);
      setEditedStore(response.data.store);
      
      // Load congrats template for this store
      try {
        const templateResponse = await api.get(`/congrats/template/${id}`);
        if (templateResponse.data.template) {
          setCongratsTemplate(templateResponse.data.template);
        }
      } catch (err) {
        console.log('No existing template, using defaults');
      }
      
      // Load campaign settings for this store
      try {
        const campaignResponse = await api.get(`/admin/stores/${id}/campaign-settings`);
        setCampaignSettings(campaignResponse.data);
      } catch (err) {
        console.log('No existing campaign settings, using defaults');
      }
    } catch (error) {
      console.error('Failed to load store:', error);
      showSimpleAlert('Error', 'Failed to load store details');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };
  
  const saveCampaignSettings = async () => {
    setSavingCampaignSettings(true);
    try {
      await api.put(`/admin/stores/${id}/campaign-settings`, campaignSettings);
      showSimpleAlert('Success', 'Campaign permissions saved!');
    } catch (error) {
      showSimpleAlert('Error', 'Failed to save campaign settings');
    } finally {
      setSavingCampaignSettings(false);
    }
  };
  
  const saveCongratsTemplate = async () => {
    setSavingTemplate(true);
    try {
      await api.post(`/congrats/template/${id}`, congratsTemplate);
      showSimpleAlert('Success', 'Congrats card template saved!');
      setShowCongratsEditor(false);
    } catch (error) {
      showSimpleAlert('Error', 'Failed to save template');
    } finally {
      setSavingTemplate(false);
    }
  };
  
  const onRefresh = () => {
    setRefreshing(true);
    loadStoreData();
  };
  
  const handleSave = async () => {
    setSaving(true);
    try {
      await api.put(`/admin/stores/${id}`, editedStore);
      showSimpleAlert('Success', 'Account updated successfully');
      loadStoreData();
      setEditMode(false);
    } catch (error) {
      showSimpleAlert('Error', 'Failed to update store');
    } finally {
      setSaving(false);
    }
  };
  
  const handleToggleActive = () => {
    if (!data) return;
    const newStatus = !data.store.active;
    showConfirm(
      newStatus ? 'Activate Store' : 'Deactivate Store',
      `Are you sure you want to ${newStatus ? 'activate' : 'deactivate'} this store?`,
      async () => {
        try {
          await api.put(`/admin/stores/${id}`, { active: newStatus });
          loadStoreData();
          showSimpleAlert('Success', `Store ${newStatus ? 'activated' : 'deactivated'}`);
        } catch (error) {
          showSimpleAlert('Error', 'Failed to update store status');
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
          loadStoreData();
        } catch (error) {
          showSimpleAlert('Error', 'Failed to update user status');
        }
      }
    );
  };
  
  const handleAddUser = async (userId: string) => {
    setActionLoading(true);
    try {
      await api.put(`/admin/hierarchy/users/${userId}/assign-store`, { store_id: id });
      showSimpleAlert('Success', 'User added to store');
      setShowAddUserModal(false);
      loadStoreData();
    } catch (error: any) {
      showSimpleAlert('Error', error.response?.data?.detail || 'Failed to add user');
    } finally {
      setActionLoading(false);
    }
  };
  
  const handleRemoveUser = (user: UserInfo) => {
    showConfirm(
      'Remove from Store',
      `Remove ${user.name} from this store?`,
      async () => {
        try {
          await api.put(`/admin/hierarchy/users/${user._id}/remove-store`, { store_id: id });
          loadStoreData();
        } catch (error) {
          showSimpleAlert('Error', 'Failed to remove user');
        }
      }
    );
  };
  
  if (loading) {
    return (
      <SafeAreaView style={styles.container} edges={['top']}>
        <View style={styles.header}>
          <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
            <Ionicons name="chevron-back" size={28} color="#007AFF" />
          </TouchableOpacity>
          <Text style={styles.title}>Account</Text>
          <View style={{ width: 40 }} />
        </View>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#007AFF" />
        </View>
      </SafeAreaView>
    );
  }
  
  if (!data) {
    return (
      <SafeAreaView style={styles.container} edges={['top']}>
        <View style={styles.header}>
          <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
            <Ionicons name="chevron-back" size={28} color="#007AFF" />
          </TouchableOpacity>
          <Text style={styles.title}>Account</Text>
          <View style={{ width: 40 }} />
        </View>
        <View style={styles.errorContainer}>
          <Ionicons name="alert-circle" size={48} color="#FF3B30" />
          <Text style={styles.errorText}>Account not found</Text>
        </View>
      </SafeAreaView>
    );
  }
  
  const store = data.store;
  
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
          <Text style={styles.title} numberOfLines={1}>{store.name}</Text>
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
            {data.organization && (
              <TouchableOpacity 
                style={styles.orgBadge}
                onPress={() => router.push(`/admin/organizations/${data.organization?._id}`)}
              >
                <Ionicons name="business" size={14} color="#007AFF" />
                <Text style={styles.orgBadgeText}>{data.organization.name}</Text>
                <Ionicons name="chevron-forward" size={14} color="#8E8E93" />
              </TouchableOpacity>
            )}
            
            <View style={styles.statusRow}>
              <Text style={styles.statusLabel}>Status</Text>
              <TouchableOpacity 
                style={[styles.statusBadge, { backgroundColor: store.active ? '#34C75920' : '#FF3B3020' }]}
                onPress={handleToggleActive}
              >
                <View style={[styles.statusDot, { backgroundColor: store.active ? '#34C759' : '#FF3B30' }]} />
                <Text style={[styles.statusText, { color: store.active ? '#34C759' : '#FF3B30' }]}>
                  {store.active ? 'Active' : 'Inactive'}
                </Text>
              </TouchableOpacity>
            </View>
            
            <View style={styles.statsRow}>
              <View style={styles.statItem}>
                <Ionicons name="people" size={20} color="#007AFF" />
                <Text style={styles.statValue}>{data.user_count}</Text>
                <Text style={styles.statLabel}>Users</Text>
              </View>
              <View style={styles.statItem}>
                <Ionicons name="person-add" size={20} color="#34C759" />
                <Text style={styles.statValue}>{data.available_users?.length || 0}</Text>
                <Text style={styles.statLabel}>Available</Text>
              </View>
            </View>
          </View>
          
          {/* Users Section */}
          <View style={styles.section}>
            <View style={styles.sectionHeader}>
              <Ionicons name="people" size={20} color="#007AFF" />
              <Text style={styles.sectionTitle}>Assigned Users ({data.users.length})</Text>
              <TouchableOpacity 
                style={styles.addButton}
                onPress={() => setShowAddUserModal(true)}
              >
                <Ionicons name="add-circle" size={24} color="#007AFF" />
              </TouchableOpacity>
            </View>
            
            {data.users.length === 0 ? (
              <View style={styles.emptySection}>
                <Text style={styles.emptyText}>No users assigned</Text>
                <TouchableOpacity 
                  style={styles.createButton}
                  onPress={() => setShowAddUserModal(true)}
                >
                  <Text style={styles.createButtonText}>Add User</Text>
                </TouchableOpacity>
              </View>
            ) : (
              data.users.map(user => (
                <TouchableOpacity 
                  key={user._id} 
                  style={styles.userCard}
                  onPress={() => router.push(`/admin/users/${user._id}`)}
                  data-testid={`user-card-${user._id}`}
                >
                  <View style={[styles.userAvatar, { backgroundColor: ROLE_COLORS[user.role] + '30' }]}>
                    <Text style={[styles.userAvatarText, { color: ROLE_COLORS[user.role] }]}>
                      {user.name?.split(' ').map(n => n[0]).join('').substring(0, 2) || '?'}
                    </Text>
                  </View>
                  <View style={styles.userInfo}>
                    <Text style={styles.userName}>{user.name}</Text>
                    <Text style={styles.userEmail}>{user.email}</Text>
                  </View>
                  <View style={styles.userActions}>
                    <View style={[styles.roleBadge, { backgroundColor: ROLE_COLORS[user.role] + '20' }]}>
                      <Text style={[styles.roleBadgeText, { color: ROLE_COLORS[user.role] }]}>
                        {ROLE_LABELS[user.role] || user.role}
                      </Text>
                    </View>
                    <View style={styles.userActionButtons}>
                      <TouchableOpacity 
                        style={[styles.statusToggle, { backgroundColor: user.is_active ? '#34C75920' : '#FF3B3020' }]}
                        onPress={(e) => {
                          e.stopPropagation();
                          handleToggleUserActive(user);
                        }}
                      >
                        <View style={[styles.statusDotSmall, { backgroundColor: user.is_active ? '#34C759' : '#FF3B30' }]} />
                      </TouchableOpacity>
                      <TouchableOpacity 
                        style={styles.removeButton}
                        onPress={(e) => {
                          e.stopPropagation();
                          handleRemoveUser(user);
                        }}
                      >
                        <Ionicons name="close-circle" size={22} color="#FF3B30" />
                      </TouchableOpacity>
                    </View>
                  </View>
                  <Ionicons name="chevron-forward" size={18} color="#8E8E93" style={{ marginLeft: 4 }} />
                </TouchableOpacity>
              ))
            )}
          </View>
          
          {/* Congrats Card Template Section */}
          <View style={styles.section}>
            <View style={styles.sectionHeader}>
              <Ionicons name="gift" size={20} color="#C9A962" />
              <Text style={styles.sectionTitle}>Congrats Card Template</Text>
              <TouchableOpacity 
                style={styles.addButton}
                onPress={() => setShowCongratsEditor(!showCongratsEditor)}
              >
                <Ionicons name={showCongratsEditor ? "chevron-up" : "create-outline"} size={22} color="#C9A962" />
              </TouchableOpacity>
            </View>
            
            {/* Preview Card */}
            <View style={[styles.congratsPreview, { backgroundColor: congratsTemplate.background_color }]}>
              <Text style={[styles.congratsPreviewHeadline, { color: congratsTemplate.accent_color }]}>
                {congratsTemplate.headline}
              </Text>
              <View style={[styles.congratsPreviewCircle, { borderColor: congratsTemplate.accent_color }]}>
                <Ionicons name="person" size={24} color={congratsTemplate.accent_color} />
              </View>
              <Text style={[styles.congratsPreviewText, { color: congratsTemplate.text_color }]}>
                Customer Name
              </Text>
            </View>
            
            {showCongratsEditor && (
              <View style={styles.congratsEditorContainer}>
                {/* Theme Presets */}
                <Text style={styles.congratsEditorLabel}>Color Theme</Text>
                <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.themeScrollContainer}>
                  {THEME_PRESETS.map((theme, index) => (
                    <TouchableOpacity
                      key={index}
                      style={[
                        styles.themePreset,
                        { backgroundColor: theme.bg, borderColor: theme.accent },
                        congratsTemplate.background_color === theme.bg && styles.themePresetSelected
                      ]}
                      onPress={() => setCongratsTemplate({
                        ...congratsTemplate,
                        background_color: theme.bg,
                        accent_color: theme.accent,
                        text_color: theme.text,
                      })}
                    >
                      <View style={[styles.themePresetAccent, { backgroundColor: theme.accent }]} />
                      <Text style={[styles.themePresetName, { color: theme.text }]}>{theme.name}</Text>
                    </TouchableOpacity>
                  ))}
                </ScrollView>
                
                {/* Headline */}
                <Text style={styles.congratsEditorLabel}>Headline</Text>
                <TextInput
                  style={styles.congratsEditorInput}
                  value={congratsTemplate.headline}
                  onChangeText={(text) => setCongratsTemplate({ ...congratsTemplate, headline: text })}
                  placeholder="Thank You!"
                  placeholderTextColor="#8E8E93"
                  maxLength={30}
                />
                
                {/* Message */}
                <Text style={styles.congratsEditorLabel}>Message</Text>
                <Text style={styles.congratsEditorHint}>Use {'{customer_name}'} for auto-fill</Text>
                <TextInput
                  style={[styles.congratsEditorInput, styles.congratsEditorTextArea]}
                  value={congratsTemplate.message}
                  onChangeText={(text) => setCongratsTemplate({ ...congratsTemplate, message: text })}
                  placeholder="Thank you for choosing us!"
                  placeholderTextColor="#8E8E93"
                  multiline
                  numberOfLines={3}
                  maxLength={200}
                />
                
                {/* Save Button */}
                <TouchableOpacity
                  style={styles.congratsSaveButton}
                  onPress={saveCongratsTemplate}
                  disabled={savingTemplate}
                >
                  {savingTemplate ? (
                    <ActivityIndicator size="small" color="#000" />
                  ) : (
                    <>
                      <Ionicons name="checkmark" size={20} color="#000" />
                      <Text style={styles.congratsSaveButtonText}>Save Template</Text>
                    </>
                  )}
                </TouchableOpacity>
              </View>
            )}
          </View>
          
          {/* Campaign Permissions Section */}
          <View style={styles.section}>
            <View style={styles.sectionHeader}>
              <Ionicons name="megaphone" size={20} color="#AF52DE" />
              <Text style={styles.sectionTitle}>Campaign Permissions</Text>
            </View>
            
            <View style={styles.permissionRow}>
              <View style={styles.permissionInfo}>
                <Text style={styles.permissionTitle}>Account Managers</Text>
                <Text style={styles.permissionDesc}>Allow managers to create and edit campaigns</Text>
              </View>
              <TouchableOpacity
                style={[
                  styles.toggleButton,
                  campaignSettings.managers_can_edit && styles.toggleButtonActive
                ]}
                onPress={() => setCampaignSettings({
                  ...campaignSettings,
                  managers_can_edit: !campaignSettings.managers_can_edit
                })}
                data-testid="toggle-managers-campaign"
              >
                <Ionicons 
                  name={campaignSettings.managers_can_edit ? "checkmark" : "close"} 
                  size={18} 
                  color={campaignSettings.managers_can_edit ? "#FFF" : "#8E8E93"} 
                />
              </TouchableOpacity>
            </View>
            
            <View style={styles.permissionRow}>
              <View style={styles.permissionInfo}>
                <Text style={styles.permissionTitle}>Sales Reps</Text>
                <Text style={styles.permissionDesc}>Allow sales reps to create and edit campaigns</Text>
              </View>
              <TouchableOpacity
                style={[
                  styles.toggleButton,
                  campaignSettings.sales_can_edit && styles.toggleButtonActive
                ]}
                onPress={() => setCampaignSettings({
                  ...campaignSettings,
                  sales_can_edit: !campaignSettings.sales_can_edit
                })}
                data-testid="toggle-sales-campaign"
              >
                <Ionicons 
                  name={campaignSettings.sales_can_edit ? "checkmark" : "close"} 
                  size={18} 
                  color={campaignSettings.sales_can_edit ? "#FFF" : "#8E8E93"} 
                />
              </TouchableOpacity>
            </View>
            
            <TouchableOpacity
              style={styles.saveCampaignSettingsButton}
              onPress={saveCampaignSettings}
              disabled={savingCampaignSettings}
            >
              {savingCampaignSettings ? (
                <ActivityIndicator size="small" color="#FFF" />
              ) : (
                <>
                  <Ionicons name="save-outline" size={18} color="#FFF" />
                  <Text style={styles.saveCampaignSettingsButtonText}>Save Permissions</Text>
                </>
              )}
            </TouchableOpacity>
          </View>
          
          {/* Edit Details Section */}
          {editMode && (
            <View style={styles.section}>
              <Text style={styles.sectionTitle}>Edit Store Details</Text>
              
              <Text style={styles.inputLabel}>Name</Text>
              <TextInput
                style={styles.input}
                value={editedStore.name}
                onChangeText={(text) => setEditedStore({ ...editedStore, name: text })}
                placeholder="Account name"
                placeholderTextColor="#8E8E93"
              />
              
              <Text style={styles.inputLabel}>Phone</Text>
              <TextInput
                style={styles.input}
                value={editedStore.phone}
                onChangeText={(text) => setEditedStore({ ...editedStore, phone: text })}
                placeholder="+1 (555) 123-4567"
                placeholderTextColor="#8E8E93"
                keyboardType="phone-pad"
              />
              
              <Text style={styles.inputLabel}>Address</Text>
              <TextInput
                style={styles.input}
                value={editedStore.address}
                onChangeText={(text) => setEditedStore({ ...editedStore, address: text })}
                placeholder="Street address"
                placeholderTextColor="#8E8E93"
              />
              
              <View style={styles.row}>
                <View style={styles.halfField}>
                  <Text style={styles.inputLabel}>City</Text>
                  <TextInput
                    style={styles.input}
                    value={editedStore.city}
                    onChangeText={(text) => setEditedStore({ ...editedStore, city: text })}
                    placeholder="City"
                    placeholderTextColor="#8E8E93"
                  />
                </View>
                <View style={styles.halfField}>
                  <Text style={styles.inputLabel}>State</Text>
                  <TextInput
                    style={styles.input}
                    value={editedStore.state}
                    onChangeText={(text) => setEditedStore({ ...editedStore, state: text })}
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
                  setEditedStore(store);
                }}
              >
                <Text style={styles.cancelButtonText}>Cancel</Text>
              </TouchableOpacity>
            </View>
          )}
          
          {/* Store Info (View Mode) */}
          {!editMode && (
            <View style={styles.section}>
              <Text style={styles.sectionTitle}>Account Details</Text>
              
              {store.phone && (
                <View style={styles.infoRow}>
                  <Ionicons name="call" size={18} color="#8E8E93" />
                  <Text style={styles.infoText}>{store.phone}</Text>
                </View>
              )}
              
              {store.address && (
                <View style={styles.infoRow}>
                  <Ionicons name="location" size={18} color="#8E8E93" />
                  <Text style={styles.infoText}>{store.address}</Text>
                </View>
              )}
              
              {(store.city || store.state) && (
                <View style={styles.infoRow}>
                  <Ionicons name="map" size={18} color="#8E8E93" />
                  <Text style={styles.infoText}>
                    {[store.city, store.state].filter(Boolean).join(', ')}
                  </Text>
                </View>
              )}
              
              {!store.phone && !store.address && !store.city && (
                <Text style={styles.emptyText}>No details added yet</Text>
              )}
            </View>
          )}
          
          <View style={{ height: 50 }} />
        </ScrollView>
      </KeyboardAvoidingView>
      
      {/* Add User Modal */}
      <WebModal visible={showAddUserModal} animationType="slide" transparent>
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Add User to Store</Text>
              <TouchableOpacity onPress={() => setShowAddUserModal(false)}>
                <Ionicons name="close" size={24} color="#8E8E93" />
              </TouchableOpacity>
            </View>
            
            <ScrollView style={styles.modalBody}>
              {data.available_users && data.available_users.length > 0 ? (
                data.available_users.map(user => (
                  <TouchableOpacity
                    key={user._id}
                    style={styles.availableUserOption}
                    onPress={() => handleAddUser(user._id)}
                    disabled={actionLoading}
                  >
                    <View style={[styles.userAvatar, { backgroundColor: ROLE_COLORS[user.role] + '30' }]}>
                      <Text style={[styles.userAvatarText, { color: ROLE_COLORS[user.role] }]}>
                        {user.name?.split(' ').map(n => n[0]).join('').substring(0, 2) || '?'}
                      </Text>
                    </View>
                    <View style={styles.userInfo}>
                      <Text style={styles.userName}>{user.name}</Text>
                      <Text style={styles.userEmail}>{user.email}</Text>
                    </View>
                    <Ionicons name="add-circle" size={24} color="#34C759" />
                  </TouchableOpacity>
                ))
              ) : (
                <View style={styles.emptyModal}>
                  <Ionicons name="people-outline" size={48} color="#8E8E93" />
                  <Text style={styles.emptyModalText}>No available users in this organization</Text>
                  <Text style={styles.emptyModalSubtext}>
                    All users are already assigned to this store
                  </Text>
                </View>
              )}
            </ScrollView>
          </View>
        </View>
      </WebModal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#000',
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
    width: 40,
  },
  title: {
    flex: 1,
    fontSize: 17,
    fontWeight: '600',
    color: '#FFF',
    textAlign: 'center',
  },
  saveButton: {
    color: '#007AFF',
    fontSize: 16,
    fontWeight: '600',
  },
  editButton: {
    color: '#007AFF',
    fontSize: 16,
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
    fontSize: 16,
    color: '#8E8E93',
    marginTop: 12,
  },
  content: {
    flex: 1,
    padding: 16,
  },
  statusCard: {
    backgroundColor: '#1C1C1E',
    borderRadius: 16,
    padding: 16,
    marginBottom: 16,
  },
  orgBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    backgroundColor: '#007AFF20',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 20,
    marginBottom: 12,
    gap: 6,
  },
  orgBadgeText: {
    color: '#007AFF',
    fontSize: 13,
    fontWeight: '600',
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
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 12,
    gap: 6,
  },
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  statusDotSmall: {
    width: 6,
    height: 6,
    borderRadius: 3,
  },
  statusText: {
    fontSize: 14,
    fontWeight: '600',
  },
  statsRow: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: '#2C2C2E',
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
    borderRadius: 16,
    padding: 16,
    marginBottom: 16,
  },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 12,
  },
  sectionTitle: {
    flex: 1,
    fontSize: 16,
    fontWeight: '600',
    color: '#FFF',
  },
  addButton: {
    marginLeft: 'auto',
  },
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
  userCard: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 12,
    backgroundColor: '#2C2C2E',
    borderRadius: 12,
    marginBottom: 8,
    gap: 12,
  },
  userAvatar: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: 'center',
    justifyContent: 'center',
  },
  userAvatarText: {
    fontSize: 14,
    fontWeight: '700',
  },
  userInfo: {
    flex: 1,
  },
  userName: {
    fontSize: 15,
    fontWeight: '600',
    color: '#FFF',
  },
  userEmail: {
    fontSize: 12,
    color: '#8E8E93',
    marginTop: 2,
  },
  userActions: {
    alignItems: 'flex-end',
    gap: 8,
  },
  roleBadge: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
  },
  roleBadgeText: {
    fontSize: 10,
    fontWeight: '700',
  },
  userActionButtons: {
    flexDirection: 'row',
    gap: 8,
  },
  statusToggle: {
    width: 28,
    height: 28,
    borderRadius: 14,
    alignItems: 'center',
    justifyContent: 'center',
  },
  removeButton: {
    padding: 2,
  },
  infoRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: '#2C2C2E',
  },
  infoText: {
    flex: 1,
    fontSize: 15,
    color: '#FFF',
  },
  inputLabel: {
    fontSize: 13,
    fontWeight: '600',
    color: '#8E8E93',
    marginBottom: 8,
    marginTop: 12,
  },
  input: {
    backgroundColor: '#2C2C2E',
    borderRadius: 10,
    padding: 14,
    fontSize: 16,
    color: '#FFF',
  },
  row: {
    flexDirection: 'row',
    gap: 12,
  },
  halfField: {
    flex: 1,
  },
  cancelButton: {
    alignItems: 'center',
    paddingVertical: 14,
    marginTop: 16,
  },
  cancelButtonText: {
    fontSize: 16,
    color: '#FF3B30',
  },
  // Modal styles
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.8)',
    justifyContent: 'flex-end',
  },
  modalContent: {
    backgroundColor: '#1C1C1E',
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    maxHeight: '70%',
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#2C2C2E',
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: '#FFF',
  },
  modalBody: {
    padding: 16,
    maxHeight: 400,
  },
  availableUserOption: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 12,
    backgroundColor: '#2C2C2E',
    borderRadius: 12,
    marginBottom: 8,
    gap: 12,
  },
  emptyModal: {
    alignItems: 'center',
    paddingVertical: 40,
  },
  emptyModalText: {
    color: '#8E8E93',
    fontSize: 15,
    marginTop: 12,
    textAlign: 'center',
  },
  emptyModalSubtext: {
    color: '#636366',
    fontSize: 13,
    marginTop: 4,
    textAlign: 'center',
  },
  // Congrats Card Template Styles
  congratsPreview: {
    borderRadius: 12,
    padding: 20,
    alignItems: 'center',
    marginTop: 12,
  },
  congratsPreviewHeadline: {
    fontSize: 20,
    fontWeight: '700',
    marginBottom: 12,
  },
  congratsPreviewCircle: {
    width: 50,
    height: 50,
    borderRadius: 25,
    borderWidth: 3,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 8,
  },
  congratsPreviewText: {
    fontSize: 14,
    fontWeight: '500',
  },
  congratsEditorContainer: {
    marginTop: 16,
    paddingTop: 16,
    borderTopWidth: 1,
    borderTopColor: '#2C2C2E',
  },
  congratsEditorLabel: {
    fontSize: 14,
    fontWeight: '600',
    color: '#FFF',
    marginBottom: 8,
    marginTop: 12,
  },
  congratsEditorHint: {
    fontSize: 12,
    color: '#8E8E93',
    marginTop: -4,
    marginBottom: 8,
  },
  congratsEditorInput: {
    backgroundColor: '#2C2C2E',
    borderRadius: 10,
    padding: 12,
    fontSize: 15,
    color: '#FFF',
  },
  congratsEditorTextArea: {
    minHeight: 80,
    textAlignVertical: 'top',
  },
  themeScrollContainer: {
    marginBottom: 8,
  },
  themePreset: {
    width: 100,
    padding: 12,
    borderRadius: 10,
    marginRight: 10,
    borderWidth: 2,
    alignItems: 'center',
  },
  themePresetSelected: {
    borderWidth: 3,
  },
  themePresetAccent: {
    width: 30,
    height: 6,
    borderRadius: 3,
    marginBottom: 6,
  },
  themePresetName: {
    fontSize: 11,
    fontWeight: '500',
  },
  congratsSaveButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#C9A962',
    borderRadius: 10,
    padding: 14,
    marginTop: 20,
    gap: 8,
  },
  congratsSaveButtonText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#000',
  },
  // Campaign Permissions Styles
  permissionRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: '#2C2C2E',
    borderRadius: 12,
    padding: 16,
    marginTop: 12,
  },
  permissionInfo: {
    flex: 1,
    marginRight: 12,
  },
  permissionTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFF',
  },
  permissionDesc: {
    fontSize: 13,
    color: '#8E8E93',
    marginTop: 2,
  },
  toggleButton: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: '#3C3C3E',
    alignItems: 'center',
    justifyContent: 'center',
  },
  toggleButtonActive: {
    backgroundColor: '#AF52DE',
  },
  saveCampaignSettingsButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#AF52DE',
    borderRadius: 10,
    padding: 14,
    marginTop: 20,
    gap: 8,
  },
  saveCampaignSettingsButtonText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFF',
  },
});
