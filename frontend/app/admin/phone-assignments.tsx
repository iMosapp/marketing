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
  ScrollView,
  KeyboardAvoidingView,
  Platform,
  Keyboard,
  TouchableWithoutFeedback,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import { useAuthStore } from '../../store/authStore';
import axios from 'axios';
import { showAlert, showSimpleAlert, showConfirm } from '../../services/alert';
import { WebModal } from '../../components/WebModal';

const API_URL = Platform.OS === 'web' ? '' : (process.env.EXPO_PUBLIC_BACKEND_URL || '');

interface User {
  _id: string;
  name: string;
  email: string;
  phone?: string;
  mvpline_number?: string;
  role?: string;
}

interface SharedInbox {
  _id: string;
  name: string;
  phone_number?: string;
  assigned_users?: string[];
  active?: boolean;
}

export default function PhoneAssignmentsScreen() {
  const router = useRouter();
  const currentUser = useAuthStore((state) => state.user);
  
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [users, setUsers] = useState<User[]>([]);
  const [sharedInboxes, setSharedInboxes] = useState<SharedInbox[]>([]);
  const [activeTab, setActiveTab] = useState<'users' | 'shared'>('users');
  
  // Edit modal state
  const [showEditsetShowEditModal] = useState(false);
  const [editingItem, setEditingItem] = useState<User | SharedInbox | null>(null);
  const [editingType, setEditingType] = useState<'user' | 'shared'>('user');
  const [phoneNumber, setPhoneNumber] = useState('');
  const [saving, setSaving] = useState(false);
  
  useFocusEffect(
    useCallback(() => {
      loadData();
    }, [])
  );
  
  const loadData = async () => {
    try {
      setLoading(true);
      await Promise.all([loadUsers(), loadSharedInboxes()]);
    } catch (error) {
      console.error('Failed to load data:', error);
    } finally {
      setLoading(false);
    }
  };
  
  const loadUsers = async () => {
    try {
      const response = await axios.get(`${API_URL}/api/admin/phone-assignments/users`);
      setUsers(response.data);
    } catch (error) {
      console.error('Failed to load users:', error);
    }
  };
  
  const loadSharedInboxes = async () => {
    try {
      const response = await axios.get(`${API_URL}/api/admin/team/shared-inboxes?user_id=${currentUser?._id || currentUser?.id}`);
      setSharedInboxes(response.data);
    } catch (error) {
      console.error('Failed to load shared inboxes:', error);
    }
  };
  
  const onRefresh = async () => {
    setRefreshing(true);
    await loadData();
    setRefreshing(false);
  };
  
  const openEditModal = (item: User | SharedInbox, type: 'user' | 'shared') => {
    setEditingItem(item);
    setEditingType(type);
    if (type === 'user') {
      setPhoneNumber((item as User).mvpline_number || '');
    } else {
      setPhoneNumber((item as SharedInbox).phone_number || '');
    }
    setShowEditModal(true);
  };
  
  const formatPhoneNumber = (value: string) => {
    // Remove all non-digit characters except +
    const cleaned = value.replace(/[^\d+]/g, '');
    
    // If starts with +, keep it
    if (cleaned.startsWith('+')) {
      return cleaned;
    }
    
    // If 10 digits, format as US number
    if (cleaned.length === 10) {
      return `+1${cleaned}`;
    }
    
    // If 11 digits starting with 1, format as US number
    if (cleaned.length === 11 && cleaned.startsWith('1')) {
      return `+${cleaned}`;
    }
    
    return cleaned;
  };
  
  const savePhoneNumber = async () => {
    if (!editingItem) return;
    
    const formattedPhone = formatPhoneNumber(phoneNumber);
    
    // Validate phone format
    if (formattedPhone && !formattedPhone.match(/^\+\d{10,15}$/)) {
      showSimpleAlert('Invalid Format', 'Please enter a valid phone number (e.g., +14155551234)');
      return;
    }
    
    setSaving(true);
    try {
      if (editingType === 'user') {
        await axios.put(`${API_URL}/api/admin/phone-assignments/users/${editingItem._id}`, {
          mvpline_number: formattedPhone || null
        });
        showSimpleAlert('Success', 'Phone number updated successfully');
      } else {
        await axios.put(`${API_URL}/api/admin/team/shared-inboxes/${editingItem._id}`, {
          phone_number: formattedPhone || null
        });
        showSimpleAlert('Success', 'Shared inbox phone updated successfully');
      }
      
      setShowEditModal(false);
      await loadData();
    } catch (error: any) {
      const message = error.response?.data?.detail || 'Failed to update phone number';
      showSimpleAlert('Error', message);
    } finally {
      setSaving(false);
    }
  };
  
  const clearPhoneNumber = async () => {
    showConfirm(
      'Remove Phone Number',
      'Are you sure you want to remove this phone number assignment?',
      async () => {
        setPhoneNumber('');
        await savePhoneNumber();
      }
    );
  };
  
  const renderUserItem = ({ item }: { item: User }) => {
    const hasPhone = !!item.mvpline_number;
    
    return (
      <TouchableOpacity
        style={[styles.card, hasPhone && styles.cardAssigned]}
        onPress={() => openEditModal(item, 'user')}
        data-testid={`user-card-${item._id}`}
      >
        <View style={styles.cardHeader}>
          <View style={styles.userInfo}>
            <Ionicons 
              name={hasPhone ? "call" : "person"} 
              size={24} 
              color={hasPhone ? "#34C759" : "#8E8E93"} 
            />
            <View style={styles.userDetails}>
              <Text style={styles.userName}>{item.name}</Text>
              <Text style={styles.userEmail}>{item.email}</Text>
            </View>
          </View>
          <Ionicons name="chevron-forward" size={20} color="#C7C7CC" />
        </View>
        
        <View style={styles.phoneSection}>
          {hasPhone ? (
            <View style={styles.phoneAssigned}>
              <Ionicons name="checkmark-circle" size={16} color="#34C759" />
              <Text style={styles.phoneNumber}>{item.mvpline_number}</Text>
            </View>
          ) : (
            <View style={styles.phoneUnassigned}>
              <Ionicons name="add-circle-outline" size={16} color="#8E8E93" />
              <Text style={styles.noPhone}>No phone assigned</Text>
            </View>
          )}
        </View>
        
        {item.role && (
          <View style={styles.roleTag}>
            <Text style={styles.roleText}>{item.role.replace('_', ' ').toUpperCase()}</Text>
          </View>
        )}
      </TouchableOpacity>
    );
  };
  
  const renderSharedInboxItem = ({ item }: { item: SharedInbox }) => {
    const hasPhone = !!item.phone_number;
    const userCount = item.assigned_users?.length || 0;
    
    return (
      <TouchableOpacity
        style={[styles.card, hasPhone && styles.cardAssigned]}
        onPress={() => openEditModal(item, 'shared')}
        data-testid={`inbox-card-${item._id}`}
      >
        <View style={styles.cardHeader}>
          <View style={styles.userInfo}>
            <Ionicons 
              name={hasPhone ? "chatbubbles" : "chatbubbles-outline"} 
              size={24} 
              color={hasPhone ? "#007AFF" : "#8E8E93"} 
            />
            <View style={styles.userDetails}>
              <Text style={styles.userName}>{item.name}</Text>
              <Text style={styles.userEmail}>{userCount} user{userCount !== 1 ? 's' : ''} assigned</Text>
            </View>
          </View>
          <Ionicons name="chevron-forward" size={20} color="#C7C7CC" />
        </View>
        
        <View style={styles.phoneSection}>
          {hasPhone ? (
            <View style={styles.phoneAssigned}>
              <Ionicons name="checkmark-circle" size={16} color="#34C759" />
              <Text style={styles.phoneNumber}>{item.phone_number}</Text>
            </View>
          ) : (
            <View style={styles.phoneUnassigned}>
              <Ionicons name="add-circle-outline" size={16} color="#8E8E93" />
              <Text style={styles.noPhone}>No phone assigned</Text>
            </View>
          )}
        </View>
        
        {!item.active && (
          <View style={[styles.roleTag, { backgroundColor: '#FF3B30' }]}>
            <Text style={styles.roleText}>INACTIVE</Text>
          </View>
        )}
      </TouchableOpacity>
    );
  };
  
  const assignedUsersCount = users.filter(u => u.mvpline_number).length;
  const assignedInboxesCount = sharedInboxes.filter(i => i.phone_number).length;
  
  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="arrow-back" size={24} color="#007AFF" />
        </TouchableOpacity>
        <Text style={styles.title}>Phone Assignments</Text>
        <View style={{ width: 40 }} />
      </View>
      
      {/* Info Card */}
      <View style={styles.infoCard}>
        <Ionicons name="information-circle" size={20} color="#007AFF" />
        <Text style={styles.infoText}>
          Assign Twilio phone numbers to users or shared inboxes. Inbound messages will be routed based on which number receives them.
        </Text>
      </View>
      
      {/* Tab Selector */}
      <View style={styles.tabContainer}>
        <TouchableOpacity
          style={[styles.tab, activeTab === 'users' && styles.tabActive]}
          onPress={() => setActiveTab('users')}
          data-testid="tab-users"
        >
          <Ionicons 
            name="person" 
            size={18} 
            color={activeTab === 'users' ? '#007AFF' : '#8E8E93'} 
          />
          <Text style={[styles.tabText, activeTab === 'users' && styles.tabTextActive]}>
            Users ({assignedUsersCount}/{users.length})
          </Text>
        </TouchableOpacity>
        
        <TouchableOpacity
          style={[styles.tab, activeTab === 'shared' && styles.tabActive]}
          onPress={() => setActiveTab('shared')}
          data-testid="tab-shared"
        >
          <Ionicons 
            name="chatbubbles" 
            size={18} 
            color={activeTab === 'shared' ? '#007AFF' : '#8E8E93'} 
          />
          <Text style={[styles.tabText, activeTab === 'shared' && styles.tabTextActive]}>
            Shared Inboxes ({assignedInboxesCount}/{sharedInboxes.length})
          </Text>
        </TouchableOpacity>
      </View>
      
      {/* Content */}
      {loading ? (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#007AFF" />
          <Text style={styles.loadingText}>Loading...</Text>
        </View>
      ) : (
        <FlatList
          data={activeTab === 'users' ? users : sharedInboxes}
          renderItem={activeTab === 'users' ? renderUserItem : renderSharedInboxItem}
          keyExtractor={(item) => item._id}
          contentContainerStyle={styles.listContent}
          refreshControl={
            <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#007AFF" />
          }
          ListEmptyComponent={
            <View style={styles.emptyContainer}>
              <Ionicons name="phone-portrait-outline" size={48} color="#C7C7CC" />
              <Text style={styles.emptyText}>
                {activeTab === 'users' ? 'No users found' : 'No shared inboxes found'}
              </Text>
            </View>
          }
        />
      )}
      
      {/* Edit Modal */}
      <WebModal visible={showEditModal} animationType="slide" transparent>
        <KeyboardAvoidingView 
          behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
          style={styles.modalOverlay}
        >
          <TouchableWithoutFeedback onPress={Keyboard.dismiss}>
            <View style={styles.modalOverlay}>
              <View style={styles.modalContent}>
                <View style={styles.modalHeader}>
                  <Text style={styles.modalTitle}>
                    {editingType === 'user' ? 'Assign Phone Number' : 'Shared Inbox Phone'}
                  </Text>
                  <TouchableOpacity onPress={() => setShowEditModal(false)}>
                    <Ionicons name="close" size={24} color="#8E8E93" />
                  </TouchableOpacity>
                </View>
                
                <ScrollView 
                  style={styles.modalBody}
                  keyboardShouldPersistTaps="handled"
                  showsVerticalScrollIndicator={false}
                >
                  <Text style={styles.editingName}>
                    {editingItem ? ('name' in editingItem ? editingItem.name : '') : ''}
                  </Text>
                  
                  <Text style={styles.inputLabel}>Twilio Phone Number</Text>
                  <TextInput
                    style={styles.phoneInput}
                    value={phoneNumber}
                    onChangeText={setPhoneNumber}
                    placeholder="+1 (555) 123-4567"
                    placeholderTextColor="#C7C7CC"
                    keyboardType="phone-pad"
                    autoFocus
                    data-testid="phone-input"
                  />
                  <Text style={styles.inputHint}>
                    Enter the Twilio phone number in E.164 format (e.g., +14155551234)
                  </Text>
                  
                  <View style={styles.routingInfo}>
                    <Ionicons name="git-branch-outline" size={20} color="#FF9500" />
                    <Text style={styles.routingText}>
                      {editingType === 'user' 
                        ? 'Messages sent to this number will appear in this user\'s inbox'
                        : 'Messages sent to this number will be distributed to assigned users'
                      }
                    </Text>
                  </View>
                </ScrollView>
                
                <View style={styles.modalFooter}>
                  {phoneNumber && (
                    <TouchableOpacity
                      style={styles.clearButton}
                      onPress={clearPhoneNumber}
                      disabled={saving}
                    >
                      <Text style={styles.clearButtonText}>Remove</Text>
                    </TouchableOpacity>
                  )}
                  
                  <TouchableOpacity
                    style={[styles.saveButton, saving && styles.saveButtonDisabled]}
                    onPress={savePhoneNumber}
                    disabled={saving}
                    data-testid="save-phone-button"
                  >
                    {saving ? (
                      <ActivityIndicator size="small" color="#fff" />
                    ) : (
                      <Text style={styles.saveButtonText}>Save</Text>
                    )}
                  </TouchableOpacity>
                </View>
              </View>
            </View>
          </TouchableWithoutFeedback>
        </KeyboardAvoidingView>
      </WebModal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F2F2F7',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
    backgroundColor: '#fff',
    borderBottomWidth: 1,
    borderBottomColor: '#E5E5EA',
  },
  backButton: {
    padding: 8,
  },
  title: {
    fontSize: 17,
    fontWeight: '600',
    color: '#000',
  },
  infoCard: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    backgroundColor: '#E8F4FD',
    margin: 16,
    padding: 12,
    borderRadius: 10,
    gap: 10,
  },
  infoText: {
    flex: 1,
    fontSize: 13,
    color: '#007AFF',
    lineHeight: 18,
  },
  tabContainer: {
    flexDirection: 'row',
    marginHorizontal: 16,
    marginBottom: 16,
    backgroundColor: '#fff',
    borderRadius: 10,
    padding: 4,
  },
  tab: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 10,
    borderRadius: 8,
    gap: 6,
  },
  tabActive: {
    backgroundColor: '#E8F4FD',
  },
  tabText: {
    fontSize: 14,
    color: '#8E8E93',
    fontWeight: '500',
  },
  tabTextActive: {
    color: '#007AFF',
  },
  listContent: {
    paddingHorizontal: 16,
    paddingBottom: 100,
  },
  card: {
    backgroundColor: '#fff',
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 2,
    elevation: 1,
  },
  cardAssigned: {
    borderLeftWidth: 3,
    borderLeftColor: '#34C759',
  },
  cardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  userInfo: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    flex: 1,
  },
  userDetails: {
    flex: 1,
  },
  userName: {
    fontSize: 16,
    fontWeight: '600',
    color: '#000',
  },
  userEmail: {
    fontSize: 13,
    color: '#8E8E93',
    marginTop: 2,
  },
  phoneSection: {
    marginTop: 12,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: '#E5E5EA',
  },
  phoneAssigned: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  phoneNumber: {
    fontSize: 15,
    color: '#34C759',
    fontWeight: '500',
    fontFamily: 'monospace',
  },
  phoneUnassigned: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  noPhone: {
    fontSize: 14,
    color: '#8E8E93',
    fontStyle: 'italic',
  },
  roleTag: {
    position: 'absolute',
    top: 8,
    right: 8,
    backgroundColor: '#007AFF',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 4,
  },
  roleText: {
    fontSize: 10,
    fontWeight: '600',
    color: '#fff',
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  loadingText: {
    marginTop: 10,
    color: '#8E8E93',
  },
  emptyContainer: {
    alignItems: 'center',
    paddingTop: 60,
  },
  emptyText: {
    marginTop: 12,
    fontSize: 16,
    color: '#8E8E93',
  },
  // Modal styles
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.5)',
    justifyContent: 'flex-end',
  },
  modalContent: {
    backgroundColor: '#fff',
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    paddingBottom: 34,
  },
  modalHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#E5E5EA',
  },
  modalTitle: {
    fontSize: 17,
    fontWeight: '600',
    color: '#000',
  },
  modalBody: {
    paddingHorizontal: 16,
    paddingTop: 16,
    paddingBottom: 16,
    maxHeight: 300,
  },
  editingName: {
    fontSize: 20,
    fontWeight: '700',
    color: '#000',
    marginBottom: 20,
  },
  inputLabel: {
    fontSize: 13,
    fontWeight: '600',
    color: '#8E8E93',
    marginBottom: 8,
    textTransform: 'uppercase',
  },
  phoneInput: {
    backgroundColor: '#F2F2F7',
    borderRadius: 10,
    padding: 14,
    fontSize: 18,
    fontFamily: 'monospace',
    color: '#000',
  },
  inputHint: {
    fontSize: 12,
    color: '#8E8E93',
    marginTop: 8,
  },
  routingInfo: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    backgroundColor: '#FFF9E6',
    padding: 12,
    borderRadius: 10,
    marginTop: 20,
    gap: 10,
  },
  routingText: {
    flex: 1,
    fontSize: 13,
    color: '#996600',
    lineHeight: 18,
  },
  modalFooter: {
    flexDirection: 'row',
    padding: 16,
    gap: 12,
  },
  clearButton: {
    flex: 1,
    backgroundColor: '#FFE5E5',
    padding: 14,
    borderRadius: 10,
    alignItems: 'center',
  },
  clearButtonText: {
    color: '#FF3B30',
    fontSize: 16,
    fontWeight: '600',
  },
  saveButton: {
    flex: 2,
    backgroundColor: '#007AFF',
    padding: 14,
    borderRadius: 10,
    alignItems: 'center',
  },
  saveButtonDisabled: {
    opacity: 0.6,
  },
  saveButtonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '600',
  },
});
