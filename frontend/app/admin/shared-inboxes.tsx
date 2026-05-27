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
  Modal,
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { useAuthStore } from '../../store/authStore';
import { showSimpleAlert, showConfirm } from '../../services/alert';
import { useToast } from '../../components/common/Toast';
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
  const { showToast } = useToast();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [inboxes, setInboxes] = useState<SharedInbox[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  
  // Modals
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showAssignModal, setShowAssignModal] = useState(false);
  const [selectedInbox, setSelectedInbox] = useState<SharedInbox | null>(null);
  
  // Create form
  const [newInbox, setNewInbox] = useState({ name: '', phone_number: '', description: '' });
  const [twilioNumbers, setTwilioNumbers] = useState<any[]>([]);
  const [showNumberPicker, setShowNumberPicker] = useState(false);

  // Edit modal
  const [editingInbox, setEditingInbox] = useState<any | null>(null);
  const [editForm, setEditForm] = useState({ name: '', phone_number: '', description: '', va_profile_id: '', va_prompt_override: '' });
  const [savingEdit, setSavingEdit] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [vaProfiles, setVaProfiles] = useState<any[]>([]);
  const [showWebhook, setShowWebhook] = useState<string | null>(null);
  const [webhookInfo, setWebhookInfo] = useState<any | null>(null);

  useEffect(() => {
    if (user?._id) {
      loadData();
      loadTwilioNumbers();
      loadVaProfiles();
    }
  }, [user?._id]);

  const loadVaProfiles = async () => {
    try {
      const res = await api.get('/va-profiles', { headers: { 'X-User-ID': user?._id } });
      setVaProfiles(res.data.profiles || []);
    } catch { setVaProfiles([]); }
  };

  const openEdit = (inbox: any) => {
    setEditingInbox(inbox);
    setEditForm({
      name: inbox.name || '',
      phone_number: inbox.phone_number || '',
      description: inbox.description || '',
      va_profile_id: inbox.va_profile_id || '',
      va_prompt_override: inbox.va_prompt_override || '',
    });
    setShowEditModal(true);
  };

  const saveEdit = async () => {
    if (!editingInbox) return;
    setSavingEdit(true);
    try {
      await api.put(`/admin/team/shared-inboxes/${editingInbox.id}?user_id=${user?._id}`, editForm);
      setShowEditModal(false);
      showToast('Inbox updated', 'success');
      await loadData();
    } catch (e: any) {
      showToast(e?.response?.data?.detail || 'Save failed', 'error');
    } finally { setSavingEdit(false); }
  };

  const loadWebhookInfo = async (inboxId: string) => {
    try {
      const res = await api.get(`/admin/team/shared-inboxes/${inboxId}/webhook-info?user_id=${user?._id}`);
      setWebhookInfo(res.data);
      setShowWebhook(inboxId);
    } catch { showToast('Failed to load webhook info', 'error'); }
  };

  const loadTwilioNumbers = async () => {
    try {
      const res = await api.get('/admin/twilio/numbers', { headers: { 'X-User-ID': user?._id } });
      setTwilioNumbers(res.data.numbers || []);
    } catch { setTwilioNumbers([]); }
  };

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
        {/* Action buttons */}
        <View style={{ flexDirection: 'row', gap: 6 }}>
          <TouchableOpacity
            onPress={() => openEdit(inbox)}
            style={{ width: 34, height: 34, borderRadius: 8, backgroundColor: '#007AFF15', alignItems: 'center', justifyContent: 'center' }}
            data-testid={`edit-inbox-${inbox.id}`}
          >
            <Ionicons name="create-outline" size={17} color="#007AFF" />
          </TouchableOpacity>
          <TouchableOpacity
            onPress={() => loadWebhookInfo(inbox.id)}
            style={{ width: 34, height: 34, borderRadius: 8, backgroundColor: '#C9A96215', alignItems: 'center', justifyContent: 'center' }}
            data-testid={`webhook-inbox-${inbox.id}`}
          >
            <Ionicons name="link-outline" size={17} color="#C9A962" />
          </TouchableOpacity>
          <TouchableOpacity
            style={styles.deleteButton}
            onPress={() => handleDeleteInbox(inbox)}
            data-testid={`delete-inbox-${inbox.id}`}
          >
            <Ionicons name="trash-outline" size={20} color="#FF3B30" />
          </TouchableOpacity>
        </View>
      </View>

      {/* Webhook info panel */}
      {showWebhook === inbox.id && webhookInfo && (
        <View style={{ backgroundColor: colors.surface, borderRadius: 10, padding: 12, marginBottom: 10, borderWidth: 1, borderColor: '#C9A96230' }}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 8 }}>
            <Ionicons name="link" size={14} color="#C9A962" />
            <Text style={{ fontSize: 12, fontWeight: '700', color: '#C9A962', textTransform: 'uppercase', letterSpacing: 0.5 }}>WEBHOOK URL</Text>
            <TouchableOpacity onPress={() => setShowWebhook(null)} style={{ marginLeft: 'auto' as any }}>
              <Ionicons name="close" size={14} color={colors.textSecondary} />
            </TouchableOpacity>
          </View>
          <Text style={{ fontSize: 11, color: colors.text, fontFamily: 'monospace', backgroundColor: colors.card, borderRadius: 6, padding: 8, marginBottom: 8 }} selectable>
            {webhookInfo.webhook_url}
          </Text>
          <Text style={{ fontSize: 11, color: colors.textSecondary, marginBottom: 6 }}>POST this JSON from your web form:</Text>
          <Text style={{ fontSize: 10, color: colors.textSecondary, fontFamily: 'monospace', backgroundColor: colors.card, borderRadius: 6, padding: 8 }} selectable>
            {JSON.stringify(webhookInfo.example_payload, null, 2)}
          </Text>
        </View>
      )}

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
                {/* Dropdown from your Twilio numbers */}
                <TouchableOpacity
                  style={[styles.input, { justifyContent: 'space-between', flexDirection: 'row', alignItems: 'center' }]}
                  onPress={() => setShowNumberPicker(v => !v)}
                  data-testid="inbox-phone-picker"
                >
                  <Text style={{ color: newInbox.phone_number ? colors.text : colors.textSecondary, fontSize: 16 }}>
                    {newInbox.phone_number || 'Select a Twilio number...'}
                  </Text>
                  <Ionicons name="chevron-down" size={16} color={colors.textSecondary} />
                </TouchableOpacity>
                {showNumberPicker && (
                  <View style={{ backgroundColor: colors.card, borderRadius: 12, borderWidth: 1, borderColor: colors.border, marginTop: 4, overflow: 'hidden' }}>
                    {twilioNumbers.length === 0 ? (
                      <View style={{ padding: 16 }}>
                        <Text style={{ color: colors.textSecondary, fontSize: 14 }}>
                          No Twilio numbers available. Purchase one in Admin → Phone Numbers.
                        </Text>
                      </View>
                    ) : (
                      twilioNumbers.map((num: any) => {
                        const alreadyAssigned = num.assigned_to && num.status === 'assigned';
                        return (
                          <TouchableOpacity
                            key={num.phone_number}
                            onPress={() => {
                              setNewInbox({ ...newInbox, phone_number: num.phone_number });
                              setShowNumberPicker(false);
                            }}
                            style={{ paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: colors.border, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}
                          >
                            <View>
                              <Text style={{ color: colors.text, fontSize: 15, fontWeight: '600' }}>{num.phone_number}</Text>
                              <Text style={{ color: colors.textSecondary, fontSize: 12, marginTop: 2 }}>
                                {alreadyAssigned ? `Assigned to ${num.assigned_to?.name || 'rep'}` : (num.status === 'pool' ? 'In pool — available' : 'Available')}
                              </Text>
                            </View>
                            {newInbox.phone_number === num.phone_number && (
                              <Ionicons name="checkmark-circle" size={20} color={colors.accent} />
                            )}
                          </TouchableOpacity>
                        );
                      })
                    )}
                  </View>
                )}
                {/* Manual entry fallback */}
                {showNumberPicker === false && !newInbox.phone_number && (
                  <TouchableOpacity onPress={() => {
                    const manual = prompt('Enter phone number manually (E.164 format, e.g. +14351234567):');
                    if (manual) setNewInbox({ ...newInbox, phone_number: manual });
                  }} style={{ marginTop: 6 }}>
                    <Text style={{ color: colors.accent, fontSize: 13 }}>+ Enter number manually</Text>
                  </TouchableOpacity>
                )}
                
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

      {/* ── Edit Inbox Modal ─────────────────────────────────────────────── */}
      <Modal visible={showEditModal} animationType="slide" presentationStyle="pageSheet">
        <SafeAreaView style={{ flex: 1, backgroundColor: colors.background }}>
          <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 14, borderBottomWidth: 1, borderBottomColor: colors.border }}>
            <TouchableOpacity onPress={() => setShowEditModal(false)}>
              <Text style={{ color: '#FF3B30', fontSize: 16, fontWeight: '600' }}>Cancel</Text>
            </TouchableOpacity>
            <Text style={{ fontSize: 17, fontWeight: '700', color: colors.text }}>Edit Inbox</Text>
            <TouchableOpacity onPress={saveEdit} disabled={savingEdit} data-testid="save-edit-inbox-btn">
              {savingEdit ? <ActivityIndicator size="small" color="#007AFF" /> : <Text style={{ color: '#007AFF', fontSize: 16, fontWeight: '700' }}>Save</Text>}
            </TouchableOpacity>
          </View>

          <ScrollView contentContainerStyle={{ padding: 20, gap: 18, paddingBottom: 60 }}>
            <View>
              <Text style={[styles.inputLabel, { color: colors.textSecondary }]}>Inbox Name</Text>
              <TextInput style={[styles.input, { color: colors.text, backgroundColor: colors.surface, borderColor: colors.border }]} value={editForm.name} onChangeText={v => setEditForm(p => ({ ...p, name: v }))} placeholder="KSL Inbox" placeholderTextColor={colors.textSecondary} />
            </View>
            <View>
              <Text style={[styles.inputLabel, { color: colors.textSecondary }]}>Phone Number</Text>
              <TextInput style={[styles.input, { color: colors.text, backgroundColor: colors.surface, borderColor: colors.border }]} value={editForm.phone_number} onChangeText={v => setEditForm(p => ({ ...p, phone_number: v }))} placeholder="+13854443045" placeholderTextColor={colors.textSecondary} keyboardType="phone-pad" />
            </View>
            <View>
              <Text style={[styles.inputLabel, { color: colors.textSecondary }]}>Description</Text>
              <TextInput style={[styles.input, { height: 70, textAlignVertical: 'top', color: colors.text, backgroundColor: colors.surface, borderColor: colors.border }]} value={editForm.description} onChangeText={v => setEditForm(p => ({ ...p, description: v }))} multiline placeholder="What is this inbox for?" placeholderTextColor={colors.textSecondary} />
            </View>

            {/* VA Profile */}
            <View>
              <Text style={[styles.inputLabel, { color: colors.textSecondary }]}>VA Profile</Text>
              <Text style={{ fontSize: 12, color: colors.textSecondary, marginBottom: 8 }}>Assign a Virtual Assistant from your VA Library to handle leads from this inbox.</Text>
              {vaProfiles.length === 0 ? (
                <TouchableOpacity onPress={() => { setShowEditModal(false); router.push('/admin/va-library' as any); }} style={{ borderRadius: 10, borderWidth: 1, borderColor: colors.border, padding: 12, flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                  <Ionicons name="person-circle-outline" size={18} color="#C9A962" />
                  <Text style={{ color: '#C9A962', fontWeight: '600' }}>Create a VA in VA Library first →</Text>
                </TouchableOpacity>
              ) : (
                <View style={{ gap: 8 }}>
                  <TouchableOpacity
                    onPress={() => setEditForm(p => ({ ...p, va_profile_id: '' }))}
                    style={{ flexDirection: 'row', alignItems: 'center', gap: 8, padding: 10, borderRadius: 10, backgroundColor: !editForm.va_profile_id ? colors.accent + '20' : colors.surface, borderWidth: 1, borderColor: !editForm.va_profile_id ? colors.accent : colors.border }}
                  >
                    <Ionicons name="close-circle-outline" size={18} color={!editForm.va_profile_id ? colors.accent : colors.textSecondary} />
                    <Text style={{ color: !editForm.va_profile_id ? colors.accent : colors.text, fontWeight: '600' }}>No VA (manual only)</Text>
                  </TouchableOpacity>
                  {vaProfiles.map((va: any) => (
                    <TouchableOpacity
                      key={va._id}
                      onPress={() => setEditForm(p => ({ ...p, va_profile_id: va._id }))}
                      style={{ flexDirection: 'row', alignItems: 'center', gap: 10, padding: 10, borderRadius: 10, backgroundColor: editForm.va_profile_id === va._id ? va.avatar_color + '20' : colors.surface, borderWidth: 1, borderColor: editForm.va_profile_id === va._id ? va.avatar_color : colors.border }}
                    >
                      <View style={{ width: 32, height: 32, borderRadius: 16, backgroundColor: va.avatar_color + '30', alignItems: 'center', justifyContent: 'center' }}>
                        <Text style={{ color: va.avatar_color, fontWeight: '800', fontSize: 14 }}>{va.name.charAt(0)}</Text>
                      </View>
                      <View style={{ flex: 1 }}>
                        <Text style={{ color: colors.text, fontWeight: '600' }}>{va.name}</Text>
                        {va.tagline ? <Text style={{ color: colors.textSecondary, fontSize: 12 }}>{va.tagline}</Text> : null}
                      </View>
                      {editForm.va_profile_id === va._id && <Ionicons name="checkmark-circle" size={20} color={va.avatar_color} />}
                    </TouchableOpacity>
                  ))}
                </View>
              )}
            </View>

            {/* Custom prompt override */}
            <View>
              <Text style={[styles.inputLabel, { color: colors.textSecondary }]}>Custom VA Instructions (optional)</Text>
              <TextInput style={[styles.input, { height: 80, textAlignVertical: 'top', color: colors.text, backgroundColor: colors.surface, borderColor: colors.border }]} value={editForm.va_prompt_override} onChangeText={v => setEditForm(p => ({ ...p, va_prompt_override: v }))} multiline placeholder="E.g. 'These are KSL classified leads, focus on price and availability first'" placeholderTextColor={colors.textSecondary} />
            </View>
          </ScrollView>
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
