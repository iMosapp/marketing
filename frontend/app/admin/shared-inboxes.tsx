import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  Pressable,
  StyleSheet,
  ScrollView,
  ActivityIndicator,
  TextInput,
  RefreshControl,
  KeyboardAvoidingView,
  Platform,
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { useAuthStore } from '../../store/authStore';
import { showSimpleAlert, showConfirm } from '../../services/alert';
import { WebModal } from '../../components/WebModal';

import { useThemeStore } from '../../store/themeStore';
const IS_WEB = Platform.OS === 'web';

interface SharedInbox {
  id: string;
  name: string;
  phone_number: string;
  description?: string;
  assigned_users: { id: string; name: string; email: string }[];
  is_active: boolean;
  created_at?: string;
}

interface User {
  id: string;
  name: string;
  email: string;
  role: string;
  phone?: string;
  shared_inbox_ids?: string[];
}

export default function SharedInboxesPage() {
  const { colors } = useThemeStore();
  const styles = getStyles(colors);
  const router = useRouter();
  const { user } = useAuthStore();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [inboxes, setInboxes] = useState<SharedInbox[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  
  // Modals
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showAssignModal, setShowAssignModal] = useState(false);
  const [selectedInbox, setSelectedInbox] = useState<SharedInbox | null>(null);
  
  // Create form
  const [newInbox, setNewInbox] = useState({
    name: '',
    phone_number: '',
    description: '',
  });

  useEffect(() => {
    if (user?._id) {
      loadData();
    }
  }, [user?._id]);

  const loadData = async () => {
    if (!user?._id) {
      setLoading(false);
      return;
    }
    try {
      const [inboxRes, usersRes] = await Promise.all([
        api.get(`/admin/team/shared-inboxes?user_id=${user._id}`),
        api.get(`/admin/team/users?user_id=${user._id}`),
      ]);
      setInboxes(inboxRes.data);
      setUsers(usersRes.data);
    } catch (error) {
      console.error('Error loading shared inboxes:', error);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const onRefresh = () => {
    setRefreshing(true);
    loadData();
  };

  const handleCreateInbox = async () => {
    if (!newInbox.name || !newInbox.phone_number) {
      showSimpleAlert('Error', 'Name and phone number are required');
      return;
    }
    
    try {
      await api.post(`/admin/team/shared-inboxes?user_id=${user?._id}`, newInbox);
      showSimpleAlert('Success', 'Shared inbox created');
      setShowCreateModal(false);
      setNewInbox({ name: '', phone_number: '', description: '' });
      loadData();
    } catch (error: any) {
      showSimpleAlert('Error', error.response?.data?.detail || 'Failed to create inbox');
    }
  };

  const handleAssignUser = async (userId: string) => {
    if (!selectedInbox) return;
    
    try {
      await api.post(
        `/admin/team/shared-inboxes/${selectedInbox.id}/assign?target_user_id=${userId}&user_id=${user?._id}`
      );
      showSimpleAlert('Success', 'User assigned to inbox');
      loadData();
    } catch (error: any) {
      showSimpleAlert('Error', error.response?.data?.detail || 'Failed to assign user');
    }
  };

  const handleUnassignUser = async (inboxId: string, userId: string) => {
    showConfirm(
      'Remove User',
      'Are you sure you want to remove this user from the inbox?',
      async () => {
        try {
          await api.post(
            `/admin/team/shared-inboxes/${inboxId}/unassign?target_user_id=${userId}&user_id=${user?._id}`
          );
          showSimpleAlert('Success', 'User removed from inbox');
          loadData();
        } catch (error: any) {
          showSimpleAlert('Error', error.response?.data?.detail || 'Failed to remove user');
        }
      }
    );
  };

  const handleDeleteInbox = async (inbox: SharedInbox) => {
    showConfirm(
      'Deactivate Inbox',
      `Are you sure you want to deactivate "${inbox.name}"? Users will no longer have access.`,
      async () => {
        try {
          await api.delete(`/admin/team/shared-inboxes/${inbox.id}?user_id=${user?._id}`);
          showSimpleAlert('Success', 'Inbox deactivated');
          loadData();
        } catch (error: any) {
          showSimpleAlert('Error', error.response?.data?.detail || 'Failed to deactivate inbox');
        }
      }
    );
  };

  const openAssignModal = (inbox: SharedInbox) => {
    setSelectedInbox(inbox);
    setShowAssignModal(true);
  };

  const getUnassignedUsers = () => {
    if (!selectedInbox) return users;
    const assignedIds = new Set(selectedInbox.assigned_users.map(u => u.id));
    return users.filter(u => !assignedIds.has(u.id));
  };

  const renderInboxCard = (inbox: SharedInbox) => (
    <View key={inbox.id} style={styles.inboxCard} data-testid={`inbox-${inbox.id}`}>
      <View style={styles.inboxHeader}>
        <View style={styles.inboxIcon}>
          <Ionicons name="mail" size={24} color="#007AFF" />
        </View>
        <View style={styles.inboxInfo}>
          <Text style={styles.inboxName}>{inbox.name}</Text>
          <Text style={styles.inboxPhone}>{inbox.phone_number}</Text>
          {inbox.description && (
            <Text style={styles.inboxDescription}>{inbox.description}</Text>
          )}
        </View>
        <TouchableOpacity
          style={styles.deleteButton}
          onPress={() => handleDeleteInbox(inbox)}
          data-testid={`delete-inbox-${inbox.id}`}
        >
          <Ionicons name="trash-outline" size={20} color="#FF3B30" />
        </TouchableOpacity>
      </View>
      
      {/* Assigned Users */}
      <View style={styles.assignedSection}>
        <View style={styles.assignedHeader}>
          <Text style={styles.assignedTitle}>
            Assigned Users ({inbox.assigned_users.length})
          </Text>
          <TouchableOpacity
            style={styles.addUserButton}
            onPress={() => openAssignModal(inbox)}
            data-testid={`add-user-${inbox.id}`}
          >
            <Ionicons name="person-add" size={16} color="#007AFF" />
            <Text style={styles.addUserText}>Add</Text>
          </TouchableOpacity>
        </View>
        
        {inbox.assigned_users.length === 0 ? (
          <Text style={styles.noUsers}>No users assigned yet</Text>
        ) : (
          <View style={styles.userChips}>
            {inbox.assigned_users.map((assignedUser) => (
              <View key={assignedUser.id} style={styles.userChip}>
                <Text style={styles.userChipText}>{assignedUser.name}</Text>
                <TouchableOpacity
                  onPress={() => handleUnassignUser(inbox.id, assignedUser.id)}
                  data-testid={`remove-user-${assignedUser.id}`}
                >
                  <Ionicons name="close-circle" size={18} color={colors.textSecondary} />
                </TouchableOpacity>
              </View>
            ))}
          </View>
        )}
      </View>
    </View>
  );

  return (
    <SafeAreaView style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="chevron-back" size={28} color="#007AFF" />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Shared Inboxes</Text>
        <TouchableOpacity
          onPress={() => setShowCreateModal(true)}
          data-testid="create-inbox-btn"
        >
          <Ionicons name="add-circle" size={28} color="#007AFF" />
        </TouchableOpacity>
      </View>

      {/* Info Banner */}
      <View style={styles.infoBanner}>
        <Ionicons name="information-circle" size={20} color="#007AFF" />
        <Text style={styles.infoText}>
          Shared inboxes allow multiple team members to manage the same phone number
        </Text>
      </View>

      <ScrollView
        style={styles.content}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#007AFF" />
        }
      >
        {loading ? (
          <ActivityIndicator color="#007AFF" style={{ marginTop: 40 }} />
        ) : inboxes.length === 0 ? (
          <View style={styles.emptyState}>
            <Ionicons name="mail-outline" size={64} color={colors.surface} />
            <Text style={styles.emptyText}>No shared inboxes yet</Text>
            <Text style={styles.emptySubtext}>Create one to let multiple users manage the same number</Text>
            <TouchableOpacity
              style={styles.createButton}
              onPress={() => setShowCreateModal(true)}
            >
              <Ionicons name="add" size={20} color={colors.text} />
              <Text style={styles.createButtonText}>Create Shared Inbox</Text>
            </TouchableOpacity>
          </View>
        ) : (
          <>
            {inboxes.map(renderInboxCard)}
            <View style={{ height: 100 }} />
          </>
        )}
      </ScrollView>

      {/* Create Modal */}
      <WebModal visible={showCreateModal} animationType="slide" transparent>
        <KeyboardAvoidingView 
          behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
          style={styles.modalOverlay}
        >
          <Pressable 
            style={styles.modalOverlay} 
            onPress={() => !IS_WEB && setShowCreateModal(false)}
          >
            <Pressable style={styles.modalContent} onPress={(e) => e.stopPropagation()}>
              <View style={styles.modalHeader}>
                <Text style={styles.modalTitle}>Create Shared Inbox</Text>
                {IS_WEB ? (
                  <button
                    type="button"
                    onClick={() => setShowCreateModal(false)}
                    style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 4 }}
                    data-testid="close-create-modal"
                  >
                    <Ionicons name="close" size={24} color={colors.textSecondary} />
                  </button>
                ) : (
                  <TouchableOpacity onPress={() => setShowCreateModal(false)}>
                    <Ionicons name="close" size={24} color={colors.textSecondary} />
                  </TouchableOpacity>
                )}
              </View>
              
              <ScrollView style={styles.modalBody} keyboardShouldPersistTaps="handled">
                <Text style={styles.inputLabel}>Inbox Name *</Text>
                <TextInput
                  style={styles.input}
                  value={newInbox.name}
                  onChangeText={(text) => setNewInbox({...newInbox, name: text})}
                  placeholder="e.g., Sales Team"
                  placeholderTextColor={colors.textSecondary}
                  data-testid="inbox-name-input"
                />
                
                <Text style={styles.inputLabel}>Phone Number *</Text>
                <TextInput
                  style={styles.input}
                  value={newInbox.phone_number}
                  onChangeText={(text) => setNewInbox({...newInbox, phone_number: text})}
                  placeholder="+1 555 123 4567"
                  placeholderTextColor={colors.textSecondary}
                  keyboardType="phone-pad"
                  data-testid="inbox-phone-input"
                />
                
                <Text style={styles.inputLabel}>Description</Text>
                <TextInput
                  style={[styles.input, styles.textArea]}
                  value={newInbox.description}
                  onChangeText={(text) => setNewInbox({...newInbox, description: text})}
                  placeholder="What is this inbox for?"
                  placeholderTextColor={colors.textSecondary}
                  multiline
                  numberOfLines={3}
                  data-testid="inbox-description-input"
                />
              </ScrollView>
              
              {IS_WEB ? (
                <button
                  type="button"
                  onClick={handleCreateInbox}
                  style={{
                    display: 'flex',
                    flexDirection: 'row',
                    alignItems: 'center',
                    justifyContent: 'center',
                    backgroundColor: '#007AFF',
                    borderRadius: 12,
                    padding: 16,
                    margin: 16,
                    gap: 8,
                    border: 'none',
                    cursor: 'pointer',
                  }}
                  data-testid="create-inbox-submit"
                >
                  <Ionicons name="checkmark-circle" size={20} color={colors.text} />
                  <Text style={styles.submitButtonText}>Create Inbox</Text>
                </button>
              ) : (
                <TouchableOpacity style={styles.submitButton} onPress={handleCreateInbox}>
                  <Ionicons name="checkmark-circle" size={20} color={colors.text} />
                  <Text style={styles.submitButtonText}>Create Inbox</Text>
                </TouchableOpacity>
              )}
            </Pressable>
          </Pressable>
        </KeyboardAvoidingView>
      </WebModal>

      {/* Assign User Modal */}
      <WebModal visible={showAssignModal} animationType="slide" transparent>
        <Pressable 
          style={styles.modalOverlay}
          onPress={() => !IS_WEB && setShowAssignModal(false)}
        >
          <Pressable style={styles.modalContent} onPress={(e) => e.stopPropagation()}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Add User to {selectedInbox?.name}</Text>
              {IS_WEB ? (
                <button
                  type="button"
                  onClick={() => setShowAssignModal(false)}
                  style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 4 }}
                  data-testid="close-assign-modal"
                >
                  <Ionicons name="close" size={24} color={colors.textSecondary} />
                </button>
              ) : (
                <TouchableOpacity onPress={() => setShowAssignModal(false)}>
                  <Ionicons name="close" size={24} color={colors.textSecondary} />
                </TouchableOpacity>
              )}
            </View>
            
            <ScrollView style={styles.modalBody}>
              {getUnassignedUsers().length === 0 ? (
                <Text style={styles.noUsers}>All users are already assigned</Text>
              ) : (
                getUnassignedUsers().map((u) => (
                  IS_WEB ? (
                    <button
                      key={u.id}
                      type="button"
                      onClick={() => {
                        handleAssignUser(u.id);
                        setShowAssignModal(false);
                      }}
                      style={{
                        display: 'flex',
                        flexDirection: 'row',
                        alignItems: 'center',
                        padding: 12,
                        borderBottom: '1px solid #2C2C2E',
                        background: 'none',
                        border: 'none',
                        borderBottomWidth: 1,
                        borderBottomColor: colors.surface,
                        width: '100%',
                        cursor: 'pointer',
                      }}
                      data-testid={`select-user-${u.id}`}
                    >
                      <View style={styles.userAvatar}>
                        <Text style={styles.userAvatarText}>
                          {u.name.split(' ').map(n => n[0]).join('')}
                        </Text>
                      </View>
                      <View style={styles.userSelectInfo}>
                        <Text style={styles.userSelectName}>{u.name}</Text>
                        <Text style={styles.userSelectEmail}>{u.email}</Text>
                      </View>
                      <Ionicons name="add-circle" size={24} color="#34C759" />
                    </button>
                  ) : (
                    <TouchableOpacity
                      key={u.id}
                      style={styles.userSelectItem}
                      onPress={() => {
                        handleAssignUser(u.id);
                        setShowAssignModal(false);
                      }}
                      data-testid={`select-user-${u.id}`}
                    >
                      <View style={styles.userAvatar}>
                        <Text style={styles.userAvatarText}>
                          {u.name.split(' ').map(n => n[0]).join('')}
                        </Text>
                      </View>
                      <View style={styles.userSelectInfo}>
                        <Text style={styles.userSelectName}>{u.name}</Text>
                        <Text style={styles.userSelectEmail}>{u.email}</Text>
                      </View>
                      <Ionicons name="add-circle" size={24} color="#34C759" />
                    </TouchableOpacity>
                  )
                ))
              )}
            </ScrollView>
          </Pressable>
        </Pressable>
      </WebModal>
    </SafeAreaView>
  );
}

const getStyles = (colors: any) => StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.bg,
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
    width: 40,
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
  },
  infoBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.card,
    padding: 12,
    marginHorizontal: 16,
    marginTop: 12,
    borderRadius: 10,
    gap: 10,
  },
  infoText: {
    flex: 1,
    fontSize: 15,
    color: colors.textSecondary,
  },
  content: {
    flex: 1,
    padding: 16,
  },
  inboxCard: {
    backgroundColor: colors.card,
    borderRadius: 16,
    padding: 16,
    marginBottom: 16,
  },
  inboxHeader: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    marginBottom: 16,
  },
  inboxIcon: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: '#007AFF20',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  inboxInfo: {
    flex: 1,
  },
  inboxName: {
    fontSize: 19,
    fontWeight: '600',
    color: colors.text,
  },
  inboxPhone: {
    fontSize: 16,
    color: '#007AFF',
    marginTop: 2,
  },
  inboxDescription: {
    fontSize: 15,
    color: colors.textSecondary,
    marginTop: 4,
  },
  deleteButton: {
    padding: 8,
  },
  assignedSection: {
    borderTopWidth: 1,
    borderTopColor: colors.surface,
    paddingTop: 12,
  },
  assignedHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  assignedTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.textSecondary,
  },
  addUserButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  addUserText: {
    fontSize: 16,
    color: '#007AFF',
  },
  noUsers: {
    fontSize: 16,
    color: colors.textSecondary,
    fontStyle: 'italic',
  },
  userChips: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  userChip: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    paddingVertical: 6,
    paddingHorizontal: 12,
    borderRadius: 20,
    gap: 6,
  },
  userChipText: {
    fontSize: 16,
    color: colors.text,
  },
  emptyState: {
    alignItems: 'center',
    paddingVertical: 60,
  },
  emptyText: {
    fontSize: 19,
    fontWeight: '600',
    color: colors.text,
    marginTop: 16,
  },
  emptySubtext: {
    fontSize: 16,
    color: colors.textSecondary,
    marginTop: 8,
    textAlign: 'center',
    paddingHorizontal: 40,
  },
  createButton: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#007AFF',
    paddingVertical: 12,
    paddingHorizontal: 20,
    borderRadius: 12,
    marginTop: 24,
    gap: 8,
  },
  createButtonText: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.8)',
    justifyContent: 'flex-end',
  },
  modalContent: {
    backgroundColor: colors.card,
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    maxHeight: '80%',
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: colors.surface,
  },
  modalTitle: {
    fontSize: 19,
    fontWeight: '600',
    color: colors.text,
  },
  modalBody: {
    padding: 16,
  },
  inputLabel: {
    fontSize: 16,
    color: colors.textSecondary,
    marginBottom: 8,
    marginTop: 12,
  },
  input: {
    backgroundColor: colors.surface,
    borderRadius: 10,
    padding: 14,
    fontSize: 18,
    color: colors.text,
  },
  textArea: {
    minHeight: 80,
    textAlignVertical: 'top',
  },
  submitButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#007AFF',
    borderRadius: 12,
    padding: 16,
    margin: 16,
    gap: 8,
  },
  submitButtonText: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
  },
  userSelectItem: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 12,
    borderBottomWidth: 1,
    borderBottomColor: colors.surface,
  },
  userAvatar: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: '#007AFF30',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  userAvatarText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#007AFF',
  },
  userSelectInfo: {
    flex: 1,
  },
  userSelectName: {
    fontSize: 18,
    fontWeight: '500',
    color: colors.text,
  },
  userSelectEmail: {
    fontSize: 15,
    color: colors.textSecondary,
  },
});
